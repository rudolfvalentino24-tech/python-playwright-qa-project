import io
import re
from datetime import datetime, timezone
from functools import wraps
from html import escape as html_escape

from flask import send_file

try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )
except ImportError:  # Keep Test Hub usable until requirements are installed.
    colors = None
    TA_CENTER = None
    A4 = None
    landscape = None
    ParagraphStyle = None
    getSampleStyleSheet = None
    mm = None
    PageBreak = None
    Paragraph = None
    SimpleDocTemplate = None
    Spacer = None
    Table = None
    TableStyle = None


EXPORT_CSS = r"""
[data-test-plan-export-link]{white-space:nowrap}
"""


def _reportlab_available():
    return SimpleDocTemplate is not None


def _filename(value):
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", (value or "Test_Plan").strip())
    return (cleaned.strip("_") or "Test_Plan")[:120]


def _plain(value):
    """Normalize user text for ReportLab's built-in fonts."""
    text = str(value or "")
    replacements = {
        "—": "-",
        "–": "-",
        "→": "->",
        "←": "<-",
        "•": "-",
        "✓": "Yes",
        "☑": "Yes",
        "☐": "No",
        "×": "x",
        "…": "...",
        "’": "'",
        "“": '"',
        "”": '"',
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text.encode("latin-1", "replace").decode("latin-1")


def _paragraph_text(value):
    return html_escape(_plain(value)).replace("\n", "<br/>")


def _query_all(hub, model, *criteria, order_by=None):
    if model is None:
        return []
    statement = hub.db.select(model)
    if criteria:
        statement = statement.where(*criteria)
    if order_by:
        statement = statement.order_by(*order_by)
    return list(hub.db.session.scalars(statement).all())


def _query_one(hub, model, *criteria):
    if model is None:
        return None
    return hub.db.session.scalar(hub.db.select(model).where(*criteria))


def _collect_plan_data(hub, plan):
    release_link_model = getattr(hub, "TestPlanReleaseLink", None)
    jira_link_model = getattr(hub, "TestPlanJiraLink", None)
    run_link_model = getattr(hub, "TestPlanRunLink", None)
    assessment_model = getattr(hub, "TestPlanAssessment", None)
    e2e_profile_model = getattr(hub, "TestPlanE2EProfile", None)
    role_model = getattr(hub, "TestPlanRole", None)
    phase_model = getattr(hub, "TestPlanPhase", None)
    dod_model = getattr(hub, "TestPlanDefinitionItem", None)
    meta_model = getattr(hub, "TestPlanCoverageMeta", None)

    releases = []
    if release_link_model is not None:
        release_links = _query_all(hub, release_link_model, release_link_model.test_plan_id == plan.id)
        release_ids = [link.release_id for link in release_links]
        if release_ids:
            releases = _query_all(
                hub,
                hub.Release,
                hub.Release.id.in_(release_ids),
                order_by=(hub.Release.release_date.desc(), hub.Release.id.desc()),
            )

    jira_scope = []
    if jira_link_model is not None:
        jira_links = _query_all(
            hub,
            jira_link_model,
            jira_link_model.test_plan_id == plan.id,
            order_by=(jira_link_model.jira_key,),
        )
        jira_scope = [link.jira_key for link in jira_links]

    assessment = None
    if assessment_model is not None:
        assessment = _query_one(hub, assessment_model, assessment_model.test_plan_id == plan.id)

    runs = []
    if run_link_model is not None:
        run_links = _query_all(hub, run_link_model, run_link_model.test_plan_id == plan.id)
        run_ids = [link.test_run_id for link in run_links]
        if run_ids:
            runs = _query_all(
                hub,
                hub.TestRun,
                hub.TestRun.id.in_(run_ids),
                order_by=(hub.TestRun.created_at.desc(), hub.TestRun.id.desc()),
            )

    items = sorted(list(plan.items or []), key=lambda item: (item.position or 0, item.id or 0))
    metas = {}
    if meta_model is not None and items:
        item_ids = [item.id for item in items]
        for meta in _query_all(hub, meta_model, meta_model.test_plan_item_id.in_(item_ids)):
            metas[meta.test_plan_item_id] = meta

    coverage_rows = []
    for item in items:
        meta = metas.get(item.id)
        case = item.test_case
        coverage_rows.append({
            "reference": getattr(meta, "reference", "") or (case.case_key if case else ""),
            "area": item.feature_snapshot,
            "scenario": item.title_snapshot,
            "priority": getattr(meta, "priority", "") or "",
            "automation_target": getattr(meta, "automation_target", "") or "",
            "test_case": case.case_key if case else "",
            "status": "Covered" if case is not None else "Pending",
        })

    covered = sum(1 for row in coverage_rows if row["status"] == "Covered")
    coverage = {
        "planned": len(coverage_rows),
        "covered": covered,
        "pending": len(coverage_rows) - covered,
        "percent": round((covered / len(coverage_rows)) * 100, 1) if coverage_rows else 0,
    }

    run_rows = []
    for run in runs:
        if hasattr(hub, "test_run_summary"):
            summary = hub.test_run_summary(run)
        else:
            total = len(getattr(run, "items", []) or [])
            summary = {"total": total, "executed": 0, "passed": 0, "failed": 0, "not_run": total, "pass_rate": 0}
        run_rows.append({"run": run, "summary": summary})

    profile = None
    roles = []
    phases = []
    dod = []
    if (getattr(plan, "plan_type", "") or "") == "End-to-End":
        if e2e_profile_model is not None:
            profile = _query_one(hub, e2e_profile_model, e2e_profile_model.test_plan_id == plan.id)
        if role_model is not None:
            roles = _query_all(hub, role_model, role_model.test_plan_id == plan.id, order_by=(role_model.id,))
        if phase_model is not None:
            phases = _query_all(hub, phase_model, phase_model.test_plan_id == plan.id, order_by=(phase_model.position, phase_model.id))
        if dod_model is not None:
            dod = _query_all(hub, dod_model, dod_model.test_plan_id == plan.id, order_by=(dod_model.position, dod_model.id))

    return {
        "releases": releases,
        "jira_scope": jira_scope,
        "assessment": assessment,
        "coverage": coverage,
        "coverage_rows": coverage_rows,
        "run_rows": run_rows,
        "profile": profile,
        "roles": roles,
        "phases": phases,
        "dod": dod,
    }


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("TestHubTitle", parent=base["Title"], fontName="Helvetica-Bold", fontSize=20, leading=24, textColor=colors.HexColor("#17325D"), spaceAfter=5 * mm),
        "subtitle": ParagraphStyle("TestHubSubtitle", parent=base["Normal"], fontName="Helvetica", fontSize=8.5, leading=11, textColor=colors.HexColor("#667085"), spaceAfter=4 * mm),
        "h1": ParagraphStyle("TestHubH1", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=13, leading=16, textColor=colors.HexColor("#17325D"), spaceBefore=4 * mm, spaceAfter=2 * mm),
        "body": ParagraphStyle("TestHubBody", parent=base["BodyText"], fontName="Helvetica", fontSize=8.5, leading=11.5, textColor=colors.HexColor("#475467"), spaceAfter=2 * mm),
        "table_header": ParagraphStyle("TestHubTableHeader", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=7, leading=8.5, textColor=colors.HexColor("#344054")),
        "table": ParagraphStyle("TestHubTable", parent=base["BodyText"], fontName="Helvetica", fontSize=6.8, leading=8.2, textColor=colors.HexColor("#475467")),
        "center": ParagraphStyle("TestHubCenter", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=8, leading=10, alignment=TA_CENTER, textColor=colors.HexColor("#17325D")),
    }


