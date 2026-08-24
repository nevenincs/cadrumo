"""Real supervisor proofs for canonical user-profile operation registrations."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import SecretStr

from ....adapters.persistence.operations import (
    OperationJournalRepository,
    OperationLeaseFilesystemRepository,
    OperationSecureReferenceRepository,
)
from ....adapters.persistence.storage import (
    SecureObjectNamespaceDefinition,
    StorageCustodyDisposition,
    StorageNamespaceScope,
    has_active_bucket_session,
)
from ....application.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationReconciliationPolicy,
    OperationRegistry,
    OperationRequest,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
    OperationSupervisor,
    OperationTerminalCondition,
)
from ....core import resolve_active_bucket_id
from ....core.classification import SensitivityClass
from ....tests.secure_namespace_registration import registered_objects
from ....tests.secure_sql import isolated_profile_storage_root
from ..._bundle_export_operation import ProfileBundleExportJournalRepository
from ..._custody_ports import profile_custody_secure_object_repository
from ..._profile_record_repository import ProfileRecordRepository
from ..._projections import record_to_path_values
from ..._registration import register_profile_with_credentials
from .._bundle_export_contracts import (
    ProfileBundleExportPurpose,
    ProfileBundleExportRequest,
    ProfileBundleExportResult,
    ProfileBundleExportTransport,
)
from .._operation_definitions import (
    PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID,
    PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID,
    PROFILE_LOGOUT_OPERATION_DEFINITION_ID,
    PROFILE_REPEATABLE_ROW_MUTATION_OPERATION_DEFINITION_ID,
    USER_PROFILE_OPERATION_DEFINITIONS,
    ProfileBundleExportOperationRequest,
    ProfileFieldMutationOperationRequest,
    ProfileLogoutOperationRequest,
    ProfileMutationOperationResult,
    ProfileRepeatableRowMutationOperationRequest,
    ProfileRepeatableRowMutationOperationResult,
    ProfileRepeatableRowValue,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_PROFILE_PASSPHRASE = "s40-profile-operation-passphrase"  # noqa: S105 - synthetic test fixture
_OPERAND_NAMESPACE = SecureObjectNamespaceDefinition(
    key="user_profile_operation_results",
    namespace="cadrumo-test.user-profile-operation-results",
    owner="cadrumo.application.user_profile.tests.test_operation_definitions",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=1,
    object_key_grammar="{content_digest}",
    scope=StorageNamespaceScope.BUCKET_LOCAL,
    custody_disposition=StorageCustodyDisposition.PROCESS_LOCAL,
)


def _supervisor(
    root: Path,
    *,
    profile_objects: object,
    owner_id: str,
    lease_token: str,
) -> tuple[OperationSupervisor, OperationSecureReferenceRepository]:
    """Build the real encrypted supervisor stack used by each family proof."""
    operands = OperationSecureReferenceRepository(
        objects=registered_objects(profile_objects, _OPERAND_NAMESPACE),  # type: ignore[arg-type]
        namespace=_OPERAND_NAMESPACE,
    )
    journal = OperationJournalRepository(storage_root=root)
    return (
        OperationSupervisor(
            registry=OperationRegistry(definitions=USER_PROFILE_OPERATION_DEFINITIONS),
            journal=journal,
            event_stream=journal,
            leases=OperationLeaseFilesystemRepository(storage_root=root),
            operands=operands,
            owner_id=owner_id,
            lease_token_factory=lambda: lease_token,
            clock=lambda: datetime.now(UTC),
            lease_duration=timedelta(minutes=6),
        ),
        operands,
    )


def _register_profile() -> UUID:
    """Create a real active profile whose encrypted store can host operands."""
    outcome = register_profile_with_credentials(
        label="S40 Profile Operation Subject",
        passphrase=_PROFILE_PASSPHRASE,
        recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
    )
    return UUID(outcome.profile_id)


def _start_from_fresh_supervisor(
    root: Path,
    *,
    profile_objects: object,
    request: OperationRequest,
    operation_id: str,
) -> tuple[object, OperationSecureReferenceRepository]:
    """Persist the request, then resolve it through a fresh real supervisor owner."""
    submitting, _ = _supervisor(
        root,
        profile_objects=profile_objects,
        owner_id="1" * 64,
        lease_token="2" * 64,
    )
    created = asyncio.run(submitting.submit(request, operation_id=operation_id))
    starting, operands = _supervisor(
        root,
        profile_objects=profile_objects,
        owner_id="3" * 64,
        lease_token="4" * 64,
    )
    return asyncio.run(starting.start(created)), operands


def test_profile_operation_families_have_one_secure_registered_definition_each() -> None:
    registry = OperationRegistry(definitions=USER_PROFILE_OPERATION_DEFINITIONS)
    definition_ids = tuple(definition.definition_id for definition in USER_PROFILE_OPERATION_DEFINITIONS)
    assert definition_ids == (
        PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID,
        PROFILE_REPEATABLE_ROW_MUTATION_OPERATION_DEFINITION_ID,
        PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID,
        PROFILE_LOGOUT_OPERATION_DEFINITION_ID,
    )
    assert len(set(definition_ids)) == len(definition_ids)
    assert all(
        registry.lookup(definition_id).capabilities.request_storage is OperationRequestStoragePolicy.SECURE_REFERENCE
        and registry.lookup(definition_id).capabilities.sensitive_input is OperationSensitiveInputPolicy.SECURE_REFERENCE
        and registry.lookup(definition_id).reconciliation_policy is OperationReconciliationPolicy.INTERRUPT
        and not registry.lookup(definition_id).capabilities.owned_resources
        for definition_id in definition_ids
    )


def test_field_mutation_runs_through_the_supervisor_and_real_encrypted_profile_store(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path) as root:
        profile_id = _register_profile()
        with profile_custody_secure_object_repository(profile_id=profile_id, dek=b"", root=root) as profile_objects:
            terminal, operands = _start_from_fresh_supervisor(
                root,
                profile_objects=profile_objects,
                request=OperationRequest(
                    definition_id=PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID,
                    subject_ref=f"profile:{profile_id}",
                    payload=ProfileFieldMutationOperationRequest(
                        profile_id=profile_id,
                        path="preferences.output_language",
                        value="es",
                    ),
                ),
                operation_id="a" * 64,
            )
            assert terminal.lifecycle is OperationLifecycle.TERMINAL
            assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
            assert terminal.effect is OperationEffect.UPDATED
            assert terminal.terminal_receipt is not None
            result = asyncio.run(operands.resolve(terminal.terminal_receipt.result_ref, ProfileMutationOperationResult))
            stored = ProfileRecordRepository.for_current_session(profile_id).load(profile_id)

        assert result.profile_id == profile_id
        assert result.record_revision == stored.record_revision
        assert result.content_digest == stored.content_digest
        assert record_to_path_values(stored)["preferences.output_language"] == "es"


def test_repeatable_row_mutation_allocates_and_persists_one_real_schema_row(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path) as root:
        profile_id = _register_profile()
        with profile_custody_secure_object_repository(profile_id=profile_id, dek=b"", root=root) as profile_objects:
            terminal, operands = _start_from_fresh_supervisor(
                root,
                profile_objects=profile_objects,
                request=OperationRequest(
                    definition_id=PROFILE_REPEATABLE_ROW_MUTATION_OPERATION_DEFINITION_ID,
                    subject_ref=f"profile:{profile_id}",
                    payload=ProfileRepeatableRowMutationOperationRequest(
                        profile_id=profile_id,
                        section_key="activities",
                        values=(ProfileRepeatableRowValue(field_key="description", value="Consultoria"),),
                    ),
                ),
                operation_id="b" * 64,
            )
            assert terminal.lifecycle is OperationLifecycle.TERMINAL
            assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
            assert terminal.effect is OperationEffect.UPDATED
            assert terminal.terminal_receipt is not None
            result = asyncio.run(
                operands.resolve(terminal.terminal_receipt.result_ref, ProfileRepeatableRowMutationOperationResult)
            )
            stored = ProfileRecordRepository.for_current_session(profile_id).load(profile_id)

        assert result.profile_id == profile_id
        assert result.section_key == "activities"
        assert result.row_index == 0
        assert result.record_revision == stored.record_revision
        assert record_to_path_values(stored)["activities.0.description"] == "Consultoria"


def test_bundle_export_reuses_the_real_durable_publication_and_journal(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path) as root:
        profile_id = _register_profile()
        destination = tmp_path / "profile-transfer.bundle"
        with profile_custody_secure_object_repository(profile_id=profile_id, dek=b"", root=root) as profile_objects:
            terminal, operands = _start_from_fresh_supervisor(
                root,
                profile_objects=profile_objects,
                request=OperationRequest(
                    definition_id=PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID,
                    subject_ref=f"profile:{profile_id}",
                    payload=ProfileBundleExportOperationRequest(
                        profile_id=profile_id,
                        export=ProfileBundleExportRequest(
                            destination=destination,
                            purpose=ProfileBundleExportPurpose.PORTABLE_TRANSFER,
                            transport=ProfileBundleExportTransport.PASSPHRASE_ENCRYPTED,
                            passphrase=SecretStr(_PROFILE_PASSPHRASE),
                        ),
                    ),
                ),
                operation_id="c" * 64,
            )
            assert terminal.lifecycle is OperationLifecycle.TERMINAL
            assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
            assert terminal.effect is OperationEffect.UPDATED
            assert terminal.terminal_receipt is not None
            result = asyncio.run(operands.resolve(terminal.terminal_receipt.result_ref, ProfileBundleExportResult))

        assert destination.is_file()
        assert destination.stat().st_size > 0
        assert result.profile_id == str(profile_id)
        assert result.destination == destination
        assert ProfileBundleExportJournalRepository(storage_root=root).scan().operations == ()


def test_profile_logout_strong_closes_real_custody_after_secure_request_resolution(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path) as root:
        profile_id = _register_profile()
        with profile_custody_secure_object_repository(profile_id=profile_id, dek=b"", root=root) as profile_objects:
            terminal, _operands = _start_from_fresh_supervisor(
                root,
                profile_objects=profile_objects,
                request=OperationRequest(
                    definition_id=PROFILE_LOGOUT_OPERATION_DEFINITION_ID,
                    subject_ref=f"profile:{profile_id}",
                    payload=ProfileLogoutOperationRequest(profile_id=profile_id),
                ),
                operation_id="d" * 64,
            )

        assert terminal.lifecycle is OperationLifecycle.TERMINAL
        assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
        assert terminal.effect is OperationEffect.UPDATED
        assert terminal.terminal_receipt is not None
        assert terminal.terminal_receipt.result_ref == f"profile:{profile_id}"
        assert has_active_bucket_session() is False
        assert resolve_active_bucket_id() is None
