from flask import Flask, request, redirect, url_for, session, jsonify, render_template_string
import os
import time
import secrets

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "qa-playground-secret-key")

DEMO_USER = "tester"
DEMO_PASSWORD = "password123"

LOGIN_HTML = r"""
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>QA Playground - Login</title>
<style>
:root{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:#172033;background:#f5f7fb}
*{box-sizing:border-box}
body{margin:0;min-height:100vh;display:grid;place-items:center;padding:24px}
.card{width:min(420px,100%);background:white;border:1px solid #dce2ec;border-radius:16px;padding:28px}
h1{margin:0 0 8px} p{color:#5f6b7a}
label{display:block;font-weight:650;margin-top:14px}
input{width:100%;padding:11px 12px;margin-top:6px;border:1px solid #b8c1cf;border-radius:9px;font-size:16px}
button{width:100%;margin-top:18px;padding:12px;border:0;border-radius:9px;background:#2457d6;color:white;font-weight:750;cursor:pointer}
.error{margin-top:12px;padding:10px;background:#fff0f0;color:#9b1c1c;border-radius:8px}
.hint{font-size:13px;background:#eef3ff;padding:10px;border-radius:8px;margin-top:16px}
</style>
</head>
<body>
<main class="card">
  <h1 data-testid="login-title">QA Testing Playground</h1>
  <p>Sign in to enter the test application.</p>

  <form id="loginForm" method="post" action="/login" data-testid="login-form">
    <label for="username">Username</label>
    <input id="username" name="username" autocomplete="username" required data-testid="username-input">

    <label for="password">Password</label>
    <input id="password" name="password" type="password" autocomplete="current-password" required data-testid="password-input">

    <label style="display:flex;align-items:center;gap:8px;font-weight:500">
        <input id="remember" name="remember" type="checkbox" style="width:auto;margin:0" data-testid="remember-checkbox">
        Remember me
    </label>

    <label style="display:flex;align-items:center;gap:8px;font-weight:500">
        <input id="termsCheckbox" name="terms" type="checkbox" required style="width:auto;margin:0" data-testid="terms-checkbox">
        <span>
            I accept the
            <a href="/terms" data-testid="terms-link">Terms & Conditions</a>
        </span>
    </label>

    <button type="submit" data-testid="login-button">Login</button>
  </form>

    {% if error %}
      <div class="error" role="alert" data-testid="login-error">{{ error }}</div>
    {% endif %}

  <div class="hint">
    Demo credentials: <strong>tester</strong> / <strong>password123</strong>
  </div>
</main>
</body>
</html>
"""

