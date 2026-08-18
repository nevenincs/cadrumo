"""Modelo 193 totals-parity gate: the per-perceptor retención store vs the resumen summary casillas.

Modelo 193's resumen-anual summary casillas (``decl.base-total``,
``decl.retenciones-total``) are computed by the registry as a SUM of the
taxpayer's four Modelo 123 quarterly filings — a ``source =
"relation_prefill"`` aggregation entirely independent of the dedicated
per-perceptor retención store
(:class:`~application.aggregation.RetencionesAggregation`,
``source = "retenciones_aggregation"``) that also materialises the
``decl.total-perceptores`` distinct-NIF count.

Nothing in the registry cross-checks that these two independently-sourced
totals agree: the M123-quarterly relation path could produce one monetary
figure while the per-perceptor detail (the row-level breakdown an operator or
AEAT audit would actually reconstruct the resumen from) sums to a different
figure, and today's engine would silently accept both without complaint
(``no-silent-under-declaration``).

This module drives the REAL registry-loaded Modelo 193 ``2025-y-siguientes``
snapshot and the REAL engine (``calculate_registry_snapshot``, no mocks) to
prove :func:`~application.aggregation.compute_retenciones_totals_parity`
against genuine engine output: a consistent per-perceptor store (rows sum to
the engine-computed summary) passes, and a dropped perceptor row (the store no
longer accounts for the full summary total) is CAUGHT with the exact delta
named, never silently accepted.

Grounding: RD 439/2007 art. 90, art. 108, Orden HAC/56/2024 (Diseño de
Registro Modelo 193, Tipo de Registro 1, posiciones 136-144 / 145-159 /
160-174), Ley 35/2006 arts. 25, 99, 101.

See Also:
    :func:`~application.aggregation.compute_retenciones_totals_parity`
        Pure comparison primitive whose deltas this regression suite asserts.
    :class:`~application.aggregation.RetencionesTotalsParity`
        Verdict model that keeps the perceptor-count, base, and retención axes
        explicit instead of collapsing mismatches into a boolean.
    :func:`~application.aggregation.aggregate_retenciones_193`
        Dedicated per-perceptor aggregator that supplies the store-side
        totals for Modelo 193.
    :class:`~application.aggregation.RetencionesAggregation`
        Repository-backed retenciones summary source enrolled on the calculate
        mesh for M180/M193 distinct-NIF counts.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import BindingSourceKind, CasillaId, Period, validated_casilla_id
from ....core.resources import resources
from ....domain.calculations.registry import (
    RelationId,
    calculate_registry_snapshot,
    materialize_relation_binding_values,
    resolve_available_bound_inputs_by_casilla_id,
    resolve_retenciones_aggregation_binding_values,
)
from ....tests.secure_sql import isolated_runtime_profile
from .._retenciones import (
    RetencionObservation,
    RetencionScheme,
    aggregate_retenciones_193,
    compute_retenciones_totals_parity,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO_193 = "193"
_FILING_YEAR = 2025


_M193_BASE_TOTAL_CASILLA: CasillaId = validated_casilla_id("decl.base-total")
_M193_RETENCIONES_TOTAL_CASILLA: CasillaId = validated_casilla_id("decl.retenciones-total")
_M193_TOTAL_PERCEPTORES_CASILLA: CasillaId = validated_casilla_id("decl.total-perceptores")

# The two Modelo 123 quarterly-relation sums feeding decl.base-total /
# decl.retenciones-total. This test's unit under test is the parity CHECK, not
# the M123->M193 relation wiring (covered by
# test_modelo_193_123_reconciliation_continuity.py), so the relation values
# are supplied directly.
_RELATION_VALUES: dict[RelationId, Decimal] = {
    "modelo-193-rel-123-base-anual": Decimal("12000.50"),
    "modelo-193-rel-123-retenciones-anual": Decimal("2280.10"),
}

# Two per-perceptor retención observations (Orden HAC/56/2024 Diseño de
# Registro, Tipo de Registro 2 "registro de perceptor") whose sums reproduce
# the relation-derived summary totals exactly: this is the CONSISTENT
# fixture.
_CONSISTENT_RETENCION_OBSERVATIONS: tuple[RetencionObservation, ...] = (
    RetencionObservation(
        source_kind=BindingSourceKind.LEDGER_TRANSACTION,
        source_object_id="c-obs-1",
        perceptor_nif="11111111H",
        perceptor_name="Perceptor One",
        scheme=RetencionScheme.CAPITAL_DIVIDEND,
        taxable_base=Decimal("8000.50"),
        retencion_amount=Decimal("1520.10"),
        accrued_on=f"{_FILING_YEAR}-03-15",
    ),
    RetencionObservation(
        source_kind=BindingSourceKind.LEDGER_TRANSACTION,
        source_object_id="c-obs-2",
        perceptor_nif="22222222J",
        perceptor_name="Perceptor Two",
        scheme=RetencionScheme.CAPITAL_INTEREST,
        taxable_base=Decimal("4000.00"),
        retencion_amount=Decimal("760.00"),
        accrued_on=f"{_FILING_YEAR}-06-01",
    ),
)
_EXPECTED_PERCEPTORES_TOTAL = 2
_EXPECTED_BASE_TOTAL = Decimal("12000.50")
_EXPECTED_RETENCIONES_TOTAL = Decimal("2280.10")


def _calculate_193(
    *,
    relation_values: dict[RelationId, Decimal],
    retencion_observations: tuple[RetencionObservation, ...],
):
    """Run the REAL 193 annual calculation from relations + the per-perceptor retención store."""
    snapshot = resources().modelos.authority.snapshot(_MODELO_193, filing_year=_FILING_YEAR, period="0A")
    relation_binding_values = materialize_relation_binding_values(snapshot.revision, relation_values, period="0A")
    aggregation = aggregate_retenciones_193(
        retencion_observations,
        period=Period.from_year_and_code(_FILING_YEAR, "0A"),
    )
    retenciones_binding_values = resolve_retenciones_aggregation_binding_values(snapshot.revision, aggregation)
    binding_values = {**relation_binding_values, **retenciones_binding_values}
    inputs = resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values)
    result = calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        binding_values=binding_values,
        relation_values=relation_values,
        date_context={"filing_period": date(_FILING_YEAR, 12, 31)},
    )
    return result, aggregation


def test_engine_computed_summary_totals_match_the_fixture_constants(tmp_path: Path) -> None:
    """Sanity anchor: the real engine reproduces the hand-derived relation sums + the aggregation count.

    Not the parity gate itself (covered below) — this pins that the fixture's
    _EXPECTED_* constants genuinely describe what the REAL M123-relation
    aggregation formula and the REAL per-perceptor aggregator produce, so the
    parity tests below check the gate against real engine output, not against
    a number this test author invented independently of the registry formula.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        result, aggregation = _calculate_193(
            relation_values=_RELATION_VALUES,
            retencion_observations=_CONSISTENT_RETENCION_OBSERVATIONS,
        )

    assert result.values[_M193_BASE_TOTAL_CASILLA] == _EXPECTED_BASE_TOTAL
    assert result.values[_M193_RETENCIONES_TOTAL_CASILLA] == _EXPECTED_RETENCIONES_TOTAL
    assert result.values[_M193_TOTAL_PERCEPTORES_CASILLA] == Decimal(_EXPECTED_PERCEPTORES_TOTAL)
    assert aggregation.total_perceptors == _EXPECTED_PERCEPTORES_TOTAL
    assert aggregation.total_taxable_base == _EXPECTED_BASE_TOTAL
    assert aggregation.total_retencion == _EXPECTED_RETENCIONES_TOTAL


