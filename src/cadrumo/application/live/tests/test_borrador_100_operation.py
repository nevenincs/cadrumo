"""Canonical lifecycle, real consent decisions and separately reviewed projections.

These inward unit fixtures do not claim native encrypted-storage acceptance.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ....core.errors.hierarchy import InternalInvariantError
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ...operations import profile_guard
from ...operations.access_resolution import OperationAccessContext
from ...operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ...operations.public_period import PublicPeriod
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ...user_profile.access_contracts import (
    AccessAction,
    AccessAllowed,
    AccessDenialCode,
    AccessDenied,
    Availability,
    DisclosureCategory,
)
from ...user_profile.access_errors import ProfileAccessRefusedError
from .. import borrador_100 as service_module
from .. import borrador_100_operation as module
from ..borrador_100 import Borrador100Snapshot, Borrador100SnapshotService, BorradorSnapshotNotFoundError
from ..borrador_100_import import prepare_borrador_100_import
from ..borrador_100_operation_ports import Borrador100OperationPorts
from ..errors import LiveApplicationInputError
from ..snapshot_base import SnapshotLifecycleState, SnapshotStateFilter
from .borrador_100_operation_support import CAPTURED_AT, PROFILE_ID, Subject, policy_decision
from .test_borrador_100 import _InMemoryBorradorRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]
_PERIOD = Period.from_year_and_code(2023, "0A")
_HUMAN_SOURCE = "file-import:sha256:" + "a" * 64


def _read_request(*, query: bool = False, **selectors: object) -> OperationRequest[module.Borrador100ReadRequest]:
    return OperationRequest[module.Borrador100ReadRequest](
        definition_id=module.BORRADOR_100_QUERY_OPERATION_DEFINITION_ID
        if query
        else module.BORRADOR_100_READ_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(PROFILE_ID)),
        payload=module.Borrador100ReadRequest.model_validate({"profile_id": PROFILE_ID, **selectors}),
    )


def _import_request(path: Path) -> OperationRequest[module.Borrador100ImportRequest]:
    return OperationRequest[module.Borrador100ImportRequest](
        definition_id=module.BORRADOR_100_IMPORT_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(PROFILE_ID)),
        payload=module.Borrador100ImportRequest(
            profile_id=PROFILE_ID,
            source_path=path,
            filing_year=_PERIOD.filing_year,
            period=PublicPeriod.from_period(_PERIOD),
        ),
    )


def _snapshot(operation: PinnedAuthorityOperation, *, minute: int = 0) -> Borrador100Snapshot:
    repository = _InMemoryBorradorRepository(bucket_id=str(PROFILE_ID))
    return Borrador100SnapshotService(bucket_id=str(PROFILE_ID), repository=repository).capture(
        filing_year=_PERIOD.filing_year,
        period=_PERIOD,
        captured_at=CAPTURED_AT + timedelta(minutes=minute),
        source_url=_HUMAN_SOURCE,
        binding_values={"casilla.0550": Decimal("0.00"), "casilla.0699": ""},
        operation=operation,
    )


def _registry(operation: PinnedAuthorityOperation) -> OperationRegistry:
    subject = Subject(operation)
    definitions = module.build_borrador_100_operation_definitions(subject.compose)
    return OperationRegistry(
        definitions=tuple(sorted(definitions, key=lambda definition: definition.definition_id)),
        public_registrations=tuple(
            sorted(
                module.build_borrador_100_operation_registrations(definitions),
                key=lambda registration: registration.contract.definition_id,
            )
        ),
    )


@pytest.fixture
def subject(monkeypatch: pytest.MonkeyPatch, authority_operation: PinnedAuthorityOperation) -> Subject:
    monkeypatch.setattr(profile_guard, "require_active_bucket_id", lambda: str(PROFILE_ID))
    monkeypatch.setattr(module, "now", lambda: CAPTURED_AT)
    return Subject(authority_operation)


def test_real_registration_compiles_distinct_closed_human_query_and_import_schemas(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    registry = _registry(authority_operation)
    human = registry.lookup_public_contract(module.BORRADOR_100_READ_OPERATION_DEFINITION_ID)
    query = registry.lookup_public_contract(module.BORRADOR_100_QUERY_OPERATION_DEFINITION_ID)
    importing = registry.lookup_public_contract(module.BORRADOR_100_IMPORT_OPERATION_DEFINITION_ID)
    assert human.result_schema is not None and query.result_schema is not None and importing.result_schema is not None
    assert human.result_schema.schema_id != query.result_schema.schema_id
    assert "source_url" in module.Borrador100SnapshotDetail.model_fields
    assert "source_url" not in module.Borrador100QueryDetail.model_fields
    assert "source_url" not in module.Borrador100QuerySummary.model_fields
    assert "warnings" in module.Borrador100ImportProjection.model_fields


@pytest.mark.asyncio
async def test_shared_canonical_view_preserves_scalars_and_withholds_query_provenance(subject: Subject) -> None:
    snapshot = _snapshot(subject.operation)
    subject.repository.seed(snapshot)
    for query in (False, True):
        request = _read_request(query=query, kind="view", snapshot_id=snapshot.snapshot_id[:16])
        await module.Borrador100ReadExecutor(subject.compose, query=query).execute(
            request, subject.context(request.definition_id)
        )
    human = cast(module.Borrador100ReadExecutionResult, subject.operands.values[0]).projection
    safe = cast(module.Borrador100QueryExecutionResult, subject.operands.values[1]).projection
    assert human.snapshot is not None and safe.snapshot is not None
    assert human.snapshot.source_url == snapshot.source_url
    assert human.snapshot.binding_map() == safe.snapshot.binding_map() == dict(snapshot.binding_values)
    assert safe.snapshot.binding_values[0].value == module.PublicDecimal(decimal="0.00")
    assert safe.snapshot.binding_values[1].value == ""
    assert safe.snapshot.period.to_period() == _PERIOD
    assert _HUMAN_SOURCE not in safe.model_dump_json() and "source_url" not in safe.model_dump_json()
    assert subject.repository.writes == subject.fence.entries == 0
    assert subject.parser.calls == 0 and set(subject.events.effects) == {OperationEffect.NONE}


@pytest.mark.asyncio
async def test_canonical_list_state_order_and_empty_latest_keep_exact_pin(
    subject: Subject, monkeypatch: pytest.MonkeyPatch
) -> None:
    older = _snapshot(subject.operation)
    newer = _snapshot(subject.operation, minute=1)
    subject.repository.seed(
        older.model_copy(
            update={"state": SnapshotLifecycleState.SUPERSEDED, "superseded_by_snapshot_id": newer.snapshot_id}
        )
    )
    subject.repository.seed(newer)

    def ambient_authority() -> None:
        raise AssertionError("worker reads must use the existing authority pin")

    monkeypatch.setattr(service_module, "bundled_indexed_authority", ambient_authority)
    request = _read_request(kind="list", state=SnapshotStateFilter.ALL)
    await module.Borrador100ReadExecutor(subject.compose, query=False).execute(
        request, subject.context(request.definition_id)
    )
    result = cast(module.Borrador100ReadExecutionResult, subject.operands.values[-1]).projection
    assert tuple(row.snapshot_id for row in result.rows) == (older.snapshot_id, newer.snapshot_id)
    assert tuple(row.state for row in result.rows) == (SnapshotLifecycleState.SUPERSEDED, SnapshotLifecycleState.ACTIVE)
    request = _read_request(query=True, kind="latest", filing_year=2024)
    await module.Borrador100ReadExecutor(subject.compose, query=True).execute(
        request, subject.context(request.definition_id)
    )
    latest = cast(module.Borrador100QueryExecutionResult, subject.operands.values[-1]).projection
    assert latest.filing_year == 2024 and latest.snapshot is None and latest.rows == ()


@pytest.mark.asyncio
async def test_wrong_profile_ports_refuse_before_repository_read(subject: Subject) -> None:
    wrong = replace(subject.ports, profile_id=uuid4())

    def compose(*, profile_id: UUID, operation: PinnedAuthorityOperation) -> Borrador100OperationPorts:
        return wrong

    request = _read_request(query=True, kind="list")
    with pytest.raises(ProfileAccessRefusedError):
        await module.Borrador100ReadExecutor(compose, query=True).execute(
            request, subject.context(request.definition_id)
        )
    assert subject.repository.reads == subject.repository.writes == 0


@pytest.mark.asyncio
async def test_view_keeps_canonical_prefix_ambiguity_refusal(subject: Subject) -> None:
    first = _snapshot(subject.operation).model_copy(update={"snapshot_id": "a" * 64})
    second = _snapshot(subject.operation, minute=1).model_copy(update={"snapshot_id": "a" * 63 + "b"})
    subject.repository.seed(first)
    subject.repository.seed(second)
    request = _read_request(query=True, kind="view", snapshot_id="a")
    with pytest.raises(BorradorSnapshotNotFoundError):
        await module.Borrador100ReadExecutor(subject.compose, query=True).execute(
            request, subject.context(request.definition_id)
        )
    assert not subject.operands.values


@pytest.mark.asyncio
async def test_import_reads_once_preserves_blank_zero_warnings_and_noop_dedup(
    subject: Subject,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "synthetic-local-input.pdf"
    path.write_bytes(b"synthetic source capture")
    original = Path.read_bytes
    reads: list[Path] = []

    def read_once(source: Path) -> bytes:
        reads.append(source)
        captured = original(source)
        source.write_bytes(b"subsequent source changes cannot affect this capture")
        return captured

    monkeypatch.setattr(Path, "read_bytes", read_once)
    request = _import_request(path)
    await module.Borrador100ImportExecutor(subject.compose).execute(request, subject.context(request.definition_id))
    assert reads == [path] and subject.parser.calls == subject.repository.writes == subject.fence.entries == 1
    result = cast(module.Borrador100ImportExecutionResult, subject.operands.values[-1]).projection
    receipt = subject.parser.receipt
    assert receipt is not None
    assert result.source_pdf_sha256 == receipt.source_pdf_sha256
    assert result.blank_casillas == (receipt.values[0].casilla_id,)
    assert result.warnings == receipt.warnings and result.extraction_coverage.decimal == "1"
    snapshot = subject.repository.load(result.snapshot.snapshot_id)
    assert "casilla." + receipt.values[0].casilla_id not in snapshot.binding_values
    assert snapshot.binding_values["casilla." + receipt.values[1].casilla_id] == Decimal("0.00")
    assert subject.events.effects[-1] is OperationEffect.UPDATED
    assert all("synthetic source" not in phase and str(path) not in phase for phase in subject.events.phases)
    path.write_bytes(b"synthetic source capture")
    await module.Borrador100ImportExecutor(subject.compose).execute(request, subject.context(request.definition_id))
    assert subject.repository.writes == subject.fence.entries == 1
    assert subject.events.effects[-1] is OperationEffect.NONE


@pytest.mark.asyncio
async def test_import_reuses_actual_multi_save_supersession(subject: Subject, tmp_path: Path) -> None:
    prior = _snapshot(subject.operation, minute=-1)
    subject.repository.seed(prior)
    path = tmp_path / "synthetic.pdf"
    path.write_bytes(b"source")
    request = _import_request(path)
    await module.Borrador100ImportExecutor(subject.compose).execute(request, subject.context(request.definition_id))
    result = cast(module.Borrador100ImportExecutionResult, subject.operands.values[-1]).projection
    assert subject.repository.writes == subject.fence.entries == 2
    assert subject.repository.load(prior.snapshot_id).superseded_by_snapshot_id == result.snapshot.snapshot_id
    assert subject.repository.load(result.snapshot.snapshot_id).state is SnapshotLifecycleState.ACTIVE
    assert subject.events.effects[-1] is OperationEffect.UPDATED


@pytest.mark.parametrize("defect", ["year", "profile", "coverage"])
def test_prepare_refuses_bad_parser_receipt_before_commit(subject: Subject, tmp_path: Path, defect: str) -> None:
    if defect == "year":
        subject.parser.change = {"ejercicio": "2024"}
    elif defect == "profile":
        subject.parser.change = {"extraction_profile_id": "different-profile"}
    else:
        subject.parser.change = {"extraction_coverage": None}
    path = tmp_path / "synthetic.pdf"
    path.write_bytes(b"source")
    with pytest.raises((LiveApplicationInputError, InternalInvariantError)):
        prepare_borrador_100_import(
            path, filing_year=_PERIOD.filing_year, period=_PERIOD, operation=subject.operation, parser=subject.parser
        )
    assert subject.repository.writes == subject.fence.entries == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure,expected",
    [
        ("first_denied", OperationEffect.NONE),
        ("second_denied", OperationEffect.PARTIAL),
        ("committed_raise", OperationEffect.UNKNOWN),
    ],
)
async def test_import_settles_actual_writer_failure_without_claiming_rollback(
    subject: Subject,
    tmp_path: Path,
    failure: str,
    expected: OperationEffect,
) -> None:
    if failure == "second_denied":
        subject.repository.seed(_snapshot(subject.operation, minute=-1))
        subject.fence.deny_entry = 2
    elif failure == "first_denied":
        subject.fence.deny_entry = 1
    else:
        subject.repository.fail_after_save = True
    path = tmp_path / "synthetic.pdf"
    path.write_bytes(b"source")
    request = _import_request(path)
    with pytest.raises((ProfileAccessRefusedError, ValueError)):
        await module.Borrador100ImportExecutor(subject.compose).execute(request, subject.context(request.definition_id))
    assert subject.events.effects[-1] is expected
    assert subject.repository.writes == (0 if failure == "first_denied" else 1)
    assert not subject.fence.active and not subject.operands.values


@pytest.mark.parametrize("missing", [DisclosureCategory.PROFILE_VALUES, DisclosureCategory.TAX_VALUES, None])
def test_agent_query_requires_both_exact_destination_disclosures(
    authority_operation: PinnedAuthorityOperation,
    missing: DisclosureCategory | None,
) -> None:
    registry = _registry(authority_operation)
    request = _read_request(query=True, kind="list")
    public = OperationRequest[BaseModel](
        definition_id=request.definition_id, subject_ref=request.subject_ref, payload=request.payload
    )
    resolved = module.resolve_borrador_100_access(
        public,
        OperationAccessContext(
            profile_id=PROFILE_ID,
            destination_id=uuid4(),
            action=AccessAction.RESULT,
            frontend=OperationFrontendProjection.MCP,
            contract=registry.lookup_public_contract(request.definition_id),
            published_authority=Availability.AVAILABLE,
            authority_operation=authority_operation,
        ),
    )
    permissions = frozenset(
        permission for permission in resolved.policy.disclosures if permission.category is not missing
    )
    decision = policy_decision(resolved, registry, disclosures=permissions)
    if missing is None:
        assert isinstance(decision, AccessAllowed)
        restricted = policy_decision(resolved, registry, disclosures=permissions, all_periods=False)
        assert isinstance(restricted, AccessDenied) and restricted.code is AccessDenialCode.PERIOD_DENIED
    else:
        assert isinstance(decision, AccessDenied) and decision.code is AccessDenialCode.DISCLOSURE_DENIED


def test_query_consent_never_authorizes_full_read_or_import(
    authority_operation: PinnedAuthorityOperation, tmp_path: Path
) -> None:
    registry = _registry(authority_operation)
    for request in (_read_request(kind="list"), _import_request(tmp_path / "private.pdf")):
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
            authority_operation=authority_operation,
        )
        resolved = module.resolve_borrador_100_access(public, context)
        assert resolved.policy.requires_human and resolved.policy.requires_all_periods
        allowed = policy_decision(resolved, registry, disclosures=resolved.policy.disclosures, human=True)
        assert isinstance(allowed, AccessAllowed)
        denied = policy_decision(
            resolved,
            registry,
            disclosures=resolved.policy.disclosures,
            operations=frozenset({module.BORRADOR_100_QUERY_OPERATION_DEFINITION_ID}),
            human=True,
        )
        assert isinstance(denied, AccessDenied) and denied.code is AccessDenialCode.OPERATION_DENIED
        with pytest.raises(ProfileAccessRefusedError):
            module.resolve_borrador_100_access(public, replace(context, frontend=OperationFrontendProjection.MCP))


def test_projector_rejects_cross_purpose_receipt(subject: Subject) -> None:
    result = module.Borrador100QueryExecutionResult(
        projection=module.Borrador100QueryProjection(profile_id=PROFILE_ID, kind="list")
    )
    receipt = OperationTerminalReceipt(
        identity=OperationIdentity(
            operation_id="a" * 64,
            definition_id=module.BORRADOR_100_QUERY_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(PROFILE_ID)),
        ),
        revision=1,
        settled_at=CAPTURED_AT,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.NONE,
        result_ref="d" * 64,
    )
    assert module.project_borrador_100_result(result, receipt) == result.projection
    with pytest.raises(ValueError):
        module.project_borrador_100_result(
            result,
            receipt.model_copy(
                update={
                    "identity": receipt.identity.model_copy(
                        update={"definition_id": module.BORRADOR_100_READ_OPERATION_DEFINITION_ID}
                    )
                }
            ),
        )
    with pytest.raises(ValidationError):
        module.Borrador100ReadRequest(profile_id=PROFILE_ID, kind="list", filing_year=2025)
