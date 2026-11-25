"""One lane's live entries, read from a document shaped as the agent's gateway serves its catalogue."""

from __future__ import annotations

from typing import Any, Final

import pytest

from cadrumo_client.contracts.model_runs import ModelRunMediaKind

from ...local_ai_relay import LocalAiFacts, LocalAiModel, LocalAiServer, ServedLocalAi
from ...providers.application.ports import LiveLaneBackground
from ...providers.application.tests.synthetic_catalog import sleeping_engine_document
from ...providers.domain.catalog import BackgroundOption
from ...providers.domain.record import LocalEngine
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


def _document(
    *models: object, provider: str = "llamacpp", transport: str = "api", health: object | None = None
) -> dict[str, Any]:
    record = {
        "provider_id": provider,
        "transport": transport,
        **({} if health is None else {"health": health}),
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

    entries = models.lane_models("llamacpp", "api")

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


def test_whether_the_lane_s_server_holds_each_model_is_read_and_an_unstated_one_stays_unknown() -> None:
    unstated = {key: value for key, value in _entry("synthetic-unstated:1").items() if key != "installed"}
    models = ServedCatalogModels(
        lambda: _document(_entry("synthetic-installed:1"), _entry("synthetic-absent:1", installed=False), unstated)
    )

    entries = models.lane_models("llamacpp", "api")

    assert entries is not None
    assert [(entry.id, entry.installed) for entry in entries] == [
        ("synthetic-installed:1", True),
        ("synthetic-absent:1", False),
        ("synthetic-unstated:1", None),
    ]


def _engine(state: str) -> dict[str, Any]:
    if state == "running":
        return {"engine": {"engine": "llamacpp", "state": "running", "reason": None, "door": None}}
    return {"engine": {"engine": "llamacpp", "state": state, "reason": "not_reachable", "door": "local_ai_setup"}}


def test_a_server_the_agent_did_not_read_holds_nothing_known_and_keeps_its_models_facts() -> None:
    document = _document(
        _entry("synthetic-held:1"), _entry("synthetic-absent:1", installed=False), health=_engine("not_running")
    )

    entries = ServedCatalogModels(lambda: document).lane_models("llamacpp", "api")

    assert entries is not None
    assert [(entry.id, entry.installed, entry.vision, entry.size_bytes) for entry in entries] == [
        ("synthetic-held:1", None, True, 2_000),
        ("synthetic-absent:1", None, True, 2_000),
    ]


def test_a_server_the_agent_read_says_what_it_holds() -> None:
    document = _document(
        _entry("synthetic-held:1"), _entry("synthetic-absent:1", installed=False), health=_engine("running")
    )

    entries = ServedCatalogModels(lambda: document).lane_models("llamacpp", "api")

    assert entries is not None
    assert [(entry.id, entry.installed) for entry in entries] == [
        ("synthetic-held:1", True),
        ("synthetic-absent:1", False),
    ]


def test_a_hosted_lane_states_no_install_even_when_its_entries_carry_one() -> None:
    document = _document(_entry("synthetic-held:1"), _entry("synthetic-absent:1", installed=False), provider="example")

    entries = ServedCatalogModels(lambda: document).lane_models("example", "api")

    assert entries is not None
    assert [(entry.id, entry.installed) for entry in entries] == [
        ("synthetic-held:1", None),
        ("synthetic-absent:1", None),
    ]


def test_no_running_agent_is_no_live_catalogue_and_an_unlisted_lane_lists_nothing() -> None:
    assert ServedCatalogModels(lambda: None).lane_models("llamacpp", "api") is None
    assert ServedCatalogModels(lambda: _document(_entry("synthetic-installed:1"))).lane_models("absent", "api") == ()


_AGENT_MODEL_ID_LENGTH: Final = 512
"""cadrumo-agent's longest model id in its served catalogue."""


def test_an_entry_at_the_agent_s_bounds_is_read() -> None:
    """A zero size is the agent's own value for an empty or unknown size; the longest id it serves is read too."""
    longest = "m" * _AGENT_MODEL_ID_LENGTH
    models = ServedCatalogModels(lambda: _document(_entry("synthetic-empty:1", size_bytes=0), _entry(longest)))

    entries = models.lane_models("llamacpp", "api")

    assert entries is not None
    assert [(entry.id, entry.size_bytes) for entry in entries] == [("synthetic-empty:1", 0), (longest, 2_000)]


@pytest.mark.parametrize(
    "document",
    [
        pytest.param(_document(_entry("synthetic-installed:1", size_bytes=-1)), id="size-negative"),
        pytest.param(_document(_entry("synthetic-installed:1", context_length=-1)), id="context-negative"),
        pytest.param(_document(_entry("synthetic-installed:1", vision="yes")), id="vision-not-a-bool"),
        pytest.param(_document(_entry("synthetic-installed:1", installed="yes")), id="installed-not-a-bool"),
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
            {"api_version": "v1", "providers": [{"provider_id": "llamacpp", "transport": "api"}]}, id="no-catalog"
        ),
    ],
)
def test_a_lane_whose_served_entries_do_not_validate_yields_no_live_catalogue(document: dict[str, Any]) -> None:
    assert ServedCatalogModels(lambda: document).lane_models("llamacpp", "api") is None


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

    background = ServedCatalogModels(lambda: _with_background(support)).lane_background("llamacpp", "api")

    assert background == LiveLaneBackground(
        accepted_media=(ModelRunMediaKind.IMAGE,),
        options=(BackgroundOption.TEMPERATURE, BackgroundOption.RESPONSE_SCHEMA),
        model_efforts={},
    )


