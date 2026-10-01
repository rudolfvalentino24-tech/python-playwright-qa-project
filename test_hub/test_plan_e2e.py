import io
import re
from datetime import datetime, timezone
from functools import wraps
from html import escape

from pypdf import PdfReader


E2E_PLAN_TYPES = ("Feature", "Regression", "End-to-End", "Release", "Smoke", "Integration", "Exploratory")
E2E_PRIORITIES = ("P0", "P1", "P2", "P3")


E2E_CSS = r"""
.e2e-create-section{display:none}
.e2e-create-section.e2e-visible{display:block}
.e2e-workspace{margin-top:16px;padding:18px;border:1px solid #e4e7ec;border-radius:12px;background:#fff}
.e2e-workspace-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;margin-bottom:12px}
.e2e-workspace-head h2{margin:0!important;font-size:18px!important}.e2e-workspace-head p{margin:4px 0 0;color:#667085;font-size:11px}
.e2e-tabs{display:flex;gap:4px;flex-wrap:wrap;margin-bottom:14px;padding:4px;background:#f2f4f7;border-radius:9px;width:max-content;max-width:100%}
.e2e-tab{border:0;border-radius:7px;padding:8px 10px;background:transparent;color:#667085;font:inherit;font-size:10px;font-weight:800;cursor:pointer}
.e2e-tab.e2e-active{background:#fff;color:#101828;box-shadow:0 1px 2px rgba(16,24,40,.07)}
.e2e-panel{display:none}.e2e-panel.e2e-active{display:block}
.e2e-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}.e2e-card{padding:13px;border:1px solid #e4e7ec;border-radius:10px;background:#fcfcfd}
.e2e-card h3{margin:0 0 7px;font-size:12px;color:#344054}.e2e-card p,.e2e-text{margin:0;color:#667085;font-size:11px;line-height:1.55;white-space:pre-wrap}
.e2e-form{display:grid;gap:9px}.e2e-form label{display:block;color:#344054;font-size:10px;font-weight:800}.e2e-form input,.e2e-form select,.e2e-form textarea{width:100%;border:1px solid #d0d5dd;border-radius:8px;background:#fff;color:#344054;font:inherit;font-size:11px}
.e2e-form input,.e2e-form select{height:38px;padding:0 9px}.e2e-form textarea{min-height:92px;padding:9px;resize:vertical}
.e2e-row{display:flex;gap:8px;align-items:center;padding:8px 0;border-top:1px solid #eaecf0}.e2e-row:first-child{border-top:0}.e2e-row-main{flex:1;min-width:0}
.e2e-row strong{display:block;color:#344054;font-size:11px}.e2e-row span{display:block;color:#667085;font-size:10px;margin-top:2px}
.e2e-actions{display:flex;gap:6px;flex-wrap:wrap}.e2e-empty{padding:18px;text-align:center;color:#98a2b3;font-size:11px}
.e2e-coverage{width:100%;border-collapse:collapse;font-size:10px}.e2e-coverage th,.e2e-coverage td{padding:8px;border-top:1px solid #eaecf0;text-align:left;vertical-align:top}.e2e-coverage th{border-top:0;background:#f9fafb;color:#667085}
.e2e-coverage input,.e2e-coverage select{width:100%;height:32px;border:1px solid #d0d5dd;border-radius:7px;padding:0 7px;font:inherit;font-size:10px}
.e2e-dod{display:grid;gap:7px}.e2e-dod form{display:flex;gap:8px;align-items:flex-start}.e2e-dod label{display:flex;gap:8px;align-items:flex-start;color:#344054;font-size:11px;line-height:1.4;flex:1}.e2e-dod input[type=checkbox]{margin-top:2px}
.e2e-import-note{padding:10px;border-radius:8px;background:#f8fafc;color:#667085;font-size:10px;line-height:1.45}
@media(max-width:800px){.e2e-grid{grid-template-columns:1fr}}
"""


E2E_CREATE_FIELDS = r"""
<details class="plan-create-section e2e-create-section" data-e2e-create="1">
  <summary>End-to-End setup</summary>
  <div class="plan-create-body">
    <div class="plan-create-grid">
      <div class="form-field"><label>Application URL</label><input name="e2e_application_url" placeholder="https://example.test"></div>
      <div class="form-field"><label>Browser coverage</label><input name="e2e_browser_coverage" placeholder="Chromium, Firefox"></div>
    </div>
    <div class="plan-create-grid">
      <div class="form-field"><label>Automation style</label><input name="e2e_automation_style" placeholder="BDD + Page Object Model"></div>
      <div class="form-field"><label>Execution model</label><input name="e2e_execution_model" placeholder="Local headed / Jenkins headless"></div>
    </div>
    <div class="form-field"><label>Primary E2E journey</label><textarea name="e2e_primary_journey" placeholder="Login → Store → Cart → Checkout → Order → Logout"></textarea></div>
  </div>
</details>
"""


IMPORT_MODAL = r"""
<div id="prdImportTestPlan" class="prd-modal-backdrop">
  <div class="prd-modal prd-lg">
    <div class="prd-modal-head">
      <div><h2>Import Test Plan from PDF</h2><p>Extract an End-to-End Test Plan for review. Test Hub will only import sections it can identify.</p></div>
      <button class="prd-close" type="button" data-prd-close="prdImportTestPlan">×</button>
    </div>
    <div class="prd-modal-body">
      <form method="post" action="{{ url_for('import_test_plan_document') }}" enctype="multipart/form-data" class="e2e-form">
        <label>PDF document<input type="file" name="document" accept="application/pdf,.pdf" required></label>
        <label>Plan name override<input name="name" placeholder="Leave blank to use the document title"></label>
        <label>Status<select name="status"><option>Draft</option><option>Active</option><option>Completed</option></select></label>
        <div class="e2e-import-note">Imported objective, coverage, roles, journey, automation strategy, implementation notes and Definition of Done remain editable after import.</div>
        <button class="primary" type="submit">Import and review</button>
      </form>
    </div>
  </div>
</div>
"""


