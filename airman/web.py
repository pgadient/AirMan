"""Web server: JSON API plus a small static web app."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import math
import secrets
import shutil
import socket
import logging
from pathlib import Path
from typing import Any, Awaitable, Callable

import pyatv.exceptions
from aiohttp import BodyPartReader, web

from . import __version__
from .auth import AuthStore, LoginLimiter
from .config import Config
from .logbuffer import RING, redact, system_summary
from .player import SpeakerManager
from .sources import Sources, SourceError
from .thumbs import ThumbnailCache

_LOGGER = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent / "static"
SESSION_COOKIE = "airman_session"
# Browsers share cookies between ports: the plain-HTTP port uses its own name, so it
# never touches the (Secure) cookie of the HTTPS page.
SESSION_COOKIE_PLAIN = "airman_session_plain"


def _session_cookie(request: web.Request) -> str:
    plain_extra_port = not request.secure and request.app[APP_KEY_CONFIG].https
    return SESSION_COOKIE_PLAIN if plain_extra_port else SESSION_COOKIE
MAX_QUERY = 300

Handler = Callable[[web.Request], Awaitable[web.StreamResponse]]

SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    ),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}

ICON_FILES = ("favicon.svg", "favicon.ico", "apple-touch-icon.png", "icon-192.png", "icon-512.png",
              "icon-maskable-192.png", "icon-maskable-512.png", "airman-icon.svg")

# Every file the page may load is listed here; nothing else in the folder is served.
STATIC_FILES = ("app.js", "style.css", "manifest.webmanifest",
                *(f"icons/{theme}/{name}" for theme in ("default", "day", "night")
                  for name in ICON_FILES),
                *(f"banners/mascot-{art}.svg" for art in ("note", "moon", "sun")),
                "banners/tile-day.svg", "banners/tile-night.svg")

PUBLIC_PATHS = {"/", "/login", "/api/login", "/airman-ca.crt", *(f"/{n}" for n in STATIC_FILES)}

APP_KEY_CONFIG = web.AppKey("config", Config)
APP_KEY_AUTH = web.AppKey("auth", AuthStore)
APP_KEY_LIMITER = web.AppKey("limiter", LoginLimiter)
APP_KEY_LOGIN_SLOT = web.AppKey("login_slot", asyncio.Semaphore)
APP_KEY_SPEAKERS = web.AppKey("speakers", SpeakerManager)
APP_KEY_SOURCES = web.AppKey("sources", Sources)
APP_KEY_THUMBS = web.AppKey("thumbs", ThumbnailCache)
APP_KEY_DATA_DIR = web.AppKey("data_dir", Path)
LOW_DISK_BYTES = 10 * 1024 ** 3  # the page warns below 10 GB free


def _client_ip(request: web.Request) -> str:
    # Deliberately ignores X-Forwarded-For: it can be forged by any client.
    return request.remote or ""


@web.middleware
async def network_guard(request: web.Request, handler: Handler) -> web.StreamResponse:
    """Refuse everybody outside the allowed (by default: local) networks."""
    try:
        ip = ipaddress.ip_address(_client_ip(request).split("%")[0])
    except ValueError:
        raise web.HTTPForbidden() from None
    if ip.version == 6 and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    if not any(ip in net for net in request.app[APP_KEY_CONFIG].networks()):
        _LOGGER.warning("Blocked request from %s", ip)
        raise web.HTTPForbidden()
    if not _allowed_host(request.host):
        # A web page using a foreign domain name that points to this server (DNS rebinding).
        _LOGGER.warning("Blocked request for host %r from %s", request.host[:100], ip)
        raise web.HTTPForbidden()
    return await handler(request)


def _allowed_host(host: str) -> bool:
    """Only IP addresses, localhost and this computer's own names may be used."""
    name = host.rsplit(":", 1)[0] if not host.endswith("]") else host
    name = name.strip("[]").lower()
    try:
        ipaddress.ip_address(name)
        return True
    except ValueError:
        pass
    own = socket.gethostname().lower()
    return name in {"localhost", own, f"{own}.local"}


@web.middleware
async def log_errors(request: web.Request, handler: Handler) -> web.StreamResponse:
    try:
        return await handler(request)
    except web.HTTPException:
        raise
    except Exception:
        _LOGGER.exception("Unhandled error in %s %s", request.method, request.path)
        raise


