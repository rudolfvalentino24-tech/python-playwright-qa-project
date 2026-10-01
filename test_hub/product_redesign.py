import re


REDESIGN_CSS = r"""
:root{
  --prd-bg:#f6f8fb;--prd-surface:#fff;--prd-line:#e4e7ec;--prd-text:#172033;
  --prd-muted:#667085;--prd-blue:#2563eb;--prd-green:#15803d;--prd-red:#b42318;
  --prd-amber:#b54708;--prd-sidebar:238px
}
*{box-sizing:border-box}
html,body{background:var(--prd-bg)!important}
body.product-redesign{margin:0!important;padding-left:var(--prd-sidebar)!important;color:var(--prd-text)!important;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif!important}
body.product-redesign>.th-nav,body.product-redesign>header{display:none!important}
.prd-sidebar{position:fixed;inset:0 auto 0 0;width:var(--prd-sidebar);z-index:500;display:flex;flex-direction:column;background:#101828;color:#d0d5dd;border-right:1px solid #1d2939}
.prd-brand{height:72px;display:flex;align-items:center;gap:10px;padding:0 18px;color:#fff;text-decoration:none;border-bottom:1px solid #1d2939}
.prd-logo{width:34px;height:34px;display:grid;place-items:center;border-radius:10px;background:#2563eb;color:#fff;font-weight:900}.prd-brand strong{font-size:18px}.prd-brand strong span{color:#84adff}
.prd-nav{padding:16px 11px;overflow:auto}.prd-nav-label{padding:14px 10px 7px;color:#667085;font-size:10px;font-weight:800;letter-spacing:.12em;text-transform:uppercase}
.prd-nav a{display:flex;align-items:center;gap:10px;min-height:42px;margin:2px 0;padding:0 11px;border-radius:8px;color:#d0d5dd;text-decoration:none;font-size:13px;font-weight:650}
.prd-nav a:hover{background:#1d2939;color:#fff}.prd-nav a.prd-active{background:#344054;color:#fff}.prd-nav i{width:18px;text-align:center;font-style:normal;color:#98a2b3}
.prd-side-foot{margin-top:auto;padding:14px 12px 18px;border-top:1px solid #1d2939}.prd-side-foot div{padding:10px 11px;border-radius:8px;background:#1d2939;color:#98a2b3;font-size:11px;line-height:1.45}
.prd-topbar{position:fixed;top:0;left:var(--prd-sidebar);right:0;z-index:450;height:64px;display:flex;align-items:center;justify-content:space-between;padding:0 26px;background:rgba(255,255,255,.96);border-bottom:1px solid var(--prd-line);backdrop-filter:blur(10px)}
.prd-topbar strong{font-size:13px;color:#344054}.prd-topbar span{font-size:11px;color:#98a2b3}.prd-mobile{display:none;border:0;background:#f2f4f7;border-radius:8px;width:34px;height:34px;cursor:pointer}
body.product-redesign main{max-width:1500px!important;margin:0 auto!important;padding:92px 28px 48px!important}
body.product-redesign .th-page{max-width:1500px!important;padding:92px 28px 48px!important}
body.product-redesign .th-card,body.product-redesign .panel,body.product-redesign .card,body.product-redesign section,body.product-redesign article{box-shadow:none!important}
body.product-redesign .th-card,body.product-redesign .panel,body.product-redesign .card{border-color:var(--prd-line)!important;border-radius:12px!important;background:#fff!important}
body.product-redesign h1{font-size:28px!important;line-height:1.15!important;letter-spacing:-.7px!important;color:#101828!important}
body.product-redesign h2{color:#101828!important}
body.product-redesign .subtitle,body.product-redesign .muted,body.product-redesign .panel-sub{color:var(--prd-muted)!important}
body.product-redesign .primary{background:#2563eb!important;border-radius:8px!important;box-shadow:none!important}
body.product-redesign .secondary{background:#fff!important;border:1px solid #d0d5dd!important;border-radius:8px!important;color:#344054!important}
body.product-redesign .danger{background:#fff!important;border:1px solid #fecdca!important;border-radius:8px!important;color:#b42318!important}
body.product-redesign input,body.product-redesign select,body.product-redesign textarea{border-color:#d0d5dd!important;border-radius:8px!important;box-shadow:none!important}
body.product-redesign table{border-collapse:collapse!important}
body.product-redesign th{background:#f9fafb!important;color:#667085!important;text-transform:uppercase;font-size:10px!important;letter-spacing:.04em}
body.product-redesign td{border-color:#f0f2f5!important}
body.product-redesign .badge,body.product-redesign .state,body.product-redesign .status-pill,body.product-redesign .process-badge{border-radius:999px!important;font-weight:750!important}
body.product-redesign .page-grid,body.product-redesign .plans-grid{grid-template-columns:1fr!important}
body.product-redesign .side-stack{position:static!important}
body.product-redesign .ai-card{display:none!important}
body.product-redesign .create-card.prd-moved,body.product-redesign #create-run.prd-moved,body.product-redesign #create-release.prd-moved{display:block!important}
.prd-page-actions{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:0 0 16px}
.prd-btn{min-height:36px;display:inline-flex;align-items:center;justify-content:center;gap:7px;padding:0 12px;border:1px solid #d0d5dd;border-radius:8px;background:#fff;color:#344054;text-decoration:none;font:inherit;font-size:12px;font-weight:700;cursor:pointer}
.prd-btn-primary{background:#2563eb;color:#fff;border-color:#2563eb}.prd-btn-danger{color:#b42318;border-color:#fecdca}
.prd-kpi-row{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px;margin:0 0 18px}.prd-kpi{padding:14px 16px;border:1px solid var(--prd-line);border-radius:10px;background:#fff}.prd-kpi small{display:block;color:#667085;font-size:10px;font-weight:750;text-transform:uppercase}.prd-kpi strong{display:block;margin-top:5px;color:#101828;font-size:23px}
.prd-modal-backdrop{position:fixed;inset:0;z-index:1000;display:none;align-items:center;justify-content:center;padding:22px;background:rgba(16,24,40,.55);backdrop-filter:blur(3px)}
.prd-modal-backdrop.prd-open{display:flex}.prd-modal{width:min(720px,100%);max-height:88vh;display:flex;flex-direction:column;border-radius:14px;background:#fff;box-shadow:0 24px 80px rgba(16,24,40,.28);overflow:hidden}.prd-modal.prd-lg{width:min(960px,100%)}
.prd-modal-head{display:flex;align-items:flex-start;justify-content:space-between;gap:14px;padding:17px 20px;border-bottom:1px solid var(--prd-line)}.prd-modal-head h2{margin:0!important;font-size:17px!important}.prd-modal-head p{margin:4px 0 0;color:#667085;font-size:11px}
.prd-modal-body{padding:18px 20px;overflow:auto}.prd-modal-foot{display:flex;justify-content:flex-end;gap:8px;padding:13px 20px;border-top:1px solid var(--prd-line);background:#fcfcfd}
.prd-close{width:34px;height:34px;border:0;border-radius:8px;background:#f2f4f7;color:#667085;cursor:pointer;font-size:18px}
.prd-tabs{display:flex;gap:2px;padding:4px;margin:0 0 16px;background:#f2f4f7;border-radius:9px;width:max-content;max-width:100%;overflow:auto}
.prd-tab{min-height:34px;padding:0 12px;border:0;border-radius:7px;background:transparent;color:#667085;font:inherit;font-size:11px;font-weight:750;cursor:pointer;white-space:nowrap}.prd-tab.prd-active{background:#fff;color:#101828;box-shadow:0 1px 2px rgba(16,24,40,.06)}
.prd-tab-panel{display:none}.prd-tab-panel.prd-active{display:block}
.prd-plan-head-actions{display:flex;gap:8px;justify-content:flex-end;flex-wrap:wrap;margin:0 0 14px}
.prd-plan-shell .grid{display:block!important}.prd-plan-shell .side-stack{display:none!important}.prd-plan-shell .process-grid{display:block!important;margin-top:0!important}
.prd-plan-shell .process-card{margin:0 0 14px!important}.prd-plan-shell #scope,.prd-plan-shell #executions,.prd-plan-shell #traceability,.prd-plan-shell #assessment{width:100%!important}
.prd-plan-shell #create-plan-run{display:none!important}
.prd-plan-shell .coverage-panel{width:100%!important}
.prd-row-menu{position:relative}.prd-row-menu>summary{list-style:none}.prd-row-menu>summary::-webkit-details-marker{display:none}
.prd-row-menu>div{position:absolute;right:0;top:36px;z-index:90;width:190px;padding:6px;border:1px solid var(--prd-line);border-radius:10px;background:#fff;box-shadow:0 16px 42px rgba(16,24,40,.14)}
.prd-row-menu button,.prd-row-menu a{width:100%;display:block;padding:8px 9px;border:0;border-radius:7px;background:transparent;color:#344054;text-align:left;text-decoration:none;font:inherit;font-size:11px;cursor:pointer}.prd-row-menu button:hover,.prd-row-menu a:hover{background:#f2f4f7}
.prd-search{width:100%;height:38px;padding:0 10px;margin-bottom:10px;border:1px solid #d0d5dd;border-radius:8px}
.prd-modal-body .case-list{max-height:440px!important;overflow:auto!important}.prd-modal-body .process-form{display:grid!important}
@media(max-width:900px){.prd-kpi-row{grid-template-columns:repeat(2,1fr)}}
@media(max-width:760px){
  :root{--prd-sidebar:0px}.prd-sidebar{width:238px;transform:translateX(-100%);transition:transform .18s ease}.prd-sidebar.prd-open{transform:translateX(0)}
  .prd-topbar{left:0;padding:0 14px}.prd-mobile{display:block}body.product-redesign{padding-left:0!important}
  body.product-redesign main,body.product-redesign .th-page{padding:84px 14px 36px!important}
}
"""

