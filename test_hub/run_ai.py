import os
from pathlib import Path

from dotenv import load_dotenv

# Load local secrets/configuration before app.py reads environment variables.
load_dotenv(Path(__file__).with_name(".env"), override=False)

import app as hub
import bdd_sync
import ai_automation
import ai_designer
import test_plan_process
import test_plan_strategy
import ui_redesign
from ai_automation import register_ai_automation
from ai_automation_guard import apply_ai_automation_guard
from ai_designer import register_ai_designer
from ai_usage import apply_ai_usage_tracking, apply_ai_usage_ui
from failure_evidence import register_failure_evidence
from help_page import register_help_page
from jira_ui_fix import apply_jira_modal_error_fix
from password_visibility_case_steps import apply_password_visibility_case_step_migration
from product_redesign import register_product_redesign
from qa_intelligence import register_qa_intelligence
from qa_workflow import register_qa_workflow
from results_ui_fix import apply_results_chart_fix
from run_guards import register_run_guards
from test_plan_controls import apply_test_plan_controls
from test_plan_e2e import register_test_plan_e2e
from test_plan_export import register_test_plan_export
from test_plan_process import register_test_plan_process
from test_plan_strategy import register_test_plan_strategy
import test_plans
from test_plans import register_test_plans
from ui_cleanup import register_ui_cleanup
from ui_redesign import register_ui_redesign
from workflow_improvements import apply_workflow_improvements


_original_step_scan = bdd_sync._scan_step_definitions
_step_scan_cache = {"stamp": None, "value": None}


def _cached_step_definitions():
    files = sorted(bdd_sync.BDD_DIR.rglob("*.py")) if bdd_sync.BDD_DIR.exists() else []
    stamp = tuple(
        (str(path), path.stat().st_mtime_ns, path.stat().st_size)
        for path in files
    )
    if stamp != _step_scan_cache["stamp"]:
        _step_scan_cache["stamp"] = stamp
        _step_scan_cache["value"] = _original_step_scan()
    return _step_scan_cache["value"] or []


bdd_sync._scan_step_definitions = _cached_step_definitions

apply_ai_automation_guard(ai_automation)
apply_ai_usage_tracking(ai_designer, ai_automation)
register_ai_designer(hub)
bdd_sync.register_bdd_sync(hub)
register_ai_automation(hub, bdd_sync)
apply_ai_usage_ui(ai_designer, bdd_sync)
apply_workflow_improvements(hub, ui_redesign, bdd_sync)

# Correct the five SCRUM-5 password-visibility Test Hub cases once after pulling
# this branch. The migration changes only their ordered Steps collections.
apply_password_visibility_case_step_migration(hub)

# Register Test Plans before the shared Test Hub UI is finalized so the
# Test Plans tab appears consistently across the existing redesigned pages.
register_test_plans(hub, ui_redesign)

# Add Test Plan maintenance controls without changing the Test Plan database model.
apply_test_plan_controls(test_plans, hub)

# Backward-compatible endpoint name used by the redesigned test-case page.
# Both endpoint names resolve to the same BDD Automation view.
if "case_automation" not in hub.app.view_functions:
    hub.app.add_url_rule(
        "/test-cases/<case_key>/automation",
        endpoint="case_automation",
        view_func=hub.app.view_functions["bdd_automation_case"],
        methods=["GET"],
    )

apply_jira_modal_error_fix(ui_redesign)

# Apply Results dashboard fixes that need access to both the Flask app/database
# and the redesigned Results template.
apply_results_chart_fix(hub, ui_redesign)

# Add concise failure reasons and direct Jenkins screenshot links to Test Runs.
register_failure_evidence(hub)

register_ui_redesign(hub, ai_designer, bdd_sync)
register_ui_cleanup(hub)
register_run_guards(hub)

# Connect Test Plans to Releases, Jira scope, Test Runs, Results, defects and
# final QA reports after the existing views have finished applying their patches.
register_test_plan_process(test_plans, hub, ui_redesign)

# The process renderer passes unattached Test Cases and unique covered Test Cases
# separately. Recombine them for Edit Coverage so every Test Case remains available
# for multi-coverage linking even after it is already used elsewhere in the plan.
coverage_cases_marker = "{% if coverage_link_cases %}"
if coverage_cases_marker in test_plans.TEST_PLAN_PAGE_HTML:
    test_plans.TEST_PLAN_PAGE_HTML = test_plans.TEST_PLAN_PAGE_HTML.replace(
        coverage_cases_marker,
        "{% set coverage_link_cases = attachable_cases + process.covered_cases %}\n                  {% if coverage_link_cases %}",
        1,
    )
else:
    raise RuntimeError(
        "Test Plan coverage linking template changed; expected coverage_link_cases marker was not found."
    )

