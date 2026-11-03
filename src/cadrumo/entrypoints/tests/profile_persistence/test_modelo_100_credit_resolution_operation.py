"""The registered credit-resolution operations run against the real composed stores, authority and gates.

Only the operation host's event and operand plumbing is a minimal stand-in. A
Modelo 100 whose two withholding credits disagree with the borrador is
calculated for real; the operations accept, revoke and list its resolutions, and
the real note gate then decides what still holds the declaration. The retained
result is what the CLI bridge reads back, so its outcome, effect and refusal
code are asserted here. All identifiers and figures are synthetic.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import cast
from uuid import UUID

import pytest
from pydantic import BaseModel

from ....adapters.persistence.profile.tests.secure_objects_fixture import secure_objects
from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ....application.modelo.calculation_note_gate import (
    SOURCE_DISAGREEMENT_FINDING_ID_LENGTH,
    blocking_calculation_issues,
)
from ....application.modelo.credit_resolution import credit_resolutions_for_work
from ....application.modelo.credit_resolution_contracts import (
    MODELO_CREDIT_RESOLUTION_ACCEPT_OPERATION_DEFINITION_ID,
    MODELO_CREDIT_RESOLUTION_LIST_OPERATION_DEFINITION_ID,
    MODELO_CREDIT_RESOLUTION_REFUSAL_CODE,
    MODELO_CREDIT_RESOLUTION_REVISION_REFUSAL_CODE,
    MODELO_CREDIT_RESOLUTION_REVOKE_OPERATION_DEFINITION_ID,
    CreditResolutionAcceptRequest,
    CreditResolutionExecutionResult,
    CreditResolutionListRequest,
    CreditResolutionRevokeRequest,
)
from ....application.modelo.credit_resolution_operation import CreditResolutionExecutor
from ....application.operations.execution_actor import (
    OperationExecutionCaller,
    OperationExecutionCallerReader,
    actor_label_is_automation,
)
from ....application.operations.models import OperationIdentity, OperationRequest
from ....application.operations.owner import OperationExecutorContext
from ....application.operations.refusal_evidence import OperationRefusalEvidence
from ....application.operations.registry import OperationFrontendProjection
from ....application.tests.operation_host_fakes import RecordingEvents
from ....application.user_profile.access_contracts import SessionKind
from ....core.casilla_id import CasillaId
from ....core.operations import OperationEffect
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.modelos.calculation_revision import CalculationRevision
from ....domain.modelos.credit_resolution import CreditResolutionState
from ....entrypoints.adapter_composition_work_ports import build_verification_repository_bundle
from .credit_resolution_live_support import (
    BUCKET_ID,
    CAPITAL_BINDING,
    CAPITAL_CASILLA,
    TRABAJO_BINDING,
    TRABAJO_CASILLA,
    CreditLiveHarness,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

__all__ = ["secure_objects"]

_REASON = "Synthetic reason: the payer's own copy of the certificate states this amount."
_CLIENT = UUID(int=7)
_PERSON_LABEL = f"cli.human.{_CLIENT}"
_AUTOMATION_LABEL = f"automation:external-client.api_key.{_CLIENT}"
_BORRADOR = {TRABAJO_BINDING: Decimal("1800.00"), CAPITAL_BINDING: Decimal("499.99")}


@pytest.fixture
def bucket_id() -> str:
    return BUCKET_ID


@pytest.fixture
def harness(secure_objects: SecureObjectRepository, operation: PinnedAuthorityOperation) -> CreditLiveHarness:
    return CreditLiveHarness.seed(secure_objects, operation=operation)


class _Cancellation:
    def __init__(self) -> None:
        self.inside = False

    @asynccontextmanager
    async def irreversible_section(self):
        self.inside = True
        try:
            yield
        finally:
            self.inside = False


class _Operands:
    def __init__(self, cancellation: _Cancellation, *, writes: bool) -> None:
        self._cancellation = cancellation
        self._writes = writes
        self.value: BaseModel | None = None

    async def put(self, value: BaseModel, *, written_at: object) -> str:
        del written_at
        # A write retains its result inside the irreversible section; a read holds none.
        assert self._cancellation.inside or not self._writes
        self.value = value
        return "d" * 64


class _Context:
    def __init__(self, authority_operation: PinnedAuthorityOperation, definition_id: str, subject_ref: str) -> None:
        self.identity = OperationIdentity(operation_id="c" * 64, definition_id=definition_id, subject_ref=subject_ref)
        self.authority_operation = authority_operation
        self.events = RecordingEvents()
        self.cancellation = _Cancellation()
        self.operands = _Operands(
            self.cancellation, writes=definition_id != MODELO_CREDIT_RESOLUTION_LIST_OPERATION_DEFINITION_ID
        )


def _caller(frontend: OperationFrontendProjection, kind: SessionKind) -> OperationExecutionCallerReader:
    def read(identity: OperationIdentity) -> OperationExecutionCaller:
        del identity
        return OperationExecutionCaller(frontend=frontend, session_kind=kind, client_id=_CLIENT)

    return read


def _run(
    harness: CreditLiveHarness,
    definition_id: str,
    payload: BaseModel,
    *,
    frontend: OperationFrontendProjection = OperationFrontendProjection.CLI,
    kind: SessionKind = SessionKind.HUMAN,
) -> tuple[str | OperationRefusalEvidence, CreditResolutionExecutionResult, list[OperationEffect]]:
    subject_ref = harness.work_unit.work_unit_id
    context = _Context(harness.operation, definition_id, subject_ref)
    request = OperationRequest(definition_id=definition_id, subject_ref=subject_ref, payload=payload)
    executor = CreditResolutionExecutor(
        build_verification_repository_bundle,
        definition_id=definition_id,
        execution_caller_reader=_caller(frontend, kind),
    )
    outcome = asyncio.run(executor.execute(request, cast(OperationExecutorContext, context)))
    retained = context.operands.value
    assert isinstance(retained, CreditResolutionExecutionResult)
    return outcome, retained, context.events.effects


def _accept(
    harness: CreditLiveHarness,
    revision: CalculationRevision,
    finding_id: str,
    reason: str = _REASON,
    frontend: OperationFrontendProjection = OperationFrontendProjection.CLI,
    kind: SessionKind = SessionKind.HUMAN,
):
    return _run(
        harness,
        MODELO_CREDIT_RESOLUTION_ACCEPT_OPERATION_DEFINITION_ID,
        CreditResolutionAcceptRequest(
            profile_id=UUID(BUCKET_ID),
            calculation_revision_id=revision.calculation_revision_id,
            finding_id=finding_id,
            reason=reason,
        ),
        frontend=frontend,
        kind=kind,
    )


def _revoke(harness: CreditLiveHarness, revision: CalculationRevision, finding_id: str, expected_revision_id: str):
    return _run(
        harness,
        MODELO_CREDIT_RESOLUTION_REVOKE_OPERATION_DEFINITION_ID,
        CreditResolutionRevokeRequest(
            profile_id=UUID(BUCKET_ID),
            calculation_revision_id=revision.calculation_revision_id,
            finding_id=finding_id,
            expected_revision_id=expected_revision_id,
        ),
    )


def _list(harness: CreditLiveHarness, revision: CalculationRevision):
    return _run(
        harness,
        MODELO_CREDIT_RESOLUTION_LIST_OPERATION_DEFINITION_ID,
        CreditResolutionListRequest(
            profile_id=UUID(BUCKET_ID), calculation_revision_id=revision.calculation_revision_id
        ),
    )


def _finding_id(revision: CalculationRevision, casilla: CasillaId) -> str:
    (issue,) = [
        item
        for item in revision.source_issues
        if item.reason == "credit_source_disagreement" and item.casilla_id == casilla
    ]
    assert issue.disagreement is not None
    return issue.disagreement.finding_key[:SOURCE_DISAGREEMENT_FINDING_ID_LENGTH]


def _held(harness: CreditLiveHarness, revision: CalculationRevision) -> set[CasillaId]:
    resolutions = credit_resolutions_for_work(harness.resolutions, harness.current_work_unit())
    return {
        issue.casilla_id
        for issue in blocking_calculation_issues(revision, resolutions)
        if issue.reason == "credit_source_disagreement" and issue.casilla_id is not None
    }


def test_accepting_a_finding_by_its_id_stores_the_resolution_and_lifts_exactly_that_hold(
    harness: CreditLiveHarness,
) -> None:
    revision = harness.calculate(_BORRADOR).revision
    assert _held(harness, revision) == {TRABAJO_CASILLA, CAPITAL_CASILLA}

    outcome, result, effects = _accept(harness, revision, _finding_id(revision, TRABAJO_CASILLA))

    assert outcome == "d" * 64
    assert effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]
    assert result.outcome == "success" and result.operation_id == "accept"
    row = result.resolution
    assert row is not None
    assert row.finding_id == _finding_id(revision, TRABAJO_CASILLA)
    assert row.key == str(TRABAJO_CASILLA)
    assert row.state is CreditResolutionState.ACTIVE and row.applies
    assert row.reason == _REASON and row.resolved_by_session == _PERSON_LABEL
    amounts = {source.role.value: source.value for source in row.sources}
    assert amounts == {"value_source": "1950.00", "cross_check": "1800.00"}
    assert _held(harness, revision) == {CAPITAL_CASILLA}


def test_an_id_that_names_no_finding_of_the_current_calculation_is_refused_and_leaves_no_effect(
    harness: CreditLiveHarness,
) -> None:
    revision = harness.calculate(_BORRADOR).revision

    outcome, result, effects = _accept(harness, revision, "0" * SOURCE_DISAGREEMENT_FINDING_ID_LENGTH)

    assert isinstance(outcome, OperationRefusalEvidence)
    assert outcome.refusal_code == MODELO_CREDIT_RESOLUTION_REFUSAL_CODE
    assert effects == [OperationEffect.UNKNOWN, OperationEffect.NONE]
    assert result.outcome == "refused" and result.refusal is not None
    assert (result.refusal.reason, result.refusal.finding_id) == ("unknown_finding", "0" * 16)
    assert _held(harness, revision) == {TRABAJO_CASILLA, CAPITAL_CASILLA}
    assert harness.resolutions.load_for_work(modelo="100", filing_year=harness.work_unit.filing_year, period="0A") == ()


def test_a_calculation_that_is_no_longer_current_cannot_be_answered(harness: CreditLiveHarness) -> None:
    first = harness.calculate(_BORRADOR).revision
    first_id = _finding_id(first, TRABAJO_CASILLA)
    harness.calculate(_BORRADOR)
    if harness.current_work_unit().current_calculation_revision_id == first.calculation_revision_id:
        pytest.fail("the second calculation must replace the first as the declaration's current one")

    outcome, result, effects = _accept(harness, first, first_id)

    assert isinstance(outcome, OperationRefusalEvidence)
    assert effects == [OperationEffect.UNKNOWN, OperationEffect.NONE]
    assert result.refusal is not None and result.refusal.reason == "calculation_not_current"
    assert _held(harness, first) == {TRABAJO_CASILLA, CAPITAL_CASILLA}
    assert harness.resolutions.load_for_work(modelo="100", filing_year=harness.work_unit.filing_year, period="0A") == ()


def test_a_finding_already_accepted_is_refused_and_a_changed_amount_is_a_new_finding(
    harness: CreditLiveHarness,
) -> None:
    revision = harness.calculate(_BORRADOR).revision
    finding_id = _finding_id(revision, TRABAJO_CASILLA)
    _accept(harness, revision, finding_id)

    outcome, result, effects = _accept(harness, revision, finding_id)

    assert isinstance(outcome, OperationRefusalEvidence)
    assert effects == [OperationEffect.UNKNOWN, OperationEffect.NONE]
    assert result.refusal is not None and result.refusal.reason == "already_resolved"

    corrected = harness.calculate({**_BORRADOR, TRABAJO_BINDING: Decimal("1801.00")}).revision
    new_id = _finding_id(corrected, TRABAJO_CASILLA)
    assert new_id != finding_id
    outcome, result, _effects = _accept(harness, corrected, new_id)
    assert outcome == "d" * 64 and result.resolution is not None


def test_revoking_needs_the_stored_revision_and_blocks_the_figure_again(harness: CreditLiveHarness) -> None:
    revision = harness.calculate(_BORRADOR).revision
    finding_id = _finding_id(revision, TRABAJO_CASILLA)
    _, accepted, _ = _accept(harness, revision, finding_id)
    assert accepted.resolution is not None
    stored_revision = accepted.resolution.revision_id

    outcome, result, effects = _revoke(harness, revision, finding_id, "e" * 64)

    assert isinstance(outcome, OperationRefusalEvidence)
    assert outcome.refusal_code == MODELO_CREDIT_RESOLUTION_REVISION_REFUSAL_CODE
    assert effects == [OperationEffect.UNKNOWN, OperationEffect.NONE]
    assert result.refusal is not None and result.refusal.reason == "stale_revision"
    assert TRABAJO_CASILLA not in _held(harness, revision)

    outcome, result, effects = _revoke(harness, revision, finding_id, stored_revision)

    assert outcome == "d" * 64
    assert effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]
    assert result.resolution is not None and result.resolution.state is CreditResolutionState.REVOKED
    assert result.resolution.revoked_by_session == _PERSON_LABEL and result.resolution.revision_id != stored_revision
    assert TRABAJO_CASILLA in _held(harness, revision)

    outcome, result, effects = _revoke(harness, revision, finding_id, result.resolution.revision_id)
    assert isinstance(outcome, OperationRefusalEvidence)
    assert result.refusal is not None and result.refusal.reason == "not_resolved"
    assert effects == [OperationEffect.UNKNOWN, OperationEffect.NONE]


def test_revoking_an_id_nothing_was_stored_under_is_refused(harness: CreditLiveHarness) -> None:
    revision = harness.calculate(_BORRADOR).revision

    outcome, result, effects = _revoke(harness, revision, "0" * SOURCE_DISAGREEMENT_FINDING_ID_LENGTH, "e" * 64)

    assert isinstance(outcome, OperationRefusalEvidence)
    assert effects == [OperationEffect.UNKNOWN, OperationEffect.NONE]
    assert result.refusal is not None and result.refusal.reason == "unknown_finding"


def test_listing_shows_every_resolution_of_the_declaration_and_whether_the_calculation_still_has_it(
    harness: CreditLiveHarness,
) -> None:
    first = harness.calculate(_BORRADOR).revision
    _accept(harness, first, _finding_id(first, TRABAJO_CASILLA))
    _accept(harness, first, _finding_id(first, CAPITAL_CASILLA))
    corrected = harness.calculate({**_BORRADOR, TRABAJO_BINDING: Decimal("1801.00")}).revision

    outcome, result, effects = _list(harness, corrected)

    assert outcome == "d" * 64
    assert effects == [OperationEffect.NONE]
    assert result.operation_id == "list" and result.resolutions is not None
    applies = {row.key: row.applies for row in result.resolutions}
    # The capital figure kept its amounts, so its acceptance still covers a finding of the current calculation.
    assert applies == {str(TRABAJO_CASILLA): False, str(CAPITAL_CASILLA): True}
    assert {row.state for row in result.resolutions} == {CreditResolutionState.ACTIVE}
    assert all(row.reason == _REASON for row in result.resolutions)


def test_an_acceptance_is_recorded_under_the_admitting_sessions_label_and_an_automations_is_marked_as_such(
    harness: CreditLiveHarness,
) -> None:
    revision = harness.calculate(_BORRADOR).revision

    _, person, _ = _accept(harness, revision, _finding_id(revision, TRABAJO_CASILLA))
    _, automation, _ = _accept(
        harness,
        revision,
        _finding_id(revision, CAPITAL_CASILLA),
        frontend=OperationFrontendProjection.EXTERNAL_CLIENT,
        kind=SessionKind.API_KEY,
    )

    assert person.resolution is not None and automation.resolution is not None
    assert person.resolution.resolved_by_session == _PERSON_LABEL
    assert not actor_label_is_automation(person.resolution.resolved_by_session)
    assert automation.resolution.resolved_by_session == _AUTOMATION_LABEL
    assert actor_label_is_automation(automation.resolution.resolved_by_session)
