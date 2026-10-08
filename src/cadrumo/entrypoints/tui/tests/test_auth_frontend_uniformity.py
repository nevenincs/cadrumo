"""TUI authentication inputs and the shared registered configuration over real encrypted profiles."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from textual.widgets import Input

from ....adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from ....application.auth.operation_definitions import (
    AUTH_CONFIGURE_OPERATION_DEFINITION_ID,
    AuthConfigureOperationRequest,
)
from ....application.operations.frontend_requests import OperationObservationRequestV1, OperationObservationSuccessV1
from ....application.operations.models import OperationRequest
from ....application.user_profile.overview import build_profile_overview
from ....application.user_profile.profile_record_repository import ProfileRecordRepository
from ....application.user_profile.registration import register_profile_with_credentials
from ....core.auth_provider import AuthProviderKind
from ....core.bucket_pointer import require_active_bucket_id
from ....core.operations import OperationTerminalCondition, profile_operation_subject
from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...operation_composition import compose_operation_dependencies
from ..components.host import ScreenHostApp
from ..profile.edit_screens import FieldEditScreen

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


@pytest.mark.asyncio
async def test_sensitive_profile_input_hides_values_while_typing(profile_operation) -> None:
    record = ProfileRecordRepository.for_current_session(
        require_active_bucket_id(),
        profile_decode_context=profile_operation.profile_decode_context(),
    ).load(require_active_bucket_id())
    overview = build_profile_overview(record, schema=profile_operation.profile_decode_context().schema)
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
async def test_public_operation_observation_and_events_omit_private_request_paths(profile_operation, tmp_path) -> None:
    private_path = tmp_path / "private-auth-operation-marker.p12"
    services = compose_operation_dependencies(authority_operation=profile_operation)
    try:
        submitted = await services.submission.submit(
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
        await services.submission.start(submitted.receipt.operation_id)
        await services.submission.settled(submitted.receipt.operation_id)
        observed = await services.observation.observe(
            OperationObservationRequestV1(
                operation_id=submitted.receipt.operation_id,
                after_cursor=0,
                page_limit=64,
            )
        )
    finally:
        await services.shutdown()
    assert isinstance(observed, OperationObservationSuccessV1)
    assert observed.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
    assert observed.event_page.events
    assert private_path.name not in observed.model_dump_json()
    assert str(private_path) not in observed.model_dump_json()
    assert _CREDENTIAL_INPUT not in observed.model_dump_json()
