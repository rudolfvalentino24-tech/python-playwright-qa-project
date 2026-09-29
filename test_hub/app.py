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
from urllib.parse import quote
from urllib.request import Request, urlopen
from datetime import datetime, timezone

BASE_DIR = Path(__file__).resolve().parent
JIRA_SITE_URL = os.environ.get("JIRA_SITE_URL", "https://qa-test-store.atlassian.net").rstrip("/")
JIRA_BASE_URL = f"{JIRA_SITE_URL}/browse"
JIRA_PROJECT_KEY = os.environ.get("JIRA_PROJECT_KEY", "SCRUM").strip().upper()
JIRA_EMAIL = os.environ.get("JIRA_EMAIL", "").strip()
JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN", "").strip()
TEST_HUB_BASE_URL = os.environ.get("TEST_HUB_BASE_URL", "http://127.0.0.1:3000").rstrip("/")

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


def jira_api_request(path, method="GET", body=None):
    """Call Jira Cloud REST API using the Test Hub Jira credentials."""
    if not JIRA_EMAIL or not JIRA_API_TOKEN:
        raise RuntimeError(
            "Jira API credentials are not configured. Set JIRA_EMAIL and JIRA_API_TOKEN."
        )

    auth = base64.b64encode(
        f"{JIRA_EMAIL}:{JIRA_API_TOKEN}".encode("utf-8")
    ).decode("ascii")
    payload = json.dumps(body).encode("utf-8") if body is not None else None
    jira_request = Request(
        f"{JIRA_SITE_URL}{path}",
        data=payload,
        method=method,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Basic {auth}",
        },
    )

    try:
        with urlopen(jira_request, timeout=10) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else None
    except HTTPError as exc:
        if exc.code == 401:
            raise RuntimeError("Jira authentication failed. Check JIRA_EMAIL and JIRA_API_TOKEN.") from exc
        if exc.code == 403:
            raise RuntimeError("Jira denied the requested action. Check Jira Link issues permission.") from exc
        if exc.code == 404:
            raise RuntimeError("Jira ticket or web link was not found.") from exc
        raise RuntimeError(f"Jira returned HTTP {exc.code}.") from exc
    except URLError as exc:
        raise RuntimeError("Test Hub could not connect to Jira.") from exc


def test_hub_jira_url(jira_key):
    return f"{TEST_HUB_BASE_URL}/jira/{jira_key}"


def test_hub_jira_global_id(jira_key):
    return f"system=test-hub&id={jira_key}"


def test_hub_remote_link_body(jira_key):
    return {
        "globalId": test_hub_jira_global_id(jira_key),
        "relationship": "tests",
        "object": {
            "url": test_hub_jira_url(jira_key),
            "title": "Test Hub — View test cases",
            "summary": f"Open all Test Hub cases linked to {jira_key}",
        },
    }


def matching_test_hub_remote_links(jira_key, remote_links):
    target_url = test_hub_jira_url(jira_key)
    target_global_id = test_hub_jira_global_id(jira_key)
    matches = []

    for link in remote_links or []:
        obj = link.get("object") or {}
        if (
            link.get("globalId") == target_global_id
            or obj.get("url") == target_url
        ):
            matches.append(link)

    return matches


def ensure_jira_test_hub_web_link(jira_key):
    """Ensure Jira has exactly one Test Hub web link for this story."""
    encoded_key = quote(jira_key, safe="")
    path = f"/rest/api/3/issue/{encoded_key}/remotelink"
    remote_links = jira_api_request(path) or []
    matches = matching_test_hub_remote_links(jira_key, remote_links)
    body = test_hub_remote_link_body(jira_key)

    if matches:
        primary = matches[0]
        jira_api_request(
            f"{path}/{primary['id']}",
            method="PUT",
            body=body,
        )
        for duplicate in matches[1:]:
            jira_api_request(
                f"{path}/{duplicate['id']}",
                method="DELETE",
            )
    else:
        jira_api_request(path, method="POST", body=body)


def remove_jira_test_hub_web_link(jira_key):
    """Remove Test Hub's web link when no Test Hub cases remain for this story."""
    remaining = db.session.scalar(
        db.select(db.func.count(TestCaseJiraLink.id)).where(
            TestCaseJiraLink.jira_key == jira_key
        )
    )
    if remaining:
        return

    encoded_key = quote(jira_key, safe="")
    path = f"/rest/api/3/issue/{encoded_key}/remotelink"
    remote_links = jira_api_request(path) or []

    for link in matching_test_hub_remote_links(jira_key, remote_links):
        jira_api_request(
            f"{path}/{link['id']}",
            method="DELETE",
        )


