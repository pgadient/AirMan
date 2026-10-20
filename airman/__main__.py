"""Command line entry point: `python -m airman`."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import logging
import mimetypes
import os
import secrets
import ssl
import sys
from dataclasses import dataclass
from pathlib import Path

from aiohttp import web

from . import __version__
from .auth import AuthStore
from .config import Config, default_data_dir
from .logbuffer import setup_logging, system_summary

_LOGGER = logging.getLogger("airman")


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="airman", description="AirPlay player with web UI")
    parser.add_argument("--data", type=Path, default=None,
                        help="data directory (default: ./data next to the program)")
    parser.add_argument("--host", help="address to listen on (overrides config)")
    parser.add_argument("-p", "--port", type=int,
                        default=int(os.environ["AIRMAN_PORT"]) if os.environ.get("AIRMAN_PORT") else None,
                        help="port to listen on (overrides config; env: AIRMAN_PORT)")
    parser.add_argument("--set-password", action="store_true",
                        help="set a new web password and exit")
    parser.add_argument("--scan", action="store_true", help="list AirPlay speakers and exit")
    parser.add_argument("--check-gui", action="store_true",
                        help="check that the dialogs (tkinter) work, then exit")
    parser.add_argument("--tray", action="store_true",
                        help="run with a system tray icon instead of a console")
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    parser.add_argument("--version", action="version", version=f"AirMan {__version__}")
    return parser.parse_args(argv)


def _set_password(auth: AuthStore) -> int:
    while True:
        first = getpass.getpass("New password (min. 8 characters): ")
        if len(first) < 8:
            print("Too short.")
            continue
        if getpass.getpass("Repeat: ") != first:
            print("Passwords do not match.")
            continue
        auth.set_password(first)
        print("Password saved. All devices have been logged out.")
        return 0


async def _scan() -> int:
    import pyatv
    from pyatv.const import Protocol

    configs = await pyatv.scan(asyncio.get_running_loop(), timeout=5, protocol=Protocol.RAOP)
    for conf in sorted(configs, key=lambda c: c.name):
        service = conf.get_service(Protocol.RAOP)
        pairing = service.pairing.name if service else "?"
        print(f"{conf.name:<30} {conf.device_info.model_str:<20} {conf.address!s:<16} "
              f"pairing: {pairing}")
    return 0


@dataclass
class Server:
    app: web.Application
    auth: AuthStore
    data_dir: Path
    host: str
    port: int
    ssl_context: ssl.SSLContext | None
    phone_url: str
    http_port: int = 0  # extra plain-HTTP port for old devices, 0 = none

    @property
    def local_url(self) -> str:
        scheme = "https" if self.ssl_context else "http"
        return f"{scheme}://localhost:{self.port}"


def _first_password(auth: AuthStore, tray: bool) -> None:
    """Make sure a web password exists before anybody can connect."""
    if auth.has_password:
        return
    if tray:
        from . import gui

        password = gui.ask_new_password("AirMan – first start")
        if password:
            auth.set_password(password)
            return
        password = secrets.token_urlsafe(9)
        auth.set_password(password)
        shown = gui.show_info("AirMan", f"Your web password is:\n\n{password}\n\n"
                                        "You can change it in the tray menu.", secret=True)
        if not shown:
            # No window possible: leave it in a private file instead of the logs.
            hint = auth.data_dir / "FIRST-PASSWORD.txt"
            hint.write_text(f"AirMan web password: {password}\nDelete this file after "
                            "logging in, or change the password.\n", encoding="utf-8")
            _LOGGER.warning("First password written to %s", hint.name)
        return
    password = secrets.token_urlsafe(9)
    auth.set_password(password)
    print("=" * 60)
    print(f"  First start. Web password: {password}")
    print("  Change it any time with:  airman --set-password")
    print("=" * 60)


def _offer_downloads(data_dir: Path) -> None:
    """Tray start: offer to install missing ffmpeg/Deno with one click."""
    from . import deps, gui

    config_file = data_dir / "config.json"
    config = Config.load(config_file)
    missing = deps.missing(config)
    if not missing or not config.offer_downloads:
        return
    lines = "\n".join(f"• {item.describe()}" for item in missing)
    installable = [i for i in missing if not isinstance(i, deps.Manual)]
    if not installable:
        gui.show_info("AirMan – first start",
                      f"AirMan needs a few free helper programs:\n\n{lines}")
        return
    question = (f"AirMan needs a few free helper programs:\n\n{lines}\n\n"
                "Install them now? Downloads come from the official sites and are checked "
                "against a built-in fingerprint before they are used.")
    if not gui.ask_yes_no("AirMan – first start", question):
        # Do not nag again; Settings in the tray menu can install them later.
        config.offer_downloads = False
        config.save(config_file)
        return

    def work(progress):
        for item in installable:
            deps.install_any(item, progress)

    try:
        gui.run_with_progress("AirMan – installing", work)
    except Exception as ex:  # noqa: BLE001
        _LOGGER.warning("Installing helper programs failed: %s", ex)
        gui.show_error("AirMan", f"Installing failed:\n{ex}\n\nYou can try again via the "
                                 "tray menu: Settings.")


def _build_server(args: argparse.Namespace, data_dir: Path, auth: AuthStore) -> Server | str:
    """Create the web app. Returns an error message instead if it can not start."""
    config = Config.load(data_dir / "config.json")
    if args.host:
        config.host = args.host
    if args.port:
        config.port = args.port

    if not config.ffmpeg():
        return (f"ffmpeg not found. Install it (e.g. winget install Gyan.FFmpeg) "
                f"or set ffmpeg_path in {data_dir / 'config.json'}")
    if not config.deno():
        _LOGGER.warning("Deno not found: YouTube will probably not work.")

    # Imported late so --help and --set-password stay fast.
    from . import tls
    from .player import SpeakerManager
    from .sources import Sources
    from .thumbs import ThumbnailCache
    from .web import create_app

    ssl_context = None
    ca_file = None
    if config.https:
        if config.tls_cert_file:
            cert_file, key_file = Path(config.tls_cert_file), Path(config.tls_key_file)
        else:
            cert_file, key_file, ca_file = tls.ensure_certificates(data_dir / "tls")
        ssl_context = tls.server_context(cert_file, key_file)

    sources = Sources(config, data_dir)
    speakers = SpeakerManager(sources, data_dir)
    # Songs from before the offline library: move them in under their known titles.
    sources.youtube.adopt([t for s in speakers.speakers.values() for t in s.history + s.queue
                           + ([s.resume] if s.resume else [])])
    thumbs = ThumbnailCache(data_dir / "thumbs", f"AirMan/{__version__}")
    app = create_app(config, auth, speakers, sources, ca_file=ca_file, thumbs=thumbs,
                     data_dir=data_dir)

    _LOGGER.info("Data in %s", data_dir)
    scheme = "https" if ssl_context else "http"
    if config.host in ("0.0.0.0", "::"):
        hosts = [ip for ip in tls.local_addresses() if not ip.startswith("127.")] or ["localhost"]
    else:
        hosts = [config.host]
    for host in hosts:
        _LOGGER.info("Open %s://%s:%d on your phone", scheme, host, config.port)
    http_port = config.http_port if ssl_context else 0
    if http_port:
        _LOGGER.info("Also without encryption for old devices: http://%s:%d", hosts[0], http_port)
    return Server(app, auth, data_dir, config.host, config.port, ssl_context,
                  f"{scheme}://{hosts[0]}:{config.port}", http_port)


async def serve(server: Server, stop: asyncio.Event) -> None:
    """Serve the page (and the optional plain-HTTP port) until stop is set."""
    runner = web.AppRunner(server.app, access_log=None)
    await runner.setup()
    try:
        await web.TCPSite(runner, server.host, server.port,
                          ssl_context=server.ssl_context).start()
        if server.http_port:
            await web.TCPSite(runner, server.host, server.http_port).start()
        await stop.wait()
    finally:
        await runner.cleanup()


async def _serve_until_stopped(server: Server) -> None:
    await serve(server, asyncio.Event())  # runs until Ctrl+C


def main(argv: list[str] | None = None) -> int:
    # Song titles are full of emoji; never crash on an old console code page.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    mimetypes.add_type("application/manifest+json", ".webmanifest")

    args = _parse_args(argv)
    if args.check_gui:
        setup_logging(args.verbose, (args.data or default_data_dir()).resolve() / "logs")
        try:
            import tkinter

            root = tkinter.Tk()
            root.withdraw()
            root.update()
            root.destroy()
        except Exception:
            _LOGGER.exception("GUI check failed")
            return 1
        _LOGGER.info("GUI check OK (Tcl/Tk %s)", tkinter.TclVersion)
        return 0
    if args.scan:
        setup_logging(args.verbose, None)
        return asyncio.run(_scan())

    data_dir = (args.data or default_data_dir()).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    setup_logging(args.verbose, data_dir / "logs")
    _LOGGER.info("Starting %s%s", system_summary(__version__), " (tray)" if args.tray else "")
    auth = AuthStore(data_dir)
    if args.set_password:
        return _set_password(auth)

    _first_password(auth, args.tray)
    if args.tray:
        _offer_downloads(data_dir)
    else:
        from . import deps

        deps.ask_in_terminal(data_dir / "config.json")
    server = _build_server(args, data_dir, auth)
    if isinstance(server, str):
        _LOGGER.error("%s", server)
        if args.tray:
            from . import gui

            gui.show_error("AirMan", server)
        return 1

    if args.tray:
        from . import tray

        return tray.run(server)
    try:
        asyncio.run(_serve_until_stopped(server))
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
