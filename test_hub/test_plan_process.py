from datetime import datetime, timezone
from functools import wraps


QA_ASSESSMENTS = {"Not Assessed", "Ready", "At Risk", "Incomplete"}


PROCESS_CSS = r'''
.process-tabs{display:flex;gap:7px;flex-wrap:wrap;margin:0 0 18px;padding:8px;border:1px solid #dce6f4;border-radius:12px;background:#fff}.process-tabs a{padding:8px 11px;border-radius:8px;color:#315275;text-decoration:none;font-size:11px;font-weight:850}.process-tabs a:hover{background:#eef5ff;color:#0b5de8}.process-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:18px}.process-card{padding:20px}.process-card h2{margin:0 0 12px;font-size:18px;color:#16345e}.process-card h3{margin:16px 0 8px;font-size:13px;color:#26476b}.process-help{margin:-5px 0 12px;color:#71829a;font-size:11px;line-height:1.45}.process-row{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:9px 0;border-top:1px solid #e9eef6}.process-row:first-of-type{border-top:0}.process-main{min-width:0}.process-title{font-size:12px;font-weight:900;color:#17325d}.process-meta{margin-top:3px;color:#71829a;font-size:10px}.process-actions{display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end}.process-form{display:grid;gap:8px}.process-form label{display:block;color:#314d6c;font-size:10px;font-weight:900}.process-form input,.process-form select,.process-form textarea{width:100%;border:1px solid #ccd9eb;border-radius:8px;background:#fff;color:#183252;font:inherit;font-size:11px;outline:none}.process-form input,.process-form select{height:38px;padding:0 9px}.process-form textarea{min-height:72px;padding:8px 9px;resize:vertical}.process-inline{display:flex;gap:7px;align-items:center}.process-inline>*{flex:1}.process-inline button,.process-inline a{flex:0 0 auto}.process-badge{display:inline-flex;align-items:center;padding:4px 8px;border-radius:999px;background:#edf2f8;color:#4b607a;font-size:10px;font-weight:850;text-decoration:none}.process-badge.pass{background:#dcfce7;color:#166534}.process-badge.fail{background:#fee2e2;color:#991b1b}.process-badge.block{background:#fef3c7;color:#92400e}.process-badge.pending{background:#fff4d6;color:#8a5b00}.process-badge.jira{background:#e8f1ff;color:#1763d8}.trace-wrap{overflow:auto}.trace-table{width:100%;border-collapse:collapse;font-size:10px}.trace-table th,.trace-table td{padding:9px 8px;border-top:1px solid #e7edf6;text-align:left;vertical-align:top}.trace-table th{border-top:0;background:#f7faff;color:#536b87;font-weight:900}.trace-table a{color:#1763d8;text-decoration:none;font-weight:800}.trace-form{display:flex;gap:5px;margin-top:6px}.trace-form input{min-width:105px;height:30px;padding:0 7px;border:1px solid #ccd9eb;border-radius:7px;font-size:10px}.trace-form button{padding:6px 8px}.execution-stats{display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin:10px 0 14px}.execution-stat{padding:10px;border-radius:9px;background:#f7faff}.execution-stat strong{display:block;font-size:16px;color:#17325d}.execution-stat span{display:block;margin-top:2px;color:#71829a;font-size:9px;font-weight:750}.run-case-list{max-height:250px;overflow:auto;border:1px solid #dce6f3;border-radius:9px}.run-case{display:flex;gap:7px;padding:8px;border-top:1px solid #edf1f6}.run-case:first-child{border-top:0}.run-case input{width:15px;height:15px;margin:2px 0 0}.run-case strong{display:block;font-size:10px;color:#243854}.run-case span{font-size:9px;color:#71829a}.assessment{display:grid;grid-template-columns:180px 1fr auto;gap:8px;align-items:end}.assessment select,.assessment textarea{width:100%;border:1px solid #ccd9eb;border-radius:8px;background:#fff;font:inherit;font-size:11px}.assessment select{height:38px;padding:0 8px}.assessment textarea{min-height:60px;padding:8px;resize:vertical}.report-link{display:inline-flex;margin-top:10px}.wide{grid-column:1/-1}@media(max-width:1000px){.process-grid{grid-template-columns:1fr}.wide{grid-column:auto}.execution-stats{grid-template-columns:repeat(3,1fr)}}@media(max-width:650px){.process-inline,.assessment{display:flex;flex-direction:column;align-items:stretch}.execution-stats{grid-template-columns:1fr 1fr}.process-row{align-items:flex-start;flex-direction:column}.process-actions{justify-content:flex-start}}
'''


