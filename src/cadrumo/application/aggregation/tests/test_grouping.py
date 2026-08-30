"""Pin behavioural invariants of the shared grouping and casilla-fold helpers."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core import Modelo
from ....core.period import Period
from ....core.casilla_id import validated_casilla_id
from ....core.aggregation import BindingSourceKind
from ....core.aggregation import LedgerIncomeGrounding, RetencionScheme
from ....domain.transactions.models import TransactionCatalogue
from .._grouping import cumulative_year_to_date_window, fold_casilla_observations, group_and_collect_names
from .._renta_income_ledger import RentaIncomeObservation
from .._retenciones import RetencionObservation
from ..errors import AggregationPeriodError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_SOURCE_LEDGER = BindingSourceKind.LEDGER_TRANSACTION
_SOURCE_INVOICE = BindingSourceKind.COLLECTIBLE_INVOICE
_SCHEME_WORK = RetencionScheme.WORK_INCOME
_SCHEME_RENT = RetencionScheme.URBAN_RENTAL


def _observation(
    source_kind: BindingSourceKind,
    perceptor_nif: str,
    scheme: RetencionScheme,
    perceptor_name: str = "",
) -> RetencionObservation:
    return RetencionObservation(
        source_kind=source_kind,
        source_object_id=f"{source_kind.value}:{perceptor_nif}:{scheme.value}:{perceptor_name or 'empty'}",
        perceptor_nif=perceptor_nif,
        perceptor_name=perceptor_name,
        scheme=scheme,
        taxable_base=Decimal("1.00"),
        retencion_amount=Decimal("0.15"),
        accrued_on="2026-01-01",
    )


def _name(obs: RetencionObservation) -> str | None:
    return obs.perceptor_name or None


def _group_key(obs: RetencionObservation) -> tuple[BindingSourceKind, str, RetencionScheme]:
    return (BindingSourceKind(obs.source_kind), obs.perceptor_nif, obs.scheme)


def _identity_key(obs: RetencionObservation) -> tuple[BindingSourceKind, str]:
    return (BindingSourceKind(obs.source_kind), obs.perceptor_nif)


def test_group_and_collect_names_buckets_by_composite_key() -> None:
    observations = (
        _observation(_SOURCE_LEDGER, "A", _SCHEME_WORK, "Alpha"),
        _observation(_SOURCE_LEDGER, "A", _SCHEME_WORK, "Alpha"),
        _observation(_SOURCE_LEDGER, "A", _SCHEME_RENT, "Alpha"),
        _observation(_SOURCE_LEDGER, "B", _SCHEME_WORK, "Beta"),
    )
    grouped, _ = group_and_collect_names(
        observations,
        group_key_fn=_group_key,
        identity_key_fn=_identity_key,
        name_fn=_name,
    )
    assert set(grouped.keys()) == {
        (_SOURCE_LEDGER, "A", _SCHEME_WORK),
        (_SOURCE_LEDGER, "A", _SCHEME_RENT),
        (_SOURCE_LEDGER, "B", _SCHEME_WORK),
    }
    assert len(grouped[(_SOURCE_LEDGER, "A", _SCHEME_WORK)]) == 2
    assert len(grouped[(_SOURCE_LEDGER, "A", _SCHEME_RENT)]) == 1
    assert len(grouped[(_SOURCE_LEDGER, "B", _SCHEME_WORK)]) == 1


def test_group_and_collect_names_preserves_iteration_order_within_bucket() -> None:
    first = _observation(_SOURCE_LEDGER, "A", _SCHEME_WORK, "Alpha")
    second = _observation(_SOURCE_LEDGER, "A", _SCHEME_WORK, "Alpha-2nd")
    third = _observation(_SOURCE_LEDGER, "A", _SCHEME_WORK, "Alpha-3rd")
    grouped, _ = group_and_collect_names(
        (first, second, third),
        group_key_fn=_group_key,
        identity_key_fn=_identity_key,
        name_fn=_name,
    )
    assert grouped[(_SOURCE_LEDGER, "A", _SCHEME_WORK)] == [first, second, third]


def test_group_and_collect_names_first_non_empty_name_wins() -> None:
    observations = (
        _observation(_SOURCE_LEDGER, "A", _SCHEME_WORK),
        _observation(_SOURCE_LEDGER, "A", _SCHEME_WORK, "First Real Name"),
        _observation(_SOURCE_LEDGER, "A", _SCHEME_WORK, "Later Name"),
    )
    _, names = group_and_collect_names(
        observations,
        group_key_fn=_group_key,
        identity_key_fn=_identity_key,
        name_fn=_name,
    )
    assert names[(_SOURCE_LEDGER, "A")] == "First Real Name"


def test_group_and_collect_names_skips_empty_names_without_clearing_prior_win() -> None:
    observations = (
        _observation(_SOURCE_LEDGER, "A", _SCHEME_WORK, "Real Name"),
        _observation(_SOURCE_LEDGER, "A", _SCHEME_WORK, ""),
        _observation(_SOURCE_LEDGER, "A", _SCHEME_WORK),
    )
    _, names = group_and_collect_names(
        observations,
        group_key_fn=_group_key,
        identity_key_fn=_identity_key,
        name_fn=_name,
    )
    assert names[(_SOURCE_LEDGER, "A")] == "Real Name"


def test_group_and_collect_names_separate_identities_get_separate_names() -> None:
    observations = (
        _observation(_SOURCE_LEDGER, "A", _SCHEME_WORK, "Alpha"),
        _observation(_SOURCE_LEDGER, "B", _SCHEME_WORK, "Beta"),
        _observation(_SOURCE_INVOICE, "A", _SCHEME_WORK, "Alpha-Invoice"),
    )
    _, names = group_and_collect_names(
        observations,
        group_key_fn=_group_key,
        identity_key_fn=_identity_key,
        name_fn=_name,
    )
    assert names == {
        (_SOURCE_LEDGER, "A"): "Alpha",
        (_SOURCE_LEDGER, "B"): "Beta",
        (_SOURCE_INVOICE, "A"): "Alpha-Invoice",
    }


def test_group_and_collect_names_empty_iterable_returns_empty_maps() -> None:
    grouped, names = group_and_collect_names(
        (),
        group_key_fn=_group_key,
        identity_key_fn=_identity_key,
        name_fn=_name,
    )
    assert grouped == {}
    assert names == {}


def test_group_and_collect_names_identity_subset_of_group_key_is_consistent() -> None:
    # When two different group keys share the same identity key (e.g.
    # same (source, nif) but different kind), the name cache must be
    # consistent — first non-empty name wins regardless of which group
    # observed it.
    observations = (
        _observation(_SOURCE_LEDGER, "A", _SCHEME_WORK),
        _observation(_SOURCE_LEDGER, "A", _SCHEME_RENT, "Name From K2"),
        _observation(_SOURCE_LEDGER, "A", _SCHEME_WORK, "Name From K1"),
    )
    grouped, names = group_and_collect_names(
        observations,
        group_key_fn=_group_key,
        identity_key_fn=_identity_key,
        name_fn=_name,
    )
    assert names[(_SOURCE_LEDGER, "A")] == "Name From K2"
    assert len(grouped[(_SOURCE_LEDGER, "A", _SCHEME_WORK)]) == 2
    assert len(grouped[(_SOURCE_LEDGER, "A", _SCHEME_RENT)]) == 1


# --------------------------------------------------------------------------
# fold_casilla_observations
#
# Driven through the production RentaIncomeObservation model rather than a
# bespoke test double, so the fold's structural Protocol is exercised against
# a real ledger observation exactly as the four consumer projections use it.
# --------------------------------------------------------------------------

_PERIOD = Period.from_year_and_code(2026, "1T")
_CASILLA_01 = validated_casilla_id("01", surface="test_grouping")
_CASILLA_02 = validated_casilla_id("02", surface="test_grouping")


def _tx(suffix: str) -> str:
    """A real hex-64 shape ending in ``suffix``, sorting exactly as the single
    trailing hex character does -- ``RentaIncomeObservation.transaction_id``
    is typed :data:`~core.identity.TransactionId`, so a short placeholder
    like the prior ``"tx-1"`` / ``"tx-a"`` literals no longer validates;
    padding to 64 characters keeps the sort-order fixtures below meaningful
    under the real shape.
    """
    return suffix.rjust(64, "0")


def _income(transaction_id: str, casilla: str, gross: str, base: str | None = None) -> RentaIncomeObservation:
    return RentaIncomeObservation(
        transaction_id=transaction_id,
        target_casilla_id=casilla,
        gross_amount=Decimal(gross),
        taxable_base_amount=None if base is None else Decimal(base),
        filing_date=date(2026, 2, 1),
        grounding=(LedgerIncomeGrounding.CASH_FALLBACK if base is None else LedgerIncomeGrounding.SUBSTRATE_DECLARED),
    )


def _gross(observation: RentaIncomeObservation) -> Decimal:
    return observation.gross_amount


def test_fold_sums_each_observation_into_its_own_casilla() -> None:
    aggregation = fold_casilla_observations(
        (
            _income(_tx("1"), _CASILLA_01, "100.00"),
            _income(_tx("2"), _CASILLA_01, "50.00"),
            _income(_tx("3"), _CASILLA_02, "7.00"),
        ),
        modelo=Modelo.M130.value,
        period=_PERIOD,
        amount_fn=_gross,
    )

    assert aggregation.modelo == Modelo.M130.value
    assert aggregation.period == _PERIOD
    assert dict(aggregation.casilla_values) == {_CASILLA_01: Decimal("150.00"), _CASILLA_02: Decimal("7.00")}


def test_fold_emits_one_provenance_row_per_casilla_in_sorted_order() -> None:
    aggregation = fold_casilla_observations(
        (
            _income(_tx("1"), _CASILLA_02, "7.00"),
            _income(_tx("2"), _CASILLA_01, "100.00"),
            _income(_tx("3"), _CASILLA_01, "50.00"),
        ),
        modelo=Modelo.M130.value,
        period=_PERIOD,
        amount_fn=_gross,
    )

    assert [row.casilla_id for row in aggregation.provenance] == [_CASILLA_01, _CASILLA_02]


def test_fold_sorts_contributing_transaction_ids_within_a_row() -> None:
    aggregation = fold_casilla_observations(
        (
            _income(_tx("c"), _CASILLA_01, "1.00"),
            _income(_tx("a"), _CASILLA_01, "1.00"),
            _income(_tx("b"), _CASILLA_01, "1.00"),
        ),
        modelo=Modelo.M130.value,
        period=_PERIOD,
        amount_fn=_gross,
    )

    assert tuple(aggregation.provenance[0].transaction_ids) == (_tx("a"), _tx("b"), _tx("c"))


def test_fold_provenance_subtotals_reconcile_with_the_casilla_totals() -> None:
    """A row's subtotal and its casilla total are summed through one accessor.

    A divergence here would mean the operator-facing provenance trace no longer
    explains the value it sits beside, which is the failure this invariant
    exists to catch.
    """
    aggregation = fold_casilla_observations(
        (
            _income(_tx("1"), _CASILLA_01, "100.00"),
            _income(_tx("2"), _CASILLA_01, "50.00"),
            _income(_tx("3"), _CASILLA_02, "7.00"),
        ),
        modelo=Modelo.M130.value,
        period=_PERIOD,
        amount_fn=_gross,
    )

    for row in aggregation.provenance:
        assert row.subtotal == aggregation.casilla_values[row.casilla_id]


def test_fold_leaves_category_id_unset_because_it_groups_on_the_casilla_axis_alone() -> None:
    """This fold has exactly one grouping axis.

    The Modelo 100 first-slice expense projection buckets by casilla AND
    spending category and emits a populated ``category_id``; it therefore keeps
    its own fold rather than routing here. Pinning ``category_id is None``
    keeps that distinction observable.
    """
    aggregation = fold_casilla_observations(
        (_income(_tx("1"), _CASILLA_01, "100.00"),),
        modelo=Modelo.M130.value,
        period=_PERIOD,
        amount_fn=_gross,
    )

    assert all(row.category_id is None for row in aggregation.provenance)


def test_fold_routes_every_amount_through_the_callers_accessor() -> None:
    """The amount accessor is load-bearing, not decorative.

    The same observations folded through the IVA-exclusive taxable base must
    produce different totals than the gross accessor, so a fold that ignored
    ``amount_fn`` and read a fixed attribute would fail here.
    """
    observations = (
        _income(_tx("1"), _CASILLA_01, "121.00", base="100.00"),
        _income(_tx("2"), _CASILLA_01, "60.50", base="50.00"),
    )

    gross_total = fold_casilla_observations(
        observations,
        modelo=Modelo.M130.value,
        period=_PERIOD,
        amount_fn=_gross,
    ).casilla_values[_CASILLA_01]
    base_total = fold_casilla_observations(
        observations,
        modelo=Modelo.M130.value,
        period=_PERIOD,
        amount_fn=lambda observation: observation.taxable_base_amount or observation.gross_amount,
    ).casilla_values[_CASILLA_01]

    assert gross_total == Decimal("181.50")
    assert base_total == Decimal("150.00")


def test_fold_of_no_observations_yields_an_empty_aggregation() -> None:
    aggregation = fold_casilla_observations(
        (),
        modelo=Modelo.M151.value,
        period=_PERIOD,
        amount_fn=_gross,
    )

    assert dict(aggregation.casilla_values) == {}
    assert tuple(aggregation.provenance) == ()
    assert aggregation.modelo == Modelo.M151.value


def test_cumulative_year_to_date_window_spans_january_to_quarter_end() -> None:
    """Each quarter accumulates from 1 January through its own last day.

    RD 439/2007 art. 110.2: Q1 covers Jan-Mar, Q2 Jan-Jun, Q3 Jan-Sep, Q4
    Jan-Dec. The start never moves off 1 January -- that is what makes the
    payment cumulative rather than per-quarter.
    """
    expected_ends = {
        "1T": date(2026, 3, 31),
        "2T": date(2026, 6, 30),
        "3T": date(2026, 9, 30),
        "4T": date(2026, 12, 31),
    }
    for token, expected_end in expected_ends.items():
        window = cumulative_year_to_date_window(Period.from_year_and_code(2026, token))
        assert window.start == date(2026, 1, 1), token
        assert window.end == expected_end, token
        assert window.period.registry_token == token


def test_cumulative_year_to_date_window_refuses_a_non_quarterly_period() -> None:
    """A pago fraccionado has no meaning outside a quarter, so this refuses.

    Inventing a span for an annual or monthly token would silently widen the
    base both halves of the Modelo 130 calculation accumulate over.
    """
    with pytest.raises(AggregationPeriodError):
        cumulative_year_to_date_window(Period.from_year_and_code(2026, "0A"))


def test_cumulative_year_to_date_window_is_the_one_the_m130_halves_share() -> None:
    """Ingresos and gastos must read the identical span for the same quarter.

    The two halves derived this window independently before it was extracted.
    They agreed, but nothing made them agree -- a one-sided edit would have
    desynchronised the base without any test noticing.
    """
    from .._renta_gasto_ledger import aggregate_renta_gasto_ledger
    from .._renta_income_ledger import aggregate_renta_income_ledger

    period = Period.from_year_and_code(2026, "3T")
    window = cumulative_year_to_date_window(period)

    empty = TransactionCatalogue()
    income = aggregate_renta_income_ledger(empty, bucket_id="b", period=period)
    gasto = aggregate_renta_gasto_ledger(empty, bucket_id="b", period=period)

    assert income.period == window.period
    assert gasto.period == window.period
    assert income.period == gasto.period
