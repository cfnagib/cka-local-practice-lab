#!/usr/bin/env python3
import asyncio, json, os, pathlib, pty, re, shlex, shutil, subprocess, threading, time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
import websockets

ROOT = pathlib.Path(__file__).resolve().parents[1]
LAB = ROOT / "lab"
QUESTION_ROOT = ROOT / "CKA-PREP"
PORT = int(os.environ.get("CKA_DASHBOARD_PORT", "8790"))
WS_PORT = int(os.environ.get("CKA_TERMINAL_PORT", "8791"))
TAILSCALE_IP = os.environ.get("CKA_TAILSCALE_IP", "").strip()
LISTEN_HOSTS = ["127.0.0.1"] + ([TAILSCALE_IP] if TAILSCALE_IP else [])
STATE_DIR = pathlib.Path(os.environ.get("XDG_STATE_HOME", pathlib.Path.home() / ".local/state")) / "cka-local-practice"
STATE_FILE = STATE_DIR / "progress.json"
QPA_WARNING = re.compile(r"qt\.qpa\.services:.*?(?:\n.*?/root\"\)\n?)?", re.DOTALL)
START_LOCK = threading.Lock()
STATE_LOCK = threading.Lock()

def lab_config(key, fallback):
    config = LAB / "config.env"
    if not config.exists():
        return fallback
    result = subprocess.run(
        ["bash", "-c", 'source "$1"; printf "%s" "${!2}"', "bash", str(config), key],
        text=True,
        capture_output=True,
    )
    return result.stdout or fallback

SSH_USER = lab_config("SSH_USER", os.environ.get("USER", "cfnagib"))
BASE_IP = lab_config("BASE_IP", "192.168.122.40")
CONTROL_IP = lab_config("CONTROL_IP", "192.168.122.63")

