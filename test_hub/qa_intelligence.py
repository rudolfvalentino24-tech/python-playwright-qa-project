import os
import re
from collections import defaultdict
from typing import Literal

try:
    from openai import OpenAI
    from pydantic import BaseModel, Field
except ImportError:  # The Test Hub can still use deterministic assistance without AI dependencies.
    OpenAI = None
    BaseModel = object
    Field = None


OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.6-terra").strip()
STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in", "is",
    "it", "of", "on", "or", "that", "the", "this", "to", "with", "user", "users",
    "should", "when", "then", "can", "will", "new", "add", "change", "feature",
}


if BaseModel is not object:
    class ImpactCase(BaseModel):
        case_key: str
        relevance: Literal["Required", "Regression", "Consider"]
        reason: str


    class ImpactAnalysis(BaseModel):
        summary: str
        risks: list[str] = Field(default_factory=list)
        cases: list[ImpactCase] = Field(default_factory=list)


    class FailureClusterSummary(BaseModel):
        summary: str
        likely_common_causes: list[str] = Field(default_factory=list)
        next_checks: list[str] = Field(default_factory=list)


def _tokens(value):
    return {
        token
        for token in re.findall(r"[a-z0-9]{3,}", (value or "").lower())
        if token not in STOP_WORDS
    }


def _risk_score_from_profile(profile, case=None):
    levels = {"Low": 1, "Medium": 2, "High": 3, "Critical": 4}
    if profile is not None:
        return sum(
            levels.get(getattr(profile, field, "Medium"), 2)
            for field in ("business_impact", "change_complexity", "regression_risk", "user_frequency")
        )
    # Unassessed cases still get a small ordering signal from their existing priority.
    return levels.get(getattr(case, "priority", "Medium"), 2) + 5


def _risk_label(score):
    if score >= 14:
        return "Critical"
    if score >= 11:
        return "High"
    if score >= 8:
        return "Medium"
    return "Low"


def _risk_profiles(hub):
    model = getattr(hub, "QaRiskProfile", None)
    if model is None:
        return {}
    return {
        profile.test_case_id: profile
        for profile in hub.db.session.scalars(hub.db.select(model)).all()
    }


def _release_case_ids(hub, release_id):
    if not release_id:
        return None
    case_ids = set()

    # Prefer planned release scope when Test Plans are linked to the Release.
    link_model = getattr(hub, "TestPlanReleaseLink", None)
    if link_model is not None and hasattr(hub, "TestPlanItem"):
        plan_ids = list(
            hub.db.session.scalars(
                hub.db.select(link_model.test_plan_id).where(link_model.release_id == release_id)
            ).all()
        )
        if plan_ids:
            case_ids.update(
                case_id
                for case_id in hub.db.session.scalars(
                    hub.db.select(hub.TestPlanItem.test_case_id).where(
                        hub.TestPlanItem.test_plan_id.in_(plan_ids),
                        hub.TestPlanItem.test_case_id.is_not(None),
                    )
                ).all()
                if case_id is not None
            )

    # Include cases that already appear in Release Test Runs as execution evidence.
    run_ids = list(
        hub.db.session.scalars(
            hub.db.select(hub.TestRun.id).where(hub.TestRun.release_id == release_id)
        ).all()
    )
    if run_ids:
        case_ids.update(
            case_id
            for case_id in hub.db.session.scalars(
                hub.db.select(hub.TestRunItem.test_case_id).where(
                    hub.TestRunItem.test_run_id.in_(run_ids),
                    hub.TestRunItem.test_case_id.is_not(None),
                )
            ).all()
            if case_id is not None
        )
    return case_ids


def suggest_affected_cases(hub, change_description, jira_key="", release_id=None, limit=30):
    """Suggest affected existing cases; the tester remains responsible for choosing the run scope."""
    change_tokens = _tokens(change_description)
    jira_key = (jira_key or "").strip().upper()
    profiles = _risk_profiles(hub)
    release_case_ids = _release_case_ids(hub, release_id)

    cases = hub.db.session.scalars(
        hub.db.select(hub.TestCase).order_by(hub.TestCase.case_key)
    ).all()
    rows = []
    for case in cases:
        if release_case_ids is not None and release_case_ids and case.id not in release_case_ids:
            # Release filtering narrows the suggestion set only when a real release scope exists.
            continue

        searchable = " ".join(
            [
                case.case_key or "",
                case.title or "",
                case.feature_name or "",
                case.preconditions or "",
                case.expected_result or "",
                " ".join(case.jira_keys),
                " ".join(case.suite_tag_list),
            ]
        )
        case_tokens = _tokens(searchable)
        overlap = sorted(change_tokens & case_tokens)
        score = 0.0
        reasons = []

        if jira_key and jira_key in case.jira_keys:
            score += 8
            reasons.append(f"directly linked to {jira_key}")
        if overlap:
            overlap_score = min(len(overlap), 5) * 1.4
            score += overlap_score
            reasons.append("matches change terms: " + ", ".join(overlap[:5]))
        if "regression" in case.suite_tag_list:
            score += 1.2
            reasons.append("regression coverage")
        if "smoke" in case.suite_tag_list:
            score += 1.0
            reasons.append("smoke coverage")
        if "release" in case.suite_tag_list:
            score += 0.8
            reasons.append("release coverage")

        risk_score = _risk_score_from_profile(profiles.get(case.id), case)
        if risk_score >= 11:
            score += 1.5
            reasons.append(f"{_risk_label(risk_score).lower()} QA risk")

        if not change_tokens and not jira_key:
            # With no change description, surface risk/regression candidates rather than arbitrary title matches.
            score += max(0, risk_score - 7) * 0.2

        if score <= 0:
            continue
        if score >= 7:
            relevance = "Required"
        elif score >= 3:
            relevance = "Regression"
        else:
            relevance = "Consider"
        rows.append(
            {
                "case": case,
                "score": round(score, 1),
                "relevance": relevance,
                "reason": "; ".join(reasons) or "related existing coverage",
                "risk_score": risk_score,
                "risk_label": _risk_label(risk_score),
            }
        )

    rows.sort(key=lambda row: (-row["score"], -row["risk_score"], row["case"].case_key))
    return rows[:limit]


