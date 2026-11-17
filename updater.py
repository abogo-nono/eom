"""Opt-in update check against GitHub Releases.

Only runs when the user enables it in Settings (or clicks "Check now"): EOM is a
privacy tool and makes no network request by default.  The request carries a
generic User-Agent and no user data.
"""

from __future__ import annotations

import json
import re

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from version import __version__

RELEASES_API = "https://api.github.com/repos/abogo-nono/eom/releases/latest"
RELEASES_PAGE = "https://github.com/abogo-nono/eom/releases/latest"
USER_AGENT = f"EOM/{__version__}"


def parse_version(text: str) -> tuple[int, ...]:
    """``'v2.10.1-beta'`` → ``(2, 10, 1)``; unparsable → ``()``."""
    match = re.match(r"^\s*v?(\d+(?:\.\d+)*)", text or "")
    return tuple(int(p) for p in match.group(1).split(".")) if match else ()


def is_newer(latest: str, current: str = __version__) -> bool:
    lv, cv = parse_version(latest), parse_version(current)
    if not lv or not cv:
        return False
    width = max(len(lv), len(cv))
    return lv + (0,) * (width - len(lv)) > cv + (0,) * (width - len(cv))


def parse_release(payload: bytes) -> tuple[str, str] | None:
    """Return ``(tag, html_url)`` from the GitHub API response, or None."""
    try:
        data = json.loads(payload)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict) or not data.get("tag_name"):
        return None
    return str(data["tag_name"]), str(data.get("html_url") or RELEASES_PAGE)


class UpdateChecker(QObject):
    """Asynchronous check. Emits ``finished(tag, url, error)``.

    *tag* is non-empty only when a newer release exists; *error* is non-empty
    when the request failed.
    """

    finished = Signal(str, str, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._nam = QNetworkAccessManager(self)
        self._reply: QNetworkReply | None = None

    def check(self) -> None:
        request = QNetworkRequest(QUrl(RELEASES_API))
        request.setHeader(QNetworkRequest.UserAgentHeader, USER_AGENT)
        request.setRawHeader(b"Accept", b"application/vnd.github+json")
        request.setTransferTimeout(10_000)
        self._reply = self._nam.get(request)
        self._reply.finished.connect(self._on_finished)

    def _on_finished(self) -> None:
        reply = self._reply
        self._reply = None
        if reply is None:
            return
        try:
            if reply.error() != QNetworkReply.NoError:
                self.finished.emit("", "", reply.errorString())
                return
            release = parse_release(bytes(reply.readAll()))
            if release is None:
                self.finished.emit("", "", "Unexpected response from GitHub")
                return
            tag, url = release
            self.finished.emit(tag if is_newer(tag) else "", url, "")
        finally:
            reply.deleteLater()
