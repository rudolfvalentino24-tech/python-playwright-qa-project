import os
from pathlib import Path

from dotenv import load_dotenv

# Load local secrets/configuration before app.py reads environment variables.
load_dotenv(Path(__file__).with_name(".env"), override=False)

import app as hub
import bdd_sync
import ai_automation
import ai_designer
import ui_redesign
from ai_automation import register_ai_automation
from ai_automation_guard import apply_ai_automation_guard
from ai_designer import register_ai_designer
from ai_usage import apply_ai_usage_tracking, apply_ai_usage_ui
from jira_ui_fix import apply_jira_modal_error_fix
from results_ui_fix import apply_results_chart_fix
from run_guards import register_run_guards
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

register_ui_redesign(hub, ai_designer, bdd_sync)
register_ui_cleanup(hub)
register_run_guards(hub)


if __name__ == "__main__":
    hub.app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "3000")),
        debug=True,
    )
