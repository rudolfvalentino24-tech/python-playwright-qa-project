import re
from datetime import datetime, timezone
from functools import wraps
from html import escape

from sqlalchemy import inspect, text


PLAN_TYPES = ("Feature", "Regression", "Release", "Smoke", "Exploratory")
DEFAULT_ENVIRONMENTS = ("QA", "Staging", "Production")


STRATEGY_CSS = r'''
.plan-create-section{margin:12px 0;border:1px solid #e4e7ec;border-radius:10px;background:#fff;overflow:hidden}.plan-create-section>summary{cursor:pointer;padding:11px 13px;background:#f9fafb;color:#344054;font-size:12px;font-weight:800;list-style:none}.plan-create-section>summary::-webkit-details-marker{display:none}.plan-create-body{padding:2px 13px 13px}.plan-create-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}.plan-check-row{display:flex;gap:8px;flex-wrap:wrap;margin-top:6px}.plan-check{display:inline-flex!important;align-items:center;gap:6px;margin:0!important;padding:8px 10px;border:1px solid #d0d5dd;border-radius:8px;background:#fff;color:#344054;font-size:11px!important;font-weight:700!important}.plan-check input{width:15px!important;height:15px!important;margin:0!important}.plan-strategy-summary{margin:0 0 20px;padding:0 0 18px;border-bottom:1px solid #e4e7ec}.plan-strategy-head{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin-bottom:12px}.plan-strategy-head h2{margin:0!important}.plan-strategy-chips{display:flex;gap:6px;flex-wrap:wrap;margin-top:7px}.plan-strategy-chip{display:inline-flex;padding:5px 8px;border-radius:999px;background:#f2f4f7;color:#475467;font-size:10px;font-weight:800}.plan-strategy-objective{padding:13px;border:1px solid #dbe5f1;border-radius:10px;background:#f8fbff;color:#344054;font-size:12px;line-height:1.55}.plan-strategy-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px}.plan-strategy-block{padding:12px;border:1px solid #e4e7ec;border-radius:10px;background:#fff}.plan-strategy-block h4{margin:0 0 6px;color:#344054;font-size:10px;text-transform:uppercase;letter-spacing:.05em}.plan-strategy-block div{color:#667085;font-size:11px;line-height:1.5}.plan-strategy-empty{color:#98a2b3;font-style:italic}.plan-list-strategy-meta{display:flex;gap:6px;flex-wrap:wrap;margin-top:6px}.plan-list-strategy-meta span{padding:4px 7px;border-radius:999px;background:#f2f4f7;color:#667085;font-size:9px;font-weight:750}@media(max-width:720px){.plan-create-grid,.plan-strategy-grid{grid-template-columns:1fr}}
'''


CREATE_FORM_FIELDS = r'''
<details class="plan-create-section" open>
  <summary>Basic information</summary>
  <div class="plan-create-body">
    <div class="form-field"><label>Name *</label><input name="name" required placeholder="Hide / Show Password — Store App"></div>
    <div class="plan-create-grid">
      <div class="form-field"><label>Plan Type *</label><select name="plan_type">{% for value in plan_types %}<option {% if value == 'Feature' %}selected{% endif %}>{{ value }}</option>{% endfor %}</select></div>
      <div class="form-field"><label>Status</label><select name="status">{% for status in statuses %}<option>{{ status }}</option>{% endfor %}</select></div>
    </div>
    <div class="plan-create-grid">
      <div class="form-field"><label>Application / Product</label><input name="application" placeholder="Store App"></div>
      <div class="form-field"><label>Feature / Module *</label><input name="feature" required placeholder="Authentication / Password Field"></div>
    </div>
    <div class="form-field"><label>Summary / Context</label><textarea name="description" placeholder="Short context for this testing effort."></textarea></div>
  </div>
</details>

<details class="plan-create-section" open>
  <summary>Objective & Scope</summary>
  <div class="plan-create-body">
    <div class="form-field"><label>Objective *</label><textarea name="objective" required placeholder="Verify that users can safely show and hide the password without changing the password value or breaking login behaviour."></textarea></div>
    <div class="plan-create-grid">
      <div class="form-field"><label>In Scope</label><textarea name="in_scope" placeholder="Password masked by default\nReveal password\nHide password again\nFocus and value preserved"></textarea></div>
      <div class="form-field"><label>Out of Scope</label><textarea name="out_of_scope" placeholder="Password reset\nBackend authentication logic\nAccount lockout"></textarea></div>
    </div>
  </div>
</details>

<details class="plan-create-section">
  <summary>Links & Environment</summary>
  <div class="plan-create-body">
    <div class="form-field"><label>Jira Stories</label><input name="jira_keys" placeholder="STORE-123, STORE-124"><div class="prd-plan-hint">Comma-separated Jira requirements. They become the Test Plan Jira scope.</div></div>
    <div class="form-field"><label>Target Release</label><select name="release_id"><option value="">No release yet</option>{% for release in releases %}<option value="{{ release.id }}">{{ release.version }}{% if release.environment %} · {{ release.environment }}{% endif %}</option>{% endfor %}</select></div>
    <div class="form-field"><label>Environment</label><div class="plan-check-row">{% for value in environments %}<label class="plan-check"><input type="checkbox" name="environments" value="{{ value }}">{{ value }}</label>{% endfor %}</div></div>
    <div class="form-field"><label>Other environment</label><input name="environment_custom" placeholder="e.g. iOS QA build"></div>
  </div>
</details>

<details class="plan-create-section">
  <summary>Quality criteria</summary>
  <div class="plan-create-body">
    <div class="form-field"><label>Risks / Edge Cases</label><textarea name="risks" placeholder="Password remains visible unexpectedly\nValue is cleared during toggle\nCursor/focus moves"></textarea></div>
    <div class="plan-create-grid">
      <div class="form-field"><label>Entry Criteria</label><textarea name="entry_criteria" placeholder="Feature deployed to QA\nAcceptance criteria approved\nTest user available"></textarea></div>
      <div class="form-field"><label>Exit Criteria</label><textarea name="exit_criteria" placeholder="Critical/High tests pass\nNo open Critical/High defects\nAutomation added"></textarea></div>
    </div>
  </div>
</details>
<button class="primary create-submit" type="submit">Create Test Plan</button>
'''


