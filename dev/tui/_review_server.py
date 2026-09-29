"""A development server for reviewing the visual inventory from another device.

A full render runs for well over an hour and its frames are only useful once
someone has looked at them. This server lets that happen from a phone, while
the render is still going: it serves every run under the review tree, pushes a
change event whenever a frame settles on disk, and records the reviewer's
notes and sign-offs in the durable store rather than in the browser.

It binds to this machine's tailnet address by default, as the local Tailscale
client reports it, and never to every interface: the tailnet is the access
control, so the server has no login of its own and must not be reachable from
anywhere the tailnet does not already admit. Writes are accepted only as ``application/json``, which a cross-origin
page cannot send without a CORS preflight that this server never answers.

Standard library only, apart from Pillow for thumbnails: a review aid should
not add a web framework to the dependency set.
"""

from __future__ import annotations

import io
import ipaddress
import json
import shutil
import socket
import socketserver
import sqlite3
import sys
import threading
from collections import OrderedDict
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial
from hashlib import sha256
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Final, override
from urllib.parse import parse_qs, unquote, urlsplit

from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, StrictBool, ValidationError

from dev._paths import REPO_ROOT, UTF_8
from dev.packaging.command_execution import run_command

from ._artifacts import DEFAULT_RUN_NAME
from ._review_catalogue import CatalogueFrame, ReviewCatalogue, RunView, viewport_grid
from ._review_store import (
    InvalidNoteError,
    NoteNotFoundError,
    ReviewStore,
    ReviewStoreVersionError,
    image_state,
)

DEFAULT_REVIEW_PORT: Final[int] = 8740
TAILSCALE_TIMEOUT_SECONDS: Final[float] = 10.0
WATCH_INTERVAL_SECONDS: Final[float] = 1.0
KEEPALIVE_SECONDS: Final[float] = 15.0
"""Idle gap between comment lines on the event stream, so a mobile network or
a sleeping tab notices a dead connection and reconnects."""

THUMBNAIL_WIDTH: Final[int] = 480
THUMBNAIL_CACHE_SIZE: Final[int] = 1024
REQUEST_BODY_LIMIT: Final[int] = 64 * 1024
PAGE_PATH: Final[Path] = Path(__file__).with_name("review_page.html")
"""Read on every request, so an edit to the page shows on the next reload."""

_IMMUTABLE: Final[str] = "public, max-age=31536000, immutable"


class TailnetUnavailableError(RuntimeError):
    """This machine has no tailnet address to bind."""