REDESIGN_JS = r"""
(function(){
  function qs(sel,root){return (root||document).querySelector(sel)}
  function qsa(sel,root){return Array.from((root||document).querySelectorAll(sel))}
  function openModal(id){const el=document.getElementById(id);if(el)el.classList.add('prd-open')}
  function closeModal(id){const el=document.getElementById(id);if(el)el.classList.remove('prd-open')}
  window.prdOpen=openModal;window.prdClose=closeModal;

  function modalize(node,id,title,subtitle,large){
    if(!node||node.dataset.prdModalized)return null;
    node.dataset.prdModalized='1';node.classList.add('prd-moved');
    const wrap=document.createElement('div');wrap.id=id;wrap.className='prd-modal-backdrop';
    wrap.innerHTML='<div class="prd-modal '+(large?'prd-lg':'')+'"><div class="prd-modal-head"><div><h2>'+title+'</h2><p>'+(subtitle||'')+'</p></div><button class="prd-close" type="button" data-prd-close="'+id+'">×</button></div><div class="prd-modal-body"></div></div>';
    wrap.querySelector('.prd-modal-body').appendChild(node);
    document.body.appendChild(wrap);
    return wrap;
  }

  function addButton(parent,label,id,primary){
    if(!parent||document.querySelector('[data-prd-open="'+id+'"]'))return;
    const b=document.createElement('button');b.type='button';b.className='prd-btn '+(primary?'prd-btn-primary':'');b.dataset.prdOpen=id;b.textContent=label;parent.appendChild(b);
  }

  function headingNode(text){
    return qsa('h1,h2,h3,strong').find(x=>x.textContent.trim().toLowerCase()===text.toLowerCase());
  }

  function sectionByHeading(text){
    const h=headingNode(text);return h?h.closest('aside,section,article,.th-card,.panel,.side-card,.card'):null;
  }

  function setupGeneralCreateModals(){
    const pageHead=qs('.page-head')||qs('.results-head')||qs('.top')||qs('main');
    let node=qs('#create-case');
    if(node){modalize(node,'prdCreateCase','Create Test Case','Add a new QA test case without leaving the list.',true);addButton(pageHead,'+ New Test Case','prdCreateCase',true)}
    node=qs('#create-plan');
    if(node){
      modalize(node,'prdCreatePlan','Create Test Plan','Define the QA scope before execution begins.',false);
      const oldLink=qs('a[href="#create-plan"]');if(oldLink){oldLink.href='#';oldLink.dataset.prdOpen='prdCreatePlan';oldLink.textContent='+ Create Test Plan'}
      else addButton(pageHead,'+ Create Test Plan','prdCreatePlan',true);
    }
    node=qs('#create-run')||sectionByHeading('Create test run');
    if(node){
      modalize(node,'prdCreateRun','Create Test Run','Choose scope, environment and execution type.',true);
      const oldLink=qs('a[href="#create-run"]');if(oldLink){oldLink.href='#';oldLink.dataset.prdOpen='prdCreateRun';oldLink.textContent='+ Create Test Run'}
      else addButton(pageHead,'+ Create Test Run','prdCreateRun',true);
    }
    node=qs('#create-release')||sectionByHeading('Create release');
    if(node){
      modalize(node,'prdCreateRelease','Create Release','Create a delivery milestone for QA evidence.',false);
      const oldLink=qs('a[href="#create-release"]');if(oldLink){oldLink.href='#';oldLink.dataset.prdOpen='prdCreateRelease';oldLink.textContent='+ Create Release'}
      else addButton(pageHead,'+ Create Release','prdCreateRelease',true);
    }
  }

  function setupTestPlan(){
    if(!/^\/test-plans\/\d+\/?$/.test(location.pathname))return;
    const main=qs('main.th-page')||qs('main');if(!main)return;
    main.classList.add('prd-plan-shell');

    const top=qs('.top',main)||qs('.page-head',main);
    const actions=document.createElement('div');actions.className='prd-plan-head-actions';
    if(top)top.insertAdjacentElement('afterend',actions);

    const attach=sectionByHeading('Attach existing Test Cases');
    if(attach){modalize(attach,'prdAttachCases','Attach Test Cases','Search and attach existing Test Cases to this plan.',true);addButton(actions,'Attach Test Cases','prdAttachCases',false)}
    const add=sectionByHeading('Add planned Test Case');
    if(add){modalize(add,'prdAddCoverage','Add planned coverage','Define required coverage before the real Test Case exists.',false);addButton(actions,'+ Add coverage','prdAddCoverage',true)}

    const createRun=qs('#create-plan-run');
    if(createRun){modalize(createRun,'prdCreatePlanRun','Create Test Run from Plan','Use covered Test Cases and keep the run linked to this plan.',true);addButton(actions,'+ Create Test Run','prdCreatePlanRun',true)}

    const scope=qs('#scope'),exec=qs('#executions'),trace=qs('#traceability'),assessment=qs('#assessment');
    let coverage=sectionByHeading('Coverage checklist');
    if(coverage)coverage.classList.add('coverage-panel');

    const oldTabs=qs('.process-tabs');if(oldTabs)oldTabs.remove();
    const tabs=document.createElement('div');tabs.className='prd-tabs';
    const defs=[['overview','Overview'],['coverage','Coverage'],['executions','Executions'],['traceability','Traceability'],['report','Report']];
    defs.forEach((d,i)=>{const b=document.createElement('button');b.className='prd-tab '+(i===0?'prd-active':'');b.type='button';b.dataset.prdTab=d[0];b.textContent=d[1];tabs.appendChild(b)});
    actions.insertAdjacentElement('afterend',tabs);

    const host=document.createElement('div');host.className='prd-plan-panels';tabs.insertAdjacentElement('afterend',host);
    function panel(name,node){const p=document.createElement('div');p.className='prd-tab-panel '+(name==='overview'?'prd-active':'');p.dataset.prdPanel=name;if(node)p.appendChild(node);host.appendChild(p);return p}
    panel('overview',scope);panel('coverage',coverage);panel('executions',exec);panel('traceability',trace);panel('report',assessment);

    // Move inline item editing and case-link forms into small pop-ups.
    qsa('.planned-edit').forEach((details,idx)=>{
      const item=details.closest('.item');const form=qs('form',details);if(!item||!form)return;
      const id='prdEditCoverage'+idx;details.remove();const wrap=modalize(form,id,'Edit planned coverage','Update the requirement without changing the linked Test Case.',false);
      if(wrap){const controls=qs('.item-controls',item);addButton(controls,'Edit',id,false)}
    });
    qsa('form.attach-inline').forEach((form,idx)=>{
      const item=form.closest('.item');if(!item)return;
      const id='prdLinkCase'+idx;const label=(form.textContent||'').includes('Change')?'Change Test Case':'Attach Test Case';
      modalize(form,id,label,'Choose the Test Case that implements this planned coverage.',true);
      const controls=qs('.item-controls',item);addButton(controls,label,id,false)
    });
  }

  function setupTabs(){
    document.addEventListener('click',e=>{
      const open=e.target.closest('[data-prd-open]');if(open){e.preventDefault();openModal(open.dataset.prdOpen)}
      const close=e.target.closest('[data-prd-close]');if(close){e.preventDefault();closeModal(close.dataset.prdClose)}
      if(e.target.classList.contains('prd-modal-backdrop'))e.target.classList.remove('prd-open');
      const tab=e.target.closest('[data-prd-tab]');if(tab){
        qsa('.prd-tab').forEach(x=>x.classList.remove('prd-active'));
        qsa('.prd-tab-panel').forEach(x=>x.classList.remove('prd-active'));
        tab.classList.add('prd-active');const p=qs('[data-prd-panel="'+tab.dataset.prdTab+'"]');if(p)p.classList.add('prd-active');
      }
    });
  }

  function setupSidebar(){
    const btn=qs('#prdMobileToggle'),side=qs('#prdSidebar');if(btn&&side)btn.addEventListener('click',()=>side.classList.toggle('prd-open'))
  }

  setupTabs();setupSidebar();setupGeneralCreateModals();setupTestPlan();
})();
"""

