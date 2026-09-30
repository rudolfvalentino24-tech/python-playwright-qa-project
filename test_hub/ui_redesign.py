from collections import defaultdict
from datetime import datetime, timedelta, timezone
from math import ceil
import re


FAVICON_LINK = '<link rel="icon" type="image/svg+xml" href="/favicon.svg">'

NAV_HTML = r'''
<div class="th-nav">
  <a class="th-brand" href="{{ url_for('index') }}">Test <span>Hub</span></a>
  <nav class="th-nav-links" aria-label="Test Hub navigation">
    <details class="th-menu">
      <summary>▣ <span>Test Cases</span>⌄</summary>
      <div class="th-menu-panel">
        <a href="{{ url_for('index') }}">All test cases</a>
        <a href="{{ url_for('index', type='Automated') }}">Automated</a>
        <a href="{{ url_for('index', type='Manual') }}">Manual</a>
        <a href="{{ url_for('index', status='Draft') }}">Drafts</a>
      </div>
    </details>
    <details class="th-menu">
      <summary>▷ <span>Test Runs</span>⌄</summary>
      <div class="th-menu-panel">
        <a href="{{ url_for('test_runs') }}">All test runs</a>
        <a href="{{ url_for('test_runs') }}#create-run">Create test run</a>
      </div>
    </details>
    <a class="th-nav-link" href="{{ url_for('results_dashboard') }}">▥ <span>Results</span></a>
    <details class="th-menu">
      <summary>◇ <span>Releases</span>⌄</summary>
      <div class="th-menu-panel">
        <a href="{{ url_for('releases') }}">All releases</a>
        <a href="{{ url_for('releases') }}#create-release">Create release</a>
      </div>
    </details>
    <details class="th-menu">
      <summary>▦ <span>Grouped by Feature</span>⌄</summary>
      <div class="th-menu-panel">
        <a href="{{ url_for('index', view='grouped') }}">Feature view</a>
        <a href="{{ url_for('index') }}">Compact view</a>
      </div>
    </details>
    <details class="th-menu">
      <summary>✦ <span>AI Test Designer</span>⌄</summary>
      <div class="th-menu-panel">
        <a href="{{ url_for('ai_test_designer') }}">Generate test cases</a>
      </div>
    </details>
  </nav>
  <details class="th-account">
    <summary aria-label="Account menu">◉⌄</summary>
    <div class="th-menu-panel th-account-panel">
      <span>Account controls coming later</span>
    </div>
  </details>
</div>
'''

SHELL_CSS = r'''
:root{--th-bg:#f4f8ff;--th-card:#fff;--th-text:#10254a;--th-muted:#697b98;--th-line:#dce6f5;--th-blue:#1468ff;--th-blue-soft:#edf5ff;--th-green:#16a34a;--th-red:#e5484d;--th-amber:#e6a315}
body{background:linear-gradient(180deg,#f8fbff 0,#f1f6ff 100%)!important;color:var(--th-text)!important}
.th-nav{position:sticky;top:0;z-index:100;min-height:70px;display:flex;align-items:center;gap:28px;padding:0 36px;background:rgba(255,255,255,.97);border-bottom:1px solid #e4ebf6;box-shadow:0 5px 18px rgba(31,73,125,.06);backdrop-filter:blur(14px)}
.th-brand{font-size:25px;font-weight:900;letter-spacing:-1px;color:#10254a;text-decoration:none;white-space:nowrap}.th-brand span{color:#1468ff}.th-nav-links{display:flex;align-items:center;gap:5px;flex:1}.th-nav-link,.th-menu>summary{min-height:42px;display:flex;align-items:center;gap:8px;padding:0 13px;border-radius:9px;color:#173763;text-decoration:none;font-size:13px;font-weight:800;cursor:pointer;list-style:none;white-space:nowrap}.th-menu>summary::-webkit-details-marker,.th-account>summary::-webkit-details-marker{display:none}.th-nav-link:hover,.th-menu>summary:hover,.th-menu[open]>summary{background:#eef5ff;color:#0b5de8}.th-menu,.th-account{position:relative}.th-menu-panel{position:absolute;top:48px;left:0;z-index:120;min-width:190px;padding:7px;border:1px solid #dbe6f4;border-radius:12px;background:#fff;box-shadow:0 18px 45px rgba(25,60,105,.17)}.th-menu-panel a,.th-menu-panel span{display:block;padding:9px 11px;border-radius:8px;color:#244262;text-decoration:none;font-size:12px;font-weight:700}.th-menu-panel a:hover{background:#f0f6ff;color:#0b5de8}.th-account{margin-left:auto}.th-account>summary{width:42px;height:42px;display:grid;place-items:center;border-radius:50%;background:#eef4fc;color:#42607e;cursor:pointer;list-style:none}.th-account-panel{left:auto;right:0}.th-page{max-width:1540px;margin:0 auto;padding:25px 32px 48px}.th-card{background:#fff;border:1px solid #dce6f4;border-radius:16px;box-shadow:0 8px 28px rgba(36,75,125,.055)}
@media(max-width:1080px){.th-nav{gap:14px;padding:0 18px}.th-nav-links{overflow-x:auto}.th-menu>summary,.th-nav-link{padding:0 10px}.th-page{padding:20px 18px 40px}}
@media(max-width:720px){.th-nav{min-height:60px}.th-brand{font-size:21px}.th-nav-link span,.th-menu>summary span{display:none}.th-nav-link,.th-menu>summary{font-size:17px}.th-page{padding:14px 10px 30px}}
'''

