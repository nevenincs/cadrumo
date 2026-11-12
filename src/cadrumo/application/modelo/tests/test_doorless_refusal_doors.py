"""Refusals that once reached the operator with words and no next step open a door of their cause.

Each refusal is raised by the owning code from a real trigger and read the way the
operation error detail reads it, through ``nested_terminal_precondition_verdict``.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from decimal import Decimal
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
from pydantic import ValidationError

from ....core.authority_grade import RegistryAuthorityGrade
from ....core.operations import profile_operation_subject
from ....core.operator_action_enums import ActionArgumentStatus, NoRecoveryOutcome
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.casilla_membership import (
    casilla_noncanonical_reference_tokens,
    declared_casilla_ids,
)
from ....domain.calculations.registry.schema import ModeloRevision
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....domain.modelos.calculation_revision import (
    LedgerFilingCoverageError,
    assert_revision_snapshot_evidence_coverage,
)
from ....domain.modelos.codes import ModeloCode, coerce_modelo_code
from ....domain.modelos.errors import ModeloValidationError
from ....domain.modelos.row_models import (
    Modelo184MemberRow,
    Modelo184ShareSumError,
    Modelo349CountryPrefixContextError,
    validate_m184_member_share_sum,
    validate_m349_country_prefix_context,
)
from ....domain.modelos.tests.test_snapshot_evidence_coverage_validator import _TX_A, _TX_B, _revision
from ....domain.modelos.work_unit import WorkUnitCatalogue
from ...cli_exception_preconditions import nested_terminal_precondition_verdict
from ...operations.models import OperationIdentity, OperationRequest
from ...operations.owner import OperationExecutorContext
from ...operator_actions.models import PreconditionVerdict
from ...tests.operation_host_fakes import IrreversibleSectionGrant, RecordingEvents
from ..invoice_withholding_capture_public import PublicAnnualRecipientDetail
from ..lifecycle_view_refusal_doors import work_address_absent_verdict
from ..reconciliation_evidence_kind import ModeloReconciliationEvidenceKind
from ..reconciliation_import_operation import (
    MODELO_RECONCILIATION_IMPORT_OPERATION_DEFINITION_ID,
    ModeloReconciliationImportExecutor,
    ModeloReconciliationImportRequest,
)
from ..result_disposition_resolution import _reject_non_revision_casilla_values
from ..work_address_errors import ModeloWorkAddressNotFoundError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("41414141-4141-4141-8141-414141414141")
_YEAR = filing_year_envelope().horizon


@pytest.fixture(autouse=True)
def _pinned_authority() -> Iterator[None]:
    """Hold the authority the runtime holds, so code that reads a form fact has it."""
    with bundled_indexed_authority().operation():
        yield


def _verdict(error: BaseException) -> PreconditionVerdict:
    verdict = nested_terminal_precondition_verdict(error)
    assert verdict is not None
    return verdict


def _bound(verdict: PreconditionVerdict) -> dict[str, object]:
    return {
        binding.argument_name: binding.value if binding.status is ActionArgumentStatus.RESOLVED else None
        for binding in verdict.argument_bindings
    }


def _assert_outcome(error: BaseException, outcome: NoRecoveryOutcome) -> PreconditionVerdict:
    verdict = _verdict(error)
    assert verdict.action is None
    assert verdict.no_recovery_outcome is outcome
    return verdict


def test_an_order_number_above_the_form_ceiling_is_the_operators_decision() -> None:
    with pytest.raises(ValidationError) as refused:
        PublicAnnualRecipientDetail.model_validate({"numero_orden": 10**9})

    verdict = _assert_outcome(refused.value, NoRecoveryOutcome.OPERATOR_DECISION)
    assert verdict.evidence[0].values["reason"] == "withholding_order_number_above_form_ceiling"


class _Operands:
    async def put(self, value: object, *, written_at: object) -> str:
        del value, written_at
        return "operand"


def _import_request(**selector: object) -> OperationRequest[ModeloReconciliationImportRequest]:
    return OperationRequest[ModeloReconciliationImportRequest](
        definition_id=MODELO_RECONCILIATION_IMPORT_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=ModeloReconciliationImportRequest.model_validate(
            {
                "profile_id": _PROFILE,
                "source_kind": next(iter(ModeloReconciliationEvidenceKind)),
                "source_path": "evidence.pdf",
                **selector,
            }
        ),
    )


def _import_context(authority_operation: object) -> OperationExecutorContext:
    return cast(
        OperationExecutorContext,
        SimpleNamespace(
            identity=OperationIdentity(
                operation_id="d" * 64,
                definition_id=MODELO_RECONCILIATION_IMPORT_OPERATION_DEFINITION_ID,
                subject_ref=profile_operation_subject(str(_PROFILE)),
            ),
            authority_operation=authority_operation,
            cancellation=IrreversibleSectionGrant(),
            events=RecordingEvents(),
            operands=_Operands(),
        ),
    )


def _refused_import(monkeypatch: pytest.MonkeyPatch, **selector: object) -> ModeloWorkAddressNotFoundError:
    """Run the real executor against a profile whose work catalogue is empty."""
    for target in (
        "cadrumo.application.modelo.reconciliation_import_operation.require_active_bucket_id",
        "cadrumo.application.operations.profile_guard.require_active_bucket_id",
    ):
        monkeypatch.setattr(target, lambda: str(_PROFILE))
    monkeypatch.setattr(
        "cadrumo.application.modelo.reconciliation_import_operation.work_unit_catalogue_repository",
        lambda **_kw: SimpleNamespace(load=WorkUnitCatalogue),
    )
    with bundled_indexed_authority().operation() as operation, pytest.raises(ModeloWorkAddressNotFoundError) as refused:
        asyncio.run(
            ModeloReconciliationImportExecutor().execute(_import_request(**selector), _import_context(operation))
        )
    return refused.value


def test_an_import_for_a_declaration_with_no_work_unit_opens_its_creation(monkeypatch: pytest.MonkeyPatch) -> None:
    refused = _refused_import(monkeypatch, modelo="130", filing_year=_YEAR, period="1T")

    verdict = _verdict(refused)
    assert verdict.action is not None
    assert verdict.action.action_id == "operator.modelo.work.create"
    assert _bound(verdict)["modelo"] == "130"


def test_an_absent_work_unit_id_opens_the_work_list() -> None:
    verdict = work_address_absent_verdict(modelo="130", filing_year=_YEAR, unit_id_stated=True)

    assert verdict.action is not None
    assert verdict.action.action_id == "operator.modelo.work.list"


def _revision_of_the_modelo() -> ModeloRevision:
    return published_snapshot("303", filing_year=_YEAR, period="1T", grade=RegistryAuthorityGrade.CALCULATION).revision


def test_a_stored_casilla_the_revision_does_not_declare_is_terminal() -> None:
    revision = _revision_of_the_modelo()
    declared = declared_casilla_ids(revision)
    undeclared = "99999"
    assert undeclared not in declared

    with pytest.raises(ModeloValidationError) as refused:
        _reject_non_revision_casilla_values(
            modelo="303",
            revision_id=revision.id,
            casilla_values={undeclared: Decimal(1)},
            declared_ids=declared,
            registry_revision=revision,
        )

    _assert_outcome(refused.value, NoRecoveryOutcome.TERMINAL)
    assert refused.value.context is not None
    assert refused.value.context["casilla_ids"] == repr(undeclared)


def test_a_stored_casilla_printed_number_that_is_not_its_id_is_terminal() -> None:
    revision = _revision_of_the_modelo()
    declared = declared_casilla_ids(revision)
    printed = next(token for token in casilla_noncanonical_reference_tokens(revision) if token not in declared)

    with pytest.raises(ModeloValidationError) as refused:
        _reject_non_revision_casilla_values(
            modelo="303",
            revision_id=revision.id,
            casilla_values={printed: Decimal(1)},
            declared_ids=declared,
            registry_revision=revision,
        )

    _assert_outcome(refused.value, NoRecoveryOutcome.TERMINAL)
    assert refused.value.context is not None
    assert "casilla_refs" in refused.value.context


def test_a_ledger_evidence_that_dropped_a_contributor_is_terminal() -> None:
    revision = _revision(snapshot_ids=(_TX_A, _TX_B), evidence_ids=(_TX_A,))

    with pytest.raises(LedgerFilingCoverageError) as refused:
        assert_revision_snapshot_evidence_coverage(revision)

    verdict = _assert_outcome(refused.value, NoRecoveryOutcome.TERMINAL)
    assert verdict.evidence[0].values["record"] == "ledger_filing_evidence"


@pytest.mark.parametrize("value", ["12", "1234", "abc", " 12"])
def test_a_modelo_code_of_the_wrong_shape_is_terminal(value: str) -> None:
    with pytest.raises(ModeloValidationError) as refused:
        ModeloCode(value)

    verdict = _assert_outcome(refused.value, NoRecoveryOutcome.TERMINAL)
    assert verdict.evidence[0].values["record"] == "modelo_code"


def test_a_modelo_code_coerced_from_another_type_is_terminal() -> None:
    with pytest.raises(ModeloValidationError) as refused:
        coerce_modelo_code(303)

    _assert_outcome(refused.value, NoRecoveryOutcome.TERMINAL)


def test_member_shares_that_do_not_total_one_hundred_are_the_operators_decision() -> None:
    rows = [
        Modelo184MemberRow(nif="33333333C", porcentaje=Decimal("60"), importe=Decimal("0"), clave="D"),
        Modelo184MemberRow(nif="44444444A", porcentaje=Decimal("30"), importe=Decimal("0"), clave="D"),
    ]

    with pytest.raises(Modelo184ShareSumError) as refused:
        validate_m184_member_share_sum(rows)

    _assert_outcome(refused.value, NoRecoveryOutcome.OPERATOR_DECISION)


def test_a_prefix_the_operation_key_does_not_admit_is_the_operators_decision() -> None:
    with pytest.raises(Modelo349CountryPrefixContextError) as refused:
        validate_m349_country_prefix_context(country_code="XI", clave_operacion="S", filing_year=_YEAR, period="4T")

    verdict = _assert_outcome(refused.value, NoRecoveryOutcome.OPERATOR_DECISION)
    assert verdict.evidence[0].values["record"] == "m349_country_prefix"
