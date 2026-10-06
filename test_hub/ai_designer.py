import os
import re
from datetime import datetime, timezone
from typing import Literal

from openai import OpenAI
from pydantic import BaseModel, Field


OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.6-terra").strip()
ALLOWED_SUITE_TAGS = {"smoke", "regression", "release"}
BDD_STEP_PATTERN = re.compile(r"^(Given|When|Then|And|But)\s+.+", re.IGNORECASE)
BDD_DEFINITION_PROVIDER = None


class SuggestedTestCase(BaseModel):
    case_key: str
    title: str
    priority: Literal["Low", "Medium", "High", "Critical"]
    type: Literal["Manual", "Automated"]
    suite_tags: list[Literal["smoke", "regression", "release"]] = Field(default_factory=list)
    preconditions: str = ""
    steps: list[str] = Field(min_length=1, max_length=15)
    expected_result: str
    coverage_reason: str
    planned_coverage_id: int | None = None


class SuggestedTestPlan(BaseModel):
    feature_summary: str
    test_cases: list[SuggestedTestCase] = Field(min_length=1, max_length=12)


DESIGNER_PAGE_HTML = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI Test Designer - Test Hub</title>
<style>
:root{--surface:rgba(255,255,255,.96);--text:#111827;--muted:#6b7280;--border:#d7dfec;--accent:#2f66e8;font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
*{box-sizing:border-box}body{margin:0;min-height:100vh;color:var(--text);background:radial-gradient(circle at 8% 5%,rgba(98,134,255,.17),transparent 28%),radial-gradient(circle at 94% 16%,rgba(36,117,255,.11),transparent 24%),linear-gradient(180deg,#f8faff,#eef3fb)}
header{display:flex;align-items:center;justify-content:space-between;padding:16px 30px;background:rgba(20,42,82,.94);color:#fff}.brand{display:flex;align-items:center;gap:12px}.icon{width:42px;height:42px;display:grid;place-items:center;border-radius:13px;background:linear-gradient(135deg,#6286ff,#1f63f2);font-size:21px}.brand strong{font-size:20px}.brand span{display:block;font-size:12px;opacity:.7}.button{padding:10px 14px;border-radius:10px;background:#eef2f7;color:#20324f;text-decoration:none;font-weight:750}
main{max-width:920px;margin:0 auto;padding:34px 22px 50px}.card{padding:27px;border:1px solid var(--border);border-radius:20px;background:var(--surface);box-shadow:0 18px 50px rgba(35,61,108,.08)}h1{margin:0 0 6px;color:#172b4d;font-size:30px}.subtitle{margin-bottom:24px;color:var(--muted);line-height:1.5}.field{margin-bottom:16px}.field label{display:block;margin-bottom:6px;font-size:12px;font-weight:800;color:#41526c}.grid{display:grid;grid-template-columns:1fr 1fr;gap:13px}input,select,textarea,button{font:inherit}input,select,textarea{width:100%;border:1px solid #ccd5e4;border-radius:11px;background:#fff;outline:none}input,select{height:47px;padding:0 13px}textarea{min-height:190px;padding:12px 13px;resize:vertical;line-height:1.5}input:focus,select:focus,textarea:focus{border-color:#3b73ef;box-shadow:0 0 0 4px rgba(59,115,239,.12)}.primary{border:0;border-radius:10px;padding:12px 17px;background:linear-gradient(90deg,#2f66e8,#2475ff);color:#fff;font-weight:800;cursor:pointer;box-shadow:0 8px 18px rgba(37,99,235,.2)}.hint{margin-top:6px;font-size:12px;color:#7a8798}.error{margin-bottom:18px;padding:13px 15px;border:1px solid #f2b8b5;border-radius:11px;background:#fff1f0;color:#9f1c16}.info{margin-bottom:20px;padding:14px 16px;border-radius:12px;background:#edf4ff;color:#294a7a;line-height:1.45;font-size:13px}@media(max-width:650px){header{padding:13px 16px}main{padding:20px 14px}.grid{grid-template-columns:1fr}}
</style>
</head>
<body>
<header><div class="brand"><div class="icon">✨</div><div><strong>AI Test Designer</strong><span>Test Hub</span></div></div><a class="button" href="{{ url_for('index') }}">Back to Test Hub</a></header>
<main><section class="card">
<h1>Design tests from a feature</h1>
<div class="subtitle">Describe the requirement or acceptance criteria. AI will propose structured test cases, compare them with your existing coverage, and let you review everything before anything is created.</div>
{% if error %}<div class="error">{{ error }}</div>{% endif %}
<div class="info">Generated cases are drafts. Automated suggestions use Given / When / Then steps and prefer your existing BDD vocabulary where possible.</div>
<form method="post" action="{{ url_for('ai_generate_test_cases') }}">
  <div class="field"><label>Feature / Module</label><input name="feature" required value="{{ feature or '' }}" placeholder="Password Reset"></div>
  <div class="field"><label>Test Plan (optional)</label><select name="test_plan_id"><option value="">No Test Plan</option>{% for test_plan in test_plans %}<option value="{{ test_plan.id }}" {% if test_plan_id|string == test_plan.id|string %}selected{% endif %}>{{ test_plan.name }} · {{ test_plan.status }}</option>{% endfor %}</select><div class="hint">Approved cases will become Covered items in this Test Plan.</div></div>
  <div class="field"><label>Feature description / acceptance criteria</label><textarea name="requirement" required placeholder="Users can request a password reset...">{{ requirement or '' }}</textarea><div class="hint">Include business rules, permissions, validations and important edge cases you already know.</div></div>
  <div class="grid">
    <div class="field"><label>Number of suggestions</label><select name="count">{% for value in range(3,13) %}<option value="{{ value }}" {% if value == count %}selected{% endif %}>{{ value }}</option>{% endfor %}</select></div>
    <div class="field"><label>Preferred test type</label><select name="preference"><option {% if preference == 'Automated' %}selected{% endif %}>Automated</option><option {% if preference == 'Mixed' %}selected{% endif %}>Mixed</option><option {% if preference == 'Manual' %}selected{% endif %}>Manual</option></select></div>
  </div>
  <div class="field"><label>Jira stories (optional)</label><input name="jira_keys" value="{{ jira_keys or '' }}" placeholder="SCRUM-12, SCRUM-13"><div class="hint">All approved cases will inherit these Jira links.</div></div>
  <button class="primary" type="submit">✨ Generate test cases</button>
</form>
</section></main>
</body>
</html>
"""


REVIEW_PAGE_HTML = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Review AI Test Cases - Test Hub</title>
<style>
:root{--surface:rgba(255,255,255,.96);--text:#111827;--muted:#6b7280;--border:#d7dfec;--accent:#2f66e8;font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}*{box-sizing:border-box}body{margin:0;min-height:100vh;color:var(--text);background:linear-gradient(180deg,#f8faff,#eef3fb)}header{display:flex;align-items:center;justify-content:space-between;padding:16px 30px;background:rgba(20,42,82,.94);color:#fff}.button{padding:10px 14px;border-radius:10px;background:#eef2f7;color:#20324f;text-decoration:none;font-weight:750}main{max-width:1180px;margin:0 auto;padding:30px 22px 50px}h1{margin:0;color:#172b4d}.subtitle{margin:6px 0 22px;color:var(--muted)}.summary{margin-bottom:18px;padding:15px 17px;border:1px solid #cddcf8;border-radius:13px;background:#edf4ff;color:#294a7a}.case{margin:14px 0;padding:19px;border:1px solid var(--border);border-radius:17px;background:var(--surface);box-shadow:0 12px 34px rgba(35,61,108,.06)}.case-head{display:flex;gap:11px;align-items:flex-start}.case-head>input{width:19px;height:19px;margin-top:12px}.fields{flex:1;min-width:0}.grid{display:grid;grid-template-columns:160px 1fr 140px 140px;gap:10px}.field{margin-top:10px}.field label{display:block;margin-bottom:5px;font-size:11px;font-weight:800;color:#56667b}input,select,textarea,button{font:inherit}input,select,textarea{width:100%;border:1px solid #ccd5e4;border-radius:9px;background:#fff;outline:none}input,select{height:40px;padding:0 10px}textarea{min-height:88px;padding:9px 10px;resize:vertical;line-height:1.4}.tag-options{display:flex;gap:8px;flex-wrap:wrap}.tag-option{display:flex!important;align-items:center;gap:7px;margin:0!important;padding:8px 10px;border:1px solid #d7dfec;border-radius:9px;background:#fff;color:#41526c;font-size:12px;font-weight:750}.tag-option input{width:16px!important;height:16px!important;margin:0!important}.warning{margin-top:9px;padding:9px 11px;border-radius:9px;background:#fff4dd;color:#8a5d00;font-size:12px;font-weight:700}.reason{margin-top:9px;color:#607087;font-size:12px}.actions{position:sticky;bottom:12px;display:flex;justify-content:flex-end;gap:8px;margin-top:20px;padding:13px;border:1px solid var(--border);border-radius:14px;background:rgba(255,255,255,.94);box-shadow:0 12px 35px rgba(35,61,108,.12);backdrop-filter:blur(10px)}.primary{border:0;border-radius:10px;padding:11px 16px;background:linear-gradient(90deg,#2f66e8,#2475ff);color:#fff;font-weight:800;cursor:pointer}.secondary{border:0;border-radius:10px;padding:11px 16px;background:#eef2f7;color:#20324f;text-decoration:none;font-weight:750}@media(max-width:850px){.grid{grid-template-columns:1fr 1fr}}@media(max-width:560px){header{padding:13px 16px}main{padding:20px 12px}.grid{grid-template-columns:1fr}}
</style>
</head>
<body>
<header><strong>✨ AI Test Designer · Review</strong><a class="button" href="{{ url_for('ai_test_designer') }}">Start over</a></header>
<main><h1>Review generated test cases</h1><div class="subtitle">Edit anything you want, uncheck cases you do not want, then create only the selected drafts.</div>
<div class="summary"><strong>{{ feature }}</strong> — {{ plan.feature_summary }}<br>{{ suggestions|length }} suggestions generated with {{ model }}.{% if selected_test_plan %}<br><strong>Test Plan:</strong> {{ selected_test_plan.name }}{% endif %}</div>
<form method="post" action="{{ url_for('ai_create_selected_cases') }}">
<input type="hidden" name="feature" value="{{ feature }}"><input type="hidden" name="jira_keys" value="{{ jira_keys }}"><input type="hidden" name="test_plan_id" value="{{ test_plan_id or '' }}"><input type="hidden" name="suggestion_count" value="{{ suggestions|length }}">
{% for item in suggestions %}
<section class="case"><div class="case-head"><input type="checkbox" name="selected" value="{{ loop.index0 }}" {% if not item.duplicate_reason %}checked{% endif %}><div class="fields">
<input type="hidden" name="planned_coverage_id_{{ loop.index0 }}" value="{{ item.planned_item.id if item.planned_item else '' }}">
<div class="grid">
<div class="field"><label>Test case ID</label><input name="case_key_{{ loop.index0 }}" value="{{ item.case.case_key }}"></div>
<div class="field"><label>Title</label><input name="title_{{ loop.index0 }}" value="{{ item.case.title }}"></div>
<div class="field"><label>Priority</label><select name="priority_{{ loop.index0 }}">{% for p in priorities %}<option {% if p == item.case.priority %}selected{% endif %}>{{ p }}</option>{% endfor %}</select></div>
<div class="field"><label>Type</label><select name="type_{{ loop.index0 }}"><option {% if item.case.type == 'Automated' %}selected{% endif %}>Automated</option><option {% if item.case.type == 'Manual' %}selected{% endif %}>Manual</option></select></div>
</div>
<div class="field"><label>Suite tags</label><div class="tag-options">{% for tag in ['smoke','regression','release'] %}<label class="tag-option"><input type="checkbox" name="suite_tags_{{ loop.index0 }}" value="{{ tag }}" {% if tag in item.case.suite_tags %}checked{% endif %}>{{ tag|capitalize }}</label>{% endfor %}</div></div>
<div class="field"><label>Preconditions</label><textarea name="preconditions_{{ loop.index0 }}">{{ item.case.preconditions }}</textarea></div>
<div class="field"><label>Steps — one per line</label><textarea name="steps_{{ loop.index0 }}">{{ item.case.steps|join('\n') }}</textarea></div>
<div class="field"><label>Expected result</label><textarea name="expected_result_{{ loop.index0 }}">{{ item.case.expected_result }}</textarea></div>
{% if item.planned_item %}<div class="reason"><strong>Planned coverage:</strong> {{ item.planned_item.title_snapshot }}</div>{% endif %}
{% if item.duplicate_reason %}<div class="warning">⚠ {{ item.duplicate_reason }} Edit it before selecting this case.</div>{% endif %}
<div class="reason"><strong>Why AI suggested it:</strong> {{ item.case.coverage_reason }}</div>
</div></div></section>
{% endfor %}
<div class="actions"><a class="secondary" href="{{ url_for('ai_test_designer') }}">Cancel</a><button class="primary" type="submit">Create selected drafts</button></div>
</form></main></body></html>
"""


def _implemented_bdd_context():
    # Reuse the real pytest-bdd scanner when Test Hub provides it from run_ai.py.
    if not callable(BDD_DEFINITION_PROVIDER):
        return "- Implemented BDD scanner is not available"

    try:
        definitions = BDD_DEFINITION_PROVIDER() or []
    except Exception as exc:
        return f"- Implemented BDD scan failed: {exc}"

    rows = []
    seen = set()
    for definition in definitions:
        text = str(definition.get("text") or "").strip()
        if not text or text.lower() in seen:
            continue
        seen.add(text.lower())
        source = str(definition.get("source") or "").strip()
        rows.append(f"- {text}" + (f" [{source}]" if source else ""))
        if len(rows) >= 200:
            break
    return "\n".join(rows) or "- No implemented BDD step definitions"


def _existing_context(hub):
    cases = hub.db.session.scalars(
        hub.db.select(hub.TestCase).order_by(hub.TestCase.feature, hub.TestCase.case_key)
    ).all()
    existing_cases = "\n".join(
        f"- {case.case_key} [{case.feature_name}] {case.title} ({case.type})"
        for case in cases
    ) or "- No existing test cases"

    step_actions = []
    seen = set()
    for case in cases:
        if case.type != "Automated":
            continue
        for step in case.steps:
            action = step.action.strip()
            if action and BDD_STEP_PATTERN.match(action) and action.lower() not in seen:
                seen.add(action.lower())
                step_actions.append(action)

    stored_steps = "\n".join(f"- {step}" for step in step_actions[:150]) or "- No stored Test Hub BDD steps"
    return existing_cases, stored_steps, _implemented_bdd_context()


def _test_plan_jira_keys(hub, test_plan):
    if test_plan is None:
        return []
    model = getattr(hub, "TestPlanJiraLink", None)
    if model is None:
        return []
    return list(
        hub.db.session.scalars(
            hub.db.select(model.jira_key)
            .where(model.test_plan_id == test_plan.id)
            .order_by(model.jira_key)
        ).all()
    )


def _test_plan_context(hub, test_plan):
    if test_plan is None:
        return "- No Test Plan selected"

    lines = [
        f"Name: {test_plan.name}",
        f"Status: {test_plan.status}",
        f"Plan type: {getattr(test_plan, 'plan_type', '') or 'Not defined'}",
        f"Application: {getattr(test_plan, 'application', '') or 'Not defined'}",
        f"Feature / Module: {getattr(test_plan, 'feature', '') or 'Not defined'}",
        f"Summary / Context: {getattr(test_plan, 'description', '') or 'Not defined'}",
        f"Objective: {getattr(test_plan, 'objective', '') or 'Not defined'}",
        f"In Scope: {getattr(test_plan, 'in_scope', '') or 'Not defined'}",
        f"Out of Scope: {getattr(test_plan, 'out_of_scope', '') or 'Not defined'}",
        f"Risks / Edge Cases: {getattr(test_plan, 'risks', '') or 'Not defined'}",
        f"Environment: {getattr(test_plan, 'environment', '') or 'Not defined'}",
        f"Entry Criteria: {getattr(test_plan, 'entry_criteria', '') or 'Not defined'}",
        f"Exit Criteria: {getattr(test_plan, 'exit_criteria', '') or 'Not defined'}",
    ]

    pending = [item for item in test_plan.items if item.test_case is None]
    covered = [item for item in test_plan.items if item.test_case is not None]

    lines.append("Pending planned coverage:")
    if pending:
        for item in pending:
            notes = f" | Notes: {item.notes}" if item.notes else ""
            lines.append(
                f"- ID {item.id}: [{item.feature_snapshot or 'Uncategorized'}] "
                f"{item.title_snapshot}{notes}"
            )
    else:
        lines.append("- None")

    lines.append("Already covered Test Plan items:")
    if covered:
        for item in covered:
            lines.append(
                f"- {item.test_case.case_key}: [{item.feature_snapshot or item.test_case.feature_name}] "
                f"{item.title_snapshot}"
            )
    else:
        lines.append("- None")

    plan_jira_keys = _test_plan_jira_keys(hub, test_plan)
    lines.append("Test Plan Jira scope: " + (", ".join(plan_jira_keys) if plan_jira_keys else "None"))
    return "\n".join(lines)


def _jira_description_text(value):
    # Jira Cloud descriptions use Atlassian Document Format; flatten the readable text for AI context.
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return "\n".join(part for part in (_jira_description_text(item) for item in value) if part).strip()
    if not isinstance(value, dict):
        return str(value).strip()

    direct_text = str(value.get("text") or "").strip()
    content_text = [_jira_description_text(item) for item in value.get("content") or []]
    parts = ([direct_text] if direct_text else []) + [part for part in content_text if part]
    separator = "\n" if value.get("type") in {"doc", "paragraph", "heading", "bulletList", "orderedList", "listItem"} else " "
    return separator.join(parts).strip()


def _jira_context(hub, jira_keys):
    jira_keys = list(dict.fromkeys(key for key in jira_keys if key))
    if not jira_keys:
        return "- No Jira stories supplied"
    if not callable(getattr(hub, "jira_api_request", None)):
        raise RuntimeError("Jira integration is not available to the AI Test Designer.")

    rows = []
    for jira_key in jira_keys:
        try:
            issue = hub.jira_api_request(
                f"/rest/api/3/issue/{jira_key}?fields=summary,status,description"
            ) or {}
        except RuntimeError as exc:
            raise RuntimeError(
                f"Could not load Jira story {jira_key} for test generation: {exc}"
            ) from exc

        fields = issue.get("fields") or {}
        summary = str(fields.get("summary") or "").strip() or "No summary"
        status = str((fields.get("status") or {}).get("name") or "").strip() or "Unknown"
        description = _jira_description_text(fields.get("description")) or "No description"
        rows.append(
            f"- {jira_key}\n"
            f"  Summary: {summary}\n"
            f"  Status: {status}\n"
            f"  Description: {description}"
        )
    return "\n".join(rows)


def _generate_plan(hub, feature, requirement, count, preference, selected_test_plan=None, jira_keys=None):
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured for Test Hub.")

    existing_cases, stored_steps, implemented_steps = _existing_context(hub)
    plan_jira_keys = _test_plan_jira_keys(hub, selected_test_plan)
    context_jira_keys = list(dict.fromkeys(list(jira_keys or []) + plan_jira_keys))
    test_plan_context = _test_plan_context(hub, selected_test_plan)
    jira_context = _jira_context(hub, context_jira_keys)
    client = OpenAI(api_key=api_key)

    instructions = f"""You are the AI Test Designer inside a QA test management system.
Generate high-value, non-duplicate test cases from the supplied feature description and the connected QA context.
Return exactly the structured schema requested.

Rules:
- Target approximately {count} cases.
- Preferred type is {preference}. Respect it unless a different type is clearly more appropriate.
- Treat Pending planned coverage in the selected Test Plan as requirements to satisfy, not optional background.
- When a suggestion is intended to satisfy one Pending planned coverage item, set planned_coverage_id to that exact numeric ID. Use null when the suggestion does not satisfy a Pending item.
- Never invent a planned_coverage_id and never point to an already-covered Test Plan item.
- Do not generate coverage that is explicitly Out of Scope in the selected Test Plan.
- Use the Test Plan Objective, In Scope, Risks / Edge Cases, environment and Jira story content when deciding what to cover.
- Do not duplicate existing test cases or already-covered Test Plan items. Cover missing happy paths, negative paths, validation, permissions, state transitions and meaningful edge cases only when relevant.
- Keep cases atomic unless the requirement genuinely calls for an end-to-end journey.
- case_key must be unique-looking, uppercase, 3-64 characters, and contain only letters, numbers, hyphens or underscores.
- For Automated cases every step must start with Given, When, Then, And or But.
- Prefer exact existing Test Hub BDD wording when it already expresses the needed action/assertion.
- Prefer the real implemented pytest-bdd step bodies shown below; add the appropriate Given/When/Then keyword while preserving their wording.
- Automated cases should normally include regression and release suite tags. Add smoke only for truly critical paths.
- Manual cases may have no suite tags.
- expected_result must be observable and testable.
- coverage_reason should briefly explain the distinct risk, Jira requirement or planned coverage item addressed.
"""

    user_input = f"""Feature / Module: {feature}

Requirement / acceptance criteria:
{requirement}

Selected Test Plan context:
{test_plan_context}

Jira story context:
{jira_context}

Existing Test Hub cases to avoid duplicating:
{existing_cases}

Stored Test Hub BDD steps to reuse when useful:
{stored_steps}

Real implemented pytest-bdd step bodies from the repository:
{implemented_steps}
"""

    response = client.responses.parse(
        model=OPENAI_MODEL,
        input=[
            {"role": "system", "content": instructions},
            {"role": "user", "content": user_input},
        ],
        text_format=SuggestedTestPlan,
    )
    plan = response.output_parsed
    if plan is None:
        raise RuntimeError("The AI response could not be parsed into test cases.")
    return plan


def _duplicate_reason(hub, feature, case):
    existing_key = hub.db.session.scalar(
        hub.db.select(hub.TestCase.id).where(hub.TestCase.case_key == case.case_key.strip().upper())
    )
    if existing_key is not None:
        return f"Test case ID {case.case_key} already exists."

    existing_cases = hub.db.session.scalars(
        hub.db.select(hub.TestCase).where(hub.TestCase.feature == feature)
    ).all()
    normalized_title = " ".join(case.title.lower().split())
    for existing in existing_cases:
        if " ".join(existing.title.lower().split()) == normalized_title:
            return f"A case with the same title already exists: {existing.case_key}."
    return ""


def _available_test_plans(hub):
    model = getattr(hub, "TestPlan", None)
    if model is None:
        return []
    return hub.db.session.scalars(
        hub.db.select(model).order_by(model.updated_at.desc(), model.id.desc())
    ).all()


def _resolve_test_plan(hub, raw_value):
    raw_value = (raw_value or "").strip()
    if not raw_value:
        return None
    if not raw_value.isdigit():
        raise ValueError("Invalid Test Plan.")
    model = getattr(hub, "TestPlan", None)
    if model is None:
        raise ValueError("Test Plans are not available.")
    plan = hub.db.session.get(model, int(raw_value))
    if plan is None:
        raise ValueError("Test Plan not found.")
    return plan


def _resolve_planned_item(selected_test_plan, planned_coverage_id):
    if selected_test_plan is None or planned_coverage_id is None:
        return None
    for item in selected_test_plan.items:
        if item.id == planned_coverage_id and item.test_case is None:
            return item
    return None


def register_ai_designer(hub):
    app = hub.app
    if "ai_test_designer" in app.view_functions:
        return

    marker = '    <aside class="card">\n      <h2>Create test case</h2>'
    replacement = """    <aside class="card">\n      <div style="margin-bottom:18px;padding:15px;border:1px solid #cddcf8;border-radius:13px;background:linear-gradient(135deg,#edf4ff,#f8fbff)">\n        <strong style="display:block;margin-bottom:5px;color:#17325d">✨ AI Test Designer</strong>\n        <div class="hint" style="margin:0 0 10px">Turn a feature or acceptance criteria into reviewable test-case drafts.</div>\n        <a class="primary button-link" href="{{ url_for('ai_test_designer') }}">Generate with AI</a>\n      </div>\n      <h2>Create test case</h2>"""
    if marker in hub.PAGE_HTML:
        hub.PAGE_HTML = hub.PAGE_HTML.replace(marker, replacement, 1)

    @app.get("/ai-test-designer")
    def ai_test_designer():
        return hub.render_template_string(
            DESIGNER_PAGE_HTML,
            error="",
            feature="",
            requirement="",
            jira_keys="",
            test_plan_id="",
            test_plans=_available_test_plans(hub),
            count=6,
            preference="Automated",
        )

    @app.post("/ai-test-designer/generate")
    def ai_generate_test_cases():
        feature = hub.request.form.get("feature", "").strip()
        requirement = hub.request.form.get("requirement", "").strip()
        jira_keys = hub.request.form.get("jira_keys", "").strip()
        test_plan_id = hub.request.form.get("test_plan_id", "").strip()
        preference = hub.request.form.get("preference", "Automated").strip()

        try:
            count = max(3, min(12, int(hub.request.form.get("count", "6"))))
        except ValueError:
            count = 6

        if preference not in {"Automated", "Manual", "Mixed"}:
            preference = "Automated"

        try:
            selected_test_plan = _resolve_test_plan(hub, test_plan_id)
        except ValueError as exc:
            return hub.render_template_string(
                DESIGNER_PAGE_HTML,
                error=str(exc),
                feature=feature,
                requirement=requirement,
                jira_keys=jira_keys,
                test_plan_id=test_plan_id,
                test_plans=_available_test_plans(hub),
                count=count,
                preference=preference,
            ), 400

        if not feature or len(requirement) < 20:
            return hub.render_template_string(
                DESIGNER_PAGE_HTML,
                error="Feature and a meaningful requirement description are required.",
                feature=feature,
                requirement=requirement,
                jira_keys=jira_keys,
                test_plan_id=test_plan_id,
                test_plans=_available_test_plans(hub),
                count=count,
                preference=preference,
            ), 400

        try:
            parsed_jira_keys = hub.parse_jira_keys(jira_keys)
            plan = _generate_plan(
                hub,
                feature,
                requirement,
                count,
                preference,
                selected_test_plan=selected_test_plan,
                jira_keys=parsed_jira_keys,
            )
        except Exception as exc:
            message = str(exc)
            if len(message) > 500:
                message = message[:500] + "…"
            return hub.render_template_string(
                DESIGNER_PAGE_HTML,
                error=message,
                feature=feature,
                requirement=requirement,
                jira_keys=jira_keys,
                test_plan_id=test_plan_id,
                test_plans=_available_test_plans(hub),
                count=count,
                preference=preference,
            ), 400

        suggestions = []
        for case in plan.test_cases:
            planned_item = _resolve_planned_item(selected_test_plan, case.planned_coverage_id)
            duplicate_reason = _duplicate_reason(hub, feature, case)
            if case.planned_coverage_id is not None and planned_item is None and not duplicate_reason:
                duplicate_reason = (
                    f"Planned coverage ID {case.planned_coverage_id} is not a Pending item in the selected Test Plan."
                )
            suggestions.append(
                {
                    "case": case,
                    "planned_item": planned_item,
                    "duplicate_reason": duplicate_reason,
                }
            )

        return hub.render_template_string(
            REVIEW_PAGE_HTML,
            feature=feature,
            jira_keys=jira_keys,
            test_plan_id=test_plan_id,
            selected_test_plan=selected_test_plan,
            plan=plan,
            suggestions=suggestions,
            priorities=["Low", "Medium", "High", "Critical"],
            model=OPENAI_MODEL,
        )

    @app.post("/ai-test-designer/create")
    def ai_create_selected_cases():
        feature = hub.request.form.get("feature", "").strip()
        selected = hub.request.form.getlist("selected")
        if not feature or not selected:
            return "Select at least one generated test case.", 400

        try:
            jira_keys = hub.parse_jira_keys(hub.request.form.get("jira_keys", ""))
            selected_test_plan = _resolve_test_plan(
                hub, hub.request.form.get("test_plan_id", "")
            )
        except ValueError as exc:
            return str(exc), 400

        errors = []
        prepared = []
        selected_keys = set()
        selected_coverage_ids = set()

        for raw_index in selected:
            try:
                index = int(raw_index)
            except ValueError:
                return "Invalid generated test case selection.", 400

            case_key = hub.request.form.get(f"case_key_{index}", "").strip().upper()
            title = hub.request.form.get(f"title_{index}", "").strip()
            priority = hub.request.form.get(f"priority_{index}", "Medium").strip()
            case_type = hub.request.form.get(f"type_{index}", "Automated").strip()
            preconditions = hub.request.form.get(f"preconditions_{index}", "").strip()
            steps = hub.normalize_lines(hub.request.form.get(f"steps_{index}", ""))
            expected_result = hub.request.form.get(f"expected_result_{index}", "").strip()
            planned_coverage_raw = hub.request.form.get(f"planned_coverage_id_{index}", "").strip()
            planned_coverage_id = None
            if planned_coverage_raw:
                if not planned_coverage_raw.isdigit():
                    errors.append(f"{case_key or 'Unnamed case'}: invalid planned coverage ID.")
                    continue
                planned_coverage_id = int(planned_coverage_raw)
                planned_item = _resolve_planned_item(selected_test_plan, planned_coverage_id)
                if planned_item is None:
                    errors.append(
                        f"{case_key or 'Unnamed case'}: planned coverage is no longer Pending in the selected Test Plan."
                    )
                    continue
                if planned_coverage_id in selected_coverage_ids:
                    errors.append(
                        f"{case_key or 'Unnamed case'}: the same planned coverage item was selected twice."
                    )
                    continue

            tags = {
                tag.strip().lower()
                for tag in hub.request.form.getlist(f"suite_tags_{index}")
                if tag.strip()
            }

            if not case_key or not title or not steps or not expected_result:
                errors.append(f"{case_key or 'Unnamed case'}: ID, title, steps and expected result are required.")
                continue
            if priority not in hub.PRIORITIES or case_type not in hub.TYPES:
                errors.append(f"{case_key}: invalid priority or type.")
                continue
            if not hub.CASE_KEY_PATTERN.match(case_key):
                errors.append(f"{case_key}: invalid test case ID format.")
                continue
            if case_key in selected_keys or hub.db.session.scalar(
                hub.db.select(hub.TestCase.id).where(hub.TestCase.case_key == case_key)
            ) is not None:
                errors.append(f"{case_key}: test case ID already exists or is selected twice.")
                continue
            if not tags.issubset(ALLOWED_SUITE_TAGS):
                errors.append(f"{case_key}: suite tags may only be smoke, regression or release.")
                continue
            if case_type == "Automated":
                invalid_steps = [step for step in steps if not BDD_STEP_PATTERN.match(step)]
                if invalid_steps:
                    errors.append(f"{case_key}: automated steps must start with Given, When, Then, And or But.")
                    continue
                tags.update({"regression", "release"})

            selected_keys.add(case_key)
            if planned_coverage_id is not None:
                selected_coverage_ids.add(planned_coverage_id)
            prepared.append({
                "case_key": case_key,
                "title": title,
                "priority": priority,
                "type": case_type,
                "suite_tags": ",".join(sorted(tags)),
                "preconditions": preconditions,
                "steps": steps,
                "expected_result": expected_result,
                "planned_coverage_id": planned_coverage_id,
            })

        if errors:
            return "\n".join(errors), 400

        created_cases = []
        for item in prepared:
            case = hub.TestCase(
                case_key=item["case_key"],
                title=item["title"],
                feature=feature,
                priority=item["priority"],
                type=item["type"],
                status="Draft",
                suite_tags=item["suite_tags"],
                preconditions=item["preconditions"],
                expected_result=item["expected_result"],
            )
            case.steps = [
                hub.TestStep(position=position, action=action)
                for position, action in enumerate(item["steps"], start=1)
            ]
            hub.set_jira_links(case, jira_keys)
            hub.db.session.add(case)
            created_cases.append((case, item))

        if selected_test_plan is not None:
            position = max(
                (item.position for item in selected_test_plan.items),
                default=0,
            ) + 1
            for case, generated in created_cases:
                planned_coverage_id = generated["planned_coverage_id"]
                if planned_coverage_id is not None:
                    # Satisfy the existing Pending coverage item instead of creating a duplicate checklist row.
                    planned_item = _resolve_planned_item(selected_test_plan, planned_coverage_id)
                    if planned_item is None:
                        hub.db.session.rollback()
                        return "Planned coverage changed before the generated Test Case could be created.", 409
                    planned_item.test_case = case
                    continue

                # Suggestions that do not target Pending coverage still become new covered plan items.
                selected_test_plan.items.append(
                    hub.TestPlanItem(
                        test_case=case,
                        position=position,
                        title_snapshot=case.title,
                        feature_snapshot=case.feature_name,
                    )
                )
                position += 1
            selected_test_plan.updated_at = datetime.now(timezone.utc)

        hub.db.session.commit()
        sync_errors = hub.sync_jira_test_hub_web_links(jira_keys)
        if sync_errors:
            return hub.redirect(hub.url_for("index", jira_sync_error=" | ".join(sync_errors)))
        return hub.redirect(hub.url_for("index"))
