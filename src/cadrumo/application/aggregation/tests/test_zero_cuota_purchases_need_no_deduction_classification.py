"""A purchase that bore no IVA is declarable without an input-IVA deduction.

Two real autónomo inputs could not be recorded at all. A monthly RETA quota is a
Social Security contribution, outside the IVA taxable event (LIVA art. 7) and
deductible for IRPF; an insurance premium is exempt under LIVA art. 20.Uno.16.
Both are RECEIVED rows, so both settled as ``soportado``, and the aggregation
demanded an exact deduction classification of every ``soportado`` row. LIVA
art. 92.Uno grants a deduction only of a cuota devengada and borne by
repercusión, and neither row bore one, so the deduction applicability catalogue
admits no kind for their categories: without a kind the row was withheld as
unclassified, and with any kind it was refused as inadmissible.

The requirement now follows that catalogue. What must NOT change is the two
refusals either side of it: an ordinary taxable purchase still needs its
classification, and a row that bore no cuota still cannot claim one.
"""

from __future__ import annotations

from collections.abc import Callable
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

type _ZeroCuotaRowFactory = Callable[..., Transaction]
"""One of the two cuota-less rows, built by a case that varies its fields."""

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PERIOD = Period.from_year_and_code(2026, "1T")
_PROFILE_ID = "zero-cuota-inputs"
_OPERATION_DATE = date(2026, 2, 10)

#: LIVA art. 7 places a Social Security contribution outside the taxable event.
_RETA_QUOTA = Decimal("314.40")
#: LIVA art. 20.Uno.16 exempts the premium on an insurance operation.
_PREMIUM = Decimal("240.00")


def _aggregate(*transactions: Transaction, operation: PinnedAuthorityOperation) -> IvaLedgerAggregation:
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
    amount: Decimal,
    iva_category: str,
    category_id: str,
    iva_rate: Decimal,
    iva_amount: Decimal,
    **updates: object,
) -> Transaction:
    """One received business row, with its declared substrate reconstituting the gross.

    ``iva_transaction`` stamps an invoice-backed ``domestic_current`` deduction on
    every outgoing row, which is exactly what these rows must not carry, so the
    two deduction fields are cleared unless a case restores them.
    """
    purchase = iva_transaction(
        provider_id,
        direction=TransactionDirection.OUTGOING,
        amount=amount,
        taxable_base=amount - iva_amount,
        iva_amount=iva_amount,
        booked_date=_OPERATION_DATE,
        iva_category=IvaCategory(iva_category),
    )
    return Transaction.model_validate(
        purchase.model_dump()
        | {
            "category_id": category_id,
            "iva_rate": iva_rate,
            "deduction_fact_kind": None,
            "deduction_provenance": None,
        }
        | updates,
    )


def _reta_quota(provider_id: str = "reta-quota", **updates: object) -> Transaction:
    return _purchase(
        provider_id,
        amount=_RETA_QUOTA,
        iva_category="operacion_no_sujeta",
        category_id="cuotas_autonomos_ss",
        iva_rate=Decimal("0"),
        iva_amount=Decimal("0"),
        **updates,
    )


def _exempt_premium(provider_id: str = "insurance-premium", **updates: object) -> Transaction:
    return _purchase(
        provider_id,
        amount=_PREMIUM,
        iva_category="domestic_exempt",
        category_id="seguros_responsabilidad_civil",
        iva_rate=Decimal("0"),
        iva_amount=Decimal("0"),
        exemption_article=IvaExemptionArticle("art_20_other"),
        **updates,
    )


def _invoice_provenance(provider_id: str) -> IvaDeductionClassificationProvenance:
    return IvaDeductionClassificationProvenance(
        authority=IvaDeductionEvidenceAuthority.from_registry("invoice_evidence"),
        source_locator=f"invoice:{provider_id}",
        evidence_digest="a" * 64,
    )


def _ordinary_deduction(provider_id: str) -> dict[str, object]:
    return {
        "deduction_fact_kind": IvaDeductionFactKind.from_registry("domestic_current"),
        "deduction_provenance": _invoice_provenance(provider_id).model_dump(),
    }


