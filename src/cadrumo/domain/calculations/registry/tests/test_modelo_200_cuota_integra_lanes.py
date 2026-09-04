"""Modelo 200 cuota-integra lanes — oracle-grounded and structural tests.

The Modelo 200 cuota-integra formula (``DP200014:00562``) now applies
the LIS Art. 29 tipo de gravamen as a tranche / sub-form table through
``lookup_bracket_by_entity_type``. Four lanes coexist:

1. **General sub-form**: post-nivelación base x 25% (LIS Art. 29.1, default rate).
2. **Micro-empresa**: transitional bracket scale 21/22 (2025) or 19/21 (2026) on the
   first 50.000 € tranche and rest, when INCN of the prior 12 months
   is below 1.000.000 € (LIS Art. 29.1 par. 1; AEAT Manual de Sociedades
   "Tipos de gravamen vigentes" / AEAT folleto actividades económicas 4.3).
3. **Art.101 ERD**: scalar DT 44ª transition 24/23/22/21 for entities
   below 10.000.000 € INCN and outside the micro-empresa lane.
4. **New-entity override**: 15% rate for the first two profit-making
   periods (LIS Art. 29 par. 4), regardless of sub-form.

These tests pin the lane behaviour and the Modelo 202 modality gate.
Numeric oracles are taken from the AEAT Manual práctico de Sociedades
2024 worked example (page 401) where available; for lanes whose
worked-example publication is not directly cited the tests assert
structural relations (ordering between lanes, anchor-band lower
bounds) rather than recomputing the registry tranche.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.authority_grade import RegistryAuthorityGrade
from .....core.casilla_id import CasillaId, validated_casilla_id
from ....deadlines.models import IVARegime, TaxpayerProfile
from ....contribuyente.entity_type import EntityType, LegalEntityForm
from ..applicability_modelo202 import Modelo202Modality, derive_modelo_202_modality
from ..formula_runtime import calculate_registry_snapshot
from ._registry_schema_support import _committed_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_FORM_BINDING = "modelo-200-2024-profile-legal-entity-form"
_NEW_ENTITY_BINDING = "modelo-200-2024-profile-new-entity-flag"
_INCN_BINDING = "modelo-200-2024-profile-incn-prior-12-months"
_ESTADO_PCT_BINDING = "modelo-200-2024-profile-tributacion-estado-porcentaje"
_M200_RESULTADO_CONTABLE_CASILLA: CasillaId = validated_casilla_id("00501", surface="_M200_RESULTADO_CONTABLE_CASILLA")
_M200_CORRECCIONES_AUMENTO_CASILLA: CasillaId = validated_casilla_id(
    "DP200013:00417",
    surface="_M200_CORRECCIONES_AUMENTO_CASILLA",
)
_M200_CORRECCIONES_DISMINUCION_CASILLA: CasillaId = validated_casilla_id(
    "DP200013:00418",
    surface="_M200_CORRECCIONES_DISMINUCION_CASILLA",
)
_M200_RESERVA_CAPITALIZACION_CASILLA: CasillaId = validated_casilla_id(
    "01032",
    surface="_M200_RESERVA_CAPITALIZACION_CASILLA",
)
_M200_BIN_APLICADA_CASILLA: CasillaId = validated_casilla_id("DP200014:00547", surface="_M200_BIN_APLICADA_CASILLA")
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
_M200_CUOTA_EJERCICIO_CASILLA: CasillaId = validated_casilla_id(
    "DP200014B:00599",
    surface="_M200_CUOTA_EJERCICIO_CASILLA",
)


def _snapshot():
    return _committed_snapshot("200", 2025, "0A", grade=RegistryAuthorityGrade.CALCULATION)


def _cuota_for(
    *,
    base: Decimal,
    form: str,
    new_entity: Decimal,
    incn: Decimal,
    filing_period: date = date(2024, 12, 31),
) -> Decimal:
    result = calculate_registry_snapshot(
        _snapshot(),
        inputs={
            # 00552 is computed: max(00550 - 01032 - 00547, 0); 00550 is
            # computed: 00501 + DP200013:00417 - DP200013:00418. Supply the
            # leaf operator-input casillas (00501 resultado contable + zero
            # corrections + zero reserva + zero BIN aplicada) so the chain
            # computes 00552 = base.
            _M200_RESULTADO_CONTABLE_CASILLA: base,
            _M200_CORRECCIONES_AUMENTO_CASILLA: Decimal("0"),
            _M200_CORRECCIONES_DISMINUCION_CASILLA: Decimal("0"),
            _M200_RESERVA_CAPITALIZACION_CASILLA: Decimal("0"),
            _M200_BIN_APLICADA_CASILLA: Decimal("0"),
            _M200_DEDUCCION_DOBLE_IMPOSICION_CASILLA: Decimal("0"),
            _M200_BONIFICACIONES_CASILLA: Decimal("0"),
            _M200_CUOTA_LIQUIDA_POSITIVA_CASILLA: Decimal("0"),
            _M200_CUOTA_LIQUIDA_NEGATIVA_CASILLA: Decimal("0"),
        },
        enum_binding_values={_FORM_BINDING: form},
        binding_values={
            _NEW_ENTITY_BINDING: new_entity,
            _INCN_BINDING: incn,
            _ESTADO_PCT_BINDING: Decimal("100"),
            # BIN-pendiente fresh-filer baseline: previous_filing binding
            # for casilla 00670 resolves to zero with no prior filing.
            "modelo-200-2024-bin-pendiente-ejercicios-anteriores": Decimal("0"),
            "modelo-200-2024-dotaciones-deterioro-creditos-saldo-no-cumplido-anteriores": Decimal("0"),
            "modelo-200-2024-dotaciones-deterioro-creditos-saldo-cumplido-anteriores": Decimal("0"),
        },
        relation_values={
            "modelo-200-2024-rel-202-pagos-fraccionados": Decimal("0"),
            "modelo-200-2024-rel-202-pagos-fraccionados-40-2": Decimal("0"),
        },
        date_context={"filing_period": filing_period},
    )
    return result.values[_M200_CUOTA_INTEGRA_CASILLA]


# ---------------------------------------------------------------------
# Lane 3 — general sub-form (AEAT Manual de Sociedades 2024, page 401)
# ---------------------------------------------------------------------


def test_general_entity_cuota_matches_aeat_manual_worked_example_page_401() -> None:
    """A sociedad limitada at 25% on a 1.000.000 base yields the AEAT manual oracle.

    The Manual práctico de Sociedades 2024 worked example on page 401
    (Liquidación del IS 2024 sin tributación mínima) publishes a base
    imponible después de la reserva de nivelación 01330 of 1.000.000
    yielding a cuota íntegra 00562 of 250.000 at the LIS Art. 29
    general rate (25%). The figure is lifted verbatim from the manual,
    not recomputed by the test author.

    INCN is supplied above the 1.000.000 € micro-empresa threshold so
    the formula routes the sub-form lane, not the pyme lane.
    """
    cuota = _cuota_for(
        base=Decimal("1000000"),
        form="sl",
        new_entity=Decimal("0"),
        incn=Decimal("10000000"),
    )
    assert cuota == Decimal("250000.00"), (
        "cuota íntegra at the LIS Art. 29 general 25% rate must equal "
        "the AEAT Manual de Sociedades 2024 worked-example oracle of "
        "250.000 (page 401)"
    )


def test_cooperativa_takes_the_lis_art_29_protected_rate() -> None:
    """A cooperativa fiscalmente protegida is taxed at the LIS Art. 29 20% rate.

    LIS Art. 29.2 (BOE-A-2014-12328) sets the rate for cooperativas
    fiscalmente protegidas at 20% (and the general activities of these
    cooperativas remain at 25% — out of scope here). The dispatch must
    route a cooperativa profile to the protected-rate bracket; the
    expected cuota for a 1.000.000 base is 200.000, derived from the
    BOE-published LIS Art. 29.2 rate the registry encodes.
    """
    cuota = _cuota_for(
        base=Decimal("1000000"),
        form="cooperativa",
        new_entity=Decimal("0"),
        incn=Decimal("10000000"),
    )
    assert cuota == Decimal("200000.00"), (
        "cuota íntegra at the LIS Art. 29.2 cooperativa protected 20% rate must equal 200.000 for a 1.000.000 base"
    )


def test_non_profit_takes_the_ley_49_2002_special_regime_rate() -> None:
    """An entidad sin fines lucrativos is taxed at the Ley 49/2002 10% special rate.

    LIS Art. 29.4 (BOE-A-2014-12328) plus the Ley 49/2002 régimen
    fiscal especial sets the rate for entidades sin fines lucrativos
    parcialmente exentas at 10%. The dispatch must route a non-profit
    profile to that bracket; for a 1.000.000 base the cuota is 100.000
    per the BOE-published 10% rate the registry encodes.
    """
    cuota = _cuota_for(
        base=Decimal("1000000"),
        form="sin_fines_lucrativos",
        new_entity=Decimal("0"),
        incn=Decimal("10000000"),
    )
    assert cuota == Decimal("100000.00")


# ---------------------------------------------------------------------
# Lane 2 — micro-empresa (LIS Art. 29.1; AEAT folleto 4.3)
# ---------------------------------------------------------------------


def test_micro_empresa_cuota_is_less_than_general_cuota_at_same_base() -> None:
    """A micro-empresa base resolves through the lower-rate pyme tranche scale.

    LIS DT 44ª sets the 2025 transitional micro-empresa tranche rates
    below the general 25% — 21%/22% for periods initiated in 2025 (AEAT
    Manual de Sociedades "Tipos de gravamen vigentes"; AEAT folleto
    actividades económicas 4.3). A profile whose prior-12-months INCN
    is below the 1.000.000 € threshold must therefore produce a cuota
    strictly less than the general-lane cuota for the same base.

    This is a structural-ordering assertion grounded in the AEAT
    publication's rate-ordering claim ("rates below the general
    rate"), not a recomputation of the tranche arithmetic.
    """
    base = Decimal("1000000")
    filing_period_2025 = date(2025, 12, 31)
    general = _cuota_for(
        base=base,
        form="sl",
        new_entity=Decimal("0"),
        incn=Decimal("10000000"),
        filing_period=filing_period_2025,
    )
    pyme = _cuota_for(
        base=base,
        form="sl",
        new_entity=Decimal("0"),
        incn=Decimal("500000"),
        filing_period=filing_period_2025,
    )
    assert pyme < general, (
        "micro-empresa cuota must be strictly less than the general 25% "
        "cuota — LIS DT 44ª micro-empresa rates (21/22 %) sit "
        "below the LIS Art. 29 general 25% rate"
    )


def test_micro_empresa_lane_anchor_at_50000_eur_first_tranche_boundary() -> None:
    """At base = 50.000 the micro-empresa cuota follows the binding year schedule.

    For INCN < 1.000.000 € the cuota integra (casilla 00562) is routed
    through ``modelo-200-cuota-integra`` against the year-segmented
    ``is.modelo-200.tipo-gravamen-pyme`` bracket, whose
    ``filing_period`` axis selects the binding rate per ejercicio:

    - **2024**: flat 23 % (Ley 31/2022 Art. 39, reduced rate for
      INCN < 1M). 50.000 × 23 % = **11.500 €**.
    - **2025**: 21 % on 0-50.000, 22 % on the rest (LIS **disposición
      transitoria 44ª**, added by Ley 7/2024 — BOE-A-2024-26694; the
      transitional micro-empresa scale over LIS Art. 29.1).
      50.000 × 21 % = **10.500 €**.

    These are the AEAT-published transitional anchors (sede AEAT,
    "Tipo de gravamen y cuota íntegra"), not test-author figures: the
    21 % first-tranche rate for 2025 appears verbatim in LIS DT 44ª.
    The 8.500 € (17 %) figure is the *final* régimen rate, not the 2025
    transitional one, and is not in force for ejercicio 2025.
    """
    base = Decimal("50000")
    pyme_2024 = _cuota_for(
        base=base,
        form="sl",
        new_entity=Decimal("0"),
        incn=Decimal("500000"),
        filing_period=date(2024, 12, 31),
    )
    assert pyme_2024 == Decimal("11500.00"), (
        "cuota at the 50.000 € tranche for 2024 must equal the Ley 31/2022 "
        "Art. 39 reduced rate (23 % on 0-1.000.000 INCN)"
    )

    pyme_2025 = _cuota_for(
        base=base,
        form="sl",
        new_entity=Decimal("0"),
        incn=Decimal("500000"),
        filing_period=date(2025, 12, 31),
    )
    assert pyme_2025 == Decimal("10500.00"), (
        "cuota at the 50.000 € tranche boundary for 2025 must equal the "
        "LIS DT 44ª transitional micro-empresa first-tranche rate "
        "(21 % on 0-50.000 → 10.500), not the final-régimen 17 % (8.500) "
        "nor the flat 23 % (11.500)"
    )


# ---------------------------------------------------------------------
# Lane 2b — art.101 ERD (LIS DT 44ª)
# ---------------------------------------------------------------------


def test_art101_erd_lane_applies_dt44_2025_rate_below_10m() -> None:
    """An art.101 ERD profile reaches the 2025 DT 44ª 24% rate.

    LIS art. 101 covers entities whose prior-period INCN is below
    10.000.000 EUR. LIS DT 44ª fixes those entities at 24% for periods
    initiated in 2025 unless a different special rate applies. A base
    of 1.000.000 with prior-period INCN 7.000.000 therefore yields
    240.000, while the 10.000.000 boundary remains outside art.101 and
    stays on the general 25% lane.
    """
    erd = _cuota_for(
        base=Decimal("1000000"),
        form="sl",
        new_entity=Decimal("0"),
        incn=Decimal("7000000"),
        filing_period=date(2025, 12, 31),
    )
    boundary_general = _cuota_for(
        base=Decimal("1000000"),
        form="sl",
        new_entity=Decimal("0"),
        incn=Decimal("10000000"),
        filing_period=date(2025, 12, 31),
    )

    assert erd == Decimal("240000.00")
    assert boundary_general == Decimal("250000.00")


# ---------------------------------------------------------------------
# Lane 1 — new-entity 15 % override (LIS Art. 29 par. 4)
# ---------------------------------------------------------------------


def test_new_entity_override_applies_15_percent_regardless_of_subform() -> None:
    """The new-entity override resolves through the 15% bracket for every sub-form.

    LIS Art. 29 par. 4 (BOE-A-2014-12328) sets a 15% rate for entities
    in their first two profit-making periods, regardless of sub-form
    (a sociedad limitada, a cooperativa, or a non-profit alike). The
    override layers on top of the sub-form lane via the if_then_else
    predicate over ``new_entity_first_two_profit_periods``.

    For a 1.000.000 base the override cuota is 150.000 — the AEAT
    published 15% rate applied to the post-nivelación base. Asserting
    the same cuota for two distinct sub-forms verifies the override
    bypasses the sub-form dispatch.
    """
    sl_cuota = _cuota_for(
        base=Decimal("1000000"),
        form="sl",
        new_entity=Decimal("1"),
        incn=Decimal("10000000"),
    )
    coop_cuota = _cuota_for(
        base=Decimal("1000000"),
        form="cooperativa",
        new_entity=Decimal("1"),
        incn=Decimal("10000000"),
    )
    assert sl_cuota == Decimal("150000.00"), (
        "new-entity override cuota must equal LIS Art. 29 par. 4 15% "
        "applied to the post-nivelación base (1.000.000 x 15% = 150.000)"
    )
    assert sl_cuota == coop_cuota, (
        "the new-entity override must bypass the sub-form dispatch — an SL and a cooperativa both reach the 15% rate"
    )


def test_new_entity_override_takes_precedence_over_micro_empresa_lane() -> None:
    """An eligible new-entity profile takes the 15% rate even at low INCN.

    The if_then_else composition places the new-entity predicate ABOVE
    the INCN micro-empresa gate, so a profile that is both
    newly-created and below the 1.000.000 € INCN threshold still
    receives the 15% override (LIS Art. 29 par. 4 wins over LIS Art.
    29.1 par. 1, per the BOE precedence — the new-entity rate is a
    distinct rate-of-the-period, not a tranche of the micro-empresa
    scale). The override cuota equals the sub-form-agnostic 15% value.
    """
    cuota = _cuota_for(
        base=Decimal("1000000"),
        form="sl",
        new_entity=Decimal("1"),
        incn=Decimal("500000"),
    )
    assert cuota == Decimal("150000.00")


# ---------------------------------------------------------------------
# Modelo 202 modality gate (LIS Art. 40 / 40.3)
# ---------------------------------------------------------------------


def _legal_entity_profile(incn: Decimal | None) -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="B12345674",
        entity_type=EntityType.LEGAL_ENTITY,
        legal_entity_form=LegalEntityForm.SL,
        iva_regime=IVARegime.GENERAL,
        incn_prior_12_months=incn,
    )


def test_modelo_202_modality_is_art_40_3_mandatory_above_threshold() -> None:
    """A profile whose INCN exceeded 6.000.000 € reaches Art. 40.3 only.

    LIS Art. 40.3 (BOE-A-2014-12328) makes the base-imponible method
    mandatory when the importe neto de la cifra de negocios of the
    prior 12 months exceeded 6.000.000 € (AEAT "Cálculo pago
    fraccionado según la modalidad regulada en el artículo 40.3 LIS").
    Art. 40.2 is not offered for such a profile.
    """
    verdict = derive_modelo_202_modality(_legal_entity_profile(Decimal("7000000")))
    assert verdict.modality is Modelo202Modality.ART_40_3_MANDATORY
    assert "ley-27-2014:art-40-3" in verdict.legal_refs


def test_modelo_202_modality_is_art_40_2_optional_at_or_below_threshold() -> None:
    """A profile at or below the threshold reaches both modalities.

    Below the 6.000.000 € threshold Art. 40.3 ceases to be mandatory
    and Art. 40.2 (cuota method, 18 %) is the default; the rationale
    records that Art. 40.3 remains optional. The strict-equality
    behaviour at exactly 6.000.000 € reflects the BOE-A-2014-12328
    wording: Art. 40.3 mandates only when INCN "ha superado" the
    threshold — equality alone does not exceed it.
    """
    below = derive_modelo_202_modality(_legal_entity_profile(Decimal("500000")))
    at_threshold = derive_modelo_202_modality(_legal_entity_profile(Decimal("6000000")))
    assert below.modality is Modelo202Modality.ART_40_2_OPTIONAL
    assert at_threshold.modality is Modelo202Modality.ART_40_2_OPTIONAL
    assert "ley-27-2014:art-40" in below.legal_refs


def test_modelo_202_modality_is_incomplete_when_incn_undeclared() -> None:
    """An undeclared INCN yields INCOMPLETE — never a guessed modality.

    The corporate-entity design §3 safe-default constraint: the engine
    never picks Art. 40.2 or Art. 40.3 on its own when the INCN is
    not known. The operator must declare the prior-12-months INCN
    first.
    """
    verdict = derive_modelo_202_modality(_legal_entity_profile(None))
    assert verdict.modality is Modelo202Modality.INCOMPLETE
    # The verdict still carries the modality legal_refs so the operator
    # sees what they are being asked to ground their answer against.
    assert "ley-27-2014:art-40-3" in verdict.legal_refs


def test_modelo_202_modality_is_incomplete_for_non_legal_entity() -> None:
    """A natural person or attribution entity yields INCOMPLETE.

    The Modelo 202 modality only makes sense for an IS contribuyente.
    A natural person files Modelo 130 / 131 (IRPF pagos fraccionados),
    and an attribution entity files Modelo 184 — neither reaches the
    Modelo 202 modality question.
    """
    natural_person = TaxpayerProfile(
        tax_id="A45678901",
        entity_type=EntityType.NATURAL_PERSON,
        iva_regime=IVARegime.GENERAL,
        incn_prior_12_months=Decimal("9000000"),
    )
    verdict = derive_modelo_202_modality(natural_person)
    assert verdict.modality is Modelo202Modality.INCOMPLETE


# ---------------------------------------------------------------------
# Regression: tributacion_estado_porcentaje binding path
# ---------------------------------------------------------------------


def test_cuota_ejercicio_00599_is_non_zero_when_estado_porcentaje_binding_supplied() -> None:
    """DP200014B:00599 is non-zero when tributacion_estado_porcentaje = 100.

    The formula
    ``modelo-200-cuota-ejercicio-a-ingresar-devolver`` multiplies the
    cuota by ``(binding / 100)`` where the binding is
    ``modelo-200-2024-profile-tributacion-estado-porcentaje``. Without
    that binding the multiplier was 0/100 = 0, silently zeroing the
    result regardless of the supplied cuota líquida.

    This test verifies the binding path from the registry formula to
    the engine result.  The oracle values are derived from the formula
    specification: for a common-regime entity (100 %) with
    ``00592 = 20.000``, ``01766 = 0``, ``01784 = 0``, the formula
    produces ``00599 = (100/100) x 20.000 = 20.000``.  The 20.000
    figure is produced by the upstream cuota chain from an 80.000 base
    at the general 25 % rate with zero deductions, so the test does not
    bypass the formula-owned cuota líquida casilla.
    """
    result = calculate_registry_snapshot(
        _snapshot(),
        inputs={
            _M200_RESULTADO_CONTABLE_CASILLA: Decimal("80000"),
            _M200_CORRECCIONES_AUMENTO_CASILLA: Decimal("0"),
            _M200_CORRECCIONES_DISMINUCION_CASILLA: Decimal("0"),
            _M200_RESERVA_CAPITALIZACION_CASILLA: Decimal("0"),
            _M200_BIN_APLICADA_CASILLA: Decimal("0"),
            _M200_DEDUCCION_DOBLE_IMPOSICION_CASILLA: Decimal("0"),
            _M200_BONIFICACIONES_CASILLA: Decimal("0"),
            _M200_CUOTA_LIQUIDA_POSITIVA_CASILLA: Decimal("0"),
            _M200_CUOTA_LIQUIDA_NEGATIVA_CASILLA: Decimal("0"),
        },
        enum_binding_values={_FORM_BINDING: "sl"},
        binding_values={
            _NEW_ENTITY_BINDING: Decimal("0"),
            _INCN_BINDING: Decimal("10000000"),
            _ESTADO_PCT_BINDING: Decimal("100"),
            # BIN-pendiente fresh-filer baseline.
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
    cuota_ejercicio = result.values[_M200_CUOTA_EJERCICIO_CASILLA]
    assert cuota_ejercicio == Decimal("20000.00"), (
        "DP200014B:00599 must equal 20.000 when tributacion_estado_porcentaje = 100 "
        "and cuota_liquida 00592 = 20.000; the formula (100/100) x 20.000 = 20.000"
    )


def test_cuota_ejercicio_00599_raises_when_estado_porcentaje_binding_absent() -> None:
    """DP200014B:00599 raises RegistryValidationError when binding is absent.

    Without ``modelo-200-2024-profile-tributacion-estado-porcentaje``
    the formula cannot evaluate — the engine raises rather than
    silently returning zero.  This is the correct fail-loud behaviour:
    operators see a missing-binding error instead of a borrador with
    00599 = 0.
    """
    from ..errors import RegistryValidationError

    with pytest.raises(RegistryValidationError, match="has no supplied value"):
        calculate_registry_snapshot(
            _snapshot(),
            inputs={
                _M200_RESULTADO_CONTABLE_CASILLA: Decimal("80000"),
                _M200_CORRECCIONES_AUMENTO_CASILLA: Decimal("0"),
                _M200_CORRECCIONES_DISMINUCION_CASILLA: Decimal("0"),
                _M200_RESERVA_CAPITALIZACION_CASILLA: Decimal("0"),
                _M200_BIN_APLICADA_CASILLA: Decimal("0"),
                _M200_DEDUCCION_DOBLE_IMPOSICION_CASILLA: Decimal("0"),
                _M200_BONIFICACIONES_CASILLA: Decimal("0"),
                _M200_CUOTA_LIQUIDA_POSITIVA_CASILLA: Decimal("0"),
                _M200_CUOTA_LIQUIDA_NEGATIVA_CASILLA: Decimal("0"),
            },
            enum_binding_values={_FORM_BINDING: "sl"},
            binding_values={
                _NEW_ENTITY_BINDING: Decimal("0"),
                _INCN_BINDING: Decimal("10000000"),
                # _ESTADO_PCT_BINDING intentionally absent
                # BIN-pendiente fresh-filer baseline (separate gate).
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
