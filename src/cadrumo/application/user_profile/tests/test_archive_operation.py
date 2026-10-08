"""Exact archive scopes and effect timing; these fixtures claim no live remote acceptance."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import replace
from pathlib import Path
from threading import Event
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ...modelo.tests.m036_operation_support import INSTANT, PROFILE_ID, policy_decision
from ...operations import profile_guard
from ...operations.access_resolution import OperationAccessContext
from ...operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from .. import archive_operation as module
from ..access_contracts import (
    AccessAction,
    AccessAllowed,
    AccessDenialCode,
    AccessDenied,
    Availability,
    DisclosureCategory,
)
from ..access_errors import ProfileAccessRefusedError
from ..archive_operation_ports import (
    ArchiveLocalWriter,
    ArchiveProviderHandoff,
    ProfileArchiveOperationPorts,
    ProfileArchivePushReport,
)
from ..bundle_export import ProfileBundleExportReconciliation, reconcile_prepared_exports
from ..bundle_export_contracts import ProfileBundleExportReconcileFailure
from ..bundle_export_operation import ProfileBundleExportJournalRepository
from .archive_operation_support import Subject, empty_push_report
from .test_bundle_export_scope import _prepared

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]


@pytest.fixture
def subject(authority_operation: PinnedAuthorityOperation, monkeypatch: pytest.MonkeyPatch) -> Subject:
    monkeypatch.setattr(profile_guard, "require_active_bucket_id", lambda: str(PROFILE_ID))
    return Subject(authority_operation)


def _registry(subject: Subject) -> OperationRegistry:
    definitions = module.build_profile_archive_operation_definitions(subject.compose)
    return OperationRegistry(
        definitions=tuple(sorted(definitions, key=lambda row: row.definition_id)),
        public_registrations=tuple(
            sorted(
                module.build_profile_archive_operation_registrations(definitions),
                key=lambda row: row.contract.definition_id,
            )
        ),
    )


def _export_request() -> OperationRequest[module.ProfileArchiveExportRequest]:
    return OperationRequest[module.ProfileArchiveExportRequest](
        definition_id=module.PROFILE_ARCHIVE_EXPORT_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(PROFILE_ID)),
        payload=module.ProfileArchiveExportRequest(
            profile_id=PROFILE_ID, target=Path("synthetic.cadrumo-bucket.tar.gz")
        ),
    )


def _push_request(*, dry_run: bool = False) -> OperationRequest[module.ProfileArchivePushRequest]:
    return OperationRequest[module.ProfileArchivePushRequest](
        definition_id=module.PROFILE_ARCHIVE_PUSH_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(PROFILE_ID)),
        payload=module.ProfileArchivePushRequest(profile_id=PROFILE_ID, dry_run=dry_run),
    )


def _reconcile_request() -> OperationRequest[module.ProfileArchiveReconcileRequest]:
    return OperationRequest[module.ProfileArchiveReconcileRequest](
        definition_id=module.PROFILE_ARCHIVE_RECONCILE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(PROFILE_ID)),
        payload=module.ProfileArchiveReconcileRequest(profile_id=PROFILE_ID),
    )


def test_real_registry_compiles_complete_human_only_family(subject: Subject) -> None:
    registry = _registry(subject)
    for definition in module.build_profile_archive_operation_definitions(subject.compose):
        assert registry.lookup_public_contract(definition.definition_id).result_schema is not None
        assert definition.permitted_frontends == frozenset({OperationFrontendProjection.CLI})
        assert OperationEffect.UNKNOWN in definition.capabilities.permitted_effects
    assert "passphrase" not in module.ProfileArchiveExportRequest.model_fields
    assert "password" not in module.ProfileArchivePushRequest.model_fields


def test_projector_preserves_partial_outcomes_and_refuses_fabricated_full_success() -> None:
    result = module.ProfileArchiveReconcileExecutionResult(
        projection=module.ProfileArchiveReconcileProjection(
            profile_id=PROFILE_ID,
            reconciled=(),
            failed=(
                ProfileBundleExportReconcileFailure(journal_id="a" * 64, destination="synthetic", reason="OSError"),
            ),
        )
    )
    receipt = OperationTerminalReceipt(
        identity=OperationIdentity(
            operation_id="b" * 64,
            definition_id=module.PROFILE_ARCHIVE_RECONCILE_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(PROFILE_ID)),
        ),
        revision=1,
        settled_at=INSTANT,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.PARTIAL,
        result_ref="d" * 64,
    )
    assert module.project_profile_archive_operation_result(result, receipt) == result.projection
    with pytest.raises(ValueError):
        module.project_profile_archive_operation_result(
            result, receipt.model_copy(update={"effect": OperationEffect.UPDATED})
        )
    wrong = receipt.identity.model_copy(update={"definition_id": module.PROFILE_ARCHIVE_EXPORT_OPERATION_DEFINITION_ID})
    with pytest.raises(ValueError):
        module.project_profile_archive_operation_result(result, receipt.model_copy(update={"identity": wrong}))


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["none", "denied", "committed"])
async def test_actual_local_writer_fence_and_uncertain_commit_settle(subject: Subject, failure: str) -> None:
    subject.fence.deny = failure == "denied"
    subject.fail_after_write = failure == "committed"
    request = _export_request()
    if failure == "none":
        await module.ProfileArchiveExportExecutor(subject.compose).execute(
            request, subject.context(request.definition_id)
        )
        result = cast(module.ProfileArchiveExportExecutionResult, subject.operands.values[-1]).projection
        assert result.receipt.to_receipt().target == str(request.payload.target)
    else:
        with pytest.raises((ProfileAccessRefusedError, OSError)):
            await module.ProfileArchiveExportExecutor(subject.compose).execute(
                request, subject.context(request.definition_id)
            )
        assert not subject.operands.values
    expected = {"none": OperationEffect.UPDATED, "denied": OperationEffect.NONE, "committed": OperationEffect.UNKNOWN}[
        failure
    ]
    assert subject.events.effects[-1] is expected
    assert subject.writes == (0 if failure == "denied" else 1)
    assert not subject.fence.active


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["dry", "empty", "handoff", "failed", "denied"])
async def test_provider_admission_releases_guard_and_never_guesses_delivery(subject: Subject, kind: str) -> None:
    subject.no_remote = kind == "empty"
    subject.fail_remote = kind == "failed"
    subject.fence.deny = kind == "denied"
    request = _push_request(dry_run=kind == "dry")
    if kind in {"failed", "denied"}:
        with pytest.raises((OSError, ProfileAccessRefusedError)):
            await module.ProfileArchivePushExecutor(subject.compose).execute(
                request, subject.context(request.definition_id)
            )
    else:
        await module.ProfileArchivePushExecutor(subject.compose).execute(
            request, subject.context(request.definition_id)
        )
    admitted = kind in {"handoff", "failed"}
    assert subject.remote_calls == int(admitted)
    assert subject.events.effects[-1] is (OperationEffect.UNKNOWN if admitted else OperationEffect.NONE)
    assert subject.writes == 0 and not subject.fence.active


@pytest.mark.asyncio
async def test_mirror_creation_receipt_has_local_fence_between_remote_handoffs(subject: Subject) -> None:
    def push(
        *,
        namespace_filter: str | None,
        limit: int | None,
        dry_run: bool,
        before_handoff: ArchiveProviderHandoff,
        write: ArchiveLocalWriter,
    ) -> ProfileArchivePushReport:
        before_handoff()
        assert not subject.fence.active

        def retain_receipt() -> None:
            assert subject.fence.active
            subject.writes += 1

        write(retain_receipt)
        assert not subject.fence.active
        before_handoff()
        assert not subject.fence.active
        return empty_push_report(dry_run=False)

    subject.ports = replace(subject.ports, push=push)
    request = _push_request()
    await module.ProfileArchivePushExecutor(subject.compose).execute(request, subject.context(request.definition_id))
    assert subject.writes == 1
    assert subject.events.effects[-1] is OperationEffect.UNKNOWN
    definition = _registry(subject).lookup(request.definition_id)
    assert OperationEffect.UPDATED in subject.events.effects
    assert set(subject.events.effects) <= definition.capabilities.permitted_effects


@pytest.mark.asyncio
async def test_cancelled_remote_owner_joins_thread_and_retains_uncertain_effect(subject: Subject) -> None:
    entered = Event()
    release = Event()
    finished = Event()

    def push(
        *,
        namespace_filter: str | None,
        limit: int | None,
        dry_run: bool,
        before_handoff: ArchiveProviderHandoff,
        write: ArchiveLocalWriter,
    ) -> ProfileArchivePushReport:
        before_handoff()
        assert not subject.fence.active
        entered.set()
        try:
            assert release.wait(5), "test must release the owned provider thread"
            return empty_push_report(dry_run=False)
        finally:
            finished.set()

    subject.ports = replace(subject.ports, push=push)
    request = _push_request()
    task = asyncio.create_task(
        module.ProfileArchivePushExecutor(subject.compose).execute(request, subject.context(request.definition_id))
    )
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done() and not finished.is_set()
    finally:
        release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert finished.is_set() and not subject.fence.active
    assert subject.events.effects[-1] is OperationEffect.UNKNOWN


@pytest.mark.asyncio
async def test_canonical_exact_profile_orphan_reconciliation_fences_real_owned_cleanup(
    subject: Subject, tmp_path: Path
) -> None:
    repository = ProfileBundleExportJournalRepository(storage_root=tmp_path)
    own, own_staged = _prepared(repository, tmp_path, str(PROFILE_ID), "own")
    foreign, foreign_staged = _prepared(repository, tmp_path, str(uuid4()), "foreign")

    def reconcile(*, write: ArchiveLocalWriter) -> ProfileBundleExportReconciliation:
        assert not subject.fence.active
        return reconcile_prepared_exports(
            journal=repository,
            profile_decode_context=subject.operation.profile_decode_context(),
            authorized_profile_id=str(PROFILE_ID),
            mutation_writer=write,
        )

    subject.ports = replace(subject.ports, reconcile=reconcile)
    request = _reconcile_request()
    await module.ProfileArchiveReconcileExecutor(subject.compose).execute(
        request, subject.context(request.definition_id)
    )
    result = cast(module.ProfileArchiveReconcileExecutionResult, subject.operands.values[-1]).projection
    assert tuple(row.operation_id for row in result.reconciled) == (own.operation_id,)
    assert not own_staged.exists() and not repository.path_for(own.operation_id).exists()
    assert foreign_staged.exists() and repository.load(foreign.operation_id) == foreign
    assert subject.fence.entries == 2 and subject.events.effects[-1] is OperationEffect.UPDATED
    assert foreign.operation_id not in result.model_dump_json()


@pytest.mark.asyncio
@pytest.mark.parametrize("uncertain", [False, True])
async def test_multiwrite_reconciliation_distinguishes_partial_from_uncertain(
    subject: Subject, uncertain: bool
) -> None:
    def reconcile(*, write: ArchiveLocalWriter) -> ProfileBundleExportReconciliation:
        def confirmed() -> None:
            assert subject.fence.active
            subject.writes += 1

        write(confirmed)
        if uncertain:

            def failed_writer() -> None:
                assert subject.fence.active
                raise OSError("synthetic uncertain cleanup")

            with suppress(OSError):
                write(failed_writer)
        return ProfileBundleExportReconciliation(
            reconciled=(),
            failures=(
                ProfileBundleExportReconcileFailure(journal_id="a" * 64, destination="synthetic", reason="OSError"),
            ),
        )

    subject.ports = replace(subject.ports, reconcile=reconcile)
    request = _reconcile_request()
    await module.ProfileArchiveReconcileExecutor(subject.compose).execute(
        request, subject.context(request.definition_id)
    )
    assert subject.events.effects[-1] is (OperationEffect.UNKNOWN if uncertain else OperationEffect.PARTIAL)


@pytest.mark.asyncio
async def test_empty_reconciliation_and_wrong_worker_pin_do_not_write(subject: Subject) -> None:
    request = _reconcile_request()
    await module.ProfileArchiveReconcileExecutor(subject.compose).execute(
        request, subject.context(request.definition_id)
    )
    assert subject.events.effects[-1] is OperationEffect.NONE and subject.fence.entries == 0
    wrong = replace(subject.ports, profile_id=uuid4())

    def compose(*, profile_id: UUID, operation: PinnedAuthorityOperation) -> ProfileArchiveOperationPorts:
        return wrong

    with pytest.raises(ProfileAccessRefusedError):
        await module.ProfileArchiveReconcileExecutor(compose).execute(request, subject.context(request.definition_id))
    assert subject.fence.entries == 0


@pytest.mark.parametrize("missing", [DisclosureCategory.PROFILE_VALUES, DisclosureCategory.TAX_VALUES, None])
def test_actual_policy_requires_complete_human_consent_and_all_periods(
    subject: Subject, missing: DisclosureCategory | None
) -> None:
    registry = _registry(subject)
    request = _export_request()
    public = OperationRequest[BaseModel](
        definition_id=request.definition_id, subject_ref=request.subject_ref, payload=request.payload
    )
    context = OperationAccessContext(
        profile_id=PROFILE_ID,
        destination_id=uuid4(),
        action=AccessAction.RESULT,
        frontend=OperationFrontendProjection.CLI,
        contract=registry.lookup_public_contract(request.definition_id),
        published_authority=Availability.AVAILABLE,
        authority_operation=subject.operation,
    )
    resolved = module.resolve_profile_archive_operation_access(public, context)
    disclosures = frozenset(row for row in resolved.policy.disclosures if row.category is not missing)
    decision = policy_decision(resolved, registry, disclosures=disclosures, human=True)
    if missing is None:
        assert isinstance(decision, AccessAllowed)
        denied = policy_decision(resolved, registry, disclosures=disclosures, human=False)
        assert isinstance(denied, AccessDenied) and denied.code is AccessDenialCode.HUMAN_AUTHORITY_REQUIRED
        restricted = policy_decision(resolved, registry, disclosures=disclosures, human=True, all_periods=False)
        assert isinstance(restricted, AccessDenied) and restricted.code is AccessDenialCode.PERIOD_DENIED
    else:
        assert isinstance(decision, AccessDenied) and decision.code is AccessDenialCode.DISCLOSURE_DENIED
    with pytest.raises(ProfileAccessRefusedError):
        module.resolve_profile_archive_operation_access(
            public, replace(context, frontend=OperationFrontendProjection.MCP)
        )
