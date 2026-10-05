from datetime import datetime, timezone

RISK_LEVELS = ("Low", "Medium", "High", "Critical")
RELEASE_DECISIONS = ("Not Assessed", "Ready", "Ready with known risks", "Not Ready")
EXPLORATORY_STATUSES = ("Planned", "In Progress", "Completed")
BLOCK_REASONS = (
    "Environment unavailable", "Test data unavailable", "Dependency incomplete",
    "Defect prevents testing", "Requirement unclear", "Access / permission", "Other",
)
PLAN_STAGE_NAMES = (
    "Scope & Strategy",
    "Coverage",
    "Test Cases Ready",
    "Execution",
    "Defects & Retest",
    "QA Sign-off",
    "Complete",
)

from qa_workspace_ui import CSS, JS, PAGE


def _risk_score(profile, case=None):
    values = {"Low": 1, "Medium": 2, "High": 3, "Critical": 4}
    if profile:
        return sum(
            values.get(getattr(profile, field, "Medium"), 2)
            for field in (
                "business_impact",
                "change_complexity",
                "regression_risk",
                "user_frequency",
            )
        )
    return values.get(getattr(case, "priority", "Medium"), 2) + 5


def _risk_label(score):
    return "Critical" if score >= 14 else "High" if score >= 11 else "Medium" if score >= 8 else "Low"