MAIN_PAGE_HTML = r'''
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Test Cases - Test Hub</title>
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<style>
''' + SHELL_CSS + r'''
*{box-sizing:border-box}body{margin:0;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.page-grid{display:grid;grid-template-columns:minmax(0,2.15fr) minmax(350px,.85fr);gap:18px;align-items:start}.main-panel,.side-card{padding:22px}.page-head{display:flex;align-items:flex-start;justify-content:space-between;gap:18px;margin-bottom:17px}.page-head h1{margin:0;font-size:31px;line-height:1.05;letter-spacing:-.7px}.subtitle{margin-top:5px;color:var(--th-muted);font-size:13px}.primary,.secondary,.danger,.icon-btn{border:0;border-radius:9px;padding:10px 14px;font:inherit;font-size:12px;font-weight:850;cursor:pointer;text-decoration:none;display:inline-flex;align-items:center;justify-content:center;gap:7px}.primary{background:linear-gradient(90deg,#1d6eff,#1468ff);color:#fff;box-shadow:0 7px 17px rgba(20,104,255,.2)}.secondary{background:#f0f4fa;color:#243f61}.danger{background:#fff0ef;color:#b42318}.toolbar{display:grid;grid-template-columns:minmax(210px,1.4fr) repeat(3,minmax(120px,.62fr)) minmax(150px,.72fr);gap:9px;margin-bottom:9px}.toolbar input,.toolbar select,.form-field input,.form-field select,.form-field textarea{width:100%;border:1px solid #ccd9eb;border-radius:9px;background:#fff;color:#183252;font:inherit;font-size:12px;outline:none}.toolbar input,.toolbar select,.form-field input,.form-field select{height:40px;padding:0 11px}.form-field textarea{min-height:82px;padding:10px 11px;resize:vertical}.toolbar input:focus,.toolbar select:focus,.form-field input:focus,.form-field select:focus,.form-field textarea:focus{border-color:#5590f7;box-shadow:0 0 0 3px rgba(43,116,245,.1)}.count-line{display:flex;justify-content:space-between;align-items:center;margin:8px 0 12px;color:var(--th-muted);font-size:11px}.case-list{display:flex;flex-direction:column;gap:9px}.case-card{position:relative;padding:14px 16px 13px;border:1px solid #dce6f3;border-radius:12px;background:#fff}.case-top{display:flex;justify-content:space-between;gap:14px;align-items:flex-start}.case-title{font-size:13px;font-weight:900;color:#102d5a;line-height:1.35}.case-title a{color:inherit;text-decoration:none}.updated{font-size:10px;color:#8090a7;white-space:nowrap}.badges{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0 9px}.badge{padding:4px 9px;border-radius:999px;background:#edf2f8;color:#4b607a;font-size:10px;font-weight:800}.badge.ready,.badge.bdd-ready{background:#dcfce7;color:#166534}.badge.bdd-work{background:#fff4d6;color:#8a5b00}.badge.jira{background:#e8f1ff;color:#1763d8}.case-copy{font-size:11px;color:#60748f;line-height:1.45}.case-copy strong{color:#294465}.case-steps{margin:3px 0 3px 21px;padding:0}.case-actions{display:flex;justify-content:flex-end;align-items:center;gap:7px;margin-top:8px}.case-actions select{height:35px;border:1px solid #d4deeb;border-radius:8px;padding:0 9px;background:#fff;color:#29405f;font:inherit;font-size:11px}.case-actions .secondary,.case-actions .danger{padding:8px 11px}.more-menu{position:relative}.more-menu>summary{width:35px;height:35px;display:grid;place-items:center;border:1px solid #d4deeb;border-radius:8px;background:#fff;cursor:pointer;list-style:none;font-weight:900}.more-menu>summary::-webkit-details-marker{display:none}.more-menu>div{position:absolute;right:0;bottom:40px;z-index:20;min-width:145px;padding:6px;border:1px solid #d8e2ef;border-radius:10px;background:#fff;box-shadow:0 12px 28px rgba(29,65,110,.17)}.more-menu a,.more-menu button{width:100%;display:block;padding:8px 9px;border:0;border-radius:7px;background:none;color:#29405f;text-align:left;text-decoration:none;font:inherit;font-size:11px;font-weight:750;cursor:pointer}.more-menu a:hover,.more-menu button:hover{background:#f2f6fc}.more-menu button{color:#b42318}.group-label{margin:15px 1px 7px;font-size:12px;font-weight:900;color:#315275}.group-label:first-child{margin-top:0}.pagination{display:flex;align-items:center;justify-content:center;gap:5px;margin-top:15px}.pagination a,.pagination span{min-width:32px;height:32px;display:grid;place-items:center;border:1px solid #d6e0ed;border-radius:8px;background:#fff;color:#34516f;text-decoration:none;font-size:11px;font-weight:800}.pagination .current{border-color:#176dff;background:#176dff;color:#fff}.pagination .disabled{opacity:.45}.side-stack{display:flex;flex-direction:column;gap:13px;position:sticky;top:88px}.ai-card{padding:18px;background:linear-gradient(135deg,#eff6ff,#f8fbff);border-color:#cfe0f7}.ai-row{display:flex;justify-content:space-between;gap:15px;align-items:center}.ai-card h2,.create-card h2{margin:0;font-size:17px;color:#16345e}.ai-card p,.create-card .helper{margin:5px 0 12px;color:#71829a;font-size:11px;line-height:1.4}.spark{font-size:30px;color:#176dff}.form-field{margin-top:11px}.form-field label{display:block;margin-bottom:5px;color:#314d6c;font-size:10px;font-weight:900}.form-row{display:grid;grid-template-columns:1fr 1fr;gap:9px}.jira-box{padding:10px;border:1px dashed #c8d7e9;border-radius:9px;background:#fbfdff}.jira-selected-list{display:flex;flex-direction:column;gap:5px;margin-bottom:7px}.jira-selected-empty{font-size:11px;color:#7b8ba2}.jira-selected-row{display:flex;align-items:center;gap:6px;font-size:11px}.jira-selected-main{flex:1;color:#245fbd;text-decoration:none}.jira-open{font-size:10px;color:#245fbd}.jira-remove{border:0;background:#fff0ef;color:#b42318;border-radius:6px;padding:4px 6px;cursor:pointer}.create-submit{width:100%;margin-top:14px}.sync-warning{grid-column:1/-1;padding:11px 14px;border:1px solid #f1cf6a;border-radius:10px;background:#fff8de;color:#8a6500;font-size:11px}.modal-backdrop{position:fixed;inset:0;z-index:200;display:flex;align-items:center;justify-content:center;padding:22px;background:rgba(17,30,54,.5);backdrop-filter:blur(4px)}.modal-backdrop[hidden]{display:none}.jira-modal{width:min(700px,100%);max-height:80vh;display:flex;flex-direction:column;border-radius:16px;background:#fff;overflow:hidden;box-shadow:0 28px 80px rgba(9,30,66,.28)}.jira-modal-head,.jira-modal-actions{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:14px 16px;border-bottom:1px solid #e1e8f2}.jira-modal-actions{justify-content:flex-end;border-top:1px solid #e1e8f2;border-bottom:0}.jira-modal-body{padding:15px;overflow:auto}.jira-modal-search{width:100%;height:40px;margin-bottom:10px;padding:0 11px;border:1px solid #ccd9eb;border-radius:9px}.jira-modal-list{display:flex;flex-direction:column;gap:6px}.jira-modal-ticket{width:100%;padding:10px;text-align:left;border:1px solid #dbe4f0;border-radius:9px;background:#fff;cursor:pointer}.jira-modal-ticket.selected{border-color:#4f82e9;background:#eef5ff}.jira-story-key{font-weight:900;color:#1763d8}.jira-story-summary{color:#4d617b}.jira-modal-message{font-size:11px;color:#71829a}.empty{padding:38px;text-align:center;color:#72839a;font-size:12px}
@media(max-width:1050px){.page-grid{grid-template-columns:1fr}.side-stack{position:static}.toolbar{grid-template-columns:1fr 1fr}.toolbar input{grid-column:1/-1}}@media(max-width:620px){.main-panel,.side-card{padding:14px}.page-head{flex-direction:column}.toolbar{grid-template-columns:1fr}.toolbar input{grid-column:auto}.case-top{flex-direction:column}.updated{display:none}.case-actions{justify-content:flex-start;flex-wrap:wrap}}
</style></head><body>
''' + NAV_HTML + r'''
<main class="th-page"><div class="page-grid">
{% if sync_warning %}<div class="sync-warning"><strong>Jira sync warning:</strong> {{ sync_warning }}</div>{% endif %}
<section class="th-card main-panel">
  <div class="page-head"><div><h1>Test Cases</h1><div class="subtitle">Manage, review, and maintain QA test cases for your application.</div></div><a class="primary" href="#create-case">＋ Create Test Case</a></div>
  <form class="toolbar" method="get" action="{{ url_for('index') }}">
    <input name="q" value="{{ filters.q }}" placeholder="⌕  Search feature, ID, title or Jira key...">
    <select name="status" onchange="this.form.submit()"><option value="">All statuses</option>{% for s in statuses %}<option value="{{ s }}" {% if filters.status == s %}selected{% endif %}>{{ s }}</option>{% endfor %}</select>
    <select name="priority" onchange="this.form.submit()"><option value="">All priorities</option>{% for p in priorities %}<option value="{{ p }}" {% if filters.priority == p %}selected{% endif %}>{{ p }}</option>{% endfor %}</select>
    <select name="type" onchange="this.form.submit()"><option value="">All types</option><option {% if filters.type == 'Manual' %}selected{% endif %}>Manual</option><option {% if filters.type == 'Automated' %}selected{% endif %}>Automated</option></select>
    <select name="sort" onchange="this.form.submit()"><option value="updated" {% if filters.sort == 'updated' %}selected{% endif %}>Updated (newest)</option><option value="id" {% if filters.sort == 'id' %}selected{% endif %}>ID</option><option value="feature" {% if filters.sort == 'feature' %}selected{% endif %}>Feature</option></select>
    {% if filters.view %}<input type="hidden" name="view" value="{{ filters.view }}">{% endif %}
    <input type="hidden" name="per_page" value="{{ pagination.per_page }}">
  </form>
  <div class="count-line"><span>Showing <strong>{{ pagination.start }}–{{ pagination.end }}</strong> of <strong>{{ pagination.total }}</strong> matching test cases</span><span>Page {{ pagination.page }} of {{ pagination.page_count }}</span></div>
  <div class="case-list">
  {% set ns = namespace(last_feature='') %}
  {% for c in cases %}
    {% if filters.view == 'grouped' and c.feature_name != ns.last_feature %}<div class="group-label">{{ c.feature_name }}</div>{% set ns.last_feature = c.feature_name %}{% endif %}
    <article class="case-card">
      <div class="case-top"><div class="case-title"><a href="{{ url_for('test_case_details', case_key=c.case_key) }}">{{ c.case_key }}</a> — {{ c.title }}</div><div class="updated">{{ c.updated_at.strftime('%d %b %Y') if c.updated_at else '' }}</div></div>
      <div class="badges"><span class="badge">{{ c.feature_name }}</span><span class="badge">{{ c.type }}</span><span class="badge">{{ c.priority }}</span><span class="badge {% if c.status == 'Ready' %}ready{% endif %}">{{ c.status }}</span>
      {% if c.type == 'Automated' %}{% set auto = automation.get(c.id) %}<span class="badge {% if auto and auto.ready %}bdd-ready{% else %}bdd-work{% endif %}">{% if auto and auto.ready %}BDD Ready{% elif auto and auto.synced %}BDD Needs work{% else %}BDD Not synced{% endif %}</span>{% endif %}
      {% for jira_key in c.jira_keys %}<a class="badge jira" href="{{ url_for('jira_story_cases', jira_key=jira_key) }}">{{ jira_key }}</a>{% endfor %}</div>
      {% if c.preconditions %}<div class="case-copy"><strong>Preconditions:</strong> {{ c.preconditions }}</div>{% endif %}
      <div class="case-copy"><strong>Steps:</strong><ol class="case-steps">{% for step in c.steps %}<li>{{ step.action }}</li>{% endfor %}</ol></div>
      <div class="case-copy"><strong>Expected:</strong> {{ c.expected_result }}</div>
      <div class="case-actions">
        {% if c.type == 'Automated' %}<a class="secondary" href="{{ url_for('case_automation', case_key=c.case_key) }}">Automation</a>{% endif %}
        <a class="secondary" href="{{ url_for('edit_case', case_key=c.case_key) }}">✎ Edit</a>
        <form method="post" action="{{ url_for('set_status', case_key=c.case_key) }}"><select name="status" onchange="this.form.submit()">{% for s in statuses %}<option value="{{ s }}" {% if s == c.status %}selected{% endif %}>{{ s }}</option>{% endfor %}</select></form>
        <details class="more-menu"><summary>•••</summary><div><a href="{{ url_for('test_case_details', case_key=c.case_key) }}">Case history</a><form method="post" action="{{ url_for('delete_case', case_key=c.case_key) }}" onsubmit="return confirm('Delete {{ c.case_key }}?')"><button type="submit">Delete</button></form></div></details>
      </div>
    </article>
  {% else %}<div class="empty">No test cases match these filters.</div>{% endfor %}
  </div>
  <nav class="pagination" aria-label="Pagination"><a class="{% if not pagination.prev_url %}disabled{% endif %}" {% if pagination.prev_url %}href="{{ pagination.prev_url }}"{% endif %}>‹</a>{% for item in pagination.pages %}{% if item.ellipsis %}<span>…</span>{% elif item.current %}<span class="current">{{ item.number }}</span>{% else %}<a href="{{ item.url }}">{{ item.number }}</a>{% endif %}{% endfor %}<a class="{% if not pagination.next_url %}disabled{% endif %}" {% if pagination.next_url %}href="{{ pagination.next_url }}"{% endif %}>›</a></nav>
</section>
<aside class="side-stack">
  <section class="th-card side-card ai-card"><div class="ai-row"><div><h2>✦ AI Test Designer</h2><p>Turn a feature or acceptance criteria into reviewable test-case drafts.</p><a class="primary" href="{{ url_for('ai_test_designer') }}">✦ Generate with AI</a></div><div class="spark">✦</div></div></section>
  <section id="create-case" class="th-card side-card create-card"><h2>▱ Create test case</h2><div class="helper">Add a new test case to your project.</div>
    <form method="post" action="{{ url_for('create_case') }}">
      <div class="form-field"><label>Feature / Module</label><input name="feature" required placeholder="Authentication"></div>
      <div class="form-field"><label>Title</label><input name="title" required placeholder="Reveal password toggles visibility"></div>
      <div class="form-field"><label>Jira stories</label><div class="jira-box"><input id="createJiraKeys" name="jira_keys" type="hidden"><div id="createSelectedJiraStories" class="jira-selected-list"></div><button class="secondary" type="button" onclick="openJiraModal('create')">↗ Add Jira ticket</button></div></div>
      <div class="form-row"><div class="form-field"><label>Priority</label><select name="priority"><option>Medium</option><option>High</option><option>Critical</option><option>Low</option></select></div><div class="form-field"><label>Type</label><select name="type"><option>Manual</option><option>Automated</option></select></div></div>
      <div class="form-row"><div class="form-field"><label>Status</label><select name="status"><option>Draft</option><option>Ready</option><option>Passed</option><option>Failed</option><option>Blocked</option></select></div><div class="form-field"><label>Test case ID</label><input name="case_key" placeholder="Auto-generate"></div></div>
      <div class="form-field"><label>Preconditions</label><textarea name="preconditions" placeholder="User is on the login page"></textarea></div>
      <div class="form-field"><label>Steps — one per line</label><textarea name="steps" required placeholder="Given...&#10;When...&#10;Then..."></textarea></div>
      <div class="form-field"><label>Expected result</label><textarea name="expected_result" required placeholder="Expected observable outcome"></textarea></div>
      <button class="primary create-submit" type="submit">＋ Create Test Case</button>
    </form>
  </section>
</aside>
</div></main>
<div id="createJiraModal" class="modal-backdrop" hidden><div class="jira-modal"><div class="jira-modal-head"><strong>Add Jira ticket</strong><button class="secondary" type="button" onclick="closeJiraModal('create')">Cancel</button></div><div class="jira-modal-body"><input id="createJiraModalSearch" class="jira-modal-search" type="search" placeholder="Search Jira key or title..." oninput="renderJiraModalStories('create')"><div id="createJiraModalList" class="jira-modal-list"></div></div><div class="jira-modal-actions"><button class="secondary" type="button" onclick="closeJiraModal('create')">Cancel</button><button class="primary" type="button" onclick="confirmJiraSelection('create')">Add selected</button></div></div></div>
<script>
let jiraStories=[];const jiraBrowseBase='{{ jira_base }}';const jiraModalSelections={};
function escapeHtml(value){const div=document.createElement('div');div.textContent=value||'';return div.innerHTML;}
function selectedJiraKeys(prefix){const value=document.getElementById(prefix+'JiraKeys').value.trim();return new Set(value?value.split(',').map(v=>v.trim().toUpperCase()).filter(Boolean):[]);}
function storyByKey(key){return jiraStories.find(story=>story.key===key);}
function renderSelectedJiraStories(prefix){const container=document.getElementById(prefix+'SelectedJiraStories');if(!container)return;const keys=[...selectedJiraKeys(prefix)];if(!keys.length){container.innerHTML='<div class="jira-selected-empty">No Jira tickets linked.</div>';return;}container.innerHTML=keys.map(key=>{const story=storyByKey(key);const summary=story?story.summary:'';return `<div class="jira-selected-row"><a class="jira-selected-main" href="/jira/${encodeURIComponent(key)}"><span class="jira-story-key">${escapeHtml(key)}</span>${summary?' — '+escapeHtml(summary):''}</a><a class="jira-open" href="${jiraBrowseBase}/${encodeURIComponent(key)}" target="_blank">Jira</a><button class="jira-remove" type="button" data-remove-jira="${escapeHtml(key)}">×</button></div>`;}).join('');container.querySelectorAll('[data-remove-jira]').forEach(button=>button.addEventListener('click',()=>removeJiraStory(prefix,button.dataset.removeJira)));}
function removeJiraStory(prefix,key){const selected=selectedJiraKeys(prefix);selected.delete(key);document.getElementById(prefix+'JiraKeys').value=[...selected].join(', ');renderSelectedJiraStories(prefix);}
function openJiraModal(prefix){jiraModalSelections[prefix]=new Set(selectedJiraKeys(prefix));document.getElementById(prefix+'JiraModalSearch').value='';document.getElementById(prefix+'JiraModal').hidden=false;renderJiraModalStories(prefix);}
function closeJiraModal(prefix){document.getElementById(prefix+'JiraModal').hidden=true;delete jiraModalSelections[prefix];}
function renderJiraModalStories(prefix){const list=document.getElementById(prefix+'JiraModalList');const search=document.getElementById(prefix+'JiraModalSearch').value.trim().toLowerCase();const selected=jiraModalSelections[prefix]||new Set();const matches=jiraStories.filter(story=>!search||story.key.toLowerCase().includes(search)||story.summary.toLowerCase().includes(search));if(!matches.length){list.innerHTML='<div class="jira-modal-message">No matching Jira tickets.</div>';return;}list.innerHTML=matches.map(story=>`<button type="button" class="jira-modal-ticket ${selected.has(story.key)?'selected':''}" data-jira-key="${story.key}"><span class="jira-story-key">${escapeHtml(story.key)}</span> — <span class="jira-story-summary">${escapeHtml(story.summary)}</span></button>`).join('');list.querySelectorAll('[data-jira-key]').forEach(button=>button.addEventListener('click',()=>{selected.has(button.dataset.jiraKey)?selected.delete(button.dataset.jiraKey):selected.add(button.dataset.jiraKey);jiraModalSelections[prefix]=selected;renderJiraModalStories(prefix);}));}
function confirmJiraSelection(prefix){const selected=jiraModalSelections[prefix]||new Set();document.getElementById(prefix+'JiraKeys').value=[...selected].join(', ');renderSelectedJiraStories(prefix);closeJiraModal(prefix);}
async function loadJiraStories(prefix){try{const response=await fetch('/api/jira/stories');const data=await response.json();if(!response.ok)throw new Error(data.error||'Unable to load Jira stories.');jiraStories=data.stories||[];renderSelectedJiraStories(prefix);}catch(error){const container=document.getElementById(prefix+'SelectedJiraStories');if(container)container.innerHTML='<div class="jira-selected-empty">'+escapeHtml(error.message)+'</div>';}}
document.addEventListener('DOMContentLoaded',()=>loadJiraStories('create'));
</script></body></html>
'''