def test_a_lane_that_honours_effort_is_read_with_the_levels_each_of_its_models_offers() -> None:
    document = _document(
        _entry("synthetic-levels:1", efforts=["low", "high"]),
        _entry("synthetic-none:1"),
        {key: value for key, value in _entry("synthetic-unstated:1").items() if key != "efforts"},
        _entry("synthetic-misspelt:1", efforts=["low", "HIGH"]),
    )
    document["providers"][1]["background_requests"] = {
        "accepts_images": False,
        "accepts_pdfs": False,
        "options": ["effort"],
    }

    background = ServedCatalogModels(lambda: document).lane_background("llamacpp", "api")

    assert background == LiveLaneBackground(
        accepted_media=(),
        options=(BackgroundOption.EFFORT,),
        model_efforts={"synthetic-levels:1": ("low", "high")},
    )


@pytest.mark.parametrize(
    ("support", "expected"),
    [
        pytest.param(
            {"accepts_images": "yes", "accepts_pdfs": True, "options": ["temperature"]},
            LiveLaneBackground(accepted_media=None, options=(BackgroundOption.TEMPERATURE,), model_efforts={}),
            id="media-flag-not-a-bool",
        ),
        pytest.param(
            {"accepts_images": False, "accepts_pdfs": False, "options": "temperature"},
            LiveLaneBackground(accepted_media=(), options=(), model_efforts={}),
            id="options-not-a-list",
        ),
        pytest.param(None, None, id="no-background-record"),
    ],
)
def test_background_support_the_document_does_not_state_reads_as_unknown(
    support: object, expected: LiveLaneBackground | None
) -> None:
    assert ServedCatalogModels(lambda: _with_background(support)).lane_background("llamacpp", "api") == expected


def test_no_running_agent_or_an_unlisted_lane_states_no_background_support() -> None:
    assert ServedCatalogModels(lambda: None).lane_background("llamacpp", "api") is None
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

    assert snapshot.lane_models("llamacpp", "api") is not None
    assert snapshot.lane_background("llamacpp", "api") is not None
    assert snapshot.lane_models("example", "cli") is not None
    assert len(reads) == 1

    models.snapshot().lane_background("llamacpp", "api")
    assert len(reads) == 2


def test_a_sleeping_server_holds_what_the_managers_files_hold_once_its_facts_are_kept() -> None:
    document = sleeping_engine_document(LocalEngine.LLAMACPP, "synthetic-held:1", "synthetic-absent:1")
    served = ServedLocalAi()
    models = ServedCatalogModels(served.over(lambda: document))

    unrelayed = models.lane_models("llamacpp", "api")
    assert unrelayed is not None
    assert [(entry.id, entry.installed) for entry in unrelayed] == [
        ("synthetic-held:1", None),
        ("synthetic-absent:1", None),
    ]

    served.keep(
        LocalAiFacts(
            engine=LocalEngine.LLAMACPP,
            server=LocalAiServer.DORMANT,
            models=(LocalAiModel(name="synthetic-held:1", stored=True),),
        )
    )

    relayed = models.lane_models("llamacpp", "api")
    assert relayed is not None
    # A model no fact names stays unknown: the agent did not read the server.
    assert [(entry.id, entry.installed) for entry in relayed] == [
        ("synthetic-held:1", True),
        ("synthetic-absent:1", None),
    ]
