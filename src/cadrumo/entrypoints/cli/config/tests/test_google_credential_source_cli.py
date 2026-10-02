"""Canonical source-input errors and public credential-source payload contract."""

import pytest

from .....adapters.outbound.google.errors import GoogleAuthError
from .....adapters.outbound.google.google_configuration_inputs import google_credential_source_selection
from .....core.google_credential_source import GoogleCredentialSourceKind
from .._google_credential_source_payloads import (
    GoogleCredentialSourceSetResult,
    GoogleCredentialSourceViewResult,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_impersonation_requires_its_target_principal() -> None:
    with pytest.raises(GoogleAuthError) as caught:
        google_credential_source_selection(
            kind=GoogleCredentialSourceKind.SERVICE_ACCOUNT_IMPERSONATION,
            target_principal=None,
            scopes=(),
            delegates=(),
            subject=None,
            lifetime_seconds=None,
        )

    assert caught.value.translated_message == "cli.config.google.credential_source.detail.target_principal_required"


def test_oauth_desktop_rejects_impersonation_options() -> None:
    with pytest.raises(GoogleAuthError) as caught:
        google_credential_source_selection(
            kind=GoogleCredentialSourceKind.OAUTH_DESKTOP,
            target_principal=None,
            scopes=("https://www.googleapis.com/auth/drive.file",),
            delegates=(),
            subject=None,
            lifetime_seconds=None,
        )

    assert (
        caught.value.translated_message
        == "cli.config.google.credential_source.detail.oauth_desktop_rejects_impersonation_options"
    )


def test_credential_source_payload_preserves_full_public_fields_without_secrets() -> None:
    set_result = GoogleCredentialSourceSetResult(
        profile="profile-id",
        kind=GoogleCredentialSourceKind.SERVICE_ACCOUNT_IMPERSONATION,
        target_principal="export@example-project.iam.gserviceaccount.com",
        target_scopes=["https://www.googleapis.com/auth/drive.file"],
        delegates=["delegate@example-project.iam.gserviceaccount.com"],
        subject="operator@example.invalid",
        lifetime_s=1800,
    )
    view_result = GoogleCredentialSourceViewResult(
        profile="profile-id",
        configured=False,
        kind=GoogleCredentialSourceKind.OAUTH_DESKTOP,
    )

    assert set(set_result.model_dump(mode="json")) == {
        "operation",
        "profile",
        "kind",
        "target_principal",
        "target_scopes",
        "delegates",
        "subject",
        "lifetime_s",
    }
    assert set_result.target_scopes == ["https://www.googleapis.com/auth/drive.file"]
    assert set(view_result.model_dump(mode="json")) == {
        "operation",
        "profile",
        "configured",
        "kind",
        "target_principal",
        "target_scopes",
        "delegates",
        "subject",
        "lifetime_s",
    }
    assert view_result.configured is False
    assert "private_key" not in set_result.model_dump(mode="json")
    assert "access_token" not in set_result.model_dump(mode="json")
