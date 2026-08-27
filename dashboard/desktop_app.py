#!/usr/bin/env python3
"""Local CKA practice window using a real VTE Linux terminal."""
import json
import pathlib
import subprocess
import threading
import urllib.request
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Vte", "2.91")
from gi.repository import GLib, Gtk, Vte

ROOT = pathlib.Path(__file__).resolve().parents[1]


def lab_value(name, fallback):
    config = ROOT / "lab" / "config.env"
    if not config.exists():
        return fallback
    value = subprocess.run(
        ["bash", "-c", 'source "$1"; printf "%s" "${!2}"', "bash", str(config), name],
        text=True, capture_output=True,
    ).stdout
    return value or fallback


class CkaPracticeApp(Gtk.Application):
    def __init__(self, base_url):
        # Do not register a single-instance DBus application. KDE can retain a
        # stale activation target after a window is closed, causing a later
        # taskbar click to exit without showing a window.
        super().__init__()
        self.base_url = base_url.rstrip("/")
        self.question = 1
        self.started = False
        self.preparing = False
        self.ssh_user = lab_value("SSH_USER", "cfnagib")
        self.base_ip = lab_value("BASE_IP", "192.168.122.40")

    def request(self, path, method="GET"):
        request = urllib.request.Request(self.base_url + path, method=method)
        with urllib.request.urlopen(request, timeout=180) as response:
            return json.loads(response.read())

    def do_activate(self):
        if self.props.active_window:
            self.props.active_window.present()
            return
        self.window = Gtk.ApplicationWindow(application=self, title="CKA Practice Lab")
        self.window.set_wmclass("cka-practice-lab", "CKA Practice Lab")
        self.window.set_default_size(1500, 950)
        self.window.maximize()
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.window.add(outer)

        header = Gtk.Box(spacing=10, margin=10)
        outer.pack_start(header, False, False, 0)
        header.pack_start(Gtk.Label(label="<b>CKA Practice Lab</b>", use_markup=True), False, False, 0)
        self.previous_button = Gtk.Button.new_with_label("← Previous")
        self.previous_button.connect("clicked", lambda *_: self.change_question(-1))
        header.pack_start(self.previous_button, False, False, 0)
        self.question_picker = Gtk.ComboBoxText()
        for number in range(1, 18):
            self.question_picker.append_text(f"Question {number}")
        self.question_picker.set_active(0)
        self.question_picker.connect("changed", self.pick_question)
        header.pack_start(self.question_picker, False, False, 0)
        self.next_button = Gtk.Button.new_with_label("Next →")
        self.next_button.connect("clicked", lambda *_: self.change_question(1))
        header.pack_start(self.next_button, False, False, 0)
        training = Gtk.Frame(label=" Training tools ")
        tools = Gtk.Box(spacing=6, margin=5)
        training.add(tools)
        header.pack_start(training, False, False, 0)
        self.start_button = Gtk.Button.new_with_label("Start Task")
        self.start_button.connect("clicked", self.start_task)
        tools.pack_start(self.start_button, False, False, 0)
        for label, callback in [("Validate", self.validate), ("Hint", self.hint), ("Review", self.review), ("Report", self.report)]:
            button = Gtk.Button.new_with_label(label)
            button.connect("clicked", callback)
            tools.pack_start(button, False, False, 0)
        self.timer = Gtk.Label(label="02:00:00")
        header.pack_end(self.timer, False, False, 0)

        split = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        split.set_position(500)
        outer.pack_start(split, True, True, 0)
        left_scroll = Gtk.ScrolledWindow()
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin=18)
        left_scroll.add(left)
        split.pack1(left_scroll, resize=False, shrink=False)
        self.title = Gtk.Label(xalign=0)
        self.title.set_use_markup(True)
        left.pack_start(self.title, False, False, 0)
        self.status = Gtk.Label(xalign=0)
        self.status.set_line_wrap(True)
        left.pack_start(self.status, False, False, 0)
        self.context = Gtk.Label(xalign=0, label="Context: base\nTask host: controlplane\nConnect with: ssh controlplane")
        left.pack_start(self.context, False, False, 0)
        self.video = Gtk.LinkButton.new_with_label("", "Watch video")
        left.pack_start(self.video, False, False, 0)
        self.task = Gtk.Label(xalign=0, yalign=0)
        self.task.set_line_wrap(True)
        self.task.set_selectable(True)
        left.pack_start(self.task, False, False, 0)

        terminal_scroll = Gtk.ScrolledWindow()
        self.terminal = Vte.Terminal()
        self.terminal.set_scrollback_lines(10000)
        self.terminal.set_font_scale(1.1)
        terminal_scroll.add(self.terminal)
        split.pack2(terminal_scroll, resize=True, shrink=False)
        self.load_question()
        self.window.show_all()

    def load_question(self):
        try:
            data = self.request(f"/api/question/{self.question}")
        except Exception:
            return
        self.title.set_markup(f"<b>{GLib.markup_escape_text(data['title'])}</b>")
        self.status.set_text("Press Start Task to prepare this task.")
        self.task.set_text(data["text"])
        self.video.set_uri(data.get("video_url") or "")
        self.video.set_visible(bool(data.get("video_url")))
        self.previous_button.set_sensitive(self.question > 1)
        self.next_button.set_sensitive(self.question < 17)

    def pick_question(self, _picker):
        selected = self.question_picker.get_active()
        if selected >= 0 and selected + 1 != self.question:
            self.question = selected + 1
            self.started = False
            self.start_button.set_label("Start Task")
            self.load_question()

    def change_question(self, delta):
        self.question = max(1, min(17, self.question + delta))
        self.question_picker.set_active(self.question - 1)

    def start_task(self, *_):
        if self.preparing:
            return
        self.preparing = True
        self.start_button.set_sensitive(False)
        self.status.set_text("Preparing environment — keyboard is locked. This usually takes 30–90 seconds.")
        self.terminal.reset(True, True)
        self.terminal.feed("Preparing task environment…\r\n")
        threading.Thread(target=self.prepare_worker, daemon=True).start()

    def prepare_worker(self):
        try:
            result = self.request(f"/api/start/{self.question}", "POST")
        except Exception as error:
            result = {"ok": False, "output": str(error)}
        GLib.idle_add(self.finish_prepare, result)

    def finish_prepare(self, result):
        self.preparing = False
        self.start_button.set_sensitive(True)
        if not result.get("ok"):
            self.status.set_text("Preparation failed. Try again.")
            self.terminal.feed((result.get("output") or "Unknown error") + "\r\n")
            return False
        self.started = True
        self.start_button.set_label("Reset Task")
        self.status.set_text("Connected to base. Read the task, then ssh to the designated host. Use Validate after you finish.")
        argv = ["ssh", "-tt", "-o", "LogLevel=ERROR", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null", f"{self.ssh_user}@{self.base_ip}", "bash -i"]
        self.terminal.spawn_async(Vte.PtyFlags.DEFAULT, str(pathlib.Path.home()), argv, None,
                                  GLib.SpawnFlags.DEFAULT, None, -1, None, None, None)
        self.terminal.grab_focus()
        return False

    def validate(self, *_):
        if self.started:
            threading.Thread(target=self.validation_worker, daemon=True).start()

    def validation_worker(self):
        try:
            result = self.request(f"/api/validate/{self.question}", "POST")
        except Exception as error:
            result = {"ok": False, "output": str(error)}
        GLib.idle_add(self.show_validation, result)

    def show_validation(self, result):
        output = result.get("output", "")
        self.terminal.feed("\r\n" + output.replace("\n", "\r\n") + "\r\n")
        self.status.set_text("Passed — this question is recorded as solved." if result.get("ok") else "Not passed yet. Review the validator output in the terminal.")
        return False

    def hint(self, *_):
        if not self.started:
            return
        try:
            data = self.request(f"/api/hint/{self.question}/1")
            self.terminal.feed("\r\nHint:\r\n" + data.get("hint", "") + "\r\n")
        except Exception:
            pass

    def review(self, *_):
        try:
            text = json.dumps(self.request(f"/api/review/{self.question}"), indent=2)
        except Exception as error:
            text = str(error)
        self.show_text("Question review", text)

    def report(self, *_):
        try:
            text = json.dumps(self.request("/api/progress"), indent=2)
        except Exception as error:
            text = str(error)
        self.show_text("Practice report", text)

    def show_text(self, title, text):
        dialog = Gtk.Dialog(title=title, transient_for=self.window, modal=True)
        view = Gtk.TextView(editable=False, monospace=True)
        view.get_buffer().set_text(text)
        scroll = Gtk.ScrolledWindow()
        scroll.set_size_request(750, 500)
        scroll.add(view)
        dialog.get_content_area().add(scroll)
        dialog.add_button("Close", Gtk.ResponseType.CLOSE)
        dialog.show_all()
        dialog.run()
        dialog.destroy()


if __name__ == "__main__":
    CkaPracticeApp("http://127.0.0.1:8790").run([])
