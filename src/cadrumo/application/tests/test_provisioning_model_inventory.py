"""Real-behavior tests for the installed-model inventory.

No mock, patch or stub reaches the code under test. Runtime interaction runs
against a real :class:`~http.server.ThreadingHTTPServer` speaking the runtime's
``/api/tags`` wire shape over real ``httpx``.
"""

from __future__ import annotations

from collections.abc import Iterator
from http import HTTPStatus
from queue import Queue
from typing import ClassVar, override

import pytest

from ...core.config import override_settings
from ...tests.loopback_llm import (
    SilentLoopbackHandler,
    serving_loopback,
    write_json_response,
)
from ..provisioning_runtime import InstalledModel, read_installed_models

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

GIB = 1024**3

VISION = "synthetic-vision-model"


class _ModelStoreLoopbackHandler(SilentLoopbackHandler):
    """A real endpoint speaking the runtime's ``/api/tags`` wire shape over the store in ``models``.

    The inventory rows carry a ``size`` the shared well-formed tags envelope
    does not model, so the body stays local here while the plumbing is shared.
    """

    models: ClassVar[list[dict[str, object]]] = []
    events: ClassVar[Queue[dict[str, object]]]

    @override
    def do_GET(self) -> None:
        self.events.put({"method": "GET", "path": self.path})
        write_json_response(self, {"models": list(self.models)}, status=HTTPStatus.OK)


@pytest.fixture
def store() -> Iterator[tuple[str, Queue[dict[str, object]]]]:
    """Serve a real runtime store on a loopback port; yield its chat URL and event queue."""
    events: Queue[dict[str, object]] = Queue()
    _ModelStoreLoopbackHandler.events = events
    _ModelStoreLoopbackHandler.models = []
    with serving_loopback(_ModelStoreLoopbackHandler, path="/api/chat") as chat_url:
        yield (chat_url, events)


# ---------------------------------------------------------------------------
# the on-disk inventory read
# ---------------------------------------------------------------------------


def test_installed_inventory_is_read_from_the_tags_endpoint(store: tuple[str, Queue[dict[str, object]]]) -> None:
    """Installed models come from ``/api/tags``, the on-disk inventory, not ``/api/ps``."""
    chat_url, events = store
    _ModelStoreLoopbackHandler.models = [{"name": VISION, "size": 4 * GIB}]
    with override_settings(cadrumo_llm_ollama_chat_url=chat_url):
        installed = read_installed_models()
    assert installed == (InstalledModel(name=VISION, size_bytes=4 * GIB),)
    assert events.get_nowait() == {"method": "GET", "path": "/api/tags"}


def test_an_unreachable_runtime_reads_as_unmeasured_not_as_empty() -> None:
    """``None`` and ``()`` are different states; an empty store is a fact, an unreachable one is not."""
    with override_settings(cadrumo_llm_ollama_chat_url="http://127.0.0.1:1/api/chat"):
        assert read_installed_models() is None