@web.middleware
async def security_headers(request: web.Request, handler: Handler) -> web.StreamResponse:
    try:
        response = await handler(request)
    except web.HTTPException as ex:
        response = ex
    response.headers.update(SECURITY_HEADERS)
    if request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    elif "Cache-Control" not in response.headers:
        # Page files: always ask before reusing a cached copy, so updates show up at
        # once (unchanged files are answered with a short "not modified").
        response.headers["Cache-Control"] = "no-cache"
    if isinstance(response, web.HTTPException):
        raise response
    return response


@web.middleware
async def require_login(request: web.Request, handler: Handler) -> web.StreamResponse:
    if request.path in PUBLIC_PATHS:
        return await handler(request)
    if not request.app[APP_KEY_AUTH].validate_session(
            request.cookies.get(_session_cookie(request))):
        raise web.HTTPUnauthorized(text='{"error":"login"}', content_type="application/json")
    return await handler(request)


@web.middleware
async def csrf_guard(request: web.Request, handler: Handler) -> web.StreamResponse:
    """State changes only via same-origin JSON POSTs.

    Browsers can not send a cross-site JSON request without a CORS preflight,
    which this server never answers, and SameSite=Strict keeps the cookie home.
    """
    if request.method not in ("GET", "HEAD"):
        if request.path == "/api/upload":
            # A plain HTML form could post multipart data from another site; the custom
            # header can only be set by our own page (anything else needs CORS).
            if (request.content_type != "multipart/form-data"
                    or request.headers.get("X-AirMan-Upload") != "1"):
                raise web.HTTPForbidden()
        elif request.content_type != "application/json":
            raise web.HTTPUnsupportedMediaType()
        origin = request.headers.get("Origin")
        if origin and origin.split("://", 1)[-1] != request.host:
            raise web.HTTPForbidden()
        if request.headers.get("Sec-Fetch-Site") not in (None, "same-origin", "none"):
            raise web.HTTPForbidden()
    return await handler(request)


def _reject_constant(name: str) -> float:
    raise ValueError(f"{name} is not allowed")


def _strict_loads(text: str) -> Any:
    """json.loads without NaN/Infinity, which would break the saved state."""
    return json.loads(text, parse_constant=_reject_constant)


def _number(value: Any) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("invalid number")
    return number


async def _json(request: web.Request) -> dict[str, Any]:
    try:
        data = await request.json(loads=_strict_loads)
    except ValueError:
        raise web.HTTPBadRequest(text="invalid json") from None
    if not isinstance(data, dict):
        raise web.HTTPBadRequest(text="expected object")
    return data


def _error(message: str, status: int = 400) -> web.Response:
    return web.json_response({"error": message}, status=status)


# ----- pages ------------------------------------------------------------------

async def index(request: web.Request) -> web.FileResponse:
    return web.FileResponse(STATIC_DIR / "index.html")


def _static(name: str) -> Handler:
    async def handler(request: web.Request) -> web.FileResponse:
        return web.FileResponse(STATIC_DIR / name)
    return handler


# ----- auth --------------------------------------------------------------------

async def login(request: web.Request) -> web.Response:
    limiter = request.app[APP_KEY_LIMITER]
    ip = _client_ip(request)
    wait = limiter.retry_after(ip)
    if wait > 0:
        _LOGGER.warning("Login from %s refused, locked for %.0fs", ip, wait)
        return web.json_response({"error": "locked", "retry_after": int(wait) + 1}, status=429)
    data = await _json(request)
    password = data.get("password")
    auth = request.app[APP_KEY_AUTH]
    limiter.attempt(ip)  # counted before the slow check, so parallel requests can not slip by
    async with request.app[APP_KEY_LOGIN_SLOT]:  # one password check at a time (CPU/RAM)
        valid = (isinstance(password, str) and len(password) <= 200
                 and await asyncio.to_thread(auth.check_password, password))
    if not valid:
        _LOGGER.warning("Failed login from %s", ip)
        await asyncio.sleep(1)  # slows down guessing even before the lockout
        return _error("wrong password", 401)
    limiter.succeeded(ip)
    _LOGGER.info("Login from %s (%s)", ip, request.headers.get("User-Agent", "?")[:120])
    token = auth.create_session()
    response = web.json_response({"ok": True})
    response.set_cookie(_session_cookie(request), token, max_age=365 * 24 * 3600,
                        httponly=True,
                        samesite="Strict", secure=request.secure, path="/")
    return response