RESULTS_PAGE_HTML = r'''
<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Results - Test Hub</title><link rel="icon" type="image/svg+xml" href="/favicon.svg"><style>
''' + SHELL_CSS + r'''
*{box-sizing:border-box}body{margin:0;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.results-head{display:flex;justify-content:space-between;gap:15px;align-items:flex-start;margin-bottom:16px}.results-head h1{margin:0;font-size:31px;letter-spacing:-.7px}.results-head p{margin:5px 0 0;color:var(--th-muted);font-size:13px}.range-form select{height:39px;padding:0 12px;border:1px solid #d3deec;border-radius:9px;background:#fff;color:#294465;font:inherit;font-size:11px;font-weight:750}.metrics{display:grid;grid-template-columns:repeat(6,1fr);gap:10px;margin-bottom:13px}.metric{padding:15px;border:1px solid #dce6f4;border-radius:13px;background:#fff;box-shadow:0 6px 22px rgba(36,75,125,.05)}.metric .label{font-size:10px;font-weight:800;color:#60738e}.metric .value{margin-top:5px;font-size:25px;font-weight:900;color:#13345f}.metric .note{margin-top:5px;font-size:9px;color:#8493a8}.green{color:#159947!important}.red{color:#df4247!important}.amber{color:#c58a00!important}.results-grid{display:grid;grid-template-columns:minmax(0,2fr) minmax(310px,.8fr);gap:13px}.panel{padding:17px;border:1px solid #dce6f4;border-radius:14px;background:#fff;box-shadow:0 7px 25px rgba(36,75,125,.05)}.panel h2{margin:0;font-size:15px;color:#17375f}.panel-sub{margin:4px 0 12px;font-size:10px;color:#7a8aa1}.trend{height:210px;display:flex;align-items:flex-end;gap:6px;padding:16px 8px 23px;border-bottom:1px solid #e7edf5}.day{height:170px;flex:1;min-width:18px;display:flex;flex-direction:column;justify-content:flex-end;position:relative}.stack{width:100%;display:flex;flex-direction:column-reverse;justify-content:flex-start}.seg{width:100%;min-height:0}.seg.p{background:#22b96b}.seg.f{background:#ef5350}.seg.b{background:#f3b523}.seg.s{background:#9ba9bc}.day-label{position:absolute;top:176px;left:50%;transform:translateX(-50%);font-size:8px;color:#8290a3;white-space:nowrap}.legend{display:flex;gap:14px;justify-content:center;margin-top:17px;font-size:9px;color:#667991}.dot{width:8px;height:8px;display:inline-block;border-radius:50%;margin-right:4px}.donut-wrap{display:grid;place-items:center;padding:10px}.donut{width:170px;height:170px;display:grid;place-items:center;border-radius:50%;position:relative}.donut:after{content:"";position:absolute;width:105px;height:105px;border-radius:50%;background:#fff}.donut strong,.donut span{position:relative;z-index:2}.donut strong{font-size:25px}.donut span{font-size:10px;color:#75869c}.summary-list{margin-top:8px}.summary-row{display:flex;justify-content:space-between;padding:8px 0;border-top:1px solid #edf1f6;font-size:10px}.summary-row:first-child{border-top:0}.bottom-grid{grid-column:1/-1;display:grid;grid-template-columns:minmax(0,2fr) minmax(310px,.8fr);gap:13px}.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse;font-size:10px}th{text-align:left;padding:8px;border-bottom:1px solid #dfe7f1;color:#61738c;background:#f7faff}td{padding:9px 8px;border-bottom:1px solid #edf1f5;color:#415772}td a{color:#1763d8;font-weight:800;text-decoration:none}.status-pill{padding:4px 8px;border-radius:999px;font-weight:850}.status-Passed{background:#dcfce7;color:#166534}.status-Failed{background:#fee2e2;color:#991b1b}.status-Blocked{background:#fff4d6;color:#8a5b00}.status-Incomplete{background:#edf2f8;color:#5b6c80}.artifacts{display:flex;flex-direction:column;gap:7px}.artifact{display:flex;justify-content:space-between;gap:8px;align-items:center;padding:10px;border:1px solid #e1e8f2;border-radius:9px}.artifact strong{display:block;font-size:10px}.artifact span{font-size:9px;color:#7b8ba0}.artifact a{font-size:10px;color:#1763d8;font-weight:850;text-decoration:none}.pagination{display:flex;gap:4px;justify-content:flex-end;margin-top:10px}.pagination a,.pagination span{min-width:29px;height:29px;display:grid;place-items:center;border:1px solid #d7e0ec;border-radius:7px;background:#fff;color:#3e5875;text-decoration:none;font-size:10px;font-weight:800}.pagination .current{background:#176dff;color:#fff;border-color:#176dff}@media(max-width:1050px){.metrics{grid-template-columns:repeat(3,1fr)}.results-grid,.bottom-grid{grid-template-columns:1fr}}@media(max-width:600px){.metrics{grid-template-columns:1fr 1fr}.results-head{flex-direction:column}.trend{overflow-x:auto}.day{min-width:28px}}
</style></head><body>''' + NAV_HTML + r'''
<main class="th-page"><div class="results-head"><div><h1>Results</h1><p>Track and analyze actual Test Hub execution results.</p></div><form class="range-form" method="get"><select name="range" onchange="this.form.submit()"><option value="7" {% if range_days == 7 %}selected{% endif %}>Last 7 days</option><option value="30" {% if range_days == 30 %}selected{% endif %}>Last 30 days</option><option value="90" {% if range_days == 90 %}selected{% endif %}>Last 90 days</option><option value="0" {% if range_days == 0 %}selected{% endif %}>All time</option></select></form></div>
<section class="metrics"><div class="metric"><div class="label">Total Runs</div><div class="value">{{ metrics.runs }}</div><div class="note">Structured test runs</div></div><div class="metric"><div class="label">Passed</div><div class="value green">{{ metrics.passed }}</div><div class="note">Latest case outcomes</div></div><div class="metric"><div class="label">Failed</div><div class="value red">{{ metrics.failed }}</div><div class="note">Latest case outcomes</div></div><div class="metric"><div class="label">Recovered / Flaky</div><div class="value amber">{{ metrics.flaky }}</div><div class="note">Failed then passed on rerun</div></div><div class="metric"><div class="label">Blocked</div><div class="value">{{ metrics.blocked }}</div><div class="note">Latest case outcomes</div></div><div class="metric"><div class="label">Pass Rate</div><div class="value green">{{ metrics.pass_rate }}%</div><div class="note">Passed / passed + failed</div></div></section>
<section class="results-grid"><div class="panel"><h2>▥ Results Trend</h2><div class="panel-sub">Final test-run outcomes over time.</div><div class="trend">{% for d in trend %}<div class="day"><div class="stack"><div class="seg p" style="height:{{ d.passed_pct }}%"></div><div class="seg f" style="height:{{ d.failed_pct }}%"></div><div class="seg b" style="height:{{ d.blocked_pct }}%"></div><div class="seg s" style="height:{{ d.skipped_pct }}%"></div></div><div class="day-label">{{ d.label }}</div></div>{% endfor %}</div><div class="legend"><span><i class="dot" style="background:#22b96b"></i>Passed</span><span><i class="dot" style="background:#ef5350"></i>Failed</span><span><i class="dot" style="background:#f3b523"></i>Blocked</span><span><i class="dot" style="background:#9ba9bc"></i>Skipped</span></div></div>
<div class="panel"><h2>◔ Execution Summary</h2><div class="panel-sub">Breakdown for the selected period.</div><div class="donut-wrap"><div class="donut" style="background:conic-gradient(#22b96b 0 {{ donut.passed_end }}%,#ef5350 {{ donut.passed_end }}% {{ donut.failed_end }}%,#f3b523 {{ donut.failed_end }}% {{ donut.blocked_end }}%,#9ba9bc {{ donut.blocked_end }}% 100%)"><div style="text-align:center"><strong>{{ metrics.total_cases }}</strong><br><span>case outcomes</span></div></div></div><div class="summary-list"><div class="summary-row"><span>Passed</span><strong>{{ metrics.passed }} · {{ donut.passed }}%</strong></div><div class="summary-row"><span>Failed</span><strong>{{ metrics.failed }} · {{ donut.failed }}%</strong></div><div class="summary-row"><span>Blocked</span><strong>{{ metrics.blocked }} · {{ donut.blocked }}%</strong></div><div class="summary-row"><span>Skipped</span><strong>{{ metrics.skipped }} · {{ donut.skipped }}%</strong></div></div></div>
<div class="bottom-grid"><div class="panel"><h2>Recent Test Runs</h2><div class="panel-sub">Latest structured executions in this period.</div><div class="table-wrap"><table><thead><tr><th>Run</th><th>Name</th><th>Release</th><th>Environment</th><th>Started</th><th>Duration</th><th>Outcome</th><th>Build</th></tr></thead><tbody>{% for row in recent_runs %}<tr><td><a href="{{ url_for('test_run_details', run_id=row.run.id) }}">TR-{{ '%04d'|format(row.run.id) }}</a></td><td>{{ row.run.name }}</td><td>{{ row.run.release.version if row.run.release else '—' }}</td><td>{{ row.run.environment or '—' }}</td><td>{{ row.started }}</td><td>{{ row.duration }}</td><td><span class="status-pill status-{{ row.outcome }}">{{ row.outcome }}</span></td><td>{% if row.run.jenkins_build_url %}<a href="{{ row.run.jenkins_build_url }}" target="_blank">#{{ row.run.jenkins_build_number or '?' }}</a>{% else %}—{% endif %}</td></tr>{% else %}<tr><td colspan="8">No runs in this period.</td></tr>{% endfor %}</tbody></table></div><div class="pagination">{% for p in run_pages %}{% if p.current %}<span class="current">{{ p.number }}</span>{% else %}<a href="{{ p.url }}">{{ p.number }}</a>{% endif %}{% endfor %}</div></div>
<div class="panel"><h2>Reports & Artifacts</h2><div class="panel-sub">Links saved from recent Jenkins executions.</div><div class="artifacts">{% for item in artifacts %}<div class="artifact"><div><strong>{{ item.title }}</strong><span>{{ item.subtitle }}</span></div><a href="{{ item.url }}" target="_blank">Open ↗</a></div>{% else %}<div class="panel-sub">No Jenkins reports or artifacts saved yet.</div>{% endfor %}</div></div></div></section></main></body></html>
'''


