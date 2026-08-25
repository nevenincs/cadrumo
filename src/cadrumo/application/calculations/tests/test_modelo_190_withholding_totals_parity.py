"""Modelo 190 totals-parity gate: per-perceptor rows vs the resumen summary casillas.

Modelo 190's resumen-anual summary casillas (``decl.percepciones-total``,
``decl.retenciones-total``) are computed by the registry as a SUM of the
taxpayer's four Modelo 111 quarterly filings — a ``source = "relation_prefill"``
aggregation entirely independent of the per-perceptor-clave
:class:`~domain.calculations.registry.WithholdingObservation` detail (the
AEAT Diseño de Registros type-2 "registro de perceptor" rows, ``source =
"withholding"``) that materialises the ``modelo-190-perceptor-row-*`` bindings
and the distinct-percepción count (``decl.total-percepciones``).

Nothing in the registry cross-checks that these two independently-sourced
totals agree: the M111-quarterly path could produce one figure while the
per-perceptor detail (the row-level breakdown an operator or AEAT audit would
actually reconstruct the resumen from) sums to a different figure, and
today's engine would silently accept both without complaint
(``no-silent-under-declaration``).

This module drives the REAL registry-loaded Modelo 190 ``2024-y-siguientes``
snapshot and the REAL engine (``calculate_registry_snapshot``, no mocks) to
prove :func:`~domain.calculations.registry.compute_withholding_totals_parity`
against genuine engine output: a consistent per-perceptor set (rows sum to the
engine-computed summary) passes, and a dropped perceptor row (the row set no
longer accounts for the full summary total) is CAUGHT with the exact delta
named, never silently accepted.

Grounding: RD 439/2007 art. 108, Orden EHA/3127/2009 art. 1 (Anexo II Tipo de
Registro 2, posiciones 82-94 percepción íntegra / 95-107 retenciones
practicadas), Orden HAC/1431/2025 art. 2, Ley 35/2006 arts. 99, 101.

See Also:
    :func:`~domain.calculations.registry.compute_withholding_totals_parity`
        Pure comparison primitive whose row-vs-summary deltas this suite
        asserts.
    :class:`~domain.calculations.registry.WithholdingTotalsParity`
        Verdict model that preserves percepciones and retenciones axes
        separately.
    :class:`~domain.calculations.registry.WithholdingObservation`
        Per-perceptor-clave row detail source for Modelo 190 bindings.
    :func:`~domain.calculations.registry.resolve_withholding_binding_values`
        Registry binding resolver that materialises withholding detail facts and
        the distinct-percepción count.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import CasillaId, validated_casilla_id
from ....core.aggregation import RetencionClave
from ....core.resources import resources
from cadrumo.domain.calculations.registry.ids import RelationId
from cadrumo.domain.calculations.registry.bindings import WithholdingObservation, compute_withholding_totals_parity, resolve_available_bound_inputs_by_casilla_id, resolve_withholding_binding_values
from cadrumo.domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from cadrumo.domain.calculations.registry.relations import materialize_relation_binding_values
from ....tests.secure_sql import isolated_runtime_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO_190 = "190"
_FILING_YEAR = 2025


_M190_PERCEPCIONES_TOTAL_CASILLA: CasillaId = validated_casilla_id("decl.percepciones-total")
_M190_RETENCIONES_TOTAL_CASILLA: CasillaId = validated_casilla_id("decl.retenciones-total")

# The nine 190<-111 annual-summary relations feeding decl.percepciones-total;
# the tenth feeds decl.retenciones-total. Values are the (arbitrary but
# distinct, per RET-1 continuity precedent) per-quarter-aggregated sums a
# taxpayer's four M111 filings would already have produced; this test's unit
# under test is the parity CHECK, not the M111->M190 relation wiring (covered
# by test_modelo_190_111_reconciliation_continuity.py), so the relation values
# are supplied directly.
_RELATION_VALUES: dict[RelationId, Decimal] = {
    "modelo-190-rel-111-trabajo-dinerario-importe-anual": Decimal("40000.00"),
    "modelo-190-rel-111-trabajo-especie-importe-anual": Decimal("5000.00"),
    "modelo-190-rel-111-actividades-dinerario-importe-anual": Decimal("0"),
    "modelo-190-rel-111-actividades-especie-importe-anual": Decimal("0"),
    "modelo-190-rel-111-premios-dinerario-importe-anual": Decimal("0"),
    "modelo-190-rel-111-premios-especie-importe-anual": Decimal("0"),
    "modelo-190-rel-111-ganancias-dinerario-importe-anual": Decimal("0"),
    "modelo-190-rel-111-ganancias-especie-importe-anual": Decimal("0"),
    "modelo-190-rel-111-derechos-imagen-importe-anual": Decimal("0"),
    "modelo-190-rel-111-retenciones-anual": Decimal("8550.00"),
}
# Sum of the ten relations above (decl.percepciones-total = sum of the first
# nine; decl.retenciones-total = copy of the tenth).
_EXPECTED_PERCEPCIONES_TOTAL = Decimal("45000.00")
_EXPECTED_RETENCIONES_TOTAL = Decimal("8550.00")

# Three per-perceptor-clave withholding detail rows (Orden EHA/3127/2009 Anexo
# II Tipo de Registro 2, posiciones 82-94 / 95-107) whose sums reproduce the
# relation-derived summary totals exactly: this is the CONSISTENT fixture.
_CONSISTENT_WITHHOLDING_OBSERVATIONS: tuple[WithholdingObservation, ...] = (
    WithholdingObservation(
        source_id="p1",
        perceptor_tax_id="11111111H",
        perceptor_legal_name="Perceptor One",
        transaction_date=date(_FILING_YEAR, 3, 15),
        clave=RetencionClave.A,
        percibido_dinerario=Decimal("25000.00"),
        retencion_practicada=Decimal("5750.00"),
    ),
    WithholdingObservation(
        source_id="p2",
        perceptor_tax_id="22222222J",
        perceptor_legal_name="Perceptor Two",
        transaction_date=date(_FILING_YEAR, 6, 1),
        clave=RetencionClave.A,
        percibido_dinerario=Decimal("15000.00"),
        percibido_especie=Decimal("5000.00"),
        retencion_practicada=Decimal("2800.00"),
    ),
)


def _calculate_190(
    *,
    relation_values: dict[RelationId, Decimal],
    withholding_observations: tuple[WithholdingObservation, ...],
):
    """Run the REAL 190 annual calculation from relations + withholding detail."""
    snapshot = resources().modelos.authority.snapshot(_MODELO_190, filing_year=_FILING_YEAR, period="0A")
    relation_binding_values = materialize_relation_binding_values(snapshot.revision, relation_values, period="0A")
    withholding_binding_values = resolve_withholding_binding_values(snapshot.revision, withholding_observations)
    binding_values = {**relation_binding_values, **withholding_binding_values}
    inputs = resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values)
    return calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        binding_values=binding_values,
        relation_values=relation_values,
        date_context={"filing_period": date(_FILING_YEAR, 12, 31)},
    )


def test_engine_computed_summary_totals_match_the_fixture_constants(tmp_path: Path) -> None:
    """Sanity anchor: the real engine reproduces the hand-derived relation sums.

    Not the parity gate itself (covered below) — this pins that the fixture's
    _EXPECTED_* constants genuinely describe what the REAL M111-relation
    aggregation formula produces, so the parity tests below are checking the
    gate against real engine output, not against a number this test author
    invented independently of the registry formula.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        result = _calculate_190(relation_values=_RELATION_VALUES, withholding_observations=())

    assert result.values[_M190_PERCEPCIONES_TOTAL_CASILLA] == _EXPECTED_PERCEPCIONES_TOTAL
    assert result.values[_M190_RETENCIONES_TOTAL_CASILLA] == _EXPECTED_RETENCIONES_TOTAL