def automation_health(hub, window=20):
    rows = []
    for case in hub.db.session.scalars(
        hub.db.select(hub.TestCase).where(hub.TestCase.type == "Automated").order_by(hub.TestCase.case_key)
    ).all():
        attempts = [result for result in case.results if result.result in {"Passed", "Failed"}][:window]
        if not attempts:
            rows.append({"case": case, "state": "Never executed", "attempts": 0, "failed": 0, "flake_rate": 0.0})
            continue
        failed = sum(1 for result in attempts if result.result == "Failed")
        passed = sum(1 for result in attempts if result.result == "Passed")
        failure_rate = round((failed / len(attempts)) * 100, 1)
        latest = attempts[0].result
        if failed and passed and 5 <= failure_rate <= 70:
            state = "Potentially flaky"
        elif latest == "Failed" and failure_rate > 70:
            state = "Consistently failing"
        else:
            state = "Stable"
        rows.append(
            {
                "case": case,
                "state": state,
                "attempts": len(attempts),
                "failed": failed,
                "passed": passed,
                "flake_rate": failure_rate,
                "latest": latest,
            }
        )
    order = {"Consistently failing": 0, "Potentially flaky": 1, "Never executed": 2, "Stable": 3}
    rows.sort(key=lambda row: (order.get(row["state"], 9), -row.get("flake_rate", 0), row["case"].case_key))
    return rows


def _failure_category(message):
    text = (message or "").lower()
    if any(word in text for word in ("timeout", "timed out", "waiting for")):
        return "Timeout / waiting"
    if any(word in text for word in ("locator", "selector", "not found", "strict mode")):
        return "Locator / UI element"
    if any(word in text for word in ("assert", "expected", "received", "mismatch")):
        return "Assertion mismatch"
    if any(word in text for word in ("500", "502", "503", "network", "connection", "request failed")):
        return "Network / service"
    if any(word in text for word in ("login", "auth", "token", "unauthorized", "forbidden")):
        return "Authentication / authorization"
    return "Other failure"


def _normalize_failure(message):
    text = (message or "No error message recorded").lower()
    text = re.sub(r"https?://\S+", "<url>", text)
    text = re.sub(r"[a-z]:\\[^\s]+|/[^\s:]+(?:/[^\s:]+)+", "<path>", text)
    text = re.sub(r"\b[0-9a-f]{8}-[0-9a-f-]{27,}\b", "<id>", text)
    text = re.sub(r"\b\d+(?:\.\d+)?\b", "<n>", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:180]


def failure_clusters(hub, release_id=None, limit=80):
    statement = hub.db.select(hub.TestResult).where(hub.TestResult.result == "Failed")
    if release_id:
        statement = statement.join(hub.TestRun, hub.TestResult.test_run_id == hub.TestRun.id).where(
            hub.TestRun.release_id == release_id
        )
    results = hub.db.session.scalars(statement.order_by(hub.TestResult.executed_at.desc()).limit(limit)).all()

    clusters = defaultdict(list)
    for result in results:
        category = _failure_category(result.error_message or result.notes)
        signature = _normalize_failure(result.error_message or result.notes)
        clusters[(category, signature)].append(result)

    rows = []
    for (category, signature), items in clusters.items():
        case_keys = []
        for result in items:
            if result.case_key_snapshot not in case_keys:
                case_keys.append(result.case_key_snapshot)
        rows.append(
            {
                "category": category,
                "signature": signature,
                "count": len(items),
                "case_keys": case_keys,
                "sample": items[0],
            }
        )
    rows.sort(key=lambda row: (-row["count"], row["category"], row["signature"]))
    return rows