SIDEBAR_TEMPLATE = r"""
<aside id="prdSidebar" class="prd-sidebar">
  <a class="prd-brand" href="{{ url_for('index') }}"><span class="prd-logo">T</span><strong>Test <span>Hub</span></strong></a>
  <nav class="prd-nav">
    <div class="prd-nav-label">Quality</div>
    <a class="{% if active=='cases' %}prd-active{% endif %}" href="{{ url_for('index') }}"><i>▣</i>Test Cases</a>
    <a class="{% if active=='plans' %}prd-active{% endif %}" href="{{ url_for('test_plans') }}"><i>☑</i>Test Plans</a>
    <a class="{% if active=='runs' %}prd-active{% endif %}" href="{{ url_for('test_runs') }}"><i>▷</i>Test Runs</a>
    <a class="{% if active=='results' %}prd-active{% endif %}" href="{{ url_for('results_dashboard') }}"><i>▥</i>Results</a>
    <div class="prd-nav-label">Delivery</div>
    <a class="{% if active=='releases' %}prd-active{% endif %}" href="{{ url_for('releases') }}"><i>◇</i>Releases</a>
    <div class="prd-nav-label">Tools</div>
    <a class="{% if active=='ai' %}prd-active{% endif %}" href="{{ url_for('ai_test_designer') }}"><i>✦</i>AI Test Designer</a>
  </nav>
  <div class="prd-side-foot"><div>QA workspace<br><strong style="color:#d0d5dd">Jira · Jenkins · Playwright</strong></div></div>
</aside>
<div class="prd-topbar">
  <div style="display:flex;align-items:center;gap:9px"><button id="prdMobileToggle" class="prd-mobile" type="button">☰</button><strong>Test Hub</strong><span>QA workspace</span></div>
</div>
"""