EDIT_STRATEGY_MODAL = r'''
<div id="prdEditPlanStrategy" class="prd-modal-backdrop">
  <div class="prd-modal prd-lg">
    <div class="prd-modal-head"><div><h2>Edit Test Plan strategy</h2><p>Update the purpose, scope and quality criteria for this plan.</p></div><button class="prd-close" type="button" data-prd-close="prdEditPlanStrategy">×</button></div>
    <div class="prd-modal-body">
      <form method="post" action="{{ url_for('update_test_plan_strategy', plan_id=plan.id) }}">
        <div class="plan-create-grid">
          <div class="form-field"><label>Plan Type</label><select name="plan_type">{% for value in plan_types %}<option {% if value == (plan.plan_type or 'Feature') %}selected{% endif %}>{{ value }}</option>{% endfor %}</select></div>
          <div class="form-field"><label>Application / Product</label><input name="application" value="{{ plan.application or '' }}"></div>
        </div>
        <div class="form-field"><label>Feature / Module *</label><input name="feature" required value="{{ plan.feature or '' }}"></div>
        <div class="form-field"><label>Summary / Context</label><textarea name="description">{{ plan.description or '' }}</textarea></div>
        <div class="form-field"><label>Objective *</label><textarea name="objective" required>{{ plan.objective or '' }}</textarea></div>
        <div class="plan-create-grid">
          <div class="form-field"><label>In Scope</label><textarea name="in_scope">{{ plan.in_scope or '' }}</textarea></div>
          <div class="form-field"><label>Out of Scope</label><textarea name="out_of_scope">{{ plan.out_of_scope or '' }}</textarea></div>
        </div>
        <div class="form-field"><label>Environment</label><input name="environment" value="{{ plan.environment or '' }}" placeholder="QA, Staging"></div>
        <div class="form-field"><label>Risks / Edge Cases</label><textarea name="risks">{{ plan.risks or '' }}</textarea></div>
        <div class="plan-create-grid">
          <div class="form-field"><label>Entry Criteria</label><textarea name="entry_criteria">{{ plan.entry_criteria or '' }}</textarea></div>
          <div class="form-field"><label>Exit Criteria</label><textarea name="exit_criteria">{{ plan.exit_criteria or '' }}</textarea></div>
        </div>
        <button class="primary" type="submit">Save strategy</button>
      </form>
    </div>
  </div>
</div>
'''


def _nl(value):
    value = (value or "").strip()
    return escape(value).replace("\n", "<br>") if value else '<span class="plan-strategy-empty">Not defined</span>'


