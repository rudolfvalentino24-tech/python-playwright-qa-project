from pathlib import Path
from flask import Flask, jsonify, redirect, render_template_string, request, url_for
import json
import os
import re
from datetime import datetime, timezone

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "test_cases.json"
JIRA_BASE_URL = os.environ.get("JIRA_BASE_URL", "https://qa-test-store.atlassian.net/browse")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "test-hub-dev-secret")

PRIORITIES = {"Low", "Medium", "High", "Critical"}
TYPES = {"Manual", "Automated"}
STATUSES = {"Draft", "Ready", "Passed", "Failed", "Blocked"}
JIRA_KEY_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*-\d+$")


def load_cases():
    if not DATA_FILE.exists():
        DATA_FILE.write_text("[]", encoding="utf-8")
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def save_cases(cases):
    DATA_FILE.write_text(json.dumps(cases, indent=2, ensure_ascii=False), encoding="utf-8")


def next_case_id(cases):
    numbers = []
    for case in cases:
        match = re.match(r"TC-(\d+)$", case.get("id", ""))
        if match:
            numbers.append(int(match.group(1)))
    return f"TC-{max(numbers, default=0) + 1:03d}"


def normalize_lines(value):
    return [line.strip() for line in value.splitlines() if line.strip()]


PAGE_HTML = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Test Hub</title>
<style>
:root{--bg:#f4f6f8;--surface:#fff;--text:#172b4d;--muted:#6b778c;--border:#dfe1e6;--accent:#0c66e4;--accent2:#0055cc;--danger:#ae2a19;--ok:#216e4e}
*{box-sizing:border-box}body{margin:0;font-family:Inter,Arial,sans-serif;background:var(--bg);color:var(--text)}
header{background:#172b4d;color:#fff;padding:18px 28px;display:flex;align-items:center;justify-content:space-between;gap:16px;position:sticky;top:0;z-index:5}
.brand{display:flex;align-items:center;gap:12px}.brand h1{font-size:22px;margin:0}.brand span{font-size:13px;opacity:.75}
main{max-width:1320px;margin:0 auto;padding:24px}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:20px}.stat{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:16px}.stat strong{display:block;font-size:26px}.stat span{color:var(--muted);font-size:13px}
.grid{display:grid;grid-template-columns:1.25fr .75fr;gap:18px}.card{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:18px}.card h2{margin:0 0 14px;font-size:18px}
.toolbar{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px}input,select,textarea,button{font:inherit}input,select,textarea{width:100%;padding:9px 10px;border:1px solid var(--border);border-radius:7px;background:#fff;color:var(--text)}textarea{min-height:82px;resize:vertical}.toolbar input{flex:1;min-width:220px}.toolbar select{width:160px}
button{border:0;border-radius:7px;padding:9px 13px;cursor:pointer;font-weight:600}.primary{background:var(--accent);color:#fff}.primary:hover{background:var(--accent2)}.secondary{background:#f1f2f4;color:var(--text)}.danger{background:#ffebe6;color:var(--danger)}
.case{border:1px solid var(--border);border-radius:9px;padding:14px;margin:10px 0}.case-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}.case-title{font-weight:700}.meta{display:flex;gap:7px;flex-wrap:wrap;margin:8px 0}.pill{font-size:12px;padding:3px 7px;border-radius:999px;background:#f1f2f4;color:#44546f}.jira{color:var(--accent);text-decoration:none;font-weight:600}.details{color:var(--muted);font-size:13px;white-space:pre-wrap}.actions{display:flex;gap:7px;flex-wrap:wrap;margin-top:10px}
.form-row{display:grid;grid-template-columns:1fr 1fr;gap:10px}.field{margin-bottom:11px}.field label{display:block;font-size:12px;font-weight:700;color:#44546f;margin-bottom:5px}.hint{font-size:12px;color:var(--muted);margin-top:5px}.empty{text-align:center;color:var(--muted);padding:36px 10px}
@media(max-width:900px){.stats{grid-template-columns:1fr 1fr}.grid{grid-template-columns:1fr}.form-row{grid-template-columns:1fr}}@media(max-width:520px){.stats{grid-template-columns:1fr}main{padding:14px}header{padding:14px 16px}}
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
        <article class="case" data-search="{{ (c.id ~ ' ' ~ c.title ~ ' ' ~ c.jira_key)|lower }}" data-type="{{ c.type }}" data-status="{{ c.status }}">
          <div class="case-head"><div><div class="case-title">{{ c.id }} — {{ c.title }}</div><div class="meta"><span class="pill">{{ c.type }}</span><span class="pill">{{ c.priority }}</span><span class="pill">{{ c.status }}</span>{% if c.jira_key %}<a class="jira" target="_blank" rel="noopener" href="{{ jira_base }}/{{ c.jira_key }}">{{ c.jira_key }}</a>{% endif %}</div></div></div>
          {% if c.preconditions %}<div class="details"><strong>Preconditions:</strong> {{ c.preconditions }}</div>{% endif %}
          <div class="details"><strong>Steps:</strong>\n{% for step in c.steps %}{{ loop.index }}. {{ step }}{% if not loop.last %}\n{% endif %}{% endfor %}</div>
          <div class="details" style="margin-top:7px"><strong>Expected:</strong> {{ c.expected_result }}</div>
          <div class="actions">
            <form method="post" action="{{ url_for('set_status', case_id=c.id) }}" style="display:flex;gap:6px"><select name="status" style="width:auto">{% for s in statuses %}<option value="{{ s }}" {% if s == c.status %}selected{% endif %}>{{ s }}</option>{% endfor %}</select><button class="secondary">Update</button></form>
            <form method="post" action="{{ url_for('delete_case', case_id=c.id) }}" onsubmit="return confirm('Delete {{ c.id }}?')"><button class="danger">Delete</button></form>
          </div>
        </article>
      {% else %}<div class="empty">No test cases yet. Create the first one on the right.</div>{% endfor %}
      </div>
    </div>
    <aside class="card">
      <h2>Create test case</h2>
      <form method="post" action="{{ url_for('create_case') }}">
        <div class="field"><label>Title</label><input name="title" required placeholder="Eye icon appears on password field focus"></div>
        <div class="form-row"><div class="field"><label>Jira story</label><input name="jira_key" placeholder="SCRUM-5"></div><div class="field"><label>Priority</label><select name="priority"><option>Medium</option><option>High</option><option>Critical</option><option>Low</option></select></div></div>
        <div class="form-row"><div class="field"><label>Type</label><select name="type"><option>Manual</option><option>Automated</option></select></div><div class="field"><label>Status</label><select name="status"><option>Draft</option><option>Ready</option><option>Passed</option><option>Failed</option><option>Blocked</option></select></div></div>
        <div class="field"><label>Preconditions</label><textarea name="preconditions" placeholder="User is on the login page"></textarea></div>
        <div class="field"><label>Steps</label><textarea name="steps" required placeholder="Click or Tab into the password field\nObserve the password field"></textarea><div class="hint">One step per line.</div></div>
        <div class="field"><label>Expected result</label><textarea name="expected_result" required placeholder="The eye icon becomes visible while the password field has focus."></textarea></div>
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
</script>
</body>
</html>
"""


@app.get("/")
def index():
    cases = load_cases()
    stats = {
        "total": len(cases),
        "manual": sum(1 for c in cases if c.get("type") == "Manual"),
        "automated": sum(1 for c in cases if c.get("type") == "Automated"),
        "ready": sum(1 for c in cases if c.get("status") == "Ready"),
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
    cases = load_cases()
    title = request.form.get("title", "").strip()
    jira_key = request.form.get("jira_key", "").strip().upper()
    priority = request.form.get("priority", "Medium").strip()
    case_type = request.form.get("type", "Manual").strip()
    status = request.form.get("status", "Draft").strip()
    preconditions = request.form.get("preconditions", "").strip()
    steps = normalize_lines(request.form.get("steps", ""))
    expected_result = request.form.get("expected_result", "").strip()

    if not title or not steps or not expected_result:
        return "Title, steps and expected result are required.", 400
    if jira_key and not JIRA_KEY_PATTERN.match(jira_key):
        return "Jira key must look like SCRUM-5.", 400
    if priority not in PRIORITIES or case_type not in TYPES or status not in STATUSES:
        return "Invalid test case metadata.", 400

    now = datetime.now(timezone.utc).isoformat()
    cases.append({
        "id": next_case_id(cases),
        "title": title,
        "jira_key": jira_key,
        "priority": priority,
        "type": case_type,
        "status": status,
        "preconditions": preconditions,
        "steps": steps,
        "expected_result": expected_result,
        "created_at": now,
        "updated_at": now,
    })
    save_cases(cases)
    return redirect(url_for("index"))


@app.post("/test-cases/<case_id>/status")
def set_status(case_id):
    status = request.form.get("status", "").strip()
    if status not in STATUSES:
        return "Invalid status.", 400
    cases = load_cases()
    for case in cases:
        if case.get("id") == case_id:
            case["status"] = status
            case["updated_at"] = datetime.now(timezone.utc).isoformat()
            save_cases(cases)
            return redirect(url_for("index"))
    return "Test case not found.", 404


@app.post("/test-cases/<case_id>/delete")
def delete_case(case_id):
    cases = load_cases()
    remaining = [case for case in cases if case.get("id") != case_id]
    if len(remaining) == len(cases):
        return "Test case not found.", 404
    save_cases(remaining)
    return redirect(url_for("index"))


@app.get("/api/test-cases")
def api_test_cases():
    return jsonify(load_cases())


@app.get("/health")
def health():
    return {"status": "ok", "app": "test-hub"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "3000")), debug=True)