def test_an_out_of_scope_reta_quota_reaches_an_observation(*, operation: PinnedAuthorityOperation) -> None:
    """The RETA quota that blocked every quarter now declares its base and no cuota."""
    result = _aggregate(_reta_quota(), operation=operation)

    assert result.issues == ()
    assert len(result.observations) == 1
    observation = result.observations[0]
    assert observation.category == IvaCategory("operacion_no_sujeta")
    assert observation.flow_direction == received_flow_direction()
    assert observation.base_amount == _RETA_QUOTA
    assert observation.iva_amount == Decimal("0")
    assert observation.deduction_fact_kind is None
    assert observation.deduction_provenance is None


def test_an_exempt_insurance_premium_reaches_an_observation(*, operation: PinnedAuthorityOperation) -> None:
    """LIVA art. 20.Uno.16: the premium bore no cuota, so it needs no deduction to declare."""
    result = _aggregate(_exempt_premium(), operation=operation)

    assert result.issues == ()
    assert len(result.observations) == 1
    observation = result.observations[0]
    assert observation.category == IvaCategory("domestic_exempt")
    assert observation.base_amount == _PREMIUM
    assert observation.iva_amount == Decimal("0")
    assert observation.deduction_fact_kind is None


def test_both_rows_declare_no_deducible_cuota_between_them(*, operation: PinnedAuthorityOperation) -> None:
    """The quarter's two zero-cuota inputs contribute base only, never a deduction."""
    result = _aggregate(_reta_quota(), _exempt_premium(), operation=operation)

    assert result.issues == ()
    assert sum(observation.base_amount for observation in result.observations) == _RETA_QUOTA + _PREMIUM
    assert sum(observation.iva_amount for observation in result.observations) == Decimal("0")


