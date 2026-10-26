"""One lane's live entries, read from a document shaped as the agent's gateway serves its catalogue."""

from __future__ import annotations

from typing import Any, Final

import pytest

from cadrumo_client.contracts.model_runs import ModelRunMediaKind

from ...providers.application.ports import LiveLaneBackground
from ...providers.domain.catalog import BackgroundOption
from ..served_catalog_models import ServedCatalogModels

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_DIGEST: Final = "sha256:" + "2" * 64


def _entry(model: str, **overrides: Any) -> dict[str, Any]:
    """One served model entry with the fields the agent serves, most of which the adapter never reads."""
    entry: dict[str, Any] = {
        "entry_id": f"local:{model}",
        "model": model,
        "display_name": model,
        "description": None,
        "capabilities": [],
        "native_control_ids": [],
        "efforts": [],
        "default_effort": None,
        "multi_agent_generation": None,
        "vision": True,
        "size_bytes": 2_000,
        "context_length": 8192,
        "licence": {"spdx": None, "name": "Licence supplied with the model", "digest": _DIGEST},
        "installed": True,
    }
    entry.update(overrides)
    return entry


def _document(*models: object, provider: str = "local", transport: str = "api") -> dict[str, Any]:
    record = {
        "provider_id": provider,
        "transport": transport,
        "catalog": {"schema_version": 2, "models": list(models), "recommended": {}},
        "background_requests": {"text": "proven", "image": "proven", "pdf": "unsupported", "options": []},
    }
    other = {"provider_id": "example", "transport": "cli", "catalog": {"models": [_entry("synthetic-other:1")]}}
    return {"api_version": "v1", "providers": [other, record]}


def test_the_lanes_entries_are_read_with_their_facts_and_nothing_else() -> None:
    models = ServedCatalogModels(
        lambda: _document(
            _entry("synthetic-installed:1"),
            _entry("synthetic-plain:1", vision=None, size_bytes=None, context_length=None, licence=None),
        )
    )

    entries = models.lane_models("local", "api")

    assert entries is not None
    assert [entry.id for entry in entries] == ["synthetic-installed:1", "synthetic-plain:1"]
    installed, plain = entries
    assert installed.licence is not None
    assert (installed.vision, installed.size_bytes, installed.context_length, installed.licence.digest) == (
        True,
        2_000,
        8192,
        _DIGEST,
    )
    assert (plain.vision, plain.size_bytes, plain.context_length, plain.licence) == (None, None, None, None)


def test_no_running_agent_is_no_live_catalogue_and_an_unlisted_lane_lists_nothing() -> None:
    assert ServedCatalogModels(lambda: None).lane_models("local", "api") is None
    assert ServedCatalogModels(lambda: _document(_entry("synthetic-installed:1"))).lane_models("absent", "api") == ()


_AGENT_MODEL_ID_LENGTH: Final = 512
"""cadrumo-agent's longest model id in its served catalogue."""


def test_an_entry_at_the_agent_s_bounds_is_read() -> None:
    """A zero size is the agent's own value for an empty or unknown size; the longest id it serves is read too."""
    longest = "m" * _AGENT_MODEL_ID_LENGTH
    models = ServedCatalogModels(lambda: _document(_entry("synthetic-empty:1", size_bytes=0), _entry(longest)))

    entries = models.lane_models("local", "api")

    assert entries is not None
    assert [(entry.id, entry.size_bytes) for entry in entries] == [("synthetic-empty:1", 0), (longest, 2_000)]


