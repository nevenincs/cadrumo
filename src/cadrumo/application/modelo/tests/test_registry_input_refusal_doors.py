"""Every refusal where a Modelo input meets the selected registry serves the door of its cause.

The verdicts are read the way the runtime reads them, through
``nested_terminal_precondition_verdict``, from refusals raised by the real
validators against the published registry.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.casilla_id import validated_casilla_id
from ....core.operator_action_enums import ActionArgumentStatus, ActionConditionality, NoRecoveryOutcome
from ....core.period import Period
from ....domain.calculations.registry.errors import RegistryFailureCondition, RegistryValidationError
from ....domain.calculations.registry.tests.authored_editions import authored_revisions_where, newest_authored_edition
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....domain.modelos.m232_row_materialisation import m232_related_party_row_casilla_values
from ....domain.modelos.perceptor_clave_scope import ClaveScopeToken
from ....domain.modelos.row_models import Modelo232VinculadaRow
from ...cli_exception_preconditions import nested_terminal_precondition_verdict
from ...operator_actions.models import PreconditionVerdict
from ..action_errors import AmendmentOverrideCasillaError
from ..calculate_input_validation import ModeloCalculateTextInputError, text_value
from ..registry_helpers import reject_unknown_override_casillas, validate_casilla_input_ids
from ..registry_input_refusals import RegistryInputCondition, registry_integrity_verdict

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_M180_YEAR = newest_authored_edition("180")
_M180_PERIOD = Period.from_year_and_code(_M180_YEAR, "0A")
_BOOLEAN_FLAG = validated_casilla_id("0100", surface="_BOOLEAN_FLAG")


def _verdict(error: BaseException) -> PreconditionVerdict:
    verdict = nested_terminal_precondition_verdict(error)
    assert verdict is not None
    return verdict


def _bindings(verdict: PreconditionVerdict) -> dict[str, object]:
    return {
        binding.argument_name: binding.value if binding.status is ActionArgumentStatus.RESOLVED else None
        for binding in verdict.argument_bindings
    }


def test_an_undeclared_override_casilla_opens_the_listing_of_its_declaration() -> None:
    """Operator input: the amendment knows its declaration, so the listing is addressed and immediate."""
    with pytest.raises(AmendmentOverrideCasillaError) as refusal:
        reject_unknown_override_casillas(
            modelo="180",
            filing_year=_M180_YEAR,
            period=_M180_PERIOD,
            overrides={"no-such-casilla": Decimal("1")},
        )

    verdict = _verdict(refusal.value)
    assert verdict.failed_condition_id == RegistryInputCondition.CASILLA_DECLARED.value
    assert verdict.action is not None
    assert verdict.action.action_id == "operator.modelo.casillas"
    assert _bindings(verdict) == {"modelo": "180", "year": _M180_YEAR, "period": "0A"}
    assert verdict.conditionality is ActionConditionality.IMMEDIATE


def test_a_declared_override_casilla_passes_without_a_refusal() -> None:
    """Detector teeth: the refusal keys on undeclared ids, not on every override."""
    accepted = reject_unknown_override_casillas(
        modelo="180",
        filing_year=_M180_YEAR,
        period=_M180_PERIOD,
        overrides={"decl.total-perceptores": Decimal("1")},
    )

    assert set(accepted) == {"decl.total-perceptores"}


def test_a_boolean_casilla_value_outside_its_domain_opens_the_value_edit_of_that_casilla() -> None:
    """Operator input: the value edit binds the refused casilla and leaves the value and unit to the operator."""
    year = authored_revisions_where(
        "100",
        lambda revision: any(
            casilla.id == _BOOLEAN_FLAG and casilla.data_type == "boolean" for casilla in revision.casillas
        ),
    )[-1].valid_from.year
    revision = published_snapshot("100", filing_year=year, period="0A").revision

    with pytest.raises(RegistryValidationError) as refusal:
        validate_casilla_input_ids(revision, {_BOOLEAN_FLAG: Decimal(2)})

    verdict = _verdict(refusal.value)
    assert verdict.failed_condition_id == RegistryInputCondition.CASILLA_VALUE_ADMITTED.value
    assert verdict.action is not None
    assert verdict.action.action_id == "operator.modelo.work.set_value"
    assert _bindings(verdict) == {"casilla_id": _BOOLEAN_FLAG, "value": None, "work_unit_id": None}
    assert set(verdict.missing_argument_names) == {"value", "work_unit_id"}
    assert validate_casilla_input_ids(revision, {_BOOLEAN_FLAG: Decimal(1)}) == {_BOOLEAN_FLAG: Decimal(1)}


def test_an_empty_text_casilla_value_opens_the_value_edit() -> None:
    """Operator input on the text channel reaches the same door as the numeric one."""
    with pytest.raises(ModeloCalculateTextInputError) as refusal:
        text_value("   ", key="0001")

    verdict = _verdict(refusal.value)
    assert verdict.action is not None
    assert verdict.action.action_id == "operator.modelo.work.set_value"
    assert _bindings(verdict)["casilla_id"] == "0001"


def test_an_unresolvable_declaration_is_terminal_because_no_action_publishes_authority() -> None:
    """Authority: a modelo the registry does not resolve leaves the amendment nothing to check against."""
    with pytest.raises(AmendmentOverrideCasillaError) as refusal:
        reject_unknown_override_casillas(
            modelo="999",
            filing_year=_M180_YEAR,
            period=_M180_PERIOD,
            overrides={"decl.total-perceptores": Decimal("1")},
        )

    verdict = _verdict(refusal.value)
    assert refusal.value.translated_message == "application.modelo.errors.amendment_registry_snapshot_unresolved"
    assert verdict.failed_condition_id == RegistryInputCondition.AUTHORITY_AVAILABLE.value
    assert verdict.action is None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.TERMINAL


def test_a_broken_registry_declaration_is_terminal_and_reads_the_same_from_domain_and_application() -> None:
    """Registry integrity: the domain factory and the application builder serve one verdict."""
    with pytest.raises(RegistryValidationError) as refusal:
        ClaveScopeToken.parse("")

    verdict = _verdict(refusal.value)
    assert verdict.failed_condition_id == RegistryFailureCondition.DECLARATION_CONSISTENT.value
    assert verdict.action is None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.TERMINAL
    assert verdict == registry_integrity_verdict("perceptor_clave_scope")


def test_related_party_rows_beyond_the_declared_capacity_are_the_operators_decision() -> None:
    """Rows the operator supplied past the form's slots name no action: which rows to keep is theirs."""
    rows = tuple(
        Modelo232VinculadaRow(
            pais="ES", nif="12345678Z", tipo_vinculacion="A", tipo_operacion="01", importe=Decimal(index)
        )
        for index in range(64)
    )

    with pytest.raises(RegistryValidationError) as refusal:
        m232_related_party_row_casilla_values(rows)

    verdict = _verdict(refusal.value)
    assert verdict.failed_condition_id == RegistryFailureCondition.ROWS_WITHIN_DECLARED_CAPACITY.value
    assert verdict.action is None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION
