"""System tray mode: the web server runs in the background, the icon in front.

Started by double-clicking AirMan.exe or with `python -m airman --tray`.
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path
from typing import TYPE_CHECKING


from . import __version__, gui

if TYPE_CHECKING:
    from .__main__ import Server

_LOGGER = logging.getLogger(__name__)

ICON = Path(__file__).resolve().parent / "static" / "icons" / "default" / "icon-192.png"
TOOLTIP = f"AirMan {__version__} – Your speakers, your music"


class BackgroundServer:
    """Runs the aiohttp app on its own event loop in a background thread."""

    def __init__(self, server: "Server") -> None:
        self.server = server
        self.loop = asyncio.new_event_loop()
        self.started = threading.Event()
        self.error: BaseException | None = None
        self._stop: asyncio.Event | None = None
        self._thread = threading.Thread(target=self._run, name="airman-server", daemon=True)

    def start(self, timeout: float = 30) -> None:
        self._thread.start()
        self.started.wait(timeout)
        if self.error:
            raise self.error

    def stop(self) -> None:
        if self._stop is not None:
            self.loop.call_soon_threadsafe(self._stop.set)
        self._thread.join(timeout=15)

    def _run(self) -> None:
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._serve())
        except BaseException as ex:  # noqa: BLE001 - reported to the main thread
            self.error = ex
            self.started.set()
        finally:
            self.loop.close()

    async def _serve(self) -> None:
        from .__main__ import serve

        self._stop = asyncio.Event()
        serving = asyncio.ensure_future(serve(self.server, self._stop))
        # serve() only ends this early if a port is taken: report that, else carry on.
        await asyncio.wait([serving], timeout=5)
        if serving.done():
            serving.result()
            return
        _LOGGER.info("Tray mode: serving on port %d", self.server.port)
        self.started.set()
        await serving


def _open_folder(path: Path) -> None:
    if sys.platform == "win32":
        os.startfile(path)  # type: ignore[attr-defined]  # noqa: S606
    elif sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
    else:
        subprocess.run(["xdg-open", str(path)], check=False)


def _restart_command() -> list[str]:
    args = [a for a in sys.argv[1:] if a != "--tray"]
    if getattr(sys, "frozen", False):
        return [sys.executable, "--tray", *args]
    return [sys.executable, "-m", "airman", "--tray", *args]


def _anything_playing(server: "Server") -> bool:
    from .web import APP_KEY_SPEAKERS

    speakers = server.app[APP_KEY_SPEAKERS].speakers.values()
    return any(s.status in ("playing", "loading") for s in speakers)


def run(server: "Server") -> int:
    try:
        import pystray
        from PIL import Image
        # pystray converts the icon to .ico/.png; Pillow loads these writers lazily,
        # so name them here or PyInstaller leaves them out of AirMan.exe.
        from PIL import IcoImagePlugin, PngImagePlugin  # noqa: F401
    except ImportError:
        gui.show_error("AirMan", "The tray icon needs the packages in requirements-tray.txt.")
        return 1

    from . import autostart, deps, updater
    from .config import Config

    if updater.can_update():
        updater.cleanup()  # leftovers of a previous update

    background = BackgroundServer(server)
    try:
        background.start()
    except OSError as ex:
        # Most likely AirMan is already running: just open it.
        _LOGGER.warning("Could not start the web server: %s", ex)
        webbrowser.open(server.local_url)
        gui.show_info("AirMan", f"AirMan is already running (or port {server.port} is in use).\n"
                                f"Opening {server.local_url}")
        return 0

    config_file = server.data_dir / "config.json"
    state: dict = {"update": None, "restart": False}
    icon_ref: dict = {}

    def restart() -> None:
        state["restart"] = True
        icon_ref["icon"].stop()

    def open_airman(icon=None, item=None) -> None:
        webbrowser.open(server.local_url)

    def change_password(icon=None, item=None) -> None:
        password = gui.ask_new_password()
        if password:
            server.auth.set_password(password)
            gui.show_info("AirMan", "Password changed. All devices have been logged out.")

    def install_components() -> bool:
        missing = deps.missing(Config.load(config_file))
        if not missing:
            gui.show_info("AirMan", "ffmpeg and Deno are installed.")
            return False

        manual = [i for i in missing if isinstance(i, deps.Manual)]
        if manual:
            gui.show_info("AirMan", "\n".join(f"• {i.describe()}" for i in manual))
        installable = [i for i in missing if not isinstance(i, deps.Manual)]
        if not installable:
            return False

        def work(progress):
            for item in installable:
                deps.install_any(item, progress)

        try:
            gui.run_with_progress("AirMan – installing", work)
        except Exception as ex:  # noqa: BLE001
            _LOGGER.warning("Installing components failed: %s", ex)
            gui.show_error("AirMan", f"Installing failed:\n{ex}")
            return False
        return True

    def settings(icon=None, item=None) -> None:
        config = Config.load(config_file)
        values = {
            "port": config.port, "https": config.https, "http_port": config.http_port,
            "media_dirs": list(config.media_dirs),
            "support_email": config.support_email, "auto_update": config.auto_update,
            "autostart": autostart.enabled(), "keep_songs": config.offline_max_mb == 0,
        }
        components = [("ffmpeg", bool(config.ffmpeg())), ("Deno", bool(config.deno()))]
        installed_now: dict = {}

        def on_install() -> None:
            installed_now["done"] = install_components()

        result = gui.settings_dialog(values, components, autostart.supported(),
                                     updater.can_update(),
                                     on_install if deps.supported() else None)
        if result is None:
            if installed_now.get("done"):
                restart()
            return
        keep = result.pop("keep_songs")
        if keep:
            config.offline_max_mb = 0
        elif config.offline_max_mb == 0:
            config.offline_max_mb = 20000
        if result.pop("autostart") != values["autostart"]:
            try:
                autostart.set_enabled(not values["autostart"])
            except OSError as ex:
                gui.show_error("AirMan", f"Could not change autostart:\n{ex}")
        for key, value in result.items():
            setattr(config, key, value)
        try:
            config.validate()
        except ValueError as ex:
            gui.show_error("AirMan", str(ex))
            return
        config.save(config_file)
        _LOGGER.info("Settings saved, restarting")
        restart()

    def check_updates(icon=None, item=None) -> None:
        find_update(manual=True)

    def install_update(icon=None, item=None) -> None:
        update = state["update"]
        if update is None:
            return
        try:
            data = gui.run_with_progress(
                "AirMan – update",
                lambda progress: (progress(f"Downloading AirMan {update.version}", 0.3),
                                  updater.download(update))[1])
            updater.install(data)
        except Exception as ex:  # noqa: BLE001
            _LOGGER.warning("Update failed: %s", ex)
            gui.show_error("AirMan", f"The update could not be installed:\n{ex}")
            return
        restart()

    def find_update(manual: bool = False) -> None:
        if not updater.can_update():
            if manual:
                gui.show_info("AirMan", "Updates are only available for the AirMan.exe program.")
            return
        try:
            update = updater.check()
        except Exception as ex:  # noqa: BLE001 - offline, repository not public yet, ...
            _LOGGER.info("Update check failed: %s", ex)
            if manual:
                gui.show_error("AirMan", f"Could not check for updates:\n{ex}")
            return
        state["update"] = update
        icon_ref["icon"].update_menu()
        if update is None:
            if manual:
                gui.show_info("AirMan", "AirMan is up to date.")
            return
        _LOGGER.info("Update available: %s", update.version)
        if manual:
            if gui.ask_yes_no("AirMan", f"AirMan {update.version} is available. Install now?"):
                install_update()
            return
        try:
            icon_ref["icon"].notify(f"AirMan {update.version} is available.", "Update")
        except Exception:  # noqa: BLE001
            pass

    def update_loop() -> None:
        import time

        time.sleep(60)
        while not state["restart"]:
            if Config.load(config_file).auto_update:
                find_update()
                update = state["update"]
                # Never interrupt music: install only while nothing plays.
                if update is not None and not _anything_playing(server):
                    try:
                        updater.install(updater.download(update))
                        _LOGGER.info("Automatic update to %s installed", update.version)
                        restart()
                        return
                    except Exception as ex:  # noqa: BLE001
                        _LOGGER.warning("Automatic update failed: %s", ex)
            time.sleep(3600 if state["update"] else 24 * 3600)

    def open_data(icon=None, item=None) -> None:
        _open_folder(server.data_dir)

    def quit_airman(icon, item=None) -> None:
        _LOGGER.info("Quit from tray")
        icon.stop()

    menu = pystray.Menu(
        pystray.MenuItem("Open AirMan", open_airman, default=True),
        pystray.MenuItem("Settings…", settings),
        pystray.MenuItem("Change password…", change_password),
        pystray.MenuItem(lambda item: f"Install update {state['update'].version}"
                         if state["update"] else "Install update",
                         install_update, visible=lambda item: state["update"] is not None),
        pystray.MenuItem("Check for updates", check_updates, visible=lambda item: updater.can_update()),
        pystray.MenuItem("Open data folder", open_data),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", quit_airman),
    )
    _LOGGER.info("Creating tray icon (%s)", ICON)
    icon = pystray.Icon("AirMan", Image.open(ICON), TOOLTIP, menu)
    icon_ref["icon"] = icon

    def ready(icon) -> None:
        try:
            icon.visible = True
            _LOGGER.info("Tray icon visible")
        except Exception:
            _LOGGER.exception("Could not show the tray icon")
            raise
        try:
            icon.notify(f"Open {server.phone_url} on your phone.", "AirMan is running")
        except Exception:  # noqa: BLE001 - notifications are optional
            pass
        if updater.can_update():
            threading.Thread(target=update_loop, name="airman-update", daemon=True).start()

    try:
        icon.run(setup=ready)
    except Exception:
        _LOGGER.exception("Tray icon failed")
        raise
    finally:
        _LOGGER.info("Tray icon stopped")
    background.stop()
    if state["restart"]:
        _LOGGER.info("Restarting: %s", " ".join(_restart_command()))
        subprocess.Popen(_restart_command(), close_fds=True)  # noqa: S603
    return 0