@pytest.mark.parametrize(
    "document",
    [
        pytest.param(_document(_entry("synthetic-installed:1", size_bytes=-1)), id="size-negative"),
        pytest.param(_document(_entry("synthetic-installed:1", context_length=-1)), id="context-negative"),
        pytest.param(_document(_entry("synthetic-installed:1", vision="yes")), id="vision-not-a-bool"),
        pytest.param(_document(_entry("synthetic-installed:1", size_bytes="2000")), id="size-not-an-integer"),
        pytest.param(
            _document(_entry("synthetic-installed:1", licence={"spdx": None, "name": "x", "digest": "sha256:zz"})),
            id="licence-digest-malformed",
        ),
        pytest.param(
            _document(
                _entry("synthetic-installed:1", licence={"spdx": None, "name": "x", "digest": _DIGEST, "text": "t"})
            ),
            id="licence-unknown-field",
        ),
        pytest.param(
            _document({key: value for key, value in _entry("synthetic-installed:1").items() if key != "vision"}),
            id="vision-missing",
        ),
        pytest.param(
            _document({key: value for key, value in _entry("synthetic-installed:1").items() if key != "model"}),
            id="model-missing",
        ),
        pytest.param(_document(_entry("")), id="model-empty"),
        pytest.param(_document(_entry("m" * (_AGENT_MODEL_ID_LENGTH + 1))), id="model-id-past-the-agent-s-bound"),
        pytest.param(_document(_entry("synthetic-installed:1"), "not-an-entry"), id="entry-not-an-object"),
        pytest.param(
            {"api_version": "v1", "providers": [{"provider_id": "local", "transport": "api"}]}, id="no-catalog"
        ),
    ],
)
def test_a_lane_whose_served_entries_do_not_validate_yields_no_live_catalogue(document: dict[str, Any]) -> None:
    assert ServedCatalogModels(lambda: document).lane_models("local", "api") is None


def _with_background(support: object) -> dict[str, Any]:
    document = _document(_entry("synthetic-installed:1"))
    document["providers"][1]["background_requests"] = support
    return document


def test_a_lanes_background_support_is_read_as_its_media_and_honoured_options() -> None:
    support = {
        "text": "proven",
        "accepts_images": True,
        "accepts_pdfs": False,
        "options": ["response_schema", "seed", 7, "temperature"],
    }

    background = ServedCatalogModels(lambda: _with_background(support)).lane_background("local", "api")

    assert background == LiveLaneBackground(
        accepted_media=(ModelRunMediaKind.IMAGE,),
        options=(BackgroundOption.TEMPERATURE, BackgroundOption.RESPONSE_SCHEMA),
    )


@pytest.mark.parametrize(
    ("support", "expected"),
    [
        pytest.param(
            {"accepts_images": "yes", "accepts_pdfs": True, "options": ["temperature"]},
            LiveLaneBackground(accepted_media=None, options=(BackgroundOption.TEMPERATURE,)),
            id="media-flag-not-a-bool",
        ),
        pytest.param(
            {"accepts_images": False, "accepts_pdfs": False, "options": "temperature"},
            LiveLaneBackground(accepted_media=(), options=()),
            id="options-not-a-list",
        ),
        pytest.param(None, None, id="no-background-record"),
    ],
)
def test_background_support_the_document_does_not_state_reads_as_unknown(
    support: object, expected: LiveLaneBackground | None
) -> None:
    assert ServedCatalogModels(lambda: _with_background(support)).lane_background("local", "api") == expected


def test_no_running_agent_or_an_unlisted_lane_states_no_background_support() -> None:
    assert ServedCatalogModels(lambda: None).lane_background("local", "api") is None
    assert (
        ServedCatalogModels(lambda: _document(_entry("synthetic-installed:1"))).lane_background("absent", "api") is None
    )


def test_a_snapshot_reads_the_document_once_when_first_asked_and_answers_everything_from_it() -> None:
    reads: list[int] = []

    def read() -> dict[str, Any]:
        reads.append(1)
        return _with_background({"accepts_images": True, "accepts_pdfs": True, "options": []})

    models = ServedCatalogModels(read)
    snapshot = models.snapshot()
    assert reads == []

    assert snapshot.lane_models("local", "api") is not None
    assert snapshot.lane_background("local", "api") is not None
    assert snapshot.lane_models("example", "cli") is not None
    assert len(reads) == 1

    models.snapshot().lane_background("local", "api")
    assert len(reads) == 2