def _extract_pdf_text(file_storage):
    payload = file_storage.read()
    reader = PdfReader(io.BytesIO(payload))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _section_map(text_value):
    headings = [
        "Objective",
        "Technology and Execution Model",
        "Application Under Test",
        "Test Accounts and Roles",
        "Proposed E2E BDD Structure",
        "Coverage Plan - Authentication and Store",
        "Coverage Plan - Cart and Checkout",
        "Coverage Plan - Order Management",
        "Coverage Plan - Authorization and Session",
        "Primary End-to-End Scenario",
        "Test Data Strategy",
        "Page Object Strategy",
        "E2E Design Rules",
        "Jenkins Strategy",
        "Implementation Phases",
        "First Implementation Target",
        "Definition of Done for E2E-001",
    ]
    positions = []
    for heading in headings:
        match = re.search(rf"(?:^|\n)\s*\d+\.\s*{re.escape(heading)}\s*(?:\n|$)", text_value, flags=re.I)
        if match:
            positions.append((match.start(), match.end(), heading))
    positions.sort()
    sections = {}
    for index, (_, end, heading) in enumerate(positions):
        next_start = positions[index + 1][0] if index + 1 < len(positions) else len(text_value)
        sections[heading] = text_value[end:next_start].strip()
    return sections


def _first_url(value):
    match = re.search(r"https?://[^\s]+", value or "")
    return match.group(0).rstrip(".,)") if match else ""


def _metadata_value(text_value, label):
    match = re.search(rf"(?:^|\n)\s*{re.escape(label)}\s+([^\n]+)", text_value or "", flags=re.I)
    return match.group(1).strip() if match else ""


def _extract_title(text_value, filename):
    lines = [line.strip() for line in text_value.splitlines() if line.strip()]
    for line in lines[:12]:
        if "test plan" in line.lower() and len(line) <= 160:
            return line
    stem = re.sub(r"\.pdf$", "", filename or "Imported E2E Test Plan", flags=re.I)
    return stem.replace("_", " ").strip() or "Imported E2E Test Plan"


def _extract_coverage(text_value):
    normalized = re.sub(r"\s+", " ", text_value or "")
    pattern = re.compile(
        r"\b(?P<case>[A-Z][A-Z0-9-]*-\d{1,3})\s+"
        r"(?P<body>.+?)\s+"
        r"(?P<priority>P[0-3])\s+"
        r"(?P<feature>[A-Za-z0-9_.-]+\.feature)\b",
        flags=re.I,
    )
    rows = []
    seen = set()
    for match in pattern.finditer(normalized):
        case_key = match.group("case").upper()
        if case_key in seen:
            continue
        seen.add(case_key)
        body = match.group("body").strip()
        tokens = body.split()
        area = tokens[0] if tokens else "E2E"
        scenario = " ".join(tokens[1:]).strip() or body
        rows.append({
            "reference": case_key,
            "area": area[:120],
            "scenario": scenario[:250],
            "priority": match.group("priority").upper(),
            "automation_target": match.group("feature"),
        })
    return rows


def _extract_roles(section):
    rows = []
    for raw in (section or "").splitlines():
        line = re.sub(r"\s+", " ", raw.strip())
        if not line or line.lower().startswith("user role"):
            continue
        if line.lower().startswith("credential handling"):
            break
        if "end-to-end test plan" in line.lower():
            break
        match = re.match(r"([A-Za-z0-9_.-]+)\s+([A-Za-z0-9_.-]+)\s+(.+)", line)
        if match:
            rows.append({"fixture_user": match.group(1), "role": match.group(2), "purpose": match.group(3)})
    return rows


def _extract_bullets(section):
    lines = []
    for raw in (section or "").splitlines():
        line = raw.strip().lstrip("•- ").strip()
        if line and not re.match(r"^\d+\s*$", line):
            lines.append(line)
    return lines


E2E_CREATE_SCRIPT = r"""
<script data-test-plan-e2e-create-js>
(function(){
  function toggle(){
    const type=document.querySelector('#create-plan select[name="plan_type"]');
    const section=document.querySelector('#create-plan [data-e2e-create]');
    if(!type||!section)return;
    section.classList.toggle('e2e-visible', type.value==='End-to-End');
  }
  document.addEventListener('change',function(event){
    if(event.target && event.target.matches('#create-plan select[name="plan_type"]'))toggle();
  });
  toggle();
})();
</script>
"""


E2E_PAGE_SCRIPT = r"""
<script data-test-plan-e2e-js>
(function(){
  document.addEventListener('click',function(event){
    const tab=event.target.closest('[data-e2e-tab]');
    if(!tab)return;
    const workspace=tab.closest('[data-test-plan-e2e-workspace]');
    if(!workspace)return;
    workspace.querySelectorAll('[data-e2e-tab]').forEach(x=>x.classList.remove('e2e-active'));
    workspace.querySelectorAll('[data-e2e-panel]').forEach(x=>x.classList.remove('e2e-active'));
    tab.classList.add('e2e-active');
    const panel=workspace.querySelector('[data-e2e-panel="'+tab.dataset.e2eTab+'"]');
    if(panel)panel.classList.add('e2e-active');
  });
})();
</script>
"""


