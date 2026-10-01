from datetime import datetime, timezone
from functools import wraps


PLAN_STATUSES = {"Draft", "Active", "Completed"}


TEST_PLANS_PAGE_HTML = r'''
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Test Plans - Test Hub</title>
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<style>
{{ shell_css|safe }}
*{box-sizing:border-box}body{margin:0;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.plans-grid{display:grid;grid-template-columns:minmax(0,1.55fr) minmax(340px,.65fr);gap:18px;align-items:start}.panel{padding:22px}.page-head{display:flex;align-items:flex-start;justify-content:space-between;gap:18px;margin-bottom:18px}.page-head h1{margin:0;font-size:31px;letter-spacing:-.7px}.subtitle{margin-top:5px;color:var(--th-muted);font-size:13px}.primary,.secondary,.danger{border:0;border-radius:9px;padding:10px 14px;font:inherit;font-size:12px;font-weight:850;cursor:pointer;text-decoration:none;display:inline-flex;align-items:center;justify-content:center;gap:7px}.primary{background:linear-gradient(90deg,#1d6eff,#1468ff);color:#fff;box-shadow:0 7px 17px rgba(20,104,255,.2)}.secondary{background:#f0f4fa;color:#243f61}.danger{background:#fff0ef;color:#b42318}.plan-list{display:flex;flex-direction:column;gap:11px}.plan-card{padding:17px;border:1px solid #dce6f3;border-radius:13px;background:#fff}.plan-top{display:flex;justify-content:space-between;gap:14px;align-items:flex-start}.plan-title{font-size:16px;font-weight:900;color:#102d5a;text-decoration:none}.plan-title:hover{color:#1468ff}.plan-description{margin-top:6px;color:#60748f;font-size:12px;line-height:1.5}.badge{display:inline-block;padding:4px 9px;border-radius:999px;background:#edf2f8;color:#4b607a;font-size:10px;font-weight:850}.badge.Active{background:#dcfce7;color:#166534}.badge.Completed{background:#e8f1ff;color:#1763d8}.plan-stats{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:14px}.mini{padding:9px 10px;border-radius:9px;background:#f7faff}.mini strong{display:block;font-size:16px;color:#17325d}.mini span{display:block;margin-top:2px;color:#71829a;font-size:10px;font-weight:750}.progress{height:8px;margin-top:12px;border-radius:999px;background:#e7edf6;overflow:hidden}.progress>div{height:100%;background:linear-gradient(90deg,#2f66e8,#2475ff)}.empty{padding:38px;text-align:center;color:#72839a;font-size:12px}.form-field{margin-top:12px}.form-field label{display:block;margin-bottom:5px;color:#314d6c;font-size:10px;font-weight:900}.form-field input,.form-field select,.form-field textarea{width:100%;border:1px solid #ccd9eb;border-radius:9px;background:#fff;color:#183252;font:inherit;font-size:12px;outline:none}.form-field input,.form-field select{height:42px;padding:0 11px}.form-field textarea{min-height:100px;padding:10px 11px;resize:vertical}.form-field input:focus,.form-field select:focus,.form-field textarea:focus{border-color:#5590f7;box-shadow:0 0 0 3px rgba(43,116,245,.1)}.create-submit{width:100%;margin-top:14px}@media(max-width:900px){.plans-grid{grid-template-columns:1fr}.plan-stats{grid-template-columns:1fr 1fr}}@media(max-width:560px){.panel{padding:14px}.page-head{flex-direction:column}.plan-top{flex-direction:column}}
</style>
</head><body>
{{ nav_html|safe }}
<main class="th-page">
  <div class="page-head"><div><h1>Test Plans</h1><div class="subtitle">Plan QA coverage, attach existing test cases, and track what still needs to be created.</div></div><a class="primary" href="#create-plan">＋ Create Test Plan</a></div>
  <div class="plans-grid">
    <section class="th-card panel">
      <div class="plan-list">
        {% for row in plan_rows %}
          <article class="plan-card">
            <div class="plan-top">
              <div>
                <a class="plan-title" href="{{ url_for('test_plan_details', plan_id=row.plan.id) }}">{{ row.plan.name }}</a>
                {% if row.plan.description %}<div class="plan-description">{{ row.plan.description }}</div>{% endif %}
              </div>
              <span class="badge {{ row.plan.status }}">{{ row.plan.status }}</span>
            </div>
            <div class="plan-stats">
              <div class="mini"><strong>{{ row.summary.total }}</strong><span>Planned</span></div>
              <div class="mini"><strong>{{ row.summary.created }}</strong><span>Created</span></div>
              <div class="mini"><strong>{{ row.summary.pending }}</strong><span>Pending</span></div>
              <div class="mini"><strong>{{ row.summary.completion }}%</strong><span>Complete</span></div>
            </div>
            <div class="progress"><div style="width:{{ row.summary.completion }}%"></div></div>
          </article>
        {% else %}
          <div class="empty">No Test Plans yet. Create the first plan on the right.</div>
        {% endfor %}
      </div>
    </section>

    <aside id="create-plan" class="th-card panel">
      <h2 style="margin:0;font-size:18px;color:#16345e">Create Test Plan</h2>
      <div class="subtitle">Start with the coverage goal. Test cases can be attached immediately or added later.</div>
      <form method="post" action="{{ url_for('create_test_plan') }}">
        <div class="form-field"><label>Name</label><input name="name" required placeholder="Authentication Release Plan"></div>
        <div class="form-field"><label>Status</label><select name="status">{% for status in statuses %}<option>{{ status }}</option>{% endfor %}</select></div>
        <div class="form-field"><label>Description</label><textarea name="description" placeholder="Coverage required for authentication before release."></textarea></div>
        <button class="primary create-submit" type="submit">Create Test Plan</button>
      </form>
    </aside>
  </div>
</main>
</body></html>
'''