def test_totals_parity_passes_when_retencion_store_reconstructs_the_summary(tmp_path: Path) -> None:
    """A complete per-perceptor retención store that sums to the engine's summary totals is consistent."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        result, aggregation = _calculate_193(
            relation_values=_RELATION_VALUES,
            retencion_observations=_CONSISTENT_RETENCION_OBSERVATIONS,
        )

    parity = compute_retenciones_totals_parity(
        aggregation,
        perceptores_summary_total=int(result.values[_M193_TOTAL_PERCEPTORES_CASILLA]),
        base_summary_total=result.values[_M193_BASE_TOTAL_CASILLA],
        retenciones_summary_total=result.values[_M193_RETENCIONES_TOTAL_CASILLA],
    )

    assert parity.is_consistent
    assert parity.perceptores_delta == 0
    assert parity.base_delta == Decimal("0.00")
    assert parity.retenciones_delta == Decimal("0.00")
    assert parity.base_aggregation_total == _EXPECTED_BASE_TOTAL
    assert parity.retenciones_aggregation_total == _EXPECTED_RETENCIONES_TOTAL


def test_totals_parity_catches_a_dropped_perceptor_row(tmp_path: Path) -> None:
    """Dropping one perceptor's row under-declares the store-level total below the resumen summary casilla.

    Grounded regression for the totals-parity gap: prior to this gate, the
    engine's monetary summary casillas were computed purely from the
    M123-relation path and NEVER cross-checked against the per-perceptor
    retención store, so a store row silently dropped from the operator's
    per-perceptor entry (a data-loss bug, an incomplete import, or a tampered
    payer export) produced no finding at all.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        # Same real engine calculation (same relation-derived summary totals)
        # as the consistent case, but the retención store detail omits
        # Perceptor Two entirely.
        result, _ = _calculate_193(
            relation_values=_RELATION_VALUES,
            retencion_observations=_CONSISTENT_RETENCION_OBSERVATIONS,
        )
        incomplete_aggregation = aggregate_retenciones_193(
            _CONSISTENT_RETENCION_OBSERVATIONS[:1],
            period=Period.from_year_and_code(_FILING_YEAR, "0A"),
        )

    parity = compute_retenciones_totals_parity(
        incomplete_aggregation,
        perceptores_summary_total=int(result.values[_M193_TOTAL_PERCEPTORES_CASILLA]),
        base_summary_total=result.values[_M193_BASE_TOTAL_CASILLA],
        retenciones_summary_total=result.values[_M193_RETENCIONES_TOTAL_CASILLA],
    )

    assert not parity.is_consistent
    # Missing perceptor two: distinct-NIF count under-declared by one.
    assert parity.perceptores_delta == -1
    # Missing perceptor two: base 4000.00 under-declared.
    assert parity.base_delta == Decimal("-4000.00")
    # Missing perceptor two: retención 760.00 under-declared.
    assert parity.retenciones_delta == Decimal("-760.00")


