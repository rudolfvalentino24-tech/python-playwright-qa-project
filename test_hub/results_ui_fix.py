def apply_results_chart_fix(ui_redesign):
    """Fix percentage-based Results Trend bars by giving their parent a height."""
    marker = ".stack{width:100%;display:flex;flex-direction:column-reverse;justify-content:flex-start}"
    replacement = ".stack{width:100%;height:100%;display:flex;flex-direction:column-reverse;justify-content:flex-start}"

    if marker in ui_redesign.RESULTS_PAGE_HTML:
        ui_redesign.RESULTS_PAGE_HTML = ui_redesign.RESULTS_PAGE_HTML.replace(
            marker,
            replacement,
            1,
        )