PROCESS_HTML = r'''
<nav class="process-tabs" aria-label="Test Plan sections">
  <a href="#overview">Overview</a>
  <a href="#coverage">Coverage</a>
  <a href="#executions">Executions</a>
  <a href="#traceability">Traceability</a>
  <a href="{{ url_for('test_plan_report', plan_id=plan.id) }}">Report</a>
</nav>

<section class="process-grid">
  <article class="th-card process-card" id="scope">
    <h2>Process scope</h2>
    <div class="process-help">Connect this Test Plan to the release and Jira requirements it is responsible for validating.</div>

    <h3>Releases</h3>
    {% for release in process.releases %}
      <div class="process-row">
        <div class="process-main"><a class="process-title" href="{{ url_for('release_details', release_id=release.id) }}">{{ release.version }}</a><div class="process-meta">{{ release.environment or 'No environment' }}{% if release.release_date %} · {{ release.release_date.strftime('%d %b %Y') }}{% endif %}</div></div>
        <form method="post" action="{{ url_for('remove_test_plan_release', plan_id=plan.id, release_id=release.id) }}"><button class="danger">Unlink</button></form>
      </div>
    {% else %}<div class="process-help">No release linked yet.</div>{% endfor %}
    {% if process.available_releases %}
      <form class="process-inline" method="post" action="{{ url_for('attach_test_plan_release', plan_id=plan.id) }}">
        <select name="release_id" required><option value="">Attach Release…</option>{% for release in process.available_releases %}<option value="{{ release.id }}">{{ release.version }}{% if release.environment %} · {{ release.environment }}{% endif %}</option>{% endfor %}</select>
        <button class="secondary">Attach</button>
      </form>
    {% endif %}

    <h3>Jira scope</h3>
    <div class="process-help">These stories define the requirements in scope for this plan.</div>
    <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px">
      {% for jira_key in process.jira_scope %}
        <span class="process-badge jira"><a href="{{ url_for('jira_story_cases', jira_key=jira_key) }}">{{ jira_key }}</a>&nbsp;
          <form style="display:inline" method="post" action="{{ url_for('remove_test_plan_jira', plan_id=plan.id, jira_key=jira_key) }}"><button title="Remove Jira scope" style="border:0;background:none;color:#b42318;cursor:pointer;font-weight:900">×</button></form>
        </span>
      {% else %}<span class="process-help">No Jira requirements linked.</span>{% endfor %}
    </div>
    <form class="process-inline" method="post" action="{{ url_for('attach_test_plan_jira', plan_id=plan.id) }}">
      <input name="jira_keys" required placeholder="SCRUM-101, SCRUM-102">
      <button class="secondary">Add Jira scope</button>
    </form>
  </article>

  <article class="th-card process-card" id="create-plan-run">
    <h2>Create Test Run from Plan</h2>
    <div class="process-help">Reuse the covered Test Cases from this plan. The new run stays linked to the plan and uses the existing Jenkins/Playwright workflow.</div>
    {% if process.covered_cases %}
      <form class="process-form" method="post" action="{{ url_for('create_test_plan_run', plan_id=plan.id) }}">
        <label>Name<input name="name" required value="{{ plan.name }} — Regression"></label>
        <div class="process-inline">
          <label>Execution type<select name="execution_type"><option>Automated</option><option>Manual</option></select></label>
          <label>Environment<input name="environment" placeholder="Staging"></label>
        </div>
        <label>Release<select name="release_id"><option value="">No release</option>{% for release in process.releases %}<option value="{{ release.id }}">{{ release.version }}</option>{% endfor %}</select></label>
        <label>Covered Test Cases</label>
        <div class="run-case-list">
          {% for case in process.covered_cases %}
            <label class="run-case"><input type="checkbox" name="case_ids" value="{{ case.id }}" checked><span><strong>{{ case.case_key }} — {{ case.title }}</strong>{{ case.feature_name }} · {{ case.type }}</span></label>
          {% endfor %}
        </div>
        <button class="primary" type="submit">Create Test Run</button>
      </form>
    {% else %}<div class="process-help">Attach Test Cases to the coverage checklist before creating a run.</div>{% endif %}
  </article>

  <article class="th-card process-card wide" id="executions">
    <h2>Executions</h2>
    <div class="execution-stats">
      <div class="execution-stat"><strong>{{ process.execution.total }}</strong><span>Covered cases</span></div>
      <div class="execution-stat"><strong>{{ process.execution.executed }}</strong><span>Executed</span></div>
      <div class="execution-stat"><strong>{{ process.execution.passed }}</strong><span>Passed</span></div>
      <div class="execution-stat"><strong>{{ process.execution.failed }}</strong><span>Failed</span></div>
      <div class="execution-stat"><strong>{{ process.execution.not_run }}</strong><span>Not Run</span></div>
      <div class="execution-stat"><strong>{{ process.execution.pass_rate }}%</strong><span>Pass rate</span></div>
    </div>

    {% for row in process.run_rows %}
      <div class="process-row">
        <div class="process-main"><a class="process-title" href="{{ url_for('test_run_details', run_id=row.run.id) }}">{{ row.run.name }}</a><div class="process-meta">{{ row.run.execution_type }} · {{ row.run.execution_status }}{% if row.run.environment %} · {{ row.run.environment }}{% endif %}{% if row.run.release %} · Release {{ row.run.release.version }}{% endif %} · {{ row.summary.executed }}/{{ row.summary.total }} executed</div></div>
        <div class="process-actions"><span class="process-badge {% if row.summary.failed %}fail{% elif row.summary.not_run %}pending{% else %}pass{% endif %}">{{ row.summary.pass_rate }}% pass</span>{% if row.run.jenkins_build_url %}<a class="secondary" target="_blank" href="{{ row.run.jenkins_build_url }}">Jenkins</a>{% endif %}<form method="post" action="{{ url_for('remove_test_plan_run', plan_id=plan.id, run_id=row.run.id) }}"><button class="danger">Unlink</button></form></div>
      </div>
    {% else %}<div class="process-help">No Test Runs linked yet.</div>{% endfor %}

    {% if process.available_runs %}
      <h3>Attach an existing Test Run</h3>
      <form class="process-inline" method="post" action="{{ url_for('attach_existing_test_plan_run', plan_id=plan.id) }}">
        <select name="run_id" required><option value="">Select Test Run…</option>{% for run in process.available_runs %}<option value="{{ run.id }}">{{ run.name }} · {{ run.execution_status }}</option>{% endfor %}</select>
        <button class="secondary">Attach</button>
      </form>
    {% endif %}
  </article>

  <article class="th-card process-card wide" id="traceability">
    <h2>Traceability</h2>
    <div class="process-help">Requirement → planned coverage → Test Case → latest execution → defect.</div>
    <div class="trace-wrap"><table class="trace-table">
      <thead><tr><th>Jira requirement</th><th>Planned coverage</th><th>Test Case</th><th>Latest result</th><th>Defect / evidence</th></tr></thead>
      <tbody>
      {% for row in process.traceability %}
        <tr>
          <td>
            {% for jira_key in row.jira_keys %}<a href="{{ url_for('jira_story_cases', jira_key=jira_key) }}">{{ jira_key }}</a>{% if not loop.last %}, {% endif %}{% endfor %}
            {% if not row.jira_keys %}<span class="process-badge pending">Unmapped</span>{% endif %}
            <form class="trace-form" method="post" action="{{ url_for('attach_test_plan_item_jira', plan_id=plan.id, item_id=row.item.id) }}"><input name="jira_key" placeholder="SCRUM-101"><button class="secondary">Link</button></form>
          </td>
          <td><strong>{{ row.item.title_snapshot }}</strong><div class="process-meta">{{ row.item.feature_snapshot }}</div></td>
          <td>{% if row.test_case %}<a href="{{ url_for('test_case_details', case_key=row.test_case.case_key) }}">{{ row.test_case.case_key }}</a><div class="process-meta">{{ row.test_case.title }}</div>{% else %}<span class="process-badge pending">Pending</span>{% endif %}</td>
          <td>{% if row.result %}<span class="process-badge {% if row.result.result == 'Passed' %}pass{% elif row.result.result == 'Failed' %}fail{% elif row.result.result == 'Blocked' %}block{% endif %}">{{ row.result.result }}</span><div class="process-meta">{{ row.result.executed_at.strftime('%d %b %Y %H:%M') }}</div>{% else %}<span class="process-badge pending">Not Run</span>{% endif %}</td>
          <td>
            {% for defect in row.defects %}<a class="process-badge fail" target="_blank" href="{{ jira_base }}/{{ defect.jira_key }}">{{ defect.jira_key }}</a>{% endfor %}
            {% if row.result and row.result.result == 'Failed' %}<form class="trace-form" method="post" action="{{ url_for('link_test_result_defect', result_id=row.result.id) }}"><input type="hidden" name="plan_id" value="{{ plan.id }}"><input name="jira_key" placeholder="BUG-248"><button class="secondary">Link defect</button></form>{% endif %}
            {% if row.result and row.result.runner_build_url %}<div style="margin-top:5px"><a target="_blank" href="{{ row.result.runner_build_url }}">Jenkins evidence ↗</a></div>{% endif %}
          </td>
        </tr>
      {% endfor %}
      </tbody>
    </table></div>
  </article>

  <article class="th-card process-card wide" id="assessment">
    <h2>QA assessment</h2>
    <div class="process-help">The decision is intentionally manual. Test Hub provides the facts; QA records the release recommendation.</div>
    <form class="assessment" method="post" action="{{ url_for('update_test_plan_assessment', plan_id=plan.id) }}">
      <label>Status<select name="qa_status">{% for value in qa_assessments %}<option {% if value == process.assessment.qa_status %}selected{% endif %}>{{ value }}</option>{% endfor %}</select></label>
      <label>Notes<textarea name="notes" placeholder="Known risks, release recommendation, blockers…">{{ process.assessment.notes }}</textarea></label>
      <button class="primary">Save assessment</button>
    </form>
    <a class="primary report-link" href="{{ url_for('test_plan_report', plan_id=plan.id) }}">Open final Test Plan report</a>
  </article>
</section>
'''


