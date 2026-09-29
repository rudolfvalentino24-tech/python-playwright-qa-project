from pathlib import Path
from flask import Flask, jsonify, redirect, render_template_string, request, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
import os
import re
from datetime import datetime, timezone

BASE_DIR = Path(__file__).resolve().parent
JIRA_BASE_URL = os.environ.get("JIRA_BASE_URL", "https://qa-test-store.atlassian.net/browse")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "test-hub-dev-secret")

database_url = os.environ.get("DATABASE_URL", f"sqlite:///{BASE_DIR / 'test_hub.db'}")
if database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
elif database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}

db = SQLAlchemy(app)

PRIORITIES = {"Low", "Medium", "High", "Critical"}
TYPES = {"Manual", "Automated"}
STATUSES = {"Draft", "Ready", "Passed", "Failed", "Blocked"}
JIRA_KEY_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*-\d+$")
CASE_KEY_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9_-]{2,63}$")


class TestCase(db.Model):
    __tablename__ = "test_cases"

    id = db.Column(db.Integer, primary_key=True)
    case_key = db.Column(db.String(64), unique=True, nullable=False, index=True)
    title = db.Column(db.String(250), nullable=False)
    jira_key = db.Column(db.String(50), nullable=True, index=True)
    priority = db.Column(db.String(20), nullable=False, default="Medium")
    type = db.Column(db.String(20), nullable=False, default="Manual")
    status = db.Column(db.String(20), nullable=False, default="Draft", index=True)
    preconditions = db.Column(db.Text, nullable=False, default="")
    expected_result = db.Column(db.Text, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    steps = db.relationship(
        "TestStep",
        back_populates="test_case",
        cascade="all, delete-orphan",
        order_by="TestStep.position",
    )

    def to_dict(self):
        return {
            "id": self.case_key,
            "title": self.title,
            "jira_key": self.jira_key or "",
            "priority": self.priority,
            "type": self.type,
            "status": self.status,
            "preconditions": self.preconditions,
            "steps": [step.action for step in self.steps],
            "expected_result": self.expected_result,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class TestStep(db.Model):
    __tablename__ = "test_steps"

    id = db.Column(db.Integer, primary_key=True)
    test_case_id = db.Column(
        db.Integer,
        db.ForeignKey("test_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position = db.Column(db.Integer, nullable=False)
    action = db.Column(db.Text, nullable=False)

    test_case = db.relationship("TestCase", back_populates="steps")


def normalize_lines(value):
    return [line.strip() for line in value.splitlines() if line.strip()]


def next_case_key(jira_key=""):
    """Generate a readable ID per Jira story, e.g. SCRUM-6-TC-001."""
    prefix = f"{jira_key}-TC-" if jira_key else "TC-"
    pattern = re.compile(rf"^{re.escape(prefix)}(\d+)$")

    numbers = []
    for (case_key,) in db.session.execute(db.select(TestCase.case_key)).all():
        match = pattern.match(case_key or "")
        if match:
            numbers.append(int(match.group(1)))

    return f"{prefix}{max(numbers, default=0) + 1:03d}"


def validate_case_key(case_key):
    if not CASE_KEY_PATTERN.match(case_key):
        return "Test case ID may contain only letters, numbers, hyphens and underscores."
    existing = db.session.scalar(
        db.select(TestCase.id).where(TestCase.case_key == case_key)
    )
    if existing is not None:
        return f"Test case ID {case_key} already exists."
    return None


PAGE_HTML = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Test Hub</title>
<style>
:root{--bg:#f4f6f8;--surface:#fff;--text:#172b4d;--muted:#6b778c;--border:#dfe1e6;--accent:#0c66e4;--accent2:#0055cc;--danger:#ae2a19}
*{box-sizing:border-box}body{margin:0;font-family:Inter,Arial,sans-serif;background:var(--bg);color:var(--text)}
header{background:#172b4d;color:#fff;padding:18px 28px;display:flex;align-items:center;justify-content:space-between;gap:16px;position:sticky;top:0;z-index:5}
.brand{display:flex;align-items:center;gap:12px}.brand h1{font-size:22px;margin:0}.brand span{font-size:13px;opacity:.75}
main{max-width:1320px;margin:0 auto;padding:24px}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:20px}.stat{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:16px}.stat strong{display:block;font-size:26px}.stat span{color:var(--muted);font-size:13px}
.grid{display:grid;grid-template-columns:1.25fr .75fr;gap:18px}.card{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:18px}.card h2{margin:0 0 14px;font-size:18px}
.toolbar{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px}input,select,textarea,button{font:inherit}input,select,textarea{width:100%;padding:9px 10px;border:1px solid var(--border);border-radius:7px;background:#fff;color:var(--text)}textarea{min-height:82px;resize:vertical}.toolbar input{flex:1;min-width:220px}.toolbar select{width:160px}
button{border:0;border-radius:7px;padding:9px 13px;cursor:pointer;font-weight:600}.primary{background:var(--accent);color:#fff}.primary:hover{background:var(--accent2)}.secondary{background:#f1f2f4;color:var(--text)}.danger{background:#ffebe6;color:var(--danger)}
.case{border:1px solid var(--border);border-radius:9px;padding:14px;margin:10px 0}.case-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}.case-title{font-weight:700}.meta{display:flex;gap:7px;flex-wrap:wrap;margin:8px 0}.pill{font-size:12px;padding:3px 7px;border-radius:999px;background:#f1f2f4;color:#44546f}.jira{color:var(--accent);text-decoration:none;font-weight:600}.details{color:var(--muted);font-size:13px;white-space:pre-wrap}.actions{display:flex;gap:7px;flex-wrap:wrap;margin-top:10px;align-items:center}.button-link{display:inline-block;text-decoration:none;border-radius:7px;padding:9px 13px;font-weight:600}.rename-form{display:flex;gap:6px;align-items:center}.rename-form input{width:190px}
.form-row{display:grid;grid-template-columns:1fr 1fr;gap:10px}.field{margin-bottom:11px}.field label{display:block;font-size:12px;font-weight:700;color:#44546f;margin-bottom:5px}.hint{font-size:12px;color:var(--muted);margin-top:5px}.empty{text-align:center;color:var(--muted);padding:36px 10px}
@media(max-width:900px){.stats{grid-template-columns:1fr 1fr}.grid{grid-template-columns:1fr}.form-row{grid-template-columns:1fr}}@media(max-width:520px){.stats{grid-template-columns:1fr}main{padding:14px}header{padding:14px 16px}.rename-form{width:100%}.rename-form input{width:100%}}
</style>
</head>
<body>
<header>
  <div class="brand"><div style="font-size:26px">🧪</div><div><h1>Test Hub</h1><span>QA test case management</span></div></div>
  <div style="font-size:13px;opacity:.8">Automation execution: GitHub Actions</div>
</header>
<main>
  <section class="stats">
    <div class="stat"><strong>{{ stats.total }}</strong><span>Total test cases</span></div>
    <div class="stat"><strong>{{ stats.manual }}</strong><span>Manual</span></div>
    <div class="stat"><strong>{{ stats.automated }}</strong><span>Automated</span></div>
    <div class="stat"><strong>{{ stats.ready }}</strong><span>Ready</span></div>
  </section>

  <section class="grid">
    <div class="card">
      <h2>Test cases</h2>
      <div class="toolbar">
        <input id="search" placeholder="Search ID, title or Jira key…" oninput="filterCases()">
        <select id="typeFilter" onchange="filterCases()"><option value="">All types</option><option>Manual</option><option>Automated</option></select>
        <select id="statusFilter" onchange="filterCases()"><option value="">All statuses</option><option>Draft</option><option>Ready</option><option>Passed</option><option>Failed</option><option>Blocked</option></select>
      </div>

      <div id="caseList">
      {% for c in cases %}
        <article class="case" data-search="{{ (c.case_key ~ ' ' ~ c.title ~ ' ' ~ (c.jira_key or ''))|lower }}" data-type="{{ c.type }}" data-status="{{ c.status }}">
          <div class="case-head">
            <div>
              <div class="case-title">{{ c.case_key }} — {{ c.title }}</div>
              <div class="meta">
                <span class="pill">{{ c.type }}</span>
                <span class="pill">{{ c.priority }}</span>
                <span class="pill">{{ c.status }}</span>
                {% if c.jira_key %}<a class="jira" target="_blank" rel="noopener" href="{{ jira_base }}/{{ c.jira_key }}">{{ c.jira_key }}</a>{% endif %}
              </div>
            </div>
          </div>

          {% if c.preconditions %}<div class="details"><strong>Preconditions:</strong> {{ c.preconditions }}</div>{% endif %}
          <div class="details"><strong>Steps:</strong>
{% for step in c.steps %}{{ loop.index }}. {{ step.action }}{% if not loop.last %}
{% endif %}{% endfor %}</div>
          <div class="details" style="margin-top:7px"><strong>Expected:</strong> {{ c.expected_result }}</div>

          <div class="actions">
            <a class="secondary button-link" href="{{ url_for('edit_case', case_key=c.case_key) }}">Edit</a>

            <form method="post" action="{{ url_for('set_status', case_key=c.case_key) }}" style="display:flex;gap:6px">
              <select name="status" style="width:auto">{% for s in statuses %}<option value="{{ s }}" {% if s == c.status %}selected{% endif %}>{{ s }}</option>{% endfor %}</select>
              <button class="secondary">Update status</button>
            </form>

            <form method="post" action="{{ url_for('delete_case', case_key=c.case_key) }}" onsubmit="return confirm('Delete {{ c.case_key }}?')">
              <button class="danger">Delete</button>
            </form>
          </div>
        </article>
      {% else %}
        <div class="empty">No test cases yet. Create the first one on the right.</div>
      {% endfor %}
      </div>
    </div>

    <aside class="card">
      <h2>Create test case</h2>
      <form method="post" action="{{ url_for('create_case') }}">
        <div class="field">
          <label>Title</label>
          <input name="title" required placeholder="Unauthenticated user is redirected to login">
        </div>

        <div class="form-row">
          <div class="field">
            <label>Jira story</label>
            <input id="jiraKey" name="jira_key" placeholder="SCRUM-6" oninput="updateIdHint()">
          </div>
          <div class="field">
            <label>Test case ID</label>
            <input name="case_key" placeholder="Leave blank to auto-generate">
            <div class="hint" id="caseIdHint">Example: SCRUM-6-TC-001</div>
          </div>
        </div>

        <div class="form-row">
          <div class="field"><label>Priority</label><select name="priority"><option>Medium</option><option>High</option><option>Critical</option><option>Low</option></select></div>
          <div class="field"><label>Type</label><select name="type"><option>Manual</option><option>Automated</option></select></div>
        </div>

        <div class="field"><label>Status</label><select name="status"><option>Draft</option><option>Ready</option><option>Passed</option><option>Failed</option><option>Blocked</option></select></div>
        <div class="field"><label>Preconditions</label><textarea name="preconditions" placeholder="User is not logged in"></textarea></div>
        <div class="field"><label>Steps</label><textarea name="steps" required placeholder="Open the Test Hub main page"></textarea><div class="hint">One step per line.</div></div>
        <div class="field"><label>Expected result</label><textarea name="expected_result" required placeholder="User is redirected to the login page."></textarea></div>
        <button class="primary" type="submit">Create test case</button>
      </form>
    </aside>
  </section>
</main>

<script>
function filterCases(){
  const q=document.getElementById('search').value.trim().toLowerCase();
  const type=document.getElementById('typeFilter').value;
  const status=document.getElementById('statusFilter').value;
  document.querySelectorAll('.case').forEach(el=>{
    const okText=!q || el.dataset.search.includes(q);
    const okType=!type || el.dataset.type===type;
    const okStatus=!status || el.dataset.status===status;
    el.style.display=(okText&&okType&&okStatus)?'block':'none';
  });
}

function updateIdHint(){
  const jira=document.getElementById('jiraKey').value.trim().toUpperCase();
  document.getElementById('caseIdHint').textContent =
    jira ? `Auto-generated example: ${jira}-TC-001` : 'Without Jira: TC-001';
}
</script>
</body>
</html>
"""


@app.get("/")
def index():
    cases = db.session.scalars(db.select(TestCase).order_by(TestCase.id.desc())).all()
    stats = {
        "total": len(cases),
        "manual": sum(1 for c in cases if c.type == "Manual"),
        "automated": sum(1 for c in cases if c.type == "Automated"),
        "ready": sum(1 for c in cases if c.status == "Ready"),
    }
    return render_template_string(
        PAGE_HTML,
        cases=cases,
        stats=stats,
        statuses=["Draft", "Ready", "Passed", "Failed", "Blocked"],
        jira_base=JIRA_BASE_URL.rstrip("/"),
    )


@app.post("/test-cases")
def create_case():
    title = request.form.get("title", "").strip()
    jira_key = request.form.get("jira_key", "").strip().upper()
    requested_case_key = request.form.get("case_key", "").strip().upper()
    priority = request.form.get("priority", "Medium").strip()
    case_type = request.form.get("type", "Manual").strip()
    status = request.form.get("status", "Draft").strip()
    preconditions = request.form.get("preconditions", "").strip()
    steps = normalize_lines(request.form.get("steps", ""))
    expected_result = request.form.get("expected_result", "").strip()

    if not title or not steps or not expected_result:
        return "Title, steps and expected result are required.", 400
    if jira_key and not JIRA_KEY_PATTERN.match(jira_key):
        return "Jira key must look like SCRUM-6.", 400
    if priority not in PRIORITIES or case_type not in TYPES or status not in STATUSES:
        return "Invalid test case metadata.", 400

    case_key = requested_case_key or next_case_key(jira_key)
    key_error = validate_case_key(case_key)
    if key_error:
        return key_error, 400

    case = TestCase(
        case_key=case_key,
        title=title,
        jira_key=jira_key or None,
        priority=priority,
        type=case_type,
        status=status,
        preconditions=preconditions,
        expected_result=expected_result,
    )
    case.steps = [
        TestStep(position=index, action=action)
        for index, action in enumerate(steps, start=1)
    ]
    db.session.add(case)
    db.session.commit()
    return redirect(url_for("index"))


EDIT_PAGE_HTML = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Edit {{ case.case_key }} - Test Hub</title>
<style>
:root{--bg:#f4f6f8;--surface:#fff;--text:#172b4d;--muted:#6b778c;--border:#dfe1e6;--accent:#0c66e4;--accent2:#0055cc}
*{box-sizing:border-box}body{margin:0;font-family:Inter,Arial,sans-serif;background:var(--bg);color:var(--text)}
main{max-width:820px;margin:32px auto;padding:0 20px}.card{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:22px}
h1{margin:0 0 20px;font-size:22px}.field{margin-bottom:14px}.field label{display:block;font-size:12px;font-weight:700;color:#44546f;margin-bottom:5px}
.form-row{display:grid;grid-template-columns:1fr 1fr;gap:12px}input,select,textarea,button{font:inherit}input,select,textarea{width:100%;padding:9px 10px;border:1px solid var(--border);border-radius:7px;background:#fff;color:var(--text)}
textarea{min-height:100px;resize:vertical}.actions{display:flex;gap:10px;margin-top:18px}.primary{background:var(--accent);color:#fff;border:0;border-radius:7px;padding:10px 14px;font-weight:700;cursor:pointer}.primary:hover{background:var(--accent2)}
.cancel{background:#f1f2f4;color:var(--text);text-decoration:none;border-radius:7px;padding:10px 14px;font-weight:700}.hint{font-size:12px;color:var(--muted);margin-top:5px}
@media(max-width:650px){.form-row{grid-template-columns:1fr}}
</style>
</head>
<body>
<main>
  <div class="card">
    <h1>Edit test case</h1>
    <form method="post" action="{{ url_for('update_case', case_key=case.case_key) }}">
      <div class="form-row">
        <div class="field"><label>Test case ID</label><input name="case_key" value="{{ case.case_key }}" required></div>
        <div class="field"><label>Jira story</label><input name="jira_key" value="{{ case.jira_key or '' }}" placeholder="SCRUM-6"></div>
      </div>
      <div class="field"><label>Title</label><input name="title" value="{{ case.title }}" required></div>
      <div class="form-row">
        <div class="field"><label>Priority</label><select name="priority">{% for p in priorities %}<option value="{{ p }}" {% if p == case.priority %}selected{% endif %}>{{ p }}</option>{% endfor %}</select></div>
        <div class="field"><label>Type</label><select name="type">{% for t in types %}<option value="{{ t }}" {% if t == case.type %}selected{% endif %}>{{ t }}</option>{% endfor %}</select></div>
      </div>
      <div class="field"><label>Status</label><select name="status">{% for s in statuses %}<option value="{{ s }}" {% if s == case.status %}selected{% endif %}>{{ s }}</option>{% endfor %}</select></div>
      <div class="field"><label>Preconditions</label><textarea name="preconditions">{{ case.preconditions }}</textarea></div>
      <div class="field"><label>Steps</label><textarea name="steps" required>{% for step in case.steps %}{{ step.action }}{% if not loop.last %}
{% endif %}{% endfor %}</textarea><div class="hint">One step per line.</div></div>
      <div class="field"><label>Expected result</label><textarea name="expected_result" required>{{ case.expected_result }}</textarea></div>
      <div class="actions">
        <button class="primary" type="submit">Save changes</button>
        <a class="cancel" href="{{ url_for('index') }}">Cancel</a>
      </div>
    </form>
  </div>
</main>
</body>
</html>
"""


@app.get("/test-cases/<case_key>/edit")
def edit_case(case_key):
    case = db.session.scalar(
        db.select(TestCase).where(TestCase.case_key == case_key)
    )
    if case is None:
        return "Test case not found.", 404

    return render_template_string(
        EDIT_PAGE_HTML,
        case=case,
        priorities=["Low", "Medium", "High", "Critical"],
        types=["Manual", "Automated"],
        statuses=["Draft", "Ready", "Passed", "Failed", "Blocked"],
    )


@app.post("/test-cases/<case_key>/edit")
def update_case(case_key):
    case = db.session.scalar(
        db.select(TestCase).where(TestCase.case_key == case_key)
    )
    if case is None:
        return "Test case not found.", 404

    new_case_key = request.form.get("case_key", "").strip().upper()
    title = request.form.get("title", "").strip()
    jira_key = request.form.get("jira_key", "").strip().upper()
    priority = request.form.get("priority", "").strip()
    case_type = request.form.get("type", "").strip()
    status = request.form.get("status", "").strip()
    preconditions = request.form.get("preconditions", "").strip()
    steps = normalize_lines(request.form.get("steps", ""))
    expected_result = request.form.get("expected_result", "").strip()

    if not new_case_key or not title or not steps or not expected_result:
        return "Test case ID, title, steps and expected result are required.", 400
    if jira_key and not JIRA_KEY_PATTERN.match(jira_key):
        return "Jira key must look like SCRUM-6.", 400
    if priority not in PRIORITIES or case_type not in TYPES or status not in STATUSES:
        return "Invalid test case metadata.", 400

    if new_case_key != case.case_key:
        key_error = validate_case_key(new_case_key)
        if key_error:
            return key_error, 400

    case.case_key = new_case_key
    case.title = title
    case.jira_key = jira_key or None
    case.priority = priority
    case.type = case_type
    case.status = status
    case.preconditions = preconditions
    case.expected_result = expected_result
    case.updated_at = datetime.now(timezone.utc)
    case.steps = [
        TestStep(position=index, action=action)
        for index, action in enumerate(steps, start=1)
    ]

    db.session.commit()
    return redirect(url_for("index"))


@app.post("/test-cases/<case_key>/status")
def set_status(case_key):
    status = request.form.get("status", "").strip()
    if status not in STATUSES:
        return "Invalid status.", 400

    case = db.session.scalar(
        db.select(TestCase).where(TestCase.case_key == case_key)
    )
    if case is None:
        return "Test case not found.", 404

    case.status = status
    case.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return redirect(url_for("index"))


@app.post("/test-cases/<case_key>/delete")
def delete_case(case_key):
    case = db.session.scalar(
        db.select(TestCase).where(TestCase.case_key == case_key)
    )
    if case is None:
        return "Test case not found.", 404

    db.session.delete(case)
    db.session.commit()
    return redirect(url_for("index"))


@app.get("/api/test-cases")
def api_test_cases():
    cases = db.session.scalars(db.select(TestCase).order_by(TestCase.id)).all()
    return jsonify([case.to_dict() for case in cases])


@app.get("/health")
def health():
    db.session.execute(text("SELECT 1"))
    return {"status": "ok", "app": "test-hub", "database": "connected"}


with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "3000")),
        debug=True,
    )
