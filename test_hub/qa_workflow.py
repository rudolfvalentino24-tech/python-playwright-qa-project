from datetime import datetime, timezone

RISK_LEVELS = ("Low", "Medium", "High", "Critical")
RELEASE_DECISIONS = ("Not Assessed", "Ready", "Ready with known risks", "Not Ready")
EXPLORATORY_STATUSES = ("Planned", "In Progress", "Completed")
BLOCK_REASONS = (
    "Environment unavailable", "Test data unavailable", "Dependency incomplete",
    "Defect prevents testing", "Requirement unclear", "Access / permission", "Other",
)

from qa_workspace_ui import CSS, JS, PAGE


def _risk_score(profile, case=None):
    values = {"Low": 1, "Medium": 2, "High": 3, "Critical": 4}
    if profile:
        return sum(values.get(getattr(profile, f, "Medium"), 2) for f in ("business_impact", "change_complexity", "regression_risk", "user_frequency"))
    return values.get(getattr(case, "priority", "Medium"), 2) + 5


def _risk_label(score):
    return "Critical" if score >= 14 else "High" if score >= 11 else "Medium" if score >= 8 else "Low"


def register_qa_workflow(hub):
    if getattr(hub.app, "_qa_workflow_registered", False):
        return

    class QaRiskProfile(hub.db.Model):
        __tablename__ = "qa_risk_profiles"
        id = hub.db.Column(hub.db.Integer, primary_key=True)
        test_case_id = hub.db.Column(hub.db.Integer, hub.db.ForeignKey("test_cases.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
        business_impact = hub.db.Column(hub.db.String(20), nullable=False, default="Medium")
        change_complexity = hub.db.Column(hub.db.String(20), nullable=False, default="Medium")
        regression_risk = hub.db.Column(hub.db.String(20), nullable=False, default="Medium")
        user_frequency = hub.db.Column(hub.db.String(20), nullable=False, default="Medium")
        notes = hub.db.Column(hub.db.Text, nullable=False, default="")
        updated_at = hub.db.Column(hub.db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    class QaRetestLink(hub.db.Model):
        __tablename__ = "qa_retest_links"
        id = hub.db.Column(hub.db.Integer, primary_key=True)
        source_result_id = hub.db.Column(hub.db.Integer, hub.db.ForeignKey("test_results.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
        defect_key = hub.db.Column(hub.db.String(50), nullable=False, default="")
        state = hub.db.Column(hub.db.String(40), nullable=False, default="Ready for Retest")
        retest_run_id = hub.db.Column(hub.db.Integer, hub.db.ForeignKey("test_runs.id", ondelete="SET NULL"), nullable=True, index=True)
        created_at = hub.db.Column(hub.db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

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
        created_at = hub.db.Column(hub.db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
        updated_at = hub.db.Column(hub.db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    class QaReleaseDecision(hub.db.Model):
        __tablename__ = "qa_release_decisions"
        id = hub.db.Column(hub.db.Integer, primary_key=True)
        release_id = hub.db.Column(hub.db.Integer, hub.db.ForeignKey("releases.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
        decision = hub.db.Column(hub.db.String(40), nullable=False, default="Not Assessed")
        comment = hub.db.Column(hub.db.Text, nullable=False, default="")
        updated_at = hub.db.Column(hub.db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    class QaResultContext(hub.db.Model):
        __tablename__ = "qa_result_context"
        id = hub.db.Column(hub.db.Integer, primary_key=True)
        test_result_id = hub.db.Column(hub.db.Integer, hub.db.ForeignKey("test_results.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
        blocked_reason = hub.db.Column(hub.db.String(80), nullable=False, default="")
        tester_notes = hub.db.Column(hub.db.Text, nullable=False, default="")
        evidence_url = hub.db.Column(hub.db.String(500), nullable=False, default="")
        updated_at = hub.db.Column(hub.db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    hub.QaRiskProfile, hub.QaRetestLink = QaRiskProfile, QaRetestLink
    hub.QaExploratorySession, hub.QaReleaseDecision, hub.QaResultContext = QaExploratorySession, QaReleaseDecision, QaResultContext
    with hub.app.app_context():
        hub.db.create_all()

    def latest():
        out = {}
        for r in hub.db.session.scalars(hub.db.select(hub.TestResult).order_by(hub.TestResult.executed_at.desc(), hub.TestResult.id.desc())).all():
            if r.test_case_id and r.test_case_id not in out:
                out[r.test_case_id] = r
        return out

    def defects(ids):
        model = getattr(hub, "TestResultDefectLink", None)
        out = {}
        if model and ids:
            for x in hub.db.session.scalars(hub.db.select(model).where(model.test_result_id.in_(ids))).all():
                out.setdefault(x.test_result_id, []).append(x.jira_key)
        return out

    def work():
        last = latest(); ids = [r.id for r in last.values()]; dmap = defects(ids)
        ret = {x.source_result_id:x for x in hub.db.session.scalars(hub.db.select(QaRetestLink).where(QaRetestLink.source_result_id.in_(ids))).all()} if ids else {}
        ctx = {x.test_result_id:x for x in hub.db.session.scalars(hub.db.select(QaResultContext).where(QaResultContext.test_result_id.in_(ids))).all()} if ids else {}
        data = {"testing":[], "retest":[], "blocked":[], "auto_failed":[]}
        for c in hub.db.session.scalars(hub.db.select(hub.TestCase).order_by(hub.TestCase.case_key)).all():
            r = last.get(c.id)
            if c.status == "Ready" and not r:
                data["testing"].append({"case":c}); continue
            if not r: continue
            row = {"case":c,"result":r,"defects":dmap.get(r.id,[]),"retest":ret.get(r.id),"context":ctx.get(r.id)}
            row["state"] = row["retest"].state if row["retest"] else "Needs Retest"
            if row["retest"] and row["retest"].retest_run_id:
                rr = hub.db.session.get(hub.TestRun, row["retest"].retest_run_id)
                rr_latest = hub.test_run_latest_results(rr) if rr else {}
                statuses = {x.result for x in rr_latest.values()}
                row["state"] = "Verified" if statuses == {"Passed"} else "Retest Failed" if "Failed" in statuses else "Retest Blocked" if "Blocked" in statuses else "Retest Created"
            if r.result == "Failed":
                data["retest"].append(row)
                if c.type == "Automated": data["auto_failed"].append(row)
            elif r.result == "Blocked": data["blocked"].append(row)
        return {k:v[:30] for k,v in data.items()}

    def gaps():
        pending=[]; jira=[]
        if hasattr(hub,"TestPlanItem"):
            for i in hub.db.session.scalars(hub.db.select(hub.TestPlanItem).where(hub.TestPlanItem.test_case_id.is_(None)).order_by(hub.TestPlanItem.test_plan_id,hub.TestPlanItem.position)).all()[:40]:
                p=hub.db.session.get(hub.TestPlan,i.test_plan_id)
                if p: pending.append({"plan":p,"item":i})
        plink=getattr(hub,"TestPlanJiraLink",None); ilink=getattr(hub,"TestPlanItemJiraLink",None)
        if plink and ilink and hasattr(hub,"TestPlanItem"):
            for x in hub.db.session.scalars(hub.db.select(plink)).all():
                p=hub.db.session.get(hub.TestPlan,x.test_plan_id)
                if not p: continue
                item_ids=[i.id for i in p.items]
                direct = bool(item_ids and hub.db.session.scalar(hub.db.select(ilink.id).where(ilink.test_plan_item_id.in_(item_ids),ilink.jira_key==x.jira_key).limit(1)))
                via_case=any(i.test_case and x.jira_key in i.test_case.jira_keys for i in p.items)
                if not direct and not via_case: jira.append({"plan":p,"jira_key":x.jira_key})
        ready=hub.db.session.scalars(hub.db.select(hub.TestCase).where(hub.TestCase.status=="Ready").order_by(hub.TestCase.case_key)).all()
        return {"pending":pending[:30],"jira":jira[:30],"never":[c for c in ready if not c.results][:30],"unclassified":[c for c in ready if not c.suite_tag_list][:30]}

    def profiles(): return {x.test_case_id:x for x in hub.db.session.scalars(hub.db.select(QaRiskProfile)).all()}
    def risk_rows(cases):
        p=profiles(); rows=[]
        for c in cases:
            s=_risk_score(p.get(c.id),c); rows.append({"case":c,"profile":p.get(c.id),"score":s,"label":_risk_label(s)})
        return sorted(rows,key=lambda x:(-x["score"],x["case"].case_key))

    def release_scope(rel):
        out={}; model=getattr(hub,"TestPlanReleaseLink",None)
        if model and hasattr(hub,"TestPlanItem"):
            pids=list(hub.db.session.scalars(hub.db.select(model.test_plan_id).where(model.release_id==rel.id)).all())
            if pids:
                for i in hub.db.session.scalars(hub.db.select(hub.TestPlanItem).where(hub.TestPlanItem.test_plan_id.in_(pids),hub.TestPlanItem.test_case_id.is_not(None))).all():
                    if i.test_case: out[i.test_case.id]=i.test_case
        for run in rel.runs:
            for i in run.items:
                if i.test_case: out[i.test_case.id]=i.test_case
        return list(out.values())

    def readiness():
        dec={x.release_id:x for x in hub.db.session.scalars(hub.db.select(QaReleaseDecision)).all()}; p=profiles(); out=[]
        rels=hub.db.session.scalars(hub.db.select(hub.Release).order_by(hub.Release.release_date.desc(),hub.Release.id.desc()).limit(8)).all()
        for rel in rels:
            scope=release_scope(rel); ids={c.id for c in scope}; last={}
            q=hub.db.select(hub.TestResult).join(hub.TestRun,hub.TestResult.test_run_id==hub.TestRun.id).where(hub.TestRun.release_id==rel.id).order_by(hub.TestResult.executed_at.desc(),hub.TestResult.id.desc())
            for r in hub.db.session.scalars(q).all():
                if r.test_case_id in ids and r.test_case_id not in last: last[r.test_case_id]=r
            total=len(scope); executed=len(last); passed=sum(r.result=="Passed" for r in last.values()); failed=sum(r.result=="Failed" for r in last.values()); blocked=sum(r.result=="Blocked" for r in last.values())
            crit=[c for c in scope if c.priority=="Critical" and last.get(c.id) and last[c.id].result=="Failed"]
            high=[c for c in scope if _risk_score(p.get(c.id),c)>=11]; high_missing=[c for c in high if c.id not in last]
            smoke=[c for c in scope if "smoke" in c.suite_tag_list]; smoke_bad=[c for c in smoke if not last.get(c.id) or last[c.id].result!="Passed"]
            cr=[{"label":"Execution complete","state":executed==total if total else None,"detail":f"{executed}/{total}" if total else "No scope"},{"label":"No Critical failures","state":not crit if total else None,"detail":f"{len(crit)} failed"},{"label":"No blocked","state":blocked==0 if executed else None,"detail":f"{blocked} blocked"},{"label":"High-risk tested","state":not high_missing if high else None,"detail":f"{len(high_missing)} untested" if high else "No high-risk scope"},{"label":"Smoke passed","state":not smoke_bad if smoke else None,"detail":f"{len(smoke_bad)} missing/failed" if smoke else "No smoke scope"}]
            out.append({"release":rel,"total":total,"executed":executed,"passed":passed,"failed":failed,"blocked":blocked,"criteria":cr,"decision":dec.get(rel.id)})
        return out

    def create_run(name,cases,execution="Automated",environment="",release=None,source=None):
        run=hub.TestRun(release_id=release.id if release else None,name=name[:250],preset="Custom",execution_type=execution if execution in {"Manual","Automated"} else "Automated",environment=environment[:80],execution_status="Planned")
        hub.db.session.add(run); hub.db.session.flush()
        for n,c in enumerate(cases,1): hub.db.session.add(hub.TestRunItem(test_run_id=run.id,test_case_id=c.id,position=n,case_key_snapshot=c.case_key,case_title_snapshot=c.title,feature_snapshot=c.feature_name))
        link=getattr(hub,"TestPlanRunLink",None)
        if link:
            pids=set()
            if source: pids.update(hub.db.session.scalars(hub.db.select(link.test_plan_id).where(link.test_run_id==source.id)).all())
            if release and hasattr(hub,"TestPlanReleaseLink"): pids.update(hub.db.session.scalars(hub.db.select(hub.TestPlanReleaseLink.test_plan_id).where(hub.TestPlanReleaseLink.release_id==release.id)).all())
            for pid in pids: hub.db.session.add(link(test_plan_id=pid,test_run_id=run.id))
        return run

    def render(analysis=None,inp=None,failure_ai=None):
        active_tab = "impact" if analysis or failure_ai else "work"
        cases=hub.db.session.scalars(hub.db.select(hub.TestCase).order_by(hub.TestCase.case_key)).all(); releases=hub.db.session.scalars(hub.db.select(hub.Release).order_by(hub.Release.release_date.desc(),hub.Release.id.desc())).all()
        analysis_cases=[]
        if analysis:
            by={r["case"].case_key:r for r in analysis.get("suggestions",[])}
            for x in analysis.get("cases",[]):
                if "row" in x: analysis_cases.append(x)
                elif by.get(x.get("case_key")): analysis_cases.append({"row":by[x["case_key"]],"relevance":x.get("relevance",by[x["case_key"]]["relevance"]),"reason":x.get("reason",by[x["case_key"]]["reason"])})
        return hub.render_template_string(PAGE,css=CSS,js=JS,active_tab=active_tab,work=work(),gaps=gaps(),readiness=readiness(),cases=cases,releases=releases,risks=risk_rows(cases),risk_levels=RISK_LEVELS,risk_fields=(("business_impact","Business impact"),("change_complexity","Change complexity"),("regression_risk","Regression risk"),("user_frequency","User frequency")),block_reasons=BLOCK_REASONS,release_decisions=RELEASE_DECISIONS,sessions=hub.db.session.scalars(hub.db.select(QaExploratorySession).order_by(QaExploratorySession.updated_at.desc()).limit(30)).all(),exploratory_statuses=EXPLORATORY_STATUSES,automation=hub.qa_automation_health(),clusters=hub.qa_failure_clusters(),analysis=analysis,analysis_cases=analysis_cases,inp=inp,failure_ai=failure_ai)

    @hub.app.get("/qa-workspace")
    def qa_workspace(): return render()

    @hub.app.post("/qa-workspace/risk")
    def qa_risk():
        raw=hub.request.form.get("case_id","");
        if not raw.isdigit(): return "Select a Test Case.",400
        c=hub.db.session.get(hub.TestCase,int(raw));
        if not c: return "Test Case not found.",404
        p=hub.db.session.scalar(hub.db.select(QaRiskProfile).where(QaRiskProfile.test_case_id==c.id)) or QaRiskProfile(test_case_id=c.id); hub.db.session.add(p)
        for f in ("business_impact","change_complexity","regression_risk","user_frequency"):
            v=hub.request.form.get(f,"Medium").strip();
            if v not in RISK_LEVELS: return "Invalid risk value.",400
            setattr(p,f,v)
        p.notes=hub.request.form.get("notes","").strip(); hub.db.session.commit(); return hub.redirect(hub.url_for("qa_workspace")+"#risk")

    @hub.app.post("/qa-workspace/results/<int:result_id>/context")
    def qa_result_context(result_id):
        r=hub.db.session.get(hub.TestResult,result_id)
        if not r: return "Test Result not found.",404
        x=hub.db.session.scalar(hub.db.select(QaResultContext).where(QaResultContext.test_result_id==r.id)) or QaResultContext(test_result_id=r.id); hub.db.session.add(x)
        reason=hub.request.form.get("blocked_reason","").strip();
        if reason and reason not in BLOCK_REASONS: return "Invalid blocked reason.",400
        x.blocked_reason=reason; x.tester_notes=hub.request.form.get("tester_notes","").strip(); hub.db.session.commit(); return hub.redirect(hub.url_for("qa_workspace")+"#work")

    @hub.app.post("/qa-workspace/retest/<int:result_id>/ready")
    def qa_mark_retest(result_id):
        r=hub.db.session.get(hub.TestResult,result_id)
        if not r or r.result!="Failed": return "Failed result not found.",404
        defect_key=hub.request.form.get("defect_key","").strip().upper()
        if defect_key:
            try:
                parsed=hub.parse_jira_keys(defect_key)
            except ValueError as exc:
                return str(exc),400
            if len(parsed)!=1:
                return "Enter one defect Jira key.",400
            defect_key=parsed[0]
            link_model=getattr(hub,"TestResultDefectLink",None)
            if link_model is not None:
                exists=hub.db.session.scalar(hub.db.select(link_model.id).where(link_model.test_result_id==r.id,link_model.jira_key==defect_key))
                if exists is None:
                    # Keep the defect in the existing result traceability instead of a parallel defect store.
                    hub.db.session.add(link_model(test_result_id=r.id,jira_key=defect_key))
        x=hub.db.session.scalar(hub.db.select(QaRetestLink).where(QaRetestLink.source_result_id==r.id)) or QaRetestLink(source_result_id=r.id)
        hub.db.session.add(x); x.defect_key=defect_key; x.state="Ready for Retest"
        hub.db.session.commit(); return hub.redirect(hub.url_for("qa_workspace")+"#work")

    @hub.app.post("/qa-workspace/retest/<int:result_id>/create")
    def qa_create_retest(result_id):
        r=hub.db.session.get(hub.TestResult,result_id)
        if not r or r.result!="Failed" or not r.test_case: return "Failed result with Test Case not found.",404
        x=hub.db.session.scalar(hub.db.select(QaRetestLink).where(QaRetestLink.source_result_id==r.id)) or QaRetestLink(source_result_id=r.id); hub.db.session.add(x)
        if x.retest_run_id: return hub.redirect(hub.url_for("test_run_details",run_id=x.retest_run_id))
        src=r.test_run; run=create_run(f"Retest — {r.case_key_snapshot} — {x.defect_key or 'failed result'}",[r.test_case],src.execution_type if src else r.test_case.type,src.environment if src else "",src.release if src else None,src); x.retest_run_id=run.id; x.state="Retest Created"; hub.db.session.commit(); return hub.redirect(hub.url_for("test_run_details",run_id=run.id))

    @hub.app.post("/qa-workspace/release/<int:release_id>/decision")
    def qa_release_decision(release_id):
        rel=hub.db.session.get(hub.Release,release_id)
        if not rel: return "Release not found.",404
        v=hub.request.form.get("decision","Not Assessed").strip();
        if v not in RELEASE_DECISIONS: return "Invalid QA decision.",400
        x=hub.db.session.scalar(hub.db.select(QaReleaseDecision).where(QaReleaseDecision.release_id==rel.id)) or QaReleaseDecision(release_id=rel.id); hub.db.session.add(x); x.decision=v; x.comment=hub.request.form.get("comment","").strip(); hub.db.session.commit(); return hub.redirect(hub.url_for("qa_workspace")+"#release")

    @hub.app.post("/qa-workspace/exploratory")
    def qa_exploratory():
        title=hub.request.form.get("title","").strip(); charter=hub.request.form.get("charter","").strip()
        if not title or not charter: return "Title and charter are required.",400
        try: mins=max(0,int(hub.request.form.get("duration_minutes","0") or 0))
        except ValueError: return "Duration must be numeric.",400
        jt=hub.request.form.get("jira_keys","").strip()
        if jt:
            try: jt=", ".join(hub.parse_jira_keys(jt))
            except ValueError as e: return str(e),400
        hub.db.session.add(QaExploratorySession(title=title[:250],charter=charter,duration_minutes=mins,environment=hub.request.form.get("environment","").strip()[:120],jira_keys=jt,coverage=hub.request.form.get("coverage","").strip(),notes=hub.request.form.get("notes","").strip())); hub.db.session.commit(); return hub.redirect(hub.url_for("qa_workspace")+"#explore")

    @hub.app.post("/qa-workspace/exploratory/<int:session_id>/status")
    def qa_exploratory_status(session_id):
        s=hub.db.session.get(QaExploratorySession,session_id)
        if not s: return "Session not found.",404
        v=hub.request.form.get("status","").strip();
        if v not in EXPLORATORY_STATUSES: return "Invalid status.",400
        s.status=v; hub.db.session.commit(); return hub.redirect(hub.url_for("qa_workspace")+"#explore")

    @hub.app.post("/qa-workspace/impact")
    def qa_impact():
        text=hub.request.form.get("change_description","").strip(); jira=hub.request.form.get("jira_key","").strip().upper(); rv=hub.request.form.get("release_id","").strip(); rid=int(rv) if rv.isdigit() else None
        if not text: return "Describe the change.",400
        return render(hub.qa_ai_impact_analysis(text,jira,rid),{"change_description":text,"jira_key":jira,"release_id":rid})

    @hub.app.post("/qa-workspace/failures/analyze")
    def qa_failure_ai(): return render(failure_ai=hub.qa_ai_failure_summary())

    @hub.app.post("/qa-workspace/smart-run")
    def qa_smart_run():
        try: ids=[int(x) for x in hub.request.form.getlist("case_ids")]
        except ValueError: return "Invalid Test Case selection.",400
        found=hub.db.session.scalars(hub.db.select(hub.TestCase).where(hub.TestCase.id.in_(ids))).all() if ids else []; by={c.id:c for c in found}; cases=[by[i] for i in ids if i in by]
        if not cases: return "Select at least one Test Case.",400
        rv=hub.request.form.get("release_id","").strip(); rel=hub.db.session.get(hub.Release,int(rv)) if rv.isdigit() else None
        run=create_run(hub.request.form.get("name","Impact Test Run").strip() or "Impact Test Run",cases,hub.request.form.get("execution_type","Automated").strip(),hub.request.form.get("environment","").strip(),rel); hub.db.session.commit(); return hub.redirect(hub.url_for("test_run_details",run_id=run.id))

    @hub.app.after_request
    def qa_nav(response):
        # Product redesign is registered later, therefore it runs first in Flask's reverse after_request order.
        if response.status_code!=200 or "text/html" not in (response.content_type or ""): return response
        html=response.get_data(as_text=True)
        if "prd-sidebar" not in html or 'href="/qa-workspace"' in html: return response
        a=html.find('<nav class="prd-nav">'); b=html.find("</nav>",a)
        if a<0 or b<0: return response
        nav=html[a:b]
        if hub.request.path.startswith("/qa-workspace"): nav=nav.replace(" prd-active","")
        link=f'<a class="{"prd-active" if hub.request.path.startswith("/qa-workspace") else ""}" href="/qa-workspace"><i>◎</i>QA Workspace</a>'
        marker='<div class="prd-nav-label">Delivery</div>'; nav=nav.replace(marker,link+marker,1) if marker in nav else nav+link
        response.set_data(html[:a]+nav+html[b:]); return response

    hub.app._qa_workflow_registered=True