def _active_section(path):
    if path.startswith("/test-plans"):
        return "plans"
    if path.startswith("/test-runs"):
        return "runs"
    if path.startswith("/results"):
        return "results"
    if path.startswith("/releases"):
        return "releases"
    if path.startswith("/ai-test") or path.startswith("/ai/"):
        return "ai"
    return "cases"


def register_product_redesign(hub):
    """Apply one product design system to every Test Hub HTML page."""
    if getattr(hub.app, "_product_redesign_registered", False):
        return

    @hub.app.after_request
    def product_redesign_response(response):
        if response.status_code != 200 or "text/html" not in (response.content_type or ""):
            return response

        html = response.get_data(as_text=True)
        if "data-product-redesign" in html or "<body" not in html:
            return response

        active = _active_section(hub.request.path)
        sidebar = hub.render_template_string(SIDEBAR_TEMPLATE, active=active)

        # Keep all existing forms/routes intact; only replace the presentation shell.
        html = html.replace("</head>", "<style data-product-redesign>"+REDESIGN_CSS+"</style></head>", 1)
        html = re.sub(
            r"<body[^>]*>",
            lambda match: '<body class="product-redesign" data-product-redesign="1">'+sidebar,
            html,
            count=1,
            flags=re.IGNORECASE,
        )
        html = html.replace("</body>", "<script>"+REDESIGN_JS+"</script></body>", 1)
        response.set_data(html)
        return response

    hub.app._product_redesign_registered = True