def _aware(value):
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _format_duration(start, finish):
    start = _aware(start)
    finish = _aware(finish)
    if not start or not finish or finish < start:
        return "—"
    seconds = int((finish - start).total_seconds())
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {sec}s"
    if minutes:
        return f"{minutes}m {sec}s"
    return f"{sec}s"


def _inject_shell(template):
    if not template:
        return template
    rendered = re.sub(r"<header\b[^>]*>.*?</header>", NAV_HTML, template, count=1, flags=re.IGNORECASE | re.DOTALL)
    if FAVICON_LINK not in rendered:
        rendered = rendered.replace("</head>", FAVICON_LINK + "</head>", 1)
    if SHELL_CSS not in rendered:
        if "</style>" in rendered:
            rendered = rendered.replace("</style>", SHELL_CSS + "</style>", 1)
        else:
            rendered = rendered.replace("</head>", "<style>" + SHELL_CSS + "</style></head>", 1)
    return rendered


def _page_links(hub, page, page_count, args):
    numbers = []
    wanted = {1, page_count, page - 2, page - 1, page, page + 1, page + 2}
    last = None
    for number in sorted(n for n in wanted if 1 <= n <= page_count):
        if last is not None and number - last > 1:
            numbers.append({"ellipsis": True})
        values = dict(args)
        values["page"] = number
        numbers.append({"number": number, "current": number == page, "url": hub.url_for("index", **values)})
        last = number
    return numbers