TEST_PLAN_PAGE_HTML = r'''
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ plan.name }} - Test Hub</title>
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<style>
{{ shell_css|safe }}
*{box-sizing:border-box}body{margin:0;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.top{display:flex;justify-content:space-between;gap:18px;align-items:flex-start;margin-bottom:18px}.top h1{margin:0;font-size:31px;letter-spacing:-.7px}.subtitle{margin-top:5px;color:var(--th-muted);font-size:13px}.actions{display:flex;gap:8px;flex-wrap:wrap}.primary,.secondary,.danger{border:0;border-radius:9px;padding:9px 12px;font:inherit;font-size:11px;font-weight:850;cursor:pointer;text-decoration:none;display:inline-flex;align-items:center;justify-content:center;gap:6px}.primary{background:linear-gradient(90deg,#1d6eff,#1468ff);color:#fff}.secondary{background:#f0f4fa;color:#243f61}.danger{background:#fff0ef;color:#b42318}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:11px;margin-bottom:18px}.stat{padding:15px;border:1px solid #dce6f4;border-radius:14px;background:#fff}.stat strong{display:block;font-size:24px;color:#17325d}.stat span{display:block;margin-top:4px;color:#71829a;font-size:11px;font-weight:750}.progress-card{padding:16px;margin-bottom:18px}.progress{height:10px;margin-top:10px;border-radius:999px;background:#e7edf6;overflow:hidden}.progress>div{height:100%;background:linear-gradient(90deg,#2f66e8,#2475ff)}.layout{display:grid;grid-template-columns:minmax(0,1.55fr) minmax(340px,.65fr);gap:18px;align-items:start}.panel{padding:20px}.panel h2{margin:0 0 13px;font-size:18px;color:#16345e}.checklist{display:flex;flex-direction:column}.item{display:grid;grid-template-columns:34px minmax(0,1fr) auto;gap:10px;align-items:start;padding:14px 0;border-top:1px solid #e7edf6}.item:first-child{border-top:0}.check{width:26px;height:26px;display:grid;place-items:center;border-radius:8px;background:#edf1f7;color:#73839a;font-weight:900}.check.created{background:#dcfce7;color:#166534}.item-title{font-size:13px;font-weight:900;color:#17325d}.item-feature{margin-top:3px;color:#71829a;font-size:11px}.item-notes{margin-top:5px;color:#60748f;font-size:11px;line-height:1.45}.linked-case{display:inline-flex;margin-top:7px;padding:5px 8px;border-radius:8px;background:#edf5ff;color:#1763d8;text-decoration:none;font-size:10px;font-weight:850}.state{display:inline-block;padding:4px 8px;border-radius:999px;font-size:10px;font-weight:850}.state.created{background:#dcfce7;color:#166534}.state.pending{background:#fff4d6;color:#8a5b00}.item-controls{display:flex;flex-direction:column;gap:6px;align-items:flex-end}.attach-inline{display:flex;gap:6px;align-items:center}.attach-inline select{max-width:240px;height:34px;border:1px solid #ccd9eb;border-radius:8px;padding:0 8px;background:#fff;color:#183252;font:inherit;font-size:10px}.side-stack{display:flex;flex-direction:column;gap:13px}.form-field{margin-top:10px}.form-field label{display:block;margin-bottom:5px;color:#314d6c;font-size:10px;font-weight:900}.form-field input,.form-field select,.form-field textarea{width:100%;border:1px solid #ccd9eb;border-radius:9px;background:#fff;color:#183252;font:inherit;font-size:11px;outline:none}.form-field input,.form-field select{height:39px;padding:0 10px}.form-field textarea{min-height:78px;padding:9px 10px;resize:vertical}.case-tools{display:flex;gap:7px;margin:8px 0}.case-tools input{flex:1;height:37px;border:1px solid #ccd9eb;border-radius:8px;padding:0 9px}.case-list{max-height:330px;overflow:auto;border:1px solid #dce6f3;border-radius:10px;background:#fff}.case-option{display:flex;gap:8px;align-items:flex-start;padding:9px 10px;border-top:1px solid #edf1f6}.case-option:first-child{border-top:0}.case-option input{width:16px;height:16px;margin:2px 0 0}.case-option strong{display:block;font-size:11px;color:#243854}.case-option span{font-size:10px;color:#71829a}.empty{padding:30px;text-align:center;color:#72839a;font-size:12px}.status-form{display:flex;gap:7px;align-items:center}.status-form select{height:36px;border:1px solid #ccd9eb;border-radius:8px;padding:0 8px;background:#fff}@media(max-width:980px){.layout{grid-template-columns:1fr}.stats{grid-template-columns:1fr 1fr}}@media(max-width:650px){.top{flex-direction:column}.item{grid-template-columns:30px 1fr}.item-controls{grid-column:2;align-items:flex-start}.attach-inline{flex-direction:column;align-items:stretch}.stats{grid-template-columns:1fr 1fr}}
</style>
</head><body>
{{ nav_html|safe }}
<main class="th-page">
  <div class="top">
    <div><h1>{{ plan.name }}</h1><div class="subtitle">{{ plan.description or 'QA coverage checklist' }}</div></div>
    <div class="actions">
      <form class="status-form" method="post" action="{{ url_for('update_test_plan_status', plan_id=plan.id) }}"><select name="status">{% for status in statuses %}<option {% if status == plan.status %}selected{% endif %}>{{ status }}</option>{% endfor %}</select><button class="secondary">Update status</button></form>
      <a class="secondary" href="{{ url_for('test_plans') }}">All Test Plans</a>
      <form method="post" action="{{ url_for('delete_test_plan', plan_id=plan.id) }}" onsubmit="return confirm('Delete this Test Plan?')"><button class="danger">Delete</button></form>
    </div>
  </div>

  <section class="stats">
    <div class="stat"><strong>{{ summary.total }}</strong><span>Planned</span></div>
    <div class="stat"><strong>{{ summary.created }}</strong><span>Created</span></div>
    <div class="stat"><strong>{{ summary.pending }}</strong><span>Pending</span></div>
    <div class="stat"><strong>{{ summary.completion }}%</strong><span>Complete</span></div>
  </section>
  <section class="th-card progress-card"><strong>Coverage progress: {{ summary.created }} / {{ summary.total }}</strong><div class="progress"><div style="width:{{ summary.completion }}%"></div></div></section>

  <div class="layout">
    <section class="th-card panel">
      <h2>Coverage checklist</h2>
      <div class="checklist">
        {% for item in plan.items %}
          {% set is_created = item.test_case is not none %}
          <div class="item">
            <div class="check {% if is_created %}created{% endif %}">{% if is_created %}✓{% else %}□{% endif %}</div>
            <div>
              <div class="item-title">{{ item.title_snapshot }}</div>
              <div class="item-feature">{{ item.feature_snapshot or 'Uncategorized' }}</div>
              {% if item.notes %}<div class="item-notes">{{ item.notes }}</div>{% endif %}
              {% if is_created %}<a class="linked-case" href="{{ url_for('test_case_details', case_key=item.test_case.case_key) }}">{{ item.test_case.case_key }} — {{ item.test_case.title }}</a>{% endif %}
            </div>
            <div class="item-controls">
              <span class="state {% if is_created %}created{% else %}pending{% endif %}">{% if is_created %}Created{% else %}Pending{% endif %}</span>
              {% if not is_created and attachable_cases %}
                <form class="attach-inline" method="post" action="{{ url_for('attach_test_plan_item_case', plan_id=plan.id, item_id=item.id) }}">
                  <select name="case_id" required><option value="">Attach Test Case…</option>{% for case in attachable_cases %}<option value="{{ case.id }}">{{ case.case_key }} — {{ case.title }}</option>{% endfor %}</select>
                  <button class="secondary">Attach</button>
                </form>
              {% endif %}
              <form method="post" action="{{ url_for('remove_test_plan_item', plan_id=plan.id, item_id=item.id) }}" onsubmit="return confirm('Remove this checklist item?')"><button class="danger">Remove</button></form>
            </div>
          </div>
        {% else %}<div class="empty">No planned coverage yet. Add a pending item or attach an existing Test Case.</div>{% endfor %}
      </div>
    </section>

    <aside class="side-stack">
      <section class="th-card panel">
        <h2>Attach existing Test Cases</h2>
        <form method="post" action="{{ url_for('attach_test_plan_cases', plan_id=plan.id) }}">
          <div class="case-tools"><input id="planCaseSearch" type="search" placeholder="Search ID, title or feature…"></div>
          <div id="planCaseList" class="case-list">
            {% for case in attachable_cases %}
              <label class="case-option" data-search="{{ (case.case_key ~ ' ' ~ case.title ~ ' ' ~ case.feature_name)|lower }}"><input type="checkbox" name="case_ids" value="{{ case.id }}"><span><strong>{{ case.case_key }} — {{ case.title }}</strong>{{ case.feature_name }} · {{ case.type }}</span></label>
            {% else %}<div class="empty">All current Test Cases are already attached.</div>{% endfor %}
          </div>
          {% if attachable_cases %}<button class="primary" style="width:100%;margin-top:10px" type="submit">Attach selected</button>{% endif %}
        </form>
      </section>

      <section class="th-card panel">
        <h2>Add planned Test Case</h2>
        <div class="subtitle">Use this when coverage is required but the real Test Case has not been created yet.</div>
        <form method="post" action="{{ url_for('add_test_plan_item', plan_id=plan.id) }}">
          <div class="form-field"><label>Feature / Module</label><input name="feature" required placeholder="Authentication"></div>
          <div class="form-field"><label>Planned test case</label><input name="title" required placeholder="Locked account handling"></div>
          <div class="form-field"><label>Notes</label><textarea name="notes" placeholder="Optional coverage notes"></textarea></div>
          <button class="primary" style="width:100%;margin-top:11px" type="submit">Add to checklist</button>
        </form>
      </section>
    </aside>
  </div>
</main>
<script>
const planCaseSearch=document.getElementById('planCaseSearch');
if(planCaseSearch){planCaseSearch.addEventListener('input',()=>{const query=planCaseSearch.value.trim().toLowerCase();document.querySelectorAll('#planCaseList .case-option').forEach(item=>{item.style.display=!query || item.dataset.search.includes(query)?'flex':'none';});});}
</script>
</body></html>
'''