def register_qa_workflow(hub):
    if getattr(hub.app, "_qa_workflow_registered", False):
        return

    class QaRiskProfile(hub.db.Model):
        __tablename__ = "qa_risk_profiles"
        id = hub.db.Column(hub.db.Integer, primary_key=True)
        test_case_id = hub.db.Column(
            hub.db.Integer,
            hub.db.ForeignKey("test_cases.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
            index=True,
        )
        business_impact = hub.db.Column(hub.db.String(20), nullable=False, default="Medium")
        change_complexity = hub.db.Column(hub.db.String(20), nullable=False, default="Medium")
        regression_risk = hub.db.Column(hub.db.String(20), nullable=False, default="Medium")
        user_frequency = hub.db.Column(hub.db.String(20), nullable=False, default="Medium")
        notes = hub.db.Column(hub.db.Text, nullable=False, default="")
        updated_at = hub.db.Column(
            hub.db.DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.now(timezone.utc),
            onupdate=lambda: datetime.now(timezone.utc),
        )

    class QaRetestLink(hub.db.Model):
        __tablename__ = "qa_retest_links"
        id = hub.db.Column(hub.db.Integer, primary_key=True)
        source_result_id = hub.db.Column(
            hub.db.Integer,
            hub.db.ForeignKey("test_results.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
            index=True,
        )
        defect_key = hub.db.Column(hub.db.String(50), nullable=False, default="")
        state = hub.db.Column(hub.db.String(40), nullable=False, default="Ready for Retest")
        retest_run_id = hub.db.Column(
            hub.db.Integer,
            hub.db.ForeignKey("test_runs.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        )
        created_at = hub.db.Column(
            hub.db.DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.now(timezone.utc),
        )

    class QaExploratorySession(hub.db.Model):
        __tablename__ = "qa_exploratory_sessions"
        id = hub.db.Column(hub.db.Integer, primary_key=True)
        title = hub.db.Column(hub.db.String(250), nullable=False)
        charter = hub.db.Column(hub.db.Text, nullable=False)
        status = hub.db.Column(hub.db.String(30), nullable=False, default="Planned")
        duration_minutes = hub.db.Column(hub.db.Integer, nullable=False, default=0)
        environment = hub.db.Column(hub.db.String(120), nullable=False, default="")
        jira_keys = hub.db.Column(hub.db.String(500), nullable=False, default="")
        coverage = hub.db.Column(hub.db.Text, nullable=False, default="")
        notes = hub.db.Column(hub.db.Text, nullable=False, default="")
        created_at = hub.db.Column(
            hub.db.DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.now(timezone.utc),
        )
        updated_at = hub.db.Column(
            hub.db.DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.now(timezone.utc),
            onupdate=lambda: datetime.now(timezone.utc),
        )

    class QaReleaseDecision(hub.db.Model):
        __tablename__ = "qa_release_decisions"
        id = hub.db.Column(hub.db.Integer, primary_key=True)
        release_id = hub.db.Column(
            hub.db.Integer,
            hub.db.ForeignKey("releases.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
            index=True,
        )
        decision = hub.db.Column(hub.db.String(40), nullable=False, default="Not Assessed")
        comment = hub.db.Column(hub.db.Text, nullable=False, default="")
        updated_at = hub.db.Column(
            hub.db.DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.now(timezone.utc),
            onupdate=lambda: datetime.now(timezone.utc),
        )

    class QaResultContext(hub.db.Model):
        __tablename__ = "qa_result_context"
        id = hub.db.Column(hub.db.Integer, primary_key=True)
        test_result_id = hub.db.Column(
            hub.db.Integer,
            hub.db.ForeignKey("test_results.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
            index=True,
        )
        blocked_reason = hub.db.Column(hub.db.String(80), nullable=False, default="")
        tester_notes = hub.db.Column(hub.db.Text, nullable=False, default="")
        evidence_url = hub.db.Column(hub.db.String(500), nullable=False, default="")
        updated_at = hub.db.Column(
            hub.db.DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.now(timezone.utc),
            onupdate=lambda: datetime.now(timezone.utc),
        )

    hub.QaRiskProfile, hub.QaRetestLink = QaRiskProfile, QaRetestLink
    hub.QaExploratorySession = QaExploratorySession
    hub.QaReleaseDecision = QaReleaseDecision
    hub.QaResultContext = QaResultContext
    with hub.app.app_context():
        hub.db.create_all()

    def latest():
        out = {}
        results = hub.db.session.scalars(
            hub.db.select(hub.TestResult).order_by(
                hub.TestResult.executed_at.desc(),
                hub.TestResult.id.desc(),
            )
        ).all()
        for result in results:
            if result.test_case_id and result.test_case_id not in out:
                out[result.test_case_id] = result
        return out

    def defects(ids):
        model = getattr(hub, "TestResultDefectLink", None)
        out = {}
        if model and ids:
            links = hub.db.session.scalars(
                hub.db.select(model).where(model.test_result_id.in_(ids))
            ).all()
            for link in links:
                out.setdefault(link.test_result_id, []).append(link.jira_key)
        return out

    def work():
        last = latest()
        ids = [result.id for result in last.values()]
        defect_map = defects(ids)
        retests = {
            item.source_result_id: item
            for item in hub.db.session.scalars(
                hub.db.select(QaRetestLink).where(QaRetestLink.source_result_id.in_(ids))
            ).all()
        } if ids else {}
        contexts = {
            item.test_result_id: item
            for item in hub.db.session.scalars(
                hub.db.select(QaResultContext).where(QaResultContext.test_result_id.in_(ids))
            ).all()
        } if ids else {}
        data = {"testing": [], "retest": [], "blocked": [], "auto_failed": []}

        cases = hub.db.session.scalars(
            hub.db.select(hub.TestCase).order_by(hub.TestCase.case_key)
        ).all()
        for case in cases:
            result = last.get(case.id)
            if case.status == "Ready" and not result:
                data["testing"].append({"case": case})
                continue
            if not result:
                continue

            row = {
                "case": case,
                "result": result,
                "defects": defect_map.get(result.id, []),
                "retest": retests.get(result.id),
                "context": contexts.get(result.id),
            }
            row["state"] = row["retest"].state if row["retest"] else "Needs Retest"
            if row["retest"] and row["retest"].retest_run_id:
                retest_run = hub.db.session.get(hub.TestRun, row["retest"].retest_run_id)
                retest_latest = hub.test_run_latest_results(retest_run) if retest_run else {}
                statuses = {item.result for item in retest_latest.values()}
                row["state"] = (
                    "Verified" if statuses == {"Passed"}
                    else "Retest Failed" if "Failed" in statuses
                    else "Retest Blocked" if "Blocked" in statuses
                    else "Retest Created"
                )
            if result.result == "Failed":
                data["retest"].append(row)
                if case.type == "Automated":
                    data["auto_failed"].append(row)
            elif result.result == "Blocked":
                data["blocked"].append(row)

        return {key: value[:30] for key, value in data.items()}

    def gaps():
        pending = []
        jira = []
        if hasattr(hub, "TestPlanItem"):
            items = hub.db.session.scalars(
                hub.db.select(hub.TestPlanItem)
                .where(hub.TestPlanItem.test_case_id.is_(None))
                .order_by(hub.TestPlanItem.test_plan_id, hub.TestPlanItem.position)
            ).all()[:40]
            for item in items:
                plan = hub.db.session.get(hub.TestPlan, item.test_plan_id)
                if plan:
                    pending.append({"plan": plan, "item": item})

        plan_jira = getattr(hub, "TestPlanJiraLink", None)
        item_jira = getattr(hub, "TestPlanItemJiraLink", None)
        if plan_jira and item_jira and hasattr(hub, "TestPlanItem"):
            for link in hub.db.session.scalars(hub.db.select(plan_jira)).all():
                plan = hub.db.session.get(hub.TestPlan, link.test_plan_id)
                if not plan:
                    continue
                item_ids = [item.id for item in plan.items]
                direct = bool(
                    item_ids
                    and hub.db.session.scalar(
                        hub.db.select(item_jira.id)
                        .where(
                            item_jira.test_plan_item_id.in_(item_ids),
                            item_jira.jira_key == link.jira_key,
                        )
                        .limit(1)
                    )
                )
                via_case = any(
                    item.test_case and link.jira_key in item.test_case.jira_keys
                    for item in plan.items
                )
                if not direct and not via_case:
                    jira.append({"plan": plan, "jira_key": link.jira_key})

        ready = hub.db.session.scalars(
            hub.db.select(hub.TestCase)
            .where(hub.TestCase.status == "Ready")
            .order_by(hub.TestCase.case_key)
        ).all()
        return {
            "pending": pending[:30],
            "jira": jira[:30],
            "never": [case for case in ready if not case.results][:30],
            "unclassified": [case for case in ready if not case.suite_tag_list][:30],
        }

    def profiles():
        return {
            item.test_case_id: item
            for item in hub.db.session.scalars(hub.db.select(QaRiskProfile)).all()
        }

    def risk_rows(cases):
        profile_map = profiles()
        rows = []
        for case in cases:
            score = _risk_score(profile_map.get(case.id), case)
            rows.append({
                "case": case,
                "profile": profile_map.get(case.id),
                "score": score,
                "label": _risk_label(score),
            })
        return sorted(rows, key=lambda row: (-row["score"], row["case"].case_key))

    def release_scope(release):
        out = {}
        model = getattr(hub, "TestPlanReleaseLink", None)
        if model and hasattr(hub, "TestPlanItem"):
            plan_ids = list(
                hub.db.session.scalars(
                    hub.db.select(model.test_plan_id).where(model.release_id == release.id)
                ).all()
            )
            if plan_ids:
                items = hub.db.session.scalars(
                    hub.db.select(hub.TestPlanItem).where(
                        hub.TestPlanItem.test_plan_id.in_(plan_ids),
                        hub.TestPlanItem.test_case_id.is_not(None),
                    )
                ).all()
                for item in items:
                    if item.test_case:
                        out[item.test_case.id] = item.test_case
        for run in release.runs:
            for item in run.items:
                if item.test_case:
                    out[item.test_case.id] = item.test_case
        return list(out.values())

    def readiness():
        decisions = {
            item.release_id: item
            for item in hub.db.session.scalars(hub.db.select(QaReleaseDecision)).all()
        }
        profile_map = profiles()
        out = []
        releases = hub.db.session.scalars(
            hub.db.select(hub.Release)
            .order_by(hub.Release.release_date.desc(), hub.Release.id.desc())
            .limit(8)
        ).all()
        for release in releases:
            scope = release_scope(release)
            ids = {case.id for case in scope}
            last = {}
            query = (
                hub.db.select(hub.TestResult)
                .join(hub.TestRun, hub.TestResult.test_run_id == hub.TestRun.id)
                .where(hub.TestRun.release_id == release.id)
                .order_by(hub.TestResult.executed_at.desc(), hub.TestResult.id.desc())
            )
            for result in hub.db.session.scalars(query).all():
                if result.test_case_id in ids and result.test_case_id not in last:
                    last[result.test_case_id] = result

            total = len(scope)
            executed = len(last)
            passed = sum(result.result == "Passed" for result in last.values())
            failed = sum(result.result == "Failed" for result in last.values())
            blocked = sum(result.result == "Blocked" for result in last.values())
            critical = [
                case for case in scope
                if case.priority == "Critical"
                and last.get(case.id)
                and last[case.id].result == "Failed"
            ]
            high = [
                case for case in scope
                if _risk_score(profile_map.get(case.id), case) >= 11
            ]
            high_missing = [case for case in high if case.id not in last]
            smoke = [case for case in scope if "smoke" in case.suite_tag_list]
            smoke_bad = [
                case for case in smoke
                if not last.get(case.id) or last[case.id].result != "Passed"
            ]
            criteria = [
                {"label": "Execution complete", "state": executed == total if total else None, "detail": f"{executed}/{total}" if total else "No scope"},
                {"label": "No Critical failures", "state": not critical if total else None, "detail": f"{len(critical)} failed"},
                {"label": "No blocked", "state": blocked == 0 if executed else None, "detail": f"{blocked} blocked"},
                {"label": "High-risk tested", "state": not high_missing if high else None, "detail": f"{len(high_missing)} untested" if high else "No high-risk scope"},
                {"label": "Smoke passed", "state": not smoke_bad if smoke else None, "detail": f"{len(smoke_bad)} missing/failed" if smoke else "No smoke scope"},
            ]
            out.append({
                "release": release,
                "total": total,
                "executed": executed,
                "passed": passed,
                "failed": failed,
                "blocked": blocked,
                "criteria": criteria,
                "decision": decisions.get(release.id),
            })
        return out

    def create_run(name, cases, execution="Automated", environment="", release=None, source=None):
        run = hub.TestRun(
            release_id=release.id if release else None,
            name=name[:250],
            preset="Custom",
            execution_type=execution if execution in {"Manual", "Automated"} else "Automated",
            environment=environment[:80],
            execution_status="Planned",
        )
        hub.db.session.add(run)
        hub.db.session.flush()
        for position, case in enumerate(cases, 1):
            hub.db.session.add(hub.TestRunItem(
                test_run_id=run.id,
                test_case_id=case.id,
                position=position,
                case_key_snapshot=case.case_key,
                case_title_snapshot=case.title,
                feature_snapshot=case.feature_name,
            ))

        link_model = getattr(hub, "TestPlanRunLink", None)
        if link_model:
            plan_ids = set()
            if source:
                plan_ids.update(
                    hub.db.session.scalars(
                        hub.db.select(link_model.test_plan_id)
                        .where(link_model.test_run_id == source.id)
                    ).all()
                )
            if release and hasattr(hub, "TestPlanReleaseLink"):
                plan_ids.update(
                    hub.db.session.scalars(
                        hub.db.select(hub.TestPlanReleaseLink.test_plan_id)
                        .where(hub.TestPlanReleaseLink.release_id == release.id)
                    ).all()
                )
            for plan_id in plan_ids:
                hub.db.session.add(link_model(test_plan_id=plan_id, test_run_id=run.id))
        return run

    def linked_plan_runs(plan):
        link_model = getattr(hub, "TestPlanRunLink", None)
        if not link_model:
            return []
        run_ids = list(
            hub.db.session.scalars(
                hub.db.select(link_model.test_run_id)
                .where(link_model.test_plan_id == plan.id)
            ).all()
        )
        if not run_ids:
            return []
        runs = hub.db.session.scalars(
            hub.db.select(hub.TestRun)
            .where(hub.TestRun.id.in_(run_ids))
            .order_by(hub.TestRun.created_at.desc(), hub.TestRun.id.desc())
        ).all()
        return list(runs)

    def plan_assessment(plan):
        model = getattr(hub, "TestPlanAssessment", None)
        if not model:
            return None
        return hub.db.session.scalar(
            hub.db.select(model).where(model.test_plan_id == plan.id)
        )

    def plan_stage(plan):
        items = list(plan.items)
        total = len(items)
        covered_items = [item for item in items if item.test_case is not None]
        covered = len(covered_items)
        pending = total - covered
        covered_case_ids = {item.test_case_id for item in covered_items if item.test_case_id}
        runs = linked_plan_runs(plan)

        latest_by_case = {}
        for run in runs:
            for result in sorted(
                run.results,
                key=lambda item: (item.executed_at or datetime.min.replace(tzinfo=timezone.utc), item.id),
                reverse=True,
            ):
                if result.test_case_id in covered_case_ids and result.test_case_id not in latest_by_case:
                    latest_by_case[result.test_case_id] = result

        executed = len(latest_by_case)
        passed = sum(result.result == "Passed" for result in latest_by_case.values())
        failed = sum(result.result == "Failed" for result in latest_by_case.values())
        blocked = sum(result.result == "Blocked" for result in latest_by_case.values())
        not_run = max(covered - executed, 0)
        assessment = plan_assessment(plan)
        active_run = next(
            (run for run in runs if run.execution_status in {"Planned", "Queued", "Running"}),
            None,
        )

        if plan.status == "Completed":
            stage_index = 6
            next_action = "Plan completed"
            action_label = "Open plan"
            action_url = hub.url_for("test_plan_details", plan_id=plan.id)
        elif total == 0:
            stage_index = 0
            next_action = "Define the scope and add planned coverage"
            action_label = "Define coverage"
            action_url = hub.url_for("test_plan_details", plan_id=plan.id) + "#coverage"
        elif pending > 0:
            stage_index = 1
            next_action = f"Create or attach {pending} missing Test Case{'s' if pending != 1 else ''}"
            action_label = "Continue coverage"
            action_url = hub.url_for("test_plan_details", plan_id=plan.id) + "#coverage"
        elif not runs:
            stage_index = 2
            next_action = "Create a Test Run from the covered Test Cases"
            action_label = "Create Test Run"
            action_url = hub.url_for("test_plan_details", plan_id=plan.id) + "#executions"
        elif failed or blocked:
            stage_index = 4
            issues = []
            if failed:
                issues.append(f"{failed} failed")
            if blocked:
                issues.append(f"{blocked} blocked")
            next_action = "Resolve " + " · ".join(issues) + " and retest"
            action_label = "Review failures"
            action_url = hub.url_for("test_plan_details", plan_id=plan.id) + "#traceability"
        elif not_run > 0 or active_run:
            stage_index = 3
            next_action = f"Execute {not_run} remaining Test Case{'s' if not_run != 1 else ''}"
            action_label = "Continue Test Run" if active_run else "Open executions"
            action_url = (
                hub.url_for("test_run_details", run_id=active_run.id)
                if active_run
                else hub.url_for("test_plan_details", plan_id=plan.id) + "#executions"
            )
        else:
            stage_index = 5
            qa_status = getattr(assessment, "qa_status", "Not Assessed") if assessment else "Not Assessed"
            if qa_status == "Ready":
                next_action = "QA assessment is Ready — mark the Test Plan Completed when the release decision is final"
            else:
                next_action = "Review the evidence and record the QA assessment"
            action_label = "QA sign-off"
            action_url = hub.url_for("test_plan_details", plan_id=plan.id) + "#assessment"

        steps = []
        for index, name in enumerate(PLAN_STAGE_NAMES):
            if stage_index == 6:
                state = "done"
            elif index < stage_index:
                state = "done"
            elif index == stage_index:
                state = "current"
            else:
                state = "future"
            steps.append({"name": name, "state": state})

        release_names = []
        release_link_model = getattr(hub, "TestPlanReleaseLink", None)
        if release_link_model:
            release_ids = list(
                hub.db.session.scalars(
                    hub.db.select(release_link_model.release_id)
                    .where(release_link_model.test_plan_id == plan.id)
                ).all()
            )
            if release_ids:
                release_names = list(
                    hub.db.session.scalars(
                        hub.db.select(hub.Release.version)
                        .where(hub.Release.id.in_(release_ids))
                    ).all()
                )

        return {
            "plan": plan,
            "stage": PLAN_STAGE_NAMES[stage_index],
            "stage_index": stage_index,
            "steps": steps,
            "total": total,
            "covered": covered,
            "pending": pending,
            "executed": executed,
            "passed": passed,
            "failed": failed,
            "blocked": blocked,
            "not_run": not_run,
            "runs": runs,
            "active_run": active_run,
            "assessment": assessment,
            "release_names": release_names,
            "next_action": next_action,
            "action_label": action_label,
            "action_url": action_url,
        }

    def sprint_summary():
        active_plans = hub.db.session.scalars(
            hub.db.select(hub.TestPlan)
            .where(hub.TestPlan.status == "Active")
            .order_by(hub.TestPlan.updated_at.desc(), hub.TestPlan.id.desc())
        ).all() if hasattr(hub, "TestPlan") else []
        rows = [plan_stage(plan) for plan in active_plans]
        planned = sum(row["total"] for row in rows)
        covered = sum(row["covered"] for row in rows)
        executed = sum(row["executed"] for row in rows)
        passed = sum(row["passed"] for row in rows)
        failed = sum(row["failed"] for row in rows)
        blocked = sum(row["blocked"] for row in rows)
        return {
            "plans": rows,
            "plan_count": len(rows),
            "planned": planned,
            "covered": covered,
            "executed": executed,
            "passed": passed,
            "failed": failed,
            "blocked": blocked,
            "coverage_pct": round((covered / planned) * 100) if planned else 0,
            "execution_pct": round((executed / covered) * 100) if covered else 0,
        }

    def active_run_tasks(sprint):
        tasks = []
        seen = set()
        for plan_row in sprint["plans"]:
            for run in plan_row["runs"]:
                if run.id in seen or run.execution_status not in {"Planned", "Queued", "Running"}:
                    continue
                summary = hub.test_run_summary(run)
                if summary.get("not_run", 0) <= 0:
                    continue
                seen.add(run.id)
                tasks.append({
                    "kind": "execution",
                    "priority": 4,
                    "label": "Execution",
                    "title": run.name,
                    "meta": f"{summary['not_run']} of {summary['total']} tests still Not Run · {plan_row['plan'].name}",
                    "action_label": "Continue Test Run",
                    "action_url": hub.url_for("test_run_details", run_id=run.id),
                })
        return tasks

    def today_queue(work_data, gap_data, sprint):
        tasks = []
        for row in work_data["blocked"]:
            tasks.append({
                "kind": "blocked",
                "priority": 1,
                "label": "Blocker",
                "title": f"{row['case'].case_key} — {row['case'].title}",
                "meta": row["context"].blocked_reason if row["context"] else "Blocked reason not recorded",
                "action_label": "Open result",
                "action_url": hub.url_for("test_case_details", case_key=row["case"].case_key),
            })
        for row in work_data["retest"]:
            tasks.append({
                "kind": "retest",
                "priority": 2,
                "label": "Retest",
                "title": f"{row['case'].case_key} — {row['case'].title}",
                "meta": ("Defect " + ", ".join(row["defects"])) if row["defects"] else row["state"],
                "action_label": "Open retest" if row["retest"] and row["retest"].retest_run_id else "Review failure",
                "action_url": (
                    hub.url_for("test_run_details", run_id=row["retest"].retest_run_id)
                    if row["retest"] and row["retest"].retest_run_id
                    else hub.url_for("test_case_details", case_key=row["case"].case_key)
                ),
            })
        for row in work_data["auto_failed"]:
            tasks.append({
                "kind": "automation",
                "priority": 3,
                "label": "Automation",
                "title": f"{row['case'].case_key} — {row['case'].title}",
                "meta": (row["result"].error_message or row["result"].notes or "Automated test failed")[:160],
                "action_label": "Inspect run",
                "action_url": hub.url_for("test_run_details", run_id=row["result"].test_run_id),
            })
        tasks.extend(active_run_tasks(sprint))

        active_plan_ids = {row["plan"].id for row in sprint["plans"]}
        for gap in gap_data["pending"]:
            if active_plan_ids and gap["plan"].id not in active_plan_ids:
                continue
            tasks.append({
                "kind": "coverage",
                "priority": 5,
                "label": "Coverage",
                "title": gap["plan"].name,
                "meta": f"Missing Test Case · {gap['item'].title_snapshot}",
                "action_label": "Open Coverage",
                "action_url": hub.url_for("test_plan_details", plan_id=gap["plan"].id) + "#coverage",
            })
        for case in gap_data["never"]:
            tasks.append({
                "kind": "testing",
                "priority": 6,
                "label": "Needs Testing",
                "title": f"{case.case_key} — {case.title}",
                "meta": f"{case.feature_name} · {case.priority} · never executed",
                "action_label": "Open Test Case",
                "action_url": hub.url_for("test_case_details", case_key=case.case_key),
            })
        for plan_row in sprint["plans"]:
            if plan_row["stage"] == "QA Sign-off":
                tasks.append({
                    "kind": "signoff",
                    "priority": 7,
                    "label": "QA Sign-off",
                    "title": plan_row["plan"].name,
                    "meta": plan_row["next_action"],
                    "action_label": "Review sign-off",
                    "action_url": plan_row["action_url"],
                })
        tasks.sort(key=lambda item: (item["priority"], item["title"]))
        return tasks[:12]

    def render(analysis=None, inp=None, failure_ai=None):
        active_tab = "impact" if analysis or failure_ai else "work"
        cases = hub.db.session.scalars(
            hub.db.select(hub.TestCase).order_by(hub.TestCase.case_key)
        ).all()
        releases = hub.db.session.scalars(
            hub.db.select(hub.Release)
            .order_by(hub.Release.release_date.desc(), hub.Release.id.desc())
        ).all()
        analysis_cases = []
        if analysis:
            by_key = {row["case"].case_key: row for row in analysis.get("suggestions", [])}
            for item in analysis.get("cases", []):
                if "row" in item:
                    analysis_cases.append(item)
                elif by_key.get(item.get("case_key")):
                    base = by_key[item["case_key"]]
                    analysis_cases.append({
                        "row": base,
                        "relevance": item.get("relevance", base["relevance"]),
                        "reason": item.get("reason", base["reason"]),
                    })

        work_data = work()
        gap_data = gaps()
        sprint = sprint_summary()
        today = today_queue(work_data, gap_data, sprint)
        recommended = today[0] if today else (
            {
                "label": sprint["plans"][0]["stage"],
                "title": sprint["plans"][0]["plan"].name,
                "meta": sprint["plans"][0]["next_action"],
                "action_label": sprint["plans"][0]["action_label"],
                "action_url": sprint["plans"][0]["action_url"],
            }
            if sprint["plans"] else None
        )

        return hub.render_template_string(
            PAGE,
            css=CSS,
            js=JS,
            active_tab=active_tab,
            work=work_data,
            gaps=gap_data,
            sprint=sprint,
            today=today,
            recommended=recommended,
            readiness=readiness(),
            cases=cases,
            releases=releases,
            risks=risk_rows(cases),
            risk_levels=RISK_LEVELS,
            risk_fields=(
                ("business_impact", "Business impact"),
                ("change_complexity", "Change complexity"),
                ("regression_risk", "Regression risk"),
                ("user_frequency", "User frequency"),
            ),
            block_reasons=BLOCK_REASONS,
            release_decisions=RELEASE_DECISIONS,
            sessions=hub.db.session.scalars(
                hub.db.select(QaExploratorySession)
                .order_by(QaExploratorySession.updated_at.desc())
                .limit(30)
            ).all(),
            exploratory_statuses=EXPLORATORY_STATUSES,
            automation=hub.qa_automation_health(),
            clusters=hub.qa_failure_clusters(),
            analysis=analysis,
            analysis_cases=analysis_cases,
            inp=inp,
            failure_ai=failure_ai,
        )

    @hub.app.get("/qa-workspace")
    def qa_workspace():
        return render()

    @hub.app.post("/qa-workspace/risk")
    def qa_risk():
        raw = hub.request.form.get("case_id", "")
        if not raw.isdigit():
            return "Select a Test Case.", 400
        case = hub.db.session.get(hub.TestCase, int(raw))
        if not case:
            return "Test Case not found.", 404
        profile = hub.db.session.scalar(
            hub.db.select(QaRiskProfile).where(QaRiskProfile.test_case_id == case.id)
        ) or QaRiskProfile(test_case_id=case.id)
        hub.db.session.add(profile)
        for field in ("business_impact", "change_complexity", "regression_risk", "user_frequency"):
            value = hub.request.form.get(field, "Medium").strip()
            if value not in RISK_LEVELS:
                return "Invalid risk value.", 400
            setattr(profile, field, value)
        profile.notes = hub.request.form.get("notes", "").strip()
        hub.db.session.commit()
        return hub.redirect(hub.url_for("qa_workspace") + "#risk")

    @hub.app.post("/qa-workspace/results/<int:result_id>/context")
    def qa_result_context(result_id):
        result = hub.db.session.get(hub.TestResult, result_id)
        if not result:
            return "Test Result not found.", 404
        context = hub.db.session.scalar(
            hub.db.select(QaResultContext).where(QaResultContext.test_result_id == result.id)
        ) or QaResultContext(test_result_id=result.id)
        hub.db.session.add(context)
        reason = hub.request.form.get("blocked_reason", "").strip()
        if reason and reason not in BLOCK_REASONS:
            return "Invalid blocked reason.", 400
        context.blocked_reason = reason
        context.tester_notes = hub.request.form.get("tester_notes", "").strip()
        hub.db.session.commit()
        return hub.redirect(hub.url_for("qa_workspace") + "#work")

    @hub.app.post("/qa-workspace/retest/<int:result_id>/ready")
    def qa_mark_retest(result_id):
        result = hub.db.session.get(hub.TestResult, result_id)
        if not result or result.result != "Failed":
            return "Failed result not found.", 404
        defect_key = hub.request.form.get("defect_key", "").strip().upper()
        if defect_key:
            try:
                parsed = hub.parse_jira_keys(defect_key)
            except ValueError as exc:
                return str(exc), 400
            if len(parsed) != 1:
                return "Enter one defect Jira key.", 400
            defect_key = parsed[0]
            link_model = getattr(hub, "TestResultDefectLink", None)
            if link_model is not None:
                exists = hub.db.session.scalar(
                    hub.db.select(link_model.id).where(
                        link_model.test_result_id == result.id,
                        link_model.jira_key == defect_key,
                    )
                )
                if exists is None:
                    # Keep the defect in the existing result traceability instead of a parallel defect store.
                    hub.db.session.add(link_model(test_result_id=result.id, jira_key=defect_key))
        link = hub.db.session.scalar(
            hub.db.select(QaRetestLink).where(QaRetestLink.source_result_id == result.id)
        ) or QaRetestLink(source_result_id=result.id)
        hub.db.session.add(link)
        link.defect_key = defect_key
        link.state = "Ready for Retest"
        hub.db.session.commit()
        return hub.redirect(hub.url_for("qa_workspace") + "#work")

    @hub.app.post("/qa-workspace/retest/<int:result_id>/create")
    def qa_create_retest(result_id):
        result = hub.db.session.get(hub.TestResult, result_id)
        if not result or result.result != "Failed" or not result.test_case:
            return "Failed result with Test Case not found.", 404
        link = hub.db.session.scalar(
            hub.db.select(QaRetestLink).where(QaRetestLink.source_result_id == result.id)
        ) or QaRetestLink(source_result_id=result.id)
        hub.db.session.add(link)
        if link.retest_run_id:
            return hub.redirect(hub.url_for("test_run_details", run_id=link.retest_run_id))
        source = result.test_run
        run = create_run(
            f"Retest — {result.case_key_snapshot} — {link.defect_key or 'failed result'}",
            [result.test_case],
            source.execution_type if source else result.test_case.type,
            source.environment if source else "",
            source.release if source else None,
            source,
        )
        link.retest_run_id = run.id
        link.state = "Retest Created"
        hub.db.session.commit()
        return hub.redirect(hub.url_for("test_run_details", run_id=run.id))

    @hub.app.post("/qa-workspace/release/<int:release_id>/decision")
    def qa_release_decision(release_id):
        release = hub.db.session.get(hub.Release, release_id)
        if not release:
            return "Release not found.", 404
        value = hub.request.form.get("decision", "Not Assessed").strip()
        if value not in RELEASE_DECISIONS:
            return "Invalid QA decision.", 400
        decision = hub.db.session.scalar(
            hub.db.select(QaReleaseDecision).where(QaReleaseDecision.release_id == release.id)
        ) or QaReleaseDecision(release_id=release.id)
        hub.db.session.add(decision)
        decision.decision = value
        decision.comment = hub.request.form.get("comment", "").strip()
        hub.db.session.commit()
        return hub.redirect(hub.url_for("qa_workspace") + "#release")

    @hub.app.post("/qa-workspace/exploratory")
    def qa_exploratory():
        title = hub.request.form.get("title", "").strip()
        charter = hub.request.form.get("charter", "").strip()
        if not title or not charter:
            return "Title and charter are required.", 400
        try:
            minutes = max(0, int(hub.request.form.get("duration_minutes", "0") or 0))
        except ValueError:
            return "Duration must be numeric.", 400
        jira_text = hub.request.form.get("jira_keys", "").strip()
        if jira_text:
            try:
                jira_text = ", ".join(hub.parse_jira_keys(jira_text))
            except ValueError as exc:
                return str(exc), 400
        hub.db.session.add(QaExploratorySession(
            title=title[:250],
            charter=charter,
            duration_minutes=minutes,
            environment=hub.request.form.get("environment", "").strip()[:120],
            jira_keys=jira_text,
            coverage=hub.request.form.get("coverage", "").strip(),
            notes=hub.request.form.get("notes", "").strip(),
        ))
        hub.db.session.commit()
        return hub.redirect(hub.url_for("qa_workspace") + "#explore")

    @hub.app.post("/qa-workspace/exploratory/<int:session_id>/status")
    def qa_exploratory_status(session_id):
        session = hub.db.session.get(QaExploratorySession, session_id)
        if not session:
            return "Session not found.", 404
        value = hub.request.form.get("status", "").strip()
        if value not in EXPLORATORY_STATUSES:
            return "Invalid status.", 400
        session.status = value
        hub.db.session.commit()
        return hub.redirect(hub.url_for("qa_workspace") + "#explore")

    @hub.app.post("/qa-workspace/impact")
    def qa_impact():
        text = hub.request.form.get("change_description", "").strip()
        jira_key = hub.request.form.get("jira_key", "").strip().upper()
        release_value = hub.request.form.get("release_id", "").strip()
        release_id = int(release_value) if release_value.isdigit() else None
        if not text:
            return "Describe the change.", 400
        return render(
            hub.qa_ai_impact_analysis(text, jira_key, release_id),
            {"change_description": text, "jira_key": jira_key, "release_id": release_id},
        )

    @hub.app.post("/qa-workspace/failures/analyze")
    def qa_failure_ai():
        return render(failure_ai=hub.qa_ai_failure_summary())

    @hub.app.post("/qa-workspace/smart-run")
    def qa_smart_run():
        try:
            ids = [int(value) for value in hub.request.form.getlist("case_ids")]
        except ValueError:
            return "Invalid Test Case selection.", 400
        found = hub.db.session.scalars(
            hub.db.select(hub.TestCase).where(hub.TestCase.id.in_(ids))
        ).all() if ids else []
        by_id = {case.id: case for case in found}
        cases = [by_id[case_id] for case_id in ids if case_id in by_id]
        if not cases:
            return "Select at least one Test Case.", 400
        release_value = hub.request.form.get("release_id", "").strip()
        release = hub.db.session.get(hub.Release, int(release_value)) if release_value.isdigit() else None
        run = create_run(
            hub.request.form.get("name", "Impact Test Run").strip() or "Impact Test Run",
            cases,
            hub.request.form.get("execution_type", "Automated").strip(),
            hub.request.form.get("environment", "").strip(),
            release,
        )
        hub.db.session.commit()
        return hub.redirect(hub.url_for("test_run_details", run_id=run.id))

    # Make the Workplace the application landing page while preserving the
    # existing `index` endpoint as the canonical Test Cases repository URL.
    original_index = hub.app.view_functions.get("index")
    root_rule = next(
        (rule for rule in hub.app.url_map.iter_rules() if rule.rule == "/" and rule.endpoint == "index"),
        None,
    )
    if original_index is None or root_rule is None:
        raise RuntimeError("QA Workplace could not remap the existing Test Cases landing route.")

    # Rebind only the endpoint of the already-compiled root rule; the URL pattern
    # itself stays unchanged, so Flask continues matching `/` normally.
    endpoint_rules = hub.app.url_map._rules_by_endpoint
    if root_rule in endpoint_rules.get("index", []):
        endpoint_rules["index"].remove(root_rule)
    root_rule.endpoint = "qa_dashboard"
    endpoint_rules.setdefault("qa_dashboard", []).append(root_rule)
    hub.app.view_functions["qa_dashboard"] = qa_workspace
    hub.app.add_url_rule("/test-cases", endpoint="index", view_func=original_index, methods=["GET"])
    hub.app.url_map._remap = True
    hub.app.url_map.update()

    @hub.app.after_request
    def qa_nav(response):
        # Product redesign is registered later, therefore it runs first in Flask's
        # reverse after_request order and provides the sidebar we refine here.
        if response.status_code != 200 or "text/html" not in (response.content_type or ""):
            return response
        html = response.get_data(as_text=True)
        if "prd-sidebar" not in html:
            return response

        # The Test Hub brand is the Dashboard/Home action, while Test Cases keeps
        # its own `/test-cases` destination through the preserved `index` endpoint.
        html = html.replace(
            '<a class="prd-brand" href="/test-cases">',
            '<a class="prd-brand" href="/">',
            1,
        )

        nav_start = html.find('<nav class="prd-nav">')
        nav_end = html.find("</nav>", nav_start)
        if nav_start < 0 or nav_end < 0:
            response.set_data(html)
            return response

        nav = html[nav_start:nav_end]
        # Remove the older injected QA Workspace item if an earlier response layer
        # produced it, then add Dashboard as the first Quality navigation item.
        nav = nav.replace(
            '<a class="" href="/qa-workspace"><i>◎</i>QA Workspace</a>',
            "",
        ).replace(
            '<a class="prd-active" href="/qa-workspace"><i>◎</i>QA Workspace</a>',
            "",
        )
        quality_marker = '<div class="prd-nav-label">Quality</div>'
        dashboard_active = hub.request.path in {"/", "/qa-workspace"}
        if dashboard_active:
            nav = nav.replace(" prd-active", "")
        dashboard_link = (
            f'<a class="{"prd-active" if dashboard_active else ""}" href="/">'
            '<i>▦</i>Dashboard</a>'
        )
        if '<i>▦</i>Dashboard' not in nav:
            nav = nav.replace(quality_marker, quality_marker + dashboard_link, 1)

        response.set_data(html[:nav_start] + nav + html[nav_end:])
        return response

    hub.app._qa_workflow_registered = True
