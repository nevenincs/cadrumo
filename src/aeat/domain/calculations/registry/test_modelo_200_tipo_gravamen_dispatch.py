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
  (17/20 for periods initiated in 2025, 19/21 for 2026) are asserted
  against the LIS Art. 29 text (BOE-A-2014-12328) and the AEAT Manual de
  Sociedades "Tipos de gravamen vigentes" / AEAT folleto actividades
  económicas 4.3 — the external authority the corporate-entity ADR §5
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
from functools import lru_cache

import pytest

from aeat.core.resources import bundled_path

from . import build_snapshot, load_registry_tree
from ._errors import RegistryValidationError
from ._formula_runtime import calculate_registry_snapshot
from ._schema import ParameterDefinition

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_REGISTRY_ROOT = bundled_path("registry", "aeat")
_DISPATCH_BINDING = "modelo-200-2024-profile-legal-entity-form"


@lru_cache(maxsize=1)
def _load_modelo_200():
    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    modelo = next(item for item in modelos if item.id == "200")
    return modelo, catalogues


@lru_cache(maxsize=1)
def _snapshot():
    modelo, catalogues = _load_modelo_200()
    return build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2024,
        period="0A",
    )


def _parameters() -> dict[str, ParameterDefinition]:
    return {parameter.id: parameter for parameter in _snapshot().revision.parameters}


