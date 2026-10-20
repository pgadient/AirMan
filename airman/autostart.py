"""'Start with Windows' for the standalone program (current user only, no admin)."""

from __future__ import annotations

import logging
import sys

_LOGGER = logging.getLogger(__name__)

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
NAME = "AirMan"


def supported() -> bool:
    return sys.platform == "win32" and bool(getattr(sys, "frozen", False))


def _command() -> str:
    return f'"{sys.executable}"'


def enabled() -> bool:
    if not supported():
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, NAME)
            return value == _command()
    except OSError:
        return False


def set_enabled(on: bool) -> None:
    if not supported():
        return
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if on:
            winreg.SetValueEx(key, NAME, 0, winreg.REG_SZ, _command())
        else:
            try:
                winreg.DeleteValue(key, NAME)
            except FileNotFoundError:
                pass
    _LOGGER.info("Start with Windows: %s", "on" if on else "off")
