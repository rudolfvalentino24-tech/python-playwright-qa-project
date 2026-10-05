HELP_PAGE = r'''
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Help & Documentation - Test Hub</title>
<style>
.help-head{display:flex;justify-content:space-between;gap:16px;align-items:flex-start;margin-bottom:18px}.help-head h1{margin:0}.help-sub{margin-top:6px;color:#667085;font-size:13px;line-height:1.5}.help-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.help-card{padding:18px;border:1px solid #e4e7ec;border-radius:12px;background:#fff}.help-card h2{margin:0 0 7px;font-size:17px}.help-card h3{margin:16px 0 7px;font-size:13px}.help-card p,.help-card li{color:#667085;font-size:11px;line-height:1.55}.help-card ul{margin:7px 0 0;padding-left:18px}.help-flow{margin:10px 0 0;padding:14px;border:1px solid #dbe5f1;border-radius:10px;background:#f8fbff;color:#344054;font:600 11px/1.75 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;white-space:pre-wrap}.help-topic-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px;margin-top:10px}.help-topic{padding:12px;border:1px solid #e4e7ec;border-radius:9px;background:#fcfcfd}.help-topic strong{display:block;color:#344054;font-size:11px}.help-topic span{display:block;margin-top:4px;color:#667085;font-size:10px;line-height:1.45}.help-links{display:grid;gap:8px;margin-top:10px}.help-link{display:block;padding:12px;border:1px solid #d0d5dd;border-radius:9px;background:#fff;color:#344054;text-decoration:none}.help-link strong{display:block;font-size:11px}.help-link span{display:block;margin-top:3px;color:#667085;font-size:10px}.help-link:hover{border-color:#84adff;background:#f8fbff}.help-glossary{display:grid;grid-template-columns:150px 1fr;gap:7px 12px;margin-top:10px}.help-glossary dt{font-size:10px;font-weight:850;color:#344054}.help-glossary dd{margin:0;color:#667085;font-size:10px;line-height:1.5}.help-note{margin-top:14px;padding:11px 12px;border-radius:9px;background:#f2f4f7;color:#475467;font-size:10px;line-height:1.5}@media(max-width:900px){.help-grid{grid-template-columns:1fr}.help-topic-grid{grid-template-columns:1fr 1fr}}@media(max-width:600px){.help-topic-grid{grid-template-columns:1fr}.help-glossary{grid-template-columns:1fr}.help-head{flex-direction:column}}
</style>
</head>
<body>
<main class="th-page">
  <div class="help-head">
    <div>
      <h1>Help & Documentation</h1>
      <div class="help-sub">Understand how Test Hub works, what each QA object means, and where to find the wider Jira, GitHub, Jenkins, Python and Playwright workflow.</div>
    </div>
  </div>

  <div class="help-grid">
    <section class="help-card">
      <h2>Getting started</h2>
      <p>Test Hub connects requirements, test planning, Test Cases, execution evidence, defects, retesting and release readiness into one QA workspace.</p>
      <div class="help-flow">Jira Story
    ↓
Test Plan
    ↓
Planned Coverage
    ↓
Test Cases
    ↓
Test Run
    ↓
Results
    ↓
Defect / Retest
    ↓
QA Sign-off</div>
      <div class="help-note">The Release is the delivery target throughout this flow. A Sprint is the timebox in which part of that Release scope is developed and tested.</div>
    </section>

    <section class="help-card">
      <h2>Core concepts</h2>
      <dl class="help-glossary">
        <dt>Test Plan</dt><dd>What QA intends to validate for a feature, regression effort, release, smoke cycle, exploratory effort or end-to-end journey.</dd>
        <dt>Planned Coverage</dt><dd>A required scenario in the Test Plan. It may exist before the actual Test Case is created.</dd>
        <dt>Test Case</dt><dd>A concrete reusable test with steps, expected behaviour, metadata and optional automation.</dd>
        <dt>Test Run</dt><dd>A specific execution of selected Test Cases against an environment and, when applicable, a Release.</dd>
        <dt>Release</dt><dd>The delivery target whose quality and readiness QA is evaluating.</dd>
        <dt>Sprint</dt><dd>The development timebox containing the work currently being built and tested.</dd>
        <dt>Blocked</dt><dd>A test that cannot currently be completed because of an environment, data, dependency, access, defect or requirement problem.</dd>
        <dt>Retest</dt><dd>Re-execution after a failed result has been fixed or is otherwise ready for verification.</dd>
      </dl>
    </section>

    <section class="help-card" style="grid-column:1/-1">
      <h2>Help topics</h2>
      <div class="help-topic-grid">
        <div class="help-topic"><strong>Test Plans</strong><span>Define strategy, Jira scope, Release scope, risks, criteria and planned coverage before execution.</span></div>
        <div class="help-topic"><strong>Test Cases</strong><span>Create reusable positive, negative, boundary, regression, accessibility and other concrete tests.</span></div>
        <div class="help-topic"><strong>Test Runs</strong><span>Execute manual or automated scope in a specific environment and keep the evidence linked to the plan.</span></div>
        <div class="help-topic"><strong>Results</strong><span>Review Passed, Failed, Blocked and Skipped outcomes together with failure evidence and Jenkins artifacts.</span></div>
        <div class="help-topic"><strong>Release Readiness</strong><span>Evaluate execution completeness, failures, blockers, high-risk coverage and smoke status before QA sign-off.</span></div>
        <div class="help-topic"><strong>Jira & Requirements</strong><span>Use refinement and Definition of Ready before turning a Story into Test Plan coverage and Test Cases.</span></div>
      </div>
    </section>

    <section class="help-card" style="grid-column:1/-1">
      <h2>Full documentation</h2>
      <p>Use these sources when you need more detail than the in-app Help page provides.</p>
      <div class="help-links">
        <a class="help-link" href="https://github.com/rudolfvalentino24-tech/python-playwright-qa-project/blob/feature/test-case-management/docs/TEST_HUB_GUIDE.md" target="_blank" rel="noopener noreferrer"><strong>Test Hub Guide — GitHub</strong><span>Detailed application guide for Test Plans, Test Cases, Test Runs, Results, Retesting, Release Readiness and QA intelligence.</span></a>
        <a class="help-link" href="https://github.com/rudolfvalentino24-tech/python-playwright-qa-project/blob/feature/test-case-management/docs/QA_WORKFLOW.md" target="_blank" rel="noopener noreferrer"><strong>QA Workflow Guide — GitHub</strong><span>End-to-end process across Jira, Test Hub, GitHub, Jenkins, Python, pytest-bdd and Playwright.</span></a>
        <a class="help-link" href="https://qa-test-store.atlassian.net/wiki/spaces/QA" target="_blank" rel="noopener noreferrer"><strong>QA & Quality Engineering — Confluence</strong><span>Team-facing QA knowledge portal, onboarding, workflow guidance and live Jira context.</span></a>
      </div>
    </section>
  </div>
</main>
</body>
</html>
'''


def register_help_page(hub):
    """Register one read-only Help page without adding data models or write actions."""
    if getattr(hub.app, "_help_page_registered", False):
        return

    # Keep product guidance available inside Test Hub without duplicating the full manuals.
    @hub.app.get("/help")
    def help_documentation():
        return hub.render_template_string(HELP_PAGE)

    hub.app._help_page_registered = True
