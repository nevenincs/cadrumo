"""The provider-settings record keeps its secret out of every ordinary rendering."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from pydantic import SecretStr, ValidationError

from cadrumo.core.model_roles import ModelRole

from ..record import (
    AssistantAuth,
    CredentialKind,
    CredentialSecretRefusal,
    CredentialState,
    ModelRoleSelection,
    ProviderCredential,
    ProviderSettingsRecord,
    credential_secret_refusal,
    new_settings_generation,
    parse_provider_settings_record,
    provider_settings_record_document,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_FAKE_KEY = "sk-test-NOT-A-REAL-KEY-domain-0001"
_UPDATED_AT = datetime(2026, 10, 13, 9, 0, tzinfo=UTC)


def _record(*, secret: str = _FAKE_KEY) -> ProviderSettingsRecord:
    return ProviderSettingsRecord(
        schema_version=1,
        provider="example_cli",
        assistant_auth=AssistantAuth.DIRECT_API,
        credential_state=CredentialState.CONFIGURED,
        credential=ProviderCredential(
            kind=CredentialKind.API_KEY,
            secret=SecretStr(secret),
            base_url="https://gateway.example.invalid/v1",
        ),
        generation=new_settings_generation(),
        updated_at=_UPDATED_AT,
    )


def test_ordinary_renderings_never_carry_the_secret() -> None:
    record = _record()

    renderings = (
        repr(record),
        str(record),
        record.model_dump_json(),
        json.dumps(record.model_dump(mode="json")),
        repr(record.credential),
    )
    for rendering in renderings:
        assert _FAKE_KEY not in rendering
        assert "NOT-A-REAL-KEY" not in rendering


def test_at_rest_document_round_trips_the_secret() -> None:
    record = _record()

    document = provider_settings_record_document(record)
    restored = parse_provider_settings_record(document)

    assert _FAKE_KEY.encode() in document
    assert restored == record
    assert restored.credential is not None
    assert restored.credential.secret.get_secret_value() == _FAKE_KEY


def test_validation_errors_do_not_echo_the_secret() -> None:
    document = json.loads(provider_settings_record_document(_record()))
    document["credential"]["base_url"] = "http://plain.example.invalid"

    with pytest.raises(ValidationError) as raised:
        parse_provider_settings_record(json.dumps(document).encode())

    assert _FAKE_KEY not in str(raised.value)


def test_generation_is_random_and_independent_of_the_secret() -> None:
    first, second = _record(), _record()

    assert first.generation != second.generation
    assert len(first.generation) == 64


def test_credential_presence_must_match_its_state() -> None:
    with pytest.raises(ValidationError):
        ProviderSettingsRecord(
            schema_version=1,
            provider="example_api",
            assistant_auth=AssistantAuth.DIRECT_API,
            credential_state=CredentialState.CONFIGURED,
            generation=new_settings_generation(),
            updated_at=_UPDATED_AT,
        )


@pytest.mark.parametrize(
    ("candidate", "refusal"),
    [
        ("", CredentialSecretRefusal.EMPTY),
        ("short", CredentialSecretRefusal.LENGTH),
        ("sk-test NOT-A-REAL-KEY", CredentialSecretRefusal.WHITESPACE_OR_CONTROL),
        ("sk-test-NOT-A-REAL-KEY\n", CredentialSecretRefusal.WHITESPACE_OR_CONTROL),
        ("sk-****************1234", CredentialSecretRefusal.MASKED_PLACEHOLDER),
        ("sk-test...1234", CredentialSecretRefusal.MASKED_PLACEHOLDER),
        ("••••••••1234", CredentialSecretRefusal.MASKED_PLACEHOLDER),
        (_FAKE_KEY, None),
    ],
)
def test_secret_acceptance(candidate: str, refusal: CredentialSecretRefusal | None) -> None:
    assert credential_secret_refusal(candidate) is refusal


_AGENT_MODEL_ID_LENGTH = 512
"""cadrumo-agent's longest model id in its catalogues."""


@pytest.mark.parametrize(
    "model",
    [
        pytest.param("m" * _AGENT_MODEL_ID_LENGTH, id="longest-the-agent-carries"),
        pytest.param("Synthetic model, edición 1", id="spaces-and-non-ascii"),
        pytest.param("!" + "~" * 255, id="printable-ascii-stored-before"),
    ],
)
def test_a_selection_names_any_model_id_the_catalogue_carries(model: str) -> None:
    selection = ModelRoleSelection(role=ModelRole.TEXT_EXTRACTION, lane="example_api", model=model)

    assert selection.model == model


@pytest.mark.parametrize(
    "model",
    [
        pytest.param("m" * (_AGENT_MODEL_ID_LENGTH + 1), id="one-past-the-agent-s-bound"),
        pytest.param("", id="empty"),
        pytest.param("synthetic\nmodel", id="control-character"),
        pytest.param("synthetic\x7fmodel", id="delete-character"),
    ],
)
def test_a_selection_refuses_a_model_id_no_catalogue_carries(model: str) -> None:
    with pytest.raises(ValidationError):
        ModelRoleSelection(role=ModelRole.TEXT_EXTRACTION, lane="example_api", model=model)


_AGENT_LANE_ID_LENGTH = 68
"""cadrumo-agent's longest lane id: its 64-character provider metadata key, an underscore and the transport."""


@pytest.mark.parametrize(
    "lane",
    [
        pytest.param("l" * (_AGENT_LANE_ID_LENGTH - 4) + "_api", id="longest-the-agent-names"),
        pytest.param("o" * 36 + "_cli", id="forty-characters-stored-before"),
    ],
)
def test_a_record_and_a_selection_are_keyed_by_any_lane_id_the_catalogue_carries(lane: str) -> None:
    document = json.loads(provider_settings_record_document(_record()))
    document["provider"] = lane

    assert parse_provider_settings_record(json.dumps(document).encode()).provider == lane
    assert ModelRoleSelection(role=ModelRole.TEXT_EXTRACTION, lane=lane, model="example-model-1").lane == lane


def test_a_record_and_a_selection_refuse_a_lane_id_one_past_the_agent_s_bound() -> None:
    lane = "l" * (_AGENT_LANE_ID_LENGTH - 3) + "_api"
    document = json.loads(provider_settings_record_document(_record()))
    document["provider"] = lane

    with pytest.raises(ValidationError):
        parse_provider_settings_record(json.dumps(document).encode())
    with pytest.raises(ValidationError):
        ModelRoleSelection(role=ModelRole.TEXT_EXTRACTION, lane=lane, model="example-model-1")
