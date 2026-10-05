"""Refresh release download metadata while refusing stale retained payloads."""

from __future__ import annotations

import contextlib
import json
from http.client import HTTPConnection, HTTPException, HTTPSConnection
from pathlib import Path
from urllib.parse import SplitResult, urlsplit

from cadrumo.core.product_identity import PRODUCT_IDENTITY

#: The runtime download payload the docs download page enhances with
#: (``initDownloadCards`` in ``docs/_static/cadrumo-docs.js``). It is pulled —
#: version agnostically — from the latest release into ``docs/_static`` before
#: the site build so the served ``_static/download-latest.json`` reflects the
#: current release once a release attaches it. Absent it (no release has
#: attached one yet), the offline Tier-1 channel table is the floor and the
#: site build proceeds unchanged.
_DOWNLOAD_LATEST_URL = f"https://github.com/{PRODUCT_IDENTITY.repository}/releases/latest/download/download-latest.json"


_DOWNLOAD_LATEST_SCHEMA = "cadrumo.download-latest.v1"


_DOWNLOAD_LATEST_STATIC_PATH = ("docs", "_static", "download-latest.json")


_DOWNLOAD_LATEST_TIMEOUT_SECONDS = 20


def _read_download_latest_body(endpoint: SplitResult, host: str, port: int | None, destination: Path) -> bytes | None:
    """Read download latest body."""
    path = endpoint.path or "/"
    if endpoint.query:
        path = f"{path}?{endpoint.query}"
    connection_type = HTTPSConnection if endpoint.scheme == "https" else HTTPConnection
    connection = connection_type(host, port, timeout=_DOWNLOAD_LATEST_TIMEOUT_SECONDS)
    try:
        connection.request("GET", path, headers={"User-Agent": "cadrumo-docs-delivery"})
        response = connection.getresponse()
        body = response.read()
        if not 200 <= response.status < 300:
            raise OSError(f"HTTP {response.status}")
    except (HTTPException, TimeoutError, OSError) as exc:
        _invalidate_download_latest(destination, f"download-latest.json unavailable ({exc})")
        return
    finally:
        connection.close()
    return body


def _invalidate_download_latest(destination: Path, reason: str) -> None:
    """Remove a stale ``download-latest.json`` (if any) and report why.

    A failed refresh must never leave a PRIOR release's payload standing as
    if it were current: an absent file is the documented safe floor (the
    offline Tier-1 channel table), while a stale-but-present one silently
    republishes an old release's download links as the current release. The
    removal itself must never raise -- an already-broken destination (e.g. a
    write failure because a path component is not a directory) has no stale
    file at that exact path to remove, and this function degrades silently
    like every other branch of the refresh.
    """
    with contextlib.suppress(OSError):
        destination.unlink(missing_ok=True)
    print(f"{reason}; serving the offline channel table.", flush=True)


def _refresh_download_latest(repo_root: Path, *, source_url: str = _DOWNLOAD_LATEST_URL) -> None:
    """Pull the latest release's ``download-latest.json`` into ``docs/_static``.

    Fetches the version-agnostic latest-release asset, validates it is the
    expected schema, and writes it to ``docs/_static/download-latest.json`` so
    the built site serves a current payload. Any failure — no release yet,
    network error, an unexpected body (e.g. a 404 page), a schema mismatch, or
    a local write failure — degrades silently (never raises) AND invalidates
    any payload retained from an earlier successful run, so the offline
    Tier-1 channel table is the floor
    rather than a stale prior release's links being served as current.

    ``source_url`` defaults to the fixed GitHub release asset URL; tests point it
    at a local HTTP server to exercise the real ``urlopen`` path against a real
    socket instead of faking the response.
    """
    destination = repo_root.joinpath(*_DOWNLOAD_LATEST_STATIC_PATH)
    endpoint = urlsplit(source_url)
    if endpoint.scheme not in {"http", "https"} or endpoint.hostname is None:
        _invalidate_download_latest(destination, f"download-latest.json unavailable (invalid URL: {source_url})")
        return
    try:
        port = endpoint.port
    except ValueError as exc:
        _invalidate_download_latest(destination, f"download-latest.json unavailable ({exc})")
        return
    body = _read_download_latest_body(endpoint, endpoint.hostname, port, destination)
    if body is None:
        return
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        _invalidate_download_latest(destination, "download-latest.json response was not JSON")
        return
    if not isinstance(payload, dict) or payload.get("schema_name") != _DOWNLOAD_LATEST_SCHEMA:
        _invalidate_download_latest(destination, "download-latest.json was not the expected payload")
        return
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(body)
    except OSError as exc:
        _invalidate_download_latest(destination, f"download-latest.json could not be written ({exc})")
        return
    print(f"Refreshed {destination.relative_to(repo_root)} from the latest release.", flush=True)
