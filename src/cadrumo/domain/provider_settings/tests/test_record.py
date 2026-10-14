"""The provider-settings record keeps its secret out of every ordinary rendering."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from pydantic import SecretStr, ValidationError

from ..record import (
    AssistantAuth,
    CredentialKind,
    CredentialSecretRefusal,
    CredentialState,
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
