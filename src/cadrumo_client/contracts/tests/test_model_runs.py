"""The model-run wire contract refuses every shape that could carry the wrong answer."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from ..model_runs import (
    MODEL_RUN_MAX_BODY_BYTES,
    ModelRunBody,
    ModelRunConsentBinding,
    ModelRunFetched,
    ModelRunHeader,
    ModelRunLane,
    ModelRunMediaKind,
    ModelRunOutcome,
    ModelRunRefusalCode,
    ModelRunServed,
    decode_model_run_body,
    encode_model_run_body,
    model_run_media_kind,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LANE = ModelRunLane(
    provider_id="example",
    transport="cli",
    model="example-model-1",
    reads_off_host=True,
    licence=None,
    size_bytes=None,
    vision=None,
    context_length=None,
    installed=None,
)
_SERVED = ModelRunServed(provider_id="example", transport="cli", model="example-model-1", agent_version="1")


@pytest.mark.parametrize(
    "fields",
    [
        {},
        {"lane": _LANE, "refusal": ModelRunRefusalCode.RUN_FAILED},
        {"served": _SERVED},
        {"lane": _LANE, "text_byte_count": 3},
        {"refusal": ModelRunRefusalCode.RUN_FAILED, "text_byte_count": 1},
    ],
)
def test_an_outcome_carries_exactly_one_answer_and_text_only_after_a_served_run(fields: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ModelRunOutcome.model_validate(fields)


def test_the_three_well_formed_outcomes_are_accepted() -> None:
    assert ModelRunOutcome(lane=_LANE).lane == _LANE
    assert ModelRunOutcome(served=_SERVED, text_byte_count=4).text_byte_count == 4
    assert ModelRunOutcome(refusal=ModelRunRefusalCode.CONSENT_MISSING).refusal is ModelRunRefusalCode.CONSENT_MISSING


def _fetched(header: ModelRunHeader | None, body_byte_count: int, *, role: str = "text_extraction") -> ModelRunFetched:
    return ModelRunFetched(
        request_id=uuid4(),
        runtime_boot_id=uuid4(),
        connection_id=uuid4(),
        run_id=uuid4(),
        role=role,
        header=header,
        body_byte_count=body_byte_count,
    )


def test_a_lookup_carries_no_body_and_a_run_always_does() -> None:
    header = ModelRunHeader(role="text_extraction", deadline_seconds=10)
    assert _fetched(None, 0).header is None
    assert _fetched(header, 5).body_byte_count == 5
    with pytest.raises(ValidationError):
        _fetched(header, 0)
    with pytest.raises(ValidationError):
        _fetched(None, 5)


def test_a_run_names_its_headers_role() -> None:
    header = ModelRunHeader(role="text_extraction", deadline_seconds=10)
    with pytest.raises(ValidationError):
        _fetched(header, 5, role="vision_transcription")


def test_consent_matches_its_own_lane_and_no_other() -> None:
    consent = ModelRunConsentBinding(
        evidence_content_address="a" * 64, provider_id="example", transport="cli", model="example-model-1"
    )
    assert consent.matches(_LANE)
    assert not consent.matches(_LANE.model_copy(update={"transport": "api"}))
    assert not consent.matches(_LANE.model_copy(update={"model": "example-model-2"}))


def test_an_off_host_lane_admits_only_a_run_consented_for_it_and_an_on_host_lane_needs_none() -> None:
    consent = ModelRunConsentBinding(
        evidence_content_address="a" * 64, provider_id="example", transport="cli", model="example-model-1"
    )
    on_host = _LANE.model_copy(update={"reads_off_host": False})
    unconsented = ModelRunHeader(role="text_extraction", deadline_seconds=30)
    consented = ModelRunHeader(role="text_extraction", deadline_seconds=30, consent=consent)
    elsewhere = ModelRunHeader(
        role="text_extraction",
        deadline_seconds=30,
        consent=consent.model_copy(update={"model": "example-model-2"}),
    )

    assert (unconsented.consent_admits(_LANE), consented.consent_admits(_LANE)) == (False, True)
    assert not elsewhere.consent_admits(_LANE)
    assert unconsented.consent_admits(on_host)
    assert not elsewhere.consent_admits(on_host)


def test_a_body_round_trips_and_one_beyond_its_bound_is_refused() -> None:
    body = ModelRunBody(system="Be terse.", prompt="Read this.", max_output_tokens=32)
    encoded = encode_model_run_body(body)
    assert decode_model_run_body(encoded) == body
    with pytest.raises(ValueError, match="bound"):
        decode_model_run_body(bytes(MODEL_RUN_MAX_BODY_BYTES + 1))


def test_a_body_that_states_no_run_option_round_trips_without_one() -> None:
    """Omitted options stay omitted across the carrier: nothing fills in a bound or a temperature."""
    body = ModelRunBody(prompt="Read this.")

    decoded = decode_model_run_body(encode_model_run_body(body))

    assert decoded == body
    assert (decoded.max_output_tokens, decoded.temperature, decoded.context_tokens) == (None, None, None)


_AGENT_MODEL_ID_LENGTH = 512
"""cadrumo-agent's longest model id in its catalogues."""


def test_a_lane_carries_the_agent_s_zero_size_and_refuses_a_negative_one() -> None:
    assert ModelRunLane.model_validate({**_LANE.model_dump(), "size_bytes": 0}).size_bytes == 0
    with pytest.raises(ValidationError):
        ModelRunLane.model_validate({**_LANE.model_dump(), "size_bytes": -1})


def test_a_lane_carries_a_model_id_as_long_as_the_agent_allows_and_refuses_one_longer() -> None:
    longest = "m" * _AGENT_MODEL_ID_LENGTH

    assert ModelRunLane.model_validate({**_LANE.model_dump(), "model": longest}).model == longest
    with pytest.raises(ValidationError):
        ModelRunLane.model_validate({**_LANE.model_dump(), "model": longest + "m"})


_AGENT_PROVIDER_ID_LENGTH = 64
"""cadrumo-agent's longest provider metadata key, which bounds a provider id."""


def test_a_lane_carries_a_provider_id_as_long_as_the_agent_allows_and_refuses_one_longer() -> None:
    longest = "p" * _AGENT_PROVIDER_ID_LENGTH

    for model in (ModelRunLane, ModelRunServed, ModelRunConsentBinding):
        fields = _SERVED.model_dump() if model is ModelRunServed else _LANE.model_dump()
        if model is ModelRunConsentBinding:
            fields = {"evidence_content_address": "a" * 64, **{key: fields[key] for key in ("transport", "model")}}
        assert model.model_validate({**fields, "provider_id": longest}).provider_id == longest
        with pytest.raises(ValidationError):
            model.model_validate({**fields, "provider_id": longest + "p"})


def test_media_kinds_are_read_from_the_media_type_alone() -> None:
    assert model_run_media_kind("image/png") is ModelRunMediaKind.IMAGE
    assert model_run_media_kind("Application/PDF") is ModelRunMediaKind.PDF
    assert model_run_media_kind("text/plain") is None