REPORT_HTML = r'''
<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{{ plan.name }} Report - Test Hub</title><style>
{{ shell_css|safe }}
*{box-sizing:border-box}body{margin:0;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.report{max-width:1200px;margin:0 auto;padding:28px}.report-head{display:flex;justify-content:space-between;gap:18px;align-items:flex-start;margin-bottom:20px}.report-head h1{margin:0;font-size:30px}.muted{color:#71829a;font-size:11px}.report-actions{display:flex;gap:8px}.button{border:0;border-radius:9px;padding:9px 12px;background:#eef3fa;color:#284566;text-decoration:none;font:inherit;font-size:11px;font-weight:850;cursor:pointer}.stats{display:grid;grid-template-columns:repeat(6,1fr);gap:9px;margin-bottom:16px}.stat{padding:13px;border:1px solid #dce6f4;border-radius:12px;background:#fff}.stat strong{display:block;font-size:21px;color:#17325d}.stat span{font-size:9px;color:#71829a;font-weight:800}.card{padding:18px;margin-top:14px;border:1px solid #dce6f4;border-radius:14px;background:#fff}.card h2{margin:0 0 11px;font-size:17px;color:#16345e}.chips{display:flex;gap:6px;flex-wrap:wrap}.chip{padding:5px 8px;border-radius:999px;background:#edf2f8;color:#4b607a;font-size:10px;font-weight:850}.chip.good{background:#dcfce7;color:#166534}.chip.bad{background:#fee2e2;color:#991b1b}.chip.warn{background:#fff4d6;color:#8a5b00}.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse;font-size:10px}th,td{padding:9px 8px;border-top:1px solid #e7edf6;text-align:left;vertical-align:top}th{border-top:0;background:#f7faff;color:#536b87}a{color:#1763d8;text-decoration:none;font-weight:800}@media print{.th-nav,.report-actions{display:none!important}.report{padding:0}.card,.stat{box-shadow:none}}@media(max-width:800px){.stats{grid-template-columns:1fr 1fr}.report-head{flex-direction:column}}
</style></head><body>{{ nav_html|safe }}<main class="report">
<div class="report-head"><div><h1>{{ plan.name }}</h1><div class="muted">Final QA Test Plan report · {{ generated_at.strftime('%d %b %Y %H:%M UTC') }}</div></div><div class="report-actions"><a class="button" href="{{ url_for('test_plan_details', plan_id=plan.id) }}">Back to plan</a><button class="button" onclick="window.print()">Print / Save PDF</button></div></div>
<div class="stats"><div class="stat"><strong>{{ coverage.total }}</strong><span>Planned</span></div><div class="stat"><strong>{{ coverage.created }}</strong><span>Covered</span></div><div class="stat"><strong>{{ coverage.pending }}</strong><span>Pending</span></div><div class="stat"><strong>{{ execution.executed }}</strong><span>Executed</span></div><div class="stat"><strong>{{ execution.failed }}</strong><span>Failed</span></div><div class="stat"><strong>{{ execution.pass_rate }}%</strong><span>Pass rate</span></div></div>
<section class="card"><h2>Scope and QA assessment</h2><div class="chips"><span class="chip">Plan: {{ plan.status }}</span><span class="chip {% if assessment.qa_status == 'Ready' %}good{% elif assessment.qa_status == 'At Risk' %}bad{% else %}warn{% endif %}">QA: {{ assessment.qa_status }}</span>{% for release in releases %}<a class="chip" href="{{ url_for('release_details', release_id=release.id) }}">Release {{ release.version }}</a>{% endfor %}{% for jira_key in jira_scope %}<a class="chip" href="{{ url_for('jira_story_cases', jira_key=jira_key) }}">{{ jira_key }}</a>{% endfor %}</div>{% if assessment.notes %}<p>{{ assessment.notes }}</p>{% endif %}</section>
<section class="card"><h2>Execution history</h2>{% for row in run_rows %}<div style="padding:8px 0;border-top:1px solid #e7edf6"><a href="{{ url_for('test_run_details', run_id=row.run.id) }}">{{ row.run.name }}</a> — {{ row.run.execution_status }} · {{ row.summary.executed }}/{{ row.summary.total }} executed · {{ row.summary.pass_rate }}% pass{% if row.run.jenkins_build_url %} · <a target="_blank" href="{{ row.run.jenkins_build_url }}">Jenkins</a>{% endif %}</div>{% else %}<div class="muted">No linked Test Runs.</div>{% endfor %}</section>
<section class="card"><h2>Traceability matrix</h2><div class="table-wrap"><table><thead><tr><th>Requirement</th><th>Planned coverage</th><th>Test Case</th><th>Latest result</th><th>Defect</th></tr></thead><tbody>{% for row in traceability %}<tr><td>{% for jira_key in row.jira_keys %}<a href="{{ url_for('jira_story_cases', jira_key=jira_key) }}">{{ jira_key }}</a>{% if not loop.last %}, {% endif %}{% endfor %}{% if not row.jira_keys %}—{% endif %}</td><td>{{ row.item.title_snapshot }}</td><td>{% if row.test_case %}<a href="{{ url_for('test_case_details', case_key=row.test_case.case_key) }}">{{ row.test_case.case_key }}</a>{% else %}Pending{% endif %}</td><td>{{ row.result.result if row.result else 'Not Run' }}</td><td>{% for defect in row.defects %}<a target="_blank" href="{{ jira_base }}/{{ defect.jira_key }}">{{ defect.jira_key }}</a>{% if not loop.last %}, {% endif %}{% endfor %}{% if not row.defects %}—{% endif %}</td></tr>{% endfor %}</tbody></table></div></section>
</main></body></html>
'''