def test_scalar_tipo_gravamen_parameters_carry_the_lis_art_29_rates() -> None:
    """The flat IS rate parameters encode the LIS Art. 29 grounded values.

    LIS Art. 29 (BOE-A-2014-12328) fixes: general 25 %; cooperativas
    fiscalmente protegidas a rate that, after the 3-pp reduction, does
    not exceed 20 %; entidades sin fines lucrativos (Ley 49/2002) 10 %;
    entidades de nueva creación 15 % for the first two profit-making
    periods. The registry must encode exactly those figures, each cited
    to ``ley-27-2014:art-29``.
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
        assert parameter.values[0].value == rate, (
            f"{parameter_id!r} must encode the LIS Art. 29 rate {rate}"
        )
        assert "ley-27-2014:art-29" in parameter.legal_refs, (
            f"{parameter_id!r} must be grounded in LIS Art. 29"
        )


def test_micro_empresa_rate_is_a_two_bracket_scale_not_a_flat_value() -> None:
    """The micro-empresa rate is the LIS Art. 29.1 two-bracket scale.

    LIS Art. 29.1 charges 17 % on the 0-50.000 EUR base tranche and 20 %
    on the rest for periods initiated in 2025, and 19 % / 21 % for 2026
    (AEAT Manual de Sociedades "Tipos de gravamen vigentes"; AEAT folleto
    actividades económicas 4.3, the authority recorded in the
    corporate-entity ADR §5). The previous registry encoding — a single
    flat ``23`` — matched no LIS Art. 29 micro-empresa tranche; the
    parameter must instead be a ``bracket_table`` carrying both windows.
    """
    parameters = _parameters()
    assert "is.modelo-200.tipo-gravamen-pyme" in parameters
    parameter = parameters["is.modelo-200.tipo-gravamen-pyme"]
    assert parameter.data_type == "bracket_table", (
        "the micro-empresa rate is a tranche scale, not a flat scalar"
    )
    assert parameter.bracket_axis == "filing_period"
    assert "ley-27-2014:art-29" in parameter.legal_refs
    assert not parameter.values, "a bracket_table parameter must not carry flat dated values"

    by_window: dict[tuple[date, date | None], dict[Decimal, Decimal]] = {}
    for bracket in parameter.brackets:
        window = (bracket.valid_from, bracket.valid_to)
        by_window.setdefault(window, {})[bracket.lower_bound] = bracket.marginal_rate

    rates_2025 = by_window[(date(2025, 1, 1), date(2025, 12, 31))]
    assert rates_2025[Decimal("0")] == Decimal("0.17"), "2025 first tranche must be 17 %"
    assert rates_2025[Decimal("50000")] == Decimal("0.20"), "2025 rest tranche must be 20 %"

    rates_2026 = by_window[(date(2026, 1, 1), date(2026, 12, 31))]
    assert rates_2026[Decimal("0")] == Decimal("0.19"), "2026 first tranche must be 19 %"
    assert rates_2026[Decimal("50000")] == Decimal("0.21"), "2026 rest tranche must be 21 %"

    # No window carries the previous wrong flat 23 % figure in any form.
    for window_rates in by_window.values():
        assert Decimal("0.23") not in window_rates.values()
        assert Decimal("23") not in window_rates.values()


def test_micro_empresa_first_tranche_fixed_addition_carries_into_the_rest_tranche() -> None:
    """The rest-tranche fixed_addition equals the cuota accumulated at 50.000.

    A ``bracket_table`` resolves a base to a cuota via
    ``fixed_addition + marginal_rate * (base - lower_bound)``. For the
    micro-empresa scale the rest tranche starts at 50.000 EUR, so its
    ``fixed_addition`` must equal the cuota the first tranche accumulates
    over its full 0-50.000 width: 50.000 x 17 % = 8.500 for 2025 and
    50.000 x 19 % = 9.500 for 2026. This is a structural-consistency
    check on the encoded bracket rows, derived from the tranche widths
    and the grounded marginal rates, not a recomputation of a registry
    formula's output.
    """
    parameter = _parameters()["is.modelo-200.tipo-gravamen-pyme"]
    rest_by_year: dict[int, Decimal] = {}
    for bracket in parameter.brackets:
        if bracket.lower_bound == Decimal("50000"):
            rest_by_year[bracket.valid_from.year] = bracket.fixed_addition
    assert rest_by_year[2025] == Decimal("8500"), "2025 rest tranche fixed_addition = 50.000 x 17 %"
    assert rest_by_year[2026] == Decimal("9500"), "2026 rest tranche fixed_addition = 50.000 x 19 %"


def test_tipo_gravamen_dispatch_routes_00558_by_legal_entity_form() -> None:
    """Changing the legal_entity_form binding changes the dispatched 00558 rate.

    The ``modelo-200-tipo-gravamen-por-forma-juridica`` formula selects
    casilla 00558 by the taxpayer's legal form: sociedades de capital
    (sl / sa) and sociedades civiles mercantiles take the general 25 %
    rate, cooperativas fiscalmente protegidas the 20 % rate, and
    entidades sin fines lucrativos the 10 % rate. This asserts the
    dispatch mechanics: flipping the enum binding selects a different
    scalar parameter, so 00558 — and the cuota íntegra 00562 derived
    from it — changes accordingly.
    """
    base_inputs = {
        "DP200014:00552": Decimal("1000000"),
        "DP200014:01033": Decimal("0"),
        "DP200014:01034": Decimal("0"),
        "DP200014B:00592": Decimal("0"),
        "DP200014B:01766": Decimal("0"),
        "DP200014B:01784": Decimal("0"),
        "DP200026:00625": Decimal("100"),
    }

    def _cuota_for(form: str) -> tuple[Decimal, Decimal]:
        result = calculate_registry_snapshot(
            _snapshot(),
            inputs=base_inputs,
            enum_binding_values={_DISPATCH_BINDING: form},
            binding_values={
                "modelo-200-2024-profile-new-entity-flag": Decimal("0"),
                "modelo-200-2024-profile-incn-prior-12-months": Decimal("10000000"),
            },
            relation_values={"modelo-200-2024-rel-202-pagos-fraccionados": Decimal("0")},
            date_context={"filing_period": date(2024, 12, 31)},
        )
        return result.values["DP200014:00558"], result.values["DP200014:00562"]

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


def test_tipo_gravamen_dispatch_raises_when_legal_entity_form_is_unsupplied() -> None:
    """A cuota chain with no legal_entity_form binding fails loudly.

    The dispatch refuses to default a rate: an undeclared legal form
    yields a ``RegistryValidationError`` rather than a silent guess —
    the corporate-entity ADR's "a wrong tax is worse than an incomplete
    answer" constraint enforced at the rate level.
    """
    with pytest.raises(RegistryValidationError, match="has no supplied value"):
        calculate_registry_snapshot(
            _snapshot(),
            inputs={
                "DP200014:00552": Decimal("1000000"),
                "DP200014:01033": Decimal("0"),
                "DP200014:01034": Decimal("0"),
                "DP200014B:00592": Decimal("0"),
                "DP200014B:01766": Decimal("0"),
                "DP200014B:01784": Decimal("0"),
                "DP200026:00625": Decimal("100"),
            },
            binding_values={
                "modelo-200-2024-profile-new-entity-flag": Decimal("0"),
                "modelo-200-2024-profile-incn-prior-12-months": Decimal("10000000"),
            },
            relation_values={"modelo-200-2024-rel-202-pagos-fraccionados": Decimal("0")},
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
            inputs={
                "DP200014:00552": Decimal("1000000"),
                "DP200014:01033": Decimal("0"),
                "DP200014:01034": Decimal("0"),
                "DP200014B:00592": Decimal("0"),
                "DP200014B:01766": Decimal("0"),
                "DP200014B:01784": Decimal("0"),
                "DP200026:00625": Decimal("100"),
            },
            enum_binding_values={_DISPATCH_BINDING: "unknown_form"},
            binding_values={
                "modelo-200-2024-profile-new-entity-flag": Decimal("0"),
                "modelo-200-2024-profile-incn-prior-12-months": Decimal("10000000"),
            },
            relation_values={"modelo-200-2024-rel-202-pagos-fraccionados": Decimal("0")},
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
    binding = next(
        b for b in _snapshot().revision.bindings if b.id == _DISPATCH_BINDING
    )
    assert binding.source == "profile"
    assert binding.typed_enum == "LegalEntityForm"
    assert binding.selector.get("field") == "legal_entity_form"
    assert "ley-27-2014:art-29" in binding.legal_refs


# Micro-empresa lane: INCN-gated routing to the LIS Art. 29.1 two-
# tranche pyme scale via `lookup_bracket_by_entity_type`. The expected
# cuotas come straight from the AEAT folleto actividades económicas
# 4.3 and the AEAT Manual de Sociedades "Tipos de gravamen vigentes"
# scale (17 % on 0-50.000 / 20 % on the rest for 2025, 19 / 21 for
# 2026) applied to round bases — these are AEAT-published worked
# tranches, not registry-formula recomputations.

_INCN_BINDING = "modelo-200-2024-profile-incn-prior-12-months"
_NEW_ENTITY_BINDING = "modelo-200-2024-profile-new-entity-flag"


def _cuota_with_bindings(
    *,
    base: Decimal,
    legal_entity_form: str,
    incn: Decimal | None,
    new_entity: Decimal,
    period_end: date,
) -> Decimal:
    binding_values: dict[str, Decimal] = {_NEW_ENTITY_BINDING: new_entity}
    if incn is not None:
        binding_values[_INCN_BINDING] = incn
    return calculate_registry_snapshot(
        _snapshot(),
        inputs={
            "DP200014:00552": base,
            "DP200014:01033": Decimal("0"),
            "DP200014:01034": Decimal("0"),
            "DP200014B:00592": Decimal("0"),
            "DP200014B:01766": Decimal("0"),
            "DP200014B:01784": Decimal("0"),
            "DP200026:00625": Decimal("100"),
        },
        enum_binding_values={_DISPATCH_BINDING: legal_entity_form},
        binding_values=binding_values,
        relation_values={"modelo-200-2024-rel-202-pagos-fraccionados": Decimal("0")},
        date_context={"filing_period": period_end},
    ).values["DP200014:00562"]


def test_micro_empresa_cuota_routes_through_pyme_two_tranche_scale_for_2025_period() -> None:
    """A pyme profile in a 2025 period applies the 17 % / 20 % scale via the bracket dispatch.

    For a base of 100.000 EUR the LIS Art. 29.1 micro-empresa scale
    yields 50.000 x 17 % + 50.000 x 20 % = 8.500 + 10.000 = 18.500
    EUR (AEAT folleto actividades económicas 4.3 worked tranches). The
    INCN binding is 500.000 — below the LIS Art. 29.1 1.000.000 EUR
    threshold ("importe neto de la cifra de negocios del período
    impositivo inmediato anterior sea inferior a 1 millón de euros")
    — so the cuota lane is the pyme bracket, not the sub-form scalar
    25 %.
    """
    cuota = _cuota_with_bindings(
        base=Decimal("100000"),
        legal_entity_form="sl",
        incn=Decimal("500000"),
        new_entity=Decimal("0"),
        period_end=date(2025, 12, 31),
    )
    assert cuota == Decimal("18500.00")


def test_micro_empresa_cuota_routes_through_pyme_two_tranche_scale_for_2026_period() -> None:
    """A pyme profile in a 2026 period applies the 19 % / 21 % scale via the bracket dispatch.

    For a base of 100.000 EUR the LIS Art. 29.1 micro-empresa scale
    yields 50.000 x 19 % + 50.000 x 21 % = 9.500 + 10.500 = 20.000
    EUR (AEAT Manual de Sociedades "Tipos de gravamen vigentes"
    2026 update). The same INCN gate and dispatch lane as the 2025
    case applies; only the bracket window shifts via ``bracket_axis
    = "filing_period"``.
    """
    cuota = _cuota_with_bindings(
        base=Decimal("100000"),
        legal_entity_form="sl",
        incn=Decimal("500000"),
        new_entity=Decimal("0"),
        period_end=date(2026, 12, 31),
    )
    assert cuota == Decimal("20000.00")


def test_incn_above_one_million_routes_through_sub_form_general_rate_not_pyme() -> None:
    """INCN above 1.000.000 EUR falls through to the sub-form general 25 % rate.

    LIS Art. 29.1: the micro-empresa scale applies only when the
    prior-12-months INCN is "inferior a 1 millón de euros". A
    sociedad limitada with INCN = 5.000.000 stays on the general
    25 % rate. For a base of 100.000 EUR the cuota is 100.000 x 25 %
    = 25.000 EUR; the pyme 18.500 EUR alternative is not reached.
    The structural check is that the INCN gate flips the dispatch
    lane: same sub-form, same base, two different cuotas keyed on
    the INCN binding alone.
    """
    cuota = _cuota_with_bindings(
        base=Decimal("100000"),
        legal_entity_form="sl",
        incn=Decimal("5000000"),
        new_entity=Decimal("0"),
        period_end=date(2025, 12, 31),
    )
    assert cuota == Decimal("25000.00")


def test_new_entity_override_beats_micro_empresa_lane_even_when_incn_qualifies() -> None:
    """The 15 % new-entity override layers on top of the micro-empresa lane.

    LIS Art. 29 par. 4 fixes 15 % for the first two profit-making
    periods of a newly created entity. The cuota formula's outer
    ``if_then_else`` selects the override first; the INCN-gated
    micro-empresa lane and the sub-form fallback never execute when
    the new-entity flag is set. For a base of 100.000 EUR the
    expected cuota is 100.000 x 15 % = 15.000 EUR — distinct from
    the 18.500 EUR pyme outcome and the 25.000 EUR general outcome
    on the same base and INCN.
    """
    cuota = _cuota_with_bindings(
        base=Decimal("100000"),
        legal_entity_form="sl",
        incn=Decimal("500000"),
        new_entity=Decimal("1"),
        period_end=date(2025, 12, 31),
    )
    assert cuota == Decimal("15000.00")


def test_new_entity_override_beats_general_sub_form_when_incn_does_not_qualify() -> None:
    """The 15 % override also wins over a general sub-form profile (INCN above threshold).

    With a high INCN (no micro-empresa lane) and the new-entity flag
    set, the outer override still routes the cuota through the 15 %
    bracket — proving the override sits ABOVE both inner lanes
    rather than only the micro-empresa lane. 100.000 x 15 % = 15.000.
    """
    cuota = _cuota_with_bindings(
        base=Decimal("100000"),
        legal_entity_form="sl",
        incn=Decimal("5000000"),
        new_entity=Decimal("1"),
        period_end=date(2025, 12, 31),
    )
    assert cuota == Decimal("15000.00")


def test_cuota_integra_raises_when_incn_binding_is_unsupplied_for_non_new_entity() -> None:
    """A non-new-entity cuota with no INCN binding raises rather than guessing.

    The micro-empresa identification is INCN-gated and INCN is
    optional on the profile (``Decimal | None``). When the
    new-entity override is OFF and the INCN binding is absent the
    formula cannot decide whether the pyme lane or the sub-form
    lane applies, and the runtime raises ``binding has no supplied
    value`` — INCOMPLETE rather than a silent default. (When the
    new-entity flag IS set the override short-circuits the inner
    ``if_then_else`` and no INCN binding is required; this is
    asserted by the override tests above which omit no INCN value
    but still pass.)
    """
    with pytest.raises(RegistryValidationError, match="incn-prior-12-months"):
        _cuota_with_bindings(
            base=Decimal("100000"),
            legal_entity_form="sl",
            incn=None,
            new_entity=Decimal("0"),
            period_end=date(2025, 12, 31),
        )


def test_cuota_integra_formula_is_a_three_lane_layered_if_then_else() -> None:
    """Structural assertion: the cuota formula is a layered ``if_then_else`` graph.

    Three dispatch lanes coexist — new-entity 15 % override, INCN-
    gated micro-empresa bracket, sub-form scalar bracket — and the
    composition selects exactly one per profile. The graph shape is
    ``if_then_else(new_entity_flag,
                   override_bracket,
                   if_then_else(less_than(incn, 1_000_000),
                                pyme_bracket,
                                sub_form_bracket))``.
    This is wiring-shape testing (permitted by the no-tautological
    -calculation-tests rule), not a registry-formula recomputation.
    """
    formula = next(
        f for f in _snapshot().revision.formulas if f.id == "modelo-200-cuota-integra"
    )
    assert formula.expression.op == "if_then_else"
    predicate, override_branch, fallback_branch = formula.expression.args
    assert predicate.binding == _NEW_ENTITY_BINDING
    assert override_branch.op == "lookup_bracket_by_entity_type"

    assert fallback_branch.op == "if_then_else"
    incn_predicate, micro_branch, sub_form_branch = fallback_branch.args
    assert incn_predicate.op == "less_than"
    assert incn_predicate.args[0].binding == _INCN_BINDING
    assert incn_predicate.args[1].literal == Decimal("1000000")

    assert micro_branch.op == "lookup_bracket_by_entity_type"
    pyme_dispatch = micro_branch.args[2].dispatch_table
    assert pyme_dispatch is not None
    assert set(pyme_dispatch.values()) == {"is.modelo-200.tipo-gravamen-pyme"}

    assert sub_form_branch.op == "lookup_bracket_by_entity_type"
    sub_form_dispatch = sub_form_branch.args[2].dispatch_table
    assert sub_form_dispatch is not None
    assert sub_form_dispatch["sl"] == "is.modelo-200.cuota-integra-bracket-general"
    assert sub_form_dispatch["cooperativa"] == "is.modelo-200.cuota-integra-bracket-cooperative-protected"
    assert sub_form_dispatch["sin_fines_lucrativos"] == "is.modelo-200.cuota-integra-bracket-non-profit-special-regime"


def test_incn_binding_is_decimal_channel_profile_sourced_and_grounded() -> None:
    """The INCN binding is profile-sourced, Decimal-channel, grounded in LIS Art. 29.

    The micro-empresa gate must read from the operator-declared
    taxpayer profile fact ``incn_prior_12_months`` (no hand-typed
    casilla), arrive on the Decimal binding channel (so the
    ``less_than`` comparison can consume it numerically), and carry
    LIS Art. 29 legal grounding.
    """
    binding = next(
        b for b in _snapshot().revision.bindings if b.id == _INCN_BINDING
    )
    assert binding.source == "profile"
    assert binding.selector.get("field") == "incn_prior_12_months"
    # The Decimal channel is determined by the binding NOT being consumed
    # as an enum-dispatch key anywhere in the formula graph; carrying no
    # ``typed_enum`` is the structural marker.
    assert binding.typed_enum is None
    assert "ley-27-2014:art-29" in binding.legal_refs