def ai_impact_analysis(hub, change_description, jira_key="", release_id=None):
    suggestions = suggest_affected_cases(hub, change_description, jira_key, release_id, limit=30)
    fallback = {
        "provider": "deterministic",
        "summary": f"{len(suggestions)} existing Test Cases matched the change context.",
        "risks": [
            f"{row['case'].case_key}: {row['reason']}"
            for row in suggestions[:5]
            if row["risk_label"] in {"High", "Critical"}
        ],
        "cases": [
            {
                "case_key": row["case"].case_key,
                "relevance": row["relevance"],
                "reason": row["reason"],
            }
            for row in suggestions
        ],
        "suggestions": suggestions,
    }

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key or OpenAI is None or BaseModel is object or not suggestions:
        return fallback

    compact_cases = "\n".join(
        f"- {row['case'].case_key} | {row['case'].feature_name} | {row['case'].title} | "
        f"priority={row['case'].priority} | tags={','.join(row['case'].suite_tag_list) or 'none'} | "
        f"heuristic={row['relevance']} | {row['reason']}"
        for row in suggestions
    )
    instructions = """You are a QA impact-analysis assistant inside Test Hub.
Use only the existing Test Cases supplied to you. Do not invent Test Case IDs.
Classify relevant existing cases as Required, Regression, or Consider and explain why.
Identify concrete testing risks from the change description. The tester makes the final scope decision.
Keep the answer concise and practical."""
    user_input = f"""Change / acceptance criteria:
{change_description}

Jira key: {jira_key or 'not supplied'}

Candidate existing Test Cases:
{compact_cases}
"""
    try:
        client = OpenAI(api_key=api_key)
        response = client.responses.parse(
            model=OPENAI_MODEL,
            input=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": user_input},
            ],
            text_format=ImpactAnalysis,
        )
        parsed = response.output_parsed
        if parsed is None:
            return fallback
        by_key = {row["case"].case_key: row for row in suggestions}
        ai_cases = []
        for item in parsed.cases:
            row = by_key.get(item.case_key)
            if row is None:
                continue
            ai_cases.append(
                {
                    "case_key": item.case_key,
                    "relevance": item.relevance,
                    "reason": item.reason,
                    "row": row,
                }
            )
        return {
            "provider": "OpenAI",
            "summary": parsed.summary,
            "risks": parsed.risks,
            "cases": ai_cases,
            "suggestions": suggestions,
        }
    except Exception as exc:
        fallback["warning"] = f"AI analysis was unavailable, so Test Hub used deterministic impact analysis: {exc}"
        return fallback


def ai_failure_summary(hub, release_id=None):
    clusters = failure_clusters(hub, release_id=release_id)
    fallback = {
        "provider": "deterministic",
        "summary": f"{sum(row['count'] for row in clusters)} recent failed results form {len(clusters)} failure groups.",
        "likely_common_causes": [
            f"{row['category']}: {row['count']} failure(s) across {', '.join(row['case_keys'][:5])}"
            for row in clusters[:5]
        ],
        "next_checks": [
            "Inspect the largest cluster first and compare its Jenkins evidence across affected Test Cases."
        ] if clusters else [],
        "clusters": clusters,
    }
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key or OpenAI is None or BaseModel is object or not clusters:
        return fallback

    cluster_text = "\n".join(
        f"- {row['category']} | count={row['count']} | cases={','.join(row['case_keys'])} | signature={row['signature']}"
        for row in clusters[:12]
    )
    instructions = """You are a QA failure-triage assistant.
Summarize only the supplied failure groups. Do not claim a root cause is proven.
Identify plausible common causes and concrete next checks. Distinguish evidence from hypothesis."""
    try:
        client = OpenAI(api_key=api_key)
        response = client.responses.parse(
            model=OPENAI_MODEL,
            input=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": cluster_text},
            ],
            text_format=FailureClusterSummary,
        )
        parsed = response.output_parsed
        if parsed is None:
            return fallback
        return {
            "provider": "OpenAI",
            "summary": parsed.summary,
            "likely_common_causes": parsed.likely_common_causes,
            "next_checks": parsed.next_checks,
            "clusters": clusters,
        }
    except Exception as exc:
        fallback["warning"] = f"AI failure summary was unavailable, so Test Hub used deterministic clustering: {exc}"
        return fallback


def register_qa_intelligence(hub):
    """Expose impact analysis, automation health and failure clustering to the QA workflow layer."""
    if getattr(hub.app, "_qa_intelligence_registered", False):
        return
    hub.qa_suggest_affected_cases = lambda change_description, jira_key="", release_id=None, limit=30: suggest_affected_cases(
        hub, change_description, jira_key, release_id, limit
    )
    hub.qa_automation_health = lambda window=20: automation_health(hub, window)
    hub.qa_failure_clusters = lambda release_id=None, limit=80: failure_clusters(hub, release_id, limit)
    hub.qa_ai_impact_analysis = lambda change_description, jira_key="", release_id=None: ai_impact_analysis(
        hub, change_description, jira_key, release_id
    )
    hub.qa_ai_failure_summary = lambda release_id=None: ai_failure_summary(hub, release_id)
    hub.app._qa_intelligence_registered = True
