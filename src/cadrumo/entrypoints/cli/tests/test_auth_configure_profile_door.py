"""Installed CLI authentication door over real encrypted profiles."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from ....adapters.persistence.storage.certificate_secret_backend import build_certificate_secret_backend
from ....adapters.persistence.storage.operator_scope import build_operator_scope_ports
from ....adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from ....application.auth.credentials import resolve_active_provider_kind
from ....application.user_profile.fact_write import apply_manager_profile_field_mutation
from ....application.user_profile.profile_record_repository import ProfileRecordRepository
from ....application.user_profile.projections import record_to_path_values
from ....application.user_profile.registration import register_profile_with_credentials
from ....core.auth_provider import AuthProviderKind
from ....core.bucket_pointer import require_active_bucket_id
from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from .cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]
_CREDENTIAL_INPUT = "synthetic-cli-auth-passphrase"


@pytest.fixture
def profile_operation(tmp_path: Path) -> Iterator[PinnedAuthorityOperation]:
    with isolated_profile_storage_root(tmp_path=tmp_path), bundled_indexed_authority().operation() as operation:
        register_profile_with_credentials(
            label="Synthetic CLI authentication",
            passphrase=_CREDENTIAL_INPUT,
            profile_create_context=operation.profile_create_context(),
            profile_decode_context=operation.profile_decode_context(),
        )
        yield operation


def _record(operation: PinnedAuthorityOperation):
    return ProfileRecordRepository.for_current_session(
        require_active_bucket_id(),
        profile_decode_context=operation.profile_decode_context(),
    ).load(require_active_bucket_id())


def _cli(*arguments: str):
    result = invoke_cached_cli(("--format", "json", "config", "auth", *arguments))
    assert result.exit_code == 0, result.output
    return json.loads(result.stdout)["result"]


@pytest.mark.parametrize("provider", tuple(AuthProviderKind))
def test_cli_selection_is_the_persisted_preference_the_backend_selects(profile_operation, provider) -> None:
    arguments = ["configure", "--provider", provider.value]
    if provider is AuthProviderKind.CLAVE_MOVIL:
        arguments.extend(("--clave-movil-route", "qr"))
    first = _cli(*arguments)
    assert first["provider"] == provider.value
    assert record_to_path_values(_record(profile_operation))["auth.provider"] == provider.value
    assert _cli("status")["provider"] == provider.value
    assert (
        resolve_active_provider_kind(
            certificate_secret_backend_factory=build_certificate_secret_backend,
            operator_scope_ports=build_operator_scope_ports(),
        )
        is provider
    )
    assert not _cli(*arguments)["changed"]


def test_invalid_cli_choice_is_sanitized_before_any_write(profile_operation) -> None:
    before = _record(profile_operation)
    invalid = "secret-auth-choice-must-not-appear"
    result = invoke_cached_cli(("--format", "json", "config", "auth", "configure", "--provider", invalid))
    assert result.exit_code != 0
    assert invalid not in result.output
    assert json.loads(result.stderr)["error"]["code"] == "REFUSED_CLI_VALIDATION_BOUNDARY"
    assert _record(profile_operation).content_digest == before.content_digest


def test_public_cli_result_excludes_private_certificate_paths(profile_operation, tmp_path) -> None:
    private_path = tmp_path / "private-certificate-name.p12"
    payload = _cli("configure", "--provider", "certificate", "--file", str(private_path))
    assert payload["certificate_file_provided"]
    assert not payload["complete"]
    serialized = json.dumps(payload)
    assert str(private_path) not in serialized
    assert private_path.name not in serialized
    assert "identity_alignment_detail" not in payload
    assert "file" not in payload


def test_identity_mismatch_is_reported_without_exposing_either_identifier(profile_operation) -> None:
    for path, value in (("identity.tax_id", "12345678Z"), ("auth.dni_nie", "87654321X")):
        apply_manager_profile_field_mutation(
            profile_id=require_active_bucket_id(),
            path=path,
            value=value,
            profile_decode_context=profile_operation.profile_decode_context(),
        )
    result = _cli("configure", "--provider", "clave_movil", "--clave-movil-route", "qr")
    assert result["identity_alignment"] == "mismatch"
    assert not result["complete"]
    assert result["precondition_action"]["failed_condition_id"] == "auth.clave_movil.identity_aligned"
    assert "12345678Z" not in json.dumps(result)
    assert "87654321X" not in json.dumps(result)
