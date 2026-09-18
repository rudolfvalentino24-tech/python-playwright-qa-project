from pathlib import Path
from flask import Flask, request, redirect, url_for, session, Response, render_template_string
import subprocess
import time
import os

BASE_DIR = Path(__file__).resolve().parent
TESTS_DIR = BASE_DIR / "tests"

app = Flask(__name__)
app.secret_key = "change-this-secret"

ALLOWED_ENVS = {"staging", "qa"}
REAUTH_SECONDS = 25 * 60


def list_tests():
    TESTS_DIR.mkdir(exist_ok=True)
    return [
        {
            "value": str(p.relative_to(BASE_DIR)).replace("\\", "/"),
            "label": p.name
        }
        for p in sorted(TESTS_DIR.glob("test_*.py"))
    ]


LOGIN_HTML = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Playwright Auth</title>
<style>
html,body{height:100%;margin:0;font-family:Arial,sans-serif;background:#123fa8;color:#fff}
.wrap{height:100%;display:flex;align-items:center;justify-content:center}
.card{width:340px;background:rgba(0,0,0,.35);padding:22px;border-radius:14px}
input,select,button{width:100%;box-sizing:border-box;margin:7px 0;padding:10px;border-radius:8px}
input,select{background:rgba(0,0,0,.3);color:white;border:1px solid rgba(255,255,255,.3)}
button{border:0;font-weight:700;cursor:pointer}
.row{display:flex;gap:8px}.row input{flex:1}.row button{width:auto}
#msg{white-space:pre-wrap;font-family:monospace;margin-top:10px}
</style>
</head>
<body>
<div class="wrap">
<div class="card">
<h2>🔐 Welcome Back!</h2>
<form id="form">
<input type="email" name="email" placeholder="Email" required>
<div class="row">
<input type="password" id="password" name="password" placeholder="Password" required>
<button type="button" id="toggle">👁️</button>
</div>
<input type="text" name="company" placeholder="Company name" required>
<select name="environment" required>
<option value="">-- Select environment --</option>
<option value="staging">Staging</option>
<option value="qa">QA</option>
</select>
<button type="submit">Run Authentication</button>
</form>
<div id="msg"></div>
</div>
</div>
<script>
const form=document.getElementById('form');
const msg=document.getElementById('msg');
const pwd=document.getElementById('password');
document.getElementById('toggle').onclick=()=>{
  pwd.type=pwd.type==='password'?'text':'password';
};
form.onsubmit=async(e)=>{
  e.preventDefault();
  msg.textContent='Running authentication...';
  const r=await fetch('/login',{method:'POST',body:new FormData(form)});
  const t=await r.text();
  if(r.ok){
    msg.textContent='✅ Authentication complete';
    setTimeout(()=>location.href='/tests',400);
  }else{
    msg.textContent='❌ '+t;
  }
};
</script>
</body>
</html>
"""


TESTS_HTML = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Python Playwright Runner</title>
<style>
html,body{margin:0;min-height:100%;font-family:Arial,sans-serif;background:#123fa8;color:#fff}
.top{position:fixed;top:15px;right:20px;display:flex;gap:10px;align-items:center}
.layout{display:flex;gap:20px;padding:80px 20px 240px}
.panel{flex:1;background:rgba(0,0,0,.35);padding:16px;border-radius:14px;min-height:560px}
button,input{padding:8px;border-radius:8px}
button{cursor:pointer;font-weight:700}
ul{list-style:none;padding:0}
li{display:flex;gap:8px;align-items:center;background:rgba(255,255,255,.1);padding:8px;margin:6px 0;border-radius:8px}
.label{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.add{background:#ffcc4d;border:0;border-radius:50%;width:26px;height:26px;padding:0}
.mode-panel{display:none}.mode-panel.active{display:block}.mode.active{background:#ffcc4d}
.runbox{min-height:150px;border:1px dashed rgba(255,255,255,.5);padding:8px;border-radius:8px}
#log{position:fixed;bottom:10px;left:50%;transform:translateX(-50%);width:80vw;height:190px;background:#000;color:#0f0;padding:12px;overflow:auto;white-space:pre-wrap;font-family:monospace;border-radius:10px}
@media(max-width:900px){.layout{flex-direction:column}}
</style>
</head>
<body>
<div class="top">
<div id="timer">25:00</div>
<form method="post" action="/logout"><button>Logout</button></form>
</div>

<div class="layout">
<div class="panel">
<h2>🧪 Test Cases</h2>
<input id="search" placeholder="Search tests..." style="width:100%;box-sizing:border-box">
<ul id="tests"></ul>
</div>

<div class="panel">
<h2>⚙️ Runs & Scheduler</h2>
<div>
<button class="mode active" data-mode="parallel">Parallel</button>
<button class="mode" data-mode="sequential">Sequential</button>
<button class="mode" data-mode="scheduler">Scheduler</button>
</div>

<div id="parallel" class="mode-panel active">
<h3>Parallel</h3>
<ul id="parallelList" class="runbox"></ul>
<label>Repeat <input id="parallelRepeat" type="number" value="1" min="1" style="width:60px"></label>
<label><input id="parallelHeaded" type="checkbox"> Headed</label>
<label><input id="parallelDebug" type="checkbox"> Debug</label>
<button onclick="runMode('parallel')">Run Parallel</button>
<button onclick="clearMode('parallel')">Clear box</button>
</div>

<div id="sequential" class="mode-panel">
<h3>Sequential</h3>
<ul id="sequentialList" class="runbox"></ul>
<label>Repeat <input id="sequentialRepeat" type="number" value="1" min="1" style="width:60px"></label>
<label><input id="sequentialHeaded" type="checkbox"> Headed</label>
<label><input id="sequentialDebug" type="checkbox"> Debug</label>
<button onclick="runMode('sequential')">Run Sequential</button>
<button onclick="clearMode('sequential')">Clear box</button>
</div>

<div id="scheduler" class="mode-panel">
<h3>Scheduler</h3>
<ul id="schedulerList" class="runbox"></ul>
<label>Repeat <input id="schedulerRepeat" type="number" value="1" min="1" style="width:60px"></label>
<input id="scheduleTime" type="datetime-local">
<button onclick="scheduleRun()">Save schedule</button>
<button onclick="clearMode('scheduler')">Clear box</button>
<h4>Saved Schedules</h4>
<ul id="savedSchedules"></ul>
</div>
</div>
</div>

<div id="log"></div>

<script>
const TESTS={{ tests|tojson }};
const sets={parallel:[],sequential:[],scheduler:[]};
let activeMode='parallel';
const schedules=[];

function renderTests(){
  const q=document.getElementById('search').value.toLowerCase();
  const ul=document.getElementById('tests');
  ul.innerHTML='';
  TESTS.filter(t=>t.label.toLowerCase().includes(q)).forEach(t=>{
    const li=document.createElement('li');
    const add=document.createElement('button');
    add.className='add'; add.textContent='+';
    add.onclick=()=>{sets[activeMode].push(t.value);renderSet(activeMode)};
    const label=document.createElement('span');
    label.className='label'; label.textContent=t.label;
    li.append(add,label); ul.appendChild(li);
  });
}

function renderSet(mode){
  const ul=document.getElementById(mode+'List');
  ul.innerHTML='';
  sets[mode].forEach((v,i)=>{
    const li=document.createElement('li');
    const label=document.createElement('span');
    label.className='label'; label.textContent=v.split('/').pop();
    const remove=document.createElement('button');
    remove.textContent='✕';
    remove.onclick=()=>{sets[mode].splice(i,1);renderSet(mode)};
    li.append(label,remove); ul.appendChild(li);
  });
}

function clearMode(mode){sets[mode]=[];renderSet(mode)}

document.querySelectorAll('.mode').forEach(b=>{
  b.onclick=()=>{
    activeMode=b.dataset.mode;
    document.querySelectorAll('.mode').forEach(x=>x.classList.remove('active'));
    b.classList.add('active');
    document.querySelectorAll('.mode-panel').forEach(x=>x.classList.remove('active'));
    document.getElementById(activeMode).classList.add('active');
  };
});

document.getElementById('search').oninput=renderTests;

async function runMode(mode){
  if(!sets[mode].length){alert('Add at least one test');return}
  const payload={
    mode,
    tests:sets[mode],
    repeat:document.getElementById(mode+'Repeat').value||1,
    headed:document.getElementById(mode+'Headed')?.checked||false,
    debug:document.getElementById(mode+'Debug')?.checked||false
  };
  const r=await fetch('/run-tests',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify(payload)
  });
  const log=document.getElementById('log');
  log.textContent='';
  const reader=r.body.getReader();
  const decoder=new TextDecoder();
  while(true){
    const {value,done}=await reader.read();
    if(done)break;
    log.textContent+=decoder.decode(value);
    log.scrollTop=log.scrollHeight;
  }
}

function scheduleRun(){
  const raw=document.getElementById('scheduleTime').value;
  if(!raw){alert('Choose a date and time');return}
  if(!sets.scheduler.length){alert('Add tests first');return}
  schedules.push({
    time:new Date(raw).getTime(),
    name:new Date(raw).toLocaleString(),
    tests:[...sets.scheduler],
    repeat:document.getElementById('schedulerRepeat').value||1,
    fired:false
  });
  renderSchedules();
}

function renderSchedules(){
  const ul=document.getElementById('savedSchedules');
  ul.innerHTML='';
  schedules.forEach((s,i)=>{
    const li=document.createElement('li');
    const label=document.createElement('span');
    label.className='label';
    label.textContent=`${s.name} — ${s.tests.length} test(s)`;
    const remove=document.createElement('button');
    remove.textContent='✕';
    remove.onclick=()=>{schedules.splice(i,1);renderSchedules()};
    li.append(label,remove);ul.appendChild(li);
  });
}

setInterval(()=>{
  schedules.forEach(s=>{
    if(!s.fired && Date.now()>=s.time){
      s.fired=true;
      fetch('/run-tests',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({
          mode:'sequential',
          tests:s.tests,
          repeat:s.repeat,
          headed:false,
          debug:false
        })
      });
      renderSchedules();
    }
  });
},1000);

let remaining={{ reauth_seconds }};
function updateTimer(){
  const m=Math.floor(remaining/60);
  const s=remaining%60;
  document.getElementById('timer').textContent=`${m}:${String(s).padStart(2,'0')}`;
}
setInterval(async()=>{
  if(remaining>0){remaining--;updateTimer()}
  else{
    await fetch('/reauth',{method:'POST'});
    remaining={{ reauth_seconds }};
    updateTimer();
  }
},1000);

renderTests();
renderSet('parallel');
renderSet('sequential');
renderSet('scheduler');
updateTimer();
</script>
</body>
</html>
"""


@app.get("/")
def index():
    if session.get("authenticated"):
        return redirect(url_for("tests_page"))
    return render_template_string(LOGIN_HTML)


@app.post("/login")
def login():
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")
    company = request.form.get("company", "").strip()
    environment = request.form.get("environment", "").strip().lower()

    if not all([email, password, company, environment]):
        return "Missing required authentication data.", 400

    if environment not in ALLOWED_ENVS:
        return "Invalid environment.", 400

    session["authenticated"] = True
    session["email"] = email
    session["password"] = password
    session["company"] = company
    session["environment"] = environment
    session["authenticated_at"] = time.time()
    return "OK"


@app.get("/tests")
def tests_page():
    if not session.get("authenticated"):
        return redirect(url_for("index"))
    return render_template_string(
        TESTS_HTML,
        tests=list_tests(),
        reauth_seconds=REAUTH_SECONDS
    )


def build_pytest_command(test_file, repeat=1, headed=False):
    cmd = ["pytest", str(test_file), "-v", "-s"]
    if int(repeat) > 1:
        cmd += ["--count", str(int(repeat))]
    if headed:
        cmd.append("--headed")
    return cmd


@app.post("/run-tests")
def run_tests():
    if not session.get("authenticated"):
        return "Unauthorized", 401

    data = request.get_json(silent=True) or {}
    mode = data.get("mode", "sequential")
    tests = data.get("tests", [])
    repeat = max(1, int(data.get("repeat", 1)))
    headed = bool(data.get("headed", False))
    debug = bool(data.get("debug", False))

    safe = []
    for rel in tests:
        candidate = (BASE_DIR / rel).resolve()
        try:
            candidate.relative_to(TESTS_DIR.resolve())
        except ValueError:
            continue
        if candidate.exists() and candidate.suffix == ".py":
            safe.append(candidate)

    if not safe:
        return "No valid tests selected", 400

    def stream():
        env = os.environ.copy()
        if debug:
            env["PWDEBUG"] = "1"

        yield f"🚀 Running {len(safe)} test file(s) in {mode} mode\n\n"

        if mode == "parallel":
            processes = []
            for p in safe:
                proc = subprocess.Popen(
                    build_pytest_command(p, repeat, headed),
                    cwd=BASE_DIR,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    env=env
                )
                processes.append((p.name, proc))

            for name, proc in processes:
                for line in proc.stdout:
                    yield f"[{name}] {line}"
                proc.wait()
                yield f"[{name}] finished with exit code {proc.returncode}\n"
        else:
            for i, p in enumerate(safe, 1):
                yield f"▶️ Running {p.name} ({i}/{len(safe)})\n"
                proc = subprocess.Popen(
                    build_pytest_command(p, repeat, headed),
                    cwd=BASE_DIR,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    env=env
                )
                for line in proc.stdout:
                    yield line
                proc.wait()
                yield f"✅ {p.name} finished with exit code {proc.returncode}\n\n"

        yield "🎉 Run finished.\n"

    return Response(stream(), mimetype="text/plain")


@app.post("/reauth")
def reauth():
    if not session.get("authenticated"):
        return "Unauthorized", 401
    session["authenticated_at"] = time.time()
    return "OK"


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


if __name__ == "__main__":
    TESTS_DIR.mkdir(exist_ok=True)
    app.run(host="127.0.0.1", port=3000, debug=True)
