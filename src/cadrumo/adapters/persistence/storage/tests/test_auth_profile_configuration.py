"""Real encrypted-profile proofs for shared authentication configuration."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from .....application.auth.credentials import resolve_active_provider_kind
from .....application.auth.operator import configure_operator_auth, reset_operator_auth
from .....application.user_profile.capsule_record import ProfileRecordConflictError
from .....application.user_profile.fact_write import apply_manager_profile_field_mutation
from .....application.user_profile.profile_record_repository import ProfileRecordRepository
from .....application.user_profile.projections import record_to_path_values
from .....application.user_profile.registration import register_profile_with_credentials
from .....application.workflow.persistence import workflow_state_repository
from .....core.auth_provider import AuthProviderKind, ClaveMovilRoute
from .....core.bucket_pointer import require_active_bucket_id
from .....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ..certificate_secret_backend import build_certificate_secret_backend
from ..operator_scope import build_operator_scope_ports
from .secure_sql import isolated_profile_storage_root

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]
_CREDENTIAL_INPUT = "synthetic-auth-configuration-passphrase"


@pytest.fixture
def profile_operation(tmp_path: Path) -> Iterator[PinnedAuthorityOperation]:
    with isolated_profile_storage_root(tmp_path=tmp_path), bundled_indexed_authority().operation() as operation:
        register_profile_with_credentials(
            label="Synthetic authentication subject",
            passphrase=_CREDENTIAL_INPUT,
            profile_create_context=operation.profile_create_context(),
            profile_decode_context=operation.profile_decode_context(),
        )
        yield operation


def _record(operation: PinnedAuthorityOperation):
    return ProfileRecordRepository.for_current_session(
        require_active_bucket_id(), profile_decode_context=operation.profile_decode_context()
    ).load(require_active_bucket_id())


@pytest.mark.parametrize("provider", tuple(AuthProviderKind))
def test_configure_publishes_the_same_preference_the_backend_selects(profile_operation, provider) -> None:
    result = configure_operator_auth(
        provider.value,
        clave_movil_route=ClaveMovilRoute.QR if provider is AuthProviderKind.CLAVE_MOVIL else None,
        operator_scope_ports=build_operator_scope_ports(),
        operation=profile_operation,
    )
    assert result.changed
    assert record_to_path_values(_record(profile_operation))["auth.provider"] == provider.value
    assert (
        resolve_active_provider_kind(
            certificate_secret_backend_factory=build_certificate_secret_backend,
            operator_scope_ports=build_operator_scope_ports(),
        )
        is provider
    )


def test_repeated_configuration_is_an_event_and_revision_noop(profile_operation) -> None:
    configure_operator_auth(
        "certificate", operator_scope_ports=build_operator_scope_ports(), operation=profile_operation
    )
    before = _record(profile_operation)
    workflow_before = workflow_state_repository().load()
    result = configure_operator_auth(
        "certificate", operator_scope_ports=build_operator_scope_ports(), operation=profile_operation
    )
    assert not result.changed
    assert _record(profile_operation).content_digest == before.content_digest
    assert workflow_state_repository().load() == workflow_before


def test_stale_auth_edit_refuses_without_changing_profile_or_backend(profile_operation) -> None:
    before = _record(profile_operation)
    configure_operator_auth(
        "certificate", operator_scope_ports=build_operator_scope_ports(), operation=profile_operation
    )
    committed = _record(profile_operation)
    with pytest.raises(ProfileRecordConflictError):
        configure_operator_auth(
            "clave_permanente",
            expected_profile_revision=before.record_revision,
            expected_profile_digest=before.content_digest,
            operator_scope_ports=build_operator_scope_ports(),
            operation=profile_operation,
        )
    assert _record(profile_operation).content_digest == committed.content_digest
    assert workflow_state_repository().load().auth.provider == "certificate"


def test_unknown_method_refuses_before_any_mutation(profile_operation) -> None:
    before = _record(profile_operation)
    with pytest.raises(KeyError):
        configure_operator_auth(
            "unknown", operator_scope_ports=build_operator_scope_ports(), operation=profile_operation
        )
    assert _record(profile_operation).content_digest == before.content_digest


def test_reset_clears_the_profile_preference_as_well_as_operational_state(profile_operation) -> None:
    configure_operator_auth(
        "certificate", operator_scope_ports=build_operator_scope_ports(), operation=profile_operation
    )
    reset_operator_auth(
        provider="certificate",
        certificate_secret_backend_factory=build_certificate_secret_backend,
        operator_scope_ports=build_operator_scope_ports(),
    )
    assert "auth.provider" not in record_to_path_values(_record(profile_operation))
    assert workflow_state_repository().load().auth.provider is None
    assert (
        resolve_active_provider_kind(
            certificate_secret_backend_factory=build_certificate_secret_backend,
            operator_scope_ports=build_operator_scope_ports(),
        )
        is None
    )


def test_profile_intent_cannot_fall_through_to_another_operational_method(profile_operation) -> None:
    configure_operator_auth(
        "certificate", operator_scope_ports=build_operator_scope_ports(), operation=profile_operation
    )
    apply_manager_profile_field_mutation(
        profile_id=require_active_bucket_id(),
        path="auth.provider",
        value="clave_permanente",
        profile_decode_context=profile_operation.profile_decode_context(),
    )
    assert workflow_state_repository().load().auth.provider == "certificate"
    assert (
        resolve_active_provider_kind(
            certificate_secret_backend_factory=build_certificate_secret_backend,
            operator_scope_ports=build_operator_scope_ports(),
        )
        is AuthProviderKind.CLAVE_PERMANENTE
    )
