"""Modelo 200 pyme bracket temporal coverage regression.

LIS Art. 29 pyme/micro-empresa rates apply across the full
``2024-y-siguientes`` revision date range (2024-01-01 onward).  An
earlier ``is.modelo-200.tipo-gravamen-pyme`` bracket table had windows
only from 2025-01-01, so any 2024 filing_period raised a
``bracket_no_window`` runtime error; the table now carries the 2024
window and this gate locks it.

Two invariants are pinned here:

1. A Modelo 200 cuota calculation for a 2024 fiscal year with a pyme-form
   (``sl``) profile resolves without raising ``bracket_no_window`` — the
   2024 window at 23 % is present and the formula executes cleanly.

2. The ``validate_bracket_table_temporal_coverage`` validator fires on a
   deliberately gapped parameter fixture, confirming the detection logic is
   not tautological: removing the check leaves the coverage gap silent.

R8-M200-1 regression: casilla DP200014:00562 classification fix
---------------------------------------------------------------

Before this fix the TOML for ``DP200014:00562`` declared
``input_kind = "manual"`` and ``required = true`` even though the formula
``modelo-200-cuota-integra`` computes it from the base imponible.  This
caused ``verify_modelo_revision`` to demand the cuota íntegra as a
user-supplied input, making every S.A. (and SL, etc.) M200 filing refuse
VERIFICADO_COMPLETO with a spurious MISSING_REQUIRED_CASILLA finding.

Three invariants are pinned here:

3. The registry snapshot declares ``DP200014:00562`` as
   ``input_kind = "computed"`` and ``required = False`` — confirming the
   TOML reclassification landed and the schema parsed it correctly.

4. ``calculate_registry_snapshot`` emits ``DP200014:00562`` in
   ``result.values`` WITHOUT the caller supplying it in ``inputs`` —
   confirming the formula engine owns the value, not the operator.

5. Anti-tautology: casilla ``00501`` (base para la liquidación) is still
   ``input_kind = "manual"`` and ``required = True`` in the same snapshot
   — confirming the classification machinery discriminates correctly and
   that invariants 3-4 are not vacuous.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core import CasillaId, RegistryAuthorityGrade, validated_casilla_id
from .._formula_runtime import calculate_registry_snapshot
from .._schema import InputKind, ParameterDefinition
from .._validate_revision_rules import _bracket_coverage_gaps
from ._registry_schema_support import _committed_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_DISPATCH_BINDING = "modelo-200-2024-profile-legal-entity-form"
_M200_RESULTADO_CONTABLE_CASILLA: CasillaId = validated_casilla_id("00501", surface="_M200_RESULTADO_CONTABLE_CASILLA")
_M200_DEDUCCION_DOBLE_IMPOSICION_CASILLA: CasillaId = validated_casilla_id(
    "DP200014:01033",
    surface="_M200_DEDUCCION_DOBLE_IMPOSICION_CASILLA",
)
_M200_BONIFICACIONES_CASILLA: CasillaId = validated_casilla_id("DP200014:01034", surface="_M200_BONIFICACIONES_CASILLA")
_M200_CUOTA_LIQUIDA_POSITIVA_CASILLA: CasillaId = validated_casilla_id(
    "DP200014B:01766",
    surface="_M200_CUOTA_LIQUIDA_POSITIVA_CASILLA",
)
_M200_CUOTA_LIQUIDA_NEGATIVA_CASILLA: CasillaId = validated_casilla_id(
    "DP200014B:01784",
    surface="_M200_CUOTA_LIQUIDA_NEGATIVA_CASILLA",
)
_M200_CUOTA_INTEGRA_CASILLA: CasillaId = validated_casilla_id("DP200014:00562", surface="_M200_CUOTA_INTEGRA_CASILLA")


def _base_inputs(base: Decimal) -> dict[CasillaId, Decimal]:
    return {
        _M200_RESULTADO_CONTABLE_CASILLA: base,
        _M200_DEDUCCION_DOBLE_IMPOSICION_CASILLA: Decimal("0"),
        _M200_BONIFICACIONES_CASILLA: Decimal("0"),
        _M200_CUOTA_LIQUIDA_POSITIVA_CASILLA: Decimal("0"),
        _M200_CUOTA_LIQUIDA_NEGATIVA_CASILLA: Decimal("0"),
    }


def _snapshot_2024():
    return _committed_snapshot("200", 2025, "0A", grade=RegistryAuthorityGrade.CALCULATION)


# ---------------------------------------------------------------------------
# 1. 2024 pyme filing resolves without bracket_no_window
# ---------------------------------------------------------------------------


def test_pyme_sl_2024_cuota_resolves_without_bracket_no_window() -> None:
    """A 2024 IS filing for an SL (pyme/micro-empresa profile) must not raise.

    Before the contract backfill the ``is.modelo-200.tipo-gravamen-pyme``
    bracket table had no window for dates in 2024, so
    ``_formula_runtime.apply_bracket_table`` raised
    ``bracket_no_window``.  The 2024 bracket at 23 % (LIS Art. 29
    pre-2025 pyme flat rate) must now exist and the cuota calculation
    must complete without error.
    """
    from .._formula_runtime import calculate_registry_snapshot

    # The micro-empresa lane applies when INCN < 1.000.000 EUR (LIS Art. 29.1).
    # Supply INCN = 500.000 EUR to route through the pyme bracket table.
    # Base imponible 00552 = 100.000 EUR; casilla 01330 (post-nivelación base)
    # equals 00552 when nivelación corrections 01033/01034 are zero.
    result = calculate_registry_snapshot(
        _snapshot_2024(),
        # 00552 is now computed; feed resultado contable 00501 with zero
        # corrections/reserva/BIN so the chain computes 00552 = 100.000.
        inputs=_base_inputs(Decimal("100000")),
        enum_binding_values={_DISPATCH_BINDING: "sl"},
        binding_values={
            "modelo-200-2024-profile-new-entity-flag": Decimal("0"),
            # INCN below 1.000.000 EUR → micro-empresa lane → tipo-gravamen-pyme bracket
            "modelo-200-2024-profile-incn-prior-12-months": Decimal("500000"),
            "modelo-200-2024-profile-tributacion-estado-porcentaje": Decimal("100"),
            "modelo-200-2024-bin-pendiente-ejercicios-anteriores": Decimal("0"),
            "modelo-200-2024-dotaciones-deterioro-creditos-saldo-no-cumplido-anteriores": Decimal("0"),
            "modelo-200-2024-dotaciones-deterioro-creditos-saldo-cumplido-anteriores": Decimal("0"),
        },
        relation_values={
            "modelo-200-2024-rel-202-pagos-fraccionados": Decimal("0"),
            "modelo-200-2024-rel-202-pagos-fraccionados-40-2": Decimal("0"),
        },
        date_context={"filing_period": date(2024, 12, 31)},
    )
    # The cuota íntegra for a micro-empresa SL at the 2024 flat pyme rate
    # (23 %, LIS Art. 29 pre-2025 regime) on a 100.000 EUR base must be
    # 23.000 EUR.  External authority: LIS Art. 29 (BOE-A-2014-12328) as
    # in force for ejercicios iniciados en 2024; AEAT Manual de
    # Sociedades "Tipos de gravamen" 2024.
    assert result.values[_M200_CUOTA_INTEGRA_CASILLA] == Decimal("23000.00"), (
        "cuota íntegra for micro-empresa SL on 100.000 EUR base at 23 % must be 23.000 EUR"
    )


def test_pyme_bracket_2024_window_is_present_in_registry() -> None:
    """The 2024 pyme bracket window exists at 23 % in the registry.

    After the contract backfill ``is.modelo-200.tipo-gravamen-pyme`` must carry a
    window covering 2024-01-01 to 2024-12-31 with ``marginal_rate = 0.23``.
    This tests the registry encoding directly against the LIS Art. 29 2024
    authority; it is not a recomputation of the formula.
    """
    parameters = {p.id: p for p in _snapshot_2024().revision.parameters}
    parameter = parameters["is.modelo-200.tipo-gravamen-pyme"]
    brackets_2024 = [b for b in parameter.brackets if b.valid_from == date(2024, 1, 1)]
    assert brackets_2024, "is.modelo-200.tipo-gravamen-pyme must have at least one bracket for 2024-01-01"
    # The 2024 flat rate was 23 % (pre-tranche regime).
    assert any(b.marginal_rate == Decimal("0.23") for b in brackets_2024), (
        "2024 bracket must carry the LIS Art. 29 pre-2025 pyme flat rate of 23 %"
    )


# ---------------------------------------------------------------------------
# 2. Coverage-gap validator anti-tautology probe
# ---------------------------------------------------------------------------


def test_coverage_validator_fires_on_deliberate_gap() -> None:
    """``_bracket_coverage_gaps`` catches a gap in a fixture parameter.

    This is an anti-tautology probe: if the gap detector never fires the contract
    regression test cannot distinguish a silent gap from a covered one.
    A ``ParameterDefinition`` fixture is constructed with ``bracket_axis =
    "filing_period"`` and brackets covering only 2025-01-01 onward — matching
    the exact pre-backfill state that was the original bug.  The detector must
    return at least one gap tuple and that gap must start at 2024-01-01.

    ``model_construct`` bypasses pydantic validation so the fixture can carry
    minimal fields without satisfying the production non-empty ref constraints.
    """
    from .._schema import BracketEntry

    bracket_2025 = BracketEntry(
        lower_bound=Decimal("0"),
        fixed_addition=Decimal("0"),
        marginal_rate=Decimal("0.17"),
        valid_from=date(2025, 1, 1),
        valid_to=date(2025, 12, 31),
    )
    gapped_parameter = ParameterDefinition.model_construct(
        id="test.gapped-bracket-table",
        data_type="bracket_table",
        unit="EUR",
        bracket_axis="filing_period",
        brackets=(bracket_2025,),
        values=(),
    )

    gaps = _bracket_coverage_gaps(
        gapped_parameter,
        revision_from=date(2024, 1, 1),
        revision_to=date(2024, 12, 31),
    )
    assert gaps, "_bracket_coverage_gaps must detect the 2024 gap when brackets start at 2025"
    assert gaps[0][0] == date(2024, 1, 1), "gap must start at the revision's valid_from (2024-01-01)"


def test_coverage_validator_passes_when_no_gap() -> None:
    """The validator must not flag a fully covered parameter as gapped.

    A ``bracket_table`` parameter whose windows start at ``revision_from``
    and extend to ``revision_to`` without interruption must produce zero
    failures.  This guards against false positives in the coverage check.
    """
    from .._schema import BracketEntry

    bracket_2024 = BracketEntry(
        lower_bound=Decimal("0"),
        fixed_addition=Decimal("0"),
        marginal_rate=Decimal("0.23"),
        valid_from=date(2024, 1, 1),
        valid_to=date(2024, 12, 31),
    )
    bracket_2025 = BracketEntry(
        lower_bound=Decimal("0"),
        fixed_addition=Decimal("0"),
        marginal_rate=Decimal("0.17"),
        valid_from=date(2025, 1, 1),
        valid_to=date(2025, 12, 31),
    )
    covered_parameter = ParameterDefinition.model_construct(
        id="test.covered-bracket-table",
        data_type="bracket_table",
        unit="EUR",
        bracket_axis="filing_period",
        brackets=(bracket_2024, bracket_2025),
        values=(),
    )

    gaps = _bracket_coverage_gaps(
        covered_parameter,
        revision_from=date(2024, 1, 1),
        revision_to=date(2025, 12, 31),
    )
    assert not gaps, "_bracket_coverage_gaps must not flag a parameter whose windows cover the full revision range"


# ---------------------------------------------------------------------------
# 3. R8-M200-1 regression: DP200014:00562 classification (R8-M200-1)
# ---------------------------------------------------------------------------


def test_cuota_integra_casilla_is_classified_computed_not_manual() -> None:
    """DP200014:00562 must be classified as computed=true, required=false in the registry.

    Before R8-M200-1 the TOML declared ``input_kind = "manual"`` and
    ``required = true``, causing ``verify_modelo_revision`` to demand the
    cuota íntegra as a user-supplied input.  After the fix the casilla must
    carry ``input_kind = "computed"`` and ``required = False`` so the
    verification layer never blocks on it.

    This tests the registry encoding directly (no formula execution) and
    would fail against the pre-fix TOML regardless of test ordering.
    """
    parameters_by_id = {c.id: c for c in _snapshot_2024().revision.casillas}
    casilla = parameters_by_id.get(_M200_CUOTA_INTEGRA_CASILLA)
    assert casilla is not None, "DP200014:00562 must be declared in the 2024-y-siguientes revision"
    assert casilla.input_kind == InputKind.COMPUTED, (
        "DP200014:00562 must be input_kind='computed'; formula modelo-200-cuota-integra owns the value"
    )
    assert casilla.required is False, (
        "DP200014:00562 must be required=false; the engine computes it — the operator never supplies it directly"
    )


def test_cuota_integra_is_emitted_by_engine_without_user_input() -> None:
    """calculate_registry_snapshot emits DP200014:00562 without it appearing in inputs.

    The formula ``modelo-200-cuota-integra`` must produce the cuota íntegra
    from the post-nivelación base imponible.  If the caller did NOT supply
    ``DP200014:00562`` in ``inputs`` and the value is still present in
    ``result.values`` the formula engine owns the casilla correctly.

    Failure mode: if the TOML misclassification is reverted (manual+required)
    the engine would no longer compute this casilla and it would either be
    absent from ``result.values`` or the engine would raise because a manual
    casilla has no supplied value.
    """
    inputs_without_00562 = {
        # 00552 is now computed; feed resultado contable 00501 (zero
        # correcciones/reserva/BIN) so the chain computes 00552 = 200.000.
        **_base_inputs(Decimal("200000")),
    }
    assert _M200_CUOTA_INTEGRA_CASILLA not in inputs_without_00562, (
        "Test fixture must NOT supply DP200014:00562 — the whole point is that "
        "the engine must produce it without operator input"
    )

    result = calculate_registry_snapshot(
        _snapshot_2024(),
        inputs=inputs_without_00562,
        enum_binding_values={_DISPATCH_BINDING: "sa"},
        binding_values={
            "modelo-200-2024-profile-new-entity-flag": Decimal("0"),
            "modelo-200-2024-profile-incn-prior-12-months": Decimal("5000000"),
            "modelo-200-2024-profile-tributacion-estado-porcentaje": Decimal("100"),
            "modelo-200-2024-bin-pendiente-ejercicios-anteriores": Decimal("0"),
            "modelo-200-2024-dotaciones-deterioro-creditos-saldo-no-cumplido-anteriores": Decimal("0"),
            "modelo-200-2024-dotaciones-deterioro-creditos-saldo-cumplido-anteriores": Decimal("0"),
        },
        relation_values={
            "modelo-200-2024-rel-202-pagos-fraccionados": Decimal("0"),
            "modelo-200-2024-rel-202-pagos-fraccionados-40-2": Decimal("0"),
        },
        date_context={"filing_period": date(2024, 12, 31)},
    )
    assert _M200_CUOTA_INTEGRA_CASILLA in result.values, (
        "formula engine must emit DP200014:00562 in result.values; "
        "if absent the formula graph is not wired correctly after TOML fix"
    )
    # S.A. (gran empresa, INCN ≥ 1.000.000 EUR) pays 25 % on 200.000 EUR base.
    # Authority: LIS Art. 29.1 (BOE-A-2014-12328) general rate for 2024.
    assert result.values[_M200_CUOTA_INTEGRA_CASILLA] == Decimal("50000.00"), (
        "cuota íntegra for S.A. at LIS Art. 29.1 general rate (25 %) on 200.000 EUR base must be 50.000 EUR"
    )


def test_cuota_integra_antitautology_manual_casilla_still_required() -> None:
    """Anti-tautology: casilla 00501 (base pérdidas y ganancias) remains manual+required.

    If the registry classification machinery were broken — e.g., every
    casilla silently defaulted to ``input_kind = "computed"`` — the invariant
    in ``test_cuota_integra_casilla_is_classified_computed_not_manual`` would
    pass vacuously.  This probe verifies that a genuinely-manual required
    casilla (``00501``, the pre-tax P&L result that operators must enter
    from their accounts) still carries ``input_kind = "manual"`` and
    ``required = True`` in the same snapshot.

    If this test fails the classification machinery is broken and the
    compute/manual distinction is unreliable across the entire revision.
    """
    parameters_by_id = {c.id: c for c in _snapshot_2024().revision.casillas}
    casilla = parameters_by_id.get(_M200_RESULTADO_CONTABLE_CASILLA)
    assert casilla is not None, (
        "00501 must be declared in the 2024-y-siguientes revision; "
        "if absent the snapshot failed to load the casilla TOML cluster"
    )
    assert casilla.input_kind == InputKind.MANUAL, (
        "00501 (resultado cuenta pérdidas y ganancias) must remain input_kind='manual'; "
        "this is an operator-supplied figure from the company's accounts"
    )
    assert casilla.required is True, "00501 must remain required=true; the verify layer must still block on its absence"