def register_ui_redesign(hub, ai_designer, bdd_sync):
    app = hub.app

    # Shared navigation/favicons for every existing Test Hub surface.
    for name in ["STORY_PAGE_HTML", "TEST_RUNS_PAGE_HTML", "TEST_RUN_PAGE_HTML", "RELEASES_PAGE_HTML", "RELEASE_PAGE_HTML", "CASE_PAGE_HTML", "EDIT_PAGE_HTML"]:
        if hasattr(hub, name):
            setattr(hub, name, _inject_shell(getattr(hub, name)))
    ai_designer.DESIGNER_PAGE_HTML = _inject_shell(ai_designer.DESIGNER_PAGE_HTML)
    ai_designer.REVIEW_PAGE_HTML = _inject_shell(ai_designer.REVIEW_PAGE_HTML)
    bdd_sync.AUTOMATION_PAGE_HTML = _inject_shell(bdd_sync.AUTOMATION_PAGE_HTML)

    @app.get("/favicon.svg")
    def test_hub_favicon():
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="#1468ff"/><path d="M24 13h16v6l-3 4v8l11 17a5 5 0 0 1-4 8H20a5 5 0 0 1-4-8l11-17v-8l-3-4v-6Zm6 8v12L20 49h24L34 33V21h-4Z" fill="white"/><circle cx="28" cy="45" r="3" fill="#8af0bb"/><circle cx="38" cy="48" r="2" fill="#8af0bb"/></svg>'''
        return app.response_class(svg, mimetype="image/svg+xml")

    def redesigned_index():
        all_cases = hub.db.session.scalars(hub.db.select(hub.TestCase).order_by(hub.TestCase.id.desc())).all()
        q = hub.request.args.get("q", "").strip().lower()
        status = hub.request.args.get("status", "").strip()
        priority = hub.request.args.get("priority", "").strip()
        case_type = hub.request.args.get("type", "").strip()
        sort = hub.request.args.get("sort", "updated").strip()
        view = hub.request.args.get("view", "").strip()
        try:
            per_page = int(hub.request.args.get("per_page", "10"))
        except ValueError:
            per_page = 10
        per_page = min(max(per_page, 5), 50)

        filtered = []
        for case in all_cases:
            searchable = " ".join([case.case_key, case.title, case.feature_name, *case.jira_keys]).lower()
            if q and q not in searchable:
                continue
            if status and case.status != status:
                continue
            if priority and case.priority != priority:
                continue
            if case_type and case.type != case_type:
                continue
            filtered.append(case)

        if sort == "id":
            filtered.sort(key=lambda c: c.case_key.lower())
        elif sort == "feature" or view == "grouped":
            filtered.sort(key=lambda c: (c.feature_name.lower(), c.case_key.lower()))
        else:
            filtered.sort(key=lambda c: (str(c.updated_at or c.created_at or ""), c.id), reverse=True)

        total = len(filtered)
        page_count = max(1, ceil(total / per_page))
        try:
            page = int(hub.request.args.get("page", "1"))
        except ValueError:
            page = 1
        page = min(max(page, 1), page_count)
        start_index = (page - 1) * per_page
        page_cases = filtered[start_index:start_index + per_page]

        args = {key: value for key, value in {
            "q": q, "status": status, "priority": priority, "type": case_type,
            "sort": sort, "view": view, "per_page": per_page,
        }.items() if value not in ("", None)}
        pagination = {
            "page": page,
            "page_count": page_count,
            "per_page": per_page,
            "total": total,
            "start": start_index + 1 if total else 0,
            "end": min(start_index + len(page_cases), total),
            "pages": _page_links(hub, page, page_count, args),
            "prev_url": hub.url_for("index", page=page - 1, **args) if page > 1 else "",
            "next_url": hub.url_for("index", page=page + 1, **args) if page < page_count else "",
        }
        stats = {
            "total": len(all_cases),
            "manual": sum(1 for c in all_cases if c.type == "Manual"),
            "automated": sum(1 for c in all_cases if c.type == "Automated"),
            "ready": sum(1 for c in all_cases if c.status == "Ready"),
        }
        automation = {
            case.id: bdd_sync.automation_status(case)
            for case in page_cases if case.type == "Automated"
        }
        return hub.render_template_string(
            MAIN_PAGE_HTML,
            cases=page_cases,
            stats=stats,
            automation=automation,
            pagination=pagination,
            filters={"q": q, "status": status, "priority": priority, "type": case_type, "sort": sort, "view": view},
            statuses=["Draft", "Ready", "Passed", "Failed", "Blocked"],
            priorities=["Low", "Medium", "High", "Critical"],
            jira_base=hub.JIRA_BASE_URL.rstrip("/"),
            sync_warning=hub.request.args.get("jira_sync_error", ""),
        )

    # Keep the established endpoint name so every existing url_for('index') continues to work.
    app.view_functions["index"] = redesigned_index

    @app.get("/results")
    def results_dashboard():
        try:
            range_days = int(hub.request.args.get("range", "30"))
        except ValueError:
            range_days = 30
        if range_days not in {0, 7, 30, 90}:
            range_days = 30

        runs = hub.db.session.scalars(
            hub.db.select(hub.TestRun).order_by(hub.TestRun.created_at.desc(), hub.TestRun.id.desc())
        ).all()
        runs = [run for run in runs if run.items]
        cutoff = datetime.now(timezone.utc) - timedelta(days=range_days) if range_days else None
        if cutoff:
            runs = [run for run in runs if _aware(run.created_at) and _aware(run.created_at) >= cutoff]

        rows = []
        totals = {"passed": 0, "failed": 0, "blocked": 0, "skipped": 0, "flaky": 0}
        daily = defaultdict(lambda: {"passed": 0, "failed": 0, "blocked": 0, "skipped": 0})
        for run in runs:
            summary = hub.test_run_summary(run)
            for key in ("passed", "failed", "blocked", "skipped"):
                totals[key] += summary[key]
            for row in summary["rows"]:
                attempts = row.get("attempts", [])
                if row["status"] == "Passed" and any(attempt.result == "Failed" for attempt in attempts[:-1]):
                    totals["flaky"] += 1

            outcome = "Incomplete"
            if summary["failed"]:
                outcome = "Failed"
            elif summary["blocked"]:
                outcome = "Blocked"
            elif summary["not_run"]:
                outcome = "Incomplete"
            elif summary["executed"]:
                outcome = "Passed"

            when = _aware(run.finished_at or run.started_at or run.created_at)
            if when:
                bucket = daily[when.date()]
                for key in ("passed", "failed", "blocked", "skipped"):
                    bucket[key] += summary[key]
            rows.append({
                "run": run,
                "summary": summary,
                "outcome": outcome,
                "started": (_aware(run.started_at).strftime("%d %b %Y %H:%M") if run.started_at else "—"),
                "duration": _format_duration(run.started_at, run.finished_at),
            })

        total_cases = sum(totals[key] for key in ("passed", "failed", "blocked", "skipped"))
        decided = totals["passed"] + totals["failed"]
        pass_rate = round(totals["passed"] / decided * 100, 1) if decided else 0
        metrics = {"runs": len(runs), "total_cases": total_cases, "pass_rate": pass_rate, **totals}

        denominator = total_cases or 1
        passed_pct = round(totals["passed"] / denominator * 100, 1)
        failed_pct = round(totals["failed"] / denominator * 100, 1)
        blocked_pct = round(totals["blocked"] / denominator * 100, 1)
        skipped_pct = round(totals["skipped"] / denominator * 100, 1)
        donut = {
            "passed": passed_pct, "failed": failed_pct, "blocked": blocked_pct, "skipped": skipped_pct,
            "passed_end": passed_pct,
            "failed_end": passed_pct + failed_pct,
            "blocked_end": passed_pct + failed_pct + blocked_pct,
        }

        today = datetime.now(timezone.utc).date()
        chart_days = min(range_days or 30, 30)
        dates = [today - timedelta(days=i) for i in reversed(range(chart_days))]
        max_day = max([sum(daily[date].values()) for date in dates] + [1])
        trend = []
        for date in dates:
            counts = daily[date]
            trend.append({
                "label": date.strftime("%d %b") if date.day in {1, 5, 10, 15, 20, 25} else date.strftime("%d"),
                **counts,
                **{f"{key}_pct": round(counts[key] / max_day * 100, 1) for key in ("passed", "failed", "blocked", "skipped")},
            })

        try:
            run_page = max(1, int(hub.request.args.get("page", "1")))
        except ValueError:
            run_page = 1
        per_page = 8
        run_page_count = max(1, ceil(len(rows) / per_page))
        run_page = min(run_page, run_page_count)
        recent_runs = rows[(run_page - 1) * per_page:run_page * per_page]
        run_pages = []
        for number in range(1, run_page_count + 1):
            run_pages.append({
                "number": number,
                "current": number == run_page,
                "url": hub.url_for("results_dashboard", range=range_days, page=number),
            })

        artifacts = []
        for row in rows[:6]:
            run = row["run"]
            if run.jenkins_report_url:
                artifacts.append({"title": f"TR-{run.id:04d} HTML Report", "subtitle": run.name, "url": run.jenkins_report_url})
            if run.jenkins_artifacts_url:
                artifacts.append({"title": f"TR-{run.id:04d} Artifacts", "subtitle": "Traces, screenshots and Jenkins artifacts", "url": run.jenkins_artifacts_url})
            if len(artifacts) >= 6:
                break

        return hub.render_template_string(
            RESULTS_PAGE_HTML,
            range_days=range_days,
            metrics=metrics,
            donut=donut,
            trend=trend,
            recent_runs=recent_runs,
            run_pages=run_pages,
            artifacts=artifacts[:6],
        )