def _p(value, style):
    return Paragraph(_paragraph_text(value), style)


def _section(story, title, value, styles):
    if not (value or "").strip():
        return
    story.append(_p(title, styles["h1"]))
    story.append(_p(value, styles["body"]))


def _metadata_table(plan, data, styles):
    release_text = ", ".join(release.version for release in data["releases"]) or "-"
    jira_text = ", ".join(data["jira_scope"]) or "-"
    rows = [
        ["Plan type", getattr(plan, "plan_type", "") or "Feature", "Status", plan.status],
        ["Application", getattr(plan, "application", "") or "-", "Feature / Module", getattr(plan, "feature", "") or "-"],
        ["Environment", getattr(plan, "environment", "") or "-", "Release", release_text],
        ["Jira scope", jira_text, "Coverage", f'{data["coverage"]["covered"]}/{data["coverage"]["planned"]} ({data["coverage"]["percent"]}%)'],
    ]
    table = Table(
        [[_p(cell, styles["table_header"] if col % 2 == 0 else styles["table"]) for col, cell in enumerate(row)] for row in rows],
        colWidths=[27 * mm, 60 * mm, 27 * mm, 60 * mm],
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D5DD")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#EAECF0")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def _coverage_table(data, styles):
    headers = ["Reference", "Area", "Scenario", "Priority", "Automation target", "Test Case", "Status"]
    rows = [[_p(header, styles["table_header"]) for header in headers]]
    for row in data["coverage_rows"]:
        rows.append([
            _p(row["reference"] or "-", styles["table"]), _p(row["area"] or "-", styles["table"]),
            _p(row["scenario"] or "-", styles["table"]), _p(row["priority"] or "-", styles["table"]),
            _p(row["automation_target"] or "-", styles["table"]), _p(row["test_case"] or "-", styles["table"]),
            _p(row["status"], styles["table"]),
        ])
    if len(rows) == 1:
        rows.append([_p("No planned coverage.", styles["table"])] + [""] * 6)
    table = Table(rows, colWidths=[20 * mm, 24 * mm, 70 * mm, 15 * mm, 37 * mm, 22 * mm, 20 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEF4FF")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D5DD")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#EAECF0")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def _runs_table(data, styles):
    rows = [[_p(value, styles["table_header"]) for value in ("Run", "Type / Environment", "Status", "Executed", "Passed", "Failed", "Pass rate")]]
    for row in data["run_rows"]:
        run = row["run"]
        summary = row["summary"]
        rows.append([
            _p(run.name, styles["table"]), _p(f'{run.execution_type} / {run.environment or "-"}', styles["table"]),
            _p(run.execution_status, styles["table"]), _p(f'{summary.get("executed", 0)}/{summary.get("total", 0)}', styles["table"]),
            _p(summary.get("passed", 0), styles["table"]), _p(summary.get("failed", 0), styles["table"]),
            _p(f'{summary.get("pass_rate", 0)}%', styles["table"]),
        ])
    if len(rows) == 1:
        rows.append([_p("No linked Test Runs.", styles["table"])] + [""] * 6)
    table = Table(rows, colWidths=[48 * mm, 45 * mm, 25 * mm, 22 * mm, 18 * mm, 18 * mm, 22 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEF4FF")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D5DD")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#EAECF0")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def _e2e_story(story, data, styles):
    profile = data["profile"]
    if profile is None:
        return
    story.append(PageBreak())
    story.append(_p("End-to-End design", styles["h1"]))
    profile_rows = [
        ["Application URL", profile.application_url or "-", "Browser coverage", profile.browser_coverage or "-"],
        ["Automation style", profile.automation_style or "-", "Execution model", profile.execution_model or "-"],
    ]
    table = Table(
        [[_p(cell, styles["table_header"] if col % 2 == 0 else styles["table"]) for col, cell in enumerate(row)] for row in profile_rows],
        colWidths=[30 * mm, 56 * mm, 30 * mm, 56 * mm],
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D5DD")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#EAECF0")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(table)
    _section(story, "Primary E2E journey", profile.primary_journey, styles)
    _section(story, "First implementation target", profile.first_target, styles)

    if data["roles"]:
        story.append(_p("Test accounts and roles", styles["h1"]))
        role_rows = [[_p(value, styles["table_header"]) for value in ("Fixture / User", "Role", "Purpose")]]
        for role in data["roles"]:
            role_rows.append([_p(role.fixture_user or "-", styles["table"]), _p(role.role_name, styles["table"]), _p(role.purpose or "-", styles["table"])])
        role_table = Table(role_rows, colWidths=[45 * mm, 45 * mm, 85 * mm], repeatRows=1)
        role_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEF4FF")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D5DD")),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#EAECF0")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(role_table)

    _section(story, "Test data strategy", profile.test_data_strategy, styles)
    _section(story, "BDD structure", profile.bdd_structure, styles)
    _section(story, "Page Object strategy", profile.page_object_strategy, styles)
    _section(story, "E2E design rules", profile.design_rules, styles)
    _section(story, "Jenkins strategy", profile.jenkins_strategy, styles)

    if data["phases"]:
        story.append(_p("Implementation phases", styles["h1"]))
        phase_rows = [[_p(value, styles["table_header"]) for value in ("#", "Focus", "Outcome", "Status")]]
        for phase in data["phases"]:
            phase_rows.append([_p(phase.position, styles["table"]), _p(phase.focus, styles["table"]), _p(phase.outcome or "-", styles["table"]), _p(phase.status, styles["table"])])
        phase_table = Table(phase_rows, colWidths=[10 * mm, 58 * mm, 80 * mm, 28 * mm], repeatRows=1)
        phase_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEF4FF")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D5DD")),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#EAECF0")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(phase_table)

    if data["dod"]:
        story.append(_p("Definition of Done", styles["h1"]))
        for item in data["dod"]:
            prefix = "[x]" if item.completed else "[ ]"
            story.append(_p(f"{prefix} {item.text}", styles["body"]))
    _section(story, "Implementation notes", profile.implementation_notes, styles)


