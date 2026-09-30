import re


# Cross-page navigation belongs in the shared top navigation. Page-level buttons
# should be reserved for actions that are specific to the current page.
_DUPLICATE_NAV_LABELS = (
    "All test cases",
    "Test cases",
    "Test Runs",
    "Releases",
    "All test runs",
    "All releases",
)


def _remove_duplicate_buttons(template):
    if not template:
        return template

    cleaned = template
    for label in _DUPLICATE_NAV_LABELS:
        cleaned = re.sub(
            rf'<a\s+class="button(?:\s+[^\"]*)?"[^>]*>\s*{re.escape(label)}\s*</a>',
            "",
            cleaned,
            flags=re.IGNORECASE,
        )

    # Remove page-action containers that became empty after duplicate links were
    # removed. These patterns deliberately do not match the shared top nav.
    cleaned = re.sub(
        r'<div\s+class="actions">\s*</div>',
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r'<div\s+style="display:flex;gap:8px;flex-wrap:wrap">\s*</div>',
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    return cleaned


def register_ui_cleanup(hub):
    # These are the legacy page templates that receive the shared navigation
    # shell at startup. Clean their old cross-page button rows afterwards.
    for name in (
        "STORY_PAGE_HTML",
        "TEST_RUNS_PAGE_HTML",
        "TEST_RUN_PAGE_HTML",
        "RELEASES_PAGE_HTML",
        "RELEASE_PAGE_HTML",
        "CASE_PAGE_HTML",
        "EDIT_PAGE_HTML",
    ):
        if hasattr(hub, name):
            setattr(hub, name, _remove_duplicate_buttons(getattr(hub, name)))