class _TailscaleSelf(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    tailscale_ips: tuple[str, ...] = Field(default=(), alias="TailscaleIPs")
    dns_name: str = Field(default="", alias="DNSName")


class _TailscaleStatus(BaseModel):
    """The two facts this server needs from ``tailscale status --json``; the rest is ignored."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    backend_state: str = Field(alias="BackendState")
    self_node: _TailscaleSelf | None = Field(default=None, alias="Self")


@dataclass(frozen=True)
class TailnetNode:
    """This machine as Tailscale describes it."""

    address: str
    """The node's tailnet IPv4 address; the only address the server binds by default."""
    name: str | None
    """The node's MagicDNS name, when MagicDNS gives it one."""


def parse_tailnet_status(payload: str) -> TailnetNode:
    """Read this node's address and name out of ``tailscale status --json`` output.

    Anything short of a running client with an IPv4 address is refused: the
    caller would otherwise have nothing safe to bind.
    """
    try:
        status = _TailscaleStatus.model_validate_json(payload)
    except ValidationError:
        raise TailnetUnavailableError("tailscale status printed something this tool cannot read") from None
    if status.backend_state != "Running":
        raise TailnetUnavailableError(f"Tailscale is {status.backend_state}, not Running")
    node = status.self_node
    addresses = () if node is None else tuple(value for value in node.tailscale_ips if _is_ipv4(value))
    if node is None or not addresses:
        raise TailnetUnavailableError("Tailscale reports no IPv4 tailnet address for this machine")
    return TailnetNode(address=addresses[0], name=node.dns_name.rstrip(".") or None)


def tailnet_node() -> TailnetNode:
    """Ask the local Tailscale client for this machine's tailnet address and name.

    Tailscale is the authority on its own addressing, so the answer is read
    from the client rather than inferred from routes or address ranges.
    """
    executable = shutil.which("tailscale")
    if executable is None:
        raise TailnetUnavailableError("the tailscale command is not on PATH")
    try:
        result = run_command(
            [executable, "status", "--json", "--peers=false"],
            cwd=REPO_ROOT,
            errors="replace",
            timeout_seconds=TAILSCALE_TIMEOUT_SECONDS,
        )
    except OSError as failure:
        raise TailnetUnavailableError(f"tailscale status could not run: {failure}") from failure
    if result.returncode != 0:
        reason = _first_line(result.stderr) or _first_line(result.stdout) or "no output"
        raise TailnetUnavailableError(f"tailscale status exited {result.returncode}: {reason}")
    return parse_tailnet_status(result.stdout)


def _is_ipv4(value: str) -> bool:
    try:
        return ipaddress.ip_address(value).version == 4
    except ValueError:
        return False


def is_wildcard_host(host: str) -> bool:
    """Whether binding ``host`` would listen on every interface."""
    if not host.strip():
        return True
    try:
        return ipaddress.ip_address(host.strip("[]")).is_unspecified
    except ValueError:
        return False


def render_thumbnail(payload: bytes, *, width: int = THUMBNAIL_WIDTH) -> bytes:
    """A WebP reduction of a PNG frame, for the grid on a phone."""
    with Image.open(io.BytesIO(payload)) as source:
        image = source.convert("RGB")
    if image.width > width:
        height = max(1, round(image.height * width / image.width))
        image = image.resize((width, height), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, format="WEBP", quality=82, method=4)
    return buffer.getvalue()


class ThumbnailCache:
    """Thumbnails by PNG digest, least recently used first out."""

    def __init__(self, capacity: int = THUMBNAIL_CACHE_SIZE) -> None:
        """Hold at most ``capacity`` thumbnails in memory."""
        self._capacity = capacity
        self._entries: OrderedDict[str, bytes] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, digest: str) -> bytes | None:
        """The cached thumbnail for a PNG digest."""
        with self._lock:
            cached = self._entries.get(digest)
            if cached is not None:
                self._entries.move_to_end(digest)
            return cached

    def put(self, digest: str, thumbnail: bytes) -> None:
        """Keep a thumbnail, evicting the least recently used past capacity."""
        with self._lock:
            self._entries[digest] = thumbnail
            self._entries.move_to_end(digest)
            while len(self._entries) > self._capacity:
                self._entries.popitem(last=False)


class ReviewState:
    """What every request thread shares: the catalogue, the store, a change counter."""

    def __init__(self, catalogue: ReviewCatalogue, store: ReviewStore) -> None:
        """Share ``catalogue`` and ``store`` across the server's threads."""
        self.catalogue = catalogue
        self.store = store
        self.thumbnails = ThumbnailCache()
        self.stopping = threading.Event()
        self._changed = threading.Condition()
        self._generation = 0

    @property
    def generation(self) -> int:
        """How many changes the server has announced; clients refetch when it moves."""
        with self._changed:
            return self._generation

    def bump(self) -> int:
        """Announce a change to every waiting event stream."""
        with self._changed:
            self._generation += 1
            self._changed.notify_all()
            return self._generation

    def wait_for_change(self, seen: int, timeout: float) -> int:
        """Block until the generation moves past ``seen``, the server stops, or ``timeout`` passes."""
        with self._changed:
            self._changed.wait_for(lambda: self._generation != seen or self.stopping.is_set(), timeout)
            return self._generation

    def refresh(self) -> bool:
        """Rescan the runs, announcing a change when one is found."""
        changed = self.catalogue.refresh()
        if changed:
            self.bump()
        return changed

    def watch(self, interval: float) -> None:
        """Rescan every ``interval`` seconds until the server stops."""
        while not self.stopping.wait(interval):
            self.refresh()

    def stop(self) -> None:
        """Release every waiting event stream and end the watch loop."""
        self.stopping.set()
        with self._changed:
            self._changed.notify_all()


