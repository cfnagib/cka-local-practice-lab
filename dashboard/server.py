#!/usr/bin/env python3
import asyncio, json, os, pathlib, pty, re, shlex, subprocess, threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
import websockets

ROOT = pathlib.Path(__file__).resolve().parents[1]
LAB = ROOT / "lab"
QUESTION_ROOT = ROOT / "CKA-PREP"
PORT = int(os.environ.get("CKA_DASHBOARD_PORT", "8790"))
WS_PORT = int(os.environ.get("CKA_TERMINAL_PORT", "8791"))
QPA_WARNING = re.compile(r"qt\.qpa\.services:.*?(?:\n.*?/root\"\)\n?)?", re.DOTALL)
START_LOCK = threading.Lock()

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
CONTROL_IP = lab_config("CONTROL_IP", "192.168.122.63")

def run_lab_script(name, *args):
    command = shlex.join([str(LAB / "scripts" / name), *args])
    return subprocess.run(["sg", "libvirt", "-c", command], cwd=LAB, text=True, capture_output=True)

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
    return {"number": n, "title": title, "text": "\n".join(body).strip(), "video_url": video_url}

def question_file(n):
    d = QUESTION_ROOT / f"Question-{n}"
    return next((d / x for x in ("Questions.bash", "Question.bash") if (d / x).exists()), None)

class Handler(SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path.startswith("/api/start/"):
            n = self.path.rsplit("/", 1)[-1]
            if not START_LOCK.acquire(blocking=False):
                body = json.dumps({"ok": False, "output": "Another question is still being prepared. Please wait."}).encode()
                self.send_response(409); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(body); return
            try:
                result = run_lab_script("reset-question.sh")
                if result.returncode == 0:
                    result = run_lab_script("run-question.sh", n)
                body = json.dumps({"ok": result.returncode == 0, "output": result.stdout + result.stderr}).encode()
            finally:
                START_LOCK.release()
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(body); return
        self.send_error(404)
    def do_GET(self):
        if self.path.startswith("/api/question/"):
            n = self.path.rsplit("/", 1)[-1]
            data = parse_question(n)
            if data:
                body = json.dumps(data).encode()
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(body); return
        return super().do_GET()
    def log_message(self, *_): pass

async def terminal(ws):
    master, slave = pty.openpty()
    proc = subprocess.Popen(["ssh", "-tt", "-o", "LogLevel=ERROR", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null", f"{SSH_USER}@{CONTROL_IP}", "bash -i"], stdin=slave, stdout=slave, stderr=slave, env={**os.environ, "TERM": "xterm-256color", "QT_QPA_PLATFORM": "offscreen"})
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
    async with websockets.serve(terminal, "127.0.0.1", WS_PORT):
        print(f"Dashboard: http://127.0.0.1:{PORT}")
        await asyncio.Future()

if __name__ == "__main__":
    os.chdir(pathlib.Path(__file__).parent / "static")
    http = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    threading.Thread(target=http.serve_forever, daemon=True).start()
    asyncio.run(main())
