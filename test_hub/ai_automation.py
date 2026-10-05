import ast
import os
import textwrap

from openai import OpenAI
from pydantic import BaseModel, Field


OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.6-luna").strip()
PAGE_OBJECTS_DIR_NAME = "playwright/pageObjects"


class AutomationProposal(BaseModel):
    summary: str
    test_code: str = ""
    page_object_file: str = ""
    page_object_class: str = ""
    page_object_methods: str = ""
    warnings: list[str] = Field(default_factory=list)


def _case_or_404(hub, case_key):
    return hub.db.session.scalar(
        hub.db.select(hub.TestCase).where(hub.TestCase.case_key == case_key)
    )


def _project_path(bdd_sync, relative_path):
    path = (bdd_sync.PROJECT_ROOT / relative_path).resolve()
    try:
        path.relative_to(bdd_sync.PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise ValueError("Generated target path is outside the project.") from exc
    return path


def _page_object_catalog(bdd_sync):
    page_objects_dir = bdd_sync.PROJECT_ROOT / PAGE_OBJECTS_DIR_NAME
    items = []
    if not page_objects_dir.exists():
        return items

    for path in sorted(page_objects_dir.glob("*.py")):
        try:
            content = path.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(path))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue

        classes = [node.name for node in tree.body if isinstance(node, ast.ClassDef)]
        items.append({
            "path": path.relative_to(bdd_sync.PROJECT_ROOT).as_posix(),
            "classes": classes,
            "content": content[:7000],
        })
    return items


def _application_context(bdd_sync):
    candidates = [
        bdd_sync.PROJECT_ROOT / "qa_testing_playground" / "store.py",
        bdd_sync.PROJECT_ROOT / "qa_testing_playground" / "qa_playground.py",
    ]
    blocks = []
    total_chars = 0
    for path in candidates:
        if not path.exists():
            continue
        try:
            content = path.read_text(encoding="utf-8")[:18000]
        except (OSError, UnicodeDecodeError):
            continue
        block = f"FILE: {path.relative_to(bdd_sync.PROJECT_ROOT).as_posix()}\n{content}"
        if total_chars + len(block) > 32000:
            break
        blocks.append(block)
        total_chars += len(block)
    return "\n\n---\n\n".join(blocks)


def _automation_context(bdd_sync, automation):
    runner_path = _project_path(bdd_sync, automation["runner_file"])
    runner_content = runner_path.read_text(encoding="utf-8")

    conftest_path = bdd_sync.BDD_DIR / "conftest.py"
    try:
        conftest_content = conftest_path.read_text(encoding="utf-8")[:12000]
    except OSError:
        conftest_content = ""

    catalog = _page_object_catalog(bdd_sync)
    page_objects = []
    total_chars = 0
    for item in catalog:
        block = (
            f"FILE: {item['path']}\n"
            f"CLASSES: {', '.join(item['classes']) or 'none'}\n"
            f"{item['content']}"
        )
        if total_chars + len(block) > 30000:
            break
        total_chars += len(block)
        page_objects.append(block)

    return {
        "runner_path": automation["runner_file"],
        "runner_content": runner_content,
        "conftest_content": conftest_content,
        "page_objects": "\n\n---\n\n".join(page_objects),
        "application_context": _application_context(bdd_sync),
        "allowed_page_objects": [item["path"] for item in catalog],
        "missing_steps": [row["step"] for row in automation["steps"] if not row["implemented"]],
    }


