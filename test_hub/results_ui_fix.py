from datetime import datetime, timedelta, timezone

from flask import request


def _aware(value):
    # Normalize stored datetimes before comparing them with the selected Results range.
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def apply_results_chart_fix(hub, ui_redesign):
    """Fix Results chart layout and expose runner-error statistics."""
    marker = ".stack{width:100%;display:flex;flex-direction:column-reverse;justify-content:flex-start}"
    replacement = ".stack{width:100%;height:100%;display:flex;flex-direction:column-reverse;justify-content:flex-start}"

    # Keep the existing Results Trend height fix so percentage bars render correctly.
    if marker in ui_redesign.RESULTS_PAGE_HTML:
        ui_redesign.RESULTS_PAGE_HTML = ui_redesign.RESULTS_PAGE_HTML.replace(
            marker,
            replacement,
            1,
        )

    metrics_marker = '<div class="metric"><div class="label">Pass Rate</div><div class="value green">{{ metrics.pass_rate }}%</div><div class="note">Passed / passed + failed</div></div>'
    run_errors_card = (
        '<div class="metric"><div class="label">Run Errors</div>'
        '<div class="value red">{{ test_hub_run_error_count() }}</div>'
        '<div class="note">Jenkins / pytest runner errors</div></div>'
    )

    # Add a separate runner-error metric without mixing infrastructure failures
    # into real test-case failures or the product pass-rate calculation.
    if run_errors_card not in ui_redesign.RESULTS_PAGE_HTML and metrics_marker in ui_redesign.RESULTS_PAGE_HTML:
        ui_redesign.RESULTS_PAGE_HTML = ui_redesign.RESULTS_PAGE_HTML.replace(
            metrics_marker,
            run_errors_card + metrics_marker,
            1,
        )
        ui_redesign.RESULTS_PAGE_HTML = ui_redesign.RESULTS_PAGE_HTML.replace(
            "grid-template-columns:repeat(6,1fr)",
            "grid-template-columns:repeat(7,1fr)",
            1,
        )

    def test_hub_run_error_count():
        # Count only structured runs in the same date range currently selected
        # on the Results dashboard.
        try:
            range_days = int(request.args.get("range", "30"))
        except ValueError:
            range_days = 30
        if range_days not in {0, 7, 30, 90}:
            range_days = 30

        runs = hub.db.session.scalars(
            hub.db.select(hub.TestRun).order_by(hub.TestRun.created_at.desc())
        ).all()
        runs = [run for run in runs if run.items]

        if range_days:
            cutoff = datetime.now(timezone.utc) - timedelta(days=range_days)
            runs = [
                run for run in runs
                if _aware(run.created_at) and _aware(run.created_at) >= cutoff
            ]

        return sum(1 for run in runs if run.execution_status == "Error")

    # Make the runner-error count available to the Results Jinja template.
    hub.app.jinja_env.globals["test_hub_run_error_count"] = test_hub_run_error_count
