"""The door a Modelo 303 IVA-wallet refusal names: the wallet's opening balance.

A refusal that cannot settle the period's carry because no opening balance is
recorded used to name no door, so the filer had to find the IVA balance and its
opening-balance entry alone. The refusal now carries the step that opens that
entry for the same modelo, filing year and period. It stays a refusal: nothing
is written, and the refusal keeps its own verdict and message.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.external_constants import OutputLanguage
from ....core.period import Period
from ....domain.calculations.registry.form_codes import form_for_role
from ....domain.calculations.registry.ids import BindingId
from ....domain.calculations.registry.tests.published_authority import (
    published_snapshot,
    published_supported_filing_years,
)
from ...operations.error_detail import build_operation_error_detail
from ...operations.next_step import OperationOpenIvaWalletOpeningBalanceStepV1, error_next_step
from ..iva_wallet_gate import ModeloIvaWalletReconciliationBlocked, apply_iva_compensation_decision_binding

pytestmark = [pytest.mark.usefixtures("authority_operation"), pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "34343434-3434-4343-8343-343434343434"
_TAXPAYER_REF = "taxpayeralpha"
_PERIOD_CODE = "2T"
_M303_PRIOR_COMPENSATION_CASILLA: CasillaId = validated_casilla_id(
    "iva.compensacion-pendiente-periodos-anteriores",
    surface="_M303_PRIOR_COMPENSATION_CASILLA",
)


def _supported_filing_years() -> tuple[int, ...]:
    """Every filing year the registry envelope admits, enumerated from the registry."""
    support = published_supported_filing_years()
    assert support is not None, "the published registry declares a supported-filing-year envelope"
    years = tuple(support.years)
    assert years, "the supported-filing-year envelope spans at least one year"
    return years


def _refuse_unseeded_carry(filing_year: int) -> ModeloIvaWalletReconciliationBlocked:
    """Ask Modelo 303 to carry a prior compensation with no recorded wallet authority."""
    period = Period.from_year_and_code(filing_year, _PERIOD_CODE)
    backend: dict[BindingId, Decimal] = {}
    with pytest.raises(ModeloIvaWalletReconciliationBlocked) as raised:
        apply_iva_compensation_decision_binding(
            form_for_role("iva.periodic"),
            filing_year,
            period,
            bucket_id=_BUCKET_ID,
            revision=published_snapshot(
                form_for_role("iva.periodic"),
                filing_year=filing_year,
                period=_PERIOD_CODE,
            ).revision,
            taxpayer_nif=_TAXPAYER_REF,
            casilla_inputs={_M303_PRIOR_COMPENSATION_CASILLA: Decimal("800")},
            backend_casilla_inputs={},
            caller_binding_values={},
            backend_binding_values=backend,
            decision=None,
        )
    assert backend == {}, "a refused carry writes no binding value"
    return raised.value


def test_unseeded_carry_refusal_names_the_opening_balance_in_every_supported_year() -> None:
    """Each supported filing year's refusal names that year's own opening-balance entry."""
    for filing_year in _supported_filing_years():
        error = _refuse_unseeded_carry(filing_year)
        step = error.operation_next_step(OutputLanguage.ES)
        assert isinstance(step, OperationOpenIvaWalletOpeningBalanceStepV1), (
            f"the {filing_year} refusal names the wallet's opening balance"
        )
        assert step.modelo == form_for_role("iva.periodic")
        assert step.filing_year == filing_year
        assert step.period_code == _PERIOD_CODE
        assert step.words.strip() != ""


def test_unseeded_carry_refusal_keeps_its_own_verdict_and_message() -> None:
    """The step is served beside the refusal, not instead of it."""
    error = _refuse_unseeded_carry(_supported_filing_years()[-1])

    assert error.translated_message == "application.modelo.errors.iva_wallet_not_seeded"
    assert error.precondition_failure.scenario_id == "modelo.work.calculate.iva_wallet.not_seeded"


def test_opening_balance_step_is_worded_in_the_refusals_own_language() -> None:
    """The words follow the language the refusal's sentence is in."""
    error = _refuse_unseeded_carry(_supported_filing_years()[-1])

    spanish = error.operation_next_step(OutputLanguage.ES)
    english = error.operation_next_step(OutputLanguage.EN)
    assert spanish is not None
    assert english is not None
    assert spanish.words != english.words


def test_refusal_detail_carries_the_opening_balance_step() -> None:
    """The one canonical detail builder serves the step to a frontend."""
    error = _refuse_unseeded_carry(_supported_filing_years()[-1])
    detail = build_operation_error_detail(error)

    assert detail is not None
    assert isinstance(detail.next_step, OperationOpenIvaWalletOpeningBalanceStepV1)
    assert detail.next_step.period_code == _PERIOD_CODE


def test_a_refusal_the_opening_balance_would_not_settle_names_no_door() -> None:
    """A wallet decision of an unsupported type is not put right by declaring a balance."""
    filing_year = _supported_filing_years()[-1]
    with pytest.raises(ModeloIvaWalletReconciliationBlocked) as raised:
        apply_iva_compensation_decision_binding(
            form_for_role("iva.periodic"),
            filing_year,
            Period.from_year_and_code(filing_year, _PERIOD_CODE),
            bucket_id=_BUCKET_ID,
            revision=published_snapshot(
                form_for_role("iva.periodic"),
                filing_year=filing_year,
                period=_PERIOD_CODE,
            ).revision,
            taxpayer_nif=_TAXPAYER_REF,
            casilla_inputs={},
            backend_casilla_inputs={},
            caller_binding_values={},
            backend_binding_values={},
            decision=object(),
        )

    assert raised.value.translated_message == "application.modelo.errors.iva_wallet_unsupported_decision_type"
    assert error_next_step(raised.value, OutputLanguage.ES) is None
