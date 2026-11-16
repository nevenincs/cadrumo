"""The administration boundary relays a catalog only when it is the catalog the agent's pinned schema states."""

from __future__ import annotations

import json
import socket
from uuid import UUID, uuid4

import pytest
from pydantic import JsonValue

from ...admin import AdminServer
from ...providers.application.tests.served_catalog_documents import changed, declared_catalog, served_catalog
from .admin_wire_support import read_frame, send_frame

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_BEARER = b"a" * 64


class _CatalogTarget:
    """Answers every catalog request with one prepared answer, as the service would."""

    def __init__(self, answer: JsonValue) -> None:
        self.answer = answer

    def admin(self, action: str, **metadata: object) -> JsonValue:
        assert action == "catalog"
        return self.answer


def _catalog_answer(answer: JsonValue) -> object:
    server = AdminServer(_CatalogTarget(answer), bearer=bytearray(_BEARER))
    try:
        with socket.create_connection(("127.0.0.1", server.port), timeout=10) as stream:
            send_frame(stream, _BEARER)
            send_frame(stream, json.dumps({"version": 1, "request_id": str(uuid4()), "action": "catalog"}).encode())
            return read_frame(stream)["result"]
    finally:
        server.close()


@pytest.mark.parametrize("answer", [served_catalog(), declared_catalog()], ids=["served", "declared"])
def test_a_catalog_the_agent_schema_states_is_relayed_as_it_is(answer: dict[str, JsonValue]) -> None:
    assert _catalog_answer(answer) == answer


def test_a_catalog_that_departs_is_refused_unavailable_with_its_log_reference() -> None:
    departing = changed(served_catalog(), ("providers", 0, "transport"), "pigeon-post")

    result = _catalog_answer(departing)

    assert isinstance(result, dict)
    assert result.keys() == {"kind", "code", "log_ref"}
    assert (result["kind"], result["code"]) == ("refused", "catalog_unavailable")
    UUID(str(result["log_ref"]))


def test_a_refusal_is_relayed_as_it_is() -> None:
    refusal: JsonValue = {"kind": "refused", "code": "service_stopping"}

    assert _catalog_answer(refusal) == refusal