def register_test_plan_process(test_plans, hub, ui_redesign):
    """Connect Test Plans to Releases, Jira, Runs, Results, defects, and reports."""
    if getattr(hub.app, "_test_plan_process_registered", False):
        return

    class TestPlanReleaseLink(hub.db.Model):
        __tablename__ = "test_plan_release_links"
        __table_args__ = (hub.UniqueConstraint("test_plan_id", "release_id", name="uq_test_plan_release"),)
        id = hub.db.Column(hub.db.Integer, primary_key=True)
        test_plan_id = hub.db.Column(hub.db.Integer, hub.db.ForeignKey("test_plans.id", ondelete="CASCADE"), nullable=False, index=True)
        release_id = hub.db.Column(hub.db.Integer, hub.db.ForeignKey("releases.id", ondelete="CASCADE"), nullable=False, index=True)

    class TestPlanJiraLink(hub.db.Model):
        __tablename__ = "test_plan_jira_links"
        __table_args__ = (hub.UniqueConstraint("test_plan_id", "jira_key", name="uq_test_plan_jira"),)
        id = hub.db.Column(hub.db.Integer, primary_key=True)
        test_plan_id = hub.db.Column(hub.db.Integer, hub.db.ForeignKey("test_plans.id", ondelete="CASCADE"), nullable=False, index=True)
        jira_key = hub.db.Column(hub.db.String(50), nullable=False, index=True)

    class TestPlanItemJiraLink(hub.db.Model):
        __tablename__ = "test_plan_item_jira_links"
        __table_args__ = (hub.UniqueConstraint("test_plan_item_id", "jira_key", name="uq_test_plan_item_jira"),)
        id = hub.db.Column(hub.db.Integer, primary_key=True)
        test_plan_item_id = hub.db.Column(hub.db.Integer, hub.db.ForeignKey("test_plan_items.id", ondelete="CASCADE"), nullable=False, index=True)
        jira_key = hub.db.Column(hub.db.String(50), nullable=False, index=True)

    class TestPlanRunLink(hub.db.Model):
        __tablename__ = "test_plan_run_links"
        __table_args__ = (hub.UniqueConstraint("test_plan_id", "test_run_id", name="uq_test_plan_run"),)
        id = hub.db.Column(hub.db.Integer, primary_key=True)
        test_plan_id = hub.db.Column(hub.db.Integer, hub.db.ForeignKey("test_plans.id", ondelete="CASCADE"), nullable=False, index=True)
        test_run_id = hub.db.Column(hub.db.Integer, hub.db.ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False, index=True)

    class TestResultDefectLink(hub.db.Model):
        __tablename__ = "test_result_defect_links"
        __table_args__ = (hub.UniqueConstraint("test_result_id", "jira_key", name="uq_test_result_defect"),)
        id = hub.db.Column(hub.db.Integer, primary_key=True)
        test_result_id = hub.db.Column(hub.db.Integer, hub.db.ForeignKey("test_results.id", ondelete="CASCADE"), nullable=False, index=True)
        jira_key = hub.db.Column(hub.db.String(50), nullable=False, index=True)

    class TestPlanAssessment(hub.db.Model):
        __tablename__ = "test_plan_assessments"
        __table_args__ = (hub.UniqueConstraint("test_plan_id", name="uq_test_plan_assessment"),)
        id = hub.db.Column(hub.db.Integer, primary_key=True)
        test_plan_id = hub.db.Column(hub.db.Integer, hub.db.ForeignKey("test_plans.id", ondelete="CASCADE"), nullable=False, index=True)
        qa_status = hub.db.Column(hub.db.String(30), nullable=False, default="Not Assessed")
        notes = hub.db.Column(hub.db.Text, nullable=False, default="")
        updated_at = hub.db.Column(hub.db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    hub.TestPlanReleaseLink = TestPlanReleaseLink
    hub.TestPlanJiraLink = TestPlanJiraLink
    hub.TestPlanItemJiraLink = TestPlanItemJiraLink
    hub.TestPlanRunLink = TestPlanRunLink
    hub.TestResultDefectLink = TestResultDefectLink
    hub.TestPlanAssessment = TestPlanAssessment

    # Add only missing relationship tables; existing Test Hub tables are not altered.
    with hub.app.app_context():
        hub.db.create_all()

    # Add section anchors and the process panels to the existing Test Plan page.
    if "process-tabs" not in test_plans.TEST_PLAN_PAGE_HTML:
        test_plans.TEST_PLAN_PAGE_HTML = test_plans.TEST_PLAN_PAGE_HTML.replace("</style>", PROCESS_CSS + "</style>", 1)
        test_plans.TEST_PLAN_PAGE_HTML = test_plans.TEST_PLAN_PAGE_HTML.replace('<main class="th-page">', '<main class="th-page">\
' + PROCESS_HTML.split('<section class="process-grid">', 1)[0], 1)
        process_body = '<section class="process-grid">' + PROCESS_HTML.split('<section class="process-grid">', 1)[1]
        test_plans.TEST_PLAN_PAGE_HTML = test_plans.TEST_PLAN_PAGE_HTML.replace("</main>\
<script>", process_body + "\
</main>\
<script>", 1)
        test_plans.TEST_PLAN_PAGE_HTML = test_plans.TEST_PLAN_PAGE_HTML.replace('<div class="top">', '<div id="overview" class="top">', 1)
        test_plans.TEST_PLAN_PAGE_HTML = test_plans.TEST_PLAN_PAGE_HTML.replace('<h2>Coverage checklist</h2>', '<h2 id="coverage">Coverage checklist</h2>', 1)

    def get_plan(plan_id):
        return hub.db.session.get(hub.TestPlan, plan_id)

    def coverage_summary(plan):
        total = len(plan.items)
        created = sum(1 for item in plan.items if item.test_case is not None)
        return {"total": total, "created": created, "pending": total - created, "completion": round((created / total) * 100, 1) if total else 0}

    def linked_release_ids(plan_id):
        return [value for (value,) in hub.db.session.execute(hub.db.select(TestPlanReleaseLink.release_id).where(TestPlanReleaseLink.test_plan_id == plan_id)).all()]

    def linked_releases(plan_id):
        ids = linked_release_ids(plan_id)
        if not ids:
            return []
        return hub.db.session.scalars(hub.db.select(hub.Release).where(hub.Release.id.in_(ids)).order_by(hub.Release.release_date.desc(), hub.Release.id.desc())).all()

    def jira_scope(plan_id):
        return [value for (value,) in hub.db.session.execute(hub.db.select(TestPlanJiraLink.jira_key).where(TestPlanJiraLink.test_plan_id == plan_id).order_by(TestPlanJiraLink.jira_key)).all()]

    def linked_run_ids(plan_id):
        return [value for (value,) in hub.db.session.execute(hub.db.select(TestPlanRunLink.test_run_id).where(TestPlanRunLink.test_plan_id == plan_id)).all()]

    def linked_runs(plan_id):
        ids = linked_run_ids(plan_id)
        if not ids:
            return []
        return hub.db.session.scalars(hub.db.select(hub.TestRun).where(hub.TestRun.id.in_(ids)).order_by(hub.TestRun.created_at.desc(), hub.TestRun.id.desc())).all()

    def latest_results(plan):
        run_ids = linked_run_ids(plan.id)
        latest = {}
        attempts = {}
        if not run_ids:
            return latest, attempts
        results = hub.db.session.scalars(hub.db.select(hub.TestResult).where(hub.TestResult.test_run_id.in_(run_ids)).order_by(hub.TestResult.executed_at.asc(), hub.TestResult.id.asc())).all()
        for result in results:
            attempts.setdefault(result.case_key_snapshot, []).append(result)
            latest[result.case_key_snapshot] = result
        return latest, attempts

    def execution_summary(plan):
        covered = [item.test_case for item in plan.items if item.test_case is not None]
        latest, attempts = latest_results(plan)
        counts = {"Passed": 0, "Failed": 0, "Blocked": 0, "Skipped": 0}
        recovered = 0
        for case in covered:
            result = latest.get(case.case_key)
            if result and result.result in counts:
                counts[result.result] += 1
            case_attempts = attempts.get(case.case_key, [])
            if result and result.result == "Passed" and any(attempt.result == "Failed" for attempt in case_attempts[:-1]):
                recovered += 1
        executed = sum(counts.values())
        decided = counts["Passed"] + counts["Failed"]
        return {"total": len(covered), "executed": executed, "not_run": max(len(covered) - executed, 0), "passed": counts["Passed"], "failed": counts["Failed"], "blocked": counts["Blocked"], "skipped": counts["Skipped"], "recovered": recovered, "pass_rate": round((counts["Passed"] / decided) * 100, 1) if decided else 0}

    def assessment_for(plan_id):
        assessment = hub.db.session.scalar(hub.db.select(TestPlanAssessment).where(TestPlanAssessment.test_plan_id == plan_id))
        if assessment is None:
            assessment = TestPlanAssessment(test_plan_id=plan_id, qa_status="Not Assessed", notes="")
        return assessment

    def traceability_rows(plan):
        latest, _ = latest_results(plan)
        item_ids = [item.id for item in plan.items]
        item_links = {}
        if item_ids:
            links = hub.db.session.scalars(hub.db.select(TestPlanItemJiraLink).where(TestPlanItemJiraLink.test_plan_item_id.in_(item_ids)).order_by(TestPlanItemJiraLink.jira_key)).all()
            for link in links:
                item_links.setdefault(link.test_plan_item_id, []).append(link.jira_key)
        result_ids = [result.id for result in latest.values()]
        defect_map = {}
        if result_ids:
            defects = hub.db.session.scalars(hub.db.select(TestResultDefectLink).where(TestResultDefectLink.test_result_id.in_(result_ids)).order_by(TestResultDefectLink.jira_key)).all()
            for defect in defects:
                defect_map.setdefault(defect.test_result_id, []).append(defect)
        rows = []
        for item in plan.items:
            case = item.test_case
            result = latest.get(case.case_key) if case else None
            keys = list(item_links.get(item.id, []))
            if not keys and case:
                keys = list(case.jira_keys)
            rows.append({"item": item, "jira_keys": keys, "test_case": case, "result": result, "defects": defect_map.get(result.id, []) if result else []})
        return rows

    def process_context(plan):
        releases = linked_releases(plan.id)
        release_ids = {release.id for release in releases}
        all_releases = hub.db.session.scalars(hub.db.select(hub.Release).order_by(hub.Release.release_date.desc(), hub.Release.id.desc())).all()
        runs = linked_runs(plan.id)
        run_ids = {run.id for run in runs}
        all_runs = hub.db.session.scalars(hub.db.select(hub.TestRun).order_by(hub.TestRun.created_at.desc(), hub.TestRun.id.desc())).all()
        covered_cases = []
        seen_case_ids = set()
        for item in plan.items:
            if item.test_case is not None and item.test_case.id not in seen_case_ids:
                covered_cases.append(item.test_case)
                seen_case_ids.add(item.test_case.id)
        return {"releases": releases, "available_releases": [release for release in all_releases if release.id not in release_ids], "jira_scope": jira_scope(plan.id), "run_rows": [{"run": run, "summary": hub.test_run_summary(run)} for run in runs], "available_runs": [run for run in all_runs if run.items and run.id not in run_ids], "execution": execution_summary(plan), "traceability": traceability_rows(plan), "assessment": assessment_for(plan.id), "covered_cases": covered_cases}

    # Replace the original Test Plan details renderer so the new process data is available.
    def test_plan_details_with_process(plan_id):
        plan = get_plan(plan_id)
        if plan is None:
            return "Test Plan not found.", 404
        all_cases = hub.db.session.scalars(hub.db.select(hub.TestCase).order_by(hub.TestCase.feature, hub.TestCase.case_key)).all()
        attached_case_ids = {item.test_case.id for item in plan.items if item.test_case is not None}
        attachable_cases = [case for case in all_cases if case.id not in attached_case_ids]
        return hub.render_template_string(test_plans.TEST_PLAN_PAGE_HTML, plan=plan, summary=coverage_summary(plan), statuses=["Draft", "Active", "Completed"], attachable_cases=attachable_cases, nav_html=test_plans.render_shared_navigation(hub, ui_redesign), shell_css=ui_redesign.SHELL_CSS, process=process_context(plan), qa_assessments=["Not Assessed", "Ready", "At Risk", "Incomplete"], jira_base=hub.JIRA_BASE_URL.rstrip("/"))

    hub.app.view_functions["test_plan_details"] = test_plan_details_with_process

    @hub.app.post("/test-plans/<int:plan_id>/releases")
    def attach_test_plan_release(plan_id):
        plan = get_plan(plan_id)
        if plan is None:
            return "Test Plan not found.", 404
        try:
            release_id = int(hub.request.form.get("release_id", ""))
        except ValueError:
            return "Select a valid release.", 400
        release = hub.db.session.get(hub.Release, release_id)
        if release is None:
            return "Release not found.", 404
        exists = hub.db.session.scalar(hub.db.select(TestPlanReleaseLink.id).where(TestPlanReleaseLink.test_plan_id == plan.id, TestPlanReleaseLink.release_id == release.id))
        if exists is None:
            hub.db.session.add(TestPlanReleaseLink(test_plan_id=plan.id, release_id=release.id))
            hub.db.session.commit()
        return hub.redirect(hub.url_for("test_plan_details", plan_id=plan.id))

    @hub.app.post("/test-plans/<int:plan_id>/releases/<int:release_id>/remove")
    def remove_test_plan_release(plan_id, release_id):
        link = hub.db.session.scalar(hub.db.select(TestPlanReleaseLink).where(TestPlanReleaseLink.test_plan_id == plan_id, TestPlanReleaseLink.release_id == release_id))
        if link:
            hub.db.session.delete(link)
            hub.db.session.commit()
        return hub.redirect(hub.url_for("test_plan_details", plan_id=plan_id))

    @hub.app.post("/test-plans/<int:plan_id>/jira")
    def attach_test_plan_jira(plan_id):
        plan = get_plan(plan_id)
        if plan is None:
            return "Test Plan not found.", 404
        try:
            keys = hub.parse_jira_keys(hub.request.form.get("jira_keys", ""))
        except ValueError as exc:
            return str(exc), 400
        existing = set(jira_scope(plan.id))
        for key in keys:
            if key not in existing:
                hub.db.session.add(TestPlanJiraLink(test_plan_id=plan.id, jira_key=key))
        hub.db.session.commit()
        return hub.redirect(hub.url_for("test_plan_details", plan_id=plan.id))

    @hub.app.post("/test-plans/<int:plan_id>/jira/<jira_key>/remove")
    def remove_test_plan_jira(plan_id, jira_key):
        jira_key = jira_key.strip().upper()
        item_ids = [item.id for item in get_plan(plan_id).items] if get_plan(plan_id) else []
        if item_ids:
            used = hub.db.session.scalar(hub.db.select(TestPlanItemJiraLink.id).where(TestPlanItemJiraLink.test_plan_item_id.in_(item_ids), TestPlanItemJiraLink.jira_key == jira_key))
            if used is not None:
                return "This Jira requirement is still mapped to a coverage item. Unlink it from traceability first.", 400
        link = hub.db.session.scalar(hub.db.select(TestPlanJiraLink).where(TestPlanJiraLink.test_plan_id == plan_id, TestPlanJiraLink.jira_key == jira_key))
        if link:
            hub.db.session.delete(link)
            hub.db.session.commit()
        return hub.redirect(hub.url_for("test_plan_details", plan_id=plan_id))

    @hub.app.post("/test-plans/<int:plan_id>/items/<int:item_id>/jira")
    def attach_test_plan_item_jira(plan_id, item_id):
        plan = get_plan(plan_id)
        item = hub.db.session.get(hub.TestPlanItem, item_id)
        if plan is None or item is None or item.test_plan_id != plan.id:
            return "Test Plan item not found.", 404
        jira_key = hub.request.form.get("jira_key", "").strip().upper()
        if not hub.JIRA_KEY_PATTERN.match(jira_key):
            return "Invalid Jira key.", 400
        scope_link = hub.db.session.scalar(hub.db.select(TestPlanJiraLink.id).where(TestPlanJiraLink.test_plan_id == plan.id, TestPlanJiraLink.jira_key == jira_key))
        if scope_link is None:
            hub.db.session.add(TestPlanJiraLink(test_plan_id=plan.id, jira_key=jira_key))
        item_link = hub.db.session.scalar(hub.db.select(TestPlanItemJiraLink.id).where(TestPlanItemJiraLink.test_plan_item_id == item.id, TestPlanItemJiraLink.jira_key == jira_key))
        if item_link is None:
            hub.db.session.add(TestPlanItemJiraLink(test_plan_item_id=item.id, jira_key=jira_key))
        hub.db.session.commit()
        return hub.redirect(hub.url_for("test_plan_details", plan_id=plan.id) + "#traceability")

    @hub.app.post("/test-plans/<int:plan_id>/test-runs")
    def create_test_plan_run(plan_id):
        plan = get_plan(plan_id)
        if plan is None:
            return "Test Plan not found.", 404
        name = hub.request.form.get("name", "").strip()
        execution_type = hub.request.form.get("execution_type", "Automated").strip()
        environment = hub.request.form.get("environment", "").strip()
        release_value = hub.request.form.get("release_id", "").strip()
        raw_case_ids = hub.request.form.getlist("case_ids")
        if not name:
            return "Test Run name is required.", 400
        if execution_type not in hub.TYPES:
            return "Invalid execution type.", 400
        if not raw_case_ids:
            return "Select at least one covered Test Case.", 400
        try:
            case_ids = [int(value) for value in raw_case_ids]
        except ValueError:
            return "Invalid Test Case selection.", 400
        covered_ids = {item.test_case.id for item in plan.items if item.test_case is not None}
        if not set(case_ids).issubset(covered_ids):
            return "A selected Test Case is not covered by this Test Plan.", 400
        cases = hub.db.session.scalars(hub.db.select(hub.TestCase).where(hub.TestCase.id.in_(case_ids)).order_by(hub.TestCase.feature, hub.TestCase.case_key)).all()
        if execution_type == "Automated" and any(case.type != "Automated" for case in cases):
            return "Automated runs can contain only Automated Test Cases.", 400
        release = None
        if release_value:
            try:
                release_id = int(release_value)
            except ValueError:
                return "Invalid release.", 400
            if release_id not in set(linked_release_ids(plan.id)):
                return "Attach the release to this Test Plan before using it in a run.", 400
            release = hub.db.session.get(hub.Release, release_id)
        run = hub.TestRun(release=release, name=name, preset="Custom", execution_type=execution_type, environment=environment or (release.environment if release else ""), execution_status="Planned", started_at=datetime.now(timezone.utc))
        run.items = [hub.TestRunItem(test_case=case, position=index, case_key_snapshot=case.case_key, case_title_snapshot=case.title, feature_snapshot=case.feature_name) for index, case in enumerate(cases, start=1)]
        hub.db.session.add(run)
        hub.db.session.flush()
        hub.db.session.add(TestPlanRunLink(test_plan_id=plan.id, test_run_id=run.id))
        hub.db.session.commit()
        return hub.redirect(hub.url_for("test_run_details", run_id=run.id))

    @hub.app.post("/test-plans/<int:plan_id>/test-runs/attach")
    def attach_existing_test_plan_run(plan_id):
        plan = get_plan(plan_id)
        if plan is None:
            return "Test Plan not found.", 404
        try:
            run_id = int(hub.request.form.get("run_id", ""))
        except ValueError:
            return "Select a valid Test Run.", 400
        run = hub.db.session.get(hub.TestRun, run_id)
        if run is None or not run.items:
            return "Structured Test Run not found.", 404
        exists = hub.db.session.scalar(hub.db.select(TestPlanRunLink.id).where(TestPlanRunLink.test_plan_id == plan.id, TestPlanRunLink.test_run_id == run.id))
        if exists is None:
            hub.db.session.add(TestPlanRunLink(test_plan_id=plan.id, test_run_id=run.id))
            hub.db.session.commit()
        return hub.redirect(hub.url_for("test_plan_details", plan_id=plan.id) + "#executions")

    @hub.app.post("/test-plans/<int:plan_id>/test-runs/<int:run_id>/remove")
    def remove_test_plan_run(plan_id, run_id):
        link = hub.db.session.scalar(hub.db.select(TestPlanRunLink).where(TestPlanRunLink.test_plan_id == plan_id, TestPlanRunLink.test_run_id == run_id))
        if link:
            hub.db.session.delete(link)
            hub.db.session.commit()
        return hub.redirect(hub.url_for("test_plan_details", plan_id=plan_id) + "#executions")

    @hub.app.post("/test-results/<int:result_id>/defects")
    def link_test_result_defect(result_id):
        result = hub.db.session.get(hub.TestResult, result_id)
        if result is None:
            return "Test Result not found.", 404
        jira_key = hub.request.form.get("jira_key", "").strip().upper()
        if not hub.JIRA_KEY_PATTERN.match(jira_key):
            return "Invalid Jira defect key.", 400
        exists = hub.db.session.scalar(hub.db.select(TestResultDefectLink.id).where(TestResultDefectLink.test_result_id == result.id, TestResultDefectLink.jira_key == jira_key))
        if exists is None:
            hub.db.session.add(TestResultDefectLink(test_result_id=result.id, jira_key=jira_key))
            hub.db.session.commit()
        plan_id = hub.request.form.get("plan_id", "").strip()
        if plan_id.isdigit():
            return hub.redirect(hub.url_for("test_plan_details", plan_id=int(plan_id)) + "#traceability")
        return hub.redirect(hub.url_for("test_run_details", run_id=result.test_run_id))

    @hub.app.post("/test-plans/<int:plan_id>/assessment")
    def update_test_plan_assessment(plan_id):
        plan = get_plan(plan_id)
        if plan is None:
            return "Test Plan not found.", 404
        qa_status = hub.request.form.get("qa_status", "Not Assessed").strip()
        notes = hub.request.form.get("notes", "").strip()
        if qa_status not in QA_ASSESSMENTS:
            return "Invalid QA assessment status.", 400
        assessment = hub.db.session.scalar(hub.db.select(TestPlanAssessment).where(TestPlanAssessment.test_plan_id == plan.id))
        if assessment is None:
            assessment = TestPlanAssessment(test_plan_id=plan.id)
            hub.db.session.add(assessment)
        assessment.qa_status = qa_status
        assessment.notes = notes
        assessment.updated_at = datetime.now(timezone.utc)
        hub.db.session.commit()
        return hub.redirect(hub.url_for("test_plan_details", plan_id=plan.id) + "#assessment")

    @hub.app.get("/test-plans/<int:plan_id>/report")
    def test_plan_report(plan_id):
        plan = get_plan(plan_id)
        if plan is None:
            return "Test Plan not found.", 404
        process = process_context(plan)
        return hub.render_template_string(REPORT_HTML, plan=plan, coverage=coverage_summary(plan), execution=process["execution"], releases=process["releases"], jira_scope=process["jira_scope"], run_rows=process["run_rows"], traceability=process["traceability"], assessment=process["assessment"], jira_base=hub.JIRA_BASE_URL.rstrip("/"), nav_html=test_plans.render_shared_navigation(hub, ui_redesign), shell_css=ui_redesign.SHELL_CSS, generated_at=datetime.now(timezone.utc))

    # Add lightweight reverse links so existing Test Case, Test Run, Release and Jira pages
    # can navigate back to the Test Plans that reference them.
    def inject_related_plans(endpoint, lookup):
        original = hub.app.view_functions.get(endpoint)
        if original is None:
            return

        @wraps(original)
        def wrapped(*args, **kwargs):
            response = hub.app.make_response(original(*args, **kwargs))
            if response.status_code != 200 or "text/html" not in response.content_type:
                return response
            plans = lookup(*args, **kwargs)
            if not plans:
                return response
            links = "".join(f'<a style="display:inline-flex;margin:4px 6px 4px 0;padding:6px 9px;border-radius:8px;background:#edf5ff;color:#1763d8;text-decoration:none;font-size:11px;font-weight:800" href="{hub.url_for("test_plan_details", plan_id=plan.id)}">{plan.name}</a>' for plan in plans)
            panel = f'<section style="max-width:1400px;margin:16px auto;padding:14px 20px;border:1px solid #dce6f4;border-radius:14px;background:#fff"><strong style="color:#17325d">Linked Test Plans</strong><div>{links}</div></section>'
            html = response.get_data(as_text=True)
            response.set_data(html.replace("</main>", panel + "</main>", 1) if "</main>" in html else html.replace("</body>", panel + "</body>", 1))
            return response

        hub.app.view_functions[endpoint] = wrapped

    def plans_for_case(case_key):
        case = hub.db.session.scalar(hub.db.select(hub.TestCase).where(hub.TestCase.case_key == case_key))
        if case is None:
            return []
        plan_ids = [value for (value,) in hub.db.session.execute(hub.db.select(hub.TestPlanItem.test_plan_id).where(hub.TestPlanItem.test_case_id == case.id).distinct()).all()]
        return hub.db.session.scalars(hub.db.select(hub.TestPlan).where(hub.TestPlan.id.in_(plan_ids))).all() if plan_ids else []

    def plans_for_run(run_id):
        plan_ids = [value for (value,) in hub.db.session.execute(hub.db.select(TestPlanRunLink.test_plan_id).where(TestPlanRunLink.test_run_id == run_id)).all()]
        return hub.db.session.scalars(hub.db.select(hub.TestPlan).where(hub.TestPlan.id.in_(plan_ids))).all() if plan_ids else []

    def plans_for_release(release_id):
        plan_ids = [value for (value,) in hub.db.session.execute(hub.db.select(TestPlanReleaseLink.test_plan_id).where(TestPlanReleaseLink.release_id == release_id)).all()]
        return hub.db.session.scalars(hub.db.select(hub.TestPlan).where(hub.TestPlan.id.in_(plan_ids))).all() if plan_ids else []

    def plans_for_jira(jira_key):
        jira_key = str(jira_key).strip().upper()
        plan_ids = [value for (value,) in hub.db.session.execute(hub.db.select(TestPlanJiraLink.test_plan_id).where(TestPlanJiraLink.jira_key == jira_key)).all()]
        return hub.db.session.scalars(hub.db.select(hub.TestPlan).where(hub.TestPlan.id.in_(plan_ids))).all() if plan_ids else []

    inject_related_plans("test_case_details", lambda case_key: plans_for_case(case_key))
    inject_related_plans("test_run_details", lambda run_id: plans_for_run(run_id))
    inject_related_plans("release_details", lambda release_id: plans_for_release(release_id))
    inject_related_plans("jira_story_cases", lambda jira_key: plans_for_jira(jira_key))

    hub.app._test_plan_process_registered = True
