"""Installed CLI/TUI doors over real encrypted profiles and operation graphs."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from textual.widgets import Input

from ....adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from ....application.user_profile.login_interaction import profile_login_choices
from ....application.user_profile.profile_record_repository import ProfileRecordRepository
from ....application.user_profile.projections import record_to_path_values
from ....application.user_profile.registration import register_profile_with_credentials
from ....core.auth_provider import AuthProviderKind
from ....core.bucket_pointer import require_active_bucket_id
from ....core.errors.hierarchy import CoreValidationError
from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...cli.tests.cli_runner import invoke_cached_cli
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
    return compose_authenticated_account_inputs(
        profile_id=require_active_bucket_id(),
        profile_label="Synthetic frontend authentication",
        login_choices=profile_login_choices(),
        operation=operation,
    )


def _values(operation: PinnedAuthorityOperation):
    record = ProfileRecordRepository.for_current_session(
        require_active_bucket_id(),
        profile_decode_context=operation.profile_decode_context(),
    ).load(require_active_bucket_id())
    return record_to_path_values(record)


def _cli(*arguments: str):
    result = invoke_cached_cli(("--format", "json", "config", "auth", *arguments))
    assert result.exit_code == 0, result.output
    return json.loads(result.stdout)["result"]


@pytest.mark.parametrize("provider", tuple(AuthProviderKind))
def test_cli_and_tui_selection_use_the_same_persisted_backend(profile_operation, provider) -> None:
    arguments = ["configure", "--provider", provider.value]
    if provider is AuthProviderKind.CLAVE_MOVIL:
        arguments.extend(("--clave-movil-route", "qr"))
    first = _cli(*arguments)
    assert first["provider"] == provider.value
    assert _values(profile_operation)["auth.provider"] == provider.value
    assert _cli("status")["provider"] == provider.value
    account = _account(profile_operation)
    before = account.profile_overview
    unchanged = account.persist_profile_field(
        "auth.provider",
        provider.value,
        before.record_revision,
        before.content_digest,
    )
    assert unchanged.record_revision == before.record_revision
    assert not _cli(*arguments)["changed"]
    changed = account.persist_profile_field(
        "auth.provider",
        "clave_permanente",
        unchanged.record_revision,
        unchanged.content_digest,
    )
    assert _values(profile_operation)["auth.provider"] == "clave_permanente"
    assert _cli("status")["provider"] == "clave_permanente"
    assert changed.content_digest == _account(profile_operation).profile_overview.content_digest


@pytest.mark.parametrize("route", ("qr", "app_request"))
def test_route_is_shared_and_survives_a_frontend_switch(profile_operation, route) -> None:
    _cli("configure", "--provider", "clave_movil", "--clave-movil-route", route)
    assert _values(profile_operation)["auth.clave_movil_route"] == route
    account = _account(profile_operation)
    baseline = account.profile_overview
    replacement = "app_request" if route == "qr" else "qr"
    account.persist_profile_field(
        "auth.clave_movil_route",
        replacement,
        baseline.record_revision,
        baseline.content_digest,
    )
    assert _values(profile_operation)["auth.clave_movil_route"] == replacement
    assert not _cli("configure", "--provider", "clave_movil", "--clave-movil-route", replacement)["changed"]


def test_stale_tui_auth_edit_uses_a_safe_operation_refusal(profile_operation) -> None:
    account = _account(profile_operation)
    stale = account.profile_overview
    _cli("configure", "--provider", "certificate")
    committed = _account(profile_operation).profile_overview
    with pytest.raises(CoreValidationError) as refusal:
        account.persist_profile_field(
            "auth.provider",
            "clave_permanente",
            stale.record_revision,
            stale.content_digest,
        )
    assert refusal.value.context is not None
    assert "PROFILE" in str(refusal.value.context["error_code"])
    assert _account(profile_operation).profile_overview.content_digest == committed.content_digest
    assert _cli("status")["provider"] == "certificate"
    assert _CREDENTIAL_INPUT not in str(refusal.value.context)


def test_invalid_cli_choice_is_sanitized_before_any_write(profile_operation) -> None:
    before = _account(profile_operation).profile_overview
    invalid = "secret-auth-choice-must-not-appear"
    result = invoke_cached_cli(("--format", "json", "config", "auth", "configure", "--provider", invalid))
    assert result.exit_code != 0
    assert invalid not in result.output
    assert json.loads(result.stderr)["error"]["code"] == "REFUSED_CLI_VALIDATION_BOUNDARY"
    assert _account(profile_operation).profile_overview.content_digest == before.content_digest


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