E2E_WORKSPACE = r"""
<section class="e2e-workspace" data-test-plan-e2e-workspace="1">
  <div class="e2e-workspace-head">
    <div><h2>End-to-End design</h2><p>Plan the complete business journey, data, roles, automation architecture, implementation phases and Definition of Done.</p></div>
  </div>
  <div class="e2e-tabs">
    <button type="button" class="e2e-tab e2e-active" data-e2e-tab="journey">Journey</button>
    <button type="button" class="e2e-tab" data-e2e-tab="coverage">Coverage design</button>
    <button type="button" class="e2e-tab" data-e2e-tab="data">Data & Roles</button>
    <button type="button" class="e2e-tab" data-e2e-tab="automation">Automation</button>
    <button type="button" class="e2e-tab" data-e2e-tab="delivery">Phases & DoD</button>
  </div>

  <div class="e2e-panel e2e-active" data-e2e-panel="journey">
    <form class="e2e-form" method="post" action="{{ url_for('update_test_plan_e2e_profile', plan_id=plan.id) }}">
      <div class="e2e-grid">
        <label>Application URL<input name="application_url" value="{{ profile.application_url }}"></label>
        <label>Browser coverage<input name="browser_coverage" value="{{ profile.browser_coverage }}" placeholder="Chromium, Firefox"></label>
        <label>Automation style<input name="automation_style" value="{{ profile.automation_style }}" placeholder="BDD + Page Object Model"></label>
        <label>Execution model<input name="execution_model" value="{{ profile.execution_model }}" placeholder="Local headed / Jenkins headless"></label>
      </div>
      <label>Primary E2E journey<textarea name="primary_journey">{{ profile.primary_journey }}</textarea></label>
      <label>First implementation target<textarea name="first_target">{{ profile.first_target }}</textarea></label>
      <button class="secondary" type="submit">Save journey</button>
    </form>
  </div>

  <div class="e2e-panel" data-e2e-panel="coverage">
    <div style="overflow:auto">
      <table class="e2e-coverage">
        <thead><tr><th>Reference</th><th>Area / planned scenario</th><th>Priority</th><th>Automation target</th><th>Test Case</th><th></th></tr></thead>
        <tbody>
        {% for row in coverage_rows %}
          <tr>
            <td><form id="e2eMeta{{ row.item.id }}" method="post" action="{{ url_for('update_test_plan_coverage_meta', plan_id=plan.id, item_id=row.item.id) }}"></form><input form="e2eMeta{{ row.item.id }}" name="reference" value="{{ row.meta.reference if row.meta else '' }}" placeholder="AUTH-01"></td>
            <td><strong>{{ row.item.feature_snapshot }}</strong><div>{{ row.item.title_snapshot }}</div></td>
            <td><select form="e2eMeta{{ row.item.id }}" name="priority">{% for value in priorities %}<option {% if row.meta and row.meta.priority == value %}selected{% endif %}>{{ value }}</option>{% endfor %}</select></td>
            <td><input form="e2eMeta{{ row.item.id }}" name="automation_target" value="{{ row.meta.automation_target if row.meta else '' }}" placeholder="authentication.feature"></td>
            <td>{% if row.item.test_case %}<a href="{{ url_for('test_case_details', case_key=row.item.test_case.case_key) }}">{{ row.item.test_case.case_key }}</a>{% else %}Pending{% endif %}</td>
            <td><button form="e2eMeta{{ row.item.id }}" class="secondary">Save</button></td>
          </tr>
        {% else %}<tr><td colspan="6"><div class="e2e-empty">No planned coverage yet.</div></td></tr>{% endfor %}
        </tbody>
      </table>
    </div>
  </div>

  <div class="e2e-panel" data-e2e-panel="data">
    <div class="e2e-grid">
      <div class="e2e-card">
        <h3>Test accounts and roles</h3>
        {% for role in roles %}
          <div class="e2e-row">
            <div class="e2e-row-main"><strong>{{ role.role_name }}</strong><span>{{ role.fixture_user or 'No fixture/user stored' }}{% if role.purpose %} · {{ role.purpose }}{% endif %}</span></div>
            <form method="post" action="{{ url_for('remove_test_plan_role', plan_id=plan.id, role_id=role.id) }}"><button class="danger">Remove</button></form>
          </div>
        {% else %}<div class="e2e-empty">No test roles yet. Store role/fixture names only, not passwords.</div>{% endfor %}
        <form class="e2e-form" method="post" action="{{ url_for('add_test_plan_role', plan_id=plan.id) }}">
          <label>Fixture / user<input name="fixture_user" placeholder="tester"></label>
          <label>Role<input name="role_name" required placeholder="admin"></label>
          <label>Purpose<input name="purpose" placeholder="Primary E2E admin user"></label>
          <button class="secondary">Add role</button>
        </form>
      </div>
      <div class="e2e-card">
        <h3>Test data strategy</h3>
        <form class="e2e-form" method="post" action="{{ url_for('update_test_plan_e2e_profile', plan_id=plan.id) }}">
          <textarea name="test_data_strategy">{{ profile.test_data_strategy }}</textarea>
          <button class="secondary">Save data strategy</button>
        </form>
      </div>
    </div>
  </div>

  <div class="e2e-panel" data-e2e-panel="automation">
    <form class="e2e-form" method="post" action="{{ url_for('update_test_plan_e2e_profile', plan_id=plan.id) }}">
      <div class="e2e-grid">
        <label>BDD structure<textarea name="bdd_structure">{{ profile.bdd_structure }}</textarea></label>
        <label>Page Object strategy<textarea name="page_object_strategy">{{ profile.page_object_strategy }}</textarea></label>
        <label>E2E design rules<textarea name="design_rules">{{ profile.design_rules }}</textarea></label>
        <label>Jenkins strategy<textarea name="jenkins_strategy">{{ profile.jenkins_strategy }}</textarea></label>
      </div>
      <button class="secondary">Save automation strategy</button>
    </form>
  </div>

  <div class="e2e-panel" data-e2e-panel="delivery">
    <div class="e2e-grid">
      <div class="e2e-card">
        <h3>Implementation phases</h3>
        {% for phase in phases %}
          <div class="e2e-row"><div class="e2e-row-main"><strong>{{ phase.position }}. {{ phase.focus }} · {{ phase.status }}</strong><span>{{ phase.outcome }}</span></div><form method="post" action="{{ url_for('remove_test_plan_phase', plan_id=plan.id, phase_id=phase.id) }}"><button class="danger">Remove</button></form></div>
        {% else %}<div class="e2e-empty">No implementation phases yet.</div>{% endfor %}
        <form class="e2e-form" method="post" action="{{ url_for('add_test_plan_phase', plan_id=plan.id) }}">
          <label>Focus<input name="focus" required placeholder="Full purchase happy path"></label>
          <label>Outcome<input name="outcome" placeholder="One stable E2E journey passing locally and in Jenkins"></label>
          <label>Status<select name="status"><option>Planned</option><option>In Progress</option><option>Completed</option></select></label>
          <button class="secondary">Add phase</button>
        </form>
      </div>
      <div class="e2e-card">
        <h3>Definition of Done</h3>
        <div class="e2e-dod">
        {% for item in dod %}
          <div class="e2e-row">
            <form method="post" action="{{ url_for('toggle_test_plan_dod', plan_id=plan.id, item_id=item.id) }}"><label><input type="checkbox" {% if item.completed %}checked{% endif %} onchange="this.form.submit()"><span {% if item.completed %}style="text-decoration:line-through;color:#98a2b3"{% endif %}>{{ item.text }}</span></label></form>
            <form method="post" action="{{ url_for('remove_test_plan_dod', plan_id=plan.id, item_id=item.id) }}"><button class="danger">Remove</button></form>
          </div>
        {% else %}<div class="e2e-empty">No Definition of Done criteria yet.</div>{% endfor %}
        </div>
        <form class="e2e-form" method="post" action="{{ url_for('add_test_plan_dod', plan_id=plan.id) }}">
          <label>Criterion<input name="text" required placeholder="Scenario passes in Jenkins headless mode"></label>
          <button class="secondary">Add criterion</button>
        </form>
      </div>
    </div>
    <div class="e2e-card" style="margin-top:10px">
      <h3>Implementation notes</h3>
      <form class="e2e-form" method="post" action="{{ url_for('update_test_plan_e2e_profile', plan_id=plan.id) }}">
        <textarea name="implementation_notes">{{ profile.implementation_notes }}</textarea>
        <button class="secondary">Save implementation notes</button>
      </form>
    </div>
  </div>
</section>
"""


