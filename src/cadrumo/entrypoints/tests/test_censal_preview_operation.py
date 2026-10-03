"""Real-supervisor acceptance for exact-profile censal preview."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID

import pytest

from cadrumo.adapters.persistence.storage.operator_scope import build_operator_scope_ports
from cadrumo.application.auth.tests.certificate_secret_fakes import InMemoryCertificateSecretBackendFactory
from cadrumo.application.live.tests.unopened_live_ports import (
    unopened_browser_session_factory,
    unopened_censal_fetch,
)
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.registry import OperationRegistry
from cadrumo.application.user_profile.capsule_record import ProfileRecordStore
from cadrumo.application.user_profile.censal_operation import CensalProfileBaseline
from cadrumo.application.user_profile.censal_preview_operation import (
    CENSAL_PREVIEW_OPERATION_DEFINITION_ID,
    CensalPreviewOperationRequest,
    CensalPreviewOperationResult,
    build_censal_preview_operation_definition,
    build_censal_preview_operation_registration,
)
from cadrumo.application.user_profile.censo_sync import CENSO_SOURCE_TAG
from cadrumo.application.user_profile.profile_record_repository import ProfileRecordRepository
from cadrumo.application.user_profile.projections import record_to_effective_facts
from cadrumo.core.bucket_pointer import require_active_bucket_id
from cadrumo.core.config import override_settings
from cadrumo.core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation

from . import test_registered_executor_conformance as conformance

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


class _PreviewBrowserResources:
    """Small process-family owner observed by the real supervisor cleanup path."""

    def __init__(self) -> None:
        task = asyncio.current_task()
        self.factory_task_name = None if task is None else task.get_name()
        self.activation_task_name: str | None = None
        self.close_task_name: str | None = None
        self.activation_count = 0
        self.close_count = 0
        self.active = False
        self.closed = False

    @contextmanager
    def activate(self) -> Iterator[None]:
        assert not self.active
        assert not self.closed
        task = asyncio.current_task()
        self.activation_task_name = None if task is None else task.get_name()
        self.activation_count += 1
        self.active = True
        try:
            yield
        finally:
            self.active = False

    async def close(self) -> None:
        assert not self.active
        task = asyncio.current_task()
        self.close_task_name = None if task is None else task.get_name()
        self.close_count += 1
        self.closed = True


def test_censal_preview_admits_its_exact_profile_and_settles_without_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    operation: PinnedAuthorityOperation,
) -> None:
    """Recorded preview runs under the exact profile and closes its worker-owned resource."""
    resources: list[_PreviewBrowserResources] = []
    expected_profile_ids: list[UUID] = []
    preflight_profile_ids: list[UUID] = []
    preflight_task_names: list[str] = []
    acquisition_profile_ids: list[str] = []
    acquisition_task_names: list[str] = []
    acquisition_scopes: list[bool] = []
    pinned_operations: list[PinnedAuthorityOperation] = []
    observation = conformance._observation()

    def browser_resources_factory() -> _PreviewBrowserResources:
        resource = _PreviewBrowserResources()
        resources.append(resource)
        return resource

    def provider_preflight(profile_id: UUID, authority: PinnedAuthorityOperation) -> None:
        del authority
        assert expected_profile_ids == [profile_id]
        preflight_profile_ids.append(profile_id)
        task = asyncio.current_task()
        preflight_task_names.append("" if task is None else task.get_name())

    async def acquire(authority: PinnedAuthorityOperation, _effect_guard: object, _on_session_write: object):
        task = asyncio.current_task()
        acquisition_task_names.append("" if task is None else task.get_name())
        active_profile_id = require_active_bucket_id()
        assert expected_profile_ids == [UUID(active_profile_id)]
        acquisition_profile_ids.append(active_profile_id)
        pinned_operations.append(authority)
        assert resources
        acquisition_scopes.append(resources[-1].active)
        return observation

    definition = build_censal_preview_operation_definition(
        certificate_secret_backend_factory=InMemoryCertificateSecretBackendFactory(),
        browser_session_factory=unopened_browser_session_factory,
        operator_scope_ports=build_operator_scope_ports(),
        censal_fetch_port=unopened_censal_fetch,
        browser_resources_factory=browser_resources_factory,
        provider_preflight=provider_preflight,
        acquire=acquire,
    )
    registration = build_censal_preview_operation_registration(definition)
    preview_registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))

    def preview_registry_builder(**_kwargs: object) -> OperationRegistry:
        return preview_registry

    monkeypatch.setattr(conformance, "build_production_operation_registry", preview_registry_builder)
    profile_decode_context = operation.profile_decode_context()
    cleanup = conformance._CloseWitness()

    with conformance._runtime(tmp_path / "censal-preview", cleanup=cleanup) as (
        driver,
        runtime_registry,
        profile_id,
    ):
        expected_profile_ids.append(profile_id)
        subject_ref = profile_operation_subject(str(profile_id))

        with override_settings(cadrumo_active_profile=str(profile_id)):
            repository = ProfileRecordRepository.for_current_session(
                profile_id,
                profile_decode_context=profile_decode_context,
            )
            record_before = repository.load(profile_id)
            history_before = ProfileRecordStore(session=repository.session).history()
            request = OperationRequest(
                definition_id=CENSAL_PREVIEW_OPERATION_DEFINITION_ID,
                subject_ref=subject_ref,
                payload=CensalPreviewOperationRequest(baseline=CensalProfileBaseline.from_record(record_before)),
            )

            submission, observed = asyncio.run(
                driver.run(
                    definition_id=CENSAL_PREVIEW_OPERATION_DEFINITION_ID,
                    subject_ref=subject_ref,
                    payload=request.payload,
                )
            )
            snapshot = asyncio.run(driver.services.submission.supervisor.inspect(submission.receipt.operation_id))
            receipt = snapshot.terminal_receipt
            assert receipt is not None
            assert receipt.identity.definition_id == CENSAL_PREVIEW_OPERATION_DEFINITION_ID
            assert receipt.identity.subject_ref == subject_ref
            assert receipt.condition is OperationTerminalCondition.SUCCEEDED
            assert receipt.effect is OperationEffect.NONE
            assert receipt.result_ref is not None
            assert observed.projection.lifecycle is OperationLifecycle.TERMINAL
            assert observed.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
            assert observed.projection.effect is OperationEffect.NONE

            preview = conformance._resolve_result_projection(
                driver,
                runtime_registry,
                definition_id=CENSAL_PREVIEW_OPERATION_DEFINITION_ID,
                operation_id=submission.receipt.operation_id,
                terminal_revision=observed.projection.revision,
                projection_type=CensalPreviewOperationResult,
            )
            assert isinstance(preview, CensalPreviewOperationResult)
            assert preview.profile_id == profile_id
            assert preview.applied is False
            assert preview.source_url == observation.source_url
            assert tuple(item.path for item in preview.adopted) == (
                "contact.fiscal_address",
                "contact.postcode",
                "contact.fiscal_address_cadastral_reference",
            )
            assert all(item.source == CENSO_SOURCE_TAG for item in preview.adopted)
            assert not preview.unchanged
            assert not preview.divergences

            record_after = repository.load(profile_id)
            history_after = ProfileRecordStore(session=repository.session).history()

        assert record_after == record_before
        assert history_after == history_before
        assert not any(fact.source == CENSO_SOURCE_TAG for fact in record_to_effective_facts(record_after).values())
        assert preflight_profile_ids == [profile_id]
        assert acquisition_profile_ids == [str(profile_id)]
        assert acquisition_scopes == [True]
        assert acquisition_task_names == [resources[0].factory_task_name]
        assert preflight_task_names == [resources[0].factory_task_name]
        assert pinned_operations
        assert len(pinned_operations) == 1
        assert len(resources) == 1
        assert resources[0].activation_count == 1
        assert resources[0].close_count == 1
        assert resources[0].closed
        assert resources[0].factory_task_name is not None
        assert resources[0].factory_task_name.startswith("operation-executor-")
        assert resources[0].close_task_name == "operation-settlement"
