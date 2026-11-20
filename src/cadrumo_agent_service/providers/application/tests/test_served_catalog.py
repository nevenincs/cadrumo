"""The catalog the service relays conforms to the agent's pinned schema with only the service's changes."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from pydantic import JsonValue

from cadrumo_client.contracts.model_runs import ModelRunTaskKind

from .. import served_catalog as served_catalog_module
from ..served_catalog import PinnedSchemaError, catalog_nonconformance, pinned_agent_components, served_schema
from .served_catalog_documents import changed, declared_catalog, served_catalog

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_the_pinned_schema_is_the_file_its_pin_names_and_carries_the_agent_catalog() -> None:
    components = pinned_agent_components()

    assert {"ProviderCatalogResponse", "ProviderCatalogRecordResponse", "DeclaredProviderCatalog"} <= set(components)


def test_a_pinned_schema_that_is_not_the_pinned_file_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    real = served_catalog_module._pinned_bytes

    def altered(name: str) -> bytes:
        data = real(name)
        return data if name == "pin.json" else data.replace(b'"openapi"', b'"openapi" ', 1)

    pinned_agent_components.cache_clear()
    monkeypatch.setattr(served_catalog_module, "_pinned_bytes", altered)
    try:
        with pytest.raises(PinnedSchemaError):
            pinned_agent_components()
    finally:
        monkeypatch.undo()
        pinned_agent_components.cache_clear()


def test_every_reference_of_the_served_schema_names_one_of_its_definitions() -> None:
    defs = served_schema()
    named = {
        reference.rsplit("/", 1)[-1]
        for reference in json.dumps(defs).split('"$ref": "')[1:]
        for reference in [reference.split('"', 1)[0]]
    }

    assert named <= set(defs)


@pytest.mark.parametrize("answer", [served_catalog(), declared_catalog()], ids=["served", "declared"])
def test_the_catalogs_the_service_relays_conform(answer: dict[str, object]) -> None:
    assert catalog_nonconformance(answer) is None


def test_a_local_model_whose_server_nobody_read_may_leave_out_whether_it_is_installed() -> None:
    answer = changed(served_catalog(), ("providers", 1, "catalog", "models", 0, "installed"), ...)

    assert catalog_nonconformance(answer) is None


@pytest.mark.parametrize(
    ("path", "value", "place"),
    [
        (("providers", 0, "model_download"), ..., "$.providers[0]"),
        (("providers", 0, "model_download"), "sometimes", "$.providers[0].model_download"),
        (("providers", 0, "carrier"), "pigeon", "$.providers[0]"),
        (("providers", 0, "transport"), "pigeon-post", "$.providers[0].transport"),
        (("providers", 0, "health", "checked_at"), "pigeon-time", "$.providers[0].health.checked_at"),
        (("providers", 0, "catalog", "state", "checked_at"), "10:00:00", "$.providers[0].catalog.state.checked_at"),
    ],
    ids=["unstamped", "unknown-stamp", "unserved-field", "unknown-transport", "not-a-time", "time-without-date"],
)
def test_a_served_catalog_that_departs_is_named_by_place_and_rule_never_by_value(
    path: tuple[str | int, ...], value: object, place: str
) -> None:
    departure = catalog_nonconformance(changed(served_catalog(), path, value))

    assert departure is not None
    assert departure.startswith(place)
    assert "pigeon" not in departure


def test_a_time_without_its_offset_is_a_departure() -> None:
    without_offset = datetime.now(UTC).replace(tzinfo=None).isoformat()
    answer = changed(served_catalog(), ("providers", 0, "health", "checked_at"), without_offset)

    assert catalog_nonconformance(answer) == "$.providers[0].health.checked_at format"


def test_a_declared_lane_without_its_stamp_is_a_departure() -> None:
    answer = changed(declared_catalog(), ("catalog", "providers", 0, "model_download"), ...)

    assert catalog_nonconformance(answer) is not None


@pytest.mark.parametrize(
    ("answer", "path"),
    [(served_catalog(), ("task_kinds",)), (declared_catalog(), ("catalog", "task_kinds"))],
    ids=["served", "declared"],
)
def test_a_catalog_without_its_task_kinds_is_a_departure(
    answer: dict[str, JsonValue], path: tuple[str | int, ...]
) -> None:
    assert catalog_nonconformance(changed(answer, path, ...)) is not None


def test_a_lane_whose_background_requests_honour_effort_conforms() -> None:
    answer = changed(served_catalog(), ("providers", 0, "background_requests", "options"), ["effort"])

    assert catalog_nonconformance(answer) is None


def test_the_task_kinds_a_run_names_are_the_agent_s_pinned_background_task_kinds() -> None:
    """A tax run names its kind in the agent's own spelling, so the setting it keys is one the window can offer."""
    pinned = pinned_agent_components()["BackgroundTaskKind"]["enum"]

    assert [kind.value for kind in ModelRunTaskKind] == pinned