def sync_jira_test_hub_web_links(current_keys, removed_keys=None):
    """Keep Jira web links synchronized with Test Hub's many-to-many links."""
    errors = []

    for jira_key in sorted(set(current_keys)):
        try:
            ensure_jira_test_hub_web_link(jira_key)
        except RuntimeError as exc:
            errors.append(f"{jira_key}: {exc}")

    for jira_key in sorted(set(removed_keys or [])):
        try:
            remove_jira_test_hub_web_link(jira_key)
        except RuntimeError as exc:
            errors.append(f"{jira_key}: {exc}")

    return errors


def fetch_jira_stories():
    """Fetch Story issues from Jira for the searchable multi-select."""
    data = jira_api_request(
        "/rest/api/3/search/jql",
        method="POST",
        body={
            "jql": f'project = "{JIRA_PROJECT_KEY}" AND issuetype = Story ORDER BY created DESC',
            "fields": ["summary", "status"],
            "maxResults": 100,
        },
    ) or {}

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
:root{
  --bg:#eef3fb;--surface:rgba(255,255,255,.94);--surface-soft:#f8faff;
  --text:#111827;--muted:#6b7280;--border:#d7dfec;
  --accent:#2f66e8;--accent2:#2475ff;--accent-soft:#edf4ff;
  --danger:#b42318;--danger-soft:#fff0ee;--warning:#8a6500;
  font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif
}
*{box-sizing:border-box}
body{
  margin:0;min-height:100vh;color:var(--text);
  background:
    radial-gradient(circle at 8% 5%,rgba(98,134,255,.18),transparent 28%),
    radial-gradient(circle at 95% 18%,rgba(36,117,255,.12),transparent 24%),
    linear-gradient(180deg,#f8faff 0%,#eef3fb 100%);
}
header{
  position:sticky;top:0;z-index:20;display:flex;align-items:center;justify-content:space-between;gap:20px;
  padding:16px 32px;background:rgba(20,42,82,.94);color:#fff;
  box-shadow:0 10px 30px rgba(24,47,90,.14);backdrop-filter:blur(14px)
}
.brand{display:flex;align-items:center;gap:13px}.brand h1{margin:0;font-size:22px;letter-spacing:-.35px}.brand span{display:block;margin-top:2px;font-size:13px;opacity:.72}
.brand-icon{width:44px;height:44px;display:grid;place-items:center;border-radius:13px;font-size:22px;background:linear-gradient(135deg,#6286ff,#1f63f2);box-shadow:0 8px 22px rgba(37,99,235,.3)}
.header-note{font-size:13px;opacity:.78}
main{max-width:1440px;margin:0 auto;padding:30px}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:22px}
.stat{
  padding:19px 20px;border:1px solid rgba(215,223,236,.9);border-radius:17px;
  background:var(--surface);box-shadow:0 12px 32px rgba(35,61,108,.07);backdrop-filter:blur(12px)
}
.stat strong{display:block;font-size:31px;line-height:1;font-weight:800;letter-spacing:-.8px;color:#19345f}
.stat span{display:block;margin-top:7px;color:var(--muted);font-size:13px;font-weight:600}
.grid{display:grid;grid-template-columns:minmax(0,1.45fr) minmax(340px,.65fr);gap:20px;align-items:start}
.card{
  background:var(--surface);border:1px solid rgba(215,223,236,.95);border-radius:19px;padding:22px;
  box-shadow:0 18px 48px rgba(35,61,108,.08);backdrop-filter:blur(12px)
}
.card h2{margin:0 0 17px;font-size:20px;letter-spacing:-.3px;color:#172b4d}
aside.card{position:sticky;top:98px}
.toolbar{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:18px}
input,select,textarea,button{font:inherit}
input,select,textarea{
  width:100%;border:1px solid #ccd5e4;border-radius:11px;background:rgba(255,255,255,.92);color:var(--text);
  outline:none;transition:border-color .18s ease,box-shadow .18s ease,background .18s ease
}
input,select{height:46px;padding:0 13px}textarea{min-height:92px;padding:11px 13px;resize:vertical;line-height:1.45}
input:focus,select:focus,textarea:focus{border-color:#3b73ef;box-shadow:0 0 0 4px rgba(59,115,239,.12);background:#fff}
.toolbar input{flex:1;min-width:240px}.toolbar select{width:168px}
button,.button-link{border:0;border-radius:10px;padding:10px 14px;cursor:pointer;font-weight:750;transition:transform .15s ease,box-shadow .15s ease,background .15s ease}
button:hover,.button-link:hover{transform:translateY(-1px)}
.primary{background:linear-gradient(90deg,#2f66e8,#2475ff);color:#fff;box-shadow:0 8px 18px rgba(37,99,235,.2)}
.primary:hover{box-shadow:0 11px 24px rgba(37,99,235,.28)}
.secondary{background:#eef2f7;color:#20324f}.secondary:hover{background:#e5ebf4}.danger{background:var(--danger-soft);color:var(--danger)}.danger:hover{background:#ffe5e1}
.feature-group{overflow:hidden;margin:15px 0;border:1px solid var(--border);border-radius:15px;background:#fff;box-shadow:0 8px 24px rgba(35,61,108,.045)}
.feature-head{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px 16px;background:linear-gradient(90deg,#f5f8ff,#fbfcff);border-bottom:1px solid #e5eaf2}
.feature-title{font-size:16px;font-weight:800;color:#17325d}.feature-count{font-size:12px;font-weight:650;color:var(--muted)}
.case{padding:17px 18px;border-top:1px solid #e9edf4;transition:background .16s ease}.case:first-of-type{border-top:0}.case:hover{background:#fbfdff}
.case-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}.case-title{font-size:15px;font-weight:800;color:#172b4d;line-height:1.35}
.meta{display:flex;gap:7px;flex-wrap:wrap;margin:10px 0 12px}.pill{font-size:12px;padding:4px 8px;border-radius:999px;background:#eef2f7;color:#526174;font-weight:650}
.jira{color:#2468e5;text-decoration:none;font-weight:800;padding:3px 7px;border-radius:7px;background:#edf4ff}.jira:hover{background:#dfeaff}
.details{margin-top:6px;color:#66758a;font-size:13px;white-space:pre-wrap;line-height:1.48}.details strong{color:#3d4f68}
.actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:13px;align-items:center}.button-link{display:inline-block;text-decoration:none}
.form-row{display:grid;grid-template-columns:1fr 1fr;gap:11px}.field{margin-bottom:13px}.field label{display:block;margin-bottom:6px;font-size:12px;font-weight:800;color:#41526c}.hint{margin-top:6px;font-size:12px;color:#7a8798;line-height:1.4}.empty{text-align:center;color:var(--muted);padding:42px 12px}
.jira-selected-list{display:flex;flex-direction:column;gap:8px;margin-bottom:9px}.jira-selected-empty{padding:11px;border:1px dashed #cbd5e3;border-radius:10px;color:var(--muted);font-size:13px;background:#fafcff}
.jira-selected-row{display:flex;align-items:center;gap:8px;padding:9px 10px;border:1px solid #d5deec;border-radius:10px;background:#f8faff}
.jira-selected-main{flex:1;min-width:0;color:var(--text);text-decoration:none}.jira-selected-main:hover .jira-story-key{text-decoration:underline}.jira-story-key{font-weight:850;color:#2468e5}.jira-story-summary{color:#4d5d72}.jira-open{color:#2468e5;text-decoration:none;font-weight:750;font-size:12px;white-space:nowrap}.jira-remove{padding:6px 9px;background:#fff0ee;color:#b42318;font-size:12px}
.sync-warning{margin-bottom:18px;padding:13px 15px;border:1px solid #f0cf64;border-radius:12px;background:#fff8dc;color:var(--warning);font-size:13px;box-shadow:0 8px 22px rgba(90,70,0,.05)}
.modal-backdrop{position:fixed;inset:0;z-index:50;display:flex;align-items:center;justify-content:center;padding:22px;background:rgba(17,30,54,.52);backdrop-filter:blur(5px)}.modal-backdrop[hidden]{display:none}
.jira-modal{width:min(740px,100%);max-height:84vh;display:flex;flex-direction:column;overflow:hidden;border:1px solid rgba(255,255,255,.65);border-radius:20px;background:rgba(255,255,255,.97);box-shadow:0 28px 90px rgba(9,30,66,.28)}
.jira-modal-head{display:flex;align-items:center;justify-content:space-between;padding:18px 20px;border-bottom:1px solid var(--border);background:#fbfcff}.jira-modal-head h3{margin:0;font-size:19px;color:#172b4d}
.jira-modal-body{padding:18px 20px;overflow:auto}.jira-modal-search{margin-bottom:13px}.jira-modal-list{display:flex;flex-direction:column;gap:7px;max-height:430px;overflow:auto}
.jira-modal-ticket{width:100%;padding:11px 13px;text-align:left;border:1px solid var(--border);border-radius:10px;background:#fff;font-weight:550}.jira-modal-ticket:hover{background:#f7faff}.jira-modal-ticket.selected{border-color:#4f7ff3;background:#edf4ff;box-shadow:0 0 0 3px rgba(59,115,239,.08)}
.jira-modal-message{padding:12px 2px;font-size:13px;color:var(--muted)}.jira-modal-actions{display:flex;justify-content:flex-end;gap:8px;padding:15px 20px;border-top:1px solid var(--border);background:#fbfcff}
@media(max-width:980px){.grid{grid-template-columns:1fr}aside.card{position:static}.stats{grid-template-columns:1fr 1fr}.form-row{grid-template-columns:1fr}}
@media(max-width:560px){header{padding:13px 16px}.header-note{display:none}main{padding:16px}.stats{grid-template-columns:1fr 1fr;gap:10px}.stat{padding:15px}.stat strong{font-size:26px}.card{padding:16px;border-radius:16px}.toolbar select{width:100%}.jira-selected-row{align-items:flex-start;flex-wrap:wrap}}

</style>
</head>
<body>
<header>
  <div class="brand"><div class="brand-icon">🧪</div><div><h1>Test Hub</h1><span>QA test case management</span></div></div>
  <div class="header-note">Grouped by feature · linked to Jira stories</div>
</header>
<main>
  {% if sync_warning %}
    <div class="sync-warning"><strong>Jira sync warning:</strong> {{ sync_warning }}</div>
  {% endif %}
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
          <input id="createJiraKeys" name="jira_keys" type="hidden">
          <div id="createSelectedJiraStories" class="jira-selected-list"></div>
          <button class="secondary" type="button" onclick="openJiraModal('create')">Add Jira ticket</button>
          <div class="hint">A test case can be linked to multiple Jira stories.</div>
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

<div id="createJiraModal" class="modal-backdrop" hidden>
  <div class="jira-modal" role="dialog" aria-modal="true" aria-labelledby="createJiraModalTitle">
    <div class="jira-modal-head">
      <h3 id="createJiraModalTitle">Add Jira ticket</h3>
      <button class="secondary" type="button" onclick="closeJiraModal('create')">Cancel</button>
    </div>
    <div class="jira-modal-body">
      <input id="createJiraModalSearch" class="jira-modal-search" type="search" placeholder="Search Jira key or title..." oninput="renderJiraModalStories('create')">
      <div id="createJiraModalList" class="jira-modal-list"></div>
    </div>
    <div class="jira-modal-actions">
      <button class="secondary" type="button" onclick="closeJiraModal('create')">Cancel</button>
      <button class="primary" type="button" onclick="confirmJiraSelection('create')">Add selected</button>
    </div>
  </div>
</div>

<script>
let jiraStories=[];
const jiraBrowseBase='{{ jira_base }}';
const jiraModalSelections={};

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

function escapeHtml(value){
  const div=document.createElement('div');
  div.textContent=value || '';
  return div.innerHTML;
}

function selectedJiraKeys(prefix){
  const value=document.getElementById(prefix+'JiraKeys').value.trim();
  return new Set(value?value.split(',').map(v=>v.trim().toUpperCase()).filter(Boolean):[]);
}

function storyByKey(key){
  return jiraStories.find(story=>story.key===key);
}

function renderSelectedJiraStories(prefix){
  const container=document.getElementById(prefix+'SelectedJiraStories');
  if(!container) return;
  const keys=[...selectedJiraKeys(prefix)];

  if(!keys.length){
    container.innerHTML='<div class="jira-selected-empty">No Jira tickets linked.</div>';
    return;
  }

  container.innerHTML=keys.map(key=>{
    const story=storyByKey(key);
    const summary=story?story.summary:'';
    return `<div class="jira-selected-row">
      <a class="jira-selected-main" href="/jira/${encodeURIComponent(key)}">
        <span class="jira-story-key">${escapeHtml(key)}</span>
        ${summary?` — <span class="jira-story-summary">${escapeHtml(summary)}</span>`:''}
      </a>
      <a class="jira-open" href="${jiraBrowseBase}/${encodeURIComponent(key)}" target="_blank" rel="noopener">Open in Jira</a>
      <button class="jira-remove" type="button" data-remove-jira="${escapeHtml(key)}">Remove</button>
    </div>`;
  }).join('');

  container.querySelectorAll('[data-remove-jira]').forEach(button=>{
    button.addEventListener('click',()=>removeJiraStory(prefix,button.dataset.removeJira));
  });
}

function removeJiraStory(prefix,key){
  const selected=selectedJiraKeys(prefix);
  selected.delete(key);
  document.getElementById(prefix+'JiraKeys').value=[...selected].join(', ');
  renderSelectedJiraStories(prefix);
}

function openJiraModal(prefix){
  jiraModalSelections[prefix]=new Set(selectedJiraKeys(prefix));
  document.getElementById(prefix+'JiraModalSearch').value='';
  document.getElementById(prefix+'JiraModal').hidden=false;
  renderJiraModalStories(prefix);
  document.getElementById(prefix+'JiraModalSearch').focus();
}

function closeJiraModal(prefix){
  document.getElementById(prefix+'JiraModal').hidden=true;
  delete jiraModalSelections[prefix];
}

function toggleModalJiraStory(prefix,key){
  const selected=jiraModalSelections[prefix] || new Set();
  selected.has(key)?selected.delete(key):selected.add(key);
  jiraModalSelections[prefix]=selected;
  renderJiraModalStories(prefix);
}

function renderJiraModalStories(prefix){
  const list=document.getElementById(prefix+'JiraModalList');
  if(!list) return;
  const search=document.getElementById(prefix+'JiraModalSearch').value.trim().toLowerCase();
  const selected=jiraModalSelections[prefix] || new Set();
  const matches=jiraStories.filter(story=>
    !search || story.key.toLowerCase().includes(search) || story.summary.toLowerCase().includes(search)
  );

  if(!matches.length){
    list.innerHTML='<div class="jira-modal-message">No matching Jira tickets.</div>';
    return;
  }

  list.innerHTML=matches.map(story=>{
    const isSelected=selected.has(story.key);
    return `<button type="button" class="jira-modal-ticket ${isSelected?'selected':''}" data-jira-key="${story.key}">
      <span class="jira-story-key">${escapeHtml(story.key)}</span> —
      <span class="jira-story-summary">${escapeHtml(story.summary)}</span>
      ${story.status?` <small>(${escapeHtml(story.status)})</small>`:''}
    </button>`;
  }).join('');

  list.querySelectorAll('[data-jira-key]').forEach(button=>{
    button.addEventListener('click',()=>toggleModalJiraStory(prefix,button.dataset.jiraKey));
  });
}

function confirmJiraSelection(prefix){
  const selected=jiraModalSelections[prefix] || new Set();
  document.getElementById(prefix+'JiraKeys').value=[...selected].join(', ');
  renderSelectedJiraStories(prefix);
  closeJiraModal(prefix);
}

async function loadJiraStories(prefix){
  try{
    const response=await fetch('/api/jira/stories');
    const data=await response.json();
    if(!response.ok) throw new Error(data.error || 'Unable to load Jira stories.');
    jiraStories=data.stories || [];
    renderSelectedJiraStories(prefix);
  }catch(error){
    const container=document.getElementById(prefix+'SelectedJiraStories');
    if(container) container.innerHTML='<div class="jira-selected-empty">'+escapeHtml(error.message)+'</div>';
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
:root{
  --bg:#eef3fb;--surface:rgba(255,255,255,.94);--text:#111827;--muted:#6b7280;--border:#d7dfec;
  --accent:#2f66e8;--accent2:#2475ff;
  font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif
}
*{box-sizing:border-box}
body{margin:0;min-height:100vh;color:var(--text);background:radial-gradient(circle at 8% 5%,rgba(98,134,255,.17),transparent 28%),radial-gradient(circle at 94% 16%,rgba(36,117,255,.11),transparent 24%),linear-gradient(180deg,#f8faff,#eef3fb)}
header{display:flex;align-items:center;justify-content:space-between;padding:16px 30px;background:rgba(20,42,82,.94);color:#fff;box-shadow:0 10px 30px rgba(24,47,90,.14);backdrop-filter:blur(14px)}
.brand{display:flex;align-items:center;gap:12px}.brand-icon{width:42px;height:42px;display:grid;place-items:center;border-radius:13px;background:linear-gradient(135deg,#6286ff,#1f63f2);box-shadow:0 8px 22px rgba(37,99,235,.3)}.brand strong{font-size:20px}.brand span{display:block;font-size:12px;opacity:.7;margin-top:2px}
.wrap{max-width:1050px;margin:0 auto;padding:34px 24px 48px}.top{display:flex;justify-content:space-between;gap:20px;align-items:flex-start;margin-bottom:22px}.top h1{margin:0 0 6px;font-size:30px;letter-spacing:-.6px;color:#172b4d}.muted{color:var(--muted);font-weight:550}
.actions{display:flex;gap:9px;flex-wrap:wrap}.button{display:inline-block;text-decoration:none;border-radius:10px;padding:10px 14px;font-weight:750;background:#eef2f7;color:#20324f;transition:transform .15s ease,box-shadow .15s ease}.button:hover{transform:translateY(-1px)}.primary{background:linear-gradient(90deg,#2f66e8,#2475ff);color:#fff;box-shadow:0 8px 18px rgba(37,99,235,.2)}
.case{margin:14px 0;padding:20px;border:1px solid rgba(215,223,236,.95);border-radius:17px;background:var(--surface);box-shadow:0 14px 38px rgba(35,61,108,.07);backdrop-filter:blur(12px)}
.title{font-size:17px;font-weight:850;color:#172b4d;line-height:1.35}.feature{margin-top:7px;font-size:13px;font-weight:750;color:#506078}.meta{display:flex;gap:7px;flex-wrap:wrap;margin:12px 0}
.pill{font-size:12px;padding:4px 8px;border-radius:999px;background:#eef2f7;color:#526174;font-weight:650}.jira{color:#2468e5;text-decoration:none;font-weight:800;padding:3px 7px;border-radius:7px;background:#edf4ff}.jira:hover{background:#dfeaff}
.details{margin-top:8px;font-size:13px;color:#66758a;white-space:pre-wrap;line-height:1.5}.details strong{color:#3d4f68}.empty{padding:38px;text-align:center;color:var(--muted);border:1px dashed var(--border);border-radius:16px;background:rgba(255,255,255,.72)}
@media(max-width:680px){header{padding:13px 16px}.wrap{padding:22px 16px}.top{flex-direction:column}.top h1{font-size:26px}.case{padding:16px}}

</style>
</head>
<body>
<header>
  <div class="brand"><div class="brand-icon">🧪</div><div><strong>Test Hub</strong><span>QA test case management</span></div></div>
</header>
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
:root{
  --bg:#eef3fb;--surface:rgba(255,255,255,.95);--text:#111827;--muted:#6b7280;--border:#d7dfec;
  --accent:#2f66e8;--accent2:#2475ff;--danger:#b42318;
  font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif
}
*{box-sizing:border-box}
body{margin:0;min-height:100vh;color:var(--text);background:radial-gradient(circle at 8% 5%,rgba(98,134,255,.17),transparent 28%),radial-gradient(circle at 94% 16%,rgba(36,117,255,.11),transparent 24%),linear-gradient(180deg,#f8faff,#eef3fb)}
header{display:flex;align-items:center;justify-content:space-between;padding:16px 30px;background:rgba(20,42,82,.94);color:#fff;box-shadow:0 10px 30px rgba(24,47,90,.14);backdrop-filter:blur(14px)}
.brand{display:flex;align-items:center;gap:12px}.brand-icon{width:42px;height:42px;display:grid;place-items:center;border-radius:13px;background:linear-gradient(135deg,#6286ff,#1f63f2);box-shadow:0 8px 22px rgba(37,99,235,.3)}.brand strong{font-size:20px}.brand span{display:block;font-size:12px;opacity:.7;margin-top:2px}
main{max-width:900px;margin:0 auto;padding:34px 22px 50px}.card{padding:28px;border:1px solid rgba(215,223,236,.95);border-radius:20px;background:var(--surface);box-shadow:0 20px 55px rgba(35,61,108,.09);backdrop-filter:blur(12px)}
h1{margin:0 0 5px;font-size:29px;letter-spacing:-.6px;color:#172b4d}.page-subtitle{margin:0 0 25px;color:var(--muted);font-size:14px}
.field{margin-bottom:16px}.field label{display:block;margin-bottom:6px;font-size:12px;font-weight:800;color:#41526c}.form-row{display:grid;grid-template-columns:1fr 1fr;gap:13px}
input,select,textarea,button{font:inherit}input,select,textarea{width:100%;border:1px solid #ccd5e4;border-radius:11px;background:rgba(255,255,255,.92);color:var(--text);outline:none;transition:border-color .18s ease,box-shadow .18s ease}
input,select{height:47px;padding:0 13px}textarea{min-height:108px;padding:11px 13px;resize:vertical;line-height:1.45}input:focus,select:focus,textarea:focus{border-color:#3b73ef;box-shadow:0 0 0 4px rgba(59,115,239,.12);background:#fff}
.actions{display:flex;gap:9px;margin-top:22px;flex-wrap:wrap}.primary,.cancel{border:0;border-radius:10px;padding:11px 15px;font-weight:750;cursor:pointer;text-decoration:none;transition:transform .15s ease,box-shadow .15s ease}.primary{background:linear-gradient(90deg,#2f66e8,#2475ff);color:#fff;box-shadow:0 8px 18px rgba(37,99,235,.2)}.primary:hover,.cancel:hover{transform:translateY(-1px)}.cancel{background:#eef2f7;color:#20324f}
.hint{margin-top:6px;font-size:12px;color:#7a8798}.jira-selected-list{display:flex;flex-direction:column;gap:8px;margin-bottom:9px}.jira-selected-empty{padding:11px;border:1px dashed #cbd5e3;border-radius:10px;color:var(--muted);font-size:13px;background:#fafcff}
.jira-selected-row{display:flex;align-items:center;gap:8px;padding:9px 10px;border:1px solid #d5deec;border-radius:10px;background:#f8faff}.jira-selected-main{flex:1;min-width:0;color:var(--text);text-decoration:none}.jira-selected-main:hover .jira-story-key{text-decoration:underline}.jira-story-key{font-weight:850;color:#2468e5}.jira-story-summary{color:#4d5d72}.jira-open{color:#2468e5;text-decoration:none;font-weight:750;font-size:12px;white-space:nowrap}.jira-remove{background:#fff0ee;color:var(--danger);border:0;border-radius:8px;padding:6px 9px;font-size:12px;cursor:pointer}
.modal-backdrop{position:fixed;inset:0;z-index:50;display:flex;align-items:center;justify-content:center;padding:22px;background:rgba(17,30,54,.52);backdrop-filter:blur(5px)}.modal-backdrop[hidden]{display:none}.jira-modal{width:min(740px,100%);max-height:84vh;display:flex;flex-direction:column;overflow:hidden;border:1px solid rgba(255,255,255,.65);border-radius:20px;background:rgba(255,255,255,.97);box-shadow:0 28px 90px rgba(9,30,66,.28)}
.jira-modal-head{display:flex;align-items:center;justify-content:space-between;padding:18px 20px;border-bottom:1px solid var(--border);background:#fbfcff}.jira-modal-head h3{margin:0;font-size:19px;color:#172b4d}.jira-modal-body{padding:18px 20px;overflow:auto}.jira-modal-search{margin-bottom:13px}.jira-modal-list{display:flex;flex-direction:column;gap:7px;max-height:430px;overflow:auto}.jira-modal-ticket{width:100%;padding:11px 13px;text-align:left;border:1px solid var(--border);border-radius:10px;background:#fff;font-weight:550;cursor:pointer}.jira-modal-ticket:hover{background:#f7faff}.jira-modal-ticket.selected{border-color:#4f7ff3;background:#edf4ff;box-shadow:0 0 0 3px rgba(59,115,239,.08)}.jira-modal-message{padding:12px 2px;font-size:13px;color:var(--muted)}.jira-modal-actions{display:flex;justify-content:flex-end;gap:8px;padding:15px 20px;border-top:1px solid var(--border);background:#fbfcff}
@media(max-width:650px){header{padding:13px 16px}main{padding:22px 14px}.card{padding:19px}.form-row{grid-template-columns:1fr}.jira-selected-row{align-items:flex-start;flex-wrap:wrap}}

</style>
</head>
<body>
<header>
  <div class="brand"><div class="brand-icon">🧪</div><div><strong>Test Hub</strong><span>QA test case management</span></div></div>
</header>
<main>
  <div class="card">
    <h1>Edit test case</h1>
    <p class="page-subtitle">Update the test case details, Jira links, execution type and expected result.</p>
    <form method="post" action="{{ url_for('update_case', case_key=case.case_key) }}">
      <div class="form-row">
        <div class="field"><label>Test case ID</label><input name="case_key" value="{{ case.case_key }}" required></div>
        <div class="field"><label>Feature / Module</label><input name="feature" value="{{ case.feature_name }}" required></div>
      </div>
      <div class="field"><label>Title</label><input name="title" value="{{ case.title }}" required></div>
      <div class="field">
        <label>Jira stories</label>
        <input id="editJiraKeys" name="jira_keys" type="hidden" value="{{ case.jira_keys|join(', ') }}">
        <div id="editSelectedJiraStories" class="jira-selected-list"></div>
        <button class="cancel" type="button" onclick="openEditJiraModal()">Add Jira ticket</button>
        <div class="hint">A test case can be linked to multiple Jira stories.</div>
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
        <a class="cancel" href="{{ url_for('index') }}">Cancel</a>
      </div>
    </form>
  </div>
</main>

<div id="editJiraModal" class="modal-backdrop" hidden>
  <div class="jira-modal" role="dialog" aria-modal="true" aria-labelledby="editJiraModalTitle">
    <div class="jira-modal-head">
      <h3 id="editJiraModalTitle">Add Jira ticket</h3>
      <button class="cancel" type="button" onclick="closeEditJiraModal()">Cancel</button>
    </div>
    <div class="jira-modal-body">
      <input id="editJiraModalSearch" class="jira-modal-search" type="search" placeholder="Search Jira key or title..." oninput="renderEditJiraModalStories()">
      <div id="editJiraModalList" class="jira-modal-list"></div>
    </div>
    <div class="jira-modal-actions">
      <button class="cancel" type="button" onclick="closeEditJiraModal()">Cancel</button>
      <button class="primary" type="button" onclick="confirmEditJiraSelection()">Add selected</button>
    </div>
  </div>
</div>

<script>
let editJiraStories=[];
let editJiraModalSelection=new Set();
const editJiraBrowseBase='{{ jira_base }}';

function escapeEditHtml(value){
  const div=document.createElement('div');
  div.textContent=value || '';
  return div.innerHTML;
}

function editSelectedJiraKeys(){
  const value=document.getElementById('editJiraKeys').value.trim();
  return new Set(value?value.split(',').map(v=>v.trim().toUpperCase()).filter(Boolean):[]);
}

function editStoryByKey(key){
  return editJiraStories.find(story=>story.key===key);
}

function renderEditSelectedJiraStories(){
  const container=document.getElementById('editSelectedJiraStories');
  const keys=[...editSelectedJiraKeys()];

  if(!keys.length){
    container.innerHTML='<div class="jira-selected-empty">No Jira tickets linked.</div>';
    return;
  }

  container.innerHTML=keys.map(key=>{
    const story=editStoryByKey(key);
    const summary=story?story.summary:'';
    return `<div class="jira-selected-row">
      <a class="jira-selected-main" href="/jira/${encodeURIComponent(key)}">
        <span class="jira-story-key">${escapeEditHtml(key)}</span>
        ${summary?` — <span class="jira-story-summary">${escapeEditHtml(summary)}</span>`:''}
      </a>
      <a class="jira-open" href="${editJiraBrowseBase}/${encodeURIComponent(key)}" target="_blank" rel="noopener">Open in Jira</a>
      <button class="jira-remove" type="button" data-remove-jira="${escapeEditHtml(key)}">Remove</button>
    </div>`;
  }).join('');

  container.querySelectorAll('[data-remove-jira]').forEach(button=>{
    button.addEventListener('click',()=>removeEditJiraStory(button.dataset.removeJira));
  });
}

function removeEditJiraStory(key){
  const selected=editSelectedJiraKeys();
  selected.delete(key);
  document.getElementById('editJiraKeys').value=[...selected].join(', ');
  renderEditSelectedJiraStories();
}

function openEditJiraModal(){
  editJiraModalSelection=new Set(editSelectedJiraKeys());
  document.getElementById('editJiraModalSearch').value='';
  document.getElementById('editJiraModal').hidden=false;
  renderEditJiraModalStories();
  document.getElementById('editJiraModalSearch').focus();
}

function closeEditJiraModal(){
  document.getElementById('editJiraModal').hidden=true;
}

function toggleEditJiraModalStory(key){
  editJiraModalSelection.has(key)?editJiraModalSelection.delete(key):editJiraModalSelection.add(key);
  renderEditJiraModalStories();
}

function renderEditJiraModalStories(){
  const list=document.getElementById('editJiraModalList');
  const search=document.getElementById('editJiraModalSearch').value.trim().toLowerCase();
  const matches=editJiraStories.filter(story=>
    !search || story.key.toLowerCase().includes(search) || story.summary.toLowerCase().includes(search)
  );

  if(!matches.length){
    list.innerHTML='<div class="jira-modal-message">No matching Jira tickets.</div>';
    return;
  }

  list.innerHTML=matches.map(story=>{
    const isSelected=editJiraModalSelection.has(story.key);
    return `<button type="button" class="jira-modal-ticket ${isSelected?'selected':''}" data-jira-key="${story.key}">
      <span class="jira-story-key">${escapeEditHtml(story.key)}</span> —
      <span class="jira-story-summary">${escapeEditHtml(story.summary)}</span>
      ${story.status?` <small>(${escapeEditHtml(story.status)})</small>`:''}
    </button>`;
  }).join('');

  list.querySelectorAll('[data-jira-key]').forEach(button=>{
    button.addEventListener('click',()=>toggleEditJiraModalStory(button.dataset.jiraKey));
  });
}

function confirmEditJiraSelection(){
  document.getElementById('editJiraKeys').value=[...editJiraModalSelection].join(', ');
  renderEditSelectedJiraStories();
  closeEditJiraModal();
}

async function loadEditJiraStories(){
  try{
    const response=await fetch('/api/jira/stories');
    const data=await response.json();
    if(!response.ok) throw new Error(data.error || 'Unable to load Jira stories.');
    editJiraStories=data.stories || [];
    renderEditSelectedJiraStories();
  }catch(error){
    const container=document.getElementById('editSelectedJiraStories');
    container.innerHTML='<div class="jira-selected-empty">'+escapeEditHtml(error.message)+'</div>';
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
        jira_base=JIRA_BASE_URL.rstrip("/"),
        sync_warning=request.args.get("jira_sync_error", ""),
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

    sync_errors = sync_jira_test_hub_web_links(jira_keys)
    if sync_errors:
        return redirect(url_for("index", jira_sync_error=" | ".join(sync_errors)))

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
        jira_base=JIRA_BASE_URL.rstrip("/"),
    )


@app.post("/test-cases/<case_key>/edit")
def update_case(case_key):
    case = db.session.scalar(
        db.select(TestCase).where(TestCase.case_key == case_key)
    )
    if case is None:
        return "Test case not found.", 404

    old_jira_keys = set(case.jira_keys)
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

    removed_jira_keys = old_jira_keys - set(jira_keys)
    sync_errors = sync_jira_test_hub_web_links(jira_keys, removed_jira_keys)
    if sync_errors:
        return redirect(url_for("index", jira_sync_error=" | ".join(sync_errors)))

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

    removed_jira_keys = set(case.jira_keys)
    db.session.delete(case)
    db.session.commit()

    sync_errors = sync_jira_test_hub_web_links([], removed_jira_keys)
    if sync_errors:
        return redirect(url_for("index", jira_sync_error=" | ".join(sync_errors)))

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