@pytest.mark.parametrize(
    ("label", "row_factory"),
    [
        ("reta-quota", _reta_quota),
        ("insurance-premium", _exempt_premium),
    ],
)
def test_a_zero_cuota_row_still_cannot_claim_a_deduction(
    label: str,
    row_factory: _ZeroCuotaRowFactory,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """The refusal half: relaxing the requirement must not admit the claim."""
    result = _aggregate(row_factory(label, **_ordinary_deduction(label)), operation=operation)

    assert result.observations == ()
    assert [issue.reason for issue in result.issues] == [
        IvaLedgerAggregationIssueReason.INADMISSIBLE_DEDUCTION_CLASSIFICATION,
    ]
    assert "domestic_current" in result.issues[0].detail


@pytest.mark.parametrize(
    ("label", "row_factory"),
    [
        ("reta-quota", _reta_quota),
        ("insurance-premium", _exempt_premium),
    ],
)
def test_evidence_without_a_kind_is_refused_rather_than_reaching_the_payload(
    label: str,
    row_factory: _ZeroCuotaRowFactory,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """Half-declared authority on a cuota-less row has nothing to complete.

    Reported here rather than left to the observation's own validator: there it
    arrives as a payload-boundary defect naming a model class, with no ledger row
    and no field for the operator to correct.
    """
    result = _aggregate(
        row_factory(label, deduction_provenance=_invoice_provenance(label).model_dump()),
        operation=operation,
    )

    assert result.observations == ()
    assert [issue.reason for issue in result.issues] == [
        IvaLedgerAggregationIssueReason.INADMISSIBLE_DEDUCTION_CLASSIFICATION,
    ]


def test_an_ordinary_taxable_purchase_still_needs_its_classification(
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """The exclusion case: a cuota WAS repercutida here, so art. 92 requires the kind."""
    result = _aggregate(
        _purchase(
            "taxable-purchase",
            amount=Decimal("121.00"),
            iva_category="domestic_general",
            category_id="material_oficina",
            iva_rate=Decimal("0.21"),
            iva_amount=Decimal("21.00"),
        ),
        operation=operation,
    )

    assert result.observations == ()
    assert [issue.reason for issue in result.issues] == [
        IvaLedgerAggregationIssueReason.MISSING_DEDUCTION_CLASSIFICATION,
    ]


def test_a_zero_rated_purchase_still_needs_its_classification(*, operation: PinnedAuthorityOperation) -> None:
    """A 0 % tipo is not an exemption: the operation is sujeta y no exenta.

    ``domestic_zero`` is a taxable domestic acquisition whose cuota happens to be
    zero, and the deduction catalogue keeps it in the domestic family. A screen
    keyed on "this row's cuota is zero" instead of on the catalogue would have
    dropped its deduction identity along with the two rows above.
    """
    result = _aggregate(
        _purchase(
            "zero-rated-purchase",
            amount=Decimal("100.00"),
            iva_category="domestic_zero",
            category_id="material_oficina",
            iva_rate=Decimal("0"),
            iva_amount=Decimal("0"),
        ),
        operation=operation,
    )

    assert result.observations == ()
    assert [issue.reason for issue in result.issues] == [
        IvaLedgerAggregationIssueReason.MISSING_DEDUCTION_CLASSIFICATION,
    ]


def test_the_observation_contract_admits_the_unclassified_cuota_less_row(
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """Teeth on the payload boundary, both directions at once.

    The aggregation gate front-runs the observation's own validator, so a gate
    that admitted these rows while the validator still refused them would fail
    the calculation from inside the payload boundary. Constructing the same two
    observations by hand asserts the contract moved with the gate -- and the
    second half asserts it did not move too far.
    """
    del operation
    unclassified = IvaLedgerObservation(
        ledger_id="insurance-premium",
        transaction_date=_OPERATION_DATE,
        category=IvaCategory("domestic_exempt"),
        exemption_article=IvaExemptionArticle("art_20_other"),
        rate_kind=IvaRateKind("zero"),
        applied_rate=Decimal("0"),
        flow_direction=received_flow_direction(),
        base_amount=_PREMIUM,
        iva_amount=Decimal("0"),
        observation_role=IvaLedgerObservationRole.SETTLEMENT,
    )

    assert unclassified.deduction_fact_kind is None

    with pytest.raises(ValidationError):
        IvaLedgerObservation(
            ledger_id="insurance-premium",
            transaction_date=_OPERATION_DATE,
            category=IvaCategory("domestic_exempt"),
            exemption_article=IvaExemptionArticle("art_20_other"),
            rate_kind=IvaRateKind("zero"),
            applied_rate=Decimal("0"),
            flow_direction=received_flow_direction(),
            base_amount=_PREMIUM,
            iva_amount=Decimal("0"),
            observation_role=IvaLedgerObservationRole.SETTLEMENT,
            deduction_fact_kind=IvaDeductionFactKind.from_registry("domestic_current"),
            deduction_provenance=_invoice_provenance("insurance-premium"),
        )


@pytest.mark.parametrize(("modelo", "period"), [("303", "1T"), ("390", "0A")])
def test_neither_row_reaches_a_declared_box_on_either_form(
    modelo: str,
    period: str,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """Measured scope of what the fix does and does not reach.

    Both rows now project an observation, and on neither Modelo 303 nor Modelo 390
    does any ``ledger_iva_aggregation`` binding draw their base. For Modelo 303
    that is the form: it declares no box for an exempt or non-subject acquisition,
    so the base belongs on the IRPF expense side alone and the aggregation's
    unrouted-quantity advisory carries it. For Modelo 390 box [230]
    ("Adquisiciones interiores exentas") the box exists and no binding fills it,
    which is a distinct open gap this asserts rather than hides -- an advisory the
    operator sees, never a silent zero.
    """
    from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot

    from ..iva_ledger import resolve_iva_ledger_binding_values

    revision = published_snapshot(modelo, filing_year=2025, period=period).revision
    observations = _aggregate(
        _reta_quota(),
        _exempt_premium(),
        operation=operation,
    ).observations

    assert len(observations) == 2
    drawn = {
        binding_id: value
        for binding_id, value in resolve_iva_ledger_binding_values(
            revision,
            observations,
            operation=operation,
        ).items()
        if value != Decimal("0")
    }

    assert drawn == {}, f"a zero-cuota acquisition reached a declared box on modelo {modelo}: {drawn}"
