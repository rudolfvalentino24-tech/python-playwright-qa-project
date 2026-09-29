from pathlib import Path
from collections import OrderedDict
from flask import Flask, jsonify, redirect, render_template_string, request, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import UniqueConstraint, inspect, text
import base64
import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from datetime import datetime, timezone

BASE_DIR = Path(__file__).resolve().parent
JIRA_SITE_URL = os.environ.get("JIRA_SITE_URL", "https://qa-test-store.atlassian.net").rstrip("/")
JIRA_BASE_URL = f"{JIRA_SITE_URL}/browse"
JIRA_PROJECT_KEY = os.environ.get("JIRA_PROJECT_KEY", "SCRUM").strip().upper()
JIRA_EMAIL = os.environ.get("JIRA_EMAIL", "").strip()
JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN", "").strip()

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
    # Kept temporarily for one-time migration from the old single-story design.
    jira_key = db.Column(db.String(50), nullable=True, index=True)
    feature = db.Column(db.String(120), nullable=True, index=True)
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
    jira_links = db.relationship(
        "TestCaseJiraLink",
        back_populates="test_case",
        cascade="all, delete-orphan",
        order_by="TestCaseJiraLink.jira_key",
    )

    @property
    def feature_name(self):
        return (self.feature or "").strip() or "Uncategorized"

    @property
    def jira_keys(self):
        return [link.jira_key for link in self.jira_links]

    def to_dict(self):
        jira_keys = self.jira_keys
        return {
            "id": self.case_key,
            "title": self.title,
            "feature": self.feature_name,
            "jira_keys": jira_keys,
            # Backward-compatible single key for anything still consuming the old API.
            "jira_key": jira_keys[0] if jira_keys else "",
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


class TestCaseJiraLink(db.Model):
    __tablename__ = "test_case_jira_links"
    __table_args__ = (
        UniqueConstraint("test_case_id", "jira_key", name="uq_test_case_jira_key"),
    )

    id = db.Column(db.Integer, primary_key=True)
    test_case_id = db.Column(
        db.Integer,
        db.ForeignKey("test_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    jira_key = db.Column(db.String(50), nullable=False, index=True)

    test_case = db.relationship("TestCase", back_populates="jira_links")


def normalize_lines(value):
    return [line.strip() for line in value.splitlines() if line.strip()]


def parse_jira_keys(value):
    keys = []
    seen = set()
    for raw in re.split(r"[\s,;]+", value.strip().upper()):
        if not raw:
            continue
        if not JIRA_KEY_PATTERN.match(raw):
            raise ValueError(f"Invalid Jira key: {raw}. Use values like SCRUM-6.")
        if raw not in seen:
            keys.append(raw)
            seen.add(raw)
    return keys


def next_case_key():
    """Generate a stable test-case ID independent of Jira stories."""
    pattern = re.compile(r"^TC-(\d+)$")
    numbers = []
    for (case_key,) in db.session.execute(db.select(TestCase.case_key)).all():
        match = pattern.match(case_key or "")
        if match:
            numbers.append(int(match.group(1)))
    return f"TC-{max(numbers, default=0) + 1:03d}"


def validate_case_key(case_key):
    if not CASE_KEY_PATTERN.match(case_key):
        return "Test case ID may contain only letters, numbers, hyphens and underscores."
    existing = db.session.scalar(
        db.select(TestCase.id).where(TestCase.case_key == case_key)
    )
    if existing is not None:
        return f"Test case ID {case_key} already exists."
    return None


def set_jira_links(case, jira_keys):
    """Synchronize Jira links without reinserting links that already exist."""
    requested_keys = set(jira_keys)

    # Remove only Jira links the user removed from the form
    for link in list(case.jira_links):
        if link.jira_key not in requested_keys:
            case.jira_links.remove(link)

    # Add only genuinely new Jira links
    existing_keys = {link.jira_key for link in case.jira_links}
    for jira_key in jira_keys:
        if jira_key not in existing_keys:
            case.jira_links.append(TestCaseJiraLink(jira_key=jira_key))


def fetch_jira_stories():
    """Fetch Story issues from Jira for the searchable multi-select."""
    if not JIRA_EMAIL or not JIRA_API_TOKEN:
        raise RuntimeError(
            "Jira API credentials are not configured. Set JIRA_EMAIL and JIRA_API_TOKEN."
        )

    auth = base64.b64encode(
        f"{JIRA_EMAIL}:{JIRA_API_TOKEN}".encode("utf-8")
    ).decode("ascii")
    payload = json.dumps({
        "jql": f'project = "{JIRA_PROJECT_KEY}" AND issuetype = Story ORDER BY created DESC',
        "fields": ["summary", "status"],
        "maxResults": 100,
    }).encode("utf-8")

    jira_request = Request(
        f"{JIRA_SITE_URL}/rest/api/3/search/jql",
        data=payload,
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Basic {auth}",
        },
    )

    try:
        with urlopen(jira_request, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 401:
            raise RuntimeError("Jira authentication failed. Check JIRA_EMAIL and JIRA_API_TOKEN.") from exc
        if exc.code == 403:
            raise RuntimeError("Jira denied access to the project. Check Jira permissions.") from exc
        raise RuntimeError(f"Jira returned HTTP {exc.code}.") from exc
    except URLError as exc:
        raise RuntimeError("Test Hub could not connect to Jira.") from exc

    stories = []
    for issue in data.get("issues", []):
        fields = issue.get("fields") or {}
        status = fields.get("status") or {}
        stories.append({
            "key": issue.get("key", ""),
            "summary": fields.get("summary", ""),
            "status": status.get("name", ""),
        })
    return stories


def grouped_cases(cases):
    grouped = {}
    for case in cases:
        grouped.setdefault(case.feature_name, []).append(case)

    names = sorted(
        grouped,
        key=lambda name: (name == "Uncategorized", name.lower()),
    )
    return [{"feature": name, "cases": grouped[name]} for name in names]


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
.grid{display:grid;grid-template-columns:1.35fr .65fr;gap:18px}.card{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:18px}.card h2{margin:0 0 14px;font-size:18px}
.toolbar{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:16px}input,select,textarea,button{font:inherit}input,select,textarea{width:100%;padding:9px 10px;border:1px solid var(--border);border-radius:7px;background:#fff;color:var(--text)}textarea{min-height:82px;resize:vertical}.toolbar input{flex:1;min-width:220px}.toolbar select{width:160px}
button{border:0;border-radius:7px;padding:9px 13px;cursor:pointer;font-weight:600}.primary{background:var(--accent);color:#fff}.primary:hover{background:var(--accent2)}.secondary{background:#f1f2f4;color:var(--text)}.danger{background:#ffebe6;color:var(--danger)}
.feature-group{border:1px solid var(--border);border-radius:10px;margin:14px 0;overflow:hidden}.feature-head{padding:13px 15px;background:#f7f8f9;display:flex;align-items:center;justify-content:space-between;gap:10px}.feature-title{font-weight:800;font-size:16px}.feature-count{font-size:12px;color:var(--muted)}
.case{border-top:1px solid var(--border);padding:14px}.case:first-of-type{border-top:0}.case-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}.case-title{font-weight:700}.meta{display:flex;gap:7px;flex-wrap:wrap;margin:8px 0}.pill{font-size:12px;padding:3px 7px;border-radius:999px;background:#f1f2f4;color:#44546f}.jira{color:var(--accent);text-decoration:none;font-weight:700}.details{color:var(--muted);font-size:13px;white-space:pre-wrap}.actions{display:flex;gap:7px;flex-wrap:wrap;margin-top:10px;align-items:center}.button-link{display:inline-block;text-decoration:none;border-radius:7px;padding:9px 13px;font-weight:600}
.form-row{display:grid;grid-template-columns:1fr 1fr;gap:10px}.field{margin-bottom:11px}.field label{display:block;font-size:12px;font-weight:700;color:#44546f;margin-bottom:5px}.hint{font-size:12px;color:var(--muted);margin-top:5px}.empty{text-align:center;color:var(--muted);padding:36px 10px}.jira-picker{border:1px solid var(--border);border-radius:8px;padding:10px;background:#fafbfc}.jira-picker-head{display:flex;gap:7px;margin-bottom:8px}.jira-picker-head input{flex:1}.jira-story-list{max-height:190px;overflow:auto;display:flex;flex-direction:column;gap:5px}.jira-story{width:100%;text-align:left;background:#fff;border:1px solid var(--border);font-weight:500}.jira-story.selected{border-color:var(--accent);background:#e9f2ff}.jira-story-key{font-weight:800;color:var(--accent)}.jira-story-summary{color:#44546f}.jira-picker-message{font-size:12px;color:var(--muted);padding:7px 2px}
@media(max-width:900px){.stats{grid-template-columns:1fr 1fr}.grid{grid-template-columns:1fr}.form-row{grid-template-columns:1fr}}@media(max-width:520px){.stats{grid-template-columns:1fr}main{padding:14px}header{padding:14px 16px}}
</style>
</head>
<body>
<header>
  <div class="brand"><div style="font-size:26px">🧪</div><div><h1>Test Hub</h1><span>QA test case management</span></div></div>
  <div style="font-size:13px;opacity:.8">Grouped by feature · linked to Jira stories</div>
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
      <h2>Test cases by feature</h2>
      <div class="toolbar">
        <input id="search" placeholder="Search feature, ID, title or Jira key…" oninput="filterCases()">
        <select id="typeFilter" onchange="filterCases()"><option value="">All types</option><option>Manual</option><option>Automated</option></select>
        <select id="statusFilter" onchange="filterCases()"><option value="">All statuses</option><option>Draft</option><option>Ready</option><option>Passed</option><option>Failed</option><option>Blocked</option></select>
      </div>

      <div id="caseList">
      {% for group in groups %}
        <section class="feature-group" data-feature="{{ group.feature|lower }}">
          <div class="feature-head">
            <div class="feature-title">{{ group.feature }}</div>
            <div class="feature-count">{{ group.cases|length }} test case{% if group.cases|length != 1 %}s{% endif %}</div>
          </div>

          {% for c in group.cases %}
          <article class="case"
                   data-search="{{ (group.feature ~ ' ' ~ c.case_key ~ ' ' ~ c.title ~ ' ' ~ (c.jira_keys|join(' ')))|lower }}"
                   data-type="{{ c.type }}"
                   data-status="{{ c.status }}">
            <div class="case-head">
              <div>
                <div class="case-title">{{ c.case_key }} — {{ c.title }}</div>
                <div class="meta">
                  <span class="pill">{{ c.type }}</span>
                  <span class="pill">{{ c.priority }}</span>
                  <span class="pill">{{ c.status }}</span>
                  {% for jira_key in c.jira_keys %}
                    <a class="jira" href="{{ url_for('jira_story_cases', jira_key=jira_key) }}">{{ jira_key }}</a>
                  {% endfor %}
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
          {% endfor %}
        </section>
      {% else %}
        <div class="empty">No test cases yet. Create the first one on the right.</div>
      {% endfor %}
      </div>
    </div>

    <aside class="card">
      <h2>Create test case</h2>
      <form method="post" action="{{ url_for('create_case') }}">
        <div class="field">
          <label>Feature / Module</label>
          <input name="feature" required placeholder="Authentication">
          <div class="hint">This controls where the test case is grouped on the front page.</div>
        </div>
        <div class="field">
          <label>Title</label>
          <input name="title" required placeholder="Reveal password toggles visibility">
        </div>
        <div class="field">
          <label>Jira stories</label>
          <input id="createJiraKeys" name="jira_keys" placeholder="SCRUM-6, SCRUM-7">
          <div class="jira-picker">
            <div class="jira-picker-head">
              <input id="createJiraSearch" type="search" placeholder="Search Jira stories..." oninput="renderJiraStories('create')">
              <button class="secondary" type="button" onclick="loadJiraStories('create')">Refresh</button>
            </div>
            <div id="createJiraStoryList" class="jira-story-list">
              <div class="jira-picker-message">Loading Jira stories…</div>
            </div>
          </div>
          <div class="hint">Select any number of Jira stories. You can still type Jira keys manually if needed.</div>
        </div>
        <div class="field">
          <label>Test case ID</label>
          <input name="case_key" placeholder="Leave blank to auto-generate">
          <div class="hint">Auto-generated IDs use TC-001, TC-002, and so on.</div>
        </div>
        <div class="form-row">
          <div class="field"><label>Priority</label><select name="priority"><option>Medium</option><option>High</option><option>Critical</option><option>Low</option></select></div>
          <div class="field"><label>Type</label><select name="type"><option>Manual</option><option>Automated</option></select></div>
        </div>
        <div class="field"><label>Status</label><select name="status"><option>Draft</option><option>Ready</option><option>Passed</option><option>Failed</option><option>Blocked</option></select></div>
        <div class="field"><label>Preconditions</label><textarea name="preconditions" placeholder="User is on the login page"></textarea></div>
        <div class="field"><label>Steps</label><textarea name="steps" required placeholder="Enter a password&#10;Click the reveal-password icon"></textarea><div class="hint">One step per line.</div></div>
        <div class="field"><label>Expected result</label><textarea name="expected_result" required placeholder="The password becomes visible."></textarea></div>
        <button class="primary" type="submit">Create test case</button>
      </form>
    </aside>
  </section>
</main>

<script>
let jiraStories=[];

function filterCases(){
  const q=document.getElementById('search').value.trim().toLowerCase();
  const type=document.getElementById('typeFilter').value;
  const status=document.getElementById('statusFilter').value;

  document.querySelectorAll('.feature-group').forEach(group=>{
    let visible=0;
    group.querySelectorAll('.case').forEach(el=>{
      const okText=!q || el.dataset.search.includes(q);
      const okType=!type || el.dataset.type===type;
      const okStatus=!status || el.dataset.status===status;
      const show=okText&&okType&&okStatus;
      el.style.display=show?'block':'none';
      if(show) visible++;
    });
    group.style.display=visible?'block':'none';
  });
}

function selectedJiraKeys(prefix){
  const input=document.getElementById(prefix+'JiraKeys');
  return new Set(input.value.split(/[\\s,;]+/).map(v=>v.trim().toUpperCase()).filter(Boolean));
}

function toggleJiraStory(prefix,key){
  const selected=selectedJiraKeys(prefix);
  selected.has(key)?selected.delete(key):selected.add(key);
  document.getElementById(prefix+'JiraKeys').value=[...selected].join(', ');
  renderJiraStories(prefix);
}

function renderJiraStories(prefix){
  const list=document.getElementById(prefix+'JiraStoryList');
  if(!list) return;
  const search=document.getElementById(prefix+'JiraSearch').value.trim().toLowerCase();
  const selected=selectedJiraKeys(prefix);
  const matches=jiraStories.filter(story=>
    !search || story.key.toLowerCase().includes(search) || story.summary.toLowerCase().includes(search)
  );

  if(!matches.length){
    list.innerHTML='<div class="jira-picker-message">No matching Jira stories.</div>';
    return;
  }

  list.innerHTML=matches.map(story=>{
    const isSelected=selected.has(story.key);
    return `<button type="button" class="jira-story ${isSelected?'selected':''}" data-jira-key="${story.key}">
      <span class="jira-story-key">${story.key}</span> —
      <span class="jira-story-summary">${escapeHtml(story.summary)}</span>
      ${story.status?` <small>(${escapeHtml(story.status)})</small>`:''}
    </button>`;
  }).join('');

  list.querySelectorAll('.jira-story').forEach(button=>{
    button.addEventListener('click',()=>toggleJiraStory(prefix,button.dataset.jiraKey));
  });
}

function escapeHtml(value){
  const div=document.createElement('div');
  div.textContent=value || '';
  return div.innerHTML;
}

async function loadJiraStories(prefix){
  const list=document.getElementById(prefix+'JiraStoryList');
  list.innerHTML='<div class="jira-picker-message">Loading Jira stories…</div>';
  try{
    const response=await fetch('/api/jira/stories');
    const data=await response.json();
    if(!response.ok) throw new Error(data.error || 'Unable to load Jira stories.');
    jiraStories=data.stories || [];
    renderJiraStories(prefix);
  }catch(error){
    list.innerHTML='<div class="jira-picker-message">'+escapeHtml(error.message)+' Manual Jira-key entry is still available above.</div>';
  }
}

document.addEventListener('DOMContentLoaded',()=>loadJiraStories('create'));
</script>
</body>
</html>
"""


STORY_PAGE_HTML = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ jira_key }} test cases - Test Hub</title>
<style>
:root{--bg:#f4f6f8;--surface:#fff;--text:#172b4d;--muted:#6b778c;--border:#dfe1e6;--accent:#0c66e4}
*{box-sizing:border-box}body{margin:0;font-family:Inter,Arial,sans-serif;background:var(--bg);color:var(--text)}
header{background:#172b4d;color:#fff;padding:18px 28px}.wrap{max-width:980px;margin:0 auto;padding:24px}
.top{display:flex;justify-content:space-between;gap:16px;align-items:flex-start;margin-bottom:18px}.top h1{margin:0 0 5px;font-size:25px}.muted{color:var(--muted)}
.actions{display:flex;gap:8px;flex-wrap:wrap}.button{display:inline-block;text-decoration:none;border-radius:7px;padding:9px 13px;font-weight:700;background:#f1f2f4;color:var(--text)}.primary{background:var(--accent);color:#fff}
.case{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:16px;margin:12px 0}.title{font-size:17px;font-weight:700}.feature{font-size:13px;font-weight:700;color:#44546f;margin-top:5px}.meta{display:flex;gap:7px;flex-wrap:wrap;margin:9px 0}.pill{font-size:12px;padding:3px 7px;border-radius:999px;background:#f1f2f4;color:#44546f}.jira{color:var(--accent);text-decoration:none;font-weight:700}.details{font-size:13px;color:var(--muted);white-space:pre-wrap;margin-top:7px}.empty{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:30px;text-align:center;color:var(--muted)}
@media(max-width:650px){.top{flex-direction:column}}
</style>
</head>
<body>
<header><strong>🧪 Test Hub</strong></header>
<main class="wrap">
  <div class="top">
    <div>
      <h1>{{ jira_key }} test cases</h1>
      <div class="muted">{{ cases|length }} linked test case{% if cases|length != 1 %}s{% endif %}</div>
    </div>
    <div class="actions">
      <a class="button" href="{{ url_for('index') }}">All test cases</a>
      <a class="button primary" target="_blank" rel="noopener" href="{{ jira_base }}/{{ jira_key }}">Open {{ jira_key }} in Jira</a>
    </div>
  </div>

  {% for c in cases %}
    <article class="case">
      <div class="title">{{ c.case_key }} — {{ c.title }}</div>
      <div class="feature">Feature: {{ c.feature_name }}</div>
      <div class="meta">
        <span class="pill">{{ c.type }}</span>
        <span class="pill">{{ c.priority }}</span>
        <span class="pill">{{ c.status }}</span>
        {% for other_key in c.jira_keys %}
          {% if other_key != jira_key %}
            <a class="jira" href="{{ url_for('jira_story_cases', jira_key=other_key) }}">{{ other_key }}</a>
          {% endif %}
        {% endfor %}
      </div>
      {% if c.preconditions %}<div class="details"><strong>Preconditions:</strong> {{ c.preconditions }}</div>{% endif %}
      <div class="details"><strong>Steps:</strong>
{% for step in c.steps %}{{ loop.index }}. {{ step.action }}{% if not loop.last %}
{% endif %}{% endfor %}</div>
      <div class="details"><strong>Expected:</strong> {{ c.expected_result }}</div>
      <div class="actions" style="margin-top:12px">
        <a class="button" href="{{ url_for('edit_case', case_key=c.case_key) }}">Edit test case</a>
      </div>
    </article>
  {% else %}
    <div class="empty">No test cases are linked to {{ jira_key }} yet.</div>
  {% endfor %}
</main>
</body>
</html>
"""


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
textarea{min-height:100px;resize:vertical}.actions{display:flex;gap:10px;margin-top:18px;flex-wrap:wrap}.primary{background:var(--accent);color:#fff;border:0;border-radius:7px;padding:10px 14px;font-weight:700;cursor:pointer}.primary:hover{background:var(--accent2)}
.cancel{background:#f1f2f4;color:var(--text);text-decoration:none;border-radius:7px;padding:10px 14px;font-weight:700}.hint{font-size:12px;color:var(--muted);margin-top:5px}.jira-picker{border:1px solid var(--border);border-radius:8px;padding:10px;background:#fafbfc}.jira-picker-head{display:flex;gap:7px;margin-bottom:8px}.jira-picker-head input{flex:1}.jira-story-list{max-height:210px;overflow:auto;display:flex;flex-direction:column;gap:5px}.jira-story{width:100%;text-align:left;background:#fff;border:1px solid var(--border);border-radius:7px;padding:8px 10px;cursor:pointer}.jira-story.selected{border-color:var(--accent);background:#e9f2ff}.jira-story-key{font-weight:800;color:var(--accent)}.jira-picker-message{font-size:12px;color:var(--muted);padding:7px 2px}
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
        <div class="field"><label>Feature / Module</label><input name="feature" value="{{ case.feature_name }}" required></div>
      </div>
      <div class="field"><label>Title</label><input name="title" value="{{ case.title }}" required></div>
      <div class="field">
        <label>Jira stories</label>
        <input id="editJiraKeys" name="jira_keys" value="{{ case.jira_keys|join(', ') }}" placeholder="SCRUM-6, SCRUM-7">
        <div class="jira-picker">
          <div class="jira-picker-head">
            <input id="editJiraSearch" type="search" placeholder="Search Jira stories..." oninput="renderEditJiraStories()">
            <button class="cancel" type="button" onclick="loadEditJiraStories()">Refresh</button>
          </div>
          <div id="editJiraStoryList" class="jira-story-list">
            <div class="jira-picker-message">Loading Jira stories…</div>
          </div>
        </div>
        <div class="hint">Select any number of Jira stories. Manual Jira-key entry remains available above.</div>
      </div>
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
        {% for jira_key in case.jira_keys %}
          <a class="cancel" href="{{ url_for('jira_story_cases', jira_key=jira_key) }}">{{ jira_key }} view</a>
        {% endfor %}
        <a class="cancel" href="{{ url_for('index') }}">Cancel</a>
      </div>
    </form>
  </div>
</main>
<script>
let editJiraStories=[];

function editSelectedJiraKeys(){
  return new Set(document.getElementById('editJiraKeys').value.split(/[\\s,;]+/).map(v=>v.trim().toUpperCase()).filter(Boolean));
}

function escapeEditHtml(value){
  const div=document.createElement('div');
  div.textContent=value || '';
  return div.innerHTML;
}

function toggleEditJiraStory(key){
  const selected=editSelectedJiraKeys();
  selected.has(key)?selected.delete(key):selected.add(key);
  document.getElementById('editJiraKeys').value=[...selected].join(', ');
  renderEditJiraStories();
}

function renderEditJiraStories(){
  const list=document.getElementById('editJiraStoryList');
  const search=document.getElementById('editJiraSearch').value.trim().toLowerCase();
  const selected=editSelectedJiraKeys();
  const matches=editJiraStories.filter(story=>
    !search || story.key.toLowerCase().includes(search) || story.summary.toLowerCase().includes(search)
  );
  if(!matches.length){
    list.innerHTML='<div class="jira-picker-message">No matching Jira stories.</div>';
    return;
  }
  list.innerHTML=matches.map(story=>{
    const isSelected=selected.has(story.key);
    return `<button type="button" class="jira-story ${isSelected?'selected':''}" data-jira-key="${story.key}">
      <span class="jira-story-key">${story.key}</span> —
      ${escapeEditHtml(story.summary)}
      ${story.status?` <small>(${escapeEditHtml(story.status)})</small>`:''}
    </button>`;
  }).join('');

  list.querySelectorAll('.jira-story').forEach(button=>{
    button.addEventListener('click',()=>toggleEditJiraStory(button.dataset.jiraKey));
  });
}

async function loadEditJiraStories(){
  const list=document.getElementById('editJiraStoryList');
  list.innerHTML='<div class="jira-picker-message">Loading Jira stories…</div>';
  try{
    const response=await fetch('/api/jira/stories');
    const data=await response.json();
    if(!response.ok) throw new Error(data.error || 'Unable to load Jira stories.');
    editJiraStories=data.stories || [];
    renderEditJiraStories();
  }catch(error){
    list.innerHTML='<div class="jira-picker-message">'+escapeEditHtml(error.message)+' Manual Jira-key entry is still available above.</div>';
  }
}

document.addEventListener('DOMContentLoaded',loadEditJiraStories);
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
        groups=grouped_cases(cases),
        stats=stats,
        statuses=["Draft", "Ready", "Passed", "Failed", "Blocked"],
    )


@app.get("/jira/<jira_key>")
def jira_story_cases(jira_key):
    jira_key = jira_key.strip().upper()
    if not JIRA_KEY_PATTERN.match(jira_key):
        return "Invalid Jira key.", 400

    cases = db.session.scalars(
        db.select(TestCase)
        .join(TestCaseJiraLink)
        .where(TestCaseJiraLink.jira_key == jira_key)
        .order_by(TestCase.id)
    ).all()

    return render_template_string(
        STORY_PAGE_HTML,
        jira_key=jira_key,
        cases=cases,
        jira_base=JIRA_BASE_URL.rstrip("/"),
    )


@app.post("/test-cases")
def create_case():
    feature = request.form.get("feature", "").strip()
    title = request.form.get("title", "").strip()
    requested_case_key = request.form.get("case_key", "").strip().upper()
    priority = request.form.get("priority", "Medium").strip()
    case_type = request.form.get("type", "Manual").strip()
    status = request.form.get("status", "Draft").strip()
    preconditions = request.form.get("preconditions", "").strip()
    steps = normalize_lines(request.form.get("steps", ""))
    expected_result = request.form.get("expected_result", "").strip()

    try:
        jira_keys = parse_jira_keys(request.form.get("jira_keys", ""))
    except ValueError as exc:
        return str(exc), 400

    if not feature or not title or not steps or not expected_result:
        return "Feature, title, steps and expected result are required.", 400
    if priority not in PRIORITIES or case_type not in TYPES or status not in STATUSES:
        return "Invalid test case metadata.", 400

    case_key = requested_case_key or next_case_key()
    key_error = validate_case_key(case_key)
    if key_error:
        return key_error, 400

    case = TestCase(
        case_key=case_key,
        title=title,
        feature=feature,
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
    set_jira_links(case, jira_keys)
    db.session.add(case)
    db.session.commit()
    return redirect(url_for("index"))


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
    feature = request.form.get("feature", "").strip()
    title = request.form.get("title", "").strip()
    priority = request.form.get("priority", "").strip()
    case_type = request.form.get("type", "").strip()
    status = request.form.get("status", "").strip()
    preconditions = request.form.get("preconditions", "").strip()
    steps = normalize_lines(request.form.get("steps", ""))
    expected_result = request.form.get("expected_result", "").strip()

    try:
        jira_keys = parse_jira_keys(request.form.get("jira_keys", ""))
    except ValueError as exc:
        return str(exc), 400

    if not new_case_key or not feature or not title or not steps or not expected_result:
        return "Test case ID, feature, title, steps and expected result are required.", 400
    if priority not in PRIORITIES or case_type not in TYPES or status not in STATUSES:
        return "Invalid test case metadata.", 400

    if new_case_key != case.case_key:
        key_error = validate_case_key(new_case_key)
        if key_error:
            return key_error, 400

    case.case_key = new_case_key
    case.feature = feature
    case.title = title
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
    set_jira_links(case, jira_keys)

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


@app.get("/api/jira/stories")
def api_jira_stories():
    try:
        stories = fetch_jira_stories()
    except RuntimeError as exc:
        return jsonify({"error": str(exc), "stories": []}), 503

    return jsonify({
        "project": JIRA_PROJECT_KEY,
        "stories": stories,
    })


@app.get("/api/test-cases")
def api_test_cases():
    cases = db.session.scalars(db.select(TestCase).order_by(TestCase.id)).all()
    return jsonify([case.to_dict() for case in cases])


@app.get("/api/jira/<jira_key>/test-cases")
def api_jira_test_cases(jira_key):
    jira_key = jira_key.strip().upper()
    if not JIRA_KEY_PATTERN.match(jira_key):
        return jsonify({"error": "Invalid Jira key."}), 400

    cases = db.session.scalars(
        db.select(TestCase)
        .join(TestCaseJiraLink)
        .where(TestCaseJiraLink.jira_key == jira_key)
        .order_by(TestCase.id)
    ).all()
    return jsonify([case.to_dict() for case in cases])


@app.get("/health")
def health():
    db.session.execute(text("SELECT 1"))
    return {"status": "ok", "app": "test-hub", "database": "connected"}


def migrate_schema_and_legacy_jira_links():
    db.create_all()

    inspector = inspect(db.engine)
    if "test_cases" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("test_cases")}
    if "feature" not in columns:
        db.session.execute(text("ALTER TABLE test_cases ADD COLUMN feature VARCHAR(120)"))
        db.session.commit()

    # Move any legacy single Jira story into the new many-to-many table once.
    legacy_cases = db.session.scalars(
        db.select(TestCase).where(TestCase.jira_key.is_not(None))
    ).all()
    for case in legacy_cases:
        legacy_key = (case.jira_key or "").strip().upper()
        if legacy_key and JIRA_KEY_PATTERN.match(legacy_key):
            exists = db.session.scalar(
                db.select(TestCaseJiraLink.id).where(
                    TestCaseJiraLink.test_case_id == case.id,
                    TestCaseJiraLink.jira_key == legacy_key,
                )
            )
            if exists is None:
                db.session.add(
                    TestCaseJiraLink(test_case_id=case.id, jira_key=legacy_key)
                )
        case.jira_key = None
    db.session.commit()


with app.app_context():
    migrate_schema_and_legacy_jira_links()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "3000")),
        debug=True,
    )
