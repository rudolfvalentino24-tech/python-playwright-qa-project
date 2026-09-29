from pathlib import Path
from collections import OrderedDict
from flask import Flask, jsonify, redirect, render_template_string, request, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import UniqueConstraint, inspect, text
import base64
import json
import os
import re
import hmac
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from datetime import datetime, timezone

BASE_DIR = Path(__file__).resolve().parent
JIRA_SITE_URL = os.environ.get("JIRA_SITE_URL", "https://qa-test-store.atlassian.net").rstrip("/")
JIRA_BASE_URL = f"{JIRA_SITE_URL}/browse"
JIRA_PROJECT_KEY = os.environ.get("JIRA_PROJECT_KEY", "SCRUM").strip().upper()
JIRA_EMAIL = os.environ.get("JIRA_EMAIL", "").strip()
JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN", "").strip()
TEST_HUB_BASE_URL = os.environ.get("TEST_HUB_BASE_URL", "http://127.0.0.1:3000").rstrip("/")
TEST_HUB_API_KEY = os.environ.get("TEST_HUB_API_KEY", "").strip()
JENKINS_URL = os.environ.get("JENKINS_URL", "http://127.0.0.1:8080").rstrip("/")
JENKINS_JOB_NAME = os.environ.get("JENKINS_JOB_NAME", "").strip()
JENKINS_USER = os.environ.get("JENKINS_USER", "").strip()
JENKINS_API_TOKEN = os.environ.get("JENKINS_API_TOKEN", "").strip()

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
RESULT_STATUSES = {"Passed", "Failed", "Blocked", "Skipped"}
RUN_PRESETS = {"Custom", "Smoke", "Regression", "Full Release"}
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
    suite_tags = db.Column(db.String(250), nullable=False, default="")
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
    results = db.relationship(
        "TestResult",
        back_populates="test_case",
        order_by="TestResult.executed_at.desc()",
    )

    @property
    def feature_name(self):
        return (self.feature or "").strip() or "Uncategorized"

    @property
    def jira_keys(self):
        return [link.jira_key for link in self.jira_links]

    @property
    def suite_tag_list(self):
        return [
            tag.strip().lower()
            for tag in (self.suite_tags or "").split(",")
            if tag.strip()
        ]

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
            "suite_tags": self.suite_tag_list,
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


class Release(db.Model):
    __tablename__ = "releases"

    id = db.Column(db.Integer, primary_key=True)
    version = db.Column(db.String(100), unique=True, nullable=False, index=True)
    release_date = db.Column(db.Date, nullable=True, index=True)
    environment = db.Column(db.String(80), nullable=False, default="")
    git_commit = db.Column(db.String(120), nullable=False, default="")
    notes = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    runs = db.relationship(
        "TestRun",
        back_populates="release",
        order_by="TestRun.started_at",
    )