def test_totals_parity_default_is_exact_equality_not_a_hardcoded_cent() -> None:
    """The DEFAULT tolerance is exact equality, and a genuine one-cent gap is caught by it.

    Modelo 193's own 2025 revision publishes an EXACT (``0.00``) verification
    tolerance -- pinned against the live registry below so this proof cannot
    silently drift -- so a caller that forgets to resolve and pass
    ``snapshot.verification_policy().tolerance`` must not have a one-cent gap
    silently absorbed by this function's own default. A prior version of this
    default was a hardcoded cent that would have masked exactly this gap.
    """
    published = (
        resources()
        .modelos.authority.snapshot(_MODELO_193, filing_year=_FILING_YEAR, period="0A")
        .verification_policy()
        .tolerance
    )
    assert published == Decimal("0"), "test precondition: modelo 193 2025 must publish exact equality"

    aggregation = aggregate_retenciones_193(
        _CONSISTENT_RETENCION_OBSERVATIONS,
        period=Period.from_year_and_code(_FILING_YEAR, "0A"),
    )

    one_cent_off = compute_retenciones_totals_parity(
        aggregation,
        perceptores_summary_total=_EXPECTED_PERCEPTORES_TOTAL,
        base_summary_total=_EXPECTED_BASE_TOTAL + Decimal("0.01"),
        retenciones_summary_total=_EXPECTED_RETENCIONES_TOTAL,
    )
    assert not one_cent_off.is_consistent, "the default must not silently absorb a genuine one-cent divergence"
    assert one_cent_off.base_delta == Decimal("-0.01")