def _generate_proposal(bdd_sync, case, automation):
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured for Test Hub.")
    if not automation["runner_exists"]:
        raise RuntimeError("Sync the case to BDD first so a pytest-bdd runner exists.")
    if not (automation["synced"] or automation["existing_reference"]):
        raise RuntimeError("Sync the case to BDD before generating automation code.")

    context = _automation_context(bdd_sync, automation)
    if not context["missing_steps"]:
        raise RuntimeError("This case has no missing BDD step implementations.")

    allowed_files = "\n".join(f"- {path}" for path in context["allowed_page_objects"]) or "- none"
    missing_steps = "\n".join(f"- {step}" for step in context["missing_steps"])

    instructions = f"""You are the AI Automation Assistant inside Test Hub.
Generate reviewable Python additions for the missing pytest-bdd steps only.
Return exactly the requested structured schema.

Hard rules:
- Implement ONLY these missing steps:\n{missing_steps}
- test_code is appended to the existing pytest-bdd runner. It must contain decorators/functions for the missing steps only.
- BDD test code must contain no comments.
- Reuse existing fixtures and shared_data patterns from the supplied runner/conftest.
- Keep Playwright locators and UI assertions in Page Object methods, not in BDD step functions.
- Prefer calling existing Page Object methods. Add new Page Object methods only when necessary.
- page_object_file must be exactly one of the allowed existing files below, or an empty string if no Page Object change is needed.
- page_object_class must be an existing class in that file, or empty if no Page Object change is needed.
- page_object_methods must contain method definitions only, without a class wrapper and without imports.
- Application source is read-only context. Never propose modifications to product/application files.
- Prefer application source as the strongest evidence for product behavior and selectors.
- If the requested behavior is not yet present in the supplied application source, you may still generate automation from the explicit Test Case and BDD scenario contract.
- When generating automation for behavior that is not yet implemented, add a clear warning that the automation is test-first and is expected to fail until development is complete.
- Do not invent arbitrary selectors. For not-yet-implemented behavior, prefer selectors justified by explicit accessible roles, labels, names, IDs or test IDs stated by the scenario, Test Case, or existing project conventions.
- In test-first mode, an existing Page Object locator or method for the same UI control is valid project-contract evidence even when that control is not yet present in application source.
- Reuse existing Page Object selectors and locator conventions for the same control instead of refusing generation.
- If an existing Page Object already identifies the target control, new interaction methods such as keyboard focus, keyboard activation, or state assertions should reuse that same locator.
- Do not leave pytest-bdd step definitions empty solely because the product feature is not implemented yet. If a step can call an existing or defensible test-first Page Object method, generate it.
- Still add a warning when the generated automation depends on behavior that is not yet present in application source.
- If no defensible selector can be derived from application source, the explicit test contract, or existing Page Object evidence, leave only that unsupported interaction unimplemented and explain why in warnings.
- Keep code concise and synchronous Playwright only.
- Do not include Markdown code fences.

Allowed Page Object files:
{allowed_files}
"""

    user_input = f"""Test case: {case.case_key} — {case.title}
Feature: {case.feature_name}
Preconditions: {case.preconditions or 'None'}
Expected result: {case.expected_result}

Scenario:
{automation['preview']}

Target pytest-bdd runner: {context['runner_path']}
Current runner code:
{context['runner_content']}

Shared BDD fixtures / reusable steps context:
{context['conftest_content']}

Existing Page Objects:
{context['page_objects']}

Application source (read-only evidence of actual supported behavior):
{context['application_context']}
"""

    client = OpenAI(api_key=api_key)
    response = client.responses.parse(
        model=OPENAI_MODEL,
        input=[
            {"role": "system", "content": instructions},
            {"role": "user", "content": user_input},
        ],
        text_format=AutomationProposal,
    )
    proposal = response.output_parsed
    if proposal is None:
        raise RuntimeError("The AI automation response could not be parsed.")

    if proposal.page_object_file and proposal.page_object_file not in context["allowed_page_objects"]:
        raise RuntimeError("AI selected a Page Object file outside the allowed project files.")
    return proposal


def _normalize_methods(raw_methods):
    text = textwrap.dedent(raw_methods or "").strip()
    if not text:
        return ""
    return textwrap.indent(text, "    ")


def _insert_class_methods(current_content, class_name, raw_methods):
    methods = _normalize_methods(raw_methods)
    if not methods:
        return current_content
    if not class_name:
        raise ValueError("A Page Object class is required when methods are provided.")

    tree = ast.parse(current_content)
    target = next(
        (node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name),
        None,
    )
    if target is None:
        raise ValueError(f"Page Object class {class_name!r} was not found.")

    lines = current_content.splitlines()
    insert_at = target.end_lineno
    updated = lines[:insert_at] + [""] + methods.splitlines() + lines[insert_at:]
    result = "\n".join(updated).rstrip() + "\n"
    ast.parse(result)
    return result