def _page_footer(canvas, doc):
    canvas.saveState()
    width, _ = doc.pagesize
    canvas.setStrokeColor(colors.HexColor("#D0D5DD"))
    canvas.setLineWidth(0.4)
    canvas.line(doc.leftMargin, 11 * mm, width - doc.rightMargin, 11 * mm)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#667085"))
    canvas.drawString(doc.leftMargin, 7 * mm, "Test Hub - Test Plan Export")
    canvas.drawRightString(width - doc.rightMargin, 7 * mm, f"Page {doc.page}")
    canvas.restoreState()


def _build_pdf(hub, plan):
    data = _collect_plan_data(hub, plan)
    styles = _styles()
    output = io.BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=landscape(A4),
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=16 * mm,
        title=_plain(plan.name),
        author="Test Hub",
    )
    story = [
        _p(plan.name, styles["title"]),
        _p(f'Test Plan export | Generated {datetime.now(timezone.utc).strftime("%d %b %Y %H:%M UTC")}', styles["subtitle"]),
        _metadata_table(plan, data, styles),
        Spacer(1, 3 * mm),
    ]
    _section(story, "Summary / Context", getattr(plan, "description", ""), styles)
    _section(story, "Objective", getattr(plan, "objective", ""), styles)
    _section(story, "In Scope", getattr(plan, "in_scope", ""), styles)
    _section(story, "Out of Scope", getattr(plan, "out_of_scope", ""), styles)
    _section(story, "Risks / Edge Cases", getattr(plan, "risks", ""), styles)
    _section(story, "Entry Criteria", getattr(plan, "entry_criteria", ""), styles)
    _section(story, "Exit Criteria", getattr(plan, "exit_criteria", ""), styles)

    assessment = data["assessment"]
    if assessment is not None:
        story.append(_p("QA assessment", styles["h1"]))
        story.append(_p(f"Status: {assessment.qa_status}", styles["body"]))
        if assessment.notes:
            story.append(_p(assessment.notes, styles["body"]))

    story.append(PageBreak())
    story.append(_p("Coverage", styles["h1"]))
    story.append(_p(f'{data["coverage"]["planned"]} planned | {data["coverage"]["covered"]} covered | {data["coverage"]["pending"]} pending | {data["coverage"]["percent"]}% coverage', styles["body"]))
    story.append(_coverage_table(data, styles))

    story.append(PageBreak())
    story.append(_p("Execution history", styles["h1"]))
    story.append(_runs_table(data, styles))

    if (getattr(plan, "plan_type", "") or "") == "End-to-End":
        _e2e_story(story, data, styles)

    doc.build(story, onFirstPage=_page_footer, onLaterPages=_page_footer)
    output.seek(0)
    return output


