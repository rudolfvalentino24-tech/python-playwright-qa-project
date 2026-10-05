import re
from datetime import datetime, timezone
from functools import wraps
from html import escape


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
body.product-redesign .grid.prd-single-column{grid-template-columns:minmax(0,1fr)!important}
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
.prd-form-field{margin:12px 0}.prd-form-field>label{display:block;margin:0 0 6px;color:#41526c;font-size:12px;font-weight:800}.prd-form-field select{width:100%;height:42px;padding:0 10px}
.prd-plan-checks{display:grid;gap:7px;padding:9px;border:1px solid #d0d5dd;border-radius:8px;background:#fcfcfd}.prd-plan-check{display:flex!important;align-items:center;gap:8px;margin:0!important;font-weight:650!important}.prd-plan-check input{width:16px!important;height:16px!important;margin:0!important}.prd-plan-hint{margin-top:5px;color:#667085;font-size:10px}
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

  let planOptionsPromise=null;
  function loadPlanOptions(){
    if(!planOptionsPromise){
      planOptionsPromise=fetch('/api/test-plans/options')
        .then(response=>response.ok?response.json():Promise.reject(new Error('Unable to load Test Plans.')))
        .then(data=>data.plans||[])
        .catch(()=>[]);
    }
    return planOptionsPromise;
  }

  function modalize(node,id,title,subtitle,large){
    if(!node||node.dataset.prdModalized)return null;
    const originalParent=node.parentElement;
    node.dataset.prdModalized='1';node.classList.add('prd-moved');
    const wrap=document.createElement('div');wrap.id=id;wrap.className='prd-modal-backdrop';
    wrap.innerHTML='<div class="prd-modal '+(large?'prd-lg':'')+'"><div class="prd-modal-head"><div><h2>'+title+'</h2><p>'+(subtitle||'')+'</p></div><button class="prd-close" type="button" data-prd-close="'+id+'">×</button></div><div class="prd-modal-body"></div></div>';
    wrap.querySelector('.prd-modal-body').appendChild(node);
    document.body.appendChild(wrap);
    if(originalParent&&originalParent.classList.contains('grid'))originalParent.classList.add('prd-single-column');
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

  function buildSinglePlanField(form,plans,name,labelText,hintText){
    if(!form||form.querySelector('[name="'+name+'"]'))return null;
    const wrap=document.createElement('div');wrap.className='prd-form-field';
    const label=document.createElement('label');label.textContent=labelText||'Test Plan';wrap.appendChild(label);
    const select=document.createElement('select');select.name=name;
    select.innerHTML='<option value="">No Test Plan</option>';
    plans.forEach(plan=>{const option=document.createElement('option');option.value=String(plan.id);option.textContent=plan.name+(plan.status?' · '+plan.status:'');select.appendChild(option)});
    wrap.appendChild(select);
    if(hintText){const hint=document.createElement('div');hint.className='prd-plan-hint';hint.textContent=hintText;wrap.appendChild(hint)}
    return {wrap,select};
  }

  function buildMultiPlanField(form,plans){
    if(!form||form.querySelector('[name="test_plan_ids"]'))return null;
    const wrap=document.createElement('div');wrap.className='prd-form-field';
    const title=document.createElement('label');title.textContent='Test Plans';wrap.appendChild(title);
    const box=document.createElement('div');box.className='prd-plan-checks';
    if(!plans.length){const empty=document.createElement('div');empty.className='prd-plan-hint';empty.textContent='No Test Plans available.';box.appendChild(empty)}
    plans.forEach(plan=>{
      const label=document.createElement('label');label.className='prd-plan-check';
      const input=document.createElement('input');input.type='checkbox';input.name='test_plan_ids';input.value=String(plan.id);
      const span=document.createElement('span');span.textContent=plan.name+(plan.status?' · '+plan.status:'');
      label.appendChild(input);label.appendChild(span);box.appendChild(label);
    });
    wrap.appendChild(box);
    const hint=document.createElement('div');hint.className='prd-plan-hint';hint.textContent='Selected Test Plans will be linked to the new Release.';wrap.appendChild(hint);
    return wrap;
  }

  function setupRunPlanFilter(form,select,plans){
    const preset=qs('#runPreset',form)||qs('[name="preset"]',form);
    const search=qs('#runCaseSearch',form);
    const options=qsa('.case-option',form);

    function enforce(){
      const plan=plans.find(item=>String(item.id)===select.value);
      const allowed=plan?new Set((plan.covered_case_ids||[]).map(String)):null;
      const query=search?search.value.trim().toLowerCase():'';

      if(plan&&preset){
        preset.value='Custom';
        qsa('option',preset).forEach(option=>option.disabled=option.value!=='Custom');
      }else if(preset){
        qsa('option',preset).forEach(option=>option.disabled=false);
      }

      options.forEach(item=>{
        const checkbox=qs('input[type="checkbox"]',item);if(!checkbox)return;
        const planAllowed=!allowed||allowed.has(checkbox.value);
        const searchAllowed=!query||(item.dataset.search||'').includes(query);
        item.style.display=planAllowed&&searchAllowed?'flex':'none';
        if(!planAllowed)checkbox.checked=false;
      });
    }

    select.addEventListener('change',enforce);
    if(search)search.addEventListener('input',()=>setTimeout(enforce,0));
    if(preset)preset.addEventListener('change',()=>setTimeout(enforce,0));
    enforce();
  }

  function setupGeneralCreateModals(){
    const pageHead=qs('.page-head')||qs('.results-head')||qs('.top')||qs('main');

    let node=qs('#create-case');
    if(node){
      modalize(node,'prdCreateCase','Create Test Case','Add a new QA test case without leaving the list.',true);
      const oldLink=qs('a[href="#create-case"]');
      if(oldLink){oldLink.href='#';oldLink.dataset.prdOpen='prdCreateCase';oldLink.textContent='+ Create Test Case'}
      else addButton(pageHead,'+ Create Test Case','prdCreateCase',true);
      const form=qs('form',node);
      loadPlanOptions().then(plans=>{
        const field=buildSinglePlanField(form,plans,'test_plan_id','Test Plan','Optional. The new Test Case becomes Covered in the selected plan.');
        if(field){
          const preconditions=qs('textarea[name="preconditions"]',form);
          const anchor=preconditions?preconditions.closest('.form-field'):null;
          anchor?form.insertBefore(field.wrap,anchor):form.insertBefore(field.wrap,form.querySelector('button[type="submit"]'));
        }
      });
    }

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
      const form=qs('form',node);
      loadPlanOptions().then(plans=>{
        const field=buildSinglePlanField(form,plans,'test_plan_id','Test Plan','Optional. Selecting a plan limits the list to its Covered Test Cases.');
        if(field){
          const releaseSelect=qs('select[name="release_id"]',form);
          const releaseLabel=releaseSelect?releaseSelect.previousElementSibling:null;
          form.insertBefore(field.wrap,releaseLabel||releaseSelect||form.querySelector('button[type="submit"]'));
          setupRunPlanFilter(form,field.select,plans);
        }
      });
    }

    node=qs('#create-release')||sectionByHeading('Create release');
    if(node){
      modalize(node,'prdCreateRelease','Create Release','Create a delivery milestone for QA evidence.',false);
      const oldLink=qs('a[href="#create-release"]');if(oldLink){oldLink.href='#';oldLink.dataset.prdOpen='prdCreateRelease';oldLink.textContent='+ Create Release'}
      else addButton(pageHead,'+ Create Release','prdCreateRelease',true);
      const form=qs('form',node);
      loadPlanOptions().then(plans=>{
        const field=buildMultiPlanField(form,plans);
        if(field){
          const notes=qs('textarea[name="notes"]',form);
          const notesLabel=notes?notes.previousElementSibling:null;
          form.insertBefore(field,notesLabel||notes||form.querySelector('button[type="submit"]'));
        }
      });
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

      const clickedMenu=e.target.closest('.more-menu');
      qsa('.more-menu[open]').forEach(menu=>{if(menu!==clickedMenu)menu.removeAttribute('open')});

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

FAVICON_LINK = (
    '<link rel="icon" type="image/svg+xml" '
    'href="data:image/svg+xml,%3Csvg%20xmlns=%27http://www.w3.org/2000/svg%27%20viewBox=%270%200%2064%2064%27%3E%3Crect%20width=%2764%27%20height=%2764%27%20rx=%2714%27%20fill=%27%232563eb%27/%3E%3Ctext%20x=%2732%27%20y=%2743%27%20text-anchor=%27middle%27%20font-family=%27Arial%2Csans-serif%27%20font-size=%2736%27%20font-weight=%27700%27%20fill=%27white%27%3ET%3C/text%3E%3C/svg%3E">'
)

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
    <a class="{% if active=='help' %}prd-active{% endif %}" href="{{ url_for('help_documentation') }}"><i>?</i>Help & Documentation</a>
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
    # Keep the Help page highlighted while users browse in-app documentation.
    if path.startswith("/help"):
        return "help"
    return "cases"


def _register_test_plan_linking(hub):
    """Reuse existing Test Plan relationship models for create and edit workflows."""
    if getattr(hub.app, "_product_plan_linking_registered", False):
        return

    @hub.app.get("/api/test-plans/options")
    def test_plan_options_api():
        plans = hub.db.session.scalars(
            hub.db.select(hub.TestPlan).order_by(hub.TestPlan.updated_at.desc(), hub.TestPlan.id.desc())
        ).all()
        return hub.jsonify({
            "plans": [
                {
                    "id": plan.id,
                    "name": plan.name,
                    "status": plan.status,
                    "covered_case_ids": [
                        item.test_case.id
                        for item in plan.items
                        if item.test_case is not None
                    ],
                }
                for plan in plans
            ]
        })

    def resolve_plan(raw_value):
        raw_value = (raw_value or "").strip()
        if not raw_value:
            return None, None
        if not raw_value.isdigit():
            return None, ("Invalid Test Plan.", 400)
        plan = hub.db.session.get(hub.TestPlan, int(raw_value))
        if plan is None:
            return None, ("Test Plan not found.", 404)
        return plan, None

    def resolve_plans(raw_values):
        plans = []
        seen = set()
        for raw_value in raw_values:
            raw_value = (raw_value or "").strip()
            if not raw_value:
                continue
            plan, error = resolve_plan(raw_value)
            if error:
                return [], error
            if plan.id not in seen:
                plans.append(plan)
                seen.add(plan.id)
        return plans, None

    def latest_id(model):
        return hub.db.session.scalar(
            hub.db.select(model.id).order_by(model.id.desc()).limit(1)
        ) or 0

    def touch_plan(plan):
        plan.updated_at = datetime.now(timezone.utc)

    original_create_case = hub.app.view_functions.get("create_case")
    if original_create_case is not None:
        @wraps(original_create_case)
        def create_case_with_plan():
            plan, error = resolve_plan(hub.request.form.get("test_plan_id"))
            if error:
                return error

            before_id = latest_id(hub.TestCase)
            response = hub.app.make_response(original_create_case())
            if plan is not None and 300 <= response.status_code < 400:
                case = hub.db.session.scalar(
                    hub.db.select(hub.TestCase)
                    .where(hub.TestCase.id > before_id)
                    .order_by(hub.TestCase.id.desc())
                )
                if case is not None:
                    exists = hub.db.session.scalar(
                        hub.db.select(hub.TestPlanItem.id).where(
                            hub.TestPlanItem.test_plan_id == plan.id,
                            hub.TestPlanItem.test_case_id == case.id,
                        )
                    )
                    if exists is None:
                        position = max((item.position for item in plan.items), default=0) + 1
                        plan.items.append(
                            hub.TestPlanItem(
                                test_case=case,
                                position=position,
                                title_snapshot=case.title,
                                feature_snapshot=case.feature_name,
                            )
                        )
                        touch_plan(plan)
                        hub.db.session.commit()
            return response

        hub.app.view_functions["create_case"] = create_case_with_plan

    original_update_case = hub.app.view_functions.get("update_case")
    if original_update_case is not None:
        @wraps(original_update_case)
        def update_case_with_plans(case_key):
            # Change Test Plan membership only when the edit page actually rendered
            # and submitted its Test Plan controls.
            if hub.request.form.get("test_plan_sync") != "1":
                return original_update_case(case_key)

            plans, error = resolve_plans(hub.request.form.getlist("test_plan_ids"))
            if error:
                return error

            existing_case = hub.db.session.scalar(
                hub.db.select(hub.TestCase).where(hub.TestCase.case_key == case_key)
            )
            case_id = existing_case.id if existing_case is not None else None

            response = hub.app.make_response(original_update_case(case_key))
            if case_id is None or not (300 <= response.status_code < 400):
                return response

            case = hub.db.session.get(hub.TestCase, case_id)
            if case is None:
                return response

            selected_plan_ids = {plan.id for plan in plans}
            linked_items = hub.db.session.scalars(
                hub.db.select(hub.TestPlanItem).where(
                    hub.TestPlanItem.test_case_id == case.id
                )
            ).all()
            linked_plan_ids = {item.test_plan_id for item in linked_items}

            # Unchecking a Test Plan detaches the implementation but keeps the
            # planned coverage requirement, so it returns to Pending.
            for item in linked_items:
                if item.test_plan_id not in selected_plan_ids:
                    plan = hub.db.session.get(hub.TestPlan, item.test_plan_id)
                    item.test_case = None
                    if plan is not None:
                        touch_plan(plan)

            # Checking a new Test Plan adds this Test Case as covered scope.
            for plan in plans:
                if plan.id in linked_plan_ids:
                    continue
                position = max((item.position for item in plan.items), default=0) + 1
                plan.items.append(
                    hub.TestPlanItem(
                        test_case=case,
                        position=position,
                        title_snapshot=case.title,
                        feature_snapshot=case.feature_name,
                    )
                )
                touch_plan(plan)

            hub.db.session.commit()
            return response

        hub.app.view_functions["update_case"] = update_case_with_plans

    original_create_run = hub.app.view_functions.get("create_test_run")
    if original_create_run is not None:
        @wraps(original_create_run)
        def create_test_run_with_plan():
            plan, error = resolve_plan(hub.request.form.get("test_plan_id"))
            if error:
                return error

            if plan is not None:
                if hub.request.form.get("preset", "Custom").strip() != "Custom":
                    return "Test Plan runs use the Custom preset so the selected plan defines the run scope.", 400
                raw_case_ids = hub.request.form.getlist("case_ids")
                if not raw_case_ids:
                    return "Select at least one Covered Test Case from the Test Plan.", 400
                try:
                    selected_ids = {int(value) for value in raw_case_ids}
                except ValueError:
                    return "Invalid Test Case selection.", 400
                covered_ids = {
                    item.test_case.id
                    for item in plan.items
                    if item.test_case is not None
                }
                if not selected_ids.issubset(covered_ids):
                    return "A selected Test Case is not Covered by the selected Test Plan.", 400

            before_id = latest_id(hub.TestRun)
            response = hub.app.make_response(original_create_run())
            if plan is not None and 300 <= response.status_code < 400:
                run = hub.db.session.scalar(
                    hub.db.select(hub.TestRun)
                    .where(hub.TestRun.id > before_id)
                    .order_by(hub.TestRun.id.desc())
                )
                if run is not None:
                    exists = hub.db.session.scalar(
                        hub.db.select(hub.TestPlanRunLink.id).where(
                            hub.TestPlanRunLink.test_plan_id == plan.id,
                            hub.TestPlanRunLink.test_run_id == run.id,
                        )
                    )
                    if exists is None:
                        hub.db.session.add(
                            hub.TestPlanRunLink(test_plan_id=plan.id, test_run_id=run.id)
                        )
                        touch_plan(plan)
                        hub.db.session.commit()
            return response

        hub.app.view_functions["create_test_run"] = create_test_run_with_plan

    original_create_release = hub.app.view_functions.get("create_release")
    if original_create_release is not None:
        @wraps(original_create_release)
        def create_release_with_plans():
            plans, error = resolve_plans(hub.request.form.getlist("test_plan_ids"))
            if error:
                return error

            before_id = latest_id(hub.Release)
            response = hub.app.make_response(original_create_release())
            if plans and 300 <= response.status_code < 400:
                release = hub.db.session.scalar(
                    hub.db.select(hub.Release)
                    .where(hub.Release.id > before_id)
                    .order_by(hub.Release.id.desc())
                )
                if release is not None:
                    for plan in plans:
                        exists = hub.db.session.scalar(
                            hub.db.select(hub.TestPlanReleaseLink.id).where(
                                hub.TestPlanReleaseLink.test_plan_id == plan.id,
                                hub.TestPlanReleaseLink.release_id == release.id,
                            )
                        )
                        if exists is None:
                            hub.db.session.add(
                                hub.TestPlanReleaseLink(test_plan_id=plan.id, release_id=release.id)
                            )
                            touch_plan(plan)
                    hub.db.session.commit()
            return response

        hub.app.view_functions["create_release"] = create_release_with_plans

    hub.app._product_plan_linking_registered = True


def register_product_redesign(hub):
    """Apply one product design system to every Test Hub HTML page."""
    if getattr(hub.app, "_product_redesign_registered", False):
        return

    # Test Plan models and relationship tables are already registered before this
    # final presentation layer is initialized, so create workflows can link to them.
    _register_test_plan_linking(hub)

    def inject_edit_case_test_plans(html):
        if hub.request.method != "GET" or hub.request.endpoint != "edit_case":
            return html
        case_key = (hub.request.view_args or {}).get("case_key")
        if not case_key or 'name="test_plan_ids"' in html:
            return html

        case = hub.db.session.scalar(
            hub.db.select(hub.TestCase).where(hub.TestCase.case_key == case_key)
        )
        if case is None:
            return html

        plans = hub.db.session.scalars(
            hub.db.select(hub.TestPlan).order_by(
                hub.TestPlan.updated_at.desc(), hub.TestPlan.id.desc()
            )
        ).all()
        linked_plan_ids = {
            value
            for (value,) in hub.db.session.execute(
                hub.db.select(hub.TestPlanItem.test_plan_id).where(
                    hub.TestPlanItem.test_case_id == case.id
                )
            ).all()
        }

        if plans:
            plan_rows = "".join(
                '<label class="prd-plan-check">'
                f'<input type="checkbox" name="test_plan_ids" value="{plan.id}"'
                + (' checked' if plan.id in linked_plan_ids else '')
                + '>'
                f'<span>{escape(plan.name)} · {escape(plan.status)}</span>'
                '</label>'
                for plan in plans
            )
        else:
            plan_rows = '<div class="prd-plan-hint">No Test Plans available.</div>'

        field = (
            '<div class="prd-form-field">'
            '<label>Test Plans</label>'
            '<input type="hidden" name="test_plan_sync" value="1">'
            f'<div class="prd-plan-checks">{plan_rows}</div>'
            '<div class="prd-plan-hint">Select every Test Plan covered by this Test Case. '
            'Unchecking a plan detaches this case but keeps the planned coverage Pending.</div>'
            '</div>'
        )
        marker = '<div class="field"><label>Preconditions</label>'
        if marker not in html:
            return html
        return html.replace(marker, field + marker, 1)

    @hub.app.after_request
    def product_redesign_response(response):
        if response.status_code != 200 or "text/html" not in (response.content_type or ""):
            return response

        html = response.get_data(as_text=True)
        if "data-product-redesign" in html or "<body" not in html:
            return response

        # Add Test Plan membership controls to the existing Edit Test Case form.
        html = inject_edit_case_test_plans(html)

        active = _active_section(hub.request.path)
        sidebar = hub.render_template_string(SIDEBAR_TEMPLATE, active=active)

        # Use the Test Hub brand mark as the browser tab icon on every product page.
        if 'rel="icon"' not in html and "</head>" in html:
            html = html.replace("</head>", FAVICON_LINK + "</head>", 1)

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