def test_totals_parity_tolerance_absorbs_sub_cent_rounding_only() -> None:
    """A one-cent delta is within an EXPLICITLY PASSED tolerance; a two-cent delta is not.

    Pure unit-level boundary check on the comparison primitive itself (no
    engine dependency) — the monetary tolerance is symmetric and exclusive of
    the boundary+epsilon. The tolerance is passed explicitly here rather than
    relied on as a default, because the registry (not this test) is the
    authority for what value a real caller resolves. The perceptor-count axis
    is an exact integer match with no tolerance.
    """
    aggregation = aggregate_retenciones_193(
        _CONSISTENT_RETENCION_OBSERVATIONS,
        period=Period.from_year_and_code(_FILING_YEAR, "0A"),
    )

    within_tolerance = compute_retenciones_totals_parity(
        aggregation,
        perceptores_summary_total=_EXPECTED_PERCEPTORES_TOTAL,
        base_summary_total=_EXPECTED_BASE_TOTAL + Decimal("0.01"),
        retenciones_summary_total=_EXPECTED_RETENCIONES_TOTAL,
        tolerance=Decimal("0.01"),
    )
    assert within_tolerance.is_consistent

    beyond_tolerance = compute_retenciones_totals_parity(
        aggregation,
        perceptores_summary_total=_EXPECTED_PERCEPTORES_TOTAL,
        base_summary_total=_EXPECTED_BASE_TOTAL + Decimal("0.02"),
        retenciones_summary_total=_EXPECTED_RETENCIONES_TOTAL,
        tolerance=Decimal("0.01"),
    )
    assert not beyond_tolerance.is_consistent
    assert beyond_tolerance.base_delta == Decimal("-0.02")

    perceptor_mismatch = compute_retenciones_totals_parity(
        aggregation,
        perceptores_summary_total=_EXPECTED_PERCEPTORES_TOTAL + 1,
        base_summary_total=_EXPECTED_BASE_TOTAL,
        retenciones_summary_total=_EXPECTED_RETENCIONES_TOTAL,
    )
    assert not perceptor_mismatch.is_consistent
    assert perceptor_mismatch.perceptores_delta == -1


def test_totals_parity_over_empty_retencion_store_reports_full_shortfall() -> None:
    """No persisted per-perceptor detail at all is a full shortfall, not a vacuous pass.

    A nil-percepciones filer legitimately has zero rows AND a zero summary
    total; this test pins that when the summary
    total is nonzero but the aggregation is empty, the gate reports the entire
    summary amount as the delta rather than silently treating "no rows" as
    "nothing to check".
    """
    empty_aggregation = aggregate_retenciones_193((), period=Period.from_year_and_code(_FILING_YEAR, "0A"))

    parity = compute_retenciones_totals_parity(
        empty_aggregation,
        perceptores_summary_total=_EXPECTED_PERCEPTORES_TOTAL,
        base_summary_total=_EXPECTED_BASE_TOTAL,
        retenciones_summary_total=_EXPECTED_RETENCIONES_TOTAL,
    )

    assert not parity.is_consistent
    assert parity.base_aggregation_total == Decimal("0")
    assert parity.perceptores_delta == -_EXPECTED_PERCEPTORES_TOTAL
    assert parity.base_delta == -_EXPECTED_BASE_TOTAL
    assert parity.retenciones_delta == -_EXPECTED_RETENCIONES_TOTAL
