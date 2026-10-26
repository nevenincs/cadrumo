"""Shared support for local-vision evidence tests."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from http import HTTPStatus
from io import BytesIO
from queue import Queue
from typing import ClassVar, override

from PIL import Image

from ..core.config import override_settings
from ..core.type_adapters import STR_KEYED_MAPPING_ADAPTER
from .loopback_llm import (
    SilentLoopbackHandler,
    ollama_chat_reply,
    read_json_body,
    serving_loopback,
    write_json_response,
)


def json_object(value: object) -> dict[str, object]:
    """Narrow one decoded JSON value to a string-keyed object for typed subscripting."""
    return STR_KEYED_MAPPING_ADAPTER.validate_python(value)


def json_array(value: object) -> list[object]:
    assert isinstance(value, list)
    return list(value)


def png_image() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (120, 80), "white").save(buffer, format="PNG")
    return buffer.getvalue()


class _ObservedOllamaRequest(SilentLoopbackHandler):
    """Loopback Ollama endpoint that serves inventory, residency and chat wire contracts."""

    events: ClassVar[Queue[dict[str, object]]]
    resident_events: ClassVar[Queue[dict[str, object]]]
    content: ClassVar[str]
    installed_models: ClassVar[tuple[str, ...]] = ()
    """Model ids reported installed on ``GET /api/tags``.

    The readers ask the runtime whether their model is installed before they
    read, so an endpoint that served chat while reporting no inventory would
    describe a runtime that cannot exist.
    """

    @override
    def do_GET(self) -> None:
        """Report the installed inventory, and a measured-empty resident set."""
        self.resident_events.put({"method": "GET", "path": self.path})
        names = self.installed_models if self.path == "/api/tags" else ()
        write_json_response(
            self, {"models": [{"name": name, "model": name, "size": 0} for name in names]}, status=HTTPStatus.OK
        )

    @override
    def do_POST(self) -> None:
        self.events.put({"body": read_json_body(self)})
        write_json_response(
            self,
            ollama_chat_reply(self.content, model="llava-test", prompt_eval_count=9, eval_count=5),
            status=HTTPStatus.OK,
        )


def run_against_loopback_ollama[T](
    content: str, call: Callable[[], T], *, installed: Iterable[str] | None = None
) -> tuple[dict[str, object], T]:
    """Stand up a loopback Ollama returning ``content`` and run ``call()`` against it.

    ``installed`` is the inventory the runtime reports; by default the models
    the text and vision readers are configured to load.
    """
    events: Queue[dict[str, object]] = Queue()
    resident_events: Queue[dict[str, object]] = Queue()
    _ObservedOllamaRequest.events = events
    _ObservedOllamaRequest.resident_events = resident_events
    _ObservedOllamaRequest.content = content
    # Captured here rather than read in the handler: the server answers on its
    # own thread, which does not see this process's settings override.
    _ObservedOllamaRequest.installed_models = tuple(
        installed if installed is not None else ("synthetic-text-extraction", "synthetic-vision-transcription")
    )
    with (
        serving_loopback(_ObservedOllamaRequest, path="/api/chat") as endpoint,
        override_settings(cadrumo_llm_ollama_chat_url=endpoint),
    ):
        result = call()
    observed = events.get_nowait()
    runtime_requests: list[dict[str, object]] = []
    while not resident_events.empty():
        runtime_requests.append(resident_events.get_nowait())
    if runtime_requests:
        observed["runtime_requests"] = runtime_requests
    return observed, result
