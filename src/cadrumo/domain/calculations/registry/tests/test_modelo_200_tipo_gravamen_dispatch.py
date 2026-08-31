"""Modelo 200 LIS Art. 29 tipo de gravamen schedule and the entity-type rate dispatch.

The Impuesto sobre Sociedades cuota íntegra (casilla 00562) applies the
LIS Art. 29 tipo de gravamen (casilla 00558) to the post-nivelación base.
Casilla 00558 is no longer typed in by hand: the
``modelo-200-tipo-gravamen-por-forma-juridica`` formula dispatches the
rate by the taxpayer's legal form through the
``lookup_parameter_by_entity_type`` op, keyed on the
``modelo-200-2024-profile-legal-entity-form`` profile binding.

Two surfaces are covered:

* The registry-encoded rate schedule against its grounding authority.
  The flat scalar rates (general 25, cooperative-protected 20,
  non-profit 10, new-entity 15) and the micro-empresa two-bracket scale
  (21/22 for periods initiated in 2025, 19/21 for 2026) are asserted
  against the LIS Art. 29 text (BOE-A-2014-12328) and the AEAT Manual de
  Sociedades "Tipos de gravamen vigentes" / AEAT folleto actividades
  económicas 4.3 — the external authority the corporate-entity design §5
  records. Asserting that the registry encodes exactly the grounded
  rates checks the registry *against* the specification; it is not a
  tautological re-application of a registry formula.

* The dispatch wiring: changing the ``legal_entity_form`` enum binding
  changes which scalar parameter casilla 00558 resolves to, and an
  unsupplied or unrecognised key fails loudly. This is graph-wiring /
  validation-error testing, explicitly permitted when no external
  numeric oracle is recomputed.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.authority_grade import RegistryAuthorityGrade
from .....core.casilla_id import CasillaId, validated_casilla_id
from .....core.resources import bundled_path
from ..binding_selector_utils import selector_as_dict
from ..errors import RegistryValidationError
from ..formula_runtime import calculate_registry_snapshot
from ..legal import verify_legal_catalogue
from ..schema_formula import ParameterDefinition
from ._registry_schema_support import _committed_modelo, _committed_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_DISPATCH_BINDING = "modelo-200-2024-profile-legal-entity-form"
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
_M200_TIPO_GRAVAMEN_CASILLA: CasillaId = validated_casilla_id("DP200014:00558", surface="_M200_TIPO_GRAVAMEN_CASILLA")
_M200_CUOTA_INTEGRA_CASILLA: CasillaId = validated_casilla_id("DP200014:00562", surface="_M200_CUOTA_INTEGRA_CASILLA")


# Both M202 pagos-fraccionados fold relations (modalidad 40.2 casilla 03 + 40.3 casilla 34)
# must be supplied to the M200 cuota-diferencial formula; default both to zero here.
_M200_PAGOS_RELATIONS_ZERO = {
    "modelo-200-2024-rel-202-pagos-fraccionados": Decimal("0"),
    "modelo-200-2024-rel-202-pagos-fraccionados-40-2": Decimal("0"),
}


def _base_inputs(base: Decimal) -> dict[CasillaId, Decimal]:
    return {
        _M200_RESULTADO_CONTABLE_CASILLA: base,
        _M200_CORRECCIONES_AUMENTO_CASILLA: Decimal("0"),
        _M200_CORRECCIONES_DISMINUCION_CASILLA: Decimal("0"),
        _M200_RESERVA_CAPITALIZACION_CASILLA: Decimal("0"),
        _M200_BIN_APLICADA_CASILLA: Decimal("0"),
        _M200_DEDUCCION_DOBLE_IMPOSICION_CASILLA: Decimal("0"),
        _M200_BONIFICACIONES_CASILLA: Decimal("0"),
        _M200_CUOTA_LIQUIDA_POSITIVA_CASILLA: Decimal("0"),
        _M200_CUOTA_LIQUIDA_NEGATIVA_CASILLA: Decimal("0"),
    }


def _snapshot():
    return _committed_snapshot("200", 2025, "0A", grade=RegistryAuthorityGrade.CALCULATION)


def _parameters() -> dict[str, ParameterDefinition]:
    return {parameter.id: parameter for parameter in _snapshot().revision.parameters}


def test_scalar_tipo_gravamen_parameters_carry_the_lis_art_29_rates() -> None:
    """The flat IS rate parameters encode the LIS Art. 29 grounded values.

    LIS Art. 29 (BOE-A-2014-12328) fixes: general 25 %; cooperativas
    fiscalmente protegidas a rate that, after the 3-pp reduction, does
    not exceed 20 %; entidades sin fines lucrativos (Ley 49/2002 art. 10)
    10 %; entidades de nueva creación 15 % for the first two profit-making
    periods. The registry must encode exactly those figures. The
    non-profit branch cites both the LIS dispatch article and the
    regime-specific Ley 49/2002 rate article.
    """
    parameters = _parameters()
    expected = {
        "is.modelo-200.tipo-gravamen-general": Decimal("25"),
        "is.modelo-200.tipo-gravamen-cooperative-protected": Decimal("20"),
        "is.modelo-200.tipo-gravamen-non-profit-special-regime": Decimal("10"),
        "is.modelo-200.tipo-gravamen-new-entity-first-2-years": Decimal("15"),
    }
    for parameter_id, rate in expected.items():
        assert parameter_id in parameters, f"parameter {parameter_id!r} must be registered"
        parameter = parameters[parameter_id]
        assert parameter.data_type == "ratio"
        assert parameter.unit == "percent"
        assert len(parameter.values) == 1, f"{parameter_id!r} must carry one dated value"
        assert parameter.values[0].value == rate, f"{parameter_id!r} must encode the LIS Art. 29 rate {rate}"
        assert "ley-27-2014:art-29" in parameter.legal_refs, f"{parameter_id!r} must be grounded in LIS Art. 29"

    nonprofit = parameters["is.modelo-200.tipo-gravamen-non-profit-special-regime"]
    assert "ley-49-2002:art-10" in nonprofit.legal_refs, (
        "the 10% special-regime branch must cite its regime-specific Ley 49/2002 Art. 10 authority"
    )


def test_nonprofit_cuota_bracket_carries_the_ley_49_2002_rate_authority() -> None:
    """The 10% cuota branch is grounded in both LIS Art. 29 and Ley 49/2002 Art. 10.

    LIS Art. 29.3 points to the Ley 49/2002 regime; Ley 49/2002 Art. 10
    is the article-level authority for the positive taxable base from
    non-exempt economic activities being taxed at 10%. The bracket used
    by casilla 00562 must carry both references so the calculation path
    is legally traceable from the dispatched rate through cuota íntegra.
    """
    bracket = _parameters()["is.modelo-200.cuota-integra-bracket-non-profit-special-regime"]

    assert bracket.data_type == "bracket_table"
    assert bracket.bracket_axis == "filing_period"
    assert "ley-27-2014:art-29" in bracket.legal_refs
    assert "ley-27-2014:art-30" in bracket.legal_refs
    assert "ley-49-2002:art-10" in bracket.legal_refs
    assert len(bracket.brackets) == 1
    assert bracket.brackets[0].marginal_rate == Decimal("0.10")

    formula_refs = {formula.id: formula.legal_refs for formula in _snapshot().revision.formulas}
    assert "ley-49-2002:art-10" in formula_refs["modelo-200-tipo-gravamen-por-forma-juridica"]
    assert "ley-49-2002:art-10" in formula_refs["modelo-200-cuota-integra"]


def test_ley_49_2002_art_10_nonprofit_rate_links_to_bundled_corpus() -> None:
    """The regime-specific 10% legal reference resolves to the bundled BOE excerpt."""
    _, catalogues = _committed_modelo("200")
    reference = catalogues.legal["ley-49-2002:art-10"]

    assert reference.corpus_ref == "corpus/normatives/html/ley-49-2002-art-10.html#a10"
    assert reference.permalink.endswith("#a10")
    assert reference.effective_from == date(2002, 12, 25)
    assert reference.required_text == (
        "Artículo 10. Tipo de gravamen.",
        "La base imponible positiva",
        "explotaciones económicas no exentas",
        "tipo del 10 por 100",
    )
    verify_legal_catalogue({reference.id: reference}, source_root=bundled_path())


def test_micro_empresa_rate_is_a_two_bracket_scale_not_a_flat_value() -> None:
    """The micro-empresa rate is the LIS Art. 29.1 two-bracket scale.

    LIS DT 44ª sets the transitional micro-empresa scale at 21 % on the
    0-50.000 EUR base tranche and 22 % on the rest for periods initiated
    in 2025, then 19 % / 21 % for 2026 (AEAT Manual de Sociedades
    "Tipos de gravamen vigentes"; AEAT folleto actividades económicas
    4.3, the authority recorded in the corporate-entity design §5). The
    final LIS Art. 29.1 17 % / 20 % scale is not the 2025 window. The
    previous registry encoding — a single flat ``23`` — matched no
    2025+ micro-empresa tranche; the parameter must instead be a
    ``bracket_table`` carrying the dated windows.
    """
    parameters = _parameters()
    assert "is.modelo-200.tipo-gravamen-pyme" in parameters
    parameter = parameters["is.modelo-200.tipo-gravamen-pyme"]
    assert parameter.data_type == "bracket_table", "the micro-empresa rate is a tranche scale, not a flat scalar"
    assert parameter.bracket_axis == "filing_period"
    assert "ley-27-2014:art-29" in parameter.legal_refs
    assert "ley-27-2014:dt-44" in parameter.legal_refs, (
        "the 2025/2026 transitional micro-empresa tranches must cite their binding source LIS DT 44ª (Ley 7/2024)"
    )
    assert not parameter.values, "a bracket_table parameter must not carry flat dated values"

    by_window: dict[tuple[date, date | None], dict[Decimal, Decimal]] = {}
    for bracket in parameter.brackets:
        window = (bracket.valid_from, bracket.valid_to)
        by_window.setdefault(window, {})[bracket.lower_bound] = bracket.marginal_rate

    # LIS DT 44ª transitional micro-empresa scale (Ley 7/2024): the
    # 2025/2026 first/rest tranche rates are the AEAT-published anchors.
    rates_2025 = by_window[(date(2025, 1, 1), date(2025, 12, 31))]
    assert rates_2025[Decimal("0")] == Decimal("0.21"), "2025 first tranche must be 21 % (LIS DT 44ª)"
    assert rates_2025[Decimal("50000")] == Decimal("0.22"), "2025 rest tranche must be 22 % (LIS DT 44ª)"

    rates_2026 = by_window[(date(2026, 1, 1), date(2026, 12, 31))]
    assert rates_2026[Decimal("0")] == Decimal("0.19"), "2026 first tranche must be 19 %"
    assert rates_2026[Decimal("50000")] == Decimal("0.21"), "2026 rest tranche must be 21 %"

    # The 2025+ windows must not carry the pre-2025 flat 23 % figure;
    # the two-tranche scale replaced it. The 2024 window is the
    # legitimate backfill at 23 % (LIS Art. 29 pre-2025 pyme regime)
    # and is expected exactly there.
    for window, window_rates in by_window.items():
        window_year = window[0].year
        if window_year >= 2025:
            assert Decimal("0.23") not in window_rates.values(), (
                f"2025+ window must not carry the pre-2025 flat 23 % rate (window {window})"
            )
        assert Decimal("23") not in window_rates.values()


def test_micro_empresa_display_rate_echoes_first_tranche_by_year() -> None:
    """Casilla 00558 echoes the first-tranche micro rate for the filing year.

    The cuota path is bracket-aware, but the official display casilla is scalar.
    It must therefore not keep showing the legacy flat 23 % once the 2025/2026
    transitional micro-company scale applies.
    """
    parameter = _parameters()["is.modelo-200.tipo-gravamen-pyme-display"]
    assert parameter.data_type == "ratio"
    assert parameter.unit == "percent"
    assert "ley-27-2014:dt-44" in parameter.legal_refs

    rates_by_year = {value.valid_from.year: value.value for value in parameter.values}
    assert rates_by_year == {
        2024: Decimal("23"),
        2025: Decimal("21"),
        2026: Decimal("19"),
    }


def test_micro_empresa_first_tranche_fixed_addition_carries_into_the_rest_tranche() -> None:
    """The rest-tranche fixed_addition equals the cuota accumulated at 50.000.

    A ``bracket_table`` resolves a base to a cuota via
    ``fixed_addition + marginal_rate * (base - lower_bound)``. For the
    micro-empresa scale the rest tranche starts at 50.000 EUR, so its
    ``fixed_addition`` must equal the cuota the first tranche accumulates
    over its full 0-50.000 width: 50.000 x 21 % = 10.500 for 2025 (LIS
    DT 44ª transitional first-tranche rate) and 50.000 x 19 % = 9.500 for
    2026. This is a structural-consistency check on the encoded bracket
    rows, derived from the tranche widths and the grounded marginal rates,
    not a recomputation of a registry formula's output.
    """
    parameter = _parameters()["is.modelo-200.tipo-gravamen-pyme"]
    rest_by_year: dict[int, Decimal] = {}
    for bracket in parameter.brackets:
        if bracket.lower_bound == Decimal("50000"):
            rest_by_year[bracket.valid_from.year] = bracket.fixed_addition
    assert rest_by_year[2025] == Decimal("10500"), "2025 rest tranche fixed_addition = 50.000 x 21 % (LIS DT 44ª)"
    assert rest_by_year[2026] == Decimal("9500"), "2026 rest tranche fixed_addition = 50.000 x 19 %"


def test_tipo_gravamen_dispatch_routes_00558_by_legal_entity_form() -> None:
    """Changing the legal_entity_form binding changes the dispatched 00558 rate.

    The ``modelo-200-tipo-gravamen-por-forma-juridica`` formula selects
    the scalar display casilla 00558 by the taxpayer's legal form:
    sociedades de capital (sl / sa) and sociedades civiles mercantiles
    take the general 25 % rate, cooperativas fiscalmente protegidas the
    20 % rate, and entidades sin fines lucrativos the 10 % rate. This
    asserts dispatch mechanics on both paths: flipping the enum binding
    selects a different scalar echo for 00558 and a different bracket
    path for cuota íntegra 00562.
    """
    base_inputs = _base_inputs(Decimal("1000000"))

    def _cuota_for(form: str) -> tuple[Decimal, Decimal]:
        result = calculate_registry_snapshot(
            _snapshot(),
            inputs=base_inputs,
            enum_binding_values={_DISPATCH_BINDING: form},
            binding_values={
                "modelo-200-2024-profile-new-entity-flag": Decimal("0"),
                "modelo-200-2024-profile-incn-prior-12-months": Decimal("10000000"),
                "modelo-200-2024-profile-tributacion-estado-porcentaje": Decimal("100"),
                "modelo-200-2024-bin-pendiente-ejercicios-anteriores": Decimal("0"),
                "modelo-200-2024-dotaciones-deterioro-creditos-saldo-no-cumplido-anteriores": Decimal("0"),
                "modelo-200-2024-dotaciones-deterioro-creditos-saldo-cumplido-anteriores": Decimal("0"),
            },
            relation_values=dict(_M200_PAGOS_RELATIONS_ZERO),
            date_context={"filing_period": date(2024, 12, 31)},
        )
        return result.values[_M200_TIPO_GRAVAMEN_CASILLA], result.values[_M200_CUOTA_INTEGRA_CASILLA]

    sl_rate, sl_cuota = _cuota_for("sl")
    sa_rate, _ = _cuota_for("sa")
    coop_rate, coop_cuota = _cuota_for("cooperativa")
    nonprofit_rate, nonprofit_cuota = _cuota_for("sin_fines_lucrativos")

    # sl and sa are both sociedades de capital — same general rate.
    assert sl_rate == sa_rate == Decimal("25")
    assert coop_rate == Decimal("20")
    assert nonprofit_rate == Decimal("10")

    # The dispatch must produce three distinct cuotas for the same base.
    assert sl_cuota != coop_cuota != nonprofit_cuota
    assert sl_cuota > coop_cuota > nonprofit_cuota

    # The cuota íntegra applies the dispatched rate to the 1.000.000 base.
    assert sl_cuota == Decimal("250000.00")
    assert coop_cuota == Decimal("200000.00")
    assert nonprofit_cuota == Decimal("100000.00")


def test_nonprofit_special_regime_stays_at_10_percent_inside_erd_threshold() -> None:
    """Ley 49/2002 entities keep the 10% special-regime rate below 1M INCN."""
    result = calculate_registry_snapshot(
        _snapshot(),
        inputs=_base_inputs(Decimal("1000000")),
        enum_binding_values={_DISPATCH_BINDING: "sin_fines_lucrativos"},
        binding_values={
            "modelo-200-2024-profile-new-entity-flag": Decimal("0"),
            "modelo-200-2024-profile-incn-prior-12-months": Decimal("500000"),
            "modelo-200-2024-profile-tributacion-estado-porcentaje": Decimal("100"),
            "modelo-200-2024-bin-pendiente-ejercicios-anteriores": Decimal("0"),
            "modelo-200-2024-dotaciones-deterioro-creditos-saldo-no-cumplido-anteriores": Decimal("0"),
            "modelo-200-2024-dotaciones-deterioro-creditos-saldo-cumplido-anteriores": Decimal("0"),
        },
        relation_values=dict(_M200_PAGOS_RELATIONS_ZERO),
        date_context={"filing_period": date(2024, 12, 31)},
    )

    assert result.values[_M200_TIPO_GRAVAMEN_CASILLA] == Decimal("10")
    assert result.values[_M200_CUOTA_INTEGRA_CASILLA] == Decimal("100000.00")


def test_tipo_gravamen_dispatch_raises_when_legal_entity_form_is_unsupplied() -> None:
    """A cuota chain with no legal_entity_form binding fails loudly.

    The dispatch refuses to default a rate: an undeclared legal form
    yields a ``RegistryValidationError`` rather than a silent guess —
    the corporate-entity design's "a wrong tax is worse than an incomplete
    answer" constraint enforced at the rate level.
    """
    with pytest.raises(RegistryValidationError, match="has no supplied value"):
        calculate_registry_snapshot(
            _snapshot(),
            inputs=_base_inputs(Decimal("1000000")),
            binding_values={
                "modelo-200-2024-profile-new-entity-flag": Decimal("0"),
                "modelo-200-2024-profile-incn-prior-12-months": Decimal("10000000"),
                "modelo-200-2024-profile-tributacion-estado-porcentaje": Decimal("100"),
                "modelo-200-2024-bin-pendiente-ejercicios-anteriores": Decimal("0"),
                "modelo-200-2024-dotaciones-deterioro-creditos-saldo-no-cumplido-anteriores": Decimal("0"),
                "modelo-200-2024-dotaciones-deterioro-creditos-saldo-cumplido-anteriores": Decimal("0"),
            },
            relation_values=dict(_M200_PAGOS_RELATIONS_ZERO),
            date_context={"filing_period": date(2024, 12, 31)},
        )


def test_tipo_gravamen_dispatch_raises_on_unrecognised_legal_entity_form() -> None:
    """A legal_entity_form value outside the dispatch table fails loudly.

    The dispatch table maps the recognised legal forms only. A key that
    is not in the table — including ``cooperativa`` typo'd, or a future
    form not yet grounded — raises a missing-key error rather than
    falling through to a default rate.
    """
    with pytest.raises(RegistryValidationError, match="missing key"):
        calculate_registry_snapshot(
            _snapshot(),
            inputs=_base_inputs(Decimal("1000000")),
            enum_binding_values={_DISPATCH_BINDING: "unknown_form"},
            binding_values={
                "modelo-200-2024-profile-new-entity-flag": Decimal("0"),
                "modelo-200-2024-profile-incn-prior-12-months": Decimal("10000000"),
                "modelo-200-2024-profile-tributacion-estado-porcentaje": Decimal("100"),
                "modelo-200-2024-bin-pendiente-ejercicios-anteriores": Decimal("0"),
                "modelo-200-2024-dotaciones-deterioro-creditos-saldo-no-cumplido-anteriores": Decimal("0"),
                "modelo-200-2024-dotaciones-deterioro-creditos-saldo-cumplido-anteriores": Decimal("0"),
            },
            relation_values=dict(_M200_PAGOS_RELATIONS_ZERO),
            date_context={"filing_period": date(2024, 12, 31)},
        )


def test_dispatch_binding_is_a_profile_sourced_enum_binding() -> None:
    """The legal_entity_form binding is profile-sourced and enum-typed.

    The cuota rate must select itself from the operator-declared
    taxpayer profile, not from a hand-typed casilla. The binding
    therefore declares ``source = "profile"`` and a ``typed_enum`` so
    the runtime routes it through the string-valued enum-dispatch
    channel of ``lookup_parameter_by_entity_type``.
    """
    binding = next(b for b in _snapshot().revision.bindings if b.id == _DISPATCH_BINDING)
    assert binding.source == "profile"
    assert binding.typed_enum == "LegalEntityForm"
    assert selector_as_dict(binding).get("field") == "legal_entity_form"
    assert "ley-27-2014:art-29" in binding.legal_refs


def test_erd_parameter_encodes_the_ley_31_2022_rate() -> None:
    """The ERD parameter encodes the Ley 31/2022 Art. 39 flat 23 % rate.

    Ley 31/2022 Art. 39 modified LIS Art. 29 to introduce a 23 %
    rate for entities whose INCN in the immediately prior period was
    below 1.000.000 EUR (entidades de reducida dimensión), effective
    for periods initiated from 2023. The registry parameter must
    encode exactly 23, be a scalar ratio/percent, and cite both the
    original LIS Art. 29 and the Ley 31/2022 modification.
    """
    parameters = _parameters()
    assert "is.modelo-200.tipo-gravamen-erd" in parameters, "ERD parameter must be registered (Ley 31/2022 Art. 39)"
    erd = parameters["is.modelo-200.tipo-gravamen-erd"]
    assert erd.data_type == "ratio"
    assert erd.unit == "percent"
    assert len(erd.values) == 1
    assert erd.values[0].value == Decimal("23"), "ERD rate must be 23 % per Ley 31/2022 Art. 39"
    assert "ley-27-2014:art-29" in erd.legal_refs
    assert "ley-31-2022:art-39" in erd.legal_refs, "ERD parameter must cite Ley 31/2022 Art. 39 as modification source"


def test_art101_erd_parameter_encodes_the_dt44_transition_schedule() -> None:
    """The art.101 ERD parameter encodes the DT 44ª 2025-2028 schedule.

    LIS art. 101 defines entidades de reducida dimensión by prior-period
    INCN below 10.000.000 EUR. LIS DT 44ª then phases their general-rate
    transition at 24/23/22/21 for periods initiated in 2025-2028, before
    the current art. 29 20% rate applies from 2029. The 2024 value stays
    25% so the dated parameter can be used safely by the shared
    2024 revision before DT 44ª takes effect.
    """
    parameters = _parameters()
    assert "is.modelo-200.tipo-gravamen-erd-art101" in parameters
    erd = parameters["is.modelo-200.tipo-gravamen-erd-art101"]
    assert erd.data_type == "ratio"
    assert erd.unit == "percent"
    assert "ley-27-2014:art-101" in erd.legal_refs
    assert "ley-27-2014:dt-44" in erd.legal_refs

    rates_by_year = {value.valid_from.year: value.value for value in erd.values}
    assert rates_by_year == {
        2024: Decimal("25"),
        2025: Decimal("24"),
        2026: Decimal("23"),
        2027: Decimal("22"),
        2028: Decimal("21"),
        2029: Decimal("20"),
    }


def test_tipo_gravamen_dispatch_routes_erd_23_when_incn_below_1m() -> None:
    """INCN < 1.000.000 EUR routes general-form entities to the ERD 23 % rate.

    Ley 31/2022 Art. 39 (LIS Art. 29): an SL with prior-period INCN
    of 850.000 EUR pays 23 % IS rather than the general 25 %. The
    tipo formula must detect the INCN threshold and select the ERD
    parameter. Aitor Etxegarai oracle: SAL INCN 850.000 → 23 %.
    """
    base_inputs = _base_inputs(Decimal("1000000"))
    common_bindings = {
        "modelo-200-2024-profile-new-entity-flag": Decimal("0"),
        "modelo-200-2024-profile-incn-prior-12-months": Decimal("850000"),
        "modelo-200-2024-profile-tributacion-estado-porcentaje": Decimal("100"),
        "modelo-200-2024-bin-pendiente-ejercicios-anteriores": Decimal("0"),
        "modelo-200-2024-dotaciones-deterioro-creditos-saldo-no-cumplido-anteriores": Decimal("0"),
        "modelo-200-2024-dotaciones-deterioro-creditos-saldo-cumplido-anteriores": Decimal("0"),
    }

    result_sal = calculate_registry_snapshot(
        _snapshot(),
        inputs=base_inputs,
        enum_binding_values={_DISPATCH_BINDING: "sal"},
        binding_values=common_bindings,
        relation_values=dict(_M200_PAGOS_RELATIONS_ZERO),
        date_context={"filing_period": date(2024, 12, 31)},
    )
    result_sl = calculate_registry_snapshot(
        _snapshot(),
        inputs=base_inputs,
        enum_binding_values={_DISPATCH_BINDING: "sl"},
        binding_values=common_bindings,
        relation_values=dict(_M200_PAGOS_RELATIONS_ZERO),
        date_context={"filing_period": date(2024, 12, 31)},
    )

    assert result_sal.values[_M200_TIPO_GRAVAMEN_CASILLA] == Decimal("23"), (
        "SAL with INCN 850k must display tipo 23 % (Ley 31/2022 ERD)"
    )
    assert result_sl.values[_M200_TIPO_GRAVAMEN_CASILLA] == Decimal("23"), (
        "SL with INCN 850k must display tipo 23 % (Ley 31/2022 ERD)"
    )
    # Cuota integra: 1.000.000 base x 23 % = 230.000.
    assert result_sal.values[_M200_CUOTA_INTEGRA_CASILLA] == Decimal("230000.00"), (
        "SAL cuota integra at ERD 23 % on 1M base = 230.000"
    )


def test_tipo_gravamen_dispatch_routes_2025_micro_display_rate_to_first_tranche() -> None:
    """Persona repro: a 2025 micro-company prints 21 while cuota is 10.500.

    Dario's CLI run used an SL with INCN below 1M and a 50.000 base. The
    cuota already followed LIS DT 44ª at 21 %, but 00558 incorrectly echoed
    the legacy 23 %. The display scalar must follow the same filing-year
    threshold as the bracket calculation.
    """
    result = calculate_registry_snapshot(
        _snapshot(),
        inputs=_base_inputs(Decimal("50000")),
        enum_binding_values={_DISPATCH_BINDING: "sl"},
        binding_values={
            "modelo-200-2024-profile-new-entity-flag": Decimal("0"),
            "modelo-200-2024-profile-incn-prior-12-months": Decimal("450000"),
            "modelo-200-2024-profile-tributacion-estado-porcentaje": Decimal("100"),
            "modelo-200-2024-bin-pendiente-ejercicios-anteriores": Decimal("0"),
            "modelo-200-2024-dotaciones-deterioro-creditos-saldo-no-cumplido-anteriores": Decimal("0"),
            "modelo-200-2024-dotaciones-deterioro-creditos-saldo-cumplido-anteriores": Decimal("0"),
        },
        relation_values=dict(_M200_PAGOS_RELATIONS_ZERO),
        date_context={"filing_period": date(2025, 12, 31)},
    )

    assert result.values[_M200_TIPO_GRAVAMEN_CASILLA] == Decimal("21")
    assert result.values[_M200_CUOTA_INTEGRA_CASILLA] == Decimal("10500.00")


def test_tipo_gravamen_dispatch_routes_2025_micro_cuota_to_rest_tranche() -> None:
    """A 2025 micro-company above 50.000 EUR uses the second tranche."""
    result = calculate_registry_snapshot(
        _snapshot(),
        inputs=_base_inputs(Decimal("100000")),
        enum_binding_values={_DISPATCH_BINDING: "sl"},
        binding_values={
            "modelo-200-2024-profile-new-entity-flag": Decimal("0"),
            "modelo-200-2024-profile-incn-prior-12-months": Decimal("450000"),
            "modelo-200-2024-profile-tributacion-estado-porcentaje": Decimal("100"),
            "modelo-200-2024-bin-pendiente-ejercicios-anteriores": Decimal("0"),
            "modelo-200-2024-dotaciones-deterioro-creditos-saldo-no-cumplido-anteriores": Decimal("0"),
            "modelo-200-2024-dotaciones-deterioro-creditos-saldo-cumplido-anteriores": Decimal("0"),
        },
        relation_values=dict(_M200_PAGOS_RELATIONS_ZERO),
        date_context={"filing_period": date(2025, 12, 31)},
    )

    assert result.values[_M200_TIPO_GRAVAMEN_CASILLA] == Decimal("21")
    assert result.values[_M200_CUOTA_INTEGRA_CASILLA] == Decimal("21500.00")
    assert result.values[_M200_CUOTA_INTEGRA_CASILLA] != Decimal("23000.00")


def test_tipo_gravamen_dispatch_routes_general_25_when_incn_at_or_above_1m() -> None:
    """INCN >= 1.000.000 EUR keeps general-form entities at the 25 % rate.

    The ERD threshold is strictly below 1M. An entity with INCN exactly
    1.000.000 EUR does NOT qualify and must stay at 25 %. This is the
    anti-tautology companion to the ERD test: crossing the 1M boundary
    changes the dispatched rate.
    """
    base_inputs = _base_inputs(Decimal("1000000"))

    result = calculate_registry_snapshot(
        _snapshot(),
        inputs=base_inputs,
        enum_binding_values={_DISPATCH_BINDING: "sa"},
        binding_values={
            "modelo-200-2024-profile-new-entity-flag": Decimal("0"),
            "modelo-200-2024-profile-incn-prior-12-months": Decimal("1500000"),
            "modelo-200-2024-profile-tributacion-estado-porcentaje": Decimal("100"),
            "modelo-200-2024-bin-pendiente-ejercicios-anteriores": Decimal("0"),
            "modelo-200-2024-dotaciones-deterioro-creditos-saldo-no-cumplido-anteriores": Decimal("0"),
            "modelo-200-2024-dotaciones-deterioro-creditos-saldo-cumplido-anteriores": Decimal("0"),
        },
        relation_values=dict(_M200_PAGOS_RELATIONS_ZERO),
        date_context={"filing_period": date(2024, 12, 31)},
    )
    assert result.values[_M200_TIPO_GRAVAMEN_CASILLA] == Decimal("25"), (
        "SA with INCN 1.5M must display tipo 25 % (above ERD threshold)"
    )
    assert result.values[_M200_CUOTA_INTEGRA_CASILLA] == Decimal("250000.00")


def test_tipo_gravamen_dispatch_routes_art101_erd_below_10m_from_2025() -> None:
    """INCN below 10M and at least 1M routes to the art.101 ERD schedule.

    For a 2025 filing period, LIS DT 44ª fixes the art.101 ERD rate at
    24%. A sociedad anónima with prior-period INCN 7.000.000 EUR is not
    a micro-empresa, but is below the art.101 10M threshold, so both the
    displayed rate and cuota path must use the ERD schedule.
    """
    result = calculate_registry_snapshot(
        _snapshot(),
        inputs=_base_inputs(Decimal("1000000")),
        enum_binding_values={_DISPATCH_BINDING: "sa"},
        binding_values={
            "modelo-200-2024-profile-new-entity-flag": Decimal("0"),
            "modelo-200-2024-profile-incn-prior-12-months": Decimal("7000000"),
            "modelo-200-2024-profile-tributacion-estado-porcentaje": Decimal("100"),
            "modelo-200-2024-bin-pendiente-ejercicios-anteriores": Decimal("0"),
            "modelo-200-2024-dotaciones-deterioro-creditos-saldo-no-cumplido-anteriores": Decimal("0"),
            "modelo-200-2024-dotaciones-deterioro-creditos-saldo-cumplido-anteriores": Decimal("0"),
        },
        relation_values=dict(_M200_PAGOS_RELATIONS_ZERO),
        date_context={"filing_period": date(2025, 12, 31)},
    )

    assert result.values[_M200_TIPO_GRAVAMEN_CASILLA] == Decimal("24")
    assert result.values[_M200_CUOTA_INTEGRA_CASILLA] == Decimal("240000.00")


def test_tipo_gravamen_dispatch_keeps_general_rate_at_art101_boundary_from_2025() -> None:
    """INCN at 10M is outside art.101 ERD and stays on the general rate."""
    result = calculate_registry_snapshot(
        _snapshot(),
        inputs=_base_inputs(Decimal("1000000")),
        enum_binding_values={_DISPATCH_BINDING: "sa"},
        binding_values={
            "modelo-200-2024-profile-new-entity-flag": Decimal("0"),
            "modelo-200-2024-profile-incn-prior-12-months": Decimal("10000000"),
            "modelo-200-2024-profile-tributacion-estado-porcentaje": Decimal("100"),
            "modelo-200-2024-bin-pendiente-ejercicios-anteriores": Decimal("0"),
            "modelo-200-2024-dotaciones-deterioro-creditos-saldo-no-cumplido-anteriores": Decimal("0"),
            "modelo-200-2024-dotaciones-deterioro-creditos-saldo-cumplido-anteriores": Decimal("0"),
        },
        relation_values=dict(_M200_PAGOS_RELATIONS_ZERO),
        date_context={"filing_period": date(2025, 12, 31)},
    )

    assert result.values[_M200_TIPO_GRAVAMEN_CASILLA] == Decimal("25")
    assert result.values[_M200_CUOTA_INTEGRA_CASILLA] == Decimal("250000.00")


def test_new_entity_flag_overrides_erd_threshold() -> None:
    """New-entity flag (LIS Art. 29 par. 4) takes priority over the ERD lane.

    Even when INCN < 1M, an entity in its first two profit-making periods
    applies the 15 % new-entity rate, not the 23 % ERD rate. The
    new-entity lane is the outermost predicate in the tipo formula.
    """
    base_inputs = _base_inputs(Decimal("500000"))

    result = calculate_registry_snapshot(
        _snapshot(),
        inputs=base_inputs,
        enum_binding_values={_DISPATCH_BINDING: "sl"},
        binding_values={
            "modelo-200-2024-profile-new-entity-flag": Decimal("1"),
            "modelo-200-2024-profile-incn-prior-12-months": Decimal("200000"),
            "modelo-200-2024-profile-tributacion-estado-porcentaje": Decimal("100"),
            "modelo-200-2024-bin-pendiente-ejercicios-anteriores": Decimal("0"),
            "modelo-200-2024-dotaciones-deterioro-creditos-saldo-no-cumplido-anteriores": Decimal("0"),
            "modelo-200-2024-dotaciones-deterioro-creditos-saldo-cumplido-anteriores": Decimal("0"),
        },
        relation_values=dict(_M200_PAGOS_RELATIONS_ZERO),
        date_context={"filing_period": date(2024, 12, 31)},
    )
    assert result.values[_M200_TIPO_GRAVAMEN_CASILLA] == Decimal("15"), (
        "new-entity flag must override ERD lane: tipo = 15 %, not 23 %"
    )
    assert result.values[_M200_CUOTA_INTEGRA_CASILLA] == Decimal("75000.00"), (
        "cuota integra at 15 % on 500k base = 75.000"
    )


def test_cooperativa_retains_20_percent_even_when_incn_below_1m() -> None:
    """Cooperativa keeps 20 % even when INCN < 1.000.000 EUR.

    The ERD 23 % rate does not override the cooperative-protected special
    regime. A cooperativa fiscalmente protegida with INCN 500k must still
    pay 20 %, not 23 %.
    """
    base_inputs = _base_inputs(Decimal("1000000"))

    result = calculate_registry_snapshot(
        _snapshot(),
        inputs=base_inputs,
        enum_binding_values={_DISPATCH_BINDING: "cooperativa"},
        binding_values={
            "modelo-200-2024-profile-new-entity-flag": Decimal("0"),
            "modelo-200-2024-profile-incn-prior-12-months": Decimal("500000"),
            "modelo-200-2024-profile-tributacion-estado-porcentaje": Decimal("100"),
            "modelo-200-2024-bin-pendiente-ejercicios-anteriores": Decimal("0"),
            "modelo-200-2024-dotaciones-deterioro-creditos-saldo-no-cumplido-anteriores": Decimal("0"),
            "modelo-200-2024-dotaciones-deterioro-creditos-saldo-cumplido-anteriores": Decimal("0"),
        },
        relation_values=dict(_M200_PAGOS_RELATIONS_ZERO),
        date_context={"filing_period": date(2024, 12, 31)},
    )
    assert result.values[_M200_TIPO_GRAVAMEN_CASILLA] == Decimal("20"), (
        "cooperativa with INCN 500k must retain 20 %, not ERD 23 %"
    )
