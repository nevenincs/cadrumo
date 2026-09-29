"""Real registered administration executors, secret broker, journal and encrypted custody."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.persistence.operations.financial_operand_custody import (
    OperationFinancialOperandCustodyFilesystemRepository,
)
from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from cadrumo.adapters.persistence.operations.secure_references import operation_secure_reference_repository
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import (
    NOW,
    PROFILE_INPUT,
    administration_subject,
    changed,
)
from cadrumo.application.operations.composition import compose_operation_services
from cadrumo.application.operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
)
from cadrumo.application.operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from cadrumo.application.user_profile.automation_administration import inspect_automation_inventory
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from cadrumo.application.user_profile.automation_enrollment import (
    AutomationInventoryProjection,
    EnrollmentKind,
    EnrollmentStage,
)
from cadrumo.application.user_profile.automation_execution import ThreadedAutomationAdministration
from cadrumo.application.user_profile.automation_operations import (
    AutomationOperationRequest,
    build_automation_operation_definitions,
    project_automation_inventory_result,
)
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.entrypoints.operation_composition import build_production_operation_registry

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_human_inventory_remains_visible_after_automation_is_disabled(tmp_path: Path) -> None:
    """Disablement blocks mutation but cannot hide a surviving consent request."""
    with administration_subject(tmp_path) as subject:
        request_id = uuid4()
        subject.service.request(request_id, subject.proposal)
        state = subject.store.enrollment_state()
        subject.store.publish_enrollment(changed(state, automation_enabled=False))
        with pytest.raises(AutomationCustodyError) as mismatch:
            inspect_automation_inventory(custody=subject.store, owner=subject.owner)
        assert mismatch.value.reason is AutomationCustodyCode.NEEDS_USER
        subject.owner.current = changed(
            subject.owner.current,
            profile=changed(subject.owner.current.profile, automation_enabled=False),
        )
        inventory = inspect_automation_inventory(custody=subject.store, owner=subject.owner)
        assert inventory == subject.service.inventory()
        assert tuple(item.receipt.request_id for item in inventory.requests) == (request_id,)
        receipt = OperationTerminalReceipt(
            identity=OperationIdentity(
                operation_id="a" * 64,
                definition_id="user-profile.automation-inventory",
                subject_ref=profile_operation_subject(str(subject.store.binding.profile_id)),
            ),
            revision=3,
            condition=OperationTerminalCondition.SUCCEEDED,
            effect=OperationEffect.NONE,
            settled_at=NOW,
            result_ref="inventory:synthetic-human",
        )
        projected = project_automation_inventory_result(inventory, receipt)
        assert isinstance(projected, AutomationInventoryProjection)
        assert tuple(item.receipt.request_id for item in projected.requests) == (request_id,)
        assert projected.requests[0].proposal.scope.operations == tuple(sorted(subject.proposal.scope.operations))
        with pytest.raises(ValueError, match="settled subject"):
            project_automation_inventory_result(
                inventory,
                receipt.model_copy(
                    update={
                        "identity": receipt.identity.model_copy(
                            update={"subject_ref": profile_operation_subject(str(uuid4()))}
                        )
                    }
                ),
            )
        with pytest.raises(AutomationCustodyError) as mutation:
            subject.service.request(uuid4(), subject.proposal)
        assert mutation.value.reason is AutomationCustodyCode.NEEDS_USER


def test_registered_enrollment_lifecycle_uses_real_supervisor_and_protected_operands(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    with administration_subject(tmp_path) as subject:
        registry = build_production_operation_registry(
            automation_administration_factory=lambda _context, _profile: ThreadedAutomationAdministration(
                subject.service
            )
        )
        journal = OperationJournalRepository(storage_root=subject.store.root / "operations")
        services = compose_operation_services(
            registry=registry,
            authority_operation=authority_operation,
            journal=journal,
            reader=journal,
            event_stream=journal,
            leases=OperationLeaseFilesystemRepository(storage_root=subject.store.root / "operations"),
            operands=operation_secure_reference_repository(),
            owner_id="1" * 64,
            lease_token_factory=lambda: "2" * 64,
            clock=lambda: NOW,
            lease_duration=timedelta(minutes=10),
            execution_timeout=timedelta(minutes=5),
            cleanup_timeout=timedelta(seconds=20),
            financial_operand_custody=OperationFinancialOperandCustodyFilesystemRepository(
                root=subject.store.root / "financial"
            ),
        )
        exercised: set[str] = set()

        async def invoke(action: str, identity: UUID, *, secret: bytes | None = None, reviewed: bool = False):
            definition_id = "user-profile.automation-" + action
            digest = None
            if reviewed:
                digest = next(
                    item.receipt.review_digest
                    for item in subject.service.inventory().requests
                    if item.receipt.request_id == identity
                )
            submitted = await services.submission.submit(
                OperationRequest(
                    definition_id=definition_id,
                    subject_ref=f"profile:{subject.store.binding.profile_id}",
                    payload=AutomationOperationRequest(
                        profile_id=subject.store.binding.profile_id, request_id=identity, review_digest=digest
                    ),
                ),
                actor_ref="operator:synthetic-human",
            )
            requirement = submitted.receipt.secret_requirement
            if requirement is not None:
                assert secret is not None
                buffer = bytearray(secret)
                await services.submission.submit_secret(requirement, buffer)
                assert buffer == bytearray(len(secret))
            await services.submission.start(submitted.receipt.operation_id)
            await services.submission.settled(submitted.receipt.operation_id)
            observed = await services.observation.observe(
                OperationObservationRequestV1(
                    operation_id=submitted.receipt.operation_id, after_cursor=0, page_limit=100
                )
            )
            assert isinstance(observed, OperationObservationSuccessV1)
            assert observed.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED, observed
            assert observed.projection.effect is (
                OperationEffect.NONE if action == "inventory" else OperationEffect.UPDATED
            )
            exercised.add(definition_id)

        async def run() -> None:
            try:
                first = uuid4()
                await invoke("request", first, secret=subject.proposal.model_dump_json().encode())
                await invoke("approve", first, secret=PROFILE_INPUT.encode(), reviewed=True)
                await invoke("inventory", uuid4())
                enrolled = subject.service.inventory().requests[0].receipt
                rotation = changed(
                    subject.proposal,
                    kind=EnrollmentKind.ROTATE,
                    target_grant_id=enrolled.grant_id,
                    target_key_id=enrolled.key_id,
                )
                rotating = uuid4()
                await invoke("rotate", rotating, secret=rotation.model_dump_json().encode())
                await invoke("approve", rotating, secret=PROFILE_INPUT.encode(), reviewed=True)
                renewal = changed(
                    subject.proposal,
                    kind=EnrollmentKind.RENEW,
                    key_expires_at=None,
                    target_grant_id=enrolled.grant_id,
                    expires_at=subject.proposal.expires_at + timedelta(days=1),
                )
                renewing = uuid4()
                await invoke("renew", renewing, secret=renewal.model_dump_json().encode())
                await invoke("approve", renewing, secret=PROFILE_INPUT.encode(), reviewed=True)
                scope = changed(
                    renewal, kind=EnrollmentKind.CHANGE_SCOPE, scope=changed(renewal.scope, actions=frozenset())
                )
                changing = uuid4()
                await invoke("scope", changing, secret=scope.model_dump_json().encode())
                await invoke("approve", changing, secret=PROFILE_INPUT.encode(), reviewed=True)
                declined = uuid4()
                await invoke("request", declined, secret=subject.proposal.model_dump_json().encode())
                await invoke("decline", declined, reviewed=True)
                assert (
                    next(
                        item for item in subject.store.enrollment_state().requests if item.request_id == declined
                    ).stage
                    is EnrollmentStage.DECLINED
                )
            finally:
                await services.shutdown()

        asyncio.run(run())
        assert exercised == {item.definition_id for item in build_automation_operation_definitions()}
        secrets = [PROFILE_INPUT.encode(), *(item.get_secret_value() for item in subject.client_native.items.values())]
        for record in subject.store.enrollment_state().requests:
            if record.candidate_key_id is not None:
                credential = subject.owner.delivery.endpoint.possession(record)
                assert credential is not None
                secrets.append(credential.get_secret_value())
        captured = capsys.readouterr()
        rendered = (captured.out + captured.err + caplog.text).encode()
        assert all(value not in rendered for value in secrets)
        for path in subject.store.root.rglob("*"):
            if path.is_file():
                data = path.read_bytes()
                assert all(value not in data for value in secrets), path


def test_missing_runtime_owner_refuses_registered_operations_without_effect(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    with administration_subject(tmp_path) as subject:
        registry = build_production_operation_registry()
        journal = OperationJournalRepository(storage_root=subject.store.root / "operations")
        services = compose_operation_services(
            registry=registry,
            authority_operation=authority_operation,
            journal=journal,
            reader=journal,
            event_stream=journal,
            leases=OperationLeaseFilesystemRepository(storage_root=subject.store.root / "operations"),
            operands=operation_secure_reference_repository(),
            owner_id="3" * 64,
            lease_token_factory=lambda: "4" * 64,
            clock=lambda: NOW,
            lease_duration=timedelta(minutes=10),
            execution_timeout=timedelta(minutes=5),
            cleanup_timeout=timedelta(seconds=20),
            financial_operand_custody=OperationFinancialOperandCustodyFilesystemRepository(
                root=subject.store.root / "financial"
            ),
        )

        async def run() -> None:
            try:
                for definition in build_automation_operation_definitions():
                    submitted = await services.submission.submit(
                        OperationRequest(
                            definition_id=definition.definition_id,
                            subject_ref=f"profile:{subject.store.binding.profile_id}",
                            payload=AutomationOperationRequest(
                                profile_id=subject.store.binding.profile_id, request_id=uuid4()
                            ),
                        ),
                        actor_ref="operator:test-actor",
                    )
                    if submitted.receipt.secret_requirement is not None:
                        await services.submission.submit_secret(
                            submitted.receipt.secret_requirement, bytearray(b"synthetic")
                        )
                    await services.submission.start(submitted.receipt.operation_id)
                    await services.submission.settled(submitted.receipt.operation_id)
                    observed = await services.observation.observe(
                        OperationObservationRequestV1(
                            operation_id=submitted.receipt.operation_id, after_cursor=0, page_limit=100
                        )
                    )
                    assert isinstance(observed, OperationObservationSuccessV1)
                    assert observed.projection.terminal_condition is OperationTerminalCondition.REFUSED
                    assert observed.projection.refusal_ref == "REFUSED_AUTOMATION_ADMINISTRATION"
                    assert observed.projection.effect is OperationEffect.NONE
            finally:
                await services.shutdown()

        asyncio.run(run())
        assert subject.store.enrollment_state().revision == 0
