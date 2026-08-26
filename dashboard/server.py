#!/usr/bin/env python3
import asyncio, json, os, pathlib, pty, subprocess, threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
import websockets

ROOT = pathlib.Path(__file__).resolve().parents[1]
LAB = ROOT / "lab"
QUESTION_ROOT = ROOT / "CKA-PREP"
PORT = int(os.environ.get("CKA_DASHBOARD_PORT", "8790"))
WS_PORT = int(os.environ.get("CKA_TERMINAL_PORT", "8791"))

def question_file(n):
    d = QUESTION_ROOT / f"Question-{n}"
    return next((d / x for x in ("Questions.bash", "Question.bash") if (d / x).exists()), None)

class Handler(SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path.startswith("/api/start/"):
            n = self.path.rsplit("/", 1)[-1]
            result = subprocess.run([str(LAB / "scripts" / "reset-question.sh")], cwd=LAB, text=True, capture_output=True)
            if result.returncode == 0:
                result = subprocess.run([str(LAB / "scripts" / "run-question.sh"), n], cwd=LAB, text=True, capture_output=True)
            body = json.dumps({"ok": result.returncode == 0, "output": result.stdout + result.stderr}).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(body); return
        self.send_error(404)
    def do_GET(self):
        if self.path.startswith("/api/question/"):
            n = self.path.rsplit("/", 1)[-1]
            f = question_file(n)
            if f:
                data = {"number": n, "text": f.read_text(errors="replace")}
                body = json.dumps(data).encode()
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(body); return
        return super().do_GET()
    def log_message(self, *_): pass

async def terminal(ws):
    master, slave = pty.openpty()
    proc = subprocess.Popen(["ssh", "-tt", "-o", "LogLevel=ERROR", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null", "cfnagib@192.168.122.63", "bash -i"], stdin=slave, stdout=slave, stderr=slave, env={**os.environ, "TERM": "xterm-256color", "QT_QPA_PLATFORM": "offscreen"})
    os.close(slave)
    loop = asyncio.get_running_loop()
    async def reader():
        while proc.poll() is None:
            try:
                data = await loop.run_in_executor(None, os.read, master, 4096)
                if data: await ws.send(data.decode(errors="replace"))
            except (OSError, websockets.exceptions.ConnectionClosed): break
    task = asyncio.create_task(reader())
    try:
        async for msg in ws:
            if isinstance(msg, str): os.write(master, msg.encode())
    finally:
        task.cancel(); proc.terminate(); os.close(master)

async def main():
    async with websockets.serve(terminal, "127.0.0.1", WS_PORT):
        print(f"Dashboard: http://127.0.0.1:{PORT}")
        await asyncio.Future()

if __name__ == "__main__":
    os.chdir(pathlib.Path(__file__).parent / "static")
    http = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    threading.Thread(target=http.serve_forever, daemon=True).start()
    asyncio.run(main())
