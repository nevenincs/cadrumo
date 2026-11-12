"""The export refusals that name a box, a settlement, a name or an amended filing give the door their cause leaves.

Each refusal is raised by the real function that owns it and read through the
error the operation would report: its served words in every language and its
door, which is a catalogued action with the arguments the boundary knows bound,
an operator decision where no action repairs the cause, or the terminal
integrity refusal where only a caller or design fault reaches it.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal

import pytest

from ....core.errors.error_codes import ErrorCategory, get_registered_error_code, resolve_error_message
from ....core.external_constants import OutputLanguage
from ....core.operator_action_enums import NoRecoveryOutcome
from ....core.payment_instalment_election import PaymentInstalmentElection
from ....core.result_disposition import ResultDisposition
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.deadlines.models import TaxpayerProfile
from ....domain.justificante.schema import Justificante
from ....domain.modelos.calculation_revision_amendment import CalculationRevisionAmendmentIdentity
from ....domain.modelos.filing_record import (
    AeatConfirmationState,
    ExternalEvidence,
    ExternalEvidenceKind,
    ModeloRecord,
    ModeloRecordCatalogue,
)
from ....domain.modelos.work_unit import WorkUnit
from ...cli_exception_preconditions import nested_terminal_precondition_verdict
from ...filing.errors import ModeloApplicationError
from ...filing.producer_snapshot import TaxpayerIdentityFacts
from ...filing.tests.export_support import approved_registry_draft
from ...operations.next_step import OperationOpenProfileFieldStepV1, error_next_step
from ..action_errors import ModeloProfileReadinessError
from ..export import export_write_failure
from ..export_amendment_evidence import _receipt, _target
from ..export_contracts import (
    ModeloExportCasillaValueRefusedError,
    ModeloExportCommand,
    ModeloExportDesignIntegrityError,
    ModeloExportEvidenceMissingError,
    ModeloExportSettlementRefusedError,
)
from ..export_preparation import compose_export_dictionary_values
from ..export_settlement import DeclaredSettlement, SettlementRefusal, settlement_dictionary_values

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LOCALES = ("es", "ca", "en", "hu")
_SET_VALUE_ACTION = "operator.modelo.work.set_value"
_CALCULATE_ACTION = "operator.modelo.work.calculate"
_IMPORT_ACTION = "operator.modelo.filing_record.import"


def _command() -> ModeloExportCommand:
    return ModeloExportCommand.model_construct(calculation_revision_id="revision-1")


def _assert_served(error: BaseException) -> None:
    for locale in _LOCALES:
        message = resolve_error_message(error, locale=locale)
        assert message
        assert "%{" not in message
        assert "application.modelo.errors" not in message


def _schema_refusal(**context: object) -> ModeloApplicationError:
    return ModeloApplicationError(
        translated_message="application.filing.export.errors.xml_value_too_long",
        context={"limit": "5", "observed": 9, **context},
    )


def test_a_schema_refusal_of_a_stated_box_opens_set_value_with_the_box_bound() -> None:
    failure = export_write_failure(_command(), _schema_refusal(box="box-a", field_id="FIELD_A_ID"))

    assert isinstance(failure, ModeloExportCasillaValueRefusedError)
    verdict = nested_terminal_precondition_verdict(failure)
    assert verdict is not None
    assert verdict.action is not None
    assert verdict.action.action_id == _SET_VALUE_ACTION
    assert {
        binding.argument_name: binding.value for binding in verdict.argument_bindings if binding.value is not None
    } == {"casilla_id": "box-a"}
    assert set(verdict.missing_argument_names) == {"work_unit_id", "value"}
    assert failure.translated_message == "application.filing.export.errors.xml_value_too_long"
    assert "box-a" in resolve_error_message(failure, locale="en")


def test_a_schema_refusal_of_a_field_that_is_no_box_is_the_operators_decision() -> None:
    failure = export_write_failure(_command(), _schema_refusal(box="FIELD_A_ID", field_id="FIELD_A_ID"))

    verdict = nested_terminal_precondition_verdict(failure)
    assert verdict is not None
    assert verdict.action is None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION


def test_a_shared_cell_refusal_is_the_operators_decision_and_keeps_its_words() -> None:
    refusal = ModeloApplicationError(
        translated_message="application.filing.export.errors.shared_casilla_cells_unadjudicated",
        context={"casilla_ids": "box-a, box-b"},
    )

    failure = export_write_failure(_command(), refusal)

    assert isinstance(failure, ModeloExportCasillaValueRefusedError)
    verdict = nested_terminal_precondition_verdict(failure)
    assert verdict is not None
    assert verdict.action is None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION
    assert "box-a, box-b" in resolve_error_message(failure, locale="en")


def _settle(refusal: SettlementRefusal) -> ModeloExportSettlementRefusedError:
    with pytest.raises(ModeloExportSettlementRefusedError) as refused:
        settlement_dictionary_values(
            disposition=ResultDisposition.INGRESO,
            settlement=DeclaredSettlement(amount=None, refusal=refusal),
            instalment=PaymentInstalmentElection.SINGLE,
            first_instalment_share=None,
            charge_account=None,
            refund_account=None,
        )
    return refused.value


def test_a_result_that_is_not_calculated_opens_calculate_leaving_the_work_unit_to_the_operator() -> None:
    refused = _settle(SettlementRefusal.RESULT_UNKNOWN)

    assert get_registered_error_code(refused).code == "REFUSED_MODELO_EXPORT_SETTLEMENT"
    verdict = nested_terminal_precondition_verdict(refused)
    assert verdict is not None
    assert verdict.action is not None
    assert verdict.action.action_id == _CALCULATE_ACTION
    assert set(verdict.missing_argument_names) == {"work_unit_id"}
    _assert_served(refused)


def test_a_settlement_the_export_does_not_compose_is_the_operators_decision() -> None:
    refused = _settle(SettlementRefusal.SETTLEMENT_UNSUPPORTED)

    verdict = nested_terminal_precondition_verdict(refused)
    assert verdict is not None
    assert verdict.action is None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION
    _assert_served(refused)


@pytest.mark.parametrize("disposition", [ResultDisposition.COMPENSACION, ResultDisposition.CUENTA_CORRIENTE_INGRESO])
def test_a_disposition_the_export_never_composes_refuses_as_a_terminal_integrity_defect(
    disposition: ResultDisposition,
) -> None:
    with pytest.raises(ModeloExportDesignIntegrityError) as refused:
        settlement_dictionary_values(
            disposition=disposition,
            settlement=DeclaredSettlement(amount=Decimal(1), refusal=None),
            instalment=PaymentInstalmentElection.SINGLE,
            first_instalment_share=None,
            charge_account=None,
            refund_account=None,
        )

    assert get_registered_error_code(refused.value).category is ErrorCategory.INTEGRITY
    verdict = nested_terminal_precondition_verdict(refused.value)
    assert verdict is not None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.TERMINAL
    _assert_served(refused.value)


def test_a_pay_disposition_without_an_amount_refuses_as_a_terminal_integrity_defect() -> None:
    with pytest.raises(ModeloExportDesignIntegrityError):
        settlement_dictionary_values(
            disposition=ResultDisposition.INGRESO,
            settlement=DeclaredSettlement(amount=Decimal(0), refusal=None),
            instalment=PaymentInstalmentElection.SINGLE,
            first_instalment_share=None,
            charge_account=None,
            refund_account=None,
        )


def test_a_profile_without_a_name_to_state_opens_the_profile_edit_that_names_it(
    operation: PinnedAuthorityOperation,
) -> None:
    nameless = TaxpayerIdentityFacts(legal_name=None, given_name=None, surnames=None, full_name=None)

    with pytest.raises(ModeloProfileReadinessError) as refused:
        compose_export_dictionary_values(
            draft=approved_registry_draft(),
            taxpayer_identity=nameless,
            bucket_id="bucket-1",
            operation=operation,
        )

    verdict = nested_terminal_precondition_verdict(refused.value)
    assert verdict is not None
    assert verdict.action is not None
    assert verdict.action.action_id == "operator.profile.edit"
    step = error_next_step(refused.value, OutputLanguage.EN)
    assert isinstance(step, OperationOpenProfileFieldStepV1)
    assert step.path == "identity.surnames"
    for locale in _LOCALES:
        message = resolve_error_message(refused.value, locale=locale)
        assert "identity.surnames" in message
        assert "%{" not in message


class _NoJustificantes:
    def load(self, csv: str, /) -> Justificante | None:
        return None

    def save(self, justificante: Justificante, /) -> None:
        raise AssertionError("the refusal reads the repository only")

    def iter_justificantes(self) -> Iterator[Justificante]:
        return iter(())


def _work_unit() -> WorkUnit:
    return WorkUnit.model_construct(work_unit_id="work-unit-1", bucket_id="bucket-1")


def _identity() -> CalculationRevisionAmendmentIdentity:
    return CalculationRevisionAmendmentIdentity.model_construct(amends_filing_record_id="record-1")


def _record(*, evidence: ExternalEvidence | None = None) -> ModeloRecord:
    return ModeloRecord.model_construct(
        filing_record_id="record-1",
        work_unit_id="work-unit-1",
        confirmation=AeatConfirmationState.PENDIENTE if evidence is None else AeatConfirmationState.CONFIRMADA,
        external_evidence=evidence,
    )


def test_an_amended_filing_without_aeat_evidence_opens_the_evidence_import_for_its_work_unit() -> None:
    catalogue = ModeloRecordCatalogue.model_construct(records={"record-1": _record()})

    with pytest.raises(ModeloExportEvidenceMissingError) as refused:
        _target(_command(), identity=_identity(), work_unit=_work_unit(), records=catalogue)

    verdict = nested_terminal_precondition_verdict(refused.value)
    assert verdict is not None
    assert verdict.action is not None
    assert verdict.action.action_id == _IMPORT_ACTION
    assert {
        binding.argument_name: binding.value for binding in verdict.argument_bindings if binding.value is not None
    } == {"work_unit_id": "work-unit-1"}
    assert set(verdict.missing_argument_names) == {"evidence_kind", "evidence_reference_id"}
    _assert_served(refused.value)


def test_an_amended_filing_the_catalogue_does_not_hold_refuses_as_a_terminal_integrity_defect() -> None:
    catalogue = ModeloRecordCatalogue.model_construct(records={})

    with pytest.raises(ModeloExportDesignIntegrityError) as refused:
        _target(_command(), identity=_identity(), work_unit=_work_unit(), records=catalogue)

    verdict = nested_terminal_precondition_verdict(refused.value)
    assert verdict is not None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.TERMINAL
    assert refused.value.context is not None
    assert refused.value.context["calculation_revision_id"] == "revision-1"


def test_a_justificante_missing_from_the_record_is_the_operators_decision() -> None:
    with pytest.raises(ModeloExportEvidenceMissingError) as refused:
        _receipt(
            _command(),
            target=_record(
                evidence=ExternalEvidence.model_construct(
                    kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF, reference_id="csv-1"
                )
            ),
            work_unit=_work_unit(),
            workflow_profile=TaxpayerProfile.model_construct(tax_id="tax-id"),
            repository=_NoJustificantes(),
        )

    verdict = nested_terminal_precondition_verdict(refused.value)
    assert verdict is not None
    assert verdict.action is None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION
    _assert_served(refused.value)