def _patch_test_plans_navigation(ui_redesign):
    # Insert Test Plans between Test Cases and Test Runs in the shared navigation.
    test_runs_marker = '''    <details class="th-menu">\n      <summary>▷ <span>Test Runs</span>⌄</summary>'''
    test_plans_link = '''    <a class="th-nav-link" href="{{ url_for('test_plans') }}">☑ <span>Test Plans</span></a>\n'''

    if test_plans_link not in ui_redesign.NAV_HTML:
        ui_redesign.NAV_HTML = ui_redesign.NAV_HTML.replace(
            test_runs_marker,
            test_plans_link + test_runs_marker,
            1,
        )

    # MAIN_PAGE_HTML and RESULTS_PAGE_HTML already contain the navigation because
    # they are assembled when ui_redesign.py is imported, so patch those copies too.
    for name, value in list(vars(ui_redesign).items()):
        if name.endswith("_PAGE_HTML") and isinstance(value, str) and test_runs_marker in value and test_plans_link not in value:
            setattr(
                ui_redesign,
                name,
                value.replace(test_runs_marker, test_plans_link + test_runs_marker, 1),
            )


def register_test_plans(hub, ui_redesign):
    """Register Test Plans, coverage checklist models, pages, and routes."""
    if getattr(hub.app, "_test_plans_registered", False):
        return

    class TestPlan(hub.db.Model):
        __tablename__ = "test_plans"

        id = hub.db.Column(hub.db.Integer, primary_key=True)
        name = hub.db.Column(hub.db.String(250), nullable=False)
        description = hub.db.Column(hub.db.Text, nullable=False, default="")
        status = hub.db.Column(hub.db.String(20), nullable=False, default="Draft", index=True)
        created_at = hub.db.Column(
            hub.db.DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.now(timezone.utc),
        )
        updated_at = hub.db.Column(
            hub.db.DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.now(timezone.utc),
            onupdate=lambda: datetime.now(timezone.utc),
        )
        items = hub.db.relationship(
            "TestPlanItem",
            back_populates="test_plan",
            cascade="all, delete-orphan",
            order_by="TestPlanItem.position",
        )

    class TestPlanItem(hub.db.Model):
        __tablename__ = "test_plan_items"

        id = hub.db.Column(hub.db.Integer, primary_key=True)
        test_plan_id = hub.db.Column(
            hub.db.Integer,
            hub.db.ForeignKey("test_plans.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
        test_case_id = hub.db.Column(
            hub.db.Integer,
            hub.db.ForeignKey("test_cases.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        )
        position = hub.db.Column(hub.db.Integer, nullable=False)
        title_snapshot = hub.db.Column(hub.db.String(250), nullable=False)
        feature_snapshot = hub.db.Column(hub.db.String(120), nullable=False, default="")
        notes = hub.db.Column(hub.db.Text, nullable=False, default="")

        test_plan = hub.db.relationship("TestPlan", back_populates="items")
        test_case = hub.db.relationship("TestCase")

        @property
        def checklist_status(self):
            # A real linked Test Case means this planned coverage has been created.
            # If the Test Case is deleted later, the plan automatically returns to Pending.
            return "Created" if self.test_case is not None else "Pending"

    # Expose the models on app.py's module object so other Test Hub extensions can
    # reuse them later without importing this feature module directly.
    hub.TestPlan = TestPlan
    hub.TestPlanItem = TestPlanItem
    hub.PLAN_STATUSES = PLAN_STATUSES

    # app.py creates its original tables during import. Create only any missing
    # tables now that the Test Plan models have been registered in SQLAlchemy metadata.
    with hub.app.app_context():
        hub.db.create_all()

    _patch_test_plans_navigation(ui_redesign)

    def plan_summary(plan):
        # Calculate coverage from live Test Case relationships so progress cannot go stale.
        total = len(plan.items)
        created = sum(1 for item in plan.items if item.test_case is not None)
        pending = total - created
        completion = round((created / total) * 100, 1) if total else 0
        return {
            "total": total,
            "created": created,
            "pending": pending,
            "completion": completion,
        }

    def touch_plan(plan):
        # Keep the plan's updated timestamp aligned with checklist changes.
        plan.updated_at = datetime.now(timezone.utc)

    def next_position(plan):
        return max((item.position for item in plan.items), default=0) + 1

    @hub.app.get("/test-plans")
    def test_plans():
        plans = hub.db.session.scalars(
            hub.db.select(TestPlan).order_by(TestPlan.updated_at.desc(), TestPlan.id.desc())
        ).all()
        return hub.render_template_string(
            TEST_PLANS_PAGE_HTML,
            plan_rows=[{"plan": plan, "summary": plan_summary(plan)} for plan in plans],
            statuses=["Draft", "Active", "Completed"],
            nav_html=ui_redesign.NAV_HTML,
            shell_css=ui_redesign.SHELL_CSS,
        )

    @hub.app.post("/test-plans")
    def create_test_plan():
        name = hub.request.form.get("name", "").strip()
        description = hub.request.form.get("description", "").strip()
        status = hub.request.form.get("status", "Draft").strip()

        if not name:
            return "Test Plan name is required.", 400
        if status not in PLAN_STATUSES:
            return "Invalid Test Plan status.", 400

        plan = TestPlan(name=name, description=description, status=status)
        hub.db.session.add(plan)
        hub.db.session.commit()
        return hub.redirect(hub.url_for("test_plan_details", plan_id=plan.id))

    @hub.app.get("/test-plans/<int:plan_id>")
    def test_plan_details(plan_id):
        plan = hub.db.session.get(TestPlan, plan_id)
        if plan is None:
            return "Test Plan not found.", 404

        all_cases = hub.db.session.scalars(
            hub.db.select(hub.TestCase).order_by(hub.TestCase.feature, hub.TestCase.case_key)
        ).all()
        attached_case_ids = {
            item.test_case.id
            for item in plan.items
            if item.test_case is not None
        }
        attachable_cases = [case for case in all_cases if case.id not in attached_case_ids]

        return hub.render_template_string(
            TEST_PLAN_PAGE_HTML,
            plan=plan,
            summary=plan_summary(plan),
            statuses=["Draft", "Active", "Completed"],
            attachable_cases=attachable_cases,
            nav_html=ui_redesign.NAV_HTML,
            shell_css=ui_redesign.SHELL_CSS,
        )

    @hub.app.post("/test-plans/<int:plan_id>/planned-items")
    def add_test_plan_item(plan_id):
        plan = hub.db.session.get(TestPlan, plan_id)
        if plan is None:
            return "Test Plan not found.", 404

        feature = hub.request.form.get("feature", "").strip()
        title = hub.request.form.get("title", "").strip()
        notes = hub.request.form.get("notes", "").strip()
        if not feature or not title:
            return "Feature and planned test case are required.", 400

        # Pending items deliberately have no test_case_id until the real Test Case exists.
        plan.items.append(
            TestPlanItem(
                position=next_position(plan),
                title_snapshot=title,
                feature_snapshot=feature,
                notes=notes,
            )
        )
        touch_plan(plan)
        hub.db.session.commit()
        return hub.redirect(hub.url_for("test_plan_details", plan_id=plan.id))

    @hub.app.post("/test-plans/<int:plan_id>/attach-cases")
    def attach_test_plan_cases(plan_id):
        plan = hub.db.session.get(TestPlan, plan_id)
        if plan is None:
            return "Test Plan not found.", 404

        raw_case_ids = hub.request.form.getlist("case_ids")
        if not raw_case_ids:
            return "Select at least one Test Case.", 400

        try:
            case_ids = [int(value) for value in raw_case_ids]
        except ValueError:
            return "Invalid Test Case selection.", 400

        cases = hub.db.session.scalars(
            hub.db.select(hub.TestCase)
            .where(hub.TestCase.id.in_(case_ids))
            .order_by(hub.TestCase.feature, hub.TestCase.case_key)
        ).all()
        if len(cases) != len(set(case_ids)):
            return "One or more selected Test Cases no longer exist.", 400

        attached_case_ids = {
            item.test_case.id
            for item in plan.items
            if item.test_case is not None
        }
        position = next_position(plan)

        for case in cases:
            if case.id in attached_case_ids:
                continue
            # Existing Test Cases become completed checklist items immediately.
            plan.items.append(
                TestPlanItem(
                    test_case=case,
                    position=position,
                    title_snapshot=case.title,
                    feature_snapshot=case.feature_name,
                )
            )
            position += 1

        touch_plan(plan)
        hub.db.session.commit()
        return hub.redirect(hub.url_for("test_plan_details", plan_id=plan.id))

    @hub.app.post("/test-plans/<int:plan_id>/items/<int:item_id>/attach")
    def attach_test_plan_item_case(plan_id, item_id):
        plan = hub.db.session.get(TestPlan, plan_id)
        item = hub.db.session.get(TestPlanItem, item_id)
        if plan is None or item is None or item.test_plan_id != plan.id:
            return "Test Plan item not found.", 404

        raw_case_id = hub.request.form.get("case_id", "").strip()
        try:
            case_id = int(raw_case_id)
        except ValueError:
            return "Select a valid Test Case.", 400

        case = hub.db.session.get(hub.TestCase, case_id)
        if case is None:
            return "Test Case not found.", 404

        duplicate = any(
            other.id != item.id
            and other.test_case is not None
            and other.test_case.id == case.id
            for other in plan.items
        )
        if duplicate:
            return "That Test Case is already attached to this Test Plan.", 400

        # Keep the original planned title/feature as the coverage requirement and
        # link the real Test Case beside it as proof that the coverage was created.
        item.test_case = case
        touch_plan(plan)
        hub.db.session.commit()
        return hub.redirect(hub.url_for("test_plan_details", plan_id=plan.id))

    @hub.app.post("/test-plans/<int:plan_id>/items/<int:item_id>/remove")
    def remove_test_plan_item(plan_id, item_id):
        plan = hub.db.session.get(TestPlan, plan_id)
        item = hub.db.session.get(TestPlanItem, item_id)
        if plan is None or item is None or item.test_plan_id != plan.id:
            return "Test Plan item not found.", 404

        hub.db.session.delete(item)
        touch_plan(plan)
        hub.db.session.commit()
        return hub.redirect(hub.url_for("test_plan_details", plan_id=plan.id))

    @hub.app.post("/test-plans/<int:plan_id>/status")
    def update_test_plan_status(plan_id):
        plan = hub.db.session.get(TestPlan, plan_id)
        if plan is None:
            return "Test Plan not found.", 404

        status = hub.request.form.get("status", "").strip()
        if status not in PLAN_STATUSES:
            return "Invalid Test Plan status.", 400

        plan.status = status
        touch_plan(plan)
        hub.db.session.commit()
        return hub.redirect(hub.url_for("test_plan_details", plan_id=plan.id))

    @hub.app.post("/test-plans/<int:plan_id>/delete")
    def delete_test_plan(plan_id):
        plan = hub.db.session.get(TestPlan, plan_id)
        if plan is None:
            return "Test Plan not found.", 404

        hub.db.session.delete(plan)
        hub.db.session.commit()
        return hub.redirect(hub.url_for("test_plans"))

    # Explicitly detach Test Plan checklist items before deleting a Test Case.
    # This keeps planned coverage visible as Pending even if SQLite FK cascades are disabled.
    original_delete_case = hub.app.view_functions.get("delete_case")
    if original_delete_case is not None:
        @wraps(original_delete_case)
        def delete_case_with_test_plan_detach(case_key):
            case = hub.db.session.scalar(
                hub.db.select(hub.TestCase).where(hub.TestCase.case_key == case_key)
            )
            if case is not None:
                linked_items = hub.db.session.scalars(
                    hub.db.select(TestPlanItem).where(TestPlanItem.test_case_id == case.id)
                ).all()
                for item in linked_items:
                    item.test_case_id = None
                hub.db.session.commit()
            return original_delete_case(case_key)

        hub.app.view_functions["delete_case"] = delete_case_with_test_plan_detach

    hub.app._test_plans_registered = True
