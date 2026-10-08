"""Ledger reset registration keeps exact-profile access and complete receipts."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ....core.operations import profile_operation_subject
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationRequest
from ...operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationRegistry,
)
from ...user_profile.access_contracts import AccessAction, Availability
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..action_ports import LedgerActionPorts
from ..reset_operation import (
    LEDGER_RESET_OPERATION_DEFINITION_ID,
    LedgerResetBlockerProjection,
    LedgerResetOperationResult,
    LedgerResetReportProjection,
    LedgerResetRequest,
    build_ledger_reset_definition,
    build_ledger_reset_registration,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")


def _unused_ports(*, bucket_id: str, operation: PinnedAuthorityOperation) -> LedgerActionPorts:
    raise AssertionError(f"unexpected operation execution for {bucket_id} with {operation!r}")


def _registry() -> tuple[OperationRegistry, OperationPublicDefinitionRegistrationV1]:
    definition = build_ledger_reset_definition(_unused_ports)
    registration = build_ledger_reset_registration(definition)
    return OperationRegistry(definitions=(definition,), public_registrations=(registration,)), registration


def _request(*, profile_id: UUID = _PROFILE, dry_run: bool = False) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=LEDGER_RESET_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
        payload=LedgerResetRequest(profile_id=profile_id, reason="reset contaminated import", dry_run=dry_run),
    )


def _access_context(
    registration: OperationPublicDefinitionRegistrationV1,
    *,
    profile_id: UUID = _PROFILE,
    action: AccessAction,
) -> OperationAccessContext:
    return OperationAccessContext(
        profile_id=profile_id,
        destination_id=uuid4(),
        action=action,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
    )


def _report(*, bucket_id: str = str(_PROFILE)) -> LedgerResetReportProjection:
    blocker = LedgerResetBlockerProjection(
        work_unit_id="b" * 64,
        calculation_revision_id="c" * 64,
        revision_state="FINALIZED",
        modelo="303",
        filing_year=2025,
        period="1T",
    )
    return LedgerResetReportProjection(
        bucket_id=bucket_id,
        removed_transaction_ids=("a" * 64,),
        dry_run=True,
        actor="operator",
        reason="reset contaminated import",
        cascaded_purchase_invoice_evidence_ids=("d" * 64,),
        cascaded_attachment_ids=("e" * 64,),
        blocking_modelo_references=(blocker,),
        stale_draft_revision_references=(blocker,),
        bucket_event_ids=("f" * 64,),
    )


def test_registered_result_roundtrips_all_reset_findings() -> None:
    _registry()
    result = LedgerResetOperationResult(profile_id=_PROFILE, report=_report())

    assert LedgerResetOperationResult.model_validate_json(result.model_dump_json()) == result
    assert result.report.removed_transaction_ids == ("a" * 64,)
    assert result.report.cascaded_purchase_invoice_evidence_ids == ("d" * 64,)
    assert result.report.cascaded_attachment_ids == ("e" * 64,)
    assert result.report.blocking_modelo_references[0].calculation_revision_id == "c" * 64
    assert result.report.stale_draft_revision_references[0].work_unit_id == "b" * 64
    assert result.report.bucket_event_ids == ("f" * 64,)


def test_registered_result_refuses_over_limit_collection_without_truncating() -> None:
    oversized = _report().model_dump(mode="python")
    oversized["removed_transaction_ids"] = ("a" * 64,) * 4097

    with pytest.raises(ValidationError):
        LedgerResetReportProjection.model_validate(oversized)


@pytest.mark.parametrize(
    ("dry_run", "action", "requires_commit"),
    (
        (True, AccessAction.SUBMIT, False),
        (False, AccessAction.SUBMIT, True),
    ),
)
def test_access_adds_commit_only_for_confirmed_reset(
    dry_run: bool,
    action: AccessAction,
    requires_commit: bool,
) -> None:
    registry, registration = _registry()
    resolved = resolve_operation_access(
        registry=registry,
        request=_request(dry_run=dry_run),
        context=_access_context(registration, action=action),
    )

    assert (AccessAction.COMMIT in resolved.policy.actions) is requires_commit


def test_access_refuses_a_request_for_a_different_profile() -> None:
    registry, registration = _registry()

    with pytest.raises(ProfileAccessRefusedError):
        resolve_operation_access(
            registry=registry,
            request=_request(profile_id=_OTHER_PROFILE),
            context=_access_context(registration, profile_id=_PROFILE, action=AccessAction.SUBMIT),
        )
