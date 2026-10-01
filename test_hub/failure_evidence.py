def _split_failure_notes(notes):
    # Keep the first line as the human-readable reason and extract the
    # optional Jenkins artifact path written by the pytest-bdd reporter.
    reason_lines = []
    screenshot_path = ""

    for raw_line in str(notes or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("Screenshot:"):
            screenshot_path = line.split(":", 1)[1].strip()
        else:
            reason_lines.append(line)

    return {
        "reason": " ".join(reason_lines).strip(),
        "screenshot_path": screenshot_path,
    }


def register_failure_evidence(hub):
    """Add readable failure evidence to the Test Run details page."""
    if getattr(hub.app, "_failure_evidence_registered", False):
        return

    def test_hub_failure_reason(result):
        # Show a concise QA-facing reason above the full pytest traceback.
        return _split_failure_notes(getattr(result, "notes", ""))["reason"]

    def test_hub_failure_screenshot_url(result):
        details = _split_failure_notes(getattr(result, "notes", ""))
        screenshot_path = details["screenshot_path"]
        build_url = str(getattr(result, "runner_build_url", "") or "").rstrip("/")

        if not screenshot_path or not build_url:
            return ""

        # Jenkins archives test-results/**, so the stable relative path can be
        # linked directly from the build's artifact endpoint.
        normalized_path = screenshot_path.replace("\\", "/").lstrip("/")
        return f"{build_url}/artifact/{normalized_path}"

    # Expose helpers to the existing Jinja template without changing the database.
    hub.app.jinja_env.globals["test_hub_failure_reason"] = test_hub_failure_reason
    hub.app.jinja_env.globals["test_hub_failure_screenshot_url"] = test_hub_failure_screenshot_url

    evidence_css = """
<style>
.failure-summary{margin-top:8px;padding:10px 12px;border:1px solid #fecaca;border-radius:10px;background:#fff7f7;color:#7f1d1d;font-size:12px;line-height:1.45}.failure-summary strong{display:block;margin-bottom:3px;color:#991b1b}.failure-evidence-links{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px}.failure-evidence-links a{display:inline-flex;align-items:center;padding:6px 9px;border-radius:8px;background:#fff1f2;color:#b42318;text-decoration:none;font-size:11px;font-weight:800}.failure-evidence-links a:hover{background:#ffe4e6}
</style>
"""

    if ".failure-summary{" not in hub.TEST_RUN_PAGE_HTML:
        hub.TEST_RUN_PAGE_HTML = hub.TEST_RUN_PAGE_HTML.replace(
            "</head>",
            evidence_css + "</head>",
            1,
        )

    marker = '''          {% if row.result and row.result.notes %}<div class="muted">{{ row.result.notes }}</div>{% endif %}
          {% if row.result and row.result.error_message %}
            <details class="muted" style="margin-top:7px">
              <summary style="cursor:pointer;font-weight:750;color:#991b1b">Failure details</summary>
              <pre style="white-space:pre-wrap;overflow:auto;margin:7px 0 0">{{ row.result.error_message }}</pre>
            </details>
          {% endif %}'''

    replacement = '''          {% if row.result and row.status == 'Failed' %}
            {% set failure_reason = test_hub_failure_reason(row.result) %}
            {% set screenshot_url = test_hub_failure_screenshot_url(row.result) %}
            {% if failure_reason %}
              <div class="failure-summary"><strong>Reason</strong>{{ failure_reason }}</div>
            {% endif %}
            {% if screenshot_url or row.result.runner_build_url %}
              <div class="failure-evidence-links">
                {% if screenshot_url %}<a href="{{ screenshot_url }}" target="_blank">📷 Failure screenshot</a>{% endif %}
                {% if row.result.runner_build_url %}<a href="{{ row.result.runner_build_url }}" target="_blank">↗ Jenkins build</a>{% endif %}
              </div>
            {% endif %}
          {% elif row.result and row.result.notes %}
            <div class="muted">{{ row.result.notes }}</div>
          {% endif %}
          {% if row.result and row.result.error_message %}
            <details class="muted" style="margin-top:7px">
              <summary style="cursor:pointer;font-weight:750;color:#991b1b">Full traceback</summary>
              <pre style="white-space:pre-wrap;overflow:auto;margin:7px 0 0">{{ row.result.error_message }}</pre>
            </details>
          {% endif %}'''

    # Replace the old generic failure block with a QA-facing summary, evidence
    # links, and the original full traceback underneath.
    if marker in hub.TEST_RUN_PAGE_HTML:
        hub.TEST_RUN_PAGE_HTML = hub.TEST_RUN_PAGE_HTML.replace(marker, replacement, 1)

    hub.app._failure_evidence_registered = True
