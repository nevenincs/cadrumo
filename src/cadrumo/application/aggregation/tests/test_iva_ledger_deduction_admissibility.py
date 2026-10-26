"""An inadmissible input-IVA deduction classification is reported, not raised.

The deduction pairing table in the IVA deduction applicability catalogue is the
authority on which ``IvaDeductionFactKind`` a row may carry. Until the gate these
tests cover existed, that table was consulted only inside
:class:`~cadrumo.domain.calculations.registry.ledger_iva_bindings.IvaLedgerObservation`'s
own model validator -- after every typed aggregation gate had passed -- so an
operator declaring a deduction their row cannot bear failed the whole Modelo
303/390 calculation with an internal payload-boundary defect naming a model class
instead of the ledger row and field to correct.

Every case here drives the real ledger aggregation against the published
authority. The observation model keeps its refusal: the last test constructs one
directly with the same facts and asserts it still refuses, so the gate cannot
pass by having relaxed the contract it front-runs.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation

from ....core.iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from ....core.period import Period
from ....domain.bienes_inversion.register import BienesInversionIvaRegister
from ....domain.calculations.registry.ledger_iva_bindings import IvaLedgerObservation
from ....domain.iva.deduction_facts import IvaDeductionClassificationProvenance
from ....domain.iva.flow import received_flow_direction
from ....domain.iva.schema import (
    IvaCashAccountingPaymentEvidence,
    IvaCategory,
    IvaExemptionArticle,
    IvaLedgerObservationRole,
    IvaRateKind,
)
from ....domain.transactions.enums import TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ..iva_ledger import (
    IvaLedgerAggregation,
    IvaLedgerAggregationIssueReason,
    aggregate_iva_ledger_observations,
)
from .ledger_transaction_support import iva_transaction

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PERIOD = Period.from_year_and_code(2026, "1T")
_PROFILE_ID = "deduction-admissibility"
_OPERATION_DATE = date(2026, 2, 10)
_PAYMENT_DATE = date(2026, 3, 5)
_DOMESTIC_GENERAL = IvaCategory("domestic_general")


def _aggregate(
    *transactions: Transaction,
    operation: PinnedAuthorityOperation,
) -> IvaLedgerAggregation:
    return aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions(transactions),
        period=_PERIOD,
        ledger_profile_id=_PROFILE_ID,
        investment_asset_register=BienesInversionIvaRegister(),
        investment_asset_profile_id=_PROFILE_ID,
        operation=operation,
    )


def _purchase(
    provider_id: str,
    *,
    taxable_base: Decimal = Decimal("100.00"),
    iva_amount: Decimal = Decimal("21.00"),
    iva_category: IvaCategory = _DOMESTIC_GENERAL,
    counterparty_country: str | None = None,
    **updates: object,
) -> Transaction:
    """An invoice-backed domestic purchase, optionally altered per case.

    The gross is reconstituted from base plus cuota rather than passed: the
    catalogue refuses a row whose movement and declared substrate disagree, and
    a case that varies the substrate has to keep that identity.
    """
    purchase = iva_transaction(
        provider_id,
        direction=TransactionDirection.OUTGOING,
        amount=taxable_base + iva_amount,
        taxable_base=taxable_base,
        iva_amount=iva_amount,
        booked_date=_OPERATION_DATE,
        iva_category=iva_category,
        counterparty_country=counterparty_country,
    )
    return Transaction.model_validate(purchase.model_dump() | updates) if updates else purchase


def _exempt_purchase(provider_id: str) -> Transaction:
    """A zero-cuota exempt acquisition still declaring an ordinary domestic deduction."""
    return _purchase(
        provider_id,
        iva_amount=Decimal("0.00"),
        iva_category=IvaCategory("domestic_exempt"),
        exemption_article=IvaExemptionArticle("art_20_other"),
        iva_rate=Decimal("0"),
    )


def _invoice_provenance(provider_id: str) -> IvaDeductionClassificationProvenance:
    return IvaDeductionClassificationProvenance(
        authority=IvaDeductionEvidenceAuthority.from_registry("invoice_evidence"),
        source_locator=f"invoice:{provider_id}",
        evidence_digest="a" * 64,
    )


def test_an_admissible_domestic_purchase_still_aggregates(*, operation: PinnedAuthorityOperation) -> None:
    """The positive path: the gate admits the pairing the catalogue declares."""
    result = _aggregate(_purchase("admissible-purchase"), operation=operation)

    assert result.issues == ()
    assert len(result.observations) == 1
    observation = result.observations[0]
    assert observation.deduction_fact_kind == IvaDeductionFactKind.from_registry("domestic_current")
    assert observation.iva_amount == Decimal("21.00")


def test_an_exempt_purchase_declared_as_an_ordinary_deduction_is_refused(
    *, operation: PinnedAuthorityOperation
) -> None:
    """An exempt acquisition grants no input deduction, so the declared kind has no authority."""
    result = _aggregate(_exempt_purchase("exempt-purchase"), operation=operation)

    assert result.observations == ()
    assert [issue.reason for issue in result.issues] == [
        IvaLedgerAggregationIssueReason.INADMISSIBLE_DEDUCTION_CLASSIFICATION,
    ]
    assert "domestic_current" in result.issues[0].detail
    assert "domestic_exempt" in result.issues[0].detail


def test_an_investment_deduction_without_its_asset_identity_is_refused(*, operation: PinnedAuthorityOperation) -> None:
    """An investment kind names a reciprocal register asset; without one it is unresolvable."""
    result = _aggregate(
        _purchase(
            "investment-purchase",
            taxable_base=Decimal("3600.00"),
            iva_amount=Decimal("756.00"),
            deduction_fact_kind="domestic_investment",
            investment_asset_id=None,
        ),
        operation=operation,
    )

    assert result.observations == ()
    assert [issue.reason for issue in result.issues] == [
        IvaLedgerAggregationIssueReason.INADMISSIBLE_DEDUCTION_CLASSIFICATION,
    ]
    assert "investment_asset_id" in result.issues[0].detail


def test_deduction_authority_on_an_output_row_is_refused(*, operation: PinnedAuthorityOperation) -> None:
    """A sale repercutes its cuota, so no evidence authority can establish a deduction on it."""
    sale = iva_transaction(
        "sale-with-deduction",
        direction=TransactionDirection.INCOMING,
        amount=Decimal("242.00"),
        taxable_base=Decimal("200.00"),
        iva_amount=Decimal("42.00"),
        booked_date=_OPERATION_DATE,
        iva_category=IvaCategory("domestic_general"),
    )
    sale = Transaction.model_validate(
        sale.model_dump()
        | {
            "deduction_fact_kind": "domestic_current",
            "deduction_provenance": _invoice_provenance("sale-with-deduction").model_dump(),
        },
    )

    result = _aggregate(sale, operation=operation)

    assert result.observations == ()
    assert [issue.reason for issue in result.issues] == [
        IvaLedgerAggregationIssueReason.INADMISSIBLE_DEDUCTION_CLASSIFICATION,
    ]


def test_a_kind_whose_required_evidence_authority_is_not_the_attached_one_is_refused(
    *, operation: PinnedAuthorityOperation
) -> None:
    """An intra-EU deduction is established by the self-assessment, not by a supplier invoice."""
    result = _aggregate(
        _purchase("intra-eu-on-invoice-evidence", deduction_fact_kind="intra_eu_current"),
        operation=operation,
    )

    assert result.observations == ()
    assert [issue.reason for issue in result.issues] == [
        IvaLedgerAggregationIssueReason.INADMISSIBLE_DEDUCTION_CLASSIFICATION,
    ]
    assert "intra_eu_self_assessment" in result.issues[0].detail


def _under_criterio_de_caja(transaction: Transaction) -> Transaction:
    """Re-declare a row as fully paid inside the period under criterio de caja."""
    taxable_base = transaction.taxable_base
    iva_amount = transaction.iva_amount
    assert taxable_base is not None
    assert iva_amount is not None
    return Transaction.model_validate(
        transaction.model_dump()
        | {
            "operation_date": _OPERATION_DATE,
            "cash_accounting_treatment": "taxpayer_regime",
            "cash_accounting_payment_evidence": (
                IvaCashAccountingPaymentEvidence(
                    payment_date=_PAYMENT_DATE,
                    taxable_base=taxable_base,
                    iva_amount=iva_amount,
                ).model_dump(),
            ),
        },
    )


def test_the_cash_accounting_projection_admits_the_same_pairing(*, operation: PinnedAuthorityOperation) -> None:
    """A criterio-de-caja row emits its settlement and informational observations unchanged."""
    result = _aggregate(_under_criterio_de_caja(_purchase("cash-admissible")), operation=operation)

    assert result.issues == ()
    assert {observation.observation_role for observation in result.observations} == {
        IvaLedgerObservationRole.SETTLEMENT,
        IvaLedgerObservationRole.OPERATION_INFORMATIONAL,
    }


def test_the_cash_accounting_projection_refuses_the_inadmissible_pairing(
    *, operation: PinnedAuthorityOperation
) -> None:
    """Both projection paths are gated: the criterio-de-caja split is not a way round it.

    The second producer of observations. Gated separately because each settlement
    part carries a payment's share of the base and cuota rather than the
    operation's, and the deduction contract reads those amounts.
    """
    result = _aggregate(
        _under_criterio_de_caja(_exempt_purchase("cash-exempt")),
        operation=operation,
    )

    assert result.observations == ()
    assert [issue.reason for issue in result.issues] == [
        IvaLedgerAggregationIssueReason.INADMISSIBLE_DEDUCTION_CLASSIFICATION,
    ]


def test_an_absent_classification_stays_its_own_distinct_reason(*, operation: PinnedAuthorityOperation) -> None:
    """Absent and inadmissible are different remedies: one is supplied, the other corrected."""
    result = _aggregate(
        _purchase("unclassified-purchase", deduction_fact_kind=None, deduction_provenance=None),
        operation=operation,
    )

    assert result.observations == ()
    assert [issue.reason for issue in result.issues] == [
        IvaLedgerAggregationIssueReason.MISSING_DEDUCTION_CLASSIFICATION,
    ]


def test_the_observation_contract_the_gate_front_runs_still_refuses(*, operation: PinnedAuthorityOperation) -> None:
    """Detector teeth: the gate is not passing because the underlying contract relaxed.

    Builds the observation the exempt case would have built. It must still raise:
    if this stopped refusing, every assertion above would pass while the
    inadmissible deduction reached a filed return.
    """
    with pytest.raises(ValidationError):
        IvaLedgerObservation(
            ledger_id="exempt-purchase",
            transaction_date=_OPERATION_DATE,
            category=IvaCategory("domestic_exempt"),
            exemption_article=IvaExemptionArticle("art_20_other"),
            rate_kind=IvaRateKind("exempt"),
            applied_rate=Decimal("0"),
            flow_direction=received_flow_direction(),
            base_amount=Decimal("100.00"),
            iva_amount=Decimal("0.00"),
            observation_role=IvaLedgerObservationRole.SETTLEMENT,
            deduction_fact_kind=IvaDeductionFactKind.from_registry("domestic_current"),
            deduction_provenance=_invoice_provenance("exempt-purchase"),
        )