def register_test_plan_e2e(hub, test_plan_strategy):
    """Add End-to-End plan design, coverage metadata, roles, phases, DoD and PDF import."""
    if getattr(hub.app, "_test_plan_e2e_registered", False):
        return

    test_plan_strategy.PLAN_TYPES = E2E_PLAN_TYPES

    class TestPlanE2EProfile(hub.db.Model):
        __tablename__ = "test_plan_e2e_profiles"
        id = hub.db.Column(hub.db.Integer, primary_key=True)
        test_plan_id = hub.db.Column(hub.db.Integer, hub.db.ForeignKey("test_plans.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
        application_url = hub.db.Column(hub.db.String(500), nullable=False, default="")
        automation_style = hub.db.Column(hub.db.String(250), nullable=False, default="")
        execution_model = hub.db.Column(hub.db.String(250), nullable=False, default="")
        browser_coverage = hub.db.Column(hub.db.String(250), nullable=False, default="")
        bdd_structure = hub.db.Column(hub.db.Text, nullable=False, default="")
        primary_journey = hub.db.Column(hub.db.Text, nullable=False, default="")
        test_data_strategy = hub.db.Column(hub.db.Text, nullable=False, default="")
        page_object_strategy = hub.db.Column(hub.db.Text, nullable=False, default="")
        design_rules = hub.db.Column(hub.db.Text, nullable=False, default="")
        jenkins_strategy = hub.db.Column(hub.db.Text, nullable=False, default="")
        implementation_notes = hub.db.Column(hub.db.Text, nullable=False, default="")
        first_target = hub.db.Column(hub.db.Text, nullable=False, default="")

    class TestPlanRole(hub.db.Model):
        __tablename__ = "test_plan_roles"
        id = hub.db.Column(hub.db.Integer, primary_key=True)
        test_plan_id = hub.db.Column(hub.db.Integer, hub.db.ForeignKey("test_plans.id", ondelete="CASCADE"), nullable=False, index=True)
        fixture_user = hub.db.Column(hub.db.String(120), nullable=False, default="")
        role_name = hub.db.Column(hub.db.String(120), nullable=False)
        purpose = hub.db.Column(hub.db.String(300), nullable=False, default="")

    class TestPlanPhase(hub.db.Model):
        __tablename__ = "test_plan_phases"
        id = hub.db.Column(hub.db.Integer, primary_key=True)
        test_plan_id = hub.db.Column(hub.db.Integer, hub.db.ForeignKey("test_plans.id", ondelete="CASCADE"), nullable=False, index=True)
        position = hub.db.Column(hub.db.Integer, nullable=False, default=1)
        focus = hub.db.Column(hub.db.String(220), nullable=False)
        outcome = hub.db.Column(hub.db.String(400), nullable=False, default="")
        status = hub.db.Column(hub.db.String(30), nullable=False, default="Planned")

    class TestPlanDefinitionItem(hub.db.Model):
        __tablename__ = "test_plan_definition_items"
        id = hub.db.Column(hub.db.Integer, primary_key=True)
        test_plan_id = hub.db.Column(hub.db.Integer, hub.db.ForeignKey("test_plans.id", ondelete="CASCADE"), nullable=False, index=True)
        position = hub.db.Column(hub.db.Integer, nullable=False, default=1)
        text = hub.db.Column(hub.db.String(500), nullable=False)
        completed = hub.db.Column(hub.db.Boolean, nullable=False, default=False)

    class TestPlanCoverageMeta(hub.db.Model):
        __tablename__ = "test_plan_coverage_meta"
        id = hub.db.Column(hub.db.Integer, primary_key=True)
        test_plan_item_id = hub.db.Column(hub.db.Integer, hub.db.ForeignKey("test_plan_items.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
        reference = hub.db.Column(hub.db.String(80), nullable=False, default="")
        priority = hub.db.Column(hub.db.String(10), nullable=False, default="P1")
        automation_target = hub.db.Column(hub.db.String(240), nullable=False, default="")

    hub.TestPlanE2EProfile = TestPlanE2EProfile
    hub.TestPlanRole = TestPlanRole
    hub.TestPlanPhase = TestPlanPhase
    hub.TestPlanDefinitionItem = TestPlanDefinitionItem
    hub.TestPlanCoverageMeta = TestPlanCoverageMeta

    with hub.app.app_context():
        hub.db.create_all()

    def plan_or_none(plan_id):
        return hub.db.session.get(hub.TestPlan, plan_id)

    def is_e2e(plan):
        return plan is not None and (plan.plan_type or "") == "End-to-End"

    def get_profile(plan_id, create=False):
        profile = hub.db.session.scalar(hub.db.select(TestPlanE2EProfile).where(TestPlanE2EProfile.test_plan_id == plan_id))
        if profile is None and create:
            profile = TestPlanE2EProfile(test_plan_id=plan_id)
            hub.db.session.add(profile)
        return profile

    def next_position(model, plan_id):
        positions = hub.db.session.scalars(hub.db.select(model.position).where(model.test_plan_id == plan_id)).all()
        return max(positions, default=0) + 1

    def touch(plan):
        plan.updated_at = datetime.now(timezone.utc)

    def render_workspace(plan):
        profile = get_profile(plan.id, create=True)
        hub.db.session.flush()
        roles = hub.db.session.scalars(hub.db.select(TestPlanRole).where(TestPlanRole.test_plan_id == plan.id).order_by(TestPlanRole.id)).all()
        phases = hub.db.session.scalars(hub.db.select(TestPlanPhase).where(TestPlanPhase.test_plan_id == plan.id).order_by(TestPlanPhase.position, TestPlanPhase.id)).all()
        dod = hub.db.session.scalars(hub.db.select(TestPlanDefinitionItem).where(TestPlanDefinitionItem.test_plan_id == plan.id).order_by(TestPlanDefinitionItem.position, TestPlanDefinitionItem.id)).all()
        metas = {}
        item_ids = [item.id for item in plan.items]
        if item_ids:
            for meta in hub.db.session.scalars(hub.db.select(TestPlanCoverageMeta).where(TestPlanCoverageMeta.test_plan_item_id.in_(item_ids))).all():
                metas[meta.test_plan_item_id] = meta
        coverage_rows = [{"item": item, "meta": metas.get(item.id)} for item in plan.items]
        return hub.render_template_string(E2E_WORKSPACE, plan=plan, profile=profile, roles=roles, phases=phases, dod=dod, coverage_rows=coverage_rows, priorities=E2E_PRIORITIES)

    original_list = hub.app.view_functions.get("test_plans")
    if original_list is not None:
        @wraps(original_list)
        def test_plans_with_e2e():
            response = hub.app.make_response(original_list())
            if response.status_code != 200 or "text/html" not in (response.content_type or ""):
                return response
            html = response.get_data(as_text=True)
            if "data-e2e-create" not in html:
                marker = '<details class="plan-create-section">\n  <summary>Quality criteria</summary>'
                if marker in html:
                    html = html.replace(marker, E2E_CREATE_FIELDS + "\n" + marker, 1)
            if "prdImportTestPlan" not in html:
                modal = hub.render_template_string(IMPORT_MODAL)
                html = html.replace("</body>", modal + E2E_CREATE_SCRIPT + "</body>", 1)
                button = '<button type="button" class="secondary" data-prd-open="prdImportTestPlan">Import PDF</button>'
                create_link = '<a class="primary" href="#create-plan">＋ Create Test Plan</a>'
                if create_link in html:
                    html = html.replace(create_link, button + create_link, 1)
            if "data-test-plan-e2e-css" not in html:
                html = html.replace("</head>", f'<style data-test-plan-e2e-css>{E2E_CSS}</style></head>', 1)
            response.set_data(html)
            return response
        hub.app.view_functions["test_plans"] = test_plans_with_e2e

    original_create = hub.app.view_functions.get("create_test_plan")
    if original_create is not None:
        @wraps(original_create)
        def create_test_plan_with_e2e():
            before_id = hub.db.session.scalar(hub.db.select(hub.TestPlan.id).order_by(hub.TestPlan.id.desc()).limit(1)) or 0
            response = hub.app.make_response(original_create())
            if not (300 <= response.status_code < 400):
                return response
            plan = hub.db.session.scalar(hub.db.select(hub.TestPlan).where(hub.TestPlan.id > before_id).order_by(hub.TestPlan.id.desc()))
            if not is_e2e(plan):
                return response
            profile = get_profile(plan.id, create=True)
            profile.application_url = hub.request.form.get("e2e_application_url", "").strip()
            profile.automation_style = hub.request.form.get("e2e_automation_style", "").strip()
            profile.execution_model = hub.request.form.get("e2e_execution_model", "").strip()
            profile.browser_coverage = hub.request.form.get("e2e_browser_coverage", "").strip()
            profile.primary_journey = hub.request.form.get("e2e_primary_journey", "").strip()
            touch(plan)
            hub.db.session.commit()
            return response
        hub.app.view_functions["create_test_plan"] = create_test_plan_with_e2e

    original_details = hub.app.view_functions.get("test_plan_details")
    if original_details is not None:
        @wraps(original_details)
        def test_plan_details_with_e2e(plan_id):
            response = hub.app.make_response(original_details(plan_id))
            plan = plan_or_none(plan_id)
            if response.status_code != 200 or not is_e2e(plan) or "text/html" not in (response.content_type or ""):
                return response
            html = response.get_data(as_text=True)
            planned_action = f'action="/test-plans/{plan.id}/planned-items"'
            form_pos = html.find(planned_action)
            if form_pos >= 0 and 'name="e2e_priority"' not in html[form_pos:form_pos + 1800]:
                form_start = html.rfind("<form", 0, form_pos)
                form_end = html.find("</form>", form_pos)
                notes_pos = html.find('<div class="form-field"><label>Notes</label>', form_start, form_end)
                if notes_pos >= 0:
                    extra = (
                        '<div class="plan-create-grid">'
                        '<div class="form-field"><label>Priority</label><select name="e2e_priority">'
                        + "".join(f"<option>{value}</option>" for value in E2E_PRIORITIES)
                        + '</select></div>'
                        '<div class="form-field"><label>Automation target</label><input name="e2e_automation_target" placeholder="authentication.feature"></div>'
                        '</div>'
                    )
                    html = html[:notes_pos] + extra + html[notes_pos:]
            if 'data-test-plan-e2e-workspace="1"' not in html:
                workspace = render_workspace(plan)
                scope_marker = '<article class="th-card process-card" id="scope">'
                if scope_marker in html:
                    close_at = html.find("</article>", html.find(scope_marker))
                    if close_at >= 0:
                        html = html[:close_at] + workspace + html[close_at:]
                else:
                    html = html.replace("</main>", workspace + "</main>", 1)
            if "data-test-plan-e2e-css" not in html:
                html = html.replace("</head>", f'<style data-test-plan-e2e-css>{E2E_CSS}</style></head>', 1)
            if "data-test-plan-e2e-js" not in html:
                html = html.replace("</body>", E2E_PAGE_SCRIPT + "</body>", 1)
            response.set_data(html)
            return response
        hub.app.view_functions["test_plan_details"] = test_plan_details_with_e2e

    original_add_item = hub.app.view_functions.get("add_test_plan_item")
    if original_add_item is not None:
        @wraps(original_add_item)
        def add_test_plan_item_with_e2e(plan_id):
            plan = plan_or_none(plan_id)
            before_ids = {item.id for item in plan.items} if plan else set()
            response = hub.app.make_response(original_add_item(plan_id))
            if not (300 <= response.status_code < 400) or not is_e2e(plan):
                return response
            hub.db.session.refresh(plan)
            item = next((candidate for candidate in plan.items if candidate.id not in before_ids), None)
            if item is not None:
                priority = hub.request.form.get("e2e_priority", "P1").strip()
                if priority not in E2E_PRIORITIES:
                    priority = "P1"
                hub.db.session.add(TestPlanCoverageMeta(
                    test_plan_item_id=item.id,
                    reference="",
                    priority=priority,
                    automation_target=hub.request.form.get("e2e_automation_target", "").strip(),
                ))
                hub.db.session.commit()
            return response
        hub.app.view_functions["add_test_plan_item"] = add_test_plan_item_with_e2e

    @hub.app.post("/test-plans/<int:plan_id>/e2e/profile")
    def update_test_plan_e2e_profile(plan_id):
        plan = plan_or_none(plan_id)
        if not is_e2e(plan):
            return "End-to-End Test Plan not found.", 404
        profile = get_profile(plan.id, create=True)
        fields = (
            "application_url", "automation_style", "execution_model", "browser_coverage",
            "bdd_structure", "primary_journey", "test_data_strategy", "page_object_strategy",
            "design_rules", "jenkins_strategy", "implementation_notes", "first_target",
        )
        for field in fields:
            if field in hub.request.form:
                setattr(profile, field, hub.request.form.get(field, "").strip())
        touch(plan)
        hub.db.session.commit()
        return hub.redirect(hub.url_for("test_plan_details", plan_id=plan.id))

    @hub.app.post("/test-plans/<int:plan_id>/e2e/roles")
    def add_test_plan_role(plan_id):
        plan = plan_or_none(plan_id)
        if not is_e2e(plan):
            return "End-to-End Test Plan not found.", 404
        role_name = hub.request.form.get("role_name", "").strip()
        if not role_name:
            return "Role is required.", 400
        hub.db.session.add(TestPlanRole(test_plan_id=plan.id, fixture_user=hub.request.form.get("fixture_user", "").strip(), role_name=role_name, purpose=hub.request.form.get("purpose", "").strip()))
        touch(plan)
        hub.db.session.commit()
        return hub.redirect(hub.url_for("test_plan_details", plan_id=plan.id))

    @hub.app.post("/test-plans/<int:plan_id>/e2e/roles/<int:role_id>/remove")
    def remove_test_plan_role(plan_id, role_id):
        role = hub.db.session.get(TestPlanRole, role_id)
        if role is None or role.test_plan_id != plan_id:
            return "Role not found.", 404
        hub.db.session.delete(role)
        hub.db.session.commit()
        return hub.redirect(hub.url_for("test_plan_details", plan_id=plan_id))

    @hub.app.post("/test-plans/<int:plan_id>/e2e/phases")
    def add_test_plan_phase(plan_id):
        plan = plan_or_none(plan_id)
        if not is_e2e(plan):
            return "End-to-End Test Plan not found.", 404
        focus = hub.request.form.get("focus", "").strip()
        if not focus:
            return "Phase focus is required.", 400
        hub.db.session.add(TestPlanPhase(test_plan_id=plan.id, position=next_position(TestPlanPhase, plan.id), focus=focus, outcome=hub.request.form.get("outcome", "").strip(), status=hub.request.form.get("status", "Planned").strip() or "Planned"))
        touch(plan)
        hub.db.session.commit()
        return hub.redirect(hub.url_for("test_plan_details", plan_id=plan.id))

    @hub.app.post("/test-plans/<int:plan_id>/e2e/phases/<int:phase_id>/remove")
    def remove_test_plan_phase(plan_id, phase_id):
        phase = hub.db.session.get(TestPlanPhase, phase_id)
        if phase is None or phase.test_plan_id != plan_id:
            return "Phase not found.", 404
        hub.db.session.delete(phase)
        hub.db.session.commit()
        return hub.redirect(hub.url_for("test_plan_details", plan_id=plan_id))

    @hub.app.post("/test-plans/<int:plan_id>/e2e/dod")
    def add_test_plan_dod(plan_id):
        plan = plan_or_none(plan_id)
        if not is_e2e(plan):
            return "End-to-End Test Plan not found.", 404
        text_value = hub.request.form.get("text", "").strip()
        if not text_value:
            return "Definition of Done item is required.", 400
        hub.db.session.add(TestPlanDefinitionItem(test_plan_id=plan.id, position=next_position(TestPlanDefinitionItem, plan.id), text=text_value))
        touch(plan)
        hub.db.session.commit()
        return hub.redirect(hub.url_for("test_plan_details", plan_id=plan.id))

    @hub.app.post("/test-plans/<int:plan_id>/e2e/dod/<int:item_id>/toggle")
    def toggle_test_plan_dod(plan_id, item_id):
        item = hub.db.session.get(TestPlanDefinitionItem, item_id)
        if item is None or item.test_plan_id != plan_id:
            return "Definition of Done item not found.", 404
        item.completed = not item.completed
        hub.db.session.commit()
        return hub.redirect(hub.url_for("test_plan_details", plan_id=plan_id))

    @hub.app.post("/test-plans/<int:plan_id>/e2e/dod/<int:item_id>/remove")
    def remove_test_plan_dod(plan_id, item_id):
        item = hub.db.session.get(TestPlanDefinitionItem, item_id)
        if item is None or item.test_plan_id != plan_id:
            return "Definition of Done item not found.", 404
        hub.db.session.delete(item)
        hub.db.session.commit()
        return hub.redirect(hub.url_for("test_plan_details", plan_id=plan_id))

    @hub.app.post("/test-plans/<int:plan_id>/e2e/coverage/<int:item_id>")
    def update_test_plan_coverage_meta(plan_id, item_id):
        plan = plan_or_none(plan_id)
        item = hub.db.session.get(hub.TestPlanItem, item_id)
        if not is_e2e(plan) or item is None or item.test_plan_id != plan.id:
            return "Coverage item not found.", 404
        meta = hub.db.session.scalar(hub.db.select(TestPlanCoverageMeta).where(TestPlanCoverageMeta.test_plan_item_id == item.id))
        if meta is None:
            meta = TestPlanCoverageMeta(test_plan_item_id=item.id)
            hub.db.session.add(meta)
        priority = hub.request.form.get("priority", "P1").strip()
        meta.priority = priority if priority in E2E_PRIORITIES else "P1"
        meta.reference = hub.request.form.get("reference", "").strip()
        meta.automation_target = hub.request.form.get("automation_target", "").strip()
        touch(plan)
        hub.db.session.commit()
        return hub.redirect(hub.url_for("test_plan_details", plan_id=plan.id))

    @hub.app.post("/test-plans/import-document")
    def import_test_plan_document():
        document = hub.request.files.get("document")
        if document is None or not (document.filename or "").lower().endswith(".pdf"):
            return "Upload a PDF Test Plan.", 400
        try:
            text_value = _extract_pdf_text(document)
        except Exception as exc:
            return f"Unable to read PDF: {exc}", 400
        sections = _section_map(text_value)
        if not sections:
            return "The PDF does not contain recognizable numbered Test Plan sections.", 400
        status = hub.request.form.get("status", "Draft").strip()
        if status not in {"Draft", "Active", "Completed"}:
            return "Invalid Test Plan status.", 400
        name = hub.request.form.get("name", "").strip() or _extract_title(text_value, document.filename)
        objective = sections.get("Objective", "").strip()
        application_name = _metadata_value(text_value, "Application")
        plan = hub.TestPlan(
            name=name[:250], description="Imported from PDF for review.", status=status,
            plan_type="End-to-End", application=application_name[:120], feature="End-to-End", objective=objective,
            in_scope="", out_of_scope="", risks="", entry_criteria="", exit_criteria="", environment="",
        )
        hub.db.session.add(plan)
        hub.db.session.flush()

        app_section = sections.get("Application Under Test", "")
        tech_section = sections.get("Technology and Execution Model", "")
        profile = TestPlanE2EProfile(
            test_plan_id=plan.id,
            application_url=_first_url(app_section),
            automation_style=_metadata_value(text_value, "Automation style") or tech_section,
            execution_model=_metadata_value(text_value, "Execution") or tech_section,
            browser_coverage="",
            bdd_structure=sections.get("Proposed E2E BDD Structure", ""),
            primary_journey=sections.get("Primary End-to-End Scenario", ""),
            test_data_strategy=sections.get("Test Data Strategy", ""),
            page_object_strategy=sections.get("Page Object Strategy", ""),
            design_rules=sections.get("E2E Design Rules", ""),
            jenkins_strategy=sections.get("Jenkins Strategy", ""),
            implementation_notes=sections.get("Implementation Phases", ""),
            first_target=sections.get("First Implementation Target", ""),
        )
        browser_match = re.search(r"Browser coverage\s+(.+)", app_section, flags=re.I)
        if browser_match:
            profile.browser_coverage = browser_match.group(1).strip()
        hub.db.session.add(profile)

        for role in _extract_roles(sections.get("Test Accounts and Roles", "")):
            hub.db.session.add(TestPlanRole(test_plan_id=plan.id, fixture_user=role["fixture_user"], role_name=role["role"], purpose=role["purpose"]))

        coverage_text = "\n".join(value for key, value in sections.items() if key.startswith("Coverage Plan"))
        for position, row in enumerate(_extract_coverage(coverage_text), start=1):
            item = hub.TestPlanItem(test_plan_id=plan.id, position=position, title_snapshot=row["scenario"], feature_snapshot=row["area"], notes="Imported planned coverage")
            hub.db.session.add(item)
            hub.db.session.flush()
            hub.db.session.add(TestPlanCoverageMeta(test_plan_item_id=item.id, reference=row["reference"], priority=row["priority"], automation_target=row["automation_target"]))

        for dod_position, text_item in enumerate(_extract_bullets(sections.get("Definition of Done for E2E-001", "")), start=1):
            hub.db.session.add(TestPlanDefinitionItem(test_plan_id=plan.id, position=dod_position, text=text_item[:500]))

        touch(plan)
        hub.db.session.commit()
        return hub.redirect(hub.url_for("test_plan_details", plan_id=plan.id))

    original_report = hub.app.view_functions.get("test_plan_report")
    if original_report is not None:
        @wraps(original_report)
        def test_plan_report_with_e2e(plan_id):
            response = hub.app.make_response(original_report(plan_id))
            plan = plan_or_none(plan_id)
            if response.status_code != 200 or not is_e2e(plan) or "text/html" not in (response.content_type or ""):
                return response
            profile = get_profile(plan.id, create=True)
            roles = hub.db.session.scalars(hub.db.select(TestPlanRole).where(TestPlanRole.test_plan_id == plan.id).order_by(TestPlanRole.id)).all()
            phases = hub.db.session.scalars(hub.db.select(TestPlanPhase).where(TestPlanPhase.test_plan_id == plan.id).order_by(TestPlanPhase.position)).all()
            dod = hub.db.session.scalars(hub.db.select(TestPlanDefinitionItem).where(TestPlanDefinitionItem.test_plan_id == plan.id).order_by(TestPlanDefinitionItem.position)).all()
            html = response.get_data(as_text=True)
            if 'data-e2e-report="1"' not in html:
                role_html = "".join(f"<li><strong>{escape(role.role_name)}</strong> — {escape(role.fixture_user or 'fixture/user not recorded')} — {escape(role.purpose)}</li>" for role in roles) or "<li>No roles recorded.</li>"
                phase_html = "".join(f"<li><strong>{phase.position}. {escape(phase.focus)}</strong> — {escape(phase.status)}{(' — ' + escape(phase.outcome)) if phase.outcome else ''}</li>" for phase in phases) or "<li>No structured phases recorded.</li>"
                dod_html = "".join(f"<li>{'✓' if item.completed else '□'} {escape(item.text)}</li>" for item in dod) or "<li>No Definition of Done criteria recorded.</li>"
                section = f'''\n<section class="card" data-e2e-report="1">\n  <h2>End-to-End design</h2>\n  <div class="e2e-grid">\n    <div><strong>Application URL</strong><div>{escape(profile.application_url or '—')}</div></div>\n    <div><strong>Browser coverage</strong><div>{escape(profile.browser_coverage or '—')}</div></div>\n    <div><strong>Automation style</strong><div>{escape(profile.automation_style or '—')}</div></div>\n    <div><strong>Execution model</strong><div>{escape(profile.execution_model or '—')}</div></div>\n  </div>\n  <h3>Primary journey</h3><div style="white-space:pre-wrap">{escape(profile.primary_journey or 'Not defined')}</div>\n  <h3>Roles</h3><ul>{role_html}</ul>\n  <h3>Implementation phases</h3><ul>{phase_html}</ul>\n  <h3>Definition of Done</h3><ul>{dod_html}</ul>\n</section>\n'''
                report_marker = '<section class="card"><h2>Traceability matrix</h2>'
                html = html.replace(report_marker, section + report_marker, 1) if report_marker in html else html.replace("</main>", section + "</main>", 1)
            if "data-test-plan-e2e-css" not in html:
                html = html.replace("</head>", f'<style data-test-plan-e2e-css>{E2E_CSS}</style></head>', 1)
            response.set_data(html)
            return response
        hub.app.view_functions["test_plan_report"] = test_plan_report_with_e2e

    hub.app._test_plan_e2e_registered = True
