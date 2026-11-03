"""Registry-build refusals for a revision's credit reconciliation.

The clean fixture is the published Modelo 100 revision itself, which must pass
every check. Each defective fixture copies it with exactly one defect, so a check
that stopped looking would let the defect through and fail here.
"""

from __future__ import annotations

import pytest

from .....core.casilla_id import validated_casilla_id
from .....core.retencion_soportada import RetencionSoportadaClase
from ..authority import PinnedAuthorityOperation
from ..credit_reconciliation import (
    BorradorCrossCheck,
    CreditReconciliationEntry,
    CreditReconciliationOperand,
    CreditReconciliationValueSource,
    FiledObservationCrossCheck,
    LedgerCrossCheck,
    RetencionSoportadaCrossCheck,
    WithholdingSide,
)
from ..credit_reconciliation_checks import (
    credit_reconciliation_digest,
    credit_reconciliation_revision_failures,
    filed_observation_source_failures,
    revision_declares_credit_reconciliation,
)
from ..errors import RegistryValidationError
from ..schema import ModeloRevision
from .authored_editions import newest_authored_edition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_TRABAJO = validated_casilla_id("0596")
_ARRENDAMIENTO = validated_casilla_id("0598")
_CUOTA_RESULTANTE = validated_casilla_id("0595")
_TRABAJO_BINDING = "renta-retencion-soportada-trabajo"
_CAPITAL_BINDING = "renta-retencion-soportada-capital-mobiliario"
_ARRENDAMIENTO_FORMULA = "renta-retenciones-arrendamientos-urbanos"


@pytest.fixture
def revision(operation: PinnedAuthorityOperation) -> ModeloRevision:
    return operation.snapshot("100", filing_year=newest_authored_edition("100"), period="0A").revision


def _with_entry(revision: ModeloRevision, entry: CreditReconciliationEntry) -> ModeloRevision:
    """Replace the entry for ``entry.casilla_id``, or add it, leaving every other entry as published."""
    kept = tuple(item for item in revision.credit_reconciliation if item.casilla_id != entry.casilla_id)
    return revision.model_copy(update={"credit_reconciliation": (*kept, entry)})


def _trabajo_entry(*cross_checks: object, value_binding: str = _TRABAJO_BINDING) -> CreditReconciliationEntry:
    return CreditReconciliationEntry.model_validate(
        {
            "casilla_id": _TRABAJO,
            "value_source": {"binding": value_binding},
            "cross_checks": cross_checks or ({"kind": "borrador", "binding": _TRABAJO_BINDING},),
        }
    )


def test_the_published_revision_declares_a_clean_credit_reconciliation(revision: ModeloRevision) -> None:
    assert revision_declares_credit_reconciliation(revision)
    assert {str(entry.casilla_id) for entry in revision.credit_reconciliation} == {
        "0596",
        "0597",
        "0598",
        "0599",
        "0603",
    }
    assert credit_reconciliation_revision_failures(revision) == ()


def test_a_casilla_outside_the_payments_on_account_total_is_refused(revision: ModeloRevision) -> None:
    entry = _trabajo_entry().model_copy(update={"casilla_id": _CUOTA_RESULTANTE})
    (failure,) = credit_reconciliation_revision_failures(_with_entry(revision, entry))
    assert "not an operand of the payments-on-account total" in failure


def test_a_value_source_other_than_the_casillas_own_binding_is_refused(revision: ModeloRevision) -> None:
    failures = credit_reconciliation_revision_failures(
        _with_entry(revision, _trabajo_entry(value_binding=_CAPITAL_BINDING))
    )
    assert any("is not the binding bound to the casilla" in failure for failure in failures)


def test_a_value_source_the_borrador_could_supply_is_refused(revision: ModeloRevision) -> None:
    bindings = tuple(
        binding.model_copy(update={"borrador_participation": None}) if binding.id == _TRABAJO_BINDING else binding
        for binding in revision.bindings
    )
    failures = credit_reconciliation_revision_failures(revision.model_copy(update={"bindings": bindings}))
    assert any("must be aeat_prefilled with borrador_participation = 'cross_check_only'" in f for f in failures)


def test_a_formula_value_source_that_does_not_compute_the_casilla_is_refused(revision: ModeloRevision) -> None:
    entry = CreditReconciliationEntry(
        casilla_id=_TRABAJO,
        value_source=CreditReconciliationValueSource(formula=_ARRENDAMIENTO_FORMULA),
        cross_checks=(BorradorCrossCheck(binding=_TRABAJO_BINDING),),
    )
    failures = credit_reconciliation_revision_failures(_with_entry(revision, entry))
    assert any("is not the formula computing the casilla" in failure for failure in failures)


def test_payer_records_of_a_class_that_does_not_credit_the_casilla_are_refused(revision: ModeloRevision) -> None:
    entry = _trabajo_entry(RetencionSoportadaCrossCheck(income_class=RetencionSoportadaClase.CAPITAL_MOBILIARIO))
    (failure,) = credit_reconciliation_revision_failures(_with_entry(revision, entry))
    assert "income class 'capital_mobiliario' does not credit a casilla" in failure


def test_a_borrador_cross_check_on_a_binding_no_snapshot_can_hold_is_refused(revision: ModeloRevision) -> None:
    entry = _trabajo_entry(BorradorCrossCheck(binding="renta-profile-tax-id"))
    (failure,) = credit_reconciliation_revision_failures(_with_entry(revision, entry))
    assert "is not aeat_prefilled" in failure


