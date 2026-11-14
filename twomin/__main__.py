"""Entry point + single-instance handling.

How it fits together:
  * The first process to start becomes the *instance*: it owns the tray and any running timer.
  * The hotkey launches a fresh process. If an instance exists, that new process shows the
    popup itself (new processes get keyboard focus reliably on GNOME), then hands the
    chosen task to the instance and exits.
  * If a timer is already running, the hotkey just brings it forward.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tomllib
from pathlib import Path

SERVER = f"twomin-{os.getuid()}"
CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "twomin" / "config.toml"


def _prefer_xwayland() -> None:
    # GNOME Wayland ignores "always on top" from native Wayland apps; XWayland honours it.
    if (os.environ.get("XDG_SESSION_TYPE") == "wayland"
            and "QT_QPA_PLATFORM" not in os.environ
            and not os.environ.get("TWOMIN_NATIVE_WAYLAND")):
        os.environ["QT_QPA_PLATFORM"] = "xcb"


def _load_config() -> dict:
    try:
        return tomllib.loads(CONFIG.read_text())
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def _request(msg: dict, timeout: int = 1000) -> dict | None:
    from PySide6.QtNetwork import QLocalSocket
    sock = QLocalSocket()
    sock.connectToServer(SERVER)
    if not sock.waitForConnected(300):
        return None
    sock.write((json.dumps(msg) + "\n").encode())
    sock.waitForBytesWritten(timeout)
    if not sock.waitForReadyRead(timeout):
        return None
    try:
        return json.loads(bytes(sock.readAll()).decode() or "{}")
    finally:
        sock.disconnectFromServer()


def _serve(ctrl, app):
    from PySide6.QtNetwork import QLocalServer
    QLocalServer.removeServer(SERVER)  # clear a stale socket from a crash
    server = QLocalServer(app)
    server.setSocketOptions(QLocalServer.UserAccessOption)

    def handle(sock):
        try:
            msg = json.loads(bytes(sock.readLine()).decode())
        except ValueError:
            msg = {}
        cmd, reply = msg.get("cmd"), {"ok": True}
        if cmd == "status":
            reply["busy"] = ctrl.busy
            reply["at_work"] = ctrl.at_work
        elif cmd == "set_work":
            ctrl.set_at_work(bool(msg.get("value")))
        elif cmd == "raise" and ctrl.busy:
            ctrl.mini.bring_forward()
        elif cmd == "start":
            ctrl.start(msg["task_id"], msg["title"], msg["steps"])
        elif cmd == "show":
            ctrl.show_popup()
        elif cmd == "quit":
            app.quit()
        sock.write((json.dumps(reply) + "\n").encode())
        sock.flush()
        sock.disconnectFromServer()

    def on_conn():
        sock = server.nextPendingConnection()
        sock.readyRead.connect(lambda: sock.canReadLine() and handle(sock))

    server.newConnection.connect(on_conn)
    server.listen(SERVER)
    return server


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="twomin", description="Two-minute start timer")
    ap.add_argument("--tray", action="store_true", help="start hidden (use at login)")
    ap.add_argument("--quit", action="store_true", help="stop the running instance")
    ap.add_argument("--seconds", type=int, help="timer length (default 120)")
    args = ap.parse_args(argv)

    _prefer_xwayland()
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from . import notify
    from .app import Controller
    from .core.store import Store
    from .ui.style import QSS, load_fonts

    app = QApplication(sys.argv[:1])
    app.setApplicationName("twomin")
    app.setDesktopFileName("twomin")
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(QIcon(str(notify.ICON)))
    load_fonts()
    app.setStyleSheet(QSS)
    seconds = args.seconds or int(_load_config().get("seconds", 120))

    status = _request({"cmd": "status"})

    if args.quit:
        if status is not None:
            _request({"cmd": "quit"})
        return 0

    if status is not None:                       # an instance is already running
        if args.tray:
            return 0
        if status.get("busy"):
            _request({"cmd": "raise"})
            return 0
        # Client mode: show the popup here, hand the result to the instance.
        ctrl = Controller(app, Store(), seconds, tray=False)
        ctrl.at_work = bool(status.get("at_work"))       # the instance holds the truth
        ctrl.sync_work = lambda v: _request({"cmd": "set_work", "value": v})

        def hand_off(task_id, title, steps):
            if _request({"cmd": "start", "task_id": task_id, "title": title, "steps": steps}) is None:
                ctrl.start(task_id, title, steps)   # instance vanished: run it ourselves
                return
            app.quit()

        ctrl.show_popup(on_start=hand_off)
        return app.exec()

    # No instance: become it.
    store = Store()
    store.close_orphans()          # timers lost to a crash/logout: still starts, now ended
    ctrl = Controller(app, store, seconds, tray=True, resident=args.tray)
    server = _serve(ctrl, app)  # noqa: F841 (keep a reference)
    if not args.tray:
        ctrl.show_popup()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