PLAYGROUND_HTML = r"""
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>QA Testing Playground</title>
<style>
:root{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:#172033;background:#f5f7fb}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0}
header{position:sticky;top:0;z-index:10;background:#172033;color:white;padding:12px 20px;display:flex;align-items:center;gap:12px;flex-wrap:wrap}
header strong{margin-right:auto}
header a,header button{color:white}
nav{display:flex;gap:8px;flex-wrap:wrap}
nav a{font-size:13px;text-decoration:none;background:#2b3850;padding:7px 9px;border-radius:7px}
.logout{border:1px solid #fff;background:transparent;padding:7px 10px;border-radius:7px;cursor:pointer}
main{width:min(1100px,calc(100% - 32px));margin:24px auto 80px}
section{background:white;border:1px solid #dce2ec;border-radius:14px;padding:20px;margin:18px 0;scroll-margin-top:90px}
h2{margin-top:0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:14px}
.row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
button,.button-link,input,select,textarea{font:inherit}
button,.button-link{padding:9px 13px;border-radius:8px;border:1px solid #aeb9c8;background:#fff;cursor:pointer;text-decoration:none;color:#172033}
.primary{background:#2457d6;color:white;border-color:#2457d6}
.danger{background:#c93636;color:white;border-color:#c93636}
button:disabled{opacity:.45;cursor:not-allowed}
input,select,textarea{width:100%;padding:10px;border:1px solid #b8c1cf;border-radius:8px;margin-top:5px}
label{display:block;margin-top:10px;font-weight:650}
.inline-label{display:flex;align-items:center;gap:7px;font-weight:500;margin:7px 0}
.inline-label input{width:auto;margin:0}
.output{margin-top:12px;padding:10px;border-radius:8px;background:#eef3f8;min-height:42px;white-space:pre-wrap}
.success{background:#e8f8ed;color:#166534}
.error{background:#fff0f0;color:#9b1c1c}
.tabs{display:flex;gap:6px;margin-bottom:10px}
.tab-panel{display:none;padding:12px;background:#f6f8fb;border-radius:8px}
.tab-panel.active{display:block}
.accordion-panel{display:none;padding:10px;background:#f6f8fb;border-radius:0 0 8px 8px}
.accordion-panel.open{display:block}
.modal-backdrop{display:none;position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:50;place-items:center;padding:20px}
.modal-backdrop.open{display:grid}
.modal{width:min(450px,100%);background:white;border-radius:14px;padding:20px}
.toast{position:fixed;right:20px;bottom:20px;background:#172033;color:white;padding:12px 16px;border-radius:9px;display:none;z-index:60}
.toast.show{display:block}
table{width:100%;border-collapse:collapse}
th,td{text-align:left;border-bottom:1px solid #e1e6ee;padding:9px}
th button{padding:4px 7px}
.pagination{display:flex;gap:6px;margin-top:12px}
.drag-list{display:grid;gap:8px}
.drag-item{padding:10px;background:#eef3ff;border:1px solid #b9c9f5;border-radius:8px;cursor:grab}
.drop-zone{padding:18px;border:2px dashed #9ca9ba;border-radius:9px;text-align:center}
.long-block{height:240px;display:grid;place-items:center;background:linear-gradient(#f3f5f8,#e7ecf4);border-radius:10px;margin:10px 0}
.progress{height:16px;background:#e5e9f0;border-radius:999px;overflow:hidden}
.progress>div{height:100%;width:0;background:#2457d6;transition:width .2s}
.tooltip-wrap{position:relative;display:inline-block}
.tooltip{display:none;position:absolute;left:0;top:105%;background:#172033;color:white;padding:7px;border-radius:6px;white-space:nowrap;font-size:13px}
.tooltip-wrap:hover .tooltip,.tooltip-wrap:focus-within .tooltip{display:block}
#contextMenu{display:none;position:absolute;background:white;border:1px solid #b8c1cf;border-radius:8px;padding:6px;z-index:40}
#contextMenu.open{display:block}
.popup-banner{
    position:fixed;
    top:70px;
    right:20px;
    z-index:100;
    padding:12px 18px;
    background:#2457d6;
    color:white;
    text-decoration:none;
    font-weight:700;
    border-radius:8px;
    box-shadow:0 4px 12px rgba(0,0,0,.18);
}
.popup-banner:hover{background:#1d46ad}
</style>
</head>
<body>
<a
  href="/popup"
  target="_blank"
  rel="noopener"
  data-testid="popup-link"
  class="popup-banner">
  Open Popup Practice Page
</a>

<header>
  <strong>QA Playground</strong>
  <nav>
    <a href="#buttons">Buttons</a>
    <a href="#forms">Forms</a>
    <a href="#widgets">Widgets</a>
    <a href="#links">Links</a>
    <a href="#table">Table</a>
    <a href="#drag">Drag & Drop</a>
    <a href="#scroll">Scroll</a>
  </nav>
  <form method="post" action="/logout" style="margin:0">
    <button class="logout" type="submit" data-testid="logout-button">Logout</button>
  </form>
</header>

<main>
<section id="welcome">
  <h1 data-testid="welcome-heading">Welcome, {{ username }}</h1>
  <p>This page is intentionally packed with common UI controls for Playwright practice.</p>
</section>

<section id="buttons">
  <h2>1. Buttons & Click Events</h2>
  <div class="row">
    <button type="button" id="normalBtn" data-testid="normal-button">Normal Button</button>
    <button type="button" id="primaryBtn" class="primary">Primary Button</button>
    <button type="button" id="doubleBtn">Double-click Me</button>
    <button type="button" id="disabledBtn" disabled>Disabled Button</button>
    <button type="button" id="dangerBtn" class="danger">Danger Button</button>
  </div>
  <div id="buttonOutput" class="output" aria-live="polite">No button clicked yet.</div>
</section>

<section id="forms">
  <h2>2. Form Inputs & Validation</h2>
  <form id="profileForm">
    <div class="grid">
      <div>
        <label for="fullName">Text input</label>
        <input id="fullName" name="fullName" placeholder="Full name" required data-testid="full-name">
      </div>
      <div>
        <label for="email">Email input</label>
        <input id="email" name="email" type="email" placeholder="qa@example.com" required>
      </div>
      <div>
        <label for="age">Number input</label>
        <input id="age" name="age" type="number" min="18" max="120" value="30">
      </div>
      <div>
        <label for="birthDate">Date input</label>
        <input id="birthDate" name="birthDate" type="date">
      </div>
      <div>
        <label for="appointment">Datetime input</label>
        <input id="appointment" name="appointment" type="datetime-local">
      </div>
      <div>
        <label for="country">Select dropdown</label>
        <select id="country" name="country">
          <option value="">Choose one</option>
          <option value="at">Austria</option>
          <option value="gr">Greece</option>
          <option value="de">Germany</option>
          <option value="uk">United Kingdom</option>
        </select>
      </div>
    </div>

    <label for="bio">Textarea</label>
    <textarea id="bio" name="bio" rows="4" maxlength="180" placeholder="Write a short description"></textarea>
    <div><span id="charCount">0</span>/180 characters</div>

    <div class="grid">
      <div>
        <h3>Checkboxes</h3>
        <label class="inline-label"><input type="checkbox" name="skills" value="python" data-testid="checkbox-python"> Python</label>
        <label class="inline-label"><input type="checkbox" name="skills" value="playwright"> Playwright</label>
        <label class="inline-label"><input type="checkbox" name="skills" value="api"> API Testing</label>
        <label class="inline-label"><input type="checkbox" name="skills" value="sql"> SQL</label>
      </div>
      <div>
        <h3>Radio Buttons</h3>
        <label class="inline-label"><input type="radio" name="level" value="junior"> Junior</label>
        <label class="inline-label"><input type="radio" name="level" value="mid" checked> Mid</label>
        <label class="inline-label"><input type="radio" name="level" value="senior"> Senior</label>
      </div>
    </div>

    <label for="experience">Range slider: <span id="rangeValue">5</span></label>
    <input id="experience" type="range" min="0" max="10" value="5">

    <label for="resume">File upload</label>
    <input id="resume" type="file" accept=".txt,.pdf,.png,.jpg">

    <div class="row" style="margin-top:12px">
      <button type="submit" class="primary" data-testid="submit-profile">Submit Form</button>
      <button type="reset">Reset Form</button>
    </div>
  </form>
  <div id="formOutput" class="output" aria-live="polite">Form has not been submitted.</div>
</section>

<section id="widgets">
  <h2>3. Tabs, Accordion, Modal, Toast & Dynamic Elements</h2>

  <h3>Tabs</h3>
  <div class="tabs" role="tablist">
    <button type="button" class="tabBtn primary" data-tab="tab1">Overview</button>
    <button type="button" class="tabBtn" data-tab="tab2">Details</button>
    <button type="button" class="tabBtn" data-tab="tab3">Settings</button>
  </div>
  <div id="tab1" class="tab-panel active">Overview tab content.</div>
  <div id="tab2" class="tab-panel">Details tab content.</div>
  <div id="tab3" class="tab-panel">Settings tab content.</div>

  <h3>Accordion</h3>
  <button type="button" id="accordionBtn" aria-expanded="false">Open Accordion</button>
  <div id="accordionPanel" class="accordion-panel">Hidden accordion content is now visible.</div>

  <h3>Modal / Dialog</h3>
  <div class="row">
    <button type="button" id="openModal">Open Modal</button>
    <button type="button" id="showToast">Show Toast</button>
    <button type="button" id="addDynamic">Add Dynamic Element</button>
    <button type="button" id="removeDynamic">Remove Dynamic Element</button>
  </div>
  <div id="dynamicArea" class="output">Dynamic area is empty.</div>

  <h3>Delayed / Loading State</h3>
  <button type="button" id="loadBtn">Load Data (2 seconds)</button>
  <div class="progress" style="margin-top:10px"><div id="progressBar"></div></div>
  <div id="loadOutput" class="output">Waiting.</div>

  <h3>Tooltip</h3>
  <span class="tooltip-wrap">
    <button type="button" id="tooltipBtn">Hover or Focus Me</button>
    <span class="tooltip" role="tooltip">This is a tooltip</span>
  </span>

  <h3>Right-click / Context Menu</h3>
  <button type="button" id="contextTarget">Right-click Me</button>
  <div id="contextMenu">
    <button type="button" id="contextAction">Context Action</button>
  </div>
</section>

<section id="frames">
  <h2>4. Iframe Practice</h2>

  <iframe
    id="dialogFrame"
    data-testid="dialog-frame"
    src="/frame-dialogs"
    title="Browser Dialog Practice"
    style="width:100%;height:300px;border:1px solid #b8c1cf;border-radius:10px;">
  </iframe>
</section>

<section id="alerts">
  <h2>4. Browser Dialogs</h2>
  <div class="row">
    <button type="button" id="alertBtn">JavaScript Alert</button>
    <button type="button" id="confirmBtn">Confirm Dialog</button>
    <button type="button" id="promptBtn">Prompt Dialog</button>
  </div>
  <div id="dialogOutput" class="output">No dialog result yet.</div>
</section>

<section id="links">
  <h2>5. Links & Navigation</h2>
  <div class="row">
    <a class="button-link" href="/secondary" id="internalLink">Internal Page</a>
    <a class="button-link" href="/popup" target="_blank" rel="noopener" data-testid="popup-link-secondary">Open Popup Page</a>
    <a class="button-link" href="https://example.com" target="_blank" rel="noopener" id="newTabLink">Open New Tab</a>
    <a class="button-link" href="#scroll-bottom">Anchor Link</a>
  </div>
</section>

<section id="table">
  <h2>6. Searchable / Sortable Table & Pagination</h2>
  <label for="tableSearch">Filter users</label>
  <input id="tableSearch" placeholder="Search by name or role">
  <table>
    <thead>
      <tr>
        <th><button type="button" id="sortName">Name ↕</button></th>
        <th>Role</th>
        <th>Status</th>
      </tr>
    </thead>
    <tbody id="tableBody"></tbody>
  </table>
  <div id="pagination" class="pagination"></div>
</section>

<section id="drag">
  <h2>7. Drag & Drop</h2>
  <p>Drag an item into the target. A click-based alternative is included for accessibility and easier automation.</p>
  <div id="dragList" class="drag-list">
    <div class="drag-item" draggable="true" data-value="Test Case A">Test Case A</div>
    <div class="drag-item" draggable="true" data-value="Test Case B">Test Case B</div>
    <div class="drag-item" draggable="true" data-value="Test Case C">Test Case C</div>
  </div>
  <div id="dropZone" class="drop-zone" style="margin-top:12px">Drop here</div>
  <select id="dragSelect" style="margin-top:10px">
    <option>Test Case A</option><option>Test Case B</option><option>Test Case C</option>
  </select>
  <button type="button" id="moveSelected" style="margin-top:8px">Move Selected Item</button>
  <div id="dropOutput" class="output">Nothing dropped yet.</div>
</section>

<section id="keyboard">
  <h2>8. Keyboard Events</h2>
  <label for="keyboardInput">Type here, then press Enter</label>
  <input id="keyboardInput" placeholder="Press Enter after typing">
  <div id="keyboardOutput" class="output">Waiting for keyboard input.</div>
</section>

<section id="scroll">
  <h2>9. Scrolling</h2>
  <p>This section provides enough vertical distance for scroll tests.</p>
  <div class="long-block">Scroll checkpoint 1</div>
  <div class="long-block">Scroll checkpoint 2</div>
  <div class="long-block">Scroll checkpoint 3</div>
  <div class="long-block">Scroll checkpoint 4</div>
  <div id="scroll-bottom" class="output success" data-testid="scroll-bottom">✅ Bottom of scroll test reached.</div>
  <button type="button" id="backTop" style="margin-top:10px">Back to Top</button>
</section>
</main>

<div id="modalBackdrop" class="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="modalTitle">
  <div class="modal">
    <h2 id="modalTitle">Test Modal</h2>
    <p>This modal is useful for visibility, focus and close-button tests.</p>
    <label for="modalInput">Modal input</label>
    <input id="modalInput" placeholder="Type inside modal">
    <button type="button" id="closeModal" class="primary" style="margin-top:12px">Close Modal</button>
  </div>
</div>

<div id="toast" class="toast" role="status">✅ Toast notification shown</div>

<script>
const buttonOutput=document.getElementById('buttonOutput');
document.getElementById('normalBtn').addEventListener('click',()=>buttonOutput.textContent='Normal button clicked');
document.getElementById('primaryBtn').addEventListener('click',()=>buttonOutput.textContent='Primary button clicked');
document.getElementById('dangerBtn').addEventListener('click',()=>buttonOutput.textContent='Danger button clicked');
document.getElementById('doubleBtn').addEventListener('dblclick',()=>buttonOutput.textContent='Double-click detected');

const bio=document.getElementById('bio');
bio.addEventListener('input',()=>document.getElementById('charCount').textContent=bio.value.length);
const range=document.getElementById('experience');
range.addEventListener('input',()=>document.getElementById('rangeValue').textContent=range.value);

document.getElementById('profileForm').addEventListener('submit',e=>{
  e.preventDefault();
  if(!e.currentTarget.reportValidity()) return;
  const fd=new FormData(e.currentTarget);
  const skills=fd.getAll('skills');
  const file=document.getElementById('resume').files[0];
  document.getElementById('formOutput').textContent=
    `Submitted successfully\nName: ${fd.get('fullName')}\nEmail: ${fd.get('email')}\nCountry: ${fd.get('country')||'(none)'}\nSkills: ${skills.join(', ')||'(none)'}\nLevel: ${fd.get('level')}\nFile: ${file?file.name:'(none)'}`;
});

document.querySelectorAll('.tabBtn').forEach(btn=>{
  btn.addEventListener('click',()=>{
    document.querySelectorAll('.tabBtn').forEach(b=>b.classList.remove('primary'));
    document.querySelectorAll('.tab-panel').forEach(p=>p.classList.remove('active'));
    btn.classList.add('primary');
    document.getElementById(btn.dataset.tab).classList.add('active');
  });
});

document.getElementById('accordionBtn').addEventListener('click',e=>{
  const panel=document.getElementById('accordionPanel');
  const open=panel.classList.toggle('open');
  e.currentTarget.setAttribute('aria-expanded',String(open));
  e.currentTarget.textContent=open?'Close Accordion':'Open Accordion';
});

const modal=document.getElementById('modalBackdrop');
document.getElementById('openModal').addEventListener('click',()=>{modal.classList.add('open');document.getElementById('modalInput').focus()});
document.getElementById('closeModal').addEventListener('click',()=>modal.classList.remove('open'));
modal.addEventListener('click',e=>{if(e.target===modal)modal.classList.remove('open')});

document.getElementById('showToast').addEventListener('click',()=>{
  const toast=document.getElementById('toast');toast.classList.add('show');
  setTimeout(()=>toast.classList.remove('show'),1800);
});

let dynamicCounter=0;
document.getElementById('addDynamic').addEventListener('click',()=>{
  dynamicCounter++;
  document.getElementById('dynamicArea').innerHTML=`<button type="button" id="dynamicButton" data-testid="dynamic-button">Dynamic Button ${dynamicCounter}</button>`;
  document.getElementById('dynamicButton').addEventListener('click',()=>document.getElementById('dynamicArea').append(' — clicked'));
});
document.getElementById('removeDynamic').addEventListener('click',()=>{document.getElementById('dynamicArea').textContent='Dynamic area is empty.'});

document.getElementById('loadBtn').addEventListener('click',()=>{
  const out=document.getElementById('loadOutput'),bar=document.getElementById('progressBar'),btn=document.getElementById('loadBtn');
  btn.disabled=true;out.textContent='Loading...';bar.style.width='25%';
  setTimeout(()=>bar.style.width='65%',700);
  setTimeout(()=>{bar.style.width='100%';out.textContent='✅ Data loaded successfully';btn.disabled=false},2000);
});

document.getElementById('alertBtn').addEventListener('click',()=>{alert('Test alert message');document.getElementById('dialogOutput').textContent='Alert accepted'});
document.getElementById('confirmBtn').addEventListener('click',()=>{const r=confirm('Do you confirm?');document.getElementById('dialogOutput').textContent='Confirm result: '+r});
document.getElementById('promptBtn').addEventListener('click',()=>{const r=prompt('Enter a value','Playwright');document.getElementById('dialogOutput').textContent='Prompt result: '+r});

const ctx=document.getElementById('contextMenu');
document.getElementById('contextTarget').addEventListener('contextmenu',e=>{e.preventDefault();ctx.style.left=e.pageX+'px';ctx.style.top=e.pageY+'px';ctx.classList.add('open')});
document.getElementById('contextAction').addEventListener('click',()=>{buttonOutput.textContent='Context action clicked';ctx.classList.remove('open')});
document.addEventListener('click',e=>{if(!ctx.contains(e.target)&&e.target.id!=='contextTarget')ctx.classList.remove('open')});

const rows=[
{name:'Alice',role:'QA Engineer',status:'Active'},
{name:'Bob',role:'Developer',status:'Active'},
{name:'Charlie',role:'Product Owner',status:'Inactive'},
{name:'Diana',role:'QA Automation',status:'Active'},
{name:'Evan',role:'Designer',status:'Active'},
{name:'Fatima',role:'Developer',status:'Inactive'},
{name:'George',role:'Scrum Master',status:'Active'},
{name:'Hana',role:'QA Engineer',status:'Active'},
{name:'Ivan',role:'DevOps',status:'Active'},
{name:'Julia',role:'Support',status:'Inactive'},
{name:'Kevin',role:'Developer',status:'Active'},
{name:'Lina',role:'QA Automation',status:'Active'}
];
let tablePage=1,sortAsc=true;
const pageSize=5;
function filteredRows(){
  const q=document.getElementById('tableSearch').value.toLowerCase();
  return rows.filter(r=>(r.name+' '+r.role+' '+r.status).toLowerCase().includes(q))
    .sort((a,b)=>sortAsc?a.name.localeCompare(b.name):b.name.localeCompare(a.name));
}
function renderTable(){
  const data=filteredRows(),pages=Math.max(1,Math.ceil(data.length/pageSize));tablePage=Math.min(tablePage,pages);
  const body=document.getElementById('tableBody');body.innerHTML='';
  data.slice((tablePage-1)*pageSize,tablePage*pageSize).forEach(r=>{
    const tr=document.createElement('tr');tr.innerHTML=`<td>${r.name}</td><td>${r.role}</td><td>${r.status}</td>`;body.appendChild(tr);
  });
  const p=document.getElementById('pagination');p.innerHTML='';
  for(let i=1;i<=pages;i++){const b=document.createElement('button');b.type='button';b.textContent=i;if(i===tablePage)b.className='primary';b.addEventListener('click',()=>{tablePage=i;renderTable()});p.appendChild(b)}
}
document.getElementById('tableSearch').addEventListener('input',()=>{tablePage=1;renderTable()});
document.getElementById('sortName').addEventListener('click',()=>{sortAsc=!sortAsc;renderTable()});
renderTable();

let dragged='';
document.querySelectorAll('.drag-item').forEach(el=>{
  el.addEventListener('dragstart',()=>dragged=el.dataset.value);
});
const drop=document.getElementById('dropZone');
drop.addEventListener('dragover',e=>e.preventDefault());
drop.addEventListener('drop',e=>{e.preventDefault();document.getElementById('dropOutput').textContent='Dropped: '+dragged});
document.getElementById('moveSelected').addEventListener('click',()=>{document.getElementById('dropOutput').textContent='Moved: '+document.getElementById('dragSelect').value});

document.getElementById('keyboardInput').addEventListener('keydown',e=>{
  if(e.key==='Enter')document.getElementById('keyboardOutput').textContent='Enter pressed with value: '+e.currentTarget.value;
});

document.getElementById('backTop').addEventListener('click',()=>window.scrollTo({top:0,behavior:'smooth'}));
</script>
</body>
</html>
"""

