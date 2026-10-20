"""Small dialogs for the tray version (tkinter ships with Python)."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_LOGGER = logging.getLogger(__name__)

_ICONS = Path(__file__).resolve().parent / "static" / "icons" / "default"


def _set_icon(root) -> None:
    """The AirMan note in the title bar (and the taskbar on Windows)."""
    try:
        import tkinter

        image = tkinter.PhotoImage(master=root, file=str(_ICONS / "icon-192.png"))
        root.iconphoto(True, image)
        root._airman_icon = image  # keep a reference, or Tk drops the picture
        if sys.platform == "win32":
            root.iconbitmap(default=str(_ICONS / "favicon.ico"))
    except Exception:  # noqa: BLE001 - an icon is nice to have, never required
        _LOGGER.debug("Could not set the window icon", exc_info=True)

MIN_PASSWORD = 8


def _root():
    import tkinter

    root = tkinter.Tk()
    _set_icon(root)
    root.withdraw()
    root.attributes("-topmost", True)
    return root


def show_info(title: str, message: str, secret: bool = False) -> bool:
    """Show a message; returns False if no window could be shown.

    secret=True: the message contains a password and is never logged.
    """
    try:
        from tkinter import messagebox

        root = _root()
        messagebox.showinfo(title, message, parent=root)
        root.destroy()
        return True
    except Exception:  # noqa: BLE001 - no display, no tkinter: log instead
        if secret:
            _LOGGER.warning("%s: could not show a window (message not logged)", title)
        else:
            _LOGGER.info("%s: %s", title, message)
        return False


def show_error(title: str, message: str) -> None:
    try:
        from tkinter import messagebox

        root = _root()
        messagebox.showerror(title, message, parent=root)
        root.destroy()
    except Exception:  # noqa: BLE001
        _LOGGER.error("%s: %s", title, message)


def ask_new_password(title: str = "AirMan") -> str | None:
    """Ask for a new web password twice. None if cancelled or no GUI available."""
    try:
        from tkinter import messagebox, simpledialog
    except ImportError:
        return None
    root = _root()
    try:
        while True:
            first = simpledialog.askstring(
                title, f"New web password (at least {MIN_PASSWORD} characters):",
                show="•", parent=root)
            if first is None:
                return None
            if len(first) < MIN_PASSWORD:
                messagebox.showwarning(title, "Too short.", parent=root)
                continue
            second = simpledialog.askstring(title, "Repeat the password:", show="•",
                                            parent=root)
            if second is None:
                return None
            if second != first:
                messagebox.showwarning(title, "The passwords do not match.", parent=root)
                continue
            return first
    finally:
        root.destroy()


def ask_yes_no(title: str, message: str) -> bool:
    try:
        from tkinter import messagebox

        root = _root()
        answer = messagebox.askyesno(title, message, parent=root)
        root.destroy()
        return bool(answer)
    except Exception:  # noqa: BLE001
        return False


def run_with_progress(title: str, work):
    """Run work(progress) in a thread while a small window shows its progress.

    progress(message, fraction 0..1) may be called from the worker thread.
    Returns work's result or raises its exception.
    """
    import threading
    import tkinter
    from tkinter import ttk

    root = tkinter.Tk()
    _set_icon(root)
    root.title(title)
    root.attributes("-topmost", True)
    root.resizable(False, False)
    root.protocol("WM_DELETE_WINDOW", lambda: None)  # finish (or fail) first
    frame = ttk.Frame(root, padding=16)
    frame.pack(fill="both")
    label = ttk.Label(frame, text="…", width=48)
    label.pack(anchor="w")
    bar = ttk.Progressbar(frame, length=360, maximum=1.0)
    bar.pack(pady=(10, 0))
    state: dict = {"message": "…", "fraction": 0.0, "done": False}

    def progress(message: str, fraction: float) -> None:
        state["message"], state["fraction"] = message, fraction

    def worker() -> None:
        try:
            state["result"] = work(progress)
        except BaseException as ex:  # noqa: BLE001 - handed to the caller
            state["error"] = ex
        state["done"] = True

    def poll() -> None:
        label.config(text=state["message"])
        bar["value"] = state["fraction"]
        if state["done"]:
            root.destroy()
        else:
            root.after(150, poll)

    threading.Thread(target=worker, daemon=True).start()
    root.after(150, poll)
    root.mainloop()
    if "error" in state:
        raise state["error"]
    return state.get("result")


def settings_dialog(values: dict, components: list[tuple[str, bool]],
                    can_autostart: bool, can_update: bool, on_install=None) -> dict | None:
    """Edit the main settings. Returns the new values, or None if cancelled.

    values: port, https, http_port, media_dirs (list), support_email, auto_update, autostart,
    keep_songs.
    components: (name, installed) for ffmpeg/Deno; on_install() installs missing ones.
    """
    import tkinter
    from tkinter import filedialog, messagebox, ttk

    root = tkinter.Tk()
    _set_icon(root)
    root.title("AirMan – Settings")
    root.attributes("-topmost", True)
    frame = ttk.Frame(root, padding=16)
    frame.pack(fill="both", expand=True)
    frame.columnconfigure(1, weight=1)
    row = 0

    def label(text: str) -> None:
        ttk.Label(frame, text=text).grid(row=row, column=0, sticky="nw", pady=4, padx=(0, 12))

    label("Port")
    port = tkinter.StringVar(value=str(values["port"]))
    ttk.Entry(frame, textvariable=port, width=8).grid(row=row, column=1, sticky="w", pady=4)
    row += 1

    https = tkinter.BooleanVar(value=values["https"])
    ttk.Checkbutton(frame, text="HTTPS (recommended)", variable=https).grid(
        row=row, column=1, sticky="w", pady=4)
    row += 1

    label("HTTP port")
    http_row = ttk.Frame(frame)
    http_row.grid(row=row, column=1, sticky="w", pady=4)
    http_port = tkinter.StringVar(value=str(values.get("http_port") or ""))
    ttk.Entry(http_row, textvariable=http_port, width=8).pack(side="left")
    ttk.Label(http_row, text="optional, for old devices; empty = off (not encrypted)").pack(
        side="left", padx=(8, 0))
    row += 1

    label("Music folders")
    folders = tkinter.Listbox(frame, height=4, width=48)
    for folder in values["media_dirs"]:
        folders.insert("end", folder)
    folders.grid(row=row, column=1, sticky="ew", pady=4)
    row += 1
    buttons = ttk.Frame(frame)
    buttons.grid(row=row, column=1, sticky="w")

    def add_folder() -> None:
        path = filedialog.askdirectory(parent=root, mustexist=True)
        if path and path not in folders.get(0, "end"):
            folders.insert("end", path)

    def remove_folder() -> None:
        for index in reversed(folders.curselection()):
            folders.delete(index)

    ttk.Button(buttons, text="Add…", command=add_folder).pack(side="left")
    ttk.Button(buttons, text="Remove", command=remove_folder).pack(side="left", padx=6)
    row += 1

    label("Email for logs")
    email = tkinter.StringVar(value=values["support_email"])
    ttk.Entry(frame, textvariable=email, width=36).grid(row=row, column=1, sticky="w", pady=4)
    row += 1

    autostart = tkinter.BooleanVar(value=values["autostart"])
    if can_autostart:
        ttk.Checkbutton(frame, text="Start with Windows", variable=autostart).grid(
            row=row, column=1, sticky="w", pady=4)
        row += 1
    keep_songs = tkinter.BooleanVar(value=values["keep_songs"])
    ttk.Checkbutton(frame, text="Never delete downloaded songs", variable=keep_songs).grid(
        row=row, column=1, sticky="w", pady=4)
    row += 1
    auto_update = tkinter.BooleanVar(value=values["auto_update"])
    if can_update:
        ttk.Checkbutton(frame, text="Install updates automatically", variable=auto_update).grid(
            row=row, column=1, sticky="w", pady=4)
        row += 1

    label("Components")
    status = ttk.Frame(frame)
    status.grid(row=row, column=1, sticky="w", pady=4)
    for name, installed in components:
        ttk.Label(status, text=f"{name}: {'installed' if installed else 'missing'}").pack(
            anchor="w")
    if on_install and not all(installed for _, installed in components):
        ttk.Button(status, text="Install missing…", command=on_install).pack(anchor="w",
                                                                            pady=(4, 0))
    row += 1

    result: dict = {}

    def save() -> None:
        try:
            new_port = int(port.get())
            if not 1024 <= new_port <= 65535:
                raise ValueError
        except ValueError:
            messagebox.showerror("AirMan", "The port must be a number from 1024 to 65535.",
                                 parent=root)
            return
        try:
            new_http = int(http_port.get().strip() or 0)
            if (new_http and not 1024 <= new_http <= 65535) or new_http == new_port:
                raise ValueError
        except ValueError:
            messagebox.showerror("AirMan", "The HTTP port must be empty or a number from 1024 "
                                 "to 65535, different from the port.", parent=root)
            return
        result.update(port=new_port, https=https.get(), http_port=new_http,
                      media_dirs=list(folders.get(0, "end")),
                      support_email=email.get().strip(), autostart=autostart.get(),
                      auto_update=auto_update.get(), keep_songs=keep_songs.get())
        root.destroy()

    actions = ttk.Frame(frame)
    actions.grid(row=row, column=0, columnspan=2, sticky="e", pady=(12, 0))
    ttk.Button(actions, text="Cancel", command=root.destroy).pack(side="right")
    ttk.Button(actions, text="Save and restart", command=save).pack(side="right", padx=6)
    root.mainloop()
    return result or None
