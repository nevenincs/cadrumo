"""Installed TUI and shared authentication doors over real encrypted profiles and operation graphs."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest
from textual.widgets import Input

from ....adapters.persistence.storage.certificate_secret_backend import build_certificate_secret_backend
from ....adapters.persistence.storage.operator_scope import build_operator_scope_ports
from ....adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from ....application.auth.configuration_result import AuthConfigurePublicResultV1
from ....application.auth.credentials import resolve_active_provider_kind
from ....application.auth.operation_definitions import (
    AUTH_CONFIGURE_OPERATION_DEFINITION_ID,
    AuthConfigureOperationRequest,
)
from ....application.operations.frontend_requests import OperationObservationRequestV1, OperationObservationSuccessV1
from ....application.operations.models import OperationRequest
from ....application.user_profile.login_interaction import profile_login_choices
from ....application.user_profile.login_session import login_profile, logout_active_profile
from ....application.user_profile.profile_record_repository import ProfileRecordRepository
from ....application.user_profile.projections import record_to_path_values
from ....application.user_profile.registration import register_profile_with_credentials
from ....core.auth_provider import AuthProviderKind, ClaveMovilRoute
from ....core.bucket_pointer import require_active_bucket_id
from ....core.errors.hierarchy import PublicErrorProjectionError
from ....core.operations import OperationTerminalCondition, profile_operation_subject
from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...auth_configuration import run_auth_configuration
from ..components.host import ScreenHostApp
from ..installed_session import compose_authenticated_account_inputs
from ..launcher import operation_services_scope
from ..profile.overview import FieldEditScreen

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]
_CREDENTIAL_INPUT = "synthetic-frontend-auth-passphrase"


@pytest.fixture
def profile_operation(tmp_path: Path) -> Iterator[PinnedAuthorityOperation]:
    with isolated_profile_storage_root(tmp_path=tmp_path), bundled_indexed_authority().operation() as operation:
        register_profile_with_credentials(
            label="Synthetic frontend authentication",
            passphrase=_CREDENTIAL_INPUT,
            profile_create_context=operation.profile_create_context(),
            profile_decode_context=operation.profile_decode_context(),
        )
        yield operation


def _account(operation: PinnedAuthorityOperation):
    choices = profile_login_choices()
    return compose_authenticated_account_inputs(
        profile_id=require_active_bucket_id(),
        profile_label=next(choice.label for choice in choices if choice.profile_id == require_active_bucket_id()),
        login_choices=choices,
        operation=operation,
    )


def _values(operation: PinnedAuthorityOperation):
    record = ProfileRecordRepository.for_current_session(
        require_active_bucket_id(),
        profile_decode_context=operation.profile_decode_context(),
    ).load(require_active_bucket_id())
    return record_to_path_values(record)


def _configure(
    operation: PinnedAuthorityOperation,
    provider: AuthProviderKind,
    *,
    clave_movil_route: ClaveMovilRoute | None = None,
) -> AuthConfigurePublicResultV1:
    return run_auth_configuration(
        AuthConfigureOperationRequest(provider=provider, clave_movil_route=clave_movil_route),
        profile_id=require_active_bucket_id(),
        operation=operation,
    )


def _selected_provider() -> AuthProviderKind | None:
    return resolve_active_provider_kind(
        certificate_secret_backend_factory=build_certificate_secret_backend,
        operator_scope_ports=build_operator_scope_ports(),
    )


@pytest.mark.parametrize("provider", tuple(AuthProviderKind))
def test_shared_door_and_tui_selection_use_the_same_persisted_backend(profile_operation, provider) -> None:
    route = ClaveMovilRoute.QR if provider is AuthProviderKind.CLAVE_MOVIL else None
    first = _configure(profile_operation, provider, clave_movil_route=route)
    assert first.provider is provider
    assert _values(profile_operation)["auth.provider"] == provider.value
    assert _selected_provider() is provider
    account = _account(profile_operation)
    before = account.profile_overview
    unchanged = account.persist_profile_field(
        "auth.provider",
        provider.value,
        before.record_revision,
        before.content_digest,
    )
    assert unchanged.record_revision == before.record_revision
    assert not _configure(profile_operation, provider, clave_movil_route=route).changed
    changed = account.persist_profile_field(
        "auth.provider",
        "clave_permanente",
        unchanged.record_revision,
        unchanged.content_digest,
    )
    assert _values(profile_operation)["auth.provider"] == "clave_permanente"
    assert _selected_provider() is AuthProviderKind.CLAVE_PERMANENTE
    assert changed.content_digest == _account(profile_operation).profile_overview.content_digest


@pytest.mark.parametrize("route", tuple(ClaveMovilRoute))
def test_route_is_shared_and_survives_a_frontend_switch(profile_operation, route) -> None:
    _configure(profile_operation, AuthProviderKind.CLAVE_MOVIL, clave_movil_route=route)
    assert _values(profile_operation)["auth.clave_movil_route"] == route.value
    account = _account(profile_operation)
    baseline = account.profile_overview
    replacement = ClaveMovilRoute.APP_REQUEST if route is ClaveMovilRoute.QR else ClaveMovilRoute.QR
    account.persist_profile_field(
        "auth.clave_movil_route",
        replacement.value,
        baseline.record_revision,
        baseline.content_digest,
    )
    assert _values(profile_operation)["auth.clave_movil_route"] == replacement.value
    assert not _configure(profile_operation, AuthProviderKind.CLAVE_MOVIL, clave_movil_route=replacement).changed


def test_stale_tui_auth_edit_uses_a_safe_operation_refusal(profile_operation) -> None:
    account = _account(profile_operation)
    stale = account.profile_overview
    _configure(profile_operation, AuthProviderKind.CERTIFICATE)
    committed = _account(profile_operation).profile_overview
    with pytest.raises(PublicErrorProjectionError) as refusal:
        account.persist_profile_field(
            "auth.provider",
            "clave_permanente",
            stale.record_revision,
            stale.content_digest,
        )
    assert refusal.value.context is not None
    assert "PROFILE" in str(refusal.value.context["error_code"])
    assert _account(profile_operation).profile_overview.content_digest == committed.content_digest
    assert _selected_provider() is AuthProviderKind.CERTIFICATE
    assert _CREDENTIAL_INPUT not in str(refusal.value.context)


@pytest.mark.asyncio
async def test_sensitive_profile_input_hides_values_while_typing(profile_operation) -> None:
    overview = _account(profile_operation).profile_overview
    field = next(
        field for section in overview.sections for field in section.fields if field.path == "auth.numero_soporte"
    )
    dialog = FieldEditScreen(field)
    host = ScreenHostApp(dialog)
    async with host.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        entry = dialog.query_one("#edit-input", Input)
        assert entry.password
        entry.value = "SYNTHETIC-CONTRAST-INPUT"
        await pilot.pause()
        assert entry.password
        assert "SYNTHETIC-CONTRAST-INPUT" not in host.export_screenshot()


@pytest.mark.asyncio
async def test_installed_tui_worker_reuses_its_running_operation_graph(profile_operation) -> None:
    async with operation_services_scope() as runtime:
        account = compose_authenticated_account_inputs(
            profile_id=require_active_bucket_id(),
            profile_label="Synthetic frontend authentication",
            login_choices=profile_login_choices(),
            operation=runtime.authority_operation,
            operation_runtime=runtime,
        )
        before = account.profile_overview
        written = await asyncio.wait_for(
            asyncio.to_thread(
                account.persist_profile_field,
                "auth.provider",
                "clave_permanente",
                before.record_revision,
                before.content_digest,
            ),
            timeout=30,
        )
        assert written.record_revision > before.record_revision
        assert _values(profile_operation)["auth.provider"] == "clave_permanente"


@pytest.mark.asyncio
async def test_public_operation_observation_and_events_omit_private_request_paths(profile_operation, tmp_path) -> None:
    private_path = tmp_path / "private-auth-operation-marker.p12"
    async with operation_services_scope() as runtime:
        submitted = await runtime.services.submission.submit(
            OperationRequest(
                definition_id=AUTH_CONFIGURE_OPERATION_DEFINITION_ID,
                subject_ref=profile_operation_subject(require_active_bucket_id()),
                payload=AuthConfigureOperationRequest(
                    provider=AuthProviderKind.CERTIFICATE,
                    certificate_path=private_path,
                ),
            ),
            actor_ref="operator:auth-configure",
        )
        await runtime.services.submission.start(submitted.receipt.operation_id)
        await runtime.services.submission.settled(submitted.receipt.operation_id)
        observed = await runtime.services.observation.observe(
            OperationObservationRequestV1(
                operation_id=submitted.receipt.operation_id,
                after_cursor=0,
                page_limit=64,
            )
        )
        assert isinstance(observed, OperationObservationSuccessV1)
        assert observed.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
        assert observed.event_page.events
        assert private_path.name not in observed.model_dump_json()
        assert str(private_path) not in observed.model_dump_json()
        assert _CREDENTIAL_INPUT not in observed.model_dump_json()


def test_delayed_auth_submission_refuses_a_profile_switch_without_redirecting_the_save(profile_operation) -> None:
    displayed_profile_id = require_active_bucket_id()
    displayed = _account(profile_operation).profile_overview
    register_profile_with_credentials(
        label="Second synthetic authentication subject",
        passphrase=_CREDENTIAL_INPUT,
        profile_create_context=profile_operation.profile_create_context(),
        profile_decode_context=profile_operation.profile_decode_context(),
    )
    replacement_profile_id = require_active_bucket_id()
    assert replacement_profile_id != displayed_profile_id
    replacement_before = _account(profile_operation).profile_overview
    with pytest.raises(PublicErrorProjectionError) as refused:
        run_auth_configuration(
            AuthConfigureOperationRequest(
                provider=AuthProviderKind.CLAVE_PERMANENTE,
                expected_profile_revision=displayed.record_revision,
                expected_profile_digest=displayed.content_digest,
            ),
            profile_id=displayed_profile_id,
            operation=profile_operation,
        )
    assert refused.value.context is not None
    assert refused.value.context["diagnostic_ref"]
    assert "auth.provider" not in _values(profile_operation)
    assert _account(profile_operation).profile_overview.content_digest == replacement_before.content_digest
    logout_active_profile()
    login_profile(
        name=displayed_profile_id,
        passphrase_callback=lambda: _CREDENTIAL_INPUT,
        profile_decode_context=profile_operation.profile_decode_context(),
    )
    original = ProfileRecordRepository.for_current_session(
        displayed_profile_id,
        profile_decode_context=profile_operation.profile_decode_context(),
    ).load(displayed_profile_id)
    assert original.content_digest == displayed.content_digest