SECONDARY_HTML = """
<!doctype html><html><head><meta charset="utf-8"><title>Secondary Page</title>
<style>body{font-family:system-ui;padding:40px;background:#f5f7fb}a{display:inline-block;margin-top:20px}</style>
</head><body>
<h1 data-testid="secondary-heading">Secondary Page</h1>
<p>You successfully navigated to another internal route.</p>
<a href="/playground" data-testid="back-link">Back to Playground</a>
</body></html>
"""

POPUP_HTML = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Popup Practice Page</title>
<style>
:root{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:#172033;background:#f5f7fb}
*{box-sizing:border-box}
body{margin:0;min-height:100vh;display:grid;place-items:center;padding:24px}
.card{width:min(560px,100%);background:white;border:1px solid #dce2ec;border-radius:16px;padding:28px}
h1{margin-top:0}
button{padding:10px 14px;border-radius:8px;border:1px solid #2457d6;background:#2457d6;color:white;cursor:pointer}
.output{margin-top:14px;padding:10px;border-radius:8px;background:#eef3f8;min-height:42px}
</style>
</head>
<body>
<main class="card">
  <h1 data-testid="popup-heading">Welcome to the Popup Page</h1>
  <p data-testid="popup-message">This page was opened in a new browser tab.</p>

  <button type="button" id="popupButton" data-testid="popup-button">
    Click Me
  </button>

  <div id="popupResult" class="output" data-testid="popup-result">
    Button has not been clicked yet.
  </div>
</main>

<script>
document.getElementById('popupButton').addEventListener('click', () => {
    document.getElementById('popupResult').textContent = 'Button clicked successfully!';
});
</script>
</body>
</html>
"""

FRAME_DIALOGS_HTML = """
<!doctype html>
<html lang="en">

<head>
<meta charset="utf-8">
<title>Frame Dialogs</title>

<style>
body{
    font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
    padding:20px;
    background:#f5f7fb;
}

button{
    padding:9px 13px;
    margin-right:8px;
    border-radius:8px;
    border:1px solid #aeb9c8;
    background:white;
    cursor:pointer;
}

.output{
    margin-top:15px;
    padding:10px;
    background:#eef3f8;
    border-radius:8px;
}
</style>
</head>

<body>

<h2 data-testid="frame-heading">
    Browser Dialogs inside Iframe
</h2>

<button
    type="button"
    id="frameAlertBtn">
    JavaScript Alert
</button>

<button
    type="button"
    id="frameConfirmBtn">
    Confirm Dialog
</button>

<button
    type="button"
    id="framePromptBtn">
    Prompt Dialog
</button>

<div
    id="frameOutput"
    class="output"
    data-testid="frame-output">
    No dialog result yet.
</div>

<script>

document.getElementById('frameAlertBtn').addEventListener('click', () => {
    alert('Frame alert message');

    document.getElementById('frameOutput').textContent =
        'Frame alert accepted';
});


document.getElementById('frameConfirmBtn').addEventListener('click', () => {

    const result = confirm('Do you confirm inside the frame?');

    document.getElementById('frameOutput').textContent =
        'Confirm result: ' + result;
});


document.getElementById('framePromptBtn').addEventListener('click', () => {

    const result = prompt(
        'Enter a value inside the frame',
        'Playwright'
    );

    document.getElementById('frameOutput').textContent =
        'Prompt result: ' + result;
});

</script>
<script>
document.getElementById("loginForm").addEventListener("submit", async (event) => {
    event.preventDefault();

    const form = event.currentTarget;

    if (!form.reportValidity()) {
        return;
    }

    const formData = new FormData(form);

    const response = await fetch("/login", {
        method: "POST",
        body: formData
    });

    const data = await response.json();

    if (response.ok) {
        localStorage.setItem("authToken", data.token);

        window.location.href = "/playground";
    } else {
        alert(data.error);
    }
});
</script>
</body>
</html>
"""


@app.get("/")
def index():
    if session.get("user"):
        return redirect(url_for("playground"))
    return render_template_string(LOGIN_HTML, error=None)


@app.post("/login")
def login():
    username = request.form.get("username", "")
    password = request.form.get("password", "")

    if username == DEMO_USER and password == DEMO_PASSWORD:

        token = secrets.token_urlsafe(32)

        session["user"] = username
        session["auth_token"] = token

        return jsonify({
            "message": "Login successful",
            "username": username,
            "token": token,
            "token_type": "Bearer"
        }), 200

    return jsonify({
        "error": "Invalid username or password"
    }), 401


@app.get("/playground")
def playground():
    if not session.get("user"):
        return redirect(url_for("index"))
    return render_template_string(PLAYGROUND_HTML, username=session["user"])


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.get("/secondary")
def secondary():
    if not session.get("user"):
        return redirect(url_for("index"))
    return SECONDARY_HTML


@app.get("/popup")
def popup():
    if not session.get("user"):
        return redirect(url_for("index"))
    return POPUP_HTML

@app.get("/frame-dialogs")
def frame_dialogs():
    if not session.get("user"):
        return redirect(url_for("index"))

    return FRAME_DIALOGS_HTML

@app.get("/api/status")
def api_status():
    time.sleep(0.3)
    return jsonify({"status": "ok", "message": "QA Playground API is working"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3001))
    debug = os.environ.get("FLASK_DEBUG") == "1"

    app.run(
        host="0.0.0.0",
        port=port,
        debug=debug
    )