def _validate_test_code(test_code):
    code = (test_code or "").strip()
    if not code:
        raise ValueError("The reviewed pytest-bdd code is empty.")
    if "```" in code:
        raise ValueError("Remove Markdown code fences before saving.")
    if any(line.lstrip().startswith("#") for line in code.splitlines()):
        raise ValueError("BDD test files must not contain comments.")
    ast.parse(code)
    return code


def _safe_runner_path(bdd_sync, automation):
    if not automation["runner_file"]:
        raise ValueError("No pytest-bdd runner is available for this case.")
    path = _project_path(bdd_sync, automation["runner_file"])
    try:
        path.relative_to(bdd_sync.TESTS_DIR.resolve())
    except ValueError as exc:
        raise ValueError("The pytest-bdd runner is outside the BDD tests directory.") from exc
    if not path.exists():
        raise ValueError("The pytest-bdd runner no longer exists.")
    return path


def _safe_page_object_path(bdd_sync, relative_path):
    path = _project_path(bdd_sync, relative_path)
    page_objects_dir = (bdd_sync.PROJECT_ROOT / PAGE_OBJECTS_DIR_NAME).resolve()
    try:
        path.relative_to(page_objects_dir)
    except ValueError as exc:
        raise ValueError("The selected Page Object is outside playwright/pageObjects.") from exc
    if path.suffix != ".py" or not path.exists():
        raise ValueError("The selected Page Object file does not exist.")
    return path


def _save_reviewed_code(bdd_sync, automation, test_code, page_object_file, page_object_class, page_object_methods):
    if "```" in (page_object_methods or ""):
        raise ValueError("Remove Markdown code fences before saving.")

    runner_path = _safe_runner_path(bdd_sync, automation)
    clean_test_code = _validate_test_code(test_code)
    runner_current = runner_path.read_text(encoding="utf-8")
    runner_updated = runner_current.rstrip() + "\n\n\n" + clean_test_code + "\n"
    ast.parse(runner_updated)

    page_object_path = None
    page_object_updated = None
    if (page_object_methods or "").strip():
        if not page_object_file:
            raise ValueError("Choose an existing Page Object file for the proposed methods.")
        page_object_path = _safe_page_object_path(bdd_sync, page_object_file)
        page_object_updated = _insert_class_methods(
            page_object_path.read_text(encoding="utf-8"),
            page_object_class.strip(),
            page_object_methods,
        )

    runner_path.write_text(runner_updated, encoding="utf-8")
    if page_object_path and page_object_updated is not None:
        page_object_path.write_text(page_object_updated, encoding="utf-8")


