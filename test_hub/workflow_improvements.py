from functools import wraps
import subprocess


SUITE_TAGS = ("smoke", "regression", "release")


def _response_status(response):
    if isinstance(response, tuple) and len(response) > 1:
        try:
            return int(response[1])
        except (TypeError, ValueError):
            return 500
    return int(getattr(response, "status_code", 200) or 200)


def _selected_suite_tags(request):
    values = []
    for raw in request.form.getlist("suite_tags"):
        tag = str(raw or "").strip().lower()
        if tag in SUITE_TAGS and tag not in values:
            values.append(tag)
    return values


def _save_suite_tags(hub, case):
    if case is None or hub.request.form.get("suite_tags_present") != "1":
        return
    case.suite_tags = ",".join(_selected_suite_tags(hub.request))
    hub.db.session.commit()


def _patch_suite_tag_forms(hub, ui_redesign):
    tag_css = """
<style>
.suite-tag-options{display:flex;gap:7px;flex-wrap:wrap}.suite-tag-option{display:flex!important;align-items:center;gap:6px!important;width:auto!important;margin:0!important;padding:7px 9px;border:1px solid #d5e0ee;border-radius:9px;background:#f8fbff;color:#38536f!important;font-size:11px!important;font-weight:800!important;cursor:pointer}.suite-tag-option input{width:15px!important;height:15px!important;margin:0!important;padding:0!important}.suite-tag-help{margin-top:6px;color:#7a8ba1;font-size:10px;line-height:1.35}.badge.suite{background:#f1ecff;color:#6546b5}
</style>
"""

    if "suite-tag-options" not in ui_redesign.MAIN_PAGE_HTML:
        ui_redesign.MAIN_PAGE_HTML = ui_redesign.MAIN_PAGE_HTML.replace(
            "</head>", tag_css + "</head>", 1
        )
        create_marker = '''      <div class="form-row"><div class="form-field"><label>Status</label><select name="status"><option>Draft</option><option>Ready</option><option>Passed</option><option>Failed</option><option>Blocked</option></select></div><div class="form-field"><label>Test case ID</label><input name="case_key" placeholder="Auto-generate"></div></div>'''
        create_tags = create_marker + '''
      <div class="form-field"><label>Suite tags</label><input type="hidden" name="suite_tags_present" value="1"><div class="suite-tag-options"><label class="suite-tag-option"><input type="checkbox" name="suite_tags" value="smoke">smoke</label><label class="suite-tag-option"><input type="checkbox" name="suite_tags" value="regression">regression</label><label class="suite-tag-option"><input type="checkbox" name="suite_tags" value="release">release</label></div><div class="suite-tag-help">Smoke, Regression and Full Release presets select Automated cases using these tags.</div></div>'''
        ui_redesign.MAIN_PAGE_HTML = ui_redesign.MAIN_PAGE_HTML.replace(
            create_marker, create_tags, 1
        )
        badge_marker = '''<span class="badge {% if c.status == 'Ready' %}ready{% endif %}">{{ c.status }}</span>'''
        badge_tags = badge_marker + '''{% for tag in c.suite_tag_list %}<span class="badge suite">@{{ tag }}</span>{% endfor %}'''
        ui_redesign.MAIN_PAGE_HTML = ui_redesign.MAIN_PAGE_HTML.replace(
            badge_marker, badge_tags, 1
        )

    if "suite-tag-options" not in hub.EDIT_PAGE_HTML:
        hub.EDIT_PAGE_HTML = hub.EDIT_PAGE_HTML.replace(
            "</head>", tag_css + "</head>", 1
        )
        edit_marker = '''      <div class="field"><label>Status</label><select name="status">{% for s in statuses %}<option value="{{ s }}" {% if s == case.status %}selected{% endif %}>{{ s }}</option>{% endfor %}</select></div>'''
        edit_tags = edit_marker + '''
      <div class="field"><label>Suite tags</label><input type="hidden" name="suite_tags_present" value="1"><div class="suite-tag-options"><label class="suite-tag-option"><input type="checkbox" name="suite_tags" value="smoke" {% if 'smoke' in case.suite_tag_list %}checked{% endif %}>smoke</label><label class="suite-tag-option"><input type="checkbox" name="suite_tags" value="regression" {% if 'regression' in case.suite_tag_list %}checked{% endif %}>regression</label><label class="suite-tag-option"><input type="checkbox" name="suite_tags" value="release" {% if 'release' in case.suite_tag_list %}checked{% endif %}>release</label></div><div class="hint">These tags control Smoke, Regression and Full Release presets.</div></div>'''
        hub.EDIT_PAGE_HTML = hub.EDIT_PAGE_HTML.replace(edit_marker, edit_tags, 1)


def _wrap_suite_tag_routes(hub):
    app = hub.app
    if getattr(app, "_suite_tag_routes_wrapped", False):
        return

    original_create = app.view_functions["create_case"]
    original_update = app.view_functions["update_case"]

    @wraps(original_create)
    def create_case_with_suite_tags():
        before_id = hub.db.session.scalar(hub.db.select(hub.db.func.max(hub.TestCase.id))) or 0
        requested_key = hub.request.form.get("case_key", "").strip().upper()
        response = original_create()
        if _response_status(response) < 400 and hub.request.form.get("suite_tags_present") == "1":
            if requested_key:
                case = hub.db.session.scalar(
                    hub.db.select(hub.TestCase).where(hub.TestCase.case_key == requested_key)
                )
            else:
                case = hub.db.session.scalar(
                    hub.db.select(hub.TestCase)
                    .where(hub.TestCase.id > before_id)
                    .order_by(hub.TestCase.id.desc())
                )
            _save_suite_tags(hub, case)
        return response

    @wraps(original_update)
    def update_case_with_suite_tags(case_key):
        new_key = hub.request.form.get("case_key", "").strip().upper()
        response = original_update(case_key)
        if _response_status(response) < 400 and hub.request.form.get("suite_tags_present") == "1":
            case = hub.db.session.scalar(
                hub.db.select(hub.TestCase).where(hub.TestCase.case_key == new_key)
            )
            _save_suite_tags(hub, case)
        return response

    app.view_functions["create_case"] = create_case_with_suite_tags
    app.view_functions["update_case"] = update_case_with_suite_tags
    app._suite_tag_routes_wrapped = True