def state_payload(state: ReviewState, run_name: str | None) -> dict[str, object]:
    """Everything the page renders, for one run."""
    generation = state.generation
    runs = state.catalogue.runs()
    view = _choose_run(runs, run_name)
    frames = view.frames if view is not None else ()
    digests = {frame.key: frame.png_sha256 for frame in frames}
    notes = state.store.notes()
    latest = max((frame.modified_ns for frame in frames), default=None)
    return {
        "generation": generation,
        "runs": [{"name": run.name, "frames": len(run.frames)} for run in runs],
        "run": None if view is None else view.name,
        "frames": [] if view is None else [_frame_payload(view, frame) for frame in frames],
        "latest_frame_at": None if latest is None else _iso(latest),
        "manifest": None if view is None else _manifest_payload(view),
        "unrecognised": [] if view is None else list(view.unrecognised),
        "notes": [
            {**note.model_dump(mode="json"), "image_state": str(image_state(note, digests.get(note.frame_key)))}
            for note in notes
        ],
        "reviewed": {key: mark.model_dump(mode="json") for key, mark in state.store.reviewed().items()},
        "store": str(state.store.path),
    }


def _choose_run(runs: tuple[RunView, ...], name: str | None) -> RunView | None:
    by_name = {run.name: run for run in runs}
    if name is not None and name in by_name:
        return by_name[name]
    if DEFAULT_RUN_NAME in by_name:
        return by_name[DEFAULT_RUN_NAME]
    return runs[0] if runs else None


def _frame_payload(view: RunView, frame: CatalogueFrame) -> dict[str, object]:
    columns, rows, orientation = viewport_grid(frame.identity.viewport)
    record = view.recorded(frame)
    return {
        "stem": frame.stem,
        "key": frame.key,
        "surface": frame.identity.surface,
        "viewport": str(frame.identity.viewport),
        "theme": str(frame.identity.theme),
        "columns": columns,
        "rows": rows,
        "orientation": orientation,
        "digest": frame.png_sha256,
        "width": frame.width,
        "height": frame.height,
        "bytes": frame.size,
        "modified_at": _iso(frame.modified_ns),
        "text": frame.stem in view.texts,
        "recorded": None
        if record is None
        else {
            "geometry_findings": list(record.geometry_findings),
            "missing_glyphs": list(record.missing_glyphs),
            "elapsed_ms": record.elapsed_ms,
        },
    }


def _manifest_payload(view: RunView) -> dict[str, object]:
    if view.manifest_error is not None:
        return {"state": "unreadable", "detail": view.manifest_error}
    manifest = view.manifest
    if manifest is None:
        return {"state": "absent"}
    described = len(view.records)
    coherent = described == len(view.frames) == len(manifest.frames)
    return {
        "state": "current" if coherent else "earlier",
        "generated_at": manifest.generated_at,
        "described": described,
        "recorded_frames": len(manifest.frames),
        "spans_a_source_change": manifest.spans_a_source_change,
        "blocked_surfaces": list(manifest.blocked_surfaces),
        "failures": [
            {
                "key": failure.key,
                "kind": str(failure.kind),
                "attempts": failure.attempts,
                "reason": _first_line(failure.detail),
            }
            for failure in manifest.failures
        ],
        "skipped": [{"key": entry.key, "reason": entry.reason} for entry in manifest.skipped],
    }


def _first_line(text: str) -> str:
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return ""


def _iso(modified_ns: int) -> str:
    return datetime.fromtimestamp(modified_ns / 1e9, tz=UTC).isoformat(timespec="seconds")


def _first(query: Mapping[str, list[str]], name: str) -> str | None:
    values = query.get(name)
    return values[0] if values else None