class TestRun(db.Model):
    __tablename__ = "test_runs"

    id = db.Column(db.Integer, primary_key=True)
    release_id = db.Column(
        db.Integer,
        db.ForeignKey("releases.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name = db.Column(db.String(250), nullable=False)
    preset = db.Column(db.String(30), nullable=False, default="Custom")
    execution_type = db.Column(db.String(20), nullable=False, default="Manual")
    environment = db.Column(db.String(80), nullable=False, default="")
    execution_status = db.Column(db.String(20), nullable=False, default="Planned", index=True)
    jenkins_queue_url = db.Column(db.String(500), nullable=False, default="")
    jenkins_build_number = db.Column(db.String(50), nullable=False, default="")
    jenkins_build_url = db.Column(db.String(500), nullable=False, default="")
    jenkins_report_url = db.Column(db.String(500), nullable=False, default="")
    jenkins_artifacts_url = db.Column(db.String(500), nullable=False, default="")
    runner_message = db.Column(db.Text, nullable=False, default="")
    started_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    finished_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    release = db.relationship("Release", back_populates="runs")
    items = db.relationship(
        "TestRunItem",
        back_populates="test_run",
        cascade="all, delete-orphan",
        order_by="TestRunItem.position",
    )
    results = db.relationship(
        "TestResult",
        back_populates="test_run",
        cascade="all, delete-orphan",
        order_by="TestResult.executed_at",
    )


class TestRunItem(db.Model):
    __tablename__ = "test_run_items"
    __table_args__ = (
        UniqueConstraint("test_run_id", "case_key_snapshot", name="uq_test_run_case_key"),
    )

    id = db.Column(db.Integer, primary_key=True)
    test_run_id = db.Column(
        db.Integer,
        db.ForeignKey("test_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    test_case_id = db.Column(
        db.Integer,
        db.ForeignKey("test_cases.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    position = db.Column(db.Integer, nullable=False)
    case_key_snapshot = db.Column(db.String(64), nullable=False)
    case_title_snapshot = db.Column(db.String(250), nullable=False)
    feature_snapshot = db.Column(db.String(120), nullable=False)

    test_run = db.relationship("TestRun", back_populates="items")
    test_case = db.relationship("TestCase")


class TestResult(db.Model):
    __tablename__ = "test_results"

    id = db.Column(db.Integer, primary_key=True)
    test_run_id = db.Column(
        db.Integer,
        db.ForeignKey("test_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    test_case_id = db.Column(
        db.Integer,
        db.ForeignKey("test_cases.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    result = db.Column(db.String(20), nullable=False, index=True)
    executed_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    duration_ms = db.Column(db.Integer, nullable=True)
    runner_build_number = db.Column(db.String(50), nullable=False, default="")
    runner_build_url = db.Column(db.String(500), nullable=False, default="")
    notes = db.Column(db.Text, nullable=False, default="")
    error_message = db.Column(db.Text, nullable=False, default="")

    # Immutable snapshots keep old reports accurate if a test case is renamed later.
    case_key_snapshot = db.Column(db.String(64), nullable=False)
    case_title_snapshot = db.Column(db.String(250), nullable=False)
    feature_snapshot = db.Column(db.String(120), nullable=False)

    test_run = db.relationship("TestRun", back_populates="results")
    test_case = db.relationship("TestCase", back_populates="results")


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


def test_case_execution_stats(case):
    counts = {status: 0 for status in RESULT_STATUSES}
    for result in case.results:
        if result.result in counts:
            counts[result.result] += 1

    total = sum(counts.values())
    decided = counts["Passed"] + counts["Failed"]
    pass_rate = round((counts["Passed"] / decided) * 100, 1) if decided else 0

    return {
        "total": total,
        "passed": counts["Passed"],
        "failed": counts["Failed"],
        "blocked": counts["Blocked"],
        "skipped": counts["Skipped"],
        "pass_rate": pass_rate,
    }


def test_run_latest_results(run):
    """Return the latest execution result for each planned test in a run."""
    latest = {}
    for result in run.results:
        latest[result.case_key_snapshot] = result
    return latest


def test_run_summary(run):
    attempts_by_case = {}
    for result in run.results:
        attempts_by_case.setdefault(result.case_key_snapshot, []).append(result)

    counts = {status: 0 for status in RESULT_STATUSES}
    rows = []

    for item in run.items:
        attempts = attempts_by_case.get(item.case_key_snapshot, [])
        result = attempts[-1] if attempts else None
        status = result.result if result else "Not Run"
        if result:
            counts[result.result] += 1
        rows.append({
            "item": item,
            "result": result,
            "status": status,
            "attempts": attempts,
        })

    total = len(run.items)
    executed = sum(counts.values())
    not_run = max(total - executed, 0)
    progress = round((executed / total) * 100, 1) if total else 0
    decided = counts["Passed"] + counts["Failed"]
    pass_rate = round((counts["Passed"] / decided) * 100, 1) if decided else 0

    return {
        "total": total,
        "executed": executed,
        "not_run": not_run,
        "passed": counts["Passed"],
        "failed": counts["Failed"],
        "blocked": counts["Blocked"],
        "skipped": counts["Skipped"],
        "progress": progress,
        "pass_rate": pass_rate,
        "attempts": len(run.results),
        "rows": rows,
    }


def release_latest_results(release):
    """Return the latest result per test case for a release."""
    latest = {}
    results = db.session.scalars(
        db.select(TestResult)
        .join(TestRun)
        .where(TestRun.release_id == release.id)
        .order_by(TestResult.executed_at.asc(), TestResult.id.asc())
    ).all()

    for result in results:
        latest[result.case_key_snapshot] = result
    return list(latest.values())


def release_report_stats(release):
    final_results = release_latest_results(release)
    counts = {status: 0 for status in RESULT_STATUSES}
    feature_counts = {}

    for result in final_results:
        if result.result in counts:
            counts[result.result] += 1

        feature = result.feature_snapshot or "Uncategorized"
        if feature not in feature_counts:
            feature_counts[feature] = {status: 0 for status in RESULT_STATUSES}
        if result.result in feature_counts[feature]:
            feature_counts[feature][result.result] += 1

    total = sum(counts.values())
    decided = counts["Passed"] + counts["Failed"]
    pass_rate = round((counts["Passed"] / decided) * 100, 1) if decided else 0

    feature_rows = []
    for feature in sorted(feature_counts):
        row = feature_counts[feature]
        row_total = sum(row.values())
        row_decided = row["Passed"] + row["Failed"]
        row_rate = round((row["Passed"] / row_decided) * 100, 1) if row_decided else 0
        feature_rows.append({
            "feature": feature,
            "total": row_total,
            "passed": row["Passed"],
            "failed": row["Failed"],
            "blocked": row["Blocked"],
            "skipped": row["Skipped"],
            "pass_rate": row_rate,
        })

    return {
        "total": total,
        "passed": counts["Passed"],
        "failed": counts["Failed"],
        "blocked": counts["Blocked"],
        "skipped": counts["Skipped"],
        "pass_rate": pass_rate,
        "features": feature_rows,
        "final_results": sorted(
            final_results,
            key=lambda item: (item.feature_snapshot.lower(), item.case_key_snapshot),
        ),
    }


def test_hub_api_authorized():
    if not TEST_HUB_API_KEY:
        return False
    supplied = request.headers.get("Authorization", "")
    expected = f"Bearer {TEST_HUB_API_KEY}"
    return hmac.compare_digest(supplied, expected)


def trigger_jenkins_test_run(run):
    """Queue a parameterized Jenkins build for one automated Test Hub run."""
    if not JENKINS_JOB_NAME:
        raise RuntimeError("JENKINS_JOB_NAME is not configured.")
    if not JENKINS_USER or not JENKINS_API_TOKEN:
        raise RuntimeError("Jenkins credentials are not configured.")
    if not TEST_HUB_API_KEY:
        raise RuntimeError("TEST_HUB_API_KEY is not configured.")

    case_ids = [item.case_key_snapshot for item in run.items]
    if not case_ids:
        raise RuntimeError("The test run has no planned test cases.")

    auth = base64.b64encode(
        f"{JENKINS_USER}:{JENKINS_API_TOKEN}".encode("utf-8")
    ).decode("ascii")
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    # Jenkins API tokens normally bypass CSRF crumbs, but use one when available.
    try:
        crumb_request = Request(
            f"{JENKINS_URL}/crumbIssuer/api/json",
            headers={"Authorization": f"Basic {auth}", "Accept": "application/json"},
        )
        with urlopen(crumb_request, timeout=10) as response:
            crumb_data = json.loads(response.read().decode("utf-8"))
            crumb_field = crumb_data.get("crumbRequestField")
            crumb_value = crumb_data.get("crumb")
            if crumb_field and crumb_value:
                headers[crumb_field] = crumb_value
    except (HTTPError, URLError, json.JSONDecodeError):
        pass

    parameters = urlencode({
        "TEST_RUN_ID": str(run.id),
        "TEST_CASE_IDS": ",".join(case_ids),
        "TEST_HUB_URL": TEST_HUB_BASE_URL,
    }).encode("utf-8")

    job_url = f"{JENKINS_URL}/job/{quote(JENKINS_JOB_NAME, safe='')}"
    build_request = Request(
        f"{job_url}/buildWithParameters",
        data=parameters,
        method="POST",
        headers=headers,
    )

    try:
        with urlopen(build_request, timeout=15) as response:
            return response.headers.get("Location", "")
    except HTTPError as exc:
        if exc.code == 401:
            raise RuntimeError("Jenkins authentication failed.") from exc
        if exc.code == 403:
            raise RuntimeError(
                "Jenkins denied the build request. Check API token, Build permission and CSRF settings."
            ) from exc
        if exc.code == 404:
            raise RuntimeError(
                "Jenkins job was not found. Check JENKINS_URL and JENKINS_JOB_NAME."
            ) from exc
        raise RuntimeError(f"Jenkins returned HTTP {exc.code}.") from exc
    except URLError as exc:
        raise RuntimeError("Test Hub could not connect to Jenkins.") from exc


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
  <div class="header-note"><a href="{{ url_for('test_runs') }}" style="color:#fff;text-decoration:none;font-weight:750">Test Runs</a> · <a href="{{ url_for('releases') }}" style="color:#fff;text-decoration:none;font-weight:750">Releases</a> · Grouped by feature</div>
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
        <input id="search" placeholder="Search feature, ID, title or Jira key…">
        <select id="typeFilter"><option value="">All types</option><option>Manual</option><option>Automated</option></select>
        <select id="statusFilter"><option value="">All statuses</option><option>Draft</option><option>Ready</option><option>Passed</option><option>Failed</option><option>Blocked</option></select>
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
                <div class="case-title"><a href="{{ url_for('test_case_details', case_key=c.case_key) }}" style="color:inherit;text-decoration:none">{{ c.case_key }} — {{ c.title }}</a></div>
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
      <div id="noSearchResults" class="empty" style="display:none">No matching test cases.</div>
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
  let totalVisible=0;

  document.querySelectorAll('.feature-group').forEach(group=>{
    const feature=(group.dataset.feature || '').toLowerCase();
    let groupVisible=0;

    group.querySelectorAll('.case').forEach(testCase=>{
      const searchableText=(feature+' '+testCase.textContent).toLowerCase();
      const matchesText=!q || searchableText.includes(q);
      const matchesType=!type || testCase.dataset.type===type;
      const matchesStatus=!status || testCase.dataset.status===status;
      const show=matchesText && matchesType && matchesStatus;

      testCase.style.display=show?'block':'none';
      if(show){
        groupVisible++;
        totalVisible++;
      }
    });

    group.style.display=groupVisible?'block':'none';

    const count=group.querySelector('.feature-count');
    if(count && (q || type || status)){
      count.textContent=groupVisible+' test case'+(groupVisible===1?'':'s');
    } else if(count){
      const originalCount=group.querySelectorAll('.case').length;
      count.textContent=originalCount+' test case'+(originalCount===1?'':'s');
    }
  });

  document.getElementById('noSearchResults').style.display=totalVisible?'none':'block';
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

document.addEventListener('DOMContentLoaded',()=>{
  document.getElementById('search').addEventListener('input',filterCases);
  document.getElementById('typeFilter').addEventListener('change',filterCases);
  document.getElementById('statusFilter').addEventListener('change',filterCases);
  loadJiraStories('create');
});
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
      <div class="title"><a href="{{ url_for('test_case_details', case_key=c.case_key) }}" style="color:inherit;text-decoration:none">{{ c.case_key }} — {{ c.title }}</a></div>
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


TEST_RUNS_PAGE_HTML = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Test Runs - Test Hub</title>
<style>
:root{--bg:#eef3fb;--surface:rgba(255,255,255,.95);--text:#111827;--muted:#6b7280;--border:#d7dfec;--accent:#2f66e8;--accent2:#2475ff;font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
*{box-sizing:border-box}body{margin:0;min-height:100vh;color:var(--text);background:radial-gradient(circle at 8% 5%,rgba(98,134,255,.17),transparent 28%),radial-gradient(circle at 94% 16%,rgba(36,117,255,.11),transparent 24%),linear-gradient(180deg,#f8faff,#eef3fb)}
header{padding:16px 30px;background:rgba(20,42,82,.94);color:#fff;box-shadow:0 10px 30px rgba(24,47,90,.14)}.brand{display:flex;align-items:center;gap:12px}.brand-icon{width:42px;height:42px;display:grid;place-items:center;border-radius:13px;background:linear-gradient(135deg,#6286ff,#1f63f2);box-shadow:0 8px 22px rgba(37,99,235,.3)}.brand strong{font-size:20px}.brand span{display:block;font-size:12px;opacity:.7}
.wrap{max-width:1260px;margin:0 auto;padding:32px 22px 50px}.top{display:flex;justify-content:space-between;gap:18px;align-items:flex-start;margin-bottom:20px}.top h1{margin:0;font-size:30px;color:#172b4d}.subtitle{margin-top:5px;color:var(--muted)}.actions{display:flex;gap:8px;flex-wrap:wrap}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px;align-items:start}.card{padding:21px;border:1px solid var(--border);border-radius:18px;background:var(--surface);box-shadow:0 16px 42px rgba(35,61,108,.07)}.card h2{margin:0 0 14px;font-size:19px;color:#172b4d}
.button,button{display:inline-block;border:0;border-radius:10px;padding:10px 14px;text-decoration:none;font:inherit;font-weight:750;cursor:pointer}.button{background:#eef2f7;color:#20324f}.primary{background:linear-gradient(90deg,#2f66e8,#2475ff);color:#fff;box-shadow:0 8px 18px rgba(37,99,235,.2)}
.run{padding:15px 0;border-top:1px solid #e7ebf2}.run:first-of-type{border-top:0}.run-head{display:flex;justify-content:space-between;gap:12px}.run-title{color:#172b4d;text-decoration:none;font-weight:850}.run-title:hover{color:#2468e5}.muted{color:var(--muted);font-size:12px;margin-top:4px}.summary{display:flex;gap:7px;flex-wrap:wrap;margin-top:9px}.pill{padding:4px 8px;border-radius:999px;background:#eef2f7;color:#526174;font-size:12px;font-weight:700}.pass{background:#dcfce7;color:#166534}.fail{background:#fee2e2;color:#991b1b}
label{display:block;margin:13px 0 6px;font-size:12px;font-weight:800;color:#41526c}input,select{width:100%;height:45px;padding:0 12px;border:1px solid #ccd5e4;border-radius:11px;background:#fff;color:var(--text);font:inherit;outline:none}input:focus,select:focus{border-color:#3b73ef;box-shadow:0 0 0 4px rgba(59,115,239,.12)}
.case-tools{display:flex;gap:8px;margin:10px 0}.case-tools input{flex:1}.case-list{max-height:430px;overflow:auto;border:1px solid var(--border);border-radius:12px;background:#fff}.case-option{display:flex;gap:10px;align-items:flex-start;padding:11px 12px;border-top:1px solid #edf0f5}.case-option:first-child{border-top:0}.case-option input{width:17px;height:17px;margin:2px 0 0}.case-option strong{display:block;font-size:13px;color:#243854}.case-option span{font-size:12px;color:var(--muted)}.empty{padding:28px;text-align:center;color:var(--muted)}
@media(max-width:850px){header{padding:13px 16px}.wrap{padding:22px 14px}.grid{grid-template-columns:1fr}.top{flex-direction:column}}
</style>
</head>
<body>
<header><div class="brand"><div class="brand-icon">🧪</div><div><strong>Test Hub</strong><span>QA test case management</span></div></div></header>
<main class="wrap">
  <div class="top">
    <div><h1>Test Runs</h1><div class="subtitle">Plan and execute manual or automated QA runs.</div></div>
    <div class="actions"><a class="button" href="{{ url_for('releases') }}">Releases</a><a class="button" href="{{ url_for('index') }}">Test cases</a></div>
  </div>

  <section class="grid">
    <div class="card">
      <h2>Run history</h2>
      {% for row in run_rows %}
        <div class="run">
          <div class="run-head">
            <div>
              <a class="run-title" href="{{ url_for('test_run_details', run_id=row.run.id) }}">{{ row.run.name }}</a>
              <div class="muted">
                {{ row.run.execution_type }} · {{ row.run.preset }}{% if row.run.environment %} · {{ row.run.environment }}{% endif %}
                {% if row.run.release %} · Release {{ row.run.release.version }}{% endif %}
              </div>
            </div>
            <strong>{{ row.summary.progress }}%</strong>
          </div>
          <div class="summary">
            <span class="pill">{{ row.summary.executed }}/{{ row.summary.total }} executed</span>
            <span class="pill pass">{{ row.summary.passed }} passed</span>
            <span class="pill fail">{{ row.summary.failed }} failed</span>
            <span class="pill">{{ row.summary.not_run }} not run</span>
          </div>
        </div>
      {% else %}<div class="empty">No structured test runs yet.</div>{% endfor %}
    </div>

    <aside class="card">
      <h2>Create test run</h2>
      <form method="post" action="{{ url_for('create_test_run') }}">
        <label>Name</label>
        <input name="name" required placeholder="Release 1.0.0 - Regression">
        <label>Preset</label>
        <select id="runPreset" name="preset">
          <option>Custom</option>
          <option>Smoke</option>
          <option>Regression</option>
          <option>Full Release</option>
        </select>
        <div class="muted">Smoke follows @smoke BDD tags. Regression and Full Release use imported BDD suite tags.</div>
        <label>Release</label>
        <select name="release_id">
          <option value="">No release</option>
          {% for release in releases %}
            <option value="{{ release.id }}" {% if selected_release_id == release.id %}selected{% endif %}>{{ release.version }}{% if release.environment %} · {{ release.environment }}{% endif %}</option>
          {% endfor %}
        </select>
        <label>Environment</label>
        <input name="environment" placeholder="Staging">
        <label>Execution type</label>
        <select id="executionType" name="execution_type"><option>Manual</option><option>Automated</option></select>
        <label>Test cases</label>
        <div class="case-tools">
          <input id="runCaseSearch" type="search" placeholder="Search ID, title or feature...">
          <button class="button" type="button" onclick="setVisibleCases(true)">Select visible</button>
          <button class="button" type="button" onclick="setVisibleCases(false)">Clear visible</button>
        </div>
        <div id="runCaseList" class="case-list">
          {% for case in cases %}
            <label class="case-option" data-search="{{ (case.case_key ~ ' ' ~ case.title ~ ' ' ~ case.feature_name)|lower }}" data-suites="{{ case.suite_tags|lower }}">
              <input type="checkbox" name="case_ids" value="{{ case.id }}">
              <span><strong>{{ case.case_key }} — {{ case.title }}</strong>{{ case.feature_name }} · {{ case.type }}{% if case.suite_tags %} · {{ case.suite_tags }}{% endif %}</span>
            </label>
          {% else %}<div class="empty">Create test cases first.</div>{% endfor %}
        </div>
        <button class="primary" style="margin-top:14px" type="submit">Create test run</button>
      </form>
    </aside>
  </section>
</main>
<script>
const runCaseSearch=document.getElementById('runCaseSearch');
const runPreset=document.getElementById('runPreset');
const executionType=document.getElementById('executionType');

function applyPreset(){
  const preset=runPreset.value;
  if(preset==='Custom') return;

  const tag={
    'Smoke':'smoke',
    'Regression':'regression',
    'Full Release':'release'
  }[preset];

  executionType.value='Automated';
  document.querySelectorAll('.case-option').forEach(item=>{
    const suites=(item.dataset.suites || '').split(',').map(value=>value.trim());
    item.querySelector('input[type="checkbox"]').checked=suites.includes(tag);
  });
}

runPreset.addEventListener('change',applyPreset);

runCaseSearch.addEventListener('input',()=>{
  const query=runCaseSearch.value.trim().toLowerCase();
  document.querySelectorAll('.case-option').forEach(item=>{
    item.style.display=!query || item.dataset.search.includes(query)?'flex':'none';
  });
});
function setVisibleCases(checked){
  document.querySelectorAll('.case-option').forEach(item=>{
    if(item.style.display!=='none') item.querySelector('input[type="checkbox"]').checked=checked;
  });
}
</script>
</body>
</html>
"""


TEST_RUN_PAGE_HTML = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ run.name }} - Test Hub</title>
<style>
:root{--bg:#eef3fb;--surface:rgba(255,255,255,.95);--text:#111827;--muted:#6b7280;--border:#d7dfec;--accent:#2f66e8;font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
*{box-sizing:border-box}body{margin:0;min-height:100vh;color:var(--text);background:radial-gradient(circle at 8% 5%,rgba(98,134,255,.17),transparent 28%),radial-gradient(circle at 94% 16%,rgba(36,117,255,.11),transparent 24%),linear-gradient(180deg,#f8faff,#eef3fb)}
header{padding:16px 30px;background:rgba(20,42,82,.94);color:#fff}.brand{display:flex;align-items:center;gap:12px}.brand-icon{width:42px;height:42px;display:grid;place-items:center;border-radius:13px;background:linear-gradient(135deg,#6286ff,#1f63f2)}.brand strong{font-size:20px}.brand span{display:block;font-size:12px;opacity:.7}
.wrap{max-width:1220px;margin:0 auto;padding:32px 22px 50px}.top{display:flex;justify-content:space-between;gap:18px;align-items:flex-start;margin-bottom:20px}.top h1{margin:0;font-size:29px;color:#172b4d}.subtitle{margin-top:5px;color:var(--muted)}.actions{display:flex;gap:8px;flex-wrap:wrap}.button,button.primary{display:inline-block;padding:10px 14px;border:0;border-radius:10px;font:inherit;text-decoration:none;font-weight:750;cursor:pointer}.button{background:#eef2f7;color:#20324f}.primary{background:linear-gradient(90deg,#2f66e8,#2475ff);color:#fff;box-shadow:0 8px 18px rgba(37,99,235,.2)}button:disabled{opacity:.55;cursor:not-allowed}
.stats{display:grid;grid-template-columns:repeat(7,1fr);gap:11px;margin-bottom:20px}.stat{padding:15px;border:1px solid var(--border);border-radius:15px;background:var(--surface);box-shadow:0 10px 28px rgba(35,61,108,.06)}.stat strong{display:block;font-size:24px;color:#17325d}.stat span{display:block;margin-top:5px;font-size:12px;color:var(--muted);font-weight:650}
.card{padding:21px;border:1px solid var(--border);border-radius:18px;background:var(--surface);box-shadow:0 16px 42px rgba(35,61,108,.07)}.progress{height:10px;margin:12px 0 20px;border-radius:999px;background:#e7ecf4;overflow:hidden}.progress>div{height:100%;background:linear-gradient(90deg,#2f66e8,#2475ff)}
.run-row{display:grid;grid-template-columns:100px minmax(260px,1fr) 130px minmax(340px,1.1fr);gap:12px;align-items:center;padding:14px 0;border-top:1px solid #e7ebf2}.run-row:first-of-type{border-top:0}.badge{display:inline-block;width:max-content;padding:5px 8px;border-radius:999px;font-size:12px;font-weight:800}.Passed{background:#dcfce7;color:#166534}.Failed{background:#fee2e2;color:#991b1b}.Blocked{background:#fef3c7;color:#92400e}.Skipped{background:#e5e7eb;color:#4b5563}.NotRun{background:#edf1f7;color:#526174}
.case-link{color:#243854;text-decoration:none;font-weight:850}.case-link:hover{color:#2468e5}.muted{margin-top:4px;color:var(--muted);font-size:12px}.attempt-history{margin-top:8px}.attempt-history summary{cursor:pointer;font-size:12px;font-weight:800;color:#456080}.attempt-row{display:flex;gap:9px;flex-wrap:wrap;padding:7px 0;border-top:1px solid #edf0f5;font-size:12px;color:#65758a}.attempt-row:first-of-type{margin-top:6px}.attempt-status{font-weight:800}.attempt-build{color:#2468e5;text-decoration:none;font-weight:750}.result-form{display:flex;gap:6px;align-items:center;flex-wrap:wrap}.result-form input{flex:1;min-width:120px;height:37px;padding:0 9px;border:1px solid #ccd5e4;border-radius:9px;font:inherit}.result-form button{border:0;border-radius:8px;padding:8px 9px;font:inherit;font-size:12px;font-weight:800;cursor:pointer}.pass{background:#dcfce7;color:#166534}.fail{background:#fee2e2;color:#991b1b}.block{background:#fef3c7;color:#92400e}.skip{background:#e5e7eb;color:#4b5563}
@media(max-width:950px){.stats{grid-template-columns:repeat(3,1fr)}.run-row{grid-template-columns:90px 1fr}.result-form{grid-column:1/-1}.run-row>.muted{grid-column:2}}
@media(max-width:560px){header{padding:13px 16px}.wrap{padding:22px 14px}.top{flex-direction:column}.stats{grid-template-columns:1fr 1fr}}
</style>
</head>
<body>
<header><div class="brand"><div class="brand-icon">🧪</div><div><strong>Test Hub</strong><span>QA test case management</span></div></div></header>
<main class="wrap">
  <div class="top">
    <div>
      <h1>{{ run.name }}</h1>
      <div class="subtitle">
        {{ run.execution_type }} · {{ run.preset }}{% if run.environment %} · {{ run.environment }}{% endif %}
        {% if run.release %} · Release {{ run.release.version }}{% endif %}
        · <strong>{{ run.execution_status }}</strong>
      </div>
    </div>
    <div class="actions">
      {% if run.execution_type == 'Automated' %}
        <form method="post" action="{{ url_for('start_automated_test_run', run_id=run.id) }}">
          <button class="primary" type="submit" {% if run.execution_status in ['Queued', 'Running'] %}disabled{% endif %}>▶ Run with Playwright</button>
        </form>
      {% endif %}
      {% if run.release %}<a class="button" href="{{ url_for('release_details', release_id=run.release.id) }}">Release report</a>{% endif %}
      <a class="button" href="{{ url_for('test_runs') }}">All test runs</a>
    </div>
  </div>

  {% if run.runner_message or run.jenkins_build_url %}
    <section class="card" style="margin-bottom:18px;padding:14px 18px">
      <strong>Runner:</strong> {{ run.runner_message or 'Jenkins execution' }}
      {% if run.jenkins_build_number %} · Build #{{ run.jenkins_build_number }}{% endif %}
      {% if run.jenkins_build_url %} · <a href="{{ run.jenkins_build_url }}" target="_blank" rel="noopener">Open Jenkins build</a>
      {% elif run.jenkins_queue_url %} · <a href="{{ run.jenkins_queue_url }}" target="_blank" rel="noopener">Open Jenkins queue</a>{% endif %}
      {% if run.jenkins_report_url %} · <a href="{{ run.jenkins_report_url }}" target="_blank" rel="noopener">HTML report</a>{% endif %}
      {% if run.jenkins_artifacts_url %} · <a href="{{ run.jenkins_artifacts_url }}" target="_blank" rel="noopener">Artifacts</a>{% endif %}
    </section>
  {% endif %}

  <section class="stats">
    <div class="stat"><strong>{{ summary.total }}</strong><span>Tests</span></div>
    <div class="stat"><strong>{{ summary.executed }}</strong><span>Executed</span></div>
    <div class="stat"><strong>{{ summary.passed }}</strong><span>Passed</span></div>
    <div class="stat"><strong>{{ summary.failed }}</strong><span>Failed</span></div>
    <div class="stat"><strong>{{ summary.blocked }}</strong><span>Blocked</span></div>
    <div class="stat"><strong>{{ summary.skipped }}</strong><span>Skipped</span></div>
    <div class="stat"><strong>{{ summary.not_run }}</strong><span>Not Run</span></div>
  </section>

  <section class="card">
    <strong>Progress: {{ summary.executed }} / {{ summary.total }} ({{ summary.progress }}%)</strong>
    <div class="progress"><div style="width:{{ summary.progress }}%"></div></div>

    {% for row in summary.rows %}
      <div class="run-row">
        <span class="badge {% if row.status == 'Not Run' %}NotRun{% else %}{{ row.status }}{% endif %}">{{ row.status }}</span>
        <div>
          {% if row.item.test_case %}
            <a class="case-link" href="{{ url_for('test_case_details', case_key=row.item.test_case.case_key) }}">{{ row.item.case_key_snapshot }} — {{ row.item.case_title_snapshot }}</a>
          {% else %}
            <strong>{{ row.item.case_key_snapshot }} — {{ row.item.case_title_snapshot }}</strong>
          {% endif %}
          <div class="muted">{{ row.item.feature_snapshot }}</div>
          {% if row.result and row.result.notes %}<div class="muted">{{ row.result.notes }}</div>{% endif %}
          {% if row.result and row.result.error_message %}
            <details class="muted" style="margin-top:7px">
              <summary style="cursor:pointer;font-weight:750;color:#991b1b">Failure details</summary>
              <pre style="white-space:pre-wrap;overflow:auto;margin:7px 0 0">{{ row.result.error_message }}</pre>
            </details>
          {% endif %}
          {% if row.attempts|length > 1 %}
            <details class="attempt-history">
              <summary>{{ row.attempts|length }} execution attempts</summary>
              {% for attempt in row.attempts %}
                <div class="attempt-row">
                  <span>Attempt {{ loop.index }}</span>
                  <span class="attempt-status">{{ attempt.result }}</span>
                  {% if attempt.runner_build_url %}
                    <a class="attempt-build" href="{{ attempt.runner_build_url }}" target="_blank" rel="noopener">Build #{{ attempt.runner_build_number or '?' }}</a>
                  {% elif attempt.runner_build_number %}
                    <span>Build #{{ attempt.runner_build_number }}</span>
                  {% endif %}
                  {% if attempt.duration_ms is not none %}
                    <span>{% if attempt.duration_ms >= 1000 %}{{ '%.2f'|format(attempt.duration_ms / 1000) }} s{% else %}{{ attempt.duration_ms }} ms{% endif %}</span>
                  {% endif %}
                  <span>{{ attempt.executed_at.strftime('%d %b %Y %H:%M') }}</span>
                </div>
              {% endfor %}
            </details>
          {% endif %}
        </div>
        <div class="muted">
          {% if row.result %}
            {{ row.result.executed_at.strftime('%d %b %H:%M') }}
            {% if row.result.duration_ms is not none %}
              · {% if row.result.duration_ms >= 1000 %}{{ '%.2f'|format(row.result.duration_ms / 1000) }} s{% else %}{{ row.result.duration_ms }} ms{% endif %}
            {% endif %}
          {% else %}Waiting{% endif %}
        </div>
        {% if run.execution_type == 'Manual' %}
          <form class="result-form" method="post" action="{{ url_for('record_test_run_result', run_id=run.id, item_id=row.item.id) }}">
            <input name="notes" placeholder="Optional notes">
            <button class="pass" name="result" value="Passed">Pass</button>
            <button class="fail" name="result" value="Failed">Fail</button>
            <button class="block" name="result" value="Blocked">Block</button>
            <button class="skip" name="result" value="Skipped">Skip</button>
          </form>
        {% else %}
          <div class="muted">
            {% if row.status == 'Not Run' %}Waiting for Playwright{% else %}Reported by Playwright{% endif %}
          </div>
        {% endif %}
      </div>
    {% else %}
      <div class="muted">This run has no planned test cases.</div>
    {% endfor %}
  </section>
</main>
{% if run.execution_status in ['Queued', 'Running'] %}
<script>setTimeout(()=>window.location.reload(),5000);</script>
{% endif %}
</body>
</html>
"""


RELEASES_PAGE_HTML = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Releases - Test Hub</title>
<style>
:root{--bg:#eef3fb;--surface:rgba(255,255,255,.95);--text:#111827;--muted:#6b7280;--border:#d7dfec;--accent:#2f66e8;--accent2:#2475ff;font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
*{box-sizing:border-box}body{margin:0;min-height:100vh;color:var(--text);background:radial-gradient(circle at 8% 5%,rgba(98,134,255,.17),transparent 28%),radial-gradient(circle at 94% 16%,rgba(36,117,255,.11),transparent 24%),linear-gradient(180deg,#f8faff,#eef3fb)}
header{display:flex;align-items:center;justify-content:space-between;padding:16px 30px;background:rgba(20,42,82,.94);color:#fff;box-shadow:0 10px 30px rgba(24,47,90,.14)}
.brand{display:flex;align-items:center;gap:12px}.brand-icon{width:42px;height:42px;display:grid;place-items:center;border-radius:13px;background:linear-gradient(135deg,#6286ff,#1f63f2);box-shadow:0 8px 22px rgba(37,99,235,.3)}.brand strong{font-size:20px}.brand span{display:block;font-size:12px;opacity:.7;margin-top:2px}
.wrap{max-width:1180px;margin:0 auto;padding:32px 22px 50px}.top{display:flex;align-items:flex-start;justify-content:space-between;gap:20px;margin-bottom:20px}.top h1{margin:0;font-size:30px;color:#172b4d;letter-spacing:-.6px}.subtitle{margin-top:5px;color:var(--muted)}
.grid{display:grid;grid-template-columns:1.35fr .65fr;gap:18px;align-items:start}.card{padding:21px;border:1px solid var(--border);border-radius:18px;background:var(--surface);box-shadow:0 16px 42px rgba(35,61,108,.07)}.card h2{margin:0 0 14px;font-size:19px;color:#172b4d}
.button,button{display:inline-block;border:0;border-radius:10px;padding:10px 14px;text-decoration:none;font:inherit;font-weight:750;cursor:pointer}.button{background:#eef2f7;color:#20324f}.primary{background:linear-gradient(90deg,#2f66e8,#2475ff);color:#fff;box-shadow:0 8px 18px rgba(37,99,235,.2)}
.release{padding:16px 0;border-top:1px solid #e7ebf2}.release:first-of-type{border-top:0}.release-head{display:flex;align-items:flex-start;justify-content:space-between;gap:14px}.release-title{font-weight:850;color:#172b4d;text-decoration:none;font-size:16px}.release-title:hover{color:#2468e5}.release-meta{margin-top:5px;color:var(--muted);font-size:13px}.summary{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}.pill{padding:4px 8px;border-radius:999px;background:#eef2f7;color:#526174;font-size:12px;font-weight:700}.pass{background:#dcfce7;color:#166534}.fail{background:#fee2e2;color:#991b1b}
label{display:block;margin:13px 0 6px;font-size:12px;font-weight:800;color:#41526c}input,textarea{width:100%;border:1px solid #ccd5e4;border-radius:11px;background:#fff;color:var(--text);font:inherit;outline:none}input{height:45px;padding:0 12px}textarea{min-height:90px;padding:10px 12px;resize:vertical}input:focus,textarea:focus{border-color:#3b73ef;box-shadow:0 0 0 4px rgba(59,115,239,.12)}.empty{padding:30px;text-align:center;color:var(--muted)}
@media(max-width:800px){header{padding:13px 16px}.wrap{padding:22px 14px}.grid{grid-template-columns:1fr}.top{flex-direction:column}}
</style>
</head>
<body>
<header><div class="brand"><div class="brand-icon">🧪</div><div><strong>Test Hub</strong><span>QA test case management</span></div></div></header>
<main class="wrap">
  <div class="top">
    <div><h1>Releases</h1><div class="subtitle">Stored QA results and release reports.</div></div>
    <div style="display:flex;gap:8px;flex-wrap:wrap"><a class="button" href="{{ url_for('test_runs') }}">Test Runs</a><a class="button" href="{{ url_for('index') }}">All test cases</a></div>
  </div>

  <section class="grid">
    <div class="card">
      <h2>Release history</h2>
      {% for item in release_rows %}
        <div class="release">
          <div class="release-head">
            <div>
              <a class="release-title" href="{{ url_for('release_details', release_id=item.release.id) }}">{{ item.release.version }}</a>
              <div class="release-meta">
                {% if item.release.release_date %}{{ item.release.release_date.strftime('%d %b %Y') }}{% else %}No release date{% endif %}
                {% if item.release.environment %} · {{ item.release.environment }}{% endif %}
                {% if item.release.git_commit %} · {{ item.release.git_commit }}{% endif %}
              </div>
            </div>
            <strong>{{ item.stats.pass_rate }}%</strong>
          </div>
          <div class="summary">
            <span class="pill">{{ item.stats.total }} tests</span>
            <span class="pill pass">{{ item.stats.passed }} passed</span>
            <span class="pill fail">{{ item.stats.failed }} failed</span>
            <span class="pill">{{ item.stats.blocked }} blocked</span>
          </div>
        </div>
      {% else %}
        <div class="empty">No releases yet. Create the first one on the right.</div>
      {% endfor %}
    </div>

    <aside class="card">
      <h2>Create release</h2>
      <form method="post" action="{{ url_for('create_release') }}">
        <label>Version / Name</label>
        <input name="version" required placeholder="1.5.0">
        <label>Release date</label>
        <input name="release_date" type="date">
        <label>Environment</label>
        <input name="environment" placeholder="Production">
        <label>Git commit</label>
        <input name="git_commit" placeholder="a81d934">
        <label>Notes</label>
        <textarea name="notes" placeholder="Optional release notes"></textarea>
        <button class="primary" style="margin-top:14px" type="submit">Create release</button>
      </form>
    </aside>
  </section>
</main>
</body>
</html>
"""


RELEASE_PAGE_HTML = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ release.version }} - Test Hub</title>
<style>
:root{--bg:#eef3fb;--surface:rgba(255,255,255,.95);--text:#111827;--muted:#6b7280;--border:#d7dfec;--accent:#2f66e8;font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
*{box-sizing:border-box}body{margin:0;min-height:100vh;color:var(--text);background:radial-gradient(circle at 8% 5%,rgba(98,134,255,.17),transparent 28%),radial-gradient(circle at 94% 16%,rgba(36,117,255,.11),transparent 24%),linear-gradient(180deg,#f8faff,#eef3fb)}
header{padding:16px 30px;background:rgba(20,42,82,.94);color:#fff;box-shadow:0 10px 30px rgba(24,47,90,.14)}.brand{display:flex;align-items:center;gap:12px}.brand-icon{width:42px;height:42px;display:grid;place-items:center;border-radius:13px;background:linear-gradient(135deg,#6286ff,#1f63f2);box-shadow:0 8px 22px rgba(37,99,235,.3)}.brand strong{font-size:20px}.brand span{display:block;font-size:12px;opacity:.7}
.wrap{max-width:1120px;margin:0 auto;padding:32px 22px 50px}.top{display:flex;justify-content:space-between;align-items:flex-start;gap:18px;margin-bottom:20px}.top h1{margin:0;font-size:30px;color:#172b4d}.subtitle{margin-top:6px;color:var(--muted)}.actions{display:flex;gap:8px;flex-wrap:wrap}.button{display:inline-block;padding:10px 14px;border-radius:10px;background:#eef2f7;color:#20324f;text-decoration:none;font-weight:750}
.stats{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:20px}.stat{padding:16px;border:1px solid var(--border);border-radius:15px;background:var(--surface);box-shadow:0 10px 28px rgba(35,61,108,.06)}.stat strong{display:block;font-size:26px;color:#17325d}.stat span{display:block;margin-top:5px;font-size:12px;font-weight:650;color:var(--muted)}
.card{margin-top:18px;padding:21px;border:1px solid var(--border);border-radius:18px;background:var(--surface);box-shadow:0 16px 42px rgba(35,61,108,.07)}.card h2{margin:0 0 14px;font-size:19px;color:#172b4d}
.info{display:flex;gap:18px;flex-wrap:wrap;color:#536277;font-size:13px}.info strong{color:#243854}.feature-row,.result-row{display:grid;gap:12px;align-items:center;padding:12px 0;border-top:1px solid #e7ebf2}.feature-row{grid-template-columns:1fr 80px 80px 80px 90px}.result-row{grid-template-columns:100px 1fr 150px}.feature-row:first-of-type,.result-row:first-of-type{border-top:0}.badge{display:inline-block;width:max-content;padding:5px 8px;border-radius:999px;font-size:12px;font-weight:800}.Passed{background:#dcfce7;color:#166534}.Failed{background:#fee2e2;color:#991b1b}.Blocked{background:#fef3c7;color:#92400e}.Skipped{background:#e5e7eb;color:#4b5563}.case-link{color:#243854;text-decoration:none;font-weight:800}.case-link:hover{color:#2468e5}.muted{color:var(--muted);font-size:12px}.empty{padding:28px;text-align:center;color:var(--muted)}
@media(max-width:760px){header{padding:13px 16px}.wrap{padding:22px 14px}.top{flex-direction:column}.stats{grid-template-columns:1fr 1fr}.feature-row{grid-template-columns:1fr 65px 65px}.feature-row>*:nth-child(n+4){display:none}.result-row{grid-template-columns:90px 1fr}.result-row .muted{grid-column:2}}
</style>
</head>
<body>
<header><div class="brand"><div class="brand-icon">🧪</div><div><strong>Test Hub</strong><span>QA test case management</span></div></div></header>
<main class="wrap">
  <div class="top">
    <div>
      <h1>Release {{ release.version }}</h1>
      <div class="subtitle">Stored QA release report</div>
    </div>
    <div class="actions"><a class="button" href="{{ url_for('test_runs', release_id=release.id) }}">Create test run</a><a class="button" href="{{ url_for('releases') }}">All releases</a><a class="button" href="{{ url_for('index') }}">Test cases</a></div>
  </div>

  <section class="stats">
    <div class="stat"><strong>{{ report.total }}</strong><span>Final test statuses</span></div>
    <div class="stat"><strong>{{ report.passed }}</strong><span>Passed</span></div>
    <div class="stat"><strong>{{ report.failed }}</strong><span>Failed</span></div>
    <div class="stat"><strong>{{ report.blocked }}</strong><span>Blocked</span></div>
    <div class="stat"><strong>{{ report.pass_rate }}%</strong><span>Pass rate</span></div>
  </section>

  <section class="card">
    <h2>Release information</h2>
    <div class="info">
      <span><strong>Date:</strong> {% if release.release_date %}{{ release.release_date.strftime('%d %b %Y') }}{% else %}—{% endif %}</span>
      <span><strong>Environment:</strong> {{ release.environment or '—' }}</span>
      <span><strong>Git commit:</strong> {{ release.git_commit or '—' }}</span>
      <span><strong>Executions:</strong> {{ execution_count }}</span>
    </div>
    {% if release.notes %}<div class="info" style="margin-top:12px"><span><strong>Notes:</strong> {{ release.notes }}</span></div>{% endif %}
  </section>

  <section class="card">
    <h2>By feature</h2>
    {% for feature in report.features %}
      <div class="feature-row">
        <strong>{{ feature.feature }}</strong>
        <span>{{ feature.total }} total</span>
        <span>{{ feature.passed }} passed</span>
        <span>{{ feature.failed }} failed</span>
        <span>{{ feature.pass_rate }}%</span>
      </div>
    {% else %}<div class="empty">No release results recorded yet.</div>{% endfor %}
  </section>

  <section class="card">
    <h2>Test runs</h2>
    {% for run in structured_runs %}
      {% set run_stats = run_summaries.get(run.id) %}
      <div class="result-row">
        <span class="badge {% if run_stats.failed %}Failed{% elif run_stats.not_run %}Blocked{% else %}Passed{% endif %}">
          {{ run_stats.progress }}%
        </span>
        <div>
          <a class="case-link" href="{{ url_for('test_run_details', run_id=run.id) }}">{{ run.name }}</a>
          <div class="muted">{{ run.execution_type }}{% if run.environment %} · {{ run.environment }}{% endif %}</div>
        </div>
        <div class="muted">{{ run_stats.executed }}/{{ run_stats.total }} executed</div>
      </div>
    {% else %}
      <div class="empty">No structured test runs for this release yet.</div>
    {% endfor %}
  </section>

  <section class="card">
    <h2>Final test results</h2>
    {% for result in report.final_results %}
      <div class="result-row">
        <span class="badge {{ result.result }}">{{ result.result }}</span>
        <div>
          {% if result.test_case %}
            <a class="case-link" href="{{ url_for('test_case_details', case_key=result.test_case.case_key) }}">{{ result.case_key_snapshot }} — {{ result.case_title_snapshot }}</a>
          {% else %}
            <strong>{{ result.case_key_snapshot }} — {{ result.case_title_snapshot }}</strong>
          {% endif %}
          <div class="muted">{{ result.feature_snapshot }}{% if result.test_run.environment %} · {{ result.test_run.environment }}{% endif %}</div>
        </div>
        <div class="muted">{{ result.executed_at.strftime('%d %b %Y %H:%M') }}</div>
      </div>
    {% else %}<div class="empty">No test results have been assigned to this release yet.</div>{% endfor %}
  </section>
</main>
</body>
</html>
"""


CASE_PAGE_HTML = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ case.case_key }} - Test Hub</title>
<style>
:root{--bg:#eef3fb;--surface:rgba(255,255,255,.95);--text:#111827;--muted:#6b7280;--border:#d7dfec;--accent:#2f66e8;--accent2:#2475ff;--danger:#b42318;font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
*{box-sizing:border-box}body{margin:0;min-height:100vh;color:var(--text);background:radial-gradient(circle at 8% 5%,rgba(98,134,255,.17),transparent 28%),radial-gradient(circle at 94% 16%,rgba(36,117,255,.11),transparent 24%),linear-gradient(180deg,#f8faff,#eef3fb)}
header{display:flex;align-items:center;justify-content:space-between;padding:16px 30px;background:rgba(20,42,82,.94);color:#fff;box-shadow:0 10px 30px rgba(24,47,90,.14)}
.brand{display:flex;align-items:center;gap:12px}.brand-icon{width:42px;height:42px;display:grid;place-items:center;border-radius:13px;background:linear-gradient(135deg,#6286ff,#1f63f2);box-shadow:0 8px 22px rgba(37,99,235,.3)}.brand strong{font-size:20px}.brand span{display:block;font-size:12px;opacity:.7;margin-top:2px}
.wrap{max-width:1100px;margin:0 auto;padding:32px 22px 50px}.top{display:flex;justify-content:space-between;gap:18px;align-items:flex-start;margin-bottom:20px}.top h1{margin:0;font-size:29px;letter-spacing:-.55px;color:#172b4d}.subtitle{margin-top:5px;color:var(--muted)}
.actions{display:flex;gap:9px;flex-wrap:wrap}.button,button{display:inline-block;border:0;border-radius:10px;padding:10px 14px;text-decoration:none;font:inherit;font-weight:750;cursor:pointer}.button{background:#eef2f7;color:#20324f}.primary{background:linear-gradient(90deg,#2f66e8,#2475ff);color:#fff;box-shadow:0 8px 18px rgba(37,99,235,.2)}
.stats{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:20px}.stat{padding:16px;border:1px solid var(--border);border-radius:15px;background:var(--surface);box-shadow:0 10px 28px rgba(35,61,108,.06)}.stat strong{display:block;font-size:26px;color:#17325d}.stat span{display:block;margin-top:5px;font-size:12px;font-weight:650;color:var(--muted)}
.grid{display:grid;grid-template-columns:1.25fr .75fr;gap:18px}.card{padding:21px;border:1px solid var(--border);border-radius:18px;background:var(--surface);box-shadow:0 16px 42px rgba(35,61,108,.07)}.card h2{margin:0 0 14px;font-size:19px;color:#172b4d}
.meta{display:flex;gap:7px;flex-wrap:wrap;margin-bottom:15px}.pill{font-size:12px;padding:4px 8px;border-radius:999px;background:#eef2f7;color:#526174;font-weight:650}.jira{color:#2468e5;text-decoration:none;font-weight:800;padding:3px 7px;border-radius:7px;background:#edf4ff}
.details{margin-top:9px;color:#607088;font-size:14px;line-height:1.5;white-space:pre-wrap}.details strong{color:#354963}
label{display:block;margin:13px 0 6px;font-size:12px;font-weight:800;color:#41526c}select,input,textarea{width:100%;border:1px solid #ccd5e4;border-radius:11px;background:#fff;color:var(--text);font:inherit;outline:none}select,input{height:45px;padding:0 12px}textarea{min-height:90px;padding:10px 12px;resize:vertical}select:focus,input:focus,textarea:focus{border-color:#3b73ef;box-shadow:0 0 0 4px rgba(59,115,239,.12)}
.history{margin-top:20px}.result-row{display:grid;grid-template-columns:105px 1fr 120px 150px;gap:12px;align-items:center;padding:13px 0;border-top:1px solid #e7ebf2}.result-row:first-of-type{border-top:0}.result-badge{display:inline-block;width:max-content;padding:5px 8px;border-radius:999px;font-size:12px;font-weight:800}.Passed{background:#dcfce7;color:#166534}.Failed{background:#fee2e2;color:#991b1b}.Blocked{background:#fef3c7;color:#92400e}.Skipped{background:#e5e7eb;color:#4b5563}.result-main{font-size:13px;color:#526174}.result-main strong{display:block;color:#243854;font-size:14px}.result-date{font-size:12px;color:var(--muted)}.empty{padding:28px;text-align:center;color:var(--muted)}
@media(max-width:780px){header{padding:13px 16px}.wrap{padding:22px 14px}.top{flex-direction:column}.stats{grid-template-columns:1fr 1fr}.grid{grid-template-columns:1fr}.result-row{grid-template-columns:90px 1fr}.result-date{grid-column:2}}
</style>
</head>
<body>
<header><div class="brand"><div class="brand-icon">🧪</div><div><strong>Test Hub</strong><span>QA test case management</span></div></div></header>
<main class="wrap">
  <div class="top">
    <div><h1>{{ case.case_key }} — {{ case.title }}</h1><div class="subtitle">{{ case.feature_name }} · execution history</div></div>
    <div class="actions">
      <a class="button" href="{{ url_for('index') }}">All test cases</a>
      <a class="button" href="{{ url_for('test_runs') }}">Test Runs</a>
      <a class="button" href="{{ url_for('releases') }}">Releases</a>
      <a class="button" href="{{ url_for('edit_case', case_key=case.case_key) }}">Edit test case</a>
    </div>
  </div>

  <section class="stats">
    <div class="stat"><strong>{{ stats.total }}</strong><span>Total executions</span></div>
    <div class="stat"><strong>{{ stats.passed }}</strong><span>Passed</span></div>
    <div class="stat"><strong>{{ stats.failed }}</strong><span>Failed</span></div>
    <div class="stat"><strong>{{ stats.blocked }}</strong><span>Blocked</span></div>
    <div class="stat"><strong>{{ stats.pass_rate }}%</strong><span>Pass rate</span></div>
  </section>

  <section class="grid">
    <div class="card">
      <h2>Test case</h2>
      <div class="meta">
        <span class="pill">{{ case.type }}</span><span class="pill">{{ case.priority }}</span><span class="pill">{{ case.status }}</span>
        {% for jira_key in case.jira_keys %}<a class="jira" href="{{ url_for('jira_story_cases', jira_key=jira_key) }}">{{ jira_key }}</a>{% endfor %}
      </div>
      {% if case.preconditions %}<div class="details"><strong>Preconditions:</strong> {{ case.preconditions }}</div>{% endif %}
      <div class="details"><strong>Steps:</strong>
{% for step in case.steps %}{{ loop.index }}. {{ step.action }}{% if not loop.last %}
{% endif %}{% endfor %}</div>
      <div class="details"><strong>Expected result:</strong> {{ case.expected_result }}</div>
    </div>

    <aside class="card">
      <h2>Record result</h2>
      <form method="post" action="{{ url_for('record_test_result', case_key=case.case_key) }}">
        <label>Result</label>
        <select name="result" required>
          <option>Passed</option><option>Failed</option><option>Blocked</option><option>Skipped</option>
        </select>
        <label>Release</label>
        <select name="release_id">
          <option value="">No release / standalone run</option>
          {% for release in releases %}
            <option value="{{ release.id }}">{{ release.version }}{% if release.environment %} · {{ release.environment }}{% endif %}</option>
          {% endfor %}
        </select>
        <label>Environment</label>
        <input name="environment" placeholder="Staging, Production, Local...">
        <label>Notes</label>
        <textarea name="notes" placeholder="Optional execution notes"></textarea>
        <button class="primary" style="margin-top:14px" type="submit">Record result</button>
      </form>
    </aside>
  </section>

  <section class="card history">
    <h2>Execution history</h2>
    {% for result in results %}
      <div class="result-row">
        <span class="result-badge {{ result.result }}">{{ result.result }}</span>
        <div class="result-main">
          <strong>{{ result.case_key_snapshot }} — {{ result.case_title_snapshot }}</strong>
          {{ result.test_run.name }}{% if result.test_run.environment %} · {{ result.test_run.environment }}{% endif %}
          {% if result.test_run.release %} · <a href="{{ url_for('release_details', release_id=result.test_run.release.id) }}" style="color:#2468e5;text-decoration:none;font-weight:750">{{ result.test_run.release.version }}</a>{% endif %}
          {% if result.notes %}<div>{{ result.notes }}</div>{% endif %}
        </div>
        <div class="result-date">
          {{ result.test_run.execution_type }}
          {% if result.runner_build_url %} · <a href="{{ result.runner_build_url }}" target="_blank" rel="noopener">Build #{{ result.runner_build_number or '?' }}</a>{% endif %}
        </div>
        <div class="result-date">
          {{ result.executed_at.strftime('%d %b %Y %H:%M') }}
          {% if result.duration_ms is not none %} · {% if result.duration_ms >= 1000 %}{{ '%.2f'|format(result.duration_ms / 1000) }} s{% else %}{{ result.duration_ms }} ms{% endif %}{% endif %}
        </div>
      </div>
    {% else %}
      <div class="empty">No execution history yet. Record the first result above.</div>
    {% endfor %}
  </section>
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


@app.get("/test-runs")
def test_runs():
    all_runs = db.session.scalars(
        db.select(TestRun).order_by(TestRun.created_at.desc(), TestRun.id.desc())
    ).all()
    all_runs = [run for run in all_runs if run.items]
    all_releases = db.session.scalars(
        db.select(Release).order_by(Release.release_date.desc(), Release.id.desc())
    ).all()
    cases = db.session.scalars(
        db.select(TestCase).order_by(TestCase.feature, TestCase.case_key)
    ).all()

    selected_release_id = None
    raw_release_id = request.args.get("release_id", "").strip()
    if raw_release_id.isdigit():
        selected_release_id = int(raw_release_id)

    return render_template_string(
        TEST_RUNS_PAGE_HTML,
        run_rows=[{"run": run, "summary": test_run_summary(run)} for run in all_runs],
        releases=all_releases,
        cases=cases,
        selected_release_id=selected_release_id,
    )


@app.post("/test-runs")
def create_test_run():
    name = request.form.get("name", "").strip()
    preset = request.form.get("preset", "Custom").strip()
    release_id_value = request.form.get("release_id", "").strip()
    environment = request.form.get("environment", "").strip()
    execution_type = request.form.get("execution_type", "Manual").strip()
    case_id_values = request.form.getlist("case_ids")

    if not name:
        return "Test run name is required.", 400
    if preset not in RUN_PRESETS:
        return "Invalid test run preset.", 400
    if execution_type not in TYPES:
        return "Invalid execution type.", 400

    release = None
    if release_id_value:
        try:
            release = db.session.get(Release, int(release_id_value))
        except ValueError:
            return "Invalid release.", 400
        if release is None:
            return "Release not found.", 404

    if preset == "Custom":
        if not case_id_values:
            return "Select at least one test case.", 400

        case_ids = []
        for raw_id in case_id_values:
            try:
                case_ids.append(int(raw_id))
            except ValueError:
                return "Invalid test case selection.", 400

        cases = db.session.scalars(
            db.select(TestCase)
            .where(TestCase.id.in_(case_ids))
            .order_by(TestCase.feature, TestCase.case_key)
        ).all()
        if len(cases) != len(set(case_ids)):
            return "One or more selected test cases no longer exist.", 400
    else:
        preset_tag = {
            "Smoke": "smoke",
            "Regression": "regression",
            "Full Release": "release",
        }[preset]
        all_cases = db.session.scalars(
            db.select(TestCase).order_by(TestCase.feature, TestCase.case_key)
        ).all()
        cases = [
            case for case in all_cases
            if case.type == "Automated" and preset_tag in case.suite_tag_list
        ]
        execution_type = "Automated"
        if not cases:
            return (
                f"No Automated test cases are tagged for the {preset} preset. "
                "Refresh the BDD import with --update-existing."
            ), 400

    run = TestRun(
        release=release,
        name=name,
        preset=preset,
        execution_type=execution_type,
        environment=environment or (release.environment if release else ""),
        started_at=datetime.now(timezone.utc),
    )
    run.items = [
        TestRunItem(
            test_case=case,
            position=index,
            case_key_snapshot=case.case_key,
            case_title_snapshot=case.title,
            feature_snapshot=case.feature_name,
        )
        for index, case in enumerate(cases, start=1)
    ]
    db.session.add(run)
    db.session.commit()
    return redirect(url_for("test_run_details", run_id=run.id))


@app.post("/test-runs/<int:run_id>/start")
def start_automated_test_run(run_id):
    run = db.session.get(TestRun, run_id)
    if run is None:
        return "Test run not found.", 404
    if run.execution_type != "Automated":
        return "Only Automated test runs can be started with Playwright.", 400
    if not run.items:
        return "This test run has no planned test cases.", 400

    run.runner_message = ""
    run.jenkins_queue_url = ""
    run.jenkins_build_number = ""
    run.jenkins_build_url = ""
    run.jenkins_report_url = ""
    run.jenkins_artifacts_url = ""
    run.finished_at = None

    try:
        queue_url = trigger_jenkins_test_run(run)
    except RuntimeError as exc:
        run.execution_status = "Error"
        run.runner_message = str(exc)
        db.session.commit()
        return redirect(url_for("test_run_details", run_id=run.id))

    run.execution_status = "Queued"
    run.jenkins_queue_url = queue_url or ""
    run.runner_message = "Jenkins build queued successfully."
    db.session.commit()
    return redirect(url_for("test_run_details", run_id=run.id))


@app.get("/test-runs/<int:run_id>")
def test_run_details(run_id):
    run = db.session.get(TestRun, run_id)
    if run is None:
        return "Test run not found.", 404

    return render_template_string(
        TEST_RUN_PAGE_HTML,
        run=run,
        summary=test_run_summary(run),
    )


@app.post("/test-runs/<int:run_id>/items/<int:item_id>/results")
def record_test_run_result(run_id, item_id):
    run = db.session.get(TestRun, run_id)
    if run is None:
        return "Test run not found.", 404

    item = db.session.get(TestRunItem, item_id)
    if item is None or item.test_run_id != run.id:
        return "Test run item not found.", 404

    result_value = request.form.get("result", "").strip()
    notes = request.form.get("notes", "").strip()
    if result_value not in RESULT_STATUSES:
        return "Invalid execution result.", 400

    executed_at = datetime.now(timezone.utc)
    result = TestResult(
        test_run=run,
        test_case=item.test_case,
        result=result_value,
        executed_at=executed_at,
        notes=notes,
        case_key_snapshot=item.case_key_snapshot,
        case_title_snapshot=item.case_title_snapshot,
        feature_snapshot=item.feature_snapshot,
    )
    db.session.add(result)
    db.session.flush()

    summary = test_run_summary(run)
    if summary["not_run"] == 0:
        run.execution_status = "Completed"
        run.finished_at = executed_at
    else:
        run.execution_status = "Running"
        run.finished_at = None
    db.session.commit()
    return redirect(url_for("test_run_details", run_id=run.id))


@app.get("/releases")
def releases():
    all_releases = db.session.scalars(
        db.select(Release).order_by(Release.release_date.desc(), Release.id.desc())
    ).all()
    release_rows = [
        {"release": release, "stats": release_report_stats(release)}
        for release in all_releases
    ]
    return render_template_string(
        RELEASES_PAGE_HTML,
        release_rows=release_rows,
    )


@app.post("/releases")
def create_release():
    version = request.form.get("version", "").strip()
    release_date_value = request.form.get("release_date", "").strip()
    environment = request.form.get("environment", "").strip()
    git_commit = request.form.get("git_commit", "").strip()
    notes = request.form.get("notes", "").strip()

    if not version:
        return "Release version/name is required.", 400

    existing = db.session.scalar(
        db.select(Release.id).where(Release.version == version)
    )
    if existing is not None:
        return f"Release {version} already exists.", 400

    release_date = None
    if release_date_value:
        try:
            release_date = datetime.strptime(release_date_value, "%Y-%m-%d").date()
        except ValueError:
            return "Invalid release date.", 400

    release = Release(
        version=version,
        release_date=release_date,
        environment=environment,
        git_commit=git_commit,
        notes=notes,
    )
    db.session.add(release)
    db.session.commit()
    return redirect(url_for("release_details", release_id=release.id))


@app.get("/releases/<int:release_id>")
def release_details(release_id):
    release = db.session.get(Release, release_id)
    if release is None:
        return "Release not found.", 404

    execution_count = db.session.scalar(
        db.select(db.func.count(TestResult.id))
        .join(TestRun)
        .where(TestRun.release_id == release.id)
    ) or 0

    return render_template_string(
        RELEASE_PAGE_HTML,
        release=release,
        report=release_report_stats(release),
        execution_count=execution_count,
        structured_runs=[run for run in release.runs if run.items],
        run_summaries={
            run.id: test_run_summary(run)
            for run in release.runs
            if run.items
        },
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


@app.get("/test-cases/<case_key>")
def test_case_details(case_key):
    case = db.session.scalar(
        db.select(TestCase).where(TestCase.case_key == case_key)
    )
    if case is None:
        return "Test case not found.", 404

    results = db.session.scalars(
        db.select(TestResult)
        .where(TestResult.test_case_id == case.id)
        .order_by(TestResult.executed_at.desc())
    ).all()

    all_releases = db.session.scalars(
        db.select(Release).order_by(Release.release_date.desc(), Release.id.desc())
    ).all()

    return render_template_string(
        CASE_PAGE_HTML,
        case=case,
        results=results,
        stats=test_case_execution_stats(case),
        releases=all_releases,
    )


@app.post("/test-cases/<case_key>/results")
def record_test_result(case_key):
    case = db.session.scalar(
        db.select(TestCase).where(TestCase.case_key == case_key)
    )
    if case is None:
        return "Test case not found.", 404

    result_value = request.form.get("result", "").strip()
    release_id_value = request.form.get("release_id", "").strip()
    environment = request.form.get("environment", "").strip()
    notes = request.form.get("notes", "").strip()

    if result_value not in RESULT_STATUSES:
        return "Invalid execution result.", 400

    release = None
    if release_id_value:
        try:
            release = db.session.get(Release, int(release_id_value))
        except ValueError:
            return "Invalid release.", 400
        if release is None:
            return "Release not found.", 404

    executed_at = datetime.now(timezone.utc)
    test_run = TestRun(
        release=release,
        name=f"Manual execution — {case.case_key}",
        execution_type="Manual",
        environment=environment or (release.environment if release else ""),
        started_at=executed_at,
        finished_at=executed_at,
    )
    test_result = TestResult(
        test_run=test_run,
        test_case=case,
        result=result_value,
        executed_at=executed_at,
        notes=notes,
        case_key_snapshot=case.case_key,
        case_title_snapshot=case.title,
        feature_snapshot=case.feature_name,
    )

    db.session.add(test_result)
    db.session.commit()
    return redirect(url_for("test_case_details", case_key=case.case_key))


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


@app.post("/api/test-runs/<int:run_id>/results")
def api_record_test_run_results(run_id):
    if not test_hub_api_authorized():
        return jsonify({"error": "Unauthorized."}), 401

    run = db.session.get(TestRun, run_id)
    if run is None:
        return jsonify({"error": "Test run not found."}), 404

    payload = request.get_json(silent=True) or {}
    submitted = payload.get("results")
    if submitted is None:
        submitted = [payload]
    if not isinstance(submitted, list):
        return jsonify({"error": "results must be a list."}), 400

    recorded = []
    now = datetime.now(timezone.utc)

    for item_data in submitted:
        case_key = str(item_data.get("case_key", "")).strip().upper()
        result_value = str(item_data.get("result", "")).strip()
        if not case_key or result_value not in RESULT_STATUSES:
            return jsonify({"error": f"Invalid result payload for {case_key or 'unknown case'}."}), 400

        item = db.session.scalar(
            db.select(TestRunItem).where(
                TestRunItem.test_run_id == run.id,
                TestRunItem.case_key_snapshot == case_key,
            )
        )
        if item is None:
            return jsonify({"error": f"{case_key} is not part of this test run."}), 400

        duration_ms = item_data.get("duration_ms")
        if duration_ms is not None:
            try:
                duration_ms = max(0, int(duration_ms))
            except (TypeError, ValueError):
                duration_ms = None

        result = TestResult(
            test_run=run,
            test_case=item.test_case,
            result=result_value,
            executed_at=now,
            duration_ms=duration_ms,
            runner_build_number=str(item_data.get("build_number", "") or "").strip(),
            runner_build_url=str(item_data.get("build_url", "") or "").strip(),
            notes=str(item_data.get("notes", "") or ""),
            error_message=str(item_data.get("error_message", "") or ""),
            case_key_snapshot=item.case_key_snapshot,
            case_title_snapshot=item.case_title_snapshot,
            feature_snapshot=item.feature_snapshot,
        )
        db.session.add(result)
        recorded.append(case_key)

    run.execution_status = "Running"
    run.runner_message = f"Playwright reported {len(recorded)} result(s)."
    db.session.commit()
    return jsonify({"recorded": recorded, "summary": {
        key: value for key, value in test_run_summary(run).items() if key != "rows"
    }})


@app.post("/api/test-runs/<int:run_id>/finish")
def api_finish_test_run(run_id):
    if not test_hub_api_authorized():
        return jsonify({"error": "Unauthorized."}), 401

    run = db.session.get(TestRun, run_id)
    if run is None:
        return jsonify({"error": "Test run not found."}), 404

    payload = request.get_json(silent=True) or {}
    runner_status = str(payload.get("status", "Completed")).strip()
    if runner_status not in {"Completed", "Error"}:
        return jsonify({"error": "Invalid runner status."}), 400

    build_number = str(payload.get("build_number", "") or "").strip()
    build_url = str(payload.get("build_url", "") or "").strip().rstrip("/")

    run.execution_status = runner_status
    run.finished_at = datetime.now(timezone.utc)
    run.runner_message = str(payload.get("message", "") or "")
    run.jenkins_build_number = build_number

    if build_url:
        run.jenkins_build_url = f"{build_url}/"
        run.jenkins_report_url = f"{build_url}/artifact/report.html"
        run.jenkins_artifacts_url = f"{build_url}/artifact/"

    db.session.commit()

    summary = test_run_summary(run)
    return jsonify({
        "status": run.execution_status,
        "summary": {key: value for key, value in summary.items() if key != "rows"},
    })


@app.get("/api/test-runs")
def api_test_runs():
    runs = db.session.scalars(
        db.select(TestRun).order_by(TestRun.created_at.desc(), TestRun.id.desc())
    ).all()
    payload = []
    for run in runs:
        summary = test_run_summary(run)
        if not run.items:
            continue
        payload.append({
            "id": run.id,
            "name": run.name,
            "preset": run.preset,
            "release_id": run.release_id,
            "release": run.release.version if run.release else None,
            "execution_type": run.execution_type,
            "environment": run.environment,
            "execution_status": run.execution_status,
            "jenkins_queue_url": run.jenkins_queue_url,
            "jenkins_build_number": run.jenkins_build_number,
            "jenkins_build_url": run.jenkins_build_url,
            "jenkins_report_url": run.jenkins_report_url,
            "jenkins_artifacts_url": run.jenkins_artifacts_url,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            "summary": {
                key: value
                for key, value in summary.items()
                if key != "rows"
            },
        })
    return jsonify(payload)


@app.get("/api/releases")
def api_releases():
    all_releases = db.session.scalars(
        db.select(Release).order_by(Release.release_date.desc(), Release.id.desc())
    ).all()
    return jsonify([
        {
            "id": release.id,
            "version": release.version,
            "release_date": release.release_date.isoformat() if release.release_date else None,
            "environment": release.environment,
            "git_commit": release.git_commit,
            "notes": release.notes,
            "report": {
                key: value
                for key, value in release_report_stats(release).items()
                if key not in {"features", "final_results"}
            },
        }
        for release in all_releases
    ])


@app.get("/api/test-cases")
def api_test_cases():
    cases = db.session.scalars(db.select(TestCase).order_by(TestCase.id)).all()
    payload = []
    for case in cases:
        item = case.to_dict()
        item["execution_stats"] = test_case_execution_stats(case)
        payload.append(item)
    return jsonify(payload)


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
    if "suite_tags" not in columns:
        db.session.execute(text("ALTER TABLE test_cases ADD COLUMN suite_tags VARCHAR(250) DEFAULT '' NOT NULL"))
        db.session.commit()

    # Existing databases already have test_runs, so add the nullable release link once.
    inspector = inspect(db.engine)
    if "test_runs" in inspector.get_table_names():
        run_columns = {column["name"] for column in inspector.get_columns("test_runs")}
        if "release_id" not in run_columns:
            db.session.execute(text("ALTER TABLE test_runs ADD COLUMN release_id INTEGER"))
            db.session.commit()
        if "preset" not in run_columns:
            db.session.execute(text("ALTER TABLE test_runs ADD COLUMN preset VARCHAR(30) DEFAULT 'Custom' NOT NULL"))
            db.session.commit()
        if "execution_status" not in run_columns:
            db.session.execute(text("ALTER TABLE test_runs ADD COLUMN execution_status VARCHAR(20) DEFAULT 'Planned' NOT NULL"))
            db.session.commit()
        if "jenkins_queue_url" not in run_columns:
            db.session.execute(text("ALTER TABLE test_runs ADD COLUMN jenkins_queue_url VARCHAR(500) DEFAULT '' NOT NULL"))
            db.session.commit()
        if "runner_message" not in run_columns:
            db.session.execute(text("ALTER TABLE test_runs ADD COLUMN runner_message TEXT DEFAULT '' NOT NULL"))
            db.session.commit()
        if "jenkins_build_number" not in run_columns:
            db.session.execute(text("ALTER TABLE test_runs ADD COLUMN jenkins_build_number VARCHAR(50) DEFAULT '' NOT NULL"))
            db.session.commit()
        if "jenkins_build_url" not in run_columns:
            db.session.execute(text("ALTER TABLE test_runs ADD COLUMN jenkins_build_url VARCHAR(500) DEFAULT '' NOT NULL"))
            db.session.commit()
        if "jenkins_report_url" not in run_columns:
            db.session.execute(text("ALTER TABLE test_runs ADD COLUMN jenkins_report_url VARCHAR(500) DEFAULT '' NOT NULL"))
            db.session.commit()
        if "jenkins_artifacts_url" not in run_columns:
            db.session.execute(text("ALTER TABLE test_runs ADD COLUMN jenkins_artifacts_url VARCHAR(500) DEFAULT '' NOT NULL"))
            db.session.commit()

    inspector = inspect(db.engine)
    if "test_results" in inspector.get_table_names():
        result_columns = {column["name"] for column in inspector.get_columns("test_results")}
        if "runner_build_number" not in result_columns:
            db.session.execute(text("ALTER TABLE test_results ADD COLUMN runner_build_number VARCHAR(50) DEFAULT '' NOT NULL"))
            db.session.commit()
        if "runner_build_url" not in result_columns:
            db.session.execute(text("ALTER TABLE test_results ADD COLUMN runner_build_url VARCHAR(500) DEFAULT '' NOT NULL"))
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