async def logout(request: web.Request) -> web.Response:
    _LOGGER.info("Logout from %s", _client_ip(request))
    request.app[APP_KEY_AUTH].revoke_session(request.cookies.get(_session_cookie(request)))
    response = web.json_response({"ok": True})
    response.del_cookie(_session_cookie(request), path="/")
    return response


# ----- player ------------------------------------------------------------------

async def state(request: web.Request) -> web.Response:
    speakers = request.app[APP_KEY_SPEAKERS]
    return web.json_response({
        "version": __version__,
        "speakers": speakers.to_list(),
        "last_speaker": speakers.preferred_speaker(),
        "sources": [{"name": s.name, "label": s.label} for s in request.app[APP_KEY_SOURCES].all()],
        "support_email": request.app[APP_KEY_CONFIG].support_email,
        "system": system_summary(__version__),
        "disk": _disk_space(request),
        "pair_names": {s.id: s.name for s in speakers.speakers.values() if s.kind == "pair"},
        "group_count": speakers.group_count(),
    })


def _disk_space(request: web.Request) -> dict[str, Any] | None:
    data_dir = request.app.get(APP_KEY_DATA_DIR)
    if data_dir is None:
        return None
    try:
        free = shutil.disk_usage(data_dir).free
    except OSError:
        return None
    return {"free": free, "low": free < LOW_DISK_BYTES}


async def logs(request: web.Request) -> web.Response:
    """Recent log lines (already redacted) for the 'send logs' button."""
    _LOGGER.info("Logs requested from %s", _client_ip(request))
    speakers = request.app[APP_KEY_SPEAKERS]
    lines = [f"{system_summary(__version__)}", "", "Speakers:"]
    for s in sorted(speakers.speakers.values(), key=lambda x: x.name.lower()):
        extra = f" pair={s.members} leader={s.target_id} left={s.left_id} balance={s.balance} split={s.split}" \
            if s.kind == "pair" else ""
        lines.append(f"  {s.name} [{s.id}] {s.model} {s.address} online={s.online} "
                     f"supported={s.supported} status={s.status} error={s.error!r}{extra}")
    lines += ["", "Log:", RING.text()]
    return web.Response(text=redact("\n".join(lines)), content_type="text/plain",
                        charset="utf-8")


async def search(request: web.Request) -> web.Response:
    data = await _json(request)
    query = data.get("q")
    source_name = str(data.get("source") or "youtube")
    # The files tab may list everything without a search term.
    empty_ok = source_name == "local"
    if (not isinstance(query, str) or len(query) > MAX_QUERY
            or (not query.strip() and not empty_ok)):
        return _error("invalid query")
    sources = request.app[APP_KEY_SOURCES]
    try:
        source = sources.get(source_name)
        results = await source.search(query.strip())
    except ValueError as ex:
        return _error(str(ex))
    except SourceError as ex:
        return _error(str(ex), 502)
    return web.json_response({"results": [t.to_dict() for t in results]})


MAX_UPLOAD = 500 * 1024 * 1024  # per file
MIN_FREE_BYTES = 2 * 1024 ** 3  # uploads stop before the disk is full


def _free_bytes(path: Path) -> int:
    try:
        return shutil.disk_usage(path).free
    except OSError:
        return 0
MAX_UPLOAD_FILES = 50


