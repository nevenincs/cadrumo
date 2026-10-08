"""Serve review requests with exact body, origin, path and state admission."""

from __future__ import annotations

import json
import socket
import socketserver
import sqlite3
from collections.abc import Callable, Mapping
from hashlib import sha256
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from typing import Final, override
from urllib.parse import parse_qs, unquote, urlsplit

from pydantic import BaseModel, ConfigDict, Field, StrictBool, ValidationError

from dev._paths import UTF_8

from ._review_catalogue import CatalogueFrame, ElementView, RunView
from ._review_payloads import state_payload
from ._review_server_contracts import _IMMUTABLE, KEEPALIVE_SECONDS, PAGE_PATH, REQUEST_BODY_LIMIT
from ._review_state import ReviewState
from ._review_store import (
    InvalidNoteError,
    NoteNotFoundError,
    ReviewStoreVersionError,
)
from ._review_thumbnails import render_thumbnail


def _first(query: Mapping[str, list[str]], name: str) -> str | None:
    values = query.get(name)
    return values[0] if values else None


_DIGEST_PATTERN: Final[str] = r"^[0-9a-f]{64}$"


class _ElementReference(BaseModel):
    """A write names the element by run and key, and the images the reviewer saw by the element's digest."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run: str
    element: str
    element_sha256: str = Field(pattern=_DIGEST_PATTERN)


class _PointedFrame(BaseModel):
    """The frame on screen when a note was written, and the digest of the image shown."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    stem: str
    png_sha256: str = Field(pattern=_DIGEST_PATTERN)


class _NoteRequest(_ElementReference):
    body: str
    frame: _PointedFrame | None = None


class _ReviewedRequest(_ElementReference):
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
        """Record a note, resolve or reopen one, or sign an element off."""
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

    def _element_of(self, request: _ElementReference) -> ElementView:
        view = self.state.catalogue.run(request.run)
        element = None if view is None else view.element(request.element)
        if element is None:
            message = f"run {request.run!r} holds no frame of element {request.element!r}"
            raise _RequestRefusedError(HTTPStatus.NOT_FOUND, message)
        return element

    def _create_note(self) -> None:
        request = self._read_body(_NoteRequest)
        element = self._element_of(request)
        pointed: tuple[str, str] | None = None
        if request.frame is not None:
            frame = next((frame for frame in element.frames if frame.stem == request.frame.stem), None)
            if frame is None:
                message = f"element {element.key!r} holds no frame {request.frame.stem!r}"
                raise _RequestRefusedError(HTTPStatus.NOT_FOUND, message)
            pointed = (frame.key, request.frame.png_sha256)
        try:
            note = self.state.store.add_note(
                element_key=element.key,
                run=request.run,
                element_sha256=request.element_sha256,
                frame=pointed,
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
        """Sign an element off, only at the images the reviewer was shown, or withdraw the sign-off."""
        request = self._read_body(_ReviewedRequest)
        element = self._element_of(request)
        if not request.reviewed:
            self.state.store.clear_sign_off(element.key)
            self.state.bump()
            self._send_json(HTTPStatus.OK, {"element_key": element.key, "cleared": True})
            return
        # The sign-off records the frames the run holds now, so they must be
        # the ones the page showed: a frame that settled since would otherwise
        # be approved unseen.
        if request.element_sha256 != element.digest:
            message = f"element {element.key!r} changed since the page loaded it; look again before signing off"
            raise _RequestRefusedError(HTTPStatus.CONFLICT, message)
        mark = self.state.store.sign_off(element_key=element.key, run=request.run, frames=element.frame_digests)
        self.state.bump()
        self._send_json(HTTPStatus.OK, mark.model_dump(mode="json"))

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
