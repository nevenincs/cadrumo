"""One ledger invoice, asserted across renta income, retenciones and IVA together.

Every domain that consumes a ledger invoice was already covered on its own, and
each was green. What nothing checked was whether the three AGREE about the same
invoice, so a decomposition satisfying each consumer's local expectation while
contradicting the others had no gate to trip.

These scenarios drive ONE transaction through all three projections and assert
the figures reconcile to a single decomposition. The invoice is an ordinary
Spanish professional service::

    base imponible      1000.00
    IVA repercutido      210.00   (21%, LIVA art. 90)
    retencion            150.00   (15%, RIRPF art. 95.1, withheld on the BASE)
    -------------------------------
    total                1210.00   = base + cuota
    cash received        1060.00   = total - retencion

Those figures come from the invoice arithmetic and the two cited rates, never
from what any aggregator currently returns. That direction matters: an expected
value read off the engine agrees with the engine by construction and proves
nothing. If a projection disagrees with the numbers below, the projection is
what is wrong.

The second scenario is the same invoice with its substrate unrecorded, which is
the common state of a clean bank import. It is not a smaller version of the
first: one missing field moves the income figure the WRONG WAY by 60 and
destroys a 150 credit, leaving the taxpayer about 210 worse off on a single
invoice. What the gates below pin is that neither half happens silently.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from ....core.modelo import Modelo
from ....core.period import Period
from ....core.aggregation import LedgerIncomeGrounding
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.ledger_bindings import resolve_ledger_renta_income_aggregation_binding_values
from ....domain.calculations.registry.schema import ModeloRevision
from ....domain.iva.schema import IvaCategory
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.retencion_parameters import load_retencion_actividades_rates
from .._iva_ledger import (
    IvaLedgerAggregationIssueReason,
    resolve_iva_ledger_binding_values,
)
from .._renta_income_ledger import aggregate_renta_income_ledger
from ._iva_authority_support import aggregate_iva_ledger_observations
from ._renta_income_aggregation_support import _raw_transaction

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# The invoice, stated once. Derived from the two cited rates and the canonical
# identity, not from engine output.
_BASE = Decimal("1000.00")
_CUOTA = Decimal("210.00")
_RETENCION = Decimal("150.00")
_TOTAL = _BASE + _CUOTA
_CASH = _TOTAL - _RETENCION

_BUCKET = "cc3c6664-c25c-49c0-8f90-2d33f2b3dfa4"  # was 'bucket-cross-domain'
_VALUE_DATE = date(2024, 2, 15)
_PERIOD = Period.from_year_and_code(2024, "1T")


def test_the_scenario_figures_satisfy_the_canonical_invoice_identity() -> None:
    """The fixture numbers are internally consistent before anything consumes them.

    Cheap, and it is the difference between a scenario grounded in invoice
    arithmetic and one grounded in four numbers somebody typed. If this fails,
    every assertion below is measuring against a fiction.

    The retención rate comes from the registry rather than a literal. A literal
    here would go on asserting 15 % after the statutory rate moved -- passing
    against superseded law while claiming to verify the chain -- and the oracle
    modules that landed alongside this one already read it from the registry, so
    a literal would also be a second spelling of one regulatory fact.

    It reads the STATUTORY rate, not
    :func:`maximum_supported_activity_retencion_rate`. That accessor returns the
    same number today but its documented role is the upper bound the withheld
    inference refuses to exceed, which is a different claim that merely
    coincides. Asserting a statutory figure through a cap would be right for the
    wrong reason, and would stop being right at all the moment the two are set
    apart deliberately.

    The IVA rate stays literal because it is the fixture's own choice of tier:
    the invoice is declared as a 21 % supply, and the registry is consulted for
    what 21 % IS, not for which tier this invoice used.
    """
    assert Decimal("1210.00") == _TOTAL
    assert Decimal("1060.00") == _CASH
    assert (_BASE * Decimal("0.21")).quantize(Decimal("0.01")) == _CUOTA
    statutory_retencion_rate = load_retencion_actividades_rates().general_rate
    assert (_BASE * statutory_retencion_rate).quantize(Decimal("0.01")) == _RETENCION


def _invoice_transaction(
    *,
    with_substrate: bool,
    provider_id: str = "tx-cross-domain",
) -> Transaction:
    """One INCOMING professional receipt, with or without its invoice substrate.

    Both variants credit the SAME cash. That is the whole point: the bank line
    is identical and only the recorded invoice differs, which is exactly the
    pair of states a cash amount cannot tell apart.
    """
    payload: dict[str, object] = {
        # Reuses the module-local raw-row factory the other income tests build
        # on, so this scenario cannot drift from them on the shape of a ledger
        # line while claiming to describe the same pipeline.
        "raw": _raw_transaction(
            provider_id,
            booked_date=_VALUE_DATE,
            value_date=_VALUE_DATE,
            amount=_CASH,
        ),
        "direction": TransactionDirection.INCOMING,
        "group_label": None,
        "source_jurisdiction": "ES",
        "business_classification": BusinessClassification.BUSINESS,
        "irpf_category": "actividad_economica",
        "lifecycle_state": TransactionLifecycleState.ACTIVE,
        "classified_at": datetime(2024, 4, 6, 13, 0, tzinfo=UTC),
        "classified_by": "manual",
    }
    if with_substrate:
        payload["taxable_base"] = _BASE
        payload["iva_amount"] = _CUOTA
        payload["iva_rate"] = Decimal("0.21")
        payload["iva_category"] = IvaCategory.DOMESTIC_GENERAL
    return Transaction.model_validate(payload)


def _catalogue(transaction: Transaction) -> TransactionCatalogue:
    return TransactionCatalogue.model_validate({transaction.transaction_id: transaction})


def _reconciliation_violations(
    income_base: Decimal | None,
    income_cash: Decimal,
    withheld: Decimal,
    iva_base: Decimal,
    iva_cuota: Decimal,
) -> tuple[str, ...]:
    """Return every way the three legs fail to describe one invoice.

    Expressed as returned DATA rather than as bare asserts so the same rule can
    be driven in both directions: the live scenario asserts it finds nothing,
    and the mutation tests below assert it finds the specific thing they broke.
    A checker that could only ever be asserted true is indistinguishable from
    one that always returns true, which is the vacuity this shape rules out.

    Accepts loose figures rather than the aggregation objects because the
    mutation tests need to feed combinations the production models would
    rightly refuse to construct.
    """
    violations: list[str] = []
    if income_base is None:
        return ("income leg declares no taxable base",)
    if iva_base != income_base:
        violations.append("iva base disagrees with income base")
    if income_base + iva_cuota != _TOTAL:
        violations.append("base plus cuota does not close the invoice total")
    if _TOTAL - withheld != income_cash:
        violations.append("total minus retencion does not close the cash received")
    return tuple(violations)


# --------------------------------------------------------------------------- #
# The grounded invoice: three domains, one decomposition
# --------------------------------------------------------------------------- #


def test_a_grounded_invoice_reconciles_across_income_retenciones_and_iva() -> None:
    """All three projections agree about one invoice, and agree with the paper.

    Income takes the IVA-exclusive base (ingresos integros, since IVA
    repercutido is collected for Hacienda -- a reading of PGC NRV 12.a/14.a,
    which is NOT bundled, so it is cited authority rather than corpus text this
    repo can re-verify). Retenciones
    recovers the 150 the payer withheld, by inference from gross minus cash.
    IVA sees the 210 cuota. Each is asserted against the invoice figure, and the
    three are then asserted to reconcile to the same total, which is the
    cross-domain property no single-domain test could state.
    """
    transaction = _invoice_transaction(with_substrate=True)
    catalogue = _catalogue(transaction)

    income = aggregate_renta_income_ledger(catalogue, bucket_id=_BUCKET, period=_PERIOD)
    iva = aggregate_iva_ledger_observations(catalogue, period=_PERIOD)

    assert len(income.observations) == 1
    observation = income.observations[0]

    # Income leg: the base, never the cash and never the IVA-inclusive total.
    assert observation.taxable_base_amount == _BASE
    assert observation.grounding is LedgerIncomeGrounding.SUBSTRATE_DECLARED
    assert observation.gross_amount == _CASH

    # Retenciones leg: the withheld figure recovered from the substrate.
    assert observation.withheld_amount == _RETENCION

    # IVA leg: the cuota repercutida.
    assert len(iva.observations) == 1
    assert iva.observations[0].base_amount == _BASE
    assert iva.observations[0].iva_amount == _CUOTA

    # Nothing was excluded from either pipeline.
    assert income.issues == ()
    assert iva.issues == ()

    # The cross-domain reconciliation: the three legs are three views of ONE
    # decomposition, so they must close the identity the invoice satisfies.
    # Driven through the shared checker, which the mutation tests below prove
    # is capable of reporting a violation.
    assert (
        _reconciliation_violations(
            income_base=observation.taxable_base_amount,
            income_cash=observation.gross_amount,
            withheld=observation.withheld_amount,
            iva_base=iva.observations[0].base_amount,
            iva_cuota=iva.observations[0].iva_amount,
        )
        == ()
    )


# --------------------------------------------------------------------------- #
# The ungrounded invoice: excluded or flagged, never silent
# --------------------------------------------------------------------------- #


def test_an_ungrounded_invoice_is_never_silently_dropped_nor_silently_folded() -> None:
    """The substrate-less twin, and the two different ways each domain answers.

    The operator instruction this pins is that a correctly-FAILING condition
    matters as much as a correct filing. The two domains answer differently and
    both answers are deliberate:

    * IVA EXCLUDES the row and says so. An untagged line has no cuota to
      declare, and inventing one would fabricate a liability.
    * Income KEEPS the row and flags it. Dropping it would under-declare by the
      whole 1060 rather than mis-measure it by 60, which is strictly worse, so
      the fallback is deliberate and the grounding marker is what makes it
      visible.

    Neither is silent, and that is the invariant. What is asserted here is not
    that the figures are right, since they are knowingly wrong, but that the
    wrongness is announced.
    """
    transaction = _invoice_transaction(with_substrate=False)
    catalogue = _catalogue(transaction)

    income = aggregate_renta_income_ledger(catalogue, bucket_id=_BUCKET, period=_PERIOD)
    iva = aggregate_iva_ledger_observations(catalogue, period=_PERIOD)

    # IVA: excluded, with a reason naming the missing fact.
    assert iva.observations == ()
    assert IvaLedgerAggregationIssueReason.MISSING_TAXABLE_BASE in {issue.reason for issue in iva.issues}

    # Income: kept, and marked as resting on cash rather than substrate.
    assert len(income.observations) == 1
    observation = income.observations[0]
    assert observation.grounding is LedgerIncomeGrounding.CASH_FALLBACK
    assert observation.taxable_base_amount is None


def test_the_ungrounded_invoice_costs_the_taxpayer_in_both_directions_at_once() -> None:
    """One missing field moves two figures against the taxpayer simultaneously.

    This is the measured harm the campaign exists to make visible, pinned as a
    regression so a later change cannot quietly alter its size. Income is
    OVER-declared, because the credited cash (1060) exceeds the base (1000):
    the IVA repercutido inflates it by more than the retencion deflates it. And
    the 150 credit is lost entirely, because the withholding inference needs the
    substrate that is missing.

    Both are asserted against the correct figures rather than as bare constants,
    so the test states WHY each number is wrong rather than merely that it is.
    """
    income = aggregate_renta_income_ledger(
        _catalogue(_invoice_transaction(with_substrate=False)),
        bucket_id=_BUCKET,
        period=_PERIOD,
    )
    observation = income.observations[0]

    # Over-declared income: the row contributes cash, which is above the base.
    assert observation.gross_amount == _CASH
    assert observation.gross_amount > _BASE
    assert observation.gross_amount - _BASE == Decimal("60.00")

    # Lost credit: the retencion cannot be inferred without the substrate.
    assert observation.withheld_amount == Decimal("0")
    assert observation.withheld_amount != _RETENCION

    # The combined swing against the taxpayer on a single invoice.
    assert (observation.gross_amount - _BASE) + _RETENCION == Decimal("210.00")


# --------------------------------------------------------------------------- #
# The reconciliation is proven able to FAIL, not merely observed passing
# --------------------------------------------------------------------------- #
#
# A cross-domain assertion that has only ever been seen green is
# indistinguishable from one that cannot go red. These drive the SAME checker
# the live scenario uses, against decompositions that are deliberately wrong in
# one place each, and assert it names exactly the break.
#
# The mutations are applied to the DATA rather than by patching the production
# decomposition, deliberately: a monkeypatched aggregator is barred here, and a
# test that rewrites the code under test proves things about the patch rather
# than about the shipped path. The complementary production-code mutations
# (breaking the aggregators themselves and confirming this module reddens) are
# run out of band and recorded separately, because they cannot live in the
# suite without patching.


def test_a_disagreeing_iva_base_is_caught() -> None:
    """If IVA and income disagree about the base, the invoice is not one invoice.

    The single most likely real divergence: two pipelines reading the same
    field through different paths and drifting apart. Each leg would still
    satisfy its own domain's tests.
    """
    violations = _reconciliation_violations(
        income_base=_BASE,
        income_cash=_CASH,
        withheld=_RETENCION,
        iva_base=_BASE + Decimal("1.00"),
        iva_cuota=_CUOTA,
    )
    assert "iva base disagrees with income base" in violations


def test_a_cuota_that_does_not_close_the_total_is_caught() -> None:
    """A wrong cuota breaks base + cuota = total even with both legs internally fine."""
    violations = _reconciliation_violations(
        income_base=_BASE,
        income_cash=_CASH,
        withheld=_RETENCION,
        iva_base=_BASE,
        iva_cuota=_CUOTA + Decimal("10.00"),
    )
    assert "base plus cuota does not close the invoice total" in violations


def test_a_withholding_that_does_not_close_the_cash_is_caught() -> None:
    """The retencion leg is checked against cash, not merely asserted non-zero.

    This is the assertion that would have caught the substrate-less case
    silently returning zero if the cash had not also moved -- the pair is what
    makes it a reconciliation rather than two independent facts.
    """
    violations = _reconciliation_violations(
        income_base=_BASE,
        income_cash=_CASH,
        withheld=Decimal("0"),
        iva_base=_BASE,
        iva_cuota=_CUOTA,
    )
    assert "total minus retencion does not close the cash received" in violations


def test_a_missing_income_base_is_caught_before_the_other_checks_run() -> None:
    """An absent base short-circuits: with no base, the later checks are unanswerable.

    Reported as its own violation rather than crashing or silently skipping,
    so the ungrounded case is distinguishable from a reconciling one.
    """
    violations = _reconciliation_violations(
        income_base=None,
        income_cash=_CASH,
        withheld=Decimal("0"),
        iva_base=_BASE,
        iva_cuota=_CUOTA,
    )
    assert violations == ("income leg declares no taxable base",)


def test_the_checker_is_silent_only_on_the_true_decomposition() -> None:
    """The control. Without it, an always-empty checker passes every test above.

    Each mutation test asserts a specific violation is PRESENT; none of them
    would fail if the checker reported every possible violation unconditionally.
    This is the other half: on the correct figures it reports nothing at all.
    """
    assert (
        _reconciliation_violations(
            income_base=_BASE,
            income_cash=_CASH,
            withheld=_RETENCION,
            iva_base=_BASE,
            iva_cuota=_CUOTA,
        )
        == ()
    )


# --------------------------------------------------------------------------- #
# The same invoice, reconciled at the BINDING level
# --------------------------------------------------------------------------- #
#
# The scenario above reconciles the three projections at the OBSERVATION level,
# which proves the pipelines agree. It does not prove the registry then routes
# those figures to the casillas a taxpayer actually files. Those are different
# claims: a correct observation consumed by the wrong binding, or by none, is
# still a wrong return.
#
# So the same invoice is driven one layer further, through the committed
# bindings, and the resolved binding VALUES are asserted against the invoice
# figures. This is the layer at which "the three domains agree" becomes a
# statement about the declaration rather than about the code.
#
# The division of labour with the per-modelo oracle modules is deliberate.
# Those assert that ONE modelo receives its published measure, with the
# grounding markers and the derivation route that got it there. This module
# asserts only what no single-modelo test can state: that the values several
# modelos file describe one invoice. Where a value is asserted here it is
# because the cross-domain claim needs it, never as a second opinion on a
# claim that already has an owner.


_M130_INGRESOS_BINDING = "modelo-130-actividad-economica-ingresos-cumulative"
_M130_RETENCIONES_BINDING = "modelo-130-actividad-economica-retenciones-cumulative"


def _modelo_130_revision() -> ModeloRevision:
    """The committed M130 revision, resolved the way production resolves it.

    Through the registry authority rather than a test-side snapshot builder, so
    the bindings asserted below are the ones a real calculate would load. A
    hand-built snapshot could agree with the test and disagree with the filing.
    """
    return (
        bundled_authority()
        .snapshot(
            Modelo.M130.value,
            filing_year=2024,
            period="1T",
        )
        .revision
    )


def test_the_filed_figures_close_the_invoice_identity() -> None:
    """Income and retenciones, as filed, reconcile with the IVA cuota to one invoice.

    The whole point of the campaign, stated at the layer that matters: the
    numbers on the declaration are three views of one document, and adding the
    cuota to the filed income must reproduce the invoice total the taxpayer
    issued.
    """
    revision = _modelo_130_revision()
    catalogue = _catalogue(_invoice_transaction(with_substrate=True))
    income = aggregate_renta_income_ledger(catalogue, bucket_id=_BUCKET, period=_PERIOD)
    iva = aggregate_iva_ledger_observations(catalogue, period=_PERIOD)

    resolved = resolve_ledger_renta_income_aggregation_binding_values(revision, income.observations)

    assert (
        _reconciliation_violations(
            income_base=resolved[_M130_INGRESOS_BINDING],
            income_cash=_CASH,
            withheld=resolved[_M130_RETENCIONES_BINDING],
            iva_base=iva.observations[0].base_amount,
            iva_cuota=iva.observations[0].iva_amount,
        )
        == ()
    )


# --------------------------------------------------------------------------- #
# The IVA leg, also at the BINDING level
# --------------------------------------------------------------------------- #
#
# The M130 assertions above carry the income and retenciones legs to the
# declaration. The IVA leg stopped at the observation, so two of the three
# domains this module exists to reconcile were checked one layer deeper than
# the third -- the binding-level insight did not cross the modelo boundary it
# was written to cross.
#
# The cuota reaches a different modelo, so it takes a different revision and a
# different resolver, but the claim is identical: a correct observation
# consumed by the wrong binding, or by none, is still a wrong return.

_M303_REPERCUTIDO_BASE_BINDING = "modelo-303-iva-repercutido-general-base"
_M303_REPERCUTIDO_CUOTA_BINDING = "modelo-303-iva-repercutido-general-cuota"


def _modelo_303_revision() -> ModeloRevision:
    """The committed M303 revision, resolved the way production resolves it.

    Same discipline as :func:`_modelo_130_revision`: through the registry
    authority, never a test-side snapshot builder, so the bindings asserted
    are the ones a real calculate would load.
    """
    return (
        bundled_authority()
        .snapshot(
            Modelo.M303.value,
            filing_year=2024,
            period="1T",
        )
        .revision
    )


def test_the_committed_m303_bindings_receive_the_invoice_figures() -> None:
    """The IVA leg reaches its filed casillas, not merely its observation.

    The repercutido base takes the same 1000 the income casilla takes, and the
    cuota takes the 210 that is collected for Hacienda rather than earned. That
    the two modelos draw the same base from one invoice is the cross-domain
    claim stated where it is filed rather than where it is computed: M130
    casilla 01 and the M303 repercutido base are the same figure reached by
    different registries.

    Asserted against the invoice figures, never against the M130 resolution --
    two modelos agreeing with each other while both disagreeing with the
    invoice is precisely the failure a cross-domain test exists to catch.
    """
    revision = _modelo_303_revision()
    iva = aggregate_iva_ledger_observations(
        _catalogue(_invoice_transaction(with_substrate=True)),
        period=_PERIOD,
    )

    resolved = resolve_iva_ledger_binding_values(revision, iva.observations)

    assert resolved[_M303_REPERCUTIDO_BASE_BINDING] == _BASE
    assert resolved[_M303_REPERCUTIDO_CUOTA_BINDING] == _CUOTA


def test_the_two_modelos_draw_the_same_base_from_one_invoice() -> None:
    """M130 casilla 01 and the M303 repercutido base are one figure, filed twice.

    This is the reconciliation the module is named for, asserted at the layer
    that reaches a return. Both sides are compared to the invoice base rather
    than to each other, so the assertion cannot be satisfied by two registries
    agreeing on a wrong number.
    """
    catalogue = _catalogue(_invoice_transaction(with_substrate=True))
    income = aggregate_renta_income_ledger(catalogue, bucket_id=_BUCKET, period=_PERIOD)
    iva = aggregate_iva_ledger_observations(catalogue, period=_PERIOD)

    m130 = resolve_ledger_renta_income_aggregation_binding_values(_modelo_130_revision(), income.observations)
    m303 = resolve_iva_ledger_binding_values(_modelo_303_revision(), iva.observations)

    assert m130[_M130_INGRESOS_BINDING] == _BASE
    assert m303[_M303_REPERCUTIDO_BASE_BINDING] == _BASE