def test_a_ledger_cross_check_on_a_binding_that_is_not_a_ledger_binding_is_refused(
    revision: ModeloRevision,
) -> None:
    entry = _trabajo_entry(LedgerCrossCheck(binding=_CAPITAL_BINDING))
    (failure,) = credit_reconciliation_revision_failures(_with_entry(revision, entry))
    assert "is not a ledger binding" in failure


def test_an_operand_the_value_formula_does_not_read_is_refused(revision: ModeloRevision) -> None:
    entry = CreditReconciliationEntry(
        casilla_id=_ARRENDAMIENTO,
        value_source=CreditReconciliationValueSource(formula=_ARRENDAMIENTO_FORMULA),
        cross_checks=(
            RetencionSoportadaCrossCheck(
                income_class=RetencionSoportadaClase.ARRENDAMIENTO_INMUEBLE_URBANO,
                operand=CreditReconciliationOperand(casilla_id=validated_casilla_id("0154")),
            ),
        ),
    )
    (failure,) = credit_reconciliation_revision_failures(_with_entry(revision, entry))
    assert "operand casilla '0154' is not an operand of formula" in failure


def test_an_operand_beside_a_binding_value_source_is_refused(revision: ModeloRevision) -> None:
    entry = _trabajo_entry(
        BorradorCrossCheck(binding=_TRABAJO_BINDING, operand=CreditReconciliationOperand(casilla_id=_TRABAJO))
    )
    (failure,) = credit_reconciliation_revision_failures(_with_entry(revision, entry))
    assert "an operand is named, but the value source is not a formula" in failure


def test_a_casilla_declared_twice_is_refused(revision: ModeloRevision) -> None:
    entry = _trabajo_entry()
    duplicated = revision.model_copy(update={"credit_reconciliation": (*revision.credit_reconciliation, entry)})
    failures = credit_reconciliation_revision_failures(duplicated)
    assert "credit reconciliation declares casilla '0596' twice" in failures


def test_the_same_cross_check_declared_twice_is_refused_at_load() -> None:
    with pytest.raises((RegistryValidationError, ValueError)):
        _trabajo_entry(
            {"kind": "borrador", "binding": _TRABAJO_BINDING},
            {"kind": "borrador", "binding": _TRABAJO_BINDING},
        )


def test_a_value_source_naming_both_a_binding_and_a_formula_is_refused_at_load() -> None:
    with pytest.raises((RegistryValidationError, ValueError)):
        CreditReconciliationValueSource.model_validate({"binding": _TRABAJO_BINDING, "formula": _ARRENDAMIENTO_FORMULA})


def test_the_digest_moves_with_any_declaration_and_only_with_one(revision: ModeloRevision) -> None:
    digest = credit_reconciliation_digest(revision)
    assert credit_reconciliation_digest(revision.model_copy()) == digest
    changed = _with_entry(
        revision, _trabajo_entry(RetencionSoportadaCrossCheck(income_class=RetencionSoportadaClase.TRABAJO))
    )
    assert credit_reconciliation_digest(changed) != digest


_M130_RETENCIONES = validated_casilla_id("06")


@pytest.fixture
def m130_fourth_quarter(operation: PinnedAuthorityOperation) -> ModeloRevision:
    return operation.snapshot("130", filing_year=newest_authored_edition("100"), period="4T").revision


def _filed(casilla: str) -> FiledObservationCrossCheck:
    return FiledObservationCrossCheck.model_validate(
        {"kind": "filed_observation", "modelo": "130", "casilla": casilla, "period": "4T"}
    )


def test_a_filed_casilla_of_withholding_suffered_may_corroborate_a_credit(m130_fourth_quarter: ModeloRevision) -> None:
    assert filed_observation_source_failures(_filed("06"), (m130_fourth_quarter,), owner="0599") == ()


def test_a_filed_casilla_with_no_declared_withholding_side_is_refused(m130_fourth_quarter: ModeloRevision) -> None:
    (failure,) = filed_observation_source_failures(_filed("01"), (m130_fourth_quarter,), owner="0599")
    assert "withholding_side = suffered" in failure


def test_a_filed_casilla_of_withholding_practised_is_refused(m130_fourth_quarter: ModeloRevision) -> None:
    practised = m130_fourth_quarter.model_copy(
        update={
            "casillas": tuple(
                casilla.model_copy(update={"withholding_side": WithholdingSide.PRACTISED})
                if casilla.id == _M130_RETENCIONES
                else casilla
                for casilla in m130_fourth_quarter.casillas
            )
        }
    )
    (failure,) = filed_observation_source_failures(_filed("06"), (practised,), owner="0599")
    assert "withholding_side = suffered" in failure


def test_a_filed_casilla_no_revision_declares_is_refused(m130_fourth_quarter: ModeloRevision) -> None:
    (failure,) = filed_observation_source_failures(_filed("99"), (m130_fourth_quarter,), owner="0599")
    assert "is not declared" in failure


def test_the_published_0599_reconciliation_reads_the_fourth_quarter_retenciones(revision: ModeloRevision) -> None:
    (entry,) = [item for item in revision.credit_reconciliation if str(item.casilla_id) == "0599"]
    filed = [check for check in entry.cross_checks if isinstance(check, FiledObservationCrossCheck)]
    assert filed == [_filed("06")]