def _strategy_summary_html(plan, include_edit=True):
    chips = []
    for value in (plan.plan_type or "Feature", plan.application, plan.feature, plan.environment):
        if value:
            chips.append(f'<span class="plan-strategy-chip">{escape(str(value))}</span>')
    edit_button = '<button type="button" class="secondary" data-prd-open="prdEditPlanStrategy">Edit strategy</button>' if include_edit else ""
    return f'''
<section class="plan-strategy-summary" data-test-plan-strategy="1">
  <div class="plan-strategy-head"><div><h2>QA strategy</h2><div class="plan-strategy-chips">{''.join(chips)}</div></div>{edit_button}</div>
  <div class="plan-strategy-objective"><strong>Objective</strong><div style="margin-top:6px">{_nl(plan.objective)}</div></div>
  <div class="plan-strategy-grid">
    <div class="plan-strategy-block"><h4>In Scope</h4><div>{_nl(plan.in_scope)}</div></div>
    <div class="plan-strategy-block"><h4>Out of Scope</h4><div>{_nl(plan.out_of_scope)}</div></div>
    <div class="plan-strategy-block"><h4>Risks / Edge Cases</h4><div>{_nl(plan.risks)}</div></div>
    <div class="plan-strategy-block"><h4>Environment</h4><div>{_nl(plan.environment)}</div></div>
    <div class="plan-strategy-block"><h4>Entry Criteria</h4><div>{_nl(plan.entry_criteria)}</div></div>
    <div class="plan-strategy-block"><h4>Exit Criteria</h4><div>{_nl(plan.exit_criteria)}</div></div>
  </div>
</section>
'''


def _add_strategy_columns(hub):
    """Add structured strategy fields to the existing TestPlan mapping and table."""
    columns = (
        ("plan_type", hub.db.String(30), "VARCHAR(30) DEFAULT 'Feature'"),
        ("application", hub.db.String(120), "VARCHAR(120) DEFAULT ''"),
        ("feature", hub.db.String(160), "VARCHAR(160) DEFAULT ''"),
        ("objective", hub.db.Text, "TEXT DEFAULT ''"),
        ("in_scope", hub.db.Text, "TEXT DEFAULT ''"),
        ("out_of_scope", hub.db.Text, "TEXT DEFAULT ''"),
        ("risks", hub.db.Text, "TEXT DEFAULT ''"),
        ("entry_criteria", hub.db.Text, "TEXT DEFAULT ''"),
        ("exit_criteria", hub.db.Text, "TEXT DEFAULT ''"),
        ("environment", hub.db.String(220), "VARCHAR(220) DEFAULT ''"),
    )

    # SQLAlchemy declarative classes support adding mapped columns after the
    # initial class declaration. Do this before any TestPlan query uses them.
    for name, column_type, _ in columns:
        if not hasattr(hub.TestPlan, name):
            setattr(hub.TestPlan, name, hub.db.Column(column_type, nullable=True))

    with hub.app.app_context():
        physical_columns = {column["name"] for column in inspect(hub.db.engine).get_columns("test_plans")}
        missing = [(name, sql_type) for name, _, sql_type in columns if name not in physical_columns]
        if missing:
            with hub.db.engine.begin() as connection:
                for name, sql_type in missing:
                    connection.execute(text(f"ALTER TABLE test_plans ADD COLUMN {name} {sql_type}"))
        with hub.db.engine.begin() as connection:
            connection.execute(text("UPDATE test_plans SET plan_type='Feature' WHERE plan_type IS NULL OR plan_type=''"))


def register_test_plan_strategy(hub):
    """Upgrade Test Plans with feature strategy, scope and creation-time links."""
    if getattr(hub.app, "_test_plan_strategy_registered", False):
        return

    _add_strategy_columns(hub)

    def releases():
        return hub.db.session.scalars(
            hub.db.select(hub.Release).order_by(hub.Release.release_date.desc(), hub.Release.id.desc())
        ).all()

    def plan_list():
        return hub.db.session.scalars(
            hub.db.select(hub.TestPlan).order_by(hub.TestPlan.updated_at.desc(), hub.TestPlan.id.desc())
        ).all()

    def environment_value(form):
        values = [value.strip() for value in form.getlist("environments") if value.strip()]
        custom = form.get("environment_custom", "").strip()
        if custom:
            values.append(custom)
        seen = []
        for value in values:
            if value not in seen:
                seen.append(value)
        return ", ".join(seen)

    def validate_strategy(form):
        plan_type = form.get("plan_type", "Feature").strip() or "Feature"
        feature = form.get("feature", "").strip()
        objective = form.get("objective", "").strip()
        if plan_type not in PLAN_TYPES:
            return None, "Invalid Test Plan type."
        if not feature:
            return None, "Feature / Module is required."
        if not objective:
            return None, "Test Plan objective is required."
        return {"plan_type": plan_type, "feature": feature, "objective": objective}, None

    original_list = hub.app.view_functions.get("test_plans")
    if original_list is not None:
        @wraps(original_list)
        def test_plans_with_strategy():
            response = hub.app.make_response(original_list())
            if response.status_code != 200 or "text/html" not in (response.content_type or ""):
                return response
            html = response.get_data(as_text=True)
            if "data-test-plan-create-strategy" not in html:
                aside_start = html.find('<aside id="create-plan"')
                aside_end = html.find("</aside>", aside_start) if aside_start >= 0 else -1
                form_start = html.find("<form", aside_start, aside_end) if aside_end >= 0 else -1
                open_end = html.find(">", form_start, aside_end) + 1 if form_start >= 0 else -1
                form_end = html.find("</form>", open_end, aside_end) if open_end > 0 else -1
                if form_start >= 0 and open_end > 0 and form_end >= 0:
                    fields = hub.render_template_string(
                        '<div data-test-plan-create-strategy="1">' + CREATE_FORM_FIELDS + '</div>',
                        plan_types=PLAN_TYPES,
                        statuses=["Draft", "Active", "Completed"],
                        releases=releases(),
                        environments=DEFAULT_ENVIRONMENTS,
                    )
                    html = html[:open_end] + fields + html[form_end:]
            if "data-test-plan-strategy-css" not in html:
                html = html.replace("</head>", f'<style data-test-plan-strategy-css>{STRATEGY_CSS}</style></head>', 1)

            # Add useful feature context to each Test Plan card without changing
            # the existing coverage statistics or links.
            for plan in plan_list():
                href = f'href="/test-plans/{plan.id}"'
                pos = html.find(href)
                if pos < 0:
                    continue
                close = html.find("</a>", pos)
                if close < 0:
                    continue
                marker = f'data-plan-strategy-meta="{plan.id}"'
                nearby = html[close:close + 500]
                if marker in nearby:
                    continue
                values = [plan.plan_type or "Feature", plan.application, plan.feature]
                chips = "".join(f"<span>{escape(str(value))}</span>" for value in values if value)
                if chips:
                    meta = f'<div class="plan-list-strategy-meta" {marker}>{chips}</div>'
                    html = html[:close + 4] + meta + html[close + 4:]
            response.set_data(html)
            return response

        hub.app.view_functions["test_plans"] = test_plans_with_strategy

    original_create = hub.app.view_functions.get("create_test_plan")
    if original_create is not None:
        @wraps(original_create)
        def create_test_plan_with_strategy():
            strategy, error = validate_strategy(hub.request.form)
            if error:
                return error, 400

            jira_text = hub.request.form.get("jira_keys", "").strip()
            try:
                jira_keys = hub.parse_jira_keys(jira_text) if jira_text else []
            except ValueError as exc:
                return str(exc), 400

            release = None
            release_value = hub.request.form.get("release_id", "").strip()
            if release_value:
                if not release_value.isdigit():
                    return "Invalid release.", 400
                release = hub.db.session.get(hub.Release, int(release_value))
                if release is None:
                    return "Release not found.", 404

            before_id = hub.db.session.scalar(
                hub.db.select(hub.TestPlan.id).order_by(hub.TestPlan.id.desc()).limit(1)
            ) or 0
            response = hub.app.make_response(original_create())
            if not (300 <= response.status_code < 400):
                return response

            plan = hub.db.session.scalar(
                hub.db.select(hub.TestPlan).where(hub.TestPlan.id > before_id).order_by(hub.TestPlan.id.desc())
            )
            if plan is None:
                return response

            plan.plan_type = strategy["plan_type"]
            plan.application = hub.request.form.get("application", "").strip()
            plan.feature = strategy["feature"]
            plan.objective = strategy["objective"]
            plan.in_scope = hub.request.form.get("in_scope", "").strip()
            plan.out_of_scope = hub.request.form.get("out_of_scope", "").strip()
            plan.risks = hub.request.form.get("risks", "").strip()
            plan.entry_criteria = hub.request.form.get("entry_criteria", "").strip()
            plan.exit_criteria = hub.request.form.get("exit_criteria", "").strip()
            plan.environment = environment_value(hub.request.form)
            plan.updated_at = datetime.now(timezone.utc)

            for jira_key in jira_keys:
                exists = hub.db.session.scalar(
                    hub.db.select(hub.TestPlanJiraLink.id).where(
                        hub.TestPlanJiraLink.test_plan_id == plan.id,
                        hub.TestPlanJiraLink.jira_key == jira_key,
                    )
                )
                if exists is None:
                    hub.db.session.add(hub.TestPlanJiraLink(test_plan_id=plan.id, jira_key=jira_key))

            if release is not None:
                exists = hub.db.session.scalar(
                    hub.db.select(hub.TestPlanReleaseLink.id).where(
                        hub.TestPlanReleaseLink.test_plan_id == plan.id,
                        hub.TestPlanReleaseLink.release_id == release.id,
                    )
                )
                if exists is None:
                    hub.db.session.add(hub.TestPlanReleaseLink(test_plan_id=plan.id, release_id=release.id))

            hub.db.session.commit()
            return response

        hub.app.view_functions["create_test_plan"] = create_test_plan_with_strategy

    @hub.app.post("/test-plans/<int:plan_id>/strategy")
    def update_test_plan_strategy(plan_id):
        plan = hub.db.session.get(hub.TestPlan, plan_id)
        if plan is None:
            return "Test Plan not found.", 404
        strategy, error = validate_strategy(hub.request.form)
        if error:
            return error, 400
        plan.plan_type = strategy["plan_type"]
        plan.application = hub.request.form.get("application", "").strip()
        plan.feature = strategy["feature"]
        plan.description = hub.request.form.get("description", "").strip()
        plan.objective = strategy["objective"]
        plan.in_scope = hub.request.form.get("in_scope", "").strip()
        plan.out_of_scope = hub.request.form.get("out_of_scope", "").strip()
        plan.risks = hub.request.form.get("risks", "").strip()
        plan.entry_criteria = hub.request.form.get("entry_criteria", "").strip()
        plan.exit_criteria = hub.request.form.get("exit_criteria", "").strip()
        plan.environment = hub.request.form.get("environment", "").strip()
        plan.updated_at = datetime.now(timezone.utc)
        hub.db.session.commit()
        return hub.redirect(hub.url_for("test_plan_details", plan_id=plan.id))

    original_details = hub.app.view_functions.get("test_plan_details")
    if original_details is not None:
        @wraps(original_details)
        def test_plan_details_with_strategy(plan_id):
            response = hub.app.make_response(original_details(plan_id))
            if response.status_code != 200 or "text/html" not in (response.content_type or ""):
                return response
            plan = hub.db.session.get(hub.TestPlan, plan_id)
            if plan is None:
                return response
            html = response.get_data(as_text=True)
            if "data-test-plan-strategy" not in html:
                scope_marker = '<article class="th-card process-card" id="scope">'
                if scope_marker in html:
                    html = html.replace(scope_marker, scope_marker + _strategy_summary_html(plan, include_edit=True), 1)
                else:
                    main_marker = '<main class="th-page">'
                    html = html.replace(main_marker, main_marker + _strategy_summary_html(plan, include_edit=True), 1)
            # Check for the actual modal element, not the button that references it.
            if 'id="prdEditPlanStrategy"' not in html:
                modal = hub.render_template_string(EDIT_STRATEGY_MODAL, plan=plan, plan_types=PLAN_TYPES)
                html = html.replace("</body>", modal + "</body>", 1)
            if "data-test-plan-strategy-css" not in html:
                html = html.replace("</head>", f'<style data-test-plan-strategy-css>{STRATEGY_CSS}</style></head>', 1)
            response.set_data(html)
            return response

        hub.app.view_functions["test_plan_details"] = test_plan_details_with_strategy

    original_report = hub.app.view_functions.get("test_plan_report")
    if original_report is not None:
        @wraps(original_report)
        def test_plan_report_with_strategy(plan_id):
            response = hub.app.make_response(original_report(plan_id))
            if response.status_code != 200 or "text/html" not in (response.content_type or ""):
                return response
            plan = hub.db.session.get(hub.TestPlan, plan_id)
            if plan is None:
                return response
            html = response.get_data(as_text=True)
            if "data-test-plan-strategy" not in html:
                marker = '<section class="card"><h2>Scope and QA assessment</h2>'
                strategy = '<section class="card">' + _strategy_summary_html(plan, include_edit=False) + '</section>'
                html = html.replace(marker, strategy + marker, 1)
            if "data-test-plan-strategy-css" not in html:
                html = html.replace("</head>", f'<style data-test-plan-strategy-css>{STRATEGY_CSS}</style></head>', 1)
            response.set_data(html)
            return response

        hub.app.view_functions["test_plan_report"] = test_plan_report_with_strategy

    hub.app._test_plan_strategy_registered = True