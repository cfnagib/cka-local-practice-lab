#!/usr/bin/env python3
"""Dedicated CKA dashboard window with Linux-terminal clipboard shortcuts."""
import json
import sys

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import Gdk, Gtk, WebKit2


class CkaPracticeApp(Gtk.Application):
    def __init__(self, url):
        super().__init__(application_id="org.cfnagib.CkaLocalPractice")
        self.url = url

    def do_activate(self):
        window = self.props.active_window
        if window:
            window.present()
            return
        window = Gtk.ApplicationWindow(application=self, title="CKA Practice Lab")
        window.set_default_size(1500, 950)
        manager = WebKit2.UserContentManager()
        manager.register_script_message_handler("ckaClipboard")
        manager.connect("script-message-received::ckaClipboard", self.on_clipboard_message)
        self.webview = WebKit2.WebView.new_with_user_content_manager(manager)
        self.webview.get_settings().set_enable_developer_extras(False)
        window.add(self.webview)
        window.show_all()
        self.webview.load_uri(self.url)

    def on_clipboard_message(self, _manager, result):
        try:
            payload = json.loads(result.get_js_value().to_string())
        except (TypeError, ValueError):
            return
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        if payload.get("action") == "copy":
            clipboard.set_text(str(payload.get("value", "")), -1)
            clipboard.store()
        elif payload.get("action") == "paste":
            clipboard.request_text(self.on_clipboard_text)

    def on_clipboard_text(self, _clipboard, text, _data=None):
        self.webview.run_javascript(
            "window.__ckaClipboardPaste(%s);" % json.dumps(text or ""),
            None, None, None,
        )


if __name__ == "__main__":
    CkaPracticeApp(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8790").run(sys.argv)
