"""Real supervisor proofs for canonical user-profile operation registrations."""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import BaseModel

from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from cadrumo.adapters.persistence.operations.secure_references import (
    OperationSecureReferenceRepository,
    operation_secure_reference_repository,
)
from ....adapters.persistence.storage import current_active_bucket_session
from ....adapters.persistence.storage.sql import SecureObjectRepository
from cadrumo.application.operations.capabilities import (
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.registry import OperationReconciliationPolicy, OperationRegistry
from cadrumo.application.operations.supervisor import OperationSupervisor
from cadrumo.core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
)
from cadrumo.application.operations.persistence.journal import OperationPersistedSnapshot
from ....core.bucket_pointer import read_pointer
from ....core.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH
from ....tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.user_profile.bundle_export_contracts import ProfileBundleExportPurpose, ProfileBundleExportResult
from cadrumo.application.user_profile.bundle_export_operation import ProfileBundleExportJournalRepository
from cadrumo.application.user_profile.custody_ports import ProfileCustodySecureObjectRepositoryPort, profile_custody_secure_object_repository
from cadrumo.application.user_profile.login_session import login_profile
from cadrumo.application.user_profile.profile_record_repository import ProfileRecordRepository
from cadrumo.application.user_profile.projections import record_to_path_values
from cadrumo.application.user_profile.registration import register_profile_with_credentials
from ..operations import (
    PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID,
    PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID,
    PROFILE_LOGOUT_OPERATION_DEFINITION_ID,
    PROFILE_REPEATABLE_ROW_MUTATION_OPERATION_DEFINITION_ID,
    USER_PROFILE_OPERATION_DEFINITIONS,
    ProfileBundleExportOperationRequest,
    ProfileFieldMutationOperationRequest,
    ProfileMutationOperationResult,
    ProfileRepeatableRowMutationOperationRequest,
    ProfileRepeatableRowMutationOperationResult,
    ProfileRepeatableRowValue,
    build_profile_logout_operation_request,
    build_user_profile_operation_registrations,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_PROFILE_PASSPHRASE = "s40-profile-operation-passphrase"  # noqa: S105 - synthetic test fixture


def _supervisor(
    root: Path,
    *,
    profile_objects: ProfileCustodySecureObjectRepositoryPort,
    owner_id: str,
    lease_token: str,
) -> tuple[OperationSupervisor, OperationSecureReferenceRepository]:
    """Build the real encrypted supervisor stack used by each family proof."""
    if not isinstance(profile_objects, SecureObjectRepository):
        raise TypeError("profile operation tests require the concrete secure-object repository")
    operands = operation_secure_reference_repository(objects=profile_objects)
    journal = OperationJournalRepository(storage_root=root)
    return (
        OperationSupervisor(
            registry=OperationRegistry(
                definitions=USER_PROFILE_OPERATION_DEFINITIONS,
                public_registrations=build_user_profile_operation_registrations(USER_PROFILE_OPERATION_DEFINITIONS),
            ),
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
    login_profile(name=outcome.profile_id, passphrase_callback=lambda: _PROFILE_PASSPHRASE)
    return UUID(outcome.profile_id)


def _start_operation(
    root: Path,
    *,
    profile_objects: ProfileCustodySecureObjectRepositoryPort,
    request: OperationRequest[BaseModel],
    operation_id: str,
) -> tuple[OperationPersistedSnapshot, OperationSecureReferenceRepository]:
    """Persist and execute one request through its real lease-owning supervisor."""
    supervisor, operands = _supervisor(
        root,
        profile_objects=profile_objects,
        owner_id="1" * 64,
        lease_token="2" * 64,
    )
    created = asyncio.run(supervisor.submit(request, operation_id=operation_id))
    return asyncio.run(supervisor.start(created)), operands


def _start_secret_operation(
    root: Path,
    *,
    profile_objects: ProfileCustodySecureObjectRepositoryPort,
    request: OperationRequest[BaseModel],
    operation_id: str,
    secret: bytes,
) -> tuple[OperationPersistedSnapshot, OperationSecureReferenceRepository]:
    """Submit one bound ephemeral secret, then run the real export executor."""
    supervisor, operands = _supervisor(
        root,
        profile_objects=profile_objects,
        owner_id="5" * 64,
        lease_token="6" * 64,
    )
    created = asyncio.run(supervisor.submit(request, operation_id=operation_id))
    requirement = asyncio.run(supervisor.inspect(created)).secret_requirement
    assert requirement is not None
    assert requirement.secret_kind == "profile.bundle-export.passphrase"  # noqa: S105
    submission = bytearray(secret)
    asyncio.run(supervisor.submit_ephemeral_secret(requirement, submission))
    assert submission == bytearray(len(secret))
    return asyncio.run(supervisor.start(created)), operands


def _assert_not_durable(root: Path, secret: bytes) -> None:
    """The one-shot export secret and derivative must not reach persistent state."""
    derivative = hashlib.sha256(secret).hexdigest().encode("ascii")
    for path in root.rglob("*"):
        if path.is_file():
            contents = path.read_bytes()
            assert secret not in contents, path
            assert derivative not in contents, path


def test_profile_operation_families_have_one_secure_registered_definition_each() -> None:
    registry = OperationRegistry(
        definitions=USER_PROFILE_OPERATION_DEFINITIONS,
        public_registrations=build_user_profile_operation_registrations(USER_PROFILE_OPERATION_DEFINITIONS),
    )
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
        and registry.lookup(definition_id).capabilities.sensitive_input
        is OperationSensitiveInputPolicy.SECURE_REFERENCE
        and registry.lookup(definition_id).reconciliation_policy is OperationReconciliationPolicy.INTERRUPT
        and not registry.lookup(definition_id).capabilities.owned_resources
        for definition_id in definition_ids
    )
    bundle_registration = registry.lookup_public_registration(PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID)
    bundle_request_binding = next(
        binding
        for binding in bundle_registration.schema_bindings
        if binding.identity.schema_id == f"{PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID}.request"
    )
    bundle_request_schema = bundle_request_binding.model_type.model_json_schema(mode="validation")

    assert bundle_registration.contract.ephemeral_secret_required is True
    assert bundle_registration.contract.request_schema == bundle_request_binding.identity
    assert set(ProfileBundleExportOperationRequest.model_fields) == {"profile_id", "destination", "purpose"}
    assert "passphrase" not in json.dumps(bundle_request_schema).lower()


def test_field_mutation_runs_through_the_supervisor_and_real_encrypted_profile_store(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path) as root:
        profile_id = _register_profile()
        with profile_custody_secure_object_repository(profile_id=profile_id, dek=b"", root=root) as profile_objects:
            terminal, operands = _start_operation(
                root,
                profile_objects=profile_objects,
                request=OperationRequest(
                    definition_id=PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID,
                    subject_ref=f"profile:{profile_id}",
                    payload=ProfileFieldMutationOperationRequest(
                        profile_id=profile_id,
                        path=PROFILE_OUTPUT_LANGUAGE_PATH,
                        value="es",
                    ),
                ),
                operation_id="a" * 64,
            )
            assert terminal.lifecycle is OperationLifecycle.TERMINAL
            assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
            assert terminal.effect is OperationEffect.UPDATED
            assert terminal.terminal_receipt is not None
            assert terminal.terminal_receipt.result_ref is not None
            result = asyncio.run(operands.resolve(terminal.terminal_receipt.result_ref, ProfileMutationOperationResult))
            stored = ProfileRecordRepository.for_current_session(profile_id).load(profile_id)

        assert result.profile_id == profile_id
        assert result.record_revision == stored.record_revision
        assert result.content_digest == stored.content_digest
        assert record_to_path_values(stored)[PROFILE_OUTPUT_LANGUAGE_PATH] == "es"


def test_repeatable_row_mutation_allocates_and_persists_one_real_schema_row(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path) as root:
        profile_id = _register_profile()
        with profile_custody_secure_object_repository(profile_id=profile_id, dek=b"", root=root) as profile_objects:
            terminal, operands = _start_operation(
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
            assert terminal.terminal_receipt.result_ref is not None
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
            terminal, operands = _start_secret_operation(
                root,
                profile_objects=profile_objects,
                request=OperationRequest(
                    definition_id=PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID,
                    subject_ref=f"profile:{profile_id}",
                    payload=ProfileBundleExportOperationRequest(
                        profile_id=profile_id,
                        destination=destination,
                        purpose=ProfileBundleExportPurpose.PORTABLE_TRANSFER,
                    ),
                ),
                operation_id="c" * 64,
                secret=_PROFILE_PASSPHRASE.encode("utf-8"),
            )
            assert terminal.lifecycle is OperationLifecycle.TERMINAL
            assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
            assert terminal.effect is OperationEffect.UPDATED
            assert terminal.terminal_receipt is not None
            assert terminal.terminal_receipt.result_ref is not None
            result = asyncio.run(operands.resolve(terminal.terminal_receipt.result_ref, ProfileBundleExportResult))

        assert destination.is_file()
        assert destination.stat().st_size > 0
        assert result.profile_id == str(profile_id)
        assert result.destination == destination
        assert ProfileBundleExportJournalRepository(storage_root=root).scan().operations == ()
        _assert_not_durable(root, _PROFILE_PASSPHRASE.encode("utf-8"))


def test_profile_logout_strong_closes_real_custody_after_secure_request_resolution(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path) as root:
        profile_id = _register_profile()
        live_session = current_active_bucket_session()
        assert live_session is not None
        assert read_pointer(root).bucket_id is not None
        with profile_custody_secure_object_repository(profile_id=profile_id, dek=b"", root=root) as profile_objects:

            async def _run_strong_close() -> OperationPersistedSnapshot:
                supervisor, _operands = _supervisor(
                    root,
                    profile_objects=profile_objects,
                    owner_id="7" * 64,
                    lease_token="8" * 64,
                )
                created = await supervisor.submit(
                    build_profile_logout_operation_request(profile_id),
                    operation_id="d" * 64,
                )
                terminal = await supervisor.start(created)
                return terminal

            terminal = asyncio.run(_run_strong_close())

        assert terminal.lifecycle is OperationLifecycle.TERMINAL
        assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
        assert terminal.effect is OperationEffect.UPDATED
        assert terminal.terminal_receipt is not None
        assert terminal.terminal_receipt.result_ref == f"profile:{profile_id}"
        assert read_pointer(root).bucket_id is None
        assert live_session.sealed is True