def _run_git(project_root, *args):
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=4,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def _git_readiness(bdd_sync, automation):
    watched = []
    for key in ("feature_file", "runner_file"):
        value = str(automation.get(key) or "").strip()
        if value:
            watched.append(value)
    watched.append("playwright/pageObjects")

    status = _run_git(bdd_sync.PROJECT_ROOT, "status", "--porcelain", "--", *watched)
    if status is None:
        return {
            "state": "unknown",
            "label": "Git status unavailable",
            "detail": "Test Hub could not read the local Git working tree.",
            "ready": False,
        }
    if status:
        changed = []
        for line in status.splitlines():
            path = line[3:].strip() if len(line) > 3 else line.strip()
            if path:
                changed.append(path)
        preview = ", ".join(changed[:3])
        if len(changed) > 3:
            preview += f" +{len(changed) - 3} more"
        return {
            "state": "local",
            "label": "Local changes",
            "detail": f"Commit and push before Jenkins runs this code. {preview}" if preview else "Commit and push before Jenkins runs this code.",
            "ready": False,
        }

    upstream = _run_git(
        bdd_sync.PROJECT_ROOT,
        "rev-parse",
        "--abbrev-ref",
        "--symbolic-full-name",
        "@{u}",
    )
    branch = _run_git(bdd_sync.PROJECT_ROOT, "rev-parse", "--abbrev-ref", "HEAD") or "unknown"
    if not upstream:
        return {
            "state": "unknown",
            "label": "No upstream branch",
            "detail": f"{branch} has no tracked remote branch, so Jenkins readiness cannot be verified.",
            "ready": False,
        }

    counts = _run_git(bdd_sync.PROJECT_ROOT, "rev-list", "--left-right", "--count", f"HEAD...{upstream}")
    if not counts:
        return {
            "state": "unknown",
            "label": "Git comparison unavailable",
            "detail": f"Could not compare {branch} with {upstream}.",
            "ready": False,
        }

    try:
        ahead, behind = [int(value) for value in counts.split()[:2]]
    except (TypeError, ValueError):
        ahead, behind = 0, 0

    if ahead and behind:
        return {
            "state": "warn",
            "label": "Branch diverged",
            "detail": f"{branch} is {ahead} commit(s) ahead and {behind} behind {upstream}. Reconcile before Jenkins execution.",
            "ready": False,
        }
    if ahead:
        return {
            "state": "committed",
            "label": "Committed · not pushed",
            "detail": f"{ahead} local commit(s) are not yet on {upstream}.",
            "ready": False,
        }
    if behind:
        return {
            "state": "warn",
            "label": "Behind remote",
            "detail": f"Local {branch} is {behind} commit(s) behind {upstream}. Pull before making more automation changes.",
            "ready": False,
        }
    return {
        "state": "ready",
        "label": "Jenkins-ready",
        "detail": f"Relevant automation files are clean and {branch} matches {upstream}.",
        "ready": True,
    }


def _patch_automation_readiness(bdd_sync):
    if getattr(bdd_sync, "_git_readiness_enabled", False):
        return

    original_status = bdd_sync.automation_status

    def automation_status_with_git(case):
        automation = original_status(case)
        automation["git_readiness"] = _git_readiness(bdd_sync, automation)
        return automation

    bdd_sync.automation_status = automation_status_with_git
    bdd_sync._git_readiness_enabled = True

    css = '''<style>.git-ready{background:#dcfce7!important;color:#166534!important}.git-local,.git-committed,.git-warn{background:#fff4d6!important;color:#8a5b00!important}.git-unknown{background:#edf2f8!important;color:#526174!important}.git-detail{margin:-4px 0 8px;color:#718096;font-size:11px;line-height:1.4}</style>'''
    bdd_sync.AUTOMATION_PAGE_HTML = bdd_sync.AUTOMATION_PAGE_HTML.replace("</head>", css + "</head>", 1)
    marker = '''    <div class="status"><span>Automation</span><span class="pill {% if automation.ready %}ready{% else %}warn{% endif %}">{% if automation.ready %}Ready{% else %}Needs work{% endif %}</span></div>'''
    readiness = marker + '''
    {% if automation.git_readiness %}<div class="status"><span>Git / Jenkins</span><span class="pill git-{{ automation.git_readiness.state }}">{{ automation.git_readiness.label }}</span></div><div class="git-detail">{{ automation.git_readiness.detail }}</div>{% endif %}'''
    bdd_sync.AUTOMATION_PAGE_HTML = bdd_sync.AUTOMATION_PAGE_HTML.replace(marker, readiness, 1)


def apply_workflow_improvements(hub, ui_redesign, bdd_sync):
    _patch_suite_tag_forms(hub, ui_redesign)
    _wrap_suite_tag_routes(hub)
    _patch_automation_readiness(bdd_sync)
