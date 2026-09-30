import os
import re
from typing import Literal

from openai import OpenAI
from pydantic import BaseModel, Field


OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.6-terra").strip()
ALLOWED_SUITE_TAGS = {"smoke", "regression", "release"}
BDD_STEP_PATTERN = re.compile(r"^(Given|When|Then|And|But)\s+.+", re.IGNORECASE)


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
:root{--surface:rgba(255,255,255,.96);--text:#111827;--muted:#6b7280;--border:#d7dfec;--accent:#2f66e8;font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}*{box-sizing:border-box}body{margin:0;min-height:100vh;color:var(--text);background:linear-gradient(180deg,#f8faff,#eef3fb)}header{display:flex;align-items:center;justify-content:space-between;padding:16px 30px;background:rgba(20,42,82,.94);color:#fff}.button{padding:10px 14px;border-radius:10px;background:#eef2f7;color:#20324f;text-decoration:none;font-weight:750}main{max-width:1180px;margin:0 auto;padding:30px 22px 50px}h1{margin:0;color:#172b4d}.subtitle{margin:6px 0 22px;color:var(--muted)}.summary{margin-bottom:18px;padding:15px 17px;border:1px solid #cddcf8;border-radius:13px;background:#edf4ff;color:#294a7a}.case{margin:14px 0;padding:19px;border:1px solid var(--border);border-radius:17px;background:var(--surface);box-shadow:0 12px 34px rgba(35,61,108,.06)}.case-head{display:flex;gap:11px;align-items:flex-start}.case-head>input{width:19px;height:19px;margin-top:12px}.fields{flex:1;min-width:0}.grid{display:grid;grid-template-columns:160px 1fr 140px 140px;gap:10px}.field{margin-top:10px}.field label{display:block;margin-bottom:5px;font-size:11px;font-weight:800;color:#56667b}input,select,textarea,button{font:inherit}input,select,textarea{width:100%;border:1px solid #ccd5e4;border-radius:9px;background:#fff;outline:none}input,select{height:40px;padding:0 10px}textarea{min-height:88px;padding:9px 10px;resize:vertical;line-height:1.4}.warning{margin-top:9px;padding:9px 11px;border-radius:9px;background:#fff4dd;color:#8a5d00;font-size:12px;font-weight:700}.reason{margin-top:9px;color:#607087;font-size:12px}.actions{position:sticky;bottom:12px;display:flex;justify-content:flex-end;gap:8px;margin-top:20px;padding:13px;border:1px solid var(--border);border-radius:14px;background:rgba(255,255,255,.94);box-shadow:0 12px 35px rgba(35,61,108,.12);backdrop-filter:blur(10px)}.primary{border:0;border-radius:10px;padding:11px 16px;background:linear-gradient(90deg,#2f66e8,#2475ff);color:#fff;font-weight:800;cursor:pointer}.secondary{border:0;border-radius:10px;padding:11px 16px;background:#eef2f7;color:#20324f;text-decoration:none;font-weight:750}@media(max-width:850px){.grid{grid-template-columns:1fr 1fr}}@media(max-width:560px){header{padding:13px 16px}main{padding:20px 12px}.grid{grid-template-columns:1fr}}
</style>
</head>
<body>
<header><strong>✨ AI Test Designer · Review</strong><a class="button" href="{{ url_for('ai_test_designer') }}">Start over</a></header>
<main><h1>Review generated test cases</h1><div class="subtitle">Edit anything you want, uncheck cases you do not want, then create only the selected drafts.</div>
<div class="summary"><strong>{{ feature }}</strong> — {{ plan.feature_summary }}<br>{{ suggestions|length }} suggestions generated with {{ model }}.</div>
<form method="post" action="{{ url_for('ai_create_selected_cases') }}">
<input type="hidden" name="feature" value="{{ feature }}"><input type="hidden" name="jira_keys" value="{{ jira_keys }}"><input type="hidden" name="suggestion_count" value="{{ suggestions|length }}">
{% for item in suggestions %}
<section class="case"><div class="case-head"><input type="checkbox" name="selected" value="{{ loop.index0 }}" {% if not item.duplicate_reason %}checked{% endif %}><div class="fields">
<div class="grid">
<div class="field"><label>Test case ID</label><input name="case_key_{{ loop.index0 }}" value="{{ item.case.case_key }}"></div>
<div class="field"><label>Title</label><input name="title_{{ loop.index0 }}" value="{{ item.case.title }}"></div>
<div class="field"><label>Priority</label><select name="priority_{{ loop.index0 }}">{% for p in priorities %}<option {% if p == item.case.priority %}selected{% endif %}>{{ p }}</option>{% endfor %}</select></div>
<div class="field"><label>Type</label><select name="type_{{ loop.index0 }}"><option {% if item.case.type == 'Automated' %}selected{% endif %}>Automated</option><option {% if item.case.type == 'Manual' %}selected{% endif %}>Manual</option></select></div>
</div>
<div class="field"><label>Suite tags</label><input name="suite_tags_{{ loop.index0 }}" value="{{ item.case.suite_tags|join(', ') }}" placeholder="smoke, regression, release"></div>
<div class="field"><label>Preconditions</label><textarea name="preconditions_{{ loop.index0 }}">{{ item.case.preconditions }}</textarea></div>
<div class="field"><label>Steps — one per line</label><textarea name="steps_{{ loop.index0 }}">{{ item.case.steps|join('\n') }}</textarea></div>
<div class="field"><label>Expected result</label><textarea name="expected_result_{{ loop.index0 }}">{{ item.case.expected_result }}</textarea></div>
{% if item.duplicate_reason %}<div class="warning">⚠ {{ item.duplicate_reason }} Edit it before selecting this case.</div>{% endif %}
<div class="reason"><strong>Why AI suggested it:</strong> {{ item.case.coverage_reason }}</div>
</div></div></section>
{% endfor %}
<div class="actions"><a class="secondary" href="{{ url_for('ai_test_designer') }}">Cancel</a><button class="primary" type="submit">Create selected drafts</button></div>
</form></main></body></html>
"""


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

    existing_steps = "\n".join(f"- {step}" for step in step_actions[:150]) or "- No existing BDD steps"
    return existing_cases, existing_steps


def _generate_plan(hub, feature, requirement, count, preference):
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured for Test Hub.")

    existing_cases, existing_steps = _existing_context(hub)
    client = OpenAI(api_key=api_key)

    instructions = f"""You are the AI Test Designer inside a QA test management system.
Generate high-value, non-duplicate test cases from the supplied feature description.
Return exactly the structured schema requested.

Rules:
- Target approximately {count} cases.
- Preferred type is {preference}. Respect it unless a different type is clearly more appropriate.
- Do not duplicate existing test cases. Cover missing happy paths, negative paths, validation, permissions, state transitions and meaningful edge cases only when relevant to the requirement.
- Keep cases atomic unless the requirement genuinely calls for an end-to-end journey.
- case_key must be unique-looking, uppercase, 3-64 characters, and contain only letters, numbers, hyphens or underscores.
- For Automated cases every step must start with Given, When, Then, And or But.
- Prefer exact existing BDD step wording when it already expresses the needed action/assertion.
- Automated cases should normally include regression and release suite tags. Add smoke only for truly critical paths.
- Manual cases may have no suite tags.
- expected_result must be observable and testable.
- coverage_reason should briefly explain the distinct risk or requirement covered.
"""

    user_input = f"""Feature / Module: {feature}

Requirement / acceptance criteria:
{requirement}

Existing Test Hub cases to avoid duplicating:
{existing_cases}

Existing BDD step vocabulary to reuse when useful:
{existing_steps}
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


def register_ai_designer(hub):
    app = hub.app
    if "ai_test_designer" in app.view_functions:
        return

    marker = '    <aside class="card">\n      <h2>Create test case</h2>'
    replacement = '''    <aside class="card">\n      <div style="margin-bottom:18px;padding:15px;border:1px solid #cddcf8;border-radius:13px;background:linear-gradient(135deg,#edf4ff,#f8fbff)">\n        <strong style="display:block;margin-bottom:5px;color:#17325d">✨ AI Test Designer</strong>\n        <div class="hint" style="margin:0 0 10px">Turn a feature or acceptance criteria into reviewable test-case drafts.</div>\n        <a class="primary button-link" href="{{ url_for('ai_test_designer') }}">Generate with AI</a>\n      </div>\n      <h2>Create test case</h2>'''
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
            count=6,
            preference="Automated",
        )

    @app.post("/ai-test-designer/generate")
    def ai_generate_test_cases():
        feature = hub.request.form.get("feature", "").strip()
        requirement = hub.request.form.get("requirement", "").strip()
        jira_keys = hub.request.form.get("jira_keys", "").strip()
        preference = hub.request.form.get("preference", "Automated").strip()

        try:
            count = max(3, min(12, int(hub.request.form.get("count", "6"))))
        except ValueError:
            count = 6

        if preference not in {"Automated", "Manual", "Mixed"}:
            preference = "Automated"

        if not feature or len(requirement) < 20:
            return hub.render_template_string(
                DESIGNER_PAGE_HTML,
                error="Feature and a meaningful requirement description are required.",
                feature=feature,
                requirement=requirement,
                jira_keys=jira_keys,
                count=count,
                preference=preference,
            ), 400

        try:
            hub.parse_jira_keys(jira_keys)
            plan = _generate_plan(hub, feature, requirement, count, preference)
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
                count=count,
                preference=preference,
            ), 400

        suggestions = [
            {"case": case, "duplicate_reason": _duplicate_reason(hub, feature, case)}
            for case in plan.test_cases
        ]
        return hub.render_template_string(
            REVIEW_PAGE_HTML,
            feature=feature,
            jira_keys=jira_keys,
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
        except ValueError as exc:
            return str(exc), 400

        errors = []
        prepared = []
        selected_keys = set()

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
            raw_tags = hub.request.form.get(f"suite_tags_{index}", "")
            tags = {
                tag.strip().lower()
                for tag in re.split(r"[,;\s]+", raw_tags)
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
            prepared.append({
                "case_key": case_key,
                "title": title,
                "priority": priority,
                "type": case_type,
                "suite_tags": ",".join(sorted(tags)),
                "preconditions": preconditions,
                "steps": steps,
                "expected_result": expected_result,
            })

        if errors:
            return "\n".join(errors), 400

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

        hub.db.session.commit()
        sync_errors = hub.sync_jira_test_hub_web_links(jira_keys)
        if sync_errors:
            return hub.redirect(hub.url_for("index", jira_sync_error=" | ".join(sync_errors)))
        return hub.redirect(hub.url_for("index"))