def launch_native_exam_terminal():
    """Open a real Linux terminal for local sessions.

    Chromium reserves Ctrl+Shift+C for Inspect Element, so its embedded terminal
    cannot faithfully train the CKA terminal clipboard shortcuts. Konsole can.
    """
    konsole = shutil.which("konsole")
    display = os.environ.get("DISPLAY")
    if not konsole or not display:
        return False
    env = os.environ.copy()
    env.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    command = [
        konsole, "--title", "CKA Exam Terminal", "-e",
        "ssh", "-tt", "-o", "LogLevel=ERROR", "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null", f"{SSH_USER}@{BASE_IP}", "bash -i",
    ]
    try:
        subprocess.Popen(command, env=env, start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except OSError:
        return False

def run_lab_script(name, *args):
    command = shlex.join([str(LAB / "scripts" / name), *args])
    return subprocess.run(["sg", "libvirt", "-c", command], cwd=LAB, text=True, capture_output=True)

def valid_question(n):
    return n.isdigit() and 1 <= int(n) <= 17 and question_file(int(n)) is not None

def load_progress():
    with STATE_LOCK:
        try:
            return json.loads(STATE_FILE.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            return {"questions": {}, "active": {}}

def save_progress(progress):
    with STATE_LOCK:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        temp = STATE_FILE.with_suffix(".tmp")
        temp.write_text(json.dumps(progress, indent=2, sort_keys=True))
        temp.replace(STATE_FILE)

def begin_attempt(n):
    progress = load_progress()
    key = str(n)
    record = progress["questions"].setdefault(key, {"attempts": 0, "solved": False, "events": []})
    record["attempts"] += 1
    progress["active"] = {"question": n, "started_at": int(time.time())}
    save_progress(progress)

def record_command(n, command):
    command = command.strip()
    if not command or len(command) > 4000:
        return
    progress = load_progress()
    record = progress["questions"].setdefault(str(n), {"attempts": 0, "solved": False, "events": []})
    events = record.setdefault("events", [])
    events.append({"type": "command", "at": int(time.time()), "command": command})
    record["events"] = events[-500:]
    save_progress(progress)

def finish_validation(n, passed, output):
    progress = load_progress()
    key = str(n)
    record = progress["questions"].setdefault(key, {"attempts": 0, "solved": False, "events": []})
    active = progress.get("active", {})
    elapsed = max(0, int(time.time()) - int(active.get("started_at", time.time()))) if active.get("question") == n else None
    record["last_validation_passed"] = passed
    if elapsed is not None:
        record["last_time_seconds"] = elapsed
    if passed:
        record["solved"] = True
        record["solved_at"] = int(time.time())
        if elapsed is not None:
            best = record.get("best_time_seconds")
            record["best_time_seconds"] = elapsed if best is None else min(best, elapsed)
    events = record.setdefault("events", [])
    events.append({"type": "validation", "at": int(time.time()), "passed": passed, "output": output[-12000:]})
    record["events"] = events[-500:]
    save_progress(progress)
    return progress

def question_hint(n, level):
    notes = QUESTION_ROOT / f"Question-{n}" / "SolutionNotes.bash"
    if not notes.exists():
        return "No hint is available for this question. Use the relevant command help and official documentation."
    lines = [line.removeprefix("#").strip() for line in notes.read_text(errors="replace").splitlines()]
    lines = [line for line in lines if line and not line.startswith("!")]
    if not lines:
        return "No hint is available for this question. Use the relevant command help and official documentation."
    chunk = 3
    start = max(0, (level - 1) * chunk)
    selection = lines[start:start + chunk]
    return "\n".join(selection) if selection else "No further hints are available."

def run_validation(n):
    remote = f"bash /tmp/cka-question-{n}/validate.sh"
    return subprocess.run([
        "ssh", "-o", "ConnectTimeout=10", "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null", f"{SSH_USER}@{CONTROL_IP}", remote,
    ], text=True, capture_output=True, timeout=90)

def parse_question(n):
    f = question_file(n)
    if not f:
        return None
    lines = f.read_text(errors="replace").splitlines()
    title = f"Question {n}"
    body = []
    video_url = None
    for raw in lines:
        line = raw.removeprefix("#").lstrip()
        if raw.startswith("# Question "):
            title = f"Question {n} · {line.removeprefix('Question ')}"
        elif line in {"Task", "Video link"}:
            continue
        elif line.startswith("https://youtu.be/"):
            video_url = line
        else:
            body.append(line)
    return {"number": n, "title": title, "text": "\n".join(body).strip(), "video_url": video_url, "target_host": "controlplane"}

def question_file(n):
    d = QUESTION_ROOT / f"Question-{n}"
    return next((d / x for x in ("Questions.bash", "Question.bash") if (d / x).exists()), None)

class Handler(SimpleHTTPRequestHandler):
    def respond_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path.startswith("/api/start/"):
            n = self.path.rsplit("/", 1)[-1]
            if not valid_question(n):
                return self.respond_json({"ok": False, "output": "Question not found."}, 404)
            if not START_LOCK.acquire(blocking=False):
                return self.respond_json({"ok": False, "output": "Another question is still being prepared. Please wait."}, 409)
            try:
                result = run_lab_script("reset-question.sh")
                if result.returncode == 0:
                    result = run_lab_script("run-question.sh", n)
                if result.returncode == 0:
                    begin_attempt(int(n))
                is_local_dashboard = self.client_address[0] in {"127.0.0.1", "::1"}
                native_terminal = result.returncode == 0 and is_local_dashboard and launch_native_exam_terminal()
                response = {"ok": result.returncode == 0, "output": result.stdout + result.stderr,
                            "native_terminal": native_terminal}
            finally:
                START_LOCK.release()
            return self.respond_json(response)
        if self.path.startswith("/api/validate/"):
            n = self.path.rsplit("/", 1)[-1]
            if not valid_question(n):
                return self.respond_json({"ok": False, "output": "Question not found."}, 404)
            try:
                result = run_validation(int(n))
                output = result.stdout + result.stderr
                if result.returncode == 255 and "ssh:" in output:
                    return self.respond_json({"ok": False, "environment_error": True, "output": "The practice VM is unavailable. Reset the question and try again."})
                passed = result.returncode == 0
                progress = finish_validation(int(n), passed, output)
                return self.respond_json({"ok": passed, "output": output, "progress": progress})
            except subprocess.TimeoutExpired:
                return self.respond_json({"ok": False, "output": "Validation timed out. Reset the question and try again."})
        if self.path.startswith("/api/activity/"):
            n = self.path.rsplit("/", 1)[-1]
            if not valid_question(n):
                return self.respond_json({"ok": False, "output": "Question not found."}, 404)
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length) or b"{}")
                record_command(int(n), str(payload.get("command", "")))
                return self.respond_json({"ok": True})
            except (ValueError, json.JSONDecodeError):
                return self.respond_json({"ok": False, "output": "Invalid activity data."}, 400)
        self.send_error(404)
    def do_GET(self):
        if self.path.startswith("/api/question/"):
            n = self.path.rsplit("/", 1)[-1]
            data = parse_question(n)
            if data:
                return self.respond_json(data)
        if self.path == "/api/progress":
            return self.respond_json(load_progress())
        if self.path.startswith("/api/review/"):
            n = self.path.rsplit("/", 1)[-1]
            if valid_question(n):
                return self.respond_json(load_progress().get("questions", {}).get(n, {"attempts": 0, "solved": False, "events": []}))
        if self.path.startswith("/api/hint/"):
            parts = self.path.strip("/").split("/")
            if len(parts) == 4 and valid_question(parts[2]) and parts[3].isdigit():
                return self.respond_json({"hint": question_hint(int(parts[2]), max(1, int(parts[3])) )})
        return super().do_GET()
    def log_message(self, *_): pass

async def terminal(ws):
    master, slave = pty.openpty()
    proc = subprocess.Popen(["ssh", "-tt", "-o", "LogLevel=ERROR", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null", f"{SSH_USER}@{BASE_IP}", "bash -i"], stdin=slave, stdout=slave, stderr=slave, env={**os.environ, "TERM": "xterm-256color", "QT_QPA_PLATFORM": "offscreen"})
    os.close(slave)
    loop = asyncio.get_running_loop()
    async def reader():
        while proc.poll() is None:
            try:
                data = await loop.run_in_executor(None, os.read, master, 4096)
                if data:
                    clean = QPA_WARNING.sub("", data.decode(errors="replace"))
                    if clean: await ws.send(clean)
            except (OSError, websockets.exceptions.ConnectionClosed): break
    task = asyncio.create_task(reader())
    try:
        async for msg in ws:
            if isinstance(msg, str): os.write(master, msg.encode())
    finally:
        task.cancel(); proc.terminate(); os.close(master)
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()

async def main():
    websocket_servers = [await websockets.serve(terminal, host, WS_PORT) for host in LISTEN_HOSTS]
    for host in LISTEN_HOSTS:
        print(f"Dashboard: http://{host}:{PORT}")
    try:
        await asyncio.Future()
    finally:
        for server in websocket_servers:
            server.close()
            await server.wait_closed()

if __name__ == "__main__":
    os.chdir(pathlib.Path(__file__).parent / "static")
    for host in LISTEN_HOSTS:
        http = ThreadingHTTPServer((host, PORT), Handler)
        threading.Thread(target=http.serve_forever, daemon=True).start()
    asyncio.run(main())