def _inject_export_link(hub, response, plan_id, report=False):
    if response.status_code != 200 or "text/html" not in (response.content_type or ""):
        return response
    html = response.get_data(as_text=True)
    if 'data-test-plan-export-link="1"' in html:
        return response
    href = hub.url_for("export_test_plan_pdf", plan_id=plan_id)
    if report:
        link = f'<a class="button" data-test-plan-export-link="1" href="{href}">Download PDF</a>'
        marker = '<div class="report-actions">'
        if marker in html:
            pos = html.find("</div>", html.find(marker))
            if pos >= 0:
                html = html[:pos] + link + html[pos:]
    else:
        link = f'<a class="secondary" data-test-plan-export-link="1" href="{href}">Export PDF</a>'
        marker = '<nav class="process-tabs"'
        if marker in html:
            pos = html.find("</nav>", html.find(marker))
            if pos >= 0:
                html = html[:pos] + link + html[pos:]
        elif "</main>" in html:
            html = html.replace("</main>", link + "</main>", 1)
    if "data-test-plan-export-css" not in html:
        html = html.replace("</head>", f'<style data-test-plan-export-css>{EXPORT_CSS}</style></head>', 1)
    response.set_data(html)
    return response


def register_test_plan_export(hub):
    """Add downloadable PDF export for every Test Plan type."""
    if getattr(hub.app, "_test_plan_export_registered", False):
        return

    @hub.app.get("/test-plans/<int:plan_id>/export.pdf")
    def export_test_plan_pdf(plan_id):
        plan = hub.db.session.get(hub.TestPlan, plan_id)
        if plan is None:
            return "Test Plan not found.", 404
        if not _reportlab_available():
            return "PDF export requires reportlab. Install test_hub/requirements.txt first.", 503
        output = _build_pdf(hub, plan)
        return send_file(output, mimetype="application/pdf", as_attachment=True, download_name=f"{_filename(plan.name)}_Test_Plan.pdf")

    original_details = hub.app.view_functions.get("test_plan_details")
    if original_details is not None:
        @wraps(original_details)
        def test_plan_details_with_export(plan_id):
            return _inject_export_link(hub, hub.app.make_response(original_details(plan_id)), plan_id, report=False)
        hub.app.view_functions["test_plan_details"] = test_plan_details_with_export

    original_report = hub.app.view_functions.get("test_plan_report")
    if original_report is not None:
        @wraps(original_report)
        def test_plan_report_with_export(plan_id):
            return _inject_export_link(hub, hub.app.make_response(original_report(plan_id)), plan_id, report=True)
        hub.app.view_functions["test_plan_report"] = test_plan_report_with_export

    hub.app._test_plan_export_registered = True