def test_totals_parity_passes_when_perceptor_rows_reconstruct_the_summary(tmp_path: Path) -> None:
    """A complete per-perceptor row set that sums to the engine's summary totals is consistent."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        result = _calculate_190(
            relation_values=_RELATION_VALUES,
            withholding_observations=_CONSISTENT_WITHHOLDING_OBSERVATIONS,
        )

    parity = compute_withholding_totals_parity(
        _CONSISTENT_WITHHOLDING_OBSERVATIONS,
        percepciones_summary_total=result.values[_M190_PERCEPCIONES_TOTAL_CASILLA],
        retenciones_summary_total=result.values[_M190_RETENCIONES_TOTAL_CASILLA],
    )

    assert parity.is_consistent
    assert parity.percepciones_delta == Decimal("0.00")
    assert parity.retenciones_delta == Decimal("0.00")
    assert parity.row_count == 2
    assert parity.percepciones_row_total == _EXPECTED_PERCEPCIONES_TOTAL
    assert parity.retenciones_row_total == _EXPECTED_RETENCIONES_TOTAL


def test_totals_parity_catches_a_dropped_perceptor_row(tmp_path: Path) -> None:
    """Dropping one perceptor's row under-declares the row-level total below the
    resumen summary casilla, and the parity gate names the exact delta.

    Grounded regression for the totals-parity gap: prior to this gate, the
    engine's summary casillas were computed purely from the M111-relation
    path and NEVER cross-checked against the per-perceptor detail, so a
    withholding-store row silently dropped from the operator's per-perceptor
    entry (a data-loss bug, an incomplete import, or a tampered payroll
    export) produced no finding at all.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        # Same real engine calculation (same summary totals) as the consistent
        # case, but the withholding detail omits Perceptor Two entirely.
        result = _calculate_190(relation_values=_RELATION_VALUES, withholding_observations=())
        incomplete_rows = _CONSISTENT_WITHHOLDING_OBSERVATIONS[:1]

    parity = compute_withholding_totals_parity(
        incomplete_rows,
        percepciones_summary_total=result.values[_M190_PERCEPCIONES_TOTAL_CASILLA],
        retenciones_summary_total=result.values[_M190_RETENCIONES_TOTAL_CASILLA],
    )

    assert not parity.is_consistent
    # Missing perceptor two: percibido 15000.00 + 5000.00 = 20000.00 under-declared.
    assert parity.percepciones_delta == Decimal("-20000.00")
    # Missing perceptor two: retención 2800.00 under-declared.
    assert parity.retenciones_delta == Decimal("-2800.00")
    assert parity.row_count == 1