# The process module adds the tabs/CSS first, then inserts the large process panel
# block before the existing Test Plan JavaScript. Older code used a collapsed
# "</main><script>" marker, while the real template contains a newline between
# those tags. Repair that missing panel insertion explicitly and fail loudly if
# the expected page boundary ever changes again.
if '<section class="process-grid">' not in test_plans.TEST_PLAN_PAGE_HTML:
    script_boundary = "</main>\n<script>"
    if script_boundary not in test_plans.TEST_PLAN_PAGE_HTML:
        raise RuntimeError(
            "Test Plan process UI could not be inserted because the expected "
            "'</main>\\n<script>' boundary was not found."
        )

    process_parts = test_plan_process.PROCESS_HTML.split(
        '<section class="process-grid">',
        1,
    )
    if len(process_parts) != 2:
        raise RuntimeError(
            "Test Plan process UI is missing its process-grid section."
        )

    # Insert Release/Jira scope, run creation, execution rollups, traceability,
    # QA assessment and the report link directly before the page JavaScript.
    process_panels = '<section class="process-grid">' + process_parts[1]
    test_plans.TEST_PLAN_PAGE_HTML = test_plans.TEST_PLAN_PAGE_HTML.replace(
        script_boundary,
        process_panels + "\n</main>\n<script>",
        1,
    )

# Do not allow the application to start with only the backend routes registered
# while the visible Test Plan process UI is silently missing again.
required_test_plan_ui = (
    'class="process-tabs"',
    'id="scope"',
    'id="executions"',
    'id="traceability"',
    'id="assessment"',
    "Open final Test Plan report",
)
missing_test_plan_ui = [
    marker
    for marker in required_test_plan_ui
    if marker not in test_plans.TEST_PLAN_PAGE_HTML
]
if missing_test_plan_ui:
    raise RuntimeError(
        "Test Plan process UI did not initialize correctly. Missing markers: "
        + ", ".join(missing_test_plan_ui)
    )

# Upgrade Test Plans with feature strategy fields, creation-time Jira/Release
# links and an editable QA strategy summary before the final product UI wraps pages.
register_test_plan_strategy(hub)

# Add the End-to-End-specific workspace, coverage metadata, roles, phases,
# Definition of Done and PDF import while reusing the existing Test Plan model.
register_test_plan_e2e(hub, test_plan_strategy)

# Add a downloadable PDF export after all Test Plan/E2E models exist so the
# document can include strategy, coverage, executions, roles, phases and DoD.
register_test_plan_export(hub)

# Add deterministic/AI QA assistance after Test Plan relationship models exist,
# then register the tester-first workspace that consumes those shared facts.
register_qa_intelligence(hub)
register_qa_workflow(hub)

# Register the read-only Help & Documentation page before the shared product shell
# so it receives the normal Test Hub navigation and styling.
register_help_page(hub)

# Keep successful actions in the context where the user performed them. Existing
# redirects that already include a section anchor are preserved unchanged.
_test_plan_redirect_fragments = {
    "add_test_plan_item": "coverage",
    "attach_test_plan_cases": "coverage",
    "attach_test_plan_item_case": "coverage",
    "remove_test_plan_item": "coverage",
    "edit_test_plan_item": "coverage",
    "detach_test_plan_item_case": "coverage",
    "attach_test_plan_release": "scope",
    "remove_test_plan_release": "scope",
    "attach_test_plan_jira": "scope",
    "remove_test_plan_jira": "scope",
}


@hub.app.after_request
def preserve_action_navigation(response):
    if response.status_code not in {301, 302, 303, 307, 308}:
        return response

    endpoint = hub.request.endpoint or ""
    location = response.headers.get("Location", "")
    if not location:
        return response

    # Jira sync errors deliberately return to the Test Cases page where the
    # existing warning UI can display the error message.
    if "jira_sync_error=" in location:
        return response

    fragment = _test_plan_redirect_fragments.get(endpoint)
    if fragment and "#" not in location:
        response.headers["Location"] = location + f"#{fragment}"
        return response

    # Editing or changing status from a Test Case details page should keep the
    # user on that Test Case instead of dropping them back on the full list.
    if endpoint == "update_case":
        case_key = hub.request.form.get("case_key", "").strip().upper()
        if not case_key:
            case_key = (hub.request.view_args or {}).get("case_key", "")
        if case_key:
            response.headers["Location"] = hub.url_for(
                "test_case_details",
                case_key=case_key,
            )
        return response

    if endpoint == "set_status":
        case_key = (hub.request.view_args or {}).get("case_key", "")
        if case_key:
            response.headers["Location"] = hub.url_for(
                "test_case_details",
                case_key=case_key,
            )
        return response

    # When AI Designer created cases for a specific Test Plan, return directly to
    # that plan's coverage instead of losing the user on the general Test Cases list.
    if endpoint == "ai_create_selected_cases":
        test_plan_id = hub.request.form.get("test_plan_id", "").strip()
        if test_plan_id.isdigit():
            response.headers["Location"] = (
                hub.url_for("test_plan_details", plan_id=int(test_plan_id))
                + "#coverage"
            )
        return response

    return response


# Apply the final product design system after every existing page and extension
# has registered so older template patches cannot overwrite the new shell/modals.
register_product_redesign(hub)


if __name__ == "__main__":
    hub.app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "3000")),
        debug=True,
    )
