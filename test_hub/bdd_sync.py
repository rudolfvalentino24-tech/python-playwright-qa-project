import ast
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
FEATURES_DIR = PROJECT_ROOT / "playwright" / "e2e_bdd" / "features"
TESTS_DIR = PROJECT_ROOT / "playwright" / "e2e_bdd" / "tests"
BDD_DIR = PROJECT_ROOT / "playwright" / "e2e_bdd"
STEP_PATTERN = re.compile(r"^(Given|When|Then|And|But)\s+(.+)$", re.IGNORECASE)
SCENARIO_PATTERN = re.compile(r"^\s*Scenario(?: Outline)?:\s*(.+?)\s*$", re.IGNORECASE)

AUTOMATION_PAGE_HTML = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ case.case_key }} Automation - Test Hub</title>
<style>
:root{--surface:rgba(255,255,255,.96);--text:#111827;--muted:#6b7280;--border:#d7dfec;--green:#166534;--amber:#92400e;--blue:#2468e5;font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}*{box-sizing:border-box}body{margin:0;min-height:100vh;color:var(--text);background:radial-gradient(circle at 8% 5%,rgba(98,134,255,.17),transparent 28%),linear-gradient(180deg,#f8faff,#eef3fb)}header{display:flex;align-items:center;justify-content:space-between;padding:16px 30px;background:rgba(20,42,82,.94);color:#fff}.brand strong{font-size:20px}.brand span{display:block;font-size:12px;opacity:.7}.button,button{display:inline-block;border:0;border-radius:10px;padding:10px 14px;text-decoration:none;font:inherit;font-weight:780;cursor:pointer}.button{background:#eef2f7;color:#20324f}.primary{background:linear-gradient(90deg,#2f66e8,#2475ff);color:#fff}.ready{background:#dcfce7;color:var(--green)}.warn{background:#fef3c7;color:var(--amber)}main{max-width:1050px;margin:0 auto;padding:32px 22px 50px}.top{display:flex;justify-content:space-between;gap:18px;align-items:flex-start;margin-bottom:20px}.top h1{margin:0;color:#172b4d;font-size:29px}.muted{color:var(--muted);font-size:13px;margin-top:5px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:17px}.card{padding:20px;border:1px solid var(--border);border-radius:18px;background:var(--surface);box-shadow:0 14px 38px rgba(35,61,108,.07)}.card h2{margin:0 0 14px;color:#172b4d;font-size:18px}.status{display:flex;justify-content:space-between;gap:12px;padding:10px 0;border-top:1px solid #edf0f5}.status:first-of-type{border-top:0}.pill{padding:4px 8px;border-radius:999px;font-size:12px;font-weight:800}.step{padding:11px 0;border-top:1px solid #edf0f5}.step:first-of-type{border-top:0}.step-head{display:flex;align-items:flex-start;gap:9px}.ok{color:#166534;font-weight:900}.missing{color:#b45309;font-weight:900}.source{margin:6px 0 0 25px;color:var(--muted);font-size:12px}.actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:17px}.message{margin-bottom:18px;padding:13px 15px;border-radius:12px;background:#edf4ff;color:#294a7a}.scenario{grid-column:1/-1}.scenario pre{white-space:pre-wrap;overflow:auto;margin:0;padding:15px;border-radius:12px;background:#111827;color:#e5edf8;font-size:12px;line-height:1.55}@media(max-width:800px){.grid{grid-template-columns:1fr}.scenario{grid-column:auto}.top{flex-direction:column}}</style>
</head>
<body>
<header><div class="brand"><strong>🧪 Test Hub · BDD Automation</strong><span>pytest-bdd synchronization</span></div><a class="button" href="{{ url_for('index') }}">Test cases</a></header>
<main>
{% if message %}<div class="message">{{ message }}</div>{% endif %}
<div class="top"><div><h1>{{ case.case_key }} — {{ case.title }}</h1><div class="muted">{{ case.feature_name }} · {{ case.status }} · {{ case.type }}</div></div><a class="button" href="{{ url_for('test_case_details', case_key=case.case_key) }}">Case history</a></div>
<section class="grid">
  <div class="card"><h2>Automation status</h2>
    <div class="status"><span>BDD scenario</span><span class="pill {% if automation.synced %}ready{% else %}warn{% endif %}">{% if automation.synced %}Synced{% elif automation.existing_reference %}Existing outline{% else %}Not synced{% endif %}</span></div>
    <div class="status"><span>Feature file</span><strong>{{ automation.feature_file or 'Not created' }}</strong></div>
    <div class="status"><span>pytest-bdd runner</span><span class="pill {% if automation.runner_exists %}ready{% else %}warn{% endif %}">{% if automation.runner_exists %}Available{% else %}Missing{% endif %}</span></div>
    <div class="status"><span>Implemented steps</span><strong>{{ automation.implemented_count }} / {{ automation.total_steps }}</strong></div>
    <div class="status"><span>Automation</span><span class="pill {% if automation.ready %}ready{% else %}warn{% endif %}">{% if automation.ready %}Ready{% else %}Needs work{% endif %}</span></div>
    <div class="actions">
      <form method="post" action="{{ url_for('sync_case_to_bdd', case_key=case.case_key) }}"><button class="primary" type="submit">{% if automation.synced %}Sync changes to BDD{% else %}Sync to BDD{% endif %}</button></form>
      {% if automation.ready and case.status != 'Ready' %}<form method="post" action="{{ url_for('set_status', case_key=case.case_key) }}"><input type="hidden" name="status" value="Ready"><button class="button" type="submit">Mark Ready</button></form>{% endif %}
    </div>
  </div>
  <div class="card"><h2>Step implementation</h2>
    {% for item in automation.steps %}<div class="step"><div class="step-head"><span class="{% if item.implemented %}ok{% else %}missing{% endif %}">{% if item.implemented %}✓{% else %}⚠{% endif %}</span><span>{{ item.step }}</span></div>{% if item.source %}<div class="source">{{ item.source }}</div>{% endif %}</div>{% else %}<div class="muted">No BDD steps found.</div>{% endfor %}
  </div>
  <div class="card scenario"><h2>Scenario preview</h2><pre>{{ automation.preview }}</pre></div>
</section>
</main></body></html>
"""


def _slug(value):
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "feature"


def _normalize(value):
    return " ".join(value.strip().split()).lower()


def _step_body(step):
    match = STEP_PATTERN.match(step.strip())
    return match.group(2).strip() if match else step.strip()


def _feature_title(path):
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip().lower().startswith("feature:"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return ""


def _find_feature_file(feature_name):
    FEATURES_DIR.mkdir(parents=True, exist_ok=True)
    normalized = _normalize(feature_name)
    for path in sorted(FEATURES_DIR.glob("*.feature")):
        if _normalize(_feature_title(path)) == normalized:
            return path
    return FEATURES_DIR / f"{_slug(feature_name)}.feature"


def _direct_scenario(path, case_key):
    if not path.exists():
        return None
    lines = path.read_text(encoding="utf-8").splitlines()
    target = case_key.upper()
    for index, line in enumerate(lines):
        match = SCENARIO_PATTERN.match(line)
        if not match:
            continue
        name = match.group(1).strip()
        upper = name.upper()
        if upper == target or upper.startswith(target + " "):
            steps = []
            end = len(lines)
            for cursor in range(index + 1, len(lines)):
                stripped = lines[cursor].strip()
                if SCENARIO_PATTERN.match(lines[cursor]) or stripped.startswith("@") or stripped.startswith("Feature:") or stripped.startswith("Background:"):
                    end = cursor
                    break
                if STEP_PATTERN.match(stripped):
                    steps.append(stripped)
            start = index
            while start > 0 and lines[start - 1].strip().startswith("@"):
                start -= 1
            return {"start": start, "heading": index, "end": end, "steps": steps, "lines": lines}
    return None


def _find_case_reference(case):
    target = case.case_key.upper()
    for path in sorted(FEATURES_DIR.glob("*.feature")):
        direct = _direct_scenario(path, case.case_key)
        if direct:
            return path, direct, False
        try:
            text = path.read_text(encoding="utf-8").upper()
        except OSError:
            continue
        if target in text:
            return path, None, True
    return None, None, False


def _literal_from_node(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _parser_pattern(value):
    escaped = re.escape(value)
    escaped = re.sub(r"\\\{[^{}]+\\\}", r".+?", escaped)
    return re.compile(r"^" + escaped + r"$", re.IGNORECASE)


def _scan_step_definitions():
    definitions = []
    if not BDD_DIR.exists():
        return definitions

    for path in sorted(BDD_DIR.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call) or not decorator.args:
                    continue
                func_name = decorator.func.id if isinstance(decorator.func, ast.Name) else ""
                if func_name not in {"given", "when", "then"}:
                    continue

                value = _literal_from_node(decorator.args[0])
                dynamic = False
                if value is None and isinstance(decorator.args[0], ast.Call) and decorator.args[0].args:
                    parser_call = decorator.args[0]
                    parser_name = parser_call.func.attr if isinstance(parser_call.func, ast.Attribute) else ""
                    if parser_name in {"parse", "cfparse"}:
                        value = _literal_from_node(parser_call.args[0])
                        dynamic = value is not None
                if not value:
                    continue

                try:
                    relative = path.relative_to(PROJECT_ROOT)
                except ValueError:
                    relative = path
                definitions.append({
                    "text": value,
                    "normalized": _normalize(value),
                    "pattern": _parser_pattern(value) if dynamic else None,
                    "source": f"{relative.as_posix()}:{node.lineno}",
                })
    return definitions


def _match_step(step, definitions):
    body = _step_body(step)
    normalized = _normalize(body)
    for definition in definitions:
        if definition["normalized"] == normalized:
            return definition
        if definition["pattern"] and definition["pattern"].match(body):
            return definition
    return None


def _runner_for_feature(feature_path):
    if not TESTS_DIR.exists():
        return None
    basename = feature_path.name
    for path in sorted(TESTS_DIR.glob("test_*_bdd.py")):
        try:
            if basename in path.read_text(encoding="utf-8"):
                return path
        except OSError:
            continue
    return None


def _scenario_lines(case):
    tags = [tag for tag in case.suite_tag_list if tag in {"smoke", "regression", "release"}]
    lines = []
    if tags:
        lines.append("  " + " ".join(f"@{tag}" for tag in tags))
    lines.append(f"  Scenario: {case.case_key} {case.title}")
    for step in case.steps:
        lines.append(f"    {step.action.strip()}")
    return lines


def _scenario_preview(case):
    return "\n".join(_scenario_lines(case))


def automation_status(case):
    definitions = _scan_step_definitions()
    step_rows = []
    for step in case.steps:
        definition = _match_step(step.action, definitions)
        step_rows.append({
            "step": step.action,
            "implemented": definition is not None,
            "source": definition["source"] if definition else "",
        })

    referenced_path, direct, outline_reference = _find_case_reference(case)
    feature_path = referenced_path or _find_feature_file(case.feature_name)
    expected_steps = [_normalize(step.action) for step in case.steps]
    file_steps = [_normalize(step) for step in direct["steps"]] if direct else []
    synced = bool(direct and expected_steps == file_steps)
    runner = _runner_for_feature(feature_path)
    implemented_count = sum(1 for item in step_rows if item["implemented"])
    ready = bool((synced or outline_reference) and runner and implemented_count == len(step_rows) and step_rows)

    try:
        feature_label = feature_path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        feature_label = str(feature_path)
    runner_label = ""
    if runner:
        try:
            runner_label = runner.relative_to(PROJECT_ROOT).as_posix()
        except ValueError:
            runner_label = str(runner)

    return {
        "synced": synced,
        "existing_reference": outline_reference,
        "feature_file": feature_label,
        "runner_exists": runner is not None,
        "runner_file": runner_label,
        "implemented_count": implemented_count,
        "total_steps": len(step_rows),
        "steps": step_rows,
        "ready": ready,
        "preview": _scenario_preview(case),
    }


def _write_scenario(case):
    reference_path, direct, outline_reference = _find_case_reference(case)
    if outline_reference and not direct:
        return reference_path, False, "This case is already represented by an existing Scenario Outline; no duplicate scenario was created."

    path = reference_path or _find_feature_file(case.feature_name)
    scenario = _scenario_lines(case)

    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines()
        direct = _direct_scenario(path, case.case_key)
        if direct:
            start, end = direct["start"], direct["end"]
            while end > start and not lines[end - 1].strip():
                end -= 1
            updated = lines[:start] + scenario + lines[end:]
            path.write_text("\n".join(updated).rstrip() + "\n", encoding="utf-8")
            created = False
        else:
            text = "\n".join(lines).rstrip()
            path.write_text(text + "\n\n" + "\n".join(scenario) + "\n", encoding="utf-8")
            created = True
    else:
        content = f"Feature: {case.feature_name}\n\n" + "\n".join(scenario) + "\n"
        path.write_text(content, encoding="utf-8")
        created = True

    runner = _runner_for_feature(path)
    if runner is None:
        TESTS_DIR.mkdir(parents=True, exist_ok=True)
        runner = TESTS_DIR / f"test_{_slug(path.stem)}_bdd.py"
        runner.write_text(
            'from pytest_bdd import scenarios\n\n\n'
            f'scenarios("../features/{path.name}")\n',
            encoding="utf-8",
        )

    verb = "created" if created else "updated"
    return path, True, f"BDD scenario {verb}. Existing pytest-bdd step definitions were left unchanged."


def _replace_create_test_run(hub):
    def create_test_run_ready_only():
        name = hub.request.form.get("name", "").strip()
        preset = hub.request.form.get("preset", "Custom").strip()
        release_id_value = hub.request.form.get("release_id", "").strip()
        environment = hub.request.form.get("environment", "").strip()
        execution_type = hub.request.form.get("execution_type", "Manual").strip()
        case_id_values = hub.request.form.getlist("case_ids")

        if not name:
            return "Test run name is required.", 400
        if preset not in hub.RUN_PRESETS:
            return "Invalid test run preset.", 400
        if execution_type not in hub.TYPES:
            return "Invalid execution type.", 400

        release = None
        if release_id_value:
            try:
                release = hub.db.session.get(hub.Release, int(release_id_value))
            except ValueError:
                return "Invalid release.", 400
            if release is None:
                return "Release not found.", 404

        if preset == "Custom":
            if not case_id_values:
                return "Select at least one test case.", 400
            try:
                case_ids = [int(raw_id) for raw_id in case_id_values]
            except ValueError:
                return "Invalid test case selection.", 400
            cases = hub.db.session.scalars(
                hub.db.select(hub.TestCase)
                .where(hub.TestCase.id.in_(case_ids))
                .order_by(hub.TestCase.feature, hub.TestCase.case_key)
            ).all()
            if len(cases) != len(set(case_ids)):
                return "One or more selected test cases no longer exist.", 400
        else:
            preset_tag = {"Smoke": "smoke", "Regression": "regression", "Full Release": "release"}[preset]
            all_cases = hub.db.session.scalars(
                hub.db.select(hub.TestCase).order_by(hub.TestCase.feature, hub.TestCase.case_key)
            ).all()
            cases = [
                case for case in all_cases
                if case.type == "Automated"
                and case.status == "Ready"
                and preset_tag in case.suite_tag_list
            ]
            execution_type = "Automated"
            if not cases:
                return f"No Ready automated test cases are available for the {preset} preset.", 400

        run = hub.TestRun(
            release=release,
            name=name,
            preset=preset,
            execution_type=execution_type,
            environment=environment or (release.environment if release else ""),
            started_at=hub.datetime.now(hub.timezone.utc),
        )
        run.items = [
            hub.TestRunItem(
                test_case=case,
                position=index,
                case_key_snapshot=case.case_key,
                case_title_snapshot=case.title,
                feature_snapshot=case.feature_name,
            )
            for index, case in enumerate(cases, start=1)
        ]
        hub.db.session.add(run)
        hub.db.session.commit()
        return hub.redirect(hub.url_for("test_run_details", run_id=run.id))

    hub.app.view_functions["create_test_run"] = create_test_run_ready_only


def register_bdd_sync(hub):
    app = hub.app
    if "bdd_automation_case" in app.view_functions:
        return

    app.jinja_env.globals["automation_status"] = automation_status

    action_marker = '<a class="secondary button-link" href="{{ url_for(\'edit_case\', case_key=c.case_key) }}">Edit</a>'
    action_replacement = '''{% if c.type == 'Automated' %}<a class="secondary button-link" href="{{ url_for('bdd_automation_case', case_key=c.case_key) }}">Automation</a>{% endif %}\n              ''' + action_marker
    if action_marker in hub.PAGE_HTML:
        hub.PAGE_HTML = hub.PAGE_HTML.replace(action_marker, action_replacement, 1)

    pill_marker = '<span class="pill">{{ c.status }}</span>'
    pill_replacement = pill_marker + '''\n                  {% if c.type == 'Automated' %}{% set auto = automation_status(c) %}<a class="pill" href="{{ url_for('bdd_automation_case', case_key=c.case_key) }}" style="text-decoration:none;{% if auto.ready %}background:#dcfce7;color:#166534{% elif auto.synced or auto.existing_reference %}background:#fef3c7;color:#92400e{% endif %}">BDD {% if auto.ready %}Ready{% elif auto.synced or auto.existing_reference %}Missing steps{% else %}Not synced{% endif %}</a>{% endif %}'''
    if pill_marker in hub.PAGE_HTML:
        hub.PAGE_HTML = hub.PAGE_HTML.replace(pill_marker, pill_replacement, 1)

    _replace_create_test_run(hub)

    @app.get("/test-cases/<case_key>/automation")
    def bdd_automation_case(case_key):
        case = hub.db.session.scalar(
            hub.db.select(hub.TestCase).where(hub.TestCase.case_key == case_key)
        )
        if case is None:
            return "Test case not found.", 404
        if case.type != "Automated":
            return "BDD automation is available only for Automated test cases.", 400
        return hub.render_template_string(
            AUTOMATION_PAGE_HTML,
            case=case,
            automation=automation_status(case),
            message=hub.request.args.get("message", ""),
        )

    @app.post("/test-cases/<case_key>/sync-bdd")
    def sync_case_to_bdd(case_key):
        case = hub.db.session.scalar(
            hub.db.select(hub.TestCase).where(hub.TestCase.case_key == case_key)
        )
        if case is None:
            return "Test case not found.", 404
        if case.type != "Automated":
            return "Only Automated test cases can be synchronized to BDD.", 400
        if not case.steps:
            return "The test case has no steps to synchronize.", 400

        invalid = [step.action for step in case.steps if not STEP_PATTERN.match(step.action.strip())]
        if invalid:
            return "Automated BDD steps must start with Given, When, Then, And or But.", 400

        try:
            _, _, message = _write_scenario(case)
        except OSError as exc:
            return f"Unable to write BDD files: {exc}", 500

        return hub.redirect(hub.url_for("bdd_automation_case", case_key=case.case_key, message=message))