class _FrameReference(BaseModel):
    """A write names the frame by run and stem, and the image the reviewer saw by digest."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run: str
    stem: str
    png_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class _NoteRequest(_FrameReference):
    body: str


class _ReviewedRequest(_FrameReference):
    reviewed: StrictBool


class _ResolvedRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    resolved: StrictBool


class _RequestRefusedError(Exception):
    """A request this server answers with an error status rather than a result."""

    def __init__(self, status: HTTPStatus, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


class ReviewRequestHandler(BaseHTTPRequestHandler):
    """The page, its JSON API, frame images and the change stream."""

    protocol_version = "HTTP/1.1"
    server_version = "cadrumo-tui-review"

    def __init__(
        self,
        request: socket.socket,
        client_address: tuple[str, int],
        server: socketserver.BaseServer,
        *,
        state: ReviewState,
    ) -> None:
        """Handle one connection against the shared review ``state``."""
        self.state = state
        super().__init__(request, client_address, server)

    @override
    def log_request(self, code: int | str = "-", size: int | str = "-") -> None:
        """Log failed requests only; a thumbnail grid would otherwise print hundreds of lines."""
        if isinstance(code, int) and code >= HTTPStatus.BAD_REQUEST:
            super().log_request(code, size)

    def do_GET(self) -> None:
        """Serve the page, the review state, frame images and the change stream."""
        url = urlsplit(self.path)
        parts = [unquote(part) for part in url.path.split("/") if part]
        query = parse_qs(url.query)
        match parts:
            case []:
                self._guarded(self._send_page)
            case ["events"]:
                self._stream_events()
            case ["api", "state"]:
                self._guarded(lambda: self._send_json(HTTPStatus.OK, state_payload(self.state, _first(query, "run"))))
            case ["image", run, name] if name.endswith(".png"):
                self._guarded(lambda: self._send_image(run, name.removesuffix(".png"), _first(query, "v")))
            case ["thumb", run, name] if name.endswith(".webp"):
                self._guarded(lambda: self._send_thumbnail(run, name.removesuffix(".webp"), _first(query, "v")))
            case ["text", run, name] if name.endswith(".txt"):
                self._guarded(lambda: self._send_text(run, name.removesuffix(".txt")))
            case _:
                self._send_error(HTTPStatus.NOT_FOUND, "no such page")

    def do_POST(self) -> None:
        """Record a note, resolve or reopen one, or sign a frame off."""
        parts = [unquote(part) for part in urlsplit(self.path).path.split("/") if part]
        match parts:
            case ["api", "notes"]:
                self._guarded(self._create_note)
            case ["api", "notes", note_id, "resolved"]:
                self._guarded(lambda: self._resolve_note(note_id))
            case ["api", "reviewed"]:
                self._guarded(self._set_reviewed)
            case _:
                self._send_error(HTTPStatus.NOT_FOUND, "no such endpoint")

    def do_DELETE(self) -> None:
        """Delete a note."""
        parts = [unquote(part) for part in urlsplit(self.path).path.split("/") if part]
        match parts:
            case ["api", "notes", note_id]:
                self._guarded(lambda: self._delete_note(note_id))
            case _:
                self._send_error(HTTPStatus.NOT_FOUND, "no such endpoint")

    def _guarded(self, action: Callable[[], None]) -> None:
        try:
            action()
        except _RequestRefusedError as refusal:
            self._send_error(refusal.status, refusal.message)
        except ReviewStoreVersionError as refusal:
            self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(refusal))
        except sqlite3.Error as failure:
            self._send_error(HTTPStatus.SERVICE_UNAVAILABLE, f"the notes store could not answer: {failure}")

    def _frame(self, run: str, stem: str) -> tuple[RunView, CatalogueFrame]:
        view = self.state.catalogue.run(run)
        frame = None if view is None else view.frame(stem)
        if view is None or frame is None:
            raise _RequestRefusedError(HTTPStatus.NOT_FOUND, f"run {run!r} holds no frame {stem!r}")
        return view, frame

    def _read_frame_bytes(self, frame: CatalogueFrame) -> tuple[bytes, bool]:
        """The PNG on disk, and whether it is still the image the catalogue digested."""
        try:
            payload = frame.png.read_bytes()
        except OSError as gone:
            raise _RequestRefusedError(HTTPStatus.NOT_FOUND, f"frame {frame.stem!r} is no longer on disk") from gone
        return payload, sha256(payload).hexdigest() == frame.png_sha256

    def _send_page(self) -> None:
        try:
            page = PAGE_PATH.read_bytes()
        except OSError as missing:
            raise _RequestRefusedError(HTTPStatus.INTERNAL_SERVER_ERROR, f"cannot read {PAGE_PATH.name}") from missing
        self._send_bytes(HTTPStatus.OK, page, "text/html; charset=utf-8", cache="no-cache")

    def _send_image(self, run: str, stem: str, version: str | None) -> None:
        _, frame = self._frame(run, stem)
        payload, intact = self._read_frame_bytes(frame)
        # A file mid-rewrite no longer matches its digest; it is served, but
        # never cached under a URL that names the digest it contradicts.
        cache = _IMMUTABLE if intact and version == frame.png_sha256 else "no-store"
        self._send_bytes(HTTPStatus.OK, payload, "image/png", cache=cache)

    def _send_thumbnail(self, run: str, stem: str, version: str | None) -> None:
        _, frame = self._frame(run, stem)
        thumbnail = self.state.thumbnails.get(frame.png_sha256)
        intact = thumbnail is not None
        if thumbnail is None:
            payload, intact = self._read_frame_bytes(frame)
            try:
                thumbnail = render_thumbnail(payload)
            except (OSError, ValueError) as unreadable:
                message = f"frame {stem!r} could not be read as an image"
                raise _RequestRefusedError(HTTPStatus.UNPROCESSABLE_ENTITY, message) from unreadable
            if intact:
                self.state.thumbnails.put(frame.png_sha256, thumbnail)
        cache = _IMMUTABLE if intact and version == frame.png_sha256 else "no-store"
        self._send_bytes(HTTPStatus.OK, thumbnail, "image/webp", cache=cache)

    def _send_text(self, run: str, stem: str) -> None:
        view, _ = self._frame(run, stem)
        path = view.text_path(stem)
        if path is None:
            raise _RequestRefusedError(HTTPStatus.NOT_FOUND, f"frame {stem!r} has no text reading")
        try:
            payload = path.read_bytes()
        except OSError as gone:
            raise _RequestRefusedError(HTTPStatus.NOT_FOUND, f"text for {stem!r} is no longer on disk") from gone
        self._send_bytes(HTTPStatus.OK, payload, "text/plain; charset=utf-8", cache="no-cache")

    def _read_body[RequestT: BaseModel](self, model: type[RequestT]) -> RequestT:
        content_type = self.headers.get("Content-Type", "").split(";")[0].strip().lower()
        if content_type != "application/json":
            raise _RequestRefusedError(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "send the body as application/json")
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            raise _RequestRefusedError(HTTPStatus.LENGTH_REQUIRED, "a Content-Length is required") from None
        if length < 0 or length > REQUEST_BODY_LIMIT:
            raise _RequestRefusedError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "the request body is too large")
        try:
            return model.model_validate_json(self.rfile.read(length))
        except ValidationError as invalid:
            problems = "; ".join(
                f"{'.'.join(str(part) for part in error['loc']) or 'body'}: {error['msg']}"
                for error in invalid.errors()
            )
            raise _RequestRefusedError(HTTPStatus.BAD_REQUEST, problems) from None

    def _frame_of(self, request: _FrameReference) -> CatalogueFrame:
        _, frame = self._frame(request.run, request.stem)
        return frame

    def _create_note(self) -> None:
        request = self._read_body(_NoteRequest)
        frame = self._frame_of(request)
        try:
            note = self.state.store.add_note(
                frame_key=frame.key,
                run=request.run,
                png_sha256=request.png_sha256,
                body=request.body,
            )
        except InvalidNoteError as refusal:
            raise _RequestRefusedError(HTTPStatus.BAD_REQUEST, str(refusal)) from None
        self.state.bump()
        self._send_json(HTTPStatus.CREATED, note.model_dump(mode="json"))

    def _resolve_note(self, note_id: str) -> None:
        identifier = _note_id(note_id)
        request = self._read_body(_ResolvedRequest)
        try:
            note = self.state.store.set_resolved(identifier, resolved=request.resolved)
        except NoteNotFoundError as missing:
            raise _RequestRefusedError(HTTPStatus.NOT_FOUND, str(missing)) from None
        self.state.bump()
        self._send_json(HTTPStatus.OK, note.model_dump(mode="json"))

    def _delete_note(self, note_id: str) -> None:
        identifier = _note_id(note_id)
        try:
            self.state.store.delete_note(identifier)
        except NoteNotFoundError as missing:
            raise _RequestRefusedError(HTTPStatus.NOT_FOUND, str(missing)) from None
        self.state.bump()
        self._send_json(HTTPStatus.OK, {"deleted": identifier})

    def _set_reviewed(self) -> None:
        request = self._read_body(_ReviewedRequest)
        frame = self._frame_of(request)
        if request.reviewed:
            mark = self.state.store.mark_reviewed(frame_key=frame.key, png_sha256=request.png_sha256)
            self.state.bump()
            self._send_json(HTTPStatus.OK, mark.model_dump(mode="json"))
            return
        self.state.store.clear_reviewed(frame.key)
        self.state.bump()
        self._send_json(HTTPStatus.OK, {"frame_key": frame.key, "cleared": True})

    def _stream_events(self) -> None:
        """Hold the connection open and write one event per announced change."""
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        seen = self.state.generation
        try:
            self.wfile.write(f"retry: 3000\nevent: change\ndata: {seen}\n\n".encode(UTF_8))
            self.wfile.flush()
            while not self.state.stopping.is_set():
                current = self.state.wait_for_change(seen, KEEPALIVE_SECONDS)
                if current == seen:
                    self.wfile.write(b": keep-alive\n\n")
                else:
                    seen = current
                    self.wfile.write(f"event: change\ndata: {seen}\n\n".encode(UTF_8))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            return

    def _send_json(self, status: HTTPStatus, payload: object) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode(UTF_8)
        self._send_bytes(status, body, "application/json; charset=utf-8", cache="no-store")

    def _send_error(self, status: HTTPStatus, message: str) -> None:
        # The body of a refused write may be unread, and on a kept-alive
        # connection those bytes would be parsed as the next request.
        self.close_connection = True
        self._send_json(status, {"error": message})

    def _send_bytes(self, status: HTTPStatus, body: bytes, content_type: str, *, cache: str) -> None:
        try:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", cache)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            if self.close_connection:
                self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            self.close_connection = True


def _note_id(text: str) -> int:
    try:
        return int(text)
    except ValueError:
        raise _RequestRefusedError(HTTPStatus.NOT_FOUND, f"no note {text!r}") from None


class ReviewHTTPServer(ThreadingHTTPServer):
    """One thread per connection; event streams must not hold up shutdown."""

    daemon_threads = True
    # On Windows SO_REUSEADDR lets a second server bind a port already in use
    # and steal half its connections, so a clash must fail loudly instead.
    allow_reuse_address = sys.platform != "win32"

    def __init__(self, address: tuple[str, int], state: ReviewState) -> None:
        """Listen on ``address`` and answer every request against ``state``."""
        if ":" in address[0]:
            self.address_family = socket.AF_INET6
        super().__init__(address, partial(ReviewRequestHandler, state=state))
        self.state = state


def serve(server: ReviewHTTPServer, *, interval: float = WATCH_INTERVAL_SECONDS) -> None:
    """Watch the runs and answer requests until interrupted."""
    watcher = threading.Thread(target=server.state.watch, args=(interval,), name="tui-review-watch", daemon=True)
    watcher.start()
    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        server.state.stop()
        server.server_close()
        watcher.join(timeout=interval * 2)


__all__ = [
    "DEFAULT_REVIEW_PORT",
    "KEEPALIVE_SECONDS",
    "PAGE_PATH",
    "TAILSCALE_TIMEOUT_SECONDS",
    "THUMBNAIL_WIDTH",
    "WATCH_INTERVAL_SECONDS",
    "ReviewHTTPServer",
    "ReviewRequestHandler",
    "ReviewState",
    "TailnetNode",
    "TailnetUnavailableError",
    "ThumbnailCache",
    "is_wildcard_host",
    "parse_tailnet_status",
    "render_thumbnail",
    "serve",
    "state_payload",
    "tailnet_node",
]