def _patch_automation_template(bdd_sync):
    template = bdd_sync.AUTOMATION_PAGE_HTML
    generate_button = '''\n      {% if not automation.ready and automation.runner_exists and (automation.synced or automation.existing_reference) and automation.implemented_count < automation.total_steps %}<form method="post" action="{{ url_for('ai_generate_automation', case_key=case.case_key) }}"><button class="button" type="submit">✨ Generate missing automation with AI</button></form>{% endif %}'''
    marker = '''      {% if automation.ready and case.status != 'Ready' %}<form method="post" action="{{ url_for('set_status', case_key=case.case_key) }}"><input type="hidden" name="status" value="Ready"><button class="button" type="submit">Mark Ready</button></form>{% endif %}'''
    if "ai_generate_automation" not in template and marker in template:
        template = template.replace(marker, generate_button + "\n" + marker, 1)

    proposal_card = '''\n  {% if proposal %}<div class="card scenario"><h2>✨ AI automation proposal</h2>\n    <div class="muted" style="margin-bottom:12px">Generated with {{ model }}. Review and edit everything before saving. Nothing is committed or pushed automatically.</div>\n    {% if proposal.warnings %}<div class="message" style="background:#fff4dd;color:#8a5d00">{% for warning in proposal.warnings %}<div>⚠ {{ warning }}</div>{% endfor %}</div>{% endif %}\n    <p style="font-size:13px;color:#41526c"><strong>Summary:</strong> {{ proposal.summary }}</p>\n    <form method="post" action="{{ url_for('ai_save_automation', case_key=case.case_key) }}">\n      <label style="display:block;margin:12px 0 6px;font-size:12px;font-weight:800">pytest-bdd additions → {{ automation.runner_file }}</label>\n      <textarea name="test_code" style="width:100%;min-height:260px;padding:12px;border:1px solid #ccd5e4;border-radius:10px;font:12px/1.5 Consolas,monospace">{{ proposal.test_code }}</textarea>\n      <label style="display:block;margin:12px 0 6px;font-size:12px;font-weight:800">Page Object file</label>\n      <input name="page_object_file" value="{{ proposal.page_object_file }}" style="width:100%;height:40px;padding:0 10px;border:1px solid #ccd5e4;border-radius:9px">\n      <label style="display:block;margin:12px 0 6px;font-size:12px;font-weight:800">Page Object class</label>\n      <input name="page_object_class" value="{{ proposal.page_object_class }}" style="width:100%;height:40px;padding:0 10px;border:1px solid #ccd5e4;border-radius:9px">\n      <label style="display:block;margin:12px 0 6px;font-size:12px;font-weight:800">Page Object methods</label>\n      <textarea name="page_object_methods" style="width:100%;min-height:260px;padding:12px;border:1px solid #ccd5e4;border-radius:10px;font:12px/1.5 Consolas,monospace">{{ proposal.page_object_methods }}</textarea>\n      {% if proposal.test_code %}<div class="actions"><button class="primary" type="submit">Save reviewed code locally</button><a class="button" href="{{ url_for('bdd_automation_case', case_key=case.case_key) }}">Discard proposal</a></div>{% else %}<div class="message" style="background:#fff4dd;color:#8a5d00">No code was proposed. Resolve the warnings or update the product requirement before generating again.</div>{% endif %}\n    </form>\n  </div>{% endif %}\n'''
    closing = "\n</section>\n</main></body></html>"
    if "AI automation proposal" not in template and closing in template:
        template = template.replace(closing, proposal_card + closing, 1)

    bdd_sync.AUTOMATION_PAGE_HTML = template


def register_ai_automation(hub, bdd_sync):
    app = hub.app
    if "ai_generate_automation" in app.view_functions:
        return

    _patch_automation_template(bdd_sync)

    @app.post("/test-cases/<case_key>/automation/ai-generate")
    def ai_generate_automation(case_key):
        case = _case_or_404(hub, case_key)
        if case is None:
            return "Test case not found.", 404
        if case.type != "Automated":
            return "AI automation generation is available only for Automated cases.", 400

        automation = bdd_sync.automation_status(case)
        try:
            proposal = _generate_proposal(bdd_sync, case, automation)
        except Exception as exc:
            message = str(exc)
            if len(message) > 700:
                message = message[:700] + "…"
            return hub.redirect(
                hub.url_for("bdd_automation_case", case_key=case.case_key, message=message)
            )

        return hub.render_template_string(
            bdd_sync.AUTOMATION_PAGE_HTML,
            case=case,
            automation=automation,
            message="AI generated a proposal. Review every line before saving.",
            proposal=proposal,
            model=OPENAI_MODEL,
        )

    @app.post("/test-cases/<case_key>/automation/ai-save")
    def ai_save_automation(case_key):
        case = _case_or_404(hub, case_key)
        if case is None:
            return "Test case not found.", 404
        if case.type != "Automated":
            return "AI automation generation is available only for Automated cases.", 400

        automation = bdd_sync.automation_status(case)
        if automation["ready"]:
            return hub.redirect(
                hub.url_for(
                    "bdd_automation_case",
                    case_key=case.case_key,
                    message="Automation is already Ready; no AI code was saved.",
                )
            )

        try:
            _save_reviewed_code(
                bdd_sync,
                automation,
                hub.request.form.get("test_code", ""),
                hub.request.form.get("page_object_file", "").strip(),
                hub.request.form.get("page_object_class", "").strip(),
                hub.request.form.get("page_object_methods", ""),
            )
        except (OSError, SyntaxError, ValueError) as exc:
            return f"AI automation was not saved: {exc}", 400

        return hub.redirect(
            hub.url_for(
                "bdd_automation_case",
                case_key=case.case_key,
                message="Reviewed AI automation saved locally. Run the test and review git diff before committing.",
            )
        )