def test_totals_parity_default_is_exact_equality_not_a_hardcoded_cent() -> None:
    """The DEFAULT tolerance is exact equality, and a genuine one-cent gap is caught by it.

    Modelo 190's own 2025 revision publishes an EXACT (``0.00``) verification
    tolerance -- pinned against the live registry below so this proof cannot
    silently drift -- so a caller that forgets to resolve and pass
    ``snapshot.verification_policy().tolerance`` must not have a one-cent gap
    silently absorbed by this function's own default. A prior version of this
    default was a hardcoded cent that would have masked exactly this gap.
    """
    published = (
        resources()
        .modelos.authority.snapshot(_MODELO_190, filing_year=_FILING_YEAR, period="0A")
        .verification_policy()
        .tolerance
    )
    assert published == Decimal("0"), "test precondition: modelo 190 2025 must publish exact equality"

    one_cent_off = compute_withholding_totals_parity(
        _CONSISTENT_WITHHOLDING_OBSERVATIONS,
        percepciones_summary_total=_EXPECTED_PERCEPCIONES_TOTAL + Decimal("0.01"),
        retenciones_summary_total=_EXPECTED_RETENCIONES_TOTAL,
    )
    assert not one_cent_off.is_consistent, "the default must not silently absorb a genuine one-cent divergence"
    assert one_cent_off.percepciones_delta == Decimal("-0.01")


def test_totals_parity_tolerance_absorbs_sub_cent_rounding_only() -> None:
    """A one-cent delta is within an EXPLICITLY PASSED tolerance; a two-cent delta is not.

    Pure unit-level boundary check on the comparison primitive itself
    (no engine dependency) — the tolerance is symmetric and exclusive of the
    boundary+epsilon. Passed explicitly rather than relied on as a default,
    because the registry (not this test) is the authority for what value a
    real caller resolves.
    """
    within_tolerance = compute_withholding_totals_parity(
        _CONSISTENT_WITHHOLDING_OBSERVATIONS,
        percepciones_summary_total=_EXPECTED_PERCEPCIONES_TOTAL + Decimal("0.01"),
        retenciones_summary_total=_EXPECTED_RETENCIONES_TOTAL,
        tolerance=Decimal("0.01"),
    )
    assert within_tolerance.is_consistent

    beyond_tolerance = compute_withholding_totals_parity(
        _CONSISTENT_WITHHOLDING_OBSERVATIONS,
        percepciones_summary_total=_EXPECTED_PERCEPCIONES_TOTAL + Decimal("0.02"),
        retenciones_summary_total=_EXPECTED_RETENCIONES_TOTAL,
        tolerance=Decimal("0.01"),
    )
    assert not beyond_tolerance.is_consistent
    assert beyond_tolerance.percepciones_delta == Decimal("-0.02")


def test_totals_parity_over_empty_observations_reports_full_shortfall() -> None:
    """No persisted per-perceptor detail at all is a full shortfall, not a vacuous pass.

    A nil-percepciones filer legitimately has zero rows AND a zero summary
    total (RET-1 empty-store ruling); this test pins that when the summary
    total is nonzero but the row set is empty, the gate reports the entire
    summary amount as the delta rather than silently treating "no rows" as
    "nothing to check".
    """
    parity = compute_withholding_totals_parity(
        (),
        percepciones_summary_total=_EXPECTED_PERCEPCIONES_TOTAL,
        retenciones_summary_total=_EXPECTED_RETENCIONES_TOTAL,
    )

    assert not parity.is_consistent
    assert parity.row_count == 0
    assert parity.percepciones_row_total == Decimal("0")
    assert parity.percepciones_delta == -_EXPECTED_PERCEPCIONES_TOTAL
    assert parity.retenciones_delta == -_EXPECTED_RETENCIONES_TOTAL