async def upload(request: web.Request) -> web.Response:
    """Store uploaded audio files in data/uploads."""
    local = request.app[APP_KEY_SOURCES].local
    reader = await request.multipart()
    saved: list[str] = []
    while (part := await reader.next()) is not None:
        if len(saved) >= MAX_UPLOAD_FILES:
            return _error("too many files")
        if not isinstance(part, BodyPartReader) or not part.filename:
            continue
        name = part.filename[:200]
        try:
            target = local.upload_target(name)
        except ValueError as ex:
            return _error(f"{name}: {ex}")
        # Unique per upload, so two uploads with the same name never share a file.
        partial = local.incoming_path(target).with_name(f"{secrets.token_hex(8)}.part")
        size = 0
        try:
            if _free_bytes(partial.parent) < MIN_FREE_BYTES:
                raise ValueError("not enough free disk space")
            with open(partial, "wb") as out:
                while chunk := await part.read_chunk(256 * 1024):
                    size += len(chunk)
                    if size > MAX_UPLOAD:
                        raise ValueError("file too large (max 500 MB)")
                    if size % (32 * 1024 * 1024) < len(chunk) and \
                            _free_bytes(partial.parent) < MIN_FREE_BYTES:
                        raise ValueError("not enough free disk space")
                    out.write(chunk)
            if size == 0:
                raise ValueError("empty file")
            if target.exists():  # taken meanwhile by a parallel upload
                target = local.upload_target(target.name)
            partial.replace(target)
        except ValueError as ex:
            partial.unlink(missing_ok=True)
            _LOGGER.info("Upload %r rejected: %s", name, ex)
            return _error(f"{name}: {ex}")
        except OSError as ex:
            partial.unlink(missing_ok=True)
            _LOGGER.warning("Upload %r failed: %s", name, ex)
            return _error(f"{name}: could not be saved")
        _LOGGER.info("Uploaded %r (%d kB) from %s", target.name, size // 1024, _client_ip(request))
        saved.append(target.name)
    return web.json_response({"saved": saved})


async def delete_file(request: web.Request) -> web.Response:
    data = await _json(request)
    try:
        request.app[APP_KEY_SOURCES].local.delete_upload(str(data.get("ref") or ""))
    except ValueError as ex:
        return _error(str(ex))
    except OSError as ex:
        _LOGGER.warning("Delete failed: %s", ex)
        return _error("could not be deleted")
    return web.json_response({"ok": True})


async def rescan(request: web.Request) -> web.Response:
    await request.app[APP_KEY_SPEAKERS].scan()
    return await state(request)


async def speaker_action(request: web.Request) -> web.Response:
    speakers = request.app[APP_KEY_SPEAKERS]
    try:
        speaker = speakers.get(request.match_info["speaker"])
    except KeyError:
        return _error("unknown speaker", 404)
    action = request.match_info["action"]
    data = await _json(request)
    sources = request.app[APP_KEY_SOURCES]
    # Playback of a group is done by the speaker that plays for it; volume, mute,
    # balance and the stereo settings stay with each speaker.
    player = speakers.playback_target(speaker)
    _LOGGER.debug("Action %s on %s from %s", action, speaker.name, _client_ip(request))
    if speaker.needs_pairing and not action.startswith("pair_"):
        return _error("pair this Apple TV first", 409)
    try:
        if action == "play":
            raw = data.get("tracks")
            if not isinstance(raw, list) or not raw:
                return _error("tracks required")
            tracks = [await asyncio.to_thread(sources.track_from_dict, t) for t in raw[:500]]
            await player.play(tracks, int(data.get("index") or 0))
            speakers.mark_used(speaker)
        elif action == "seek":
            await player.seek(_number(data.get("position")))
        elif action == "continue":
            await player.continue_playing()
            speakers.mark_used(speaker)
        elif action == "enqueue":
            raw = data.get("tracks")
            if not isinstance(raw, list) or not raw:
                return _error("tracks required")
            await player.enqueue([await asyncio.to_thread(sources.track_from_dict, t)
                                   for t in raw[:500]])
            speakers.mark_used(speaker)
        elif action == "queue_move":
            await player.queue_move(int(data.get("from")), int(data.get("to")))
        elif action == "queue_remove":
            await player.queue_remove(int(data.get("index")))
        elif action == "queue_play":
            await player.queue_play(int(data.get("index")))
            speakers.mark_used(speaker)
        elif action == "queue_clear":
            await player.queue_clear()
        elif action == "replay":
            await player.replay()
            speakers.mark_used(speaker)
        elif action == "history":
            index = int(data.get("index", -1))
            if not 0 <= index < len(speaker.history):
                return _error("invalid index")
            await player.play([speaker.history[index]])
            speakers.mark_used(speaker)
        elif action == "pause":
            await player.pause()
        elif action == "stop":
            await player.stop_and_forget()
        elif action == "next":
            await player.skip(1)
        elif action == "previous":
            await player.skip(-1)
        elif action == "volume":
            await speaker.set_volume(_number(data.get("volume")))
        elif action == "balance":
            await speaker.set_balance(_number(data.get("balance")))
        elif action == "mute":
            await speaker.set_muted(bool(data.get("muted")))
        elif action == "repeat":
            player.set_repeat(str(data.get("mode")))
        elif action == "sleep":
            minutes = _number(data.get("minutes") or 0)
            if not 0 <= minutes <= 24 * 60:
                return _error("invalid sleep time")
            player.set_sleep(minutes)
        elif action == "left":
            await speaker.set_left(str(data.get("member")))
        elif action == "split":
            await speaker.set_split(bool(data.get("split")))
        elif action == "testtone":
            await speaker.play_test_tone()
        elif action == "group":
            group = data.get("group")
            if not isinstance(group, int) or isinstance(group, bool):
                return _error("group must be a number")
            await speakers.set_group(speaker, group)
        elif action == "pair_start":
            try:
                await speakers.pair_start(speaker.id)
            except (OSError, asyncio.TimeoutError, pyatv.exceptions.PairingError) as ex:
                _LOGGER.info("Pairing with %s could not start: %s", speaker.name, ex)
                return _error("Apple TV not reachable", 502)
        elif action == "pair_finish":
            await speakers.pair_finish(speaker.id, str(data.get("pin") or "").strip())
        elif action == "pair_cancel":
            await speakers.pair_cancel()
        else:
            return _error("unknown action", 404)
    except (ValueError, TypeError) as ex:
        _LOGGER.info("Action %s on %s rejected: %s", action, speaker.name, ex)
        return _error(str(ex) or "invalid request")
    # Every speaker of a group may have changed: the page refreshes all of them.
    return web.json_response({"speaker": speaker.to_dict(), "speakers": speakers.to_list()})


# ----- app -----------------------------------------------------------------------

async def thumbnail(request: web.Request) -> web.StreamResponse:
    path = await request.app[APP_KEY_THUMBS].get(request.match_info["video"])
    if path is None:
        raise web.HTTPNotFound()
    return web.FileResponse(path, headers={"Cache-Control": "private, max-age=604800"})


def _ca_download(ca_file: Path | None) -> Handler:
    """The local CA certificate (public data), so phones can trust AirMan's HTTPS."""
    async def handler(request: web.Request) -> web.StreamResponse:
        if ca_file is None or not ca_file.is_file():
            raise web.HTTPNotFound()
        return web.Response(body=ca_file.read_bytes(), content_type="application/x-x509-ca-cert",
                            headers={"Content-Disposition": 'attachment; filename="airman-ca.crt"'})
    return handler


def create_app(config: Config, auth: AuthStore, speakers: SpeakerManager,
               sources: Sources, ca_file: Path | None = None,
               thumbs: ThumbnailCache | None = None,
               data_dir: Path | None = None) -> web.Application:
    app = web.Application(
        client_max_size=64 * 1024,
        middlewares=[network_guard, security_headers, log_errors, require_login, csrf_guard],
    )
    app[APP_KEY_CONFIG] = config
    app[APP_KEY_AUTH] = auth
    app[APP_KEY_LIMITER] = LoginLimiter()
    app[APP_KEY_LOGIN_SLOT] = asyncio.Semaphore(1)
    app[APP_KEY_SPEAKERS] = speakers
    app[APP_KEY_SOURCES] = sources
    if data_dir is not None:
        app[APP_KEY_DATA_DIR] = data_dir
    if thumbs is not None:
        app[APP_KEY_THUMBS] = thumbs
        app.router.add_get("/thumbs/{video}.jpg", thumbnail)

    app.router.add_get("/", index)
    app.router.add_get("/login", index)
    for name in STATIC_FILES:
        app.router.add_get(f"/{name}", _static(name))
    app.router.add_get("/airman-ca.crt", _ca_download(ca_file))
    app.router.add_post("/api/login", login)
    app.router.add_post("/api/logout", logout)
    app.router.add_get("/api/state", state)
    app.router.add_get("/api/logs", logs)
    app.router.add_post("/api/search", search)
    app.router.add_post("/api/upload", upload)
    app.router.add_post("/api/files/delete", delete_file)
    app.router.add_post("/api/rescan", rescan)
    app.router.add_post("/api/speakers/{speaker}/{action}", speaker_action)

    async def on_startup(_app: web.Application) -> None:
        await speakers.start()

    async def on_cleanup(_app: web.Application) -> None:
        await speakers.shutdown()

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    return app
