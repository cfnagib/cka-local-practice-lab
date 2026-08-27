#!/usr/bin/env python3
"""Local CKA practice window using a real VTE Linux terminal."""
import json
import pathlib
import subprocess
import threading
import time
import urllib.request
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("Vte", "2.91")
from gi.repository import Gdk, Gio, GLib, Gtk, Pango, Vte

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


class CkaPracticeApp:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip("/")
        self.question = 1
        self.started = False
        self.preparing = False
        self.started_at = None
        self.spawn_cancellable = None
        self.ssh_user = lab_value("SSH_USER", "cfnagib")
        self.base_ip = lab_value("BASE_IP", "192.168.122.40")
        self.build_window()

    def request(self, path, method="GET"):
        request = urllib.request.Request(self.base_url + path, method=method)
        with urllib.request.urlopen(request, timeout=180) as response:
            return json.loads(response.read())

    def build_window(self):
        GLib.set_prgname("cka-practice-lab")
        Gdk.set_program_class("CKAPracticeLab")
        self.window = Gtk.Window(title="CKA Practice Lab")
        self.window.connect("destroy", Gtk.main_quit)
        self.window.set_default_size(1500, 950)
        self.window.maximize()
        self.install_styles()
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
        self.tool_buttons = [self.start_button]
        for label, callback in [("Validate", self.validate), ("Hint", self.hint), ("Review", self.review), ("Report", self.report)]:
            button = Gtk.Button.new_with_label(label)
            button.connect("clicked", callback)
            tools.pack_start(button, False, False, 0)
            self.tool_buttons.append(button)
        self.timer = Gtk.Label(label="02:00:00")
        header.pack_end(self.timer, False, False, 0)

        split = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        split.set_position(650)
        outer.pack_start(split, True, True, 0)
        left_scroll = Gtk.ScrolledWindow()
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin=18)
        left_scroll.add(left)
        split.pack1(left_scroll, resize=False, shrink=False)
        self.title = Gtk.Label(xalign=0)
        self.title.set_use_markup(True)
        self.title.set_name("task-title")
        left.pack_start(self.title, False, False, 0)
        self.status = Gtk.Label(xalign=0)
        self.status.set_line_wrap(True)
        self.status.set_name("status-message")
        left.pack_start(self.status, False, False, 0)
        self.context = Gtk.Label(xalign=0, label="Context: base\nTask host: controlplane\nConnect with: ssh controlplane")
        left.pack_start(self.context, False, False, 0)
        self.video = Gtk.LinkButton.new_with_label("", "Watch video")
        left.pack_start(self.video, False, False, 0)
        self.task = Gtk.Label(xalign=0, yalign=0)
        self.task.set_line_wrap(True)
        self.task.set_selectable(True)
        self.task.set_name("task-text")
        left.pack_start(self.task, False, False, 0)

        terminal_scroll = Gtk.ScrolledWindow()
        self.terminal = Vte.Terminal()
        self.terminal.set_scrollback_lines(10000)
        self.terminal.set_font(Pango.FontDescription("Monospace 13"))
        self.terminal.connect("key-press-event", self.terminal_key_press)
        terminal_scroll.add(self.terminal)
        split.pack2(terminal_scroll, resize=True, shrink=False)
        self.load_question()
        GLib.timeout_add_seconds(1, self.update_timer)

    def install_styles(self):
        provider = Gtk.CssProvider()
        provider.load_from_data(b"""
            #task-title { font-size: 20px; font-weight: 700; }
            #status-message {
                background: #17324d;
                color: #f3f8ff;
                border-radius: 6px;
                font-size: 15px;
                font-weight: 700;
                padding: 10px;
            }
            #task-text { font-size: 15px; }
            button, combobox { font-size: 14px; padding: 5px; }
        """)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def terminal_key_press(self, _terminal, event):
        control = bool(event.state & Gdk.ModifierType.CONTROL_MASK)
        shift = bool(event.state & Gdk.ModifierType.SHIFT_MASK)
        key = Gdk.keyval_name(event.keyval)
        if control and shift and key in {"c", "C"}:
            self.terminal.copy_clipboard_format(Vte.Format.TEXT)
            return True
        if control and shift and key in {"v", "V"}:
            self.terminal.paste_clipboard()
            return True
        if shift and key in {"Left", "Right", "Up", "Down"}:
            # Bash/readline does not provide graphical Shift+Arrow selection.
            # Some terminal stacks leak the final A/B/C/D byte of the modified
            # escape sequence. Send the corresponding normal arrow instead.
            arrows = {
                "Left": b"\x1b[D",
                "Right": b"\x1b[C",
                "Up": b"\x1b[A",
                "Down": b"\x1b[B",
            }
            self.terminal.feed_child(arrows[key])
            return True
        return False

    def update_timer(self):
        remaining = 7200
        if self.started_at is not None:
            remaining = max(0, 7200 - int(time.monotonic() - self.started_at))
        hours, remainder = divmod(remaining, 3600)
        minutes, seconds = divmod(remainder, 60)
        self.timer.set_text(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
        return True

    def set_preparing_controls(self, preparing):
        self.previous_button.set_sensitive(not preparing and self.question > 1)
        self.next_button.set_sensitive(not preparing and self.question < 17)
        self.question_picker.set_sensitive(not preparing)
        for button in self.tool_buttons:
            button.set_sensitive(not preparing)

    def run(self):
        self.window.show_all()
        self.window.present()
        Gtk.main()

    def load_question(self):
        try:
            data = self.request(f"/api/question/{self.question}")
        except Exception as error:
            self.status.set_text(f"Could not load this task: {error}")
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
        self.set_preparing_controls(True)
        self.status.set_text("Preparing environment. The task button is locked while the VMs reset; this usually takes 30–90 seconds.")
        self.terminal.reset(True, True)
        self.terminal.feed(b"Preparing task environment...\r\nPlease wait while the lab is reset.\r\n")
        threading.Thread(target=self.prepare_worker, daemon=True).start()

    def prepare_worker(self):
        try:
            result = self.request(f"/api/start/{self.question}", "POST")
        except Exception as error:
            result = {"ok": False, "output": str(error)}
        GLib.idle_add(self.finish_prepare, result)

    def finish_prepare(self, result):
        self.preparing = False
        self.set_preparing_controls(False)
        if not result.get("ok"):
            self.status.set_text("Preparation failed. Try again.")
            self.terminal.feed(((result.get("output") or "Unknown error") + "\r\n").encode())
            return False
        try:
            self.status.set_text("Environment is ready. Opening the terminal session...")
            argv = ["ssh", "-tt", "-o", "LogLevel=ERROR", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null", f"{self.ssh_user}@{self.base_ip}", "bash -i"]
            self.spawn_cancellable = Gio.Cancellable()
            # Use named arguments. The VTE typelib on Ubuntu 26.04 exposes an
            # ambiguous positional signature and otherwise shifts cancellable
            # into the timeout slot.
            self.terminal.spawn_async(
                pty_flags=Vte.PtyFlags.DEFAULT,
                working_directory=str(pathlib.Path.home()),
                argv=argv,
                envv=None,
                spawn_flags=GLib.SpawnFlags.DEFAULT,
                child_setup=None,
                timeout=-1,
                cancellable=self.spawn_cancellable,
                callback=self.terminal_started,
                user_data=self,
            )
        except Exception as error:
            self.status.set_text(f"Environment is ready, but the terminal could not start: {error}")
            self.terminal.feed((f"Terminal startup error: {error}\r\n").encode())
        return False

    def terminal_started(self, _terminal, _pid, error, _data):
        if error:
            self.status.set_text(f"Environment is ready, but the terminal could not start: {error}")
            self.terminal.feed((f"Terminal startup error: {error}\r\n").encode())
            return
        self.started = True
        self.started_at = time.monotonic()
        self.start_button.set_label("Reset Task")
        self.status.set_text("Connected to base. Read the task, then ssh to the designated host. Use Validate after you finish.")
        self.terminal.grab_focus()

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
        self.terminal.feed(("\r\n" + output.replace("\n", "\r\n") + "\r\n").encode())
        self.status.set_text("Passed — this question is recorded as solved." if result.get("ok") else "Not passed yet. Review the validator output in the terminal.")
        return False

    def hint(self, *_):
        if not self.started:
            return
        try:
            data = self.request(f"/api/hint/{self.question}/1")
            self.terminal.feed(("\r\nHint:\r\n" + data.get("hint", "") + "\r\n").encode())
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
    CkaPracticeApp("http://127.0.0.1:8790").run()
