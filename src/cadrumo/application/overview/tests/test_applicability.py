"""Real-behaviour persona tests for the modelo-applicability engine.

Each test pins one operator persona and asserts the derived modelo
verdict. Expected modelo sets are taken from the taxpayer-type
applicability research grounding, not hand-invented:

* A pure landlord (capital inmobiliario only) → Modelo 100, NOT 130
  (research §1.1 — a pure landlord, the wrong-guidance defect).
* A salaried-only taxpayer → Modelo 100, no quarterly modelos
  (research §1.1 — rendimientos del trabajo).
* A pensioner → Modelo 100, no quarterly modelos (research §1.1 —
  pensión is a rendimiento del trabajo).
* An autónomo en estimación directa → 130 / 303 (research §1.1, §2.1 —
  the unchanged-by-design persona).
* A sociedad limitada → 200 / 202, NOT 100 / 130 (research §1.2).
* An attribution entity → ``attribution_pass_through`` for the cuota
  modelos 100 / 130 / 200 / 202 (it runs no IS and no IRPF cuota of
  its own) and ``applicable`` for its own informational Modelo 184
  (corporate-entity contract §2).
* An undeclared profile → ``incomplete`` with the undeclared rationale.
* A modelo with no seed rule → ``incomplete`` with the un-ruled
  rationale, distinct from the undeclared one even on a declared
  profile.

Every verdict is the real output of :func:`derive_modelo_applicability`
over a constructed profile, with no shortcut fixtures or circular assertions.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from cadrumo.domain.calculations.registry.applicability import (
    ApplicabilityVerdict,
    derive_modelo_applicability,
    derive_tax_route,
    has_applicability_rule,
    iter_modelo_applicability_rules,
    taxpayer_model_is_declared,
)
from cadrumo.domain.calculations.registry.applicability_routes import TaxRoute
from cadrumo.domain.calculations.registry.legal import verify_legal_catalogue

from ....core import Modelo
from ....core.resources import bundled_path
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.deadlines import (
    EntityType,
    IrpfEstimationRegime,
    IrpfIncomeCategory,
    IVARegime,
    LegalEntityForm,
    TaxpayerProfile,
)
from .calendar_test_support import profile as _autonomo

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ProfileFactory = Callable[[], TaxpayerProfile]


# ---------------------------------------------------------------------
# Persona fixtures — each is a declared three-axis taxpayer model.
# ---------------------------------------------------------------------


def _landlord() -> TaxpayerProfile:
    """A pure landlord: rendimientos del capital inmobiliario only."""

    return TaxpayerProfile(
        tax_id="X1234567L",
        entity_type=EntityType.NATURAL_PERSON,
        irpf_income_categories=frozenset({IrpfIncomeCategory.CAPITAL_INMOBILIARIO}),
        iva_regime=IVARegime.EXENTO,
    )


def _salaried_only() -> TaxpayerProfile:
    """A salaried-only taxpayer: rendimientos del trabajo only."""

    return TaxpayerProfile(
        tax_id="Y2345678Z",
        entity_type=EntityType.NATURAL_PERSON,
        irpf_income_categories=frozenset({IrpfIncomeCategory.TRABAJO}),
        iva_regime=IVARegime.EXENTO,
    )


def _pensioner() -> TaxpayerProfile:
    """A pensioner: pensión only (a rendimiento del trabajo)."""

    return TaxpayerProfile(
        tax_id="Z3456789D",
        entity_type=EntityType.NATURAL_PERSON,
        irpf_income_categories=frozenset({IrpfIncomeCategory.PENSION}),
        iva_regime=IVARegime.EXENTO,
    )


def _sociedad_limitada() -> TaxpayerProfile:
    """A sociedad limitada: an Impuesto sobre Sociedades contribuyente."""

    return TaxpayerProfile(
        tax_id="B12345674",
        entity_type=EntityType.LEGAL_ENTITY,
        legal_entity_form=LegalEntityForm.SL,
        iva_regime=IVARegime.GENERAL,
    )


def _undeclared() -> TaxpayerProfile:
    """A profile with no taxpayer model declared at all."""

    return TaxpayerProfile(tax_id="C5678901I", iva_regime=IVARegime.GENERAL)


def _attribution_entity() -> TaxpayerProfile:
    """An attribution entity: comunidad de bienes / sociedad civil.

    A third entity type — neither persona física nor entidad jurídica —
    under the régimen de atribución de rentas.
    """

    return TaxpayerProfile(
        tax_id="E12345674",
        entity_type=EntityType.ATTRIBUTION_ENTITY,
        iva_regime=IVARegime.GENERAL,
    )


# ---------------------------------------------------------------------
# Landlord — Modelo 100, NOT 130 (wrong-guidance defect closed)
# ---------------------------------------------------------------------


def test_core_personas_route_to_expected_modelo_verdicts() -> None:
    """Core personas map to their expected Renta, IVA, and corporate modelo verdicts."""

    cases = (
        ("landlord-m100", _landlord, "100", ApplicabilityVerdict.APPLICABLE, True, None),
        ("landlord-m130", _landlord, "130", ApplicabilityVerdict.NOT_APPLICABLE, False, "actividades económicas"),
        ("landlord-m303", _landlord, "303", ApplicabilityVerdict.NOT_APPLICABLE, False, None),
        ("landlord-m200", _landlord, "200", ApplicabilityVerdict.NOT_APPLICABLE, False, None),
        ("landlord-m202", _landlord, "202", ApplicabilityVerdict.NOT_APPLICABLE, False, None),
        ("salaried-m100", _salaried_only, "100", ApplicabilityVerdict.APPLICABLE, True, None),
        ("salaried-m130", _salaried_only, "130", ApplicabilityVerdict.NOT_APPLICABLE, False, None),
        ("salaried-m303", _salaried_only, "303", ApplicabilityVerdict.NOT_APPLICABLE, False, None),
        ("salaried-m200", _salaried_only, "200", ApplicabilityVerdict.NOT_APPLICABLE, False, None),
        ("salaried-m202", _salaried_only, "202", ApplicabilityVerdict.NOT_APPLICABLE, False, None),
        ("pensioner-m100", _pensioner, "100", ApplicabilityVerdict.APPLICABLE, True, None),
        ("pensioner-m130", _pensioner, "130", ApplicabilityVerdict.NOT_APPLICABLE, False, None),
        ("pensioner-m303", _pensioner, "303", ApplicabilityVerdict.NOT_APPLICABLE, False, None),
        ("pensioner-m200", _pensioner, "200", ApplicabilityVerdict.NOT_APPLICABLE, False, None),
        ("pensioner-m202", _pensioner, "202", ApplicabilityVerdict.NOT_APPLICABLE, False, None),
        ("autonomo-m100", _autonomo, "100", ApplicabilityVerdict.APPLICABLE, True, None),
        ("autonomo-m130", _autonomo, "130", ApplicabilityVerdict.APPLICABLE, True, None),
        ("autonomo-m303", _autonomo, "303", ApplicabilityVerdict.APPLICABLE, True, None),
        ("autonomo-m200", _autonomo, "200", ApplicabilityVerdict.NOT_APPLICABLE, False, None),
        ("autonomo-m202", _autonomo, "202", ApplicabilityVerdict.NOT_APPLICABLE, False, None),
        ("sl-m100", _sociedad_limitada, "100", ApplicabilityVerdict.NOT_APPLICABLE, False, None),
        ("sl-m130", _sociedad_limitada, "130", ApplicabilityVerdict.NOT_APPLICABLE, False, None),
        ("sl-m200", _sociedad_limitada, "200", ApplicabilityVerdict.APPLICABLE, True, None),
        ("sl-m202", _sociedad_limitada, "202", ApplicabilityVerdict.APPLICABLE, True, None),
        ("sl-m303", _sociedad_limitada, "303", ApplicabilityVerdict.APPLICABLE, True, None),
    )

    for case_id, profile_factory, modelo, expected_verdict, expected_applicable, reason_fragment in cases:
        result = derive_modelo_applicability(profile_factory(), modelo)
        assert result.verdict is expected_verdict, case_id
        assert result.applicable is expected_applicable, case_id
        if expected_applicable:
            assert result.legal_refs, case_id
        if reason_fragment is not None:
            assert reason_fragment in result.reason, case_id


# ---------------------------------------------------------------------
# Undeclared profile — incomplete (the safe default)
# ---------------------------------------------------------------------


def test_undeclared_profile_is_not_declared() -> None:
    """The taxpayer-model declared check is False for an undeclared profile."""

    assert taxpayer_model_is_declared(_undeclared()) is False
    assert taxpayer_model_is_declared(_autonomo()) is True
    assert taxpayer_model_is_declared(_sociedad_limitada()) is True


def test_undeclared_profile_yields_incomplete_for_every_modelo() -> None:
    """An undeclared taxpayer model yields an explicit incomplete
    verdict — never a confident wrong obligation, never the autónomo
    guess."""

    profile = _undeclared()
    for modelo in ("100", "130", "303", "200", "202"):
        result = derive_modelo_applicability(profile, modelo)
        assert result.verdict is ApplicabilityVerdict.INCOMPLETE, modelo
        assert result.applicable is False
        assert "tipo de contribuyente" in result.reason
        assert "config profile edit" in result.reason


def test_natural_person_without_income_categories_is_incomplete() -> None:
    """A natural person who declared no income category is undeclared:
    the engine cannot tell a landlord from an autónomo, so it refuses
    to guess rather than defaulting to autónomo."""

    profile = TaxpayerProfile(
        tax_id="D6789012I",
        entity_type=EntityType.NATURAL_PERSON,
        iva_regime=IVARegime.GENERAL,
    )
    assert taxpayer_model_is_declared(profile) is False
    result = derive_modelo_applicability(profile, "130")
    assert result.verdict is ApplicabilityVerdict.INCOMPLETE


def _an_unruled_modelo() -> str:
    """Return a modelo the engine has no applicability rule for, chosen at run time.

    This was hardcoded as Modelo 232, and it rotted: 232's rule was authored in
    the registry and enrolled, so the test asserting the UN-RULED path began
    asserting it against a ruled modelo. The subject here is the un-ruled
    rationale, not any particular modelo, so the subject is selected from what
    the engine actually reports and cannot go stale the same way.
    """
    unruled = sorted(modelo.value for modelo in Modelo if not has_applicability_rule(modelo.value))
    assert unruled, (
        "every modelo now carries an applicability rule, so the un-ruled rationale is "
        "unreachable and these two tests should be retired along with it"
    )
    return unruled[0]


def test_modelo_without_seed_rule_is_incomplete() -> None:
    """A modelo outside the rule set has no derived rule yet.

    It reports incomplete -- the deferred expansion completes coverage -- rather
    than a confident guess.
    """

    result = derive_modelo_applicability(_autonomo(), _an_unruled_modelo())
    assert result.verdict is ApplicabilityVerdict.INCOMPLETE
    assert "todavía no se ha derivado una regla de aplicabilidad" in result.reason


# ---------------------------------------------------------------------
# INCOMPLETE rationale split — un-ruled modelo vs undeclared profile
# ---------------------------------------------------------------------


def test_unruled_modelo_on_declared_profile_uses_unruled_reason() -> None:
    """A fully declared profile asking about an un-ruled modelo gets the
    *un-ruled* rationale — a statement about rule coverage, not a wrong
    instruction to declare the taxpayer type the operator has already
    declared."""

    profile = _landlord()
    assert taxpayer_model_is_declared(profile) is True

    result = derive_modelo_applicability(profile, _an_unruled_modelo())
    assert result.verdict is ApplicabilityVerdict.INCOMPLETE
    assert "todavía no se ha derivado una regla de aplicabilidad" in result.reason
    # The un-ruled rationale must NOT tell a declared operator to
    # declare their taxpayer type.
    assert "no está declarado" not in result.reason
    assert "config profile edit" not in result.reason
    assert result.legal_refs


def test_unruled_modelo_reason_differs_from_undeclared_reason() -> None:
    """The two INCOMPLETE causes carry structurally distinct prose."""

    unruled = derive_modelo_applicability(_autonomo(), "232")
    undeclared = derive_modelo_applicability(_undeclared(), "100")
    assert unruled.reason != undeclared.reason


def test_undeclared_profile_still_uses_undeclared_reason() -> None:
    """The undeclared-taxpayer path keeps the 'declare your taxpayer
    type first' rationale — that guidance is correct when the profile
    itself is incomplete."""

    result = derive_modelo_applicability(_undeclared(), "100")
    assert result.verdict is ApplicabilityVerdict.INCOMPLETE
    assert "tipo de contribuyente" in result.reason
    assert "config profile edit" in result.reason


def test_natural_person_no_income_categories_uses_undeclared_reason() -> None:
    """A natural person with a category-gated modelo but no declared
    income category is an undeclared taxpayer model — it keeps the
    undeclared rationale, not the un-ruled one."""

    profile = TaxpayerProfile(
        tax_id="F6789012I",
        entity_type=EntityType.NATURAL_PERSON,
        iva_regime=IVARegime.GENERAL,
    )
    result = derive_modelo_applicability(profile, "130")
    assert result.verdict is ApplicabilityVerdict.INCOMPLETE
    assert result.reason == derive_modelo_applicability(_undeclared(), "100").reason


# ---------------------------------------------------------------------
# not_applicable rationale — entity-type-neutral wording
# ---------------------------------------------------------------------


def test_attribution_entity_cuota_modelos_are_pass_through() -> None:
    """An attribution entity asked about a cuota self-assessment
    (Modelo 100 / 130 / 200 / 202) gets the ATTRIBUTION_PASS_THROUGH
    verdict — it runs no IS and no IRPF cuota of its own. This is the
    honest answer to 'what is my cuota': none, the income is taxed in
    the members' returns (corporate-entity contract §2)."""

    profile = _attribution_entity()
    for modelo in ("100", "130", "200", "202"):
        result = derive_modelo_applicability(profile, modelo)
        assert result.verdict is ApplicabilityVerdict.ATTRIBUTION_PASS_THROUGH, modelo
        # A pass-through verdict is not an applicable obligation.
        assert result.applicable is False, modelo


def test_attribution_entity_pass_through_reason_is_honest() -> None:
    """The pass-through rationale states the entity runs no cuota of its
    own and the income is taxed in the members' returns — not a generic
    'modelo does not apply' line."""

    result = derive_modelo_applicability(_attribution_entity(), "200")
    assert result.verdict is ApplicabilityVerdict.ATTRIBUTION_PASS_THROUGH
    assert "atribución de rentas" in result.reason
    assert "cada miembro" in result.reason
    # The pass-through verdict is grounded in the LIRPF attribution
    # articles, not the modelo-specific IS / IRPF refs.
    assert result.legal_refs == ("ley-35-2006:art-86", "ley-35-2006:art-87")


def test_attribution_entity_owes_modelo_184() -> None:
    """Modelo 184 (declaración informativa de atribución de rentas) is
    the attribution entity's OWN obligation — applicable, not a
    pass-through (corporate-entity contract §2)."""

    result = derive_modelo_applicability(_attribution_entity(), "184")
    assert result.verdict is ApplicabilityVerdict.APPLICABLE
    assert result.applicable is True
    assert result.legal_refs


def test_non_attribution_entities_do_not_owe_modelo_184() -> None:
    """Modelo 184 is the attribution entity's own obligation only."""

    for case_id, profile_factory in (("natural-person", _landlord), ("legal-entity", _sociedad_limitada)):
        result = derive_modelo_applicability(profile_factory(), "184")
        assert result.verdict is ApplicabilityVerdict.NOT_APPLICABLE, case_id
        assert result.applicable is False, case_id


def test_attribution_entity_modelo_100_reason_not_persona_fisica() -> None:
    """The Modelo 100 pass-through rationale for an attribution entity
    must not mislabel it a persona física or an entidad jurídica."""

    result = derive_modelo_applicability(_attribution_entity(), "100")
    assert result.verdict is ApplicabilityVerdict.ATTRIBUTION_PASS_THROUGH
    assert "persona física" not in result.reason
    assert "entidad jurídica" not in result.reason


# ---------------------------------------------------------------------
# Tax-routing contract — entity_type selects the tax (contract §4)
# ---------------------------------------------------------------------


_TAX_ROUTE_CASES: tuple[tuple[str, _ProfileFactory, TaxRoute], ...] = (
    ("landlord-irpf", _landlord, TaxRoute.IRPF),
    ("autonomo-irpf", _autonomo, TaxRoute.IRPF),
    ("legal-entity-is", _sociedad_limitada, TaxRoute.IMPUESTO_SOCIEDADES),
    ("attribution-pass-through", _attribution_entity, TaxRoute.ATTRIBUTION_PASS_THROUGH),
    ("undeclared", _undeclared, TaxRoute.INCOMPLETE),
)


def test_entity_type_routes_to_expected_tax_branch() -> None:
    """The entity-type axis selects the tax route and never defaults a tax."""

    for case_id, profile_factory, expected_route in _TAX_ROUTE_CASES:
        assert derive_tax_route(profile_factory()) is expected_route, case_id


def test_no_seed_not_applicable_reason_asserts_excluded_taxpayer_type() -> None:
    """No seed rule's not-applicable rationale may positively assert
    what *other* entity type the excluded taxpayer is — an attribution
    entity is a third type that any such assertion would mislabel."""

    forbidden = (
        "Una persona física tributa",
        "Una entidad jurídica tributa",
    )
    for rule in iter_modelo_applicability_rules():
        for phrase in forbidden:
            assert phrase not in rule.not_applicable_reason, rule.modelo


# ---------------------------------------------------------------------
# Core modelo set — estimación-regime split (Modelo 130 vs 131)
# ---------------------------------------------------------------------


def _autonomo_objetiva() -> TaxpayerProfile:
    """An autónomo en estimación objetiva (módulos)."""

    return TaxpayerProfile(
        tax_id="A4567890A",
        entity_type=EntityType.NATURAL_PERSON,
        irpf_income_categories=frozenset({IrpfIncomeCategory.ACTIVIDAD_ECONOMICA}),
        irpf_estimation_regime=IrpfEstimationRegime.OBJETIVA,
        iva_regime=IVARegime.SIMPLIFICADO,
    )


def _autonomo_simplificada() -> TaxpayerProfile:
    """An autónomo en estimación directa simplificada."""

    return TaxpayerProfile(
        tax_id="A4567890A",
        entity_type=EntityType.NATURAL_PERSON,
        irpf_income_categories=frozenset({IrpfIncomeCategory.ACTIVIDAD_ECONOMICA}),
        irpf_estimation_regime=IrpfEstimationRegime.DIRECTA_SIMPLIFICADA,
        iva_regime=IVARegime.GENERAL,
    )


def test_pago_fraccionado_regime_matrix_routes_modelos_130_and_131() -> None:
    """M130/M131 stay mutually exclusive by estimation regime and taxpayer route."""

    default_directa_profile = TaxpayerProfile(
        tax_id="A4567890A",
        entity_type=EntityType.NATURAL_PERSON,
        irpf_income_categories=frozenset({IrpfIncomeCategory.ACTIVIDAD_ECONOMICA}),
        iva_regime=IVARegime.GENERAL,
    )
    modulos_general_profile = TaxpayerProfile(
        tax_id="A4567890A",
        entity_type=EntityType.NATURAL_PERSON,
        irpf_income_categories=frozenset({IrpfIncomeCategory.ACTIVIDAD_ECONOMICA}),
        iva_regime=IVARegime.GENERAL,
        irpf_estimation_regime=IrpfEstimationRegime.OBJETIVA,
    )
    assert default_directa_profile.irpf_estimation_regime is None
    assert modulos_general_profile.irpf_estimation_regime is IrpfEstimationRegime.OBJETIVA

    cases = (
        ("objetiva-m130", _autonomo_objetiva(), "130", ApplicabilityVerdict.NOT_APPLICABLE, False),
        ("objetiva-m131", _autonomo_objetiva(), "131", ApplicabilityVerdict.APPLICABLE, True),
        ("directa-normal-m130", _autonomo(), "130", ApplicabilityVerdict.APPLICABLE, True),
        ("directa-normal-m131", _autonomo(), "131", ApplicabilityVerdict.NOT_APPLICABLE, False),
        ("directa-simplificada-m130", _autonomo_simplificada(), "130", ApplicabilityVerdict.APPLICABLE, True),
        ("directa-simplificada-m131", _autonomo_simplificada(), "131", ApplicabilityVerdict.NOT_APPLICABLE, False),
        ("default-directa-m130", default_directa_profile, "130", ApplicabilityVerdict.APPLICABLE, True),
        ("default-directa-m131", default_directa_profile, "131", ApplicabilityVerdict.NOT_APPLICABLE, False),
        ("modulos-general-m130", modulos_general_profile, "130", ApplicabilityVerdict.NOT_APPLICABLE, False),
        ("modulos-general-m131", modulos_general_profile, "131", ApplicabilityVerdict.APPLICABLE, True),
        ("landlord-m131", _landlord(), "131", ApplicabilityVerdict.NOT_APPLICABLE, False),
        ("sl-m130", _sociedad_limitada(), "130", ApplicabilityVerdict.NOT_APPLICABLE, False),
        ("sl-m131", _sociedad_limitada(), "131", ApplicabilityVerdict.NOT_APPLICABLE, False),
        ("attribution-m131", _attribution_entity(), "131", ApplicabilityVerdict.ATTRIBUTION_PASS_THROUGH, False),
    )

    for case_id, profile, modelo, expected_verdict, expected_applicable in cases:
        result = derive_modelo_applicability(profile, modelo)
        assert result.verdict is expected_verdict, case_id
        assert result.applicable is expected_applicable, case_id


# ---------------------------------------------------------------------
# Core modelo set — Modelo 390 (annual IVA companion to 303)
# ---------------------------------------------------------------------


_MODELO_390_CASES: tuple[tuple[str, _ProfileFactory, ApplicabilityVerdict, bool], ...] = (
    ("autonomo", _autonomo, ApplicabilityVerdict.APPLICABLE, True),
    ("legal-entity", _sociedad_limitada, ApplicabilityVerdict.APPLICABLE, True),
    ("attribution-entity", _attribution_entity, ApplicabilityVerdict.APPLICABLE, True),
    ("landlord", _landlord, ApplicabilityVerdict.NOT_APPLICABLE, False),
)


def test_modelo_390_follows_iva_subject_activity_gate() -> None:
    """Modelo 390 follows the annual IVA-summary gate for each core persona."""

    for case_id, profile_factory, expected_verdict, expected_applicable in _MODELO_390_CASES:
        result = derive_modelo_applicability(profile_factory(), "390")
        assert result.verdict is expected_verdict, case_id
        assert result.applicable is expected_applicable, case_id


def test_modelo_390_tracks_modelo_303_verdict() -> None:
    """Modelo 390 is the annual companion to Modelo 303: the two carry
    the same applicability gate for every core persona."""

    for profile in (_landlord(), _salaried_only(), _autonomo(), _sociedad_limitada(), _attribution_entity()):
        m303 = derive_modelo_applicability(profile, "303")
        m390 = derive_modelo_applicability(profile, "390")
        assert m303.verdict is m390.verdict, profile.tax_id


# ---------------------------------------------------------------------
# Core modelo set — payer-fact modelos (111 / 115 / 190 / 180 / 349 / 347)
# ---------------------------------------------------------------------


def test_payer_fact_modelos_apply_when_required_fact_is_declared() -> None:
    """Payer-fact modelos apply when their specific taxpayer fact is positively declared."""

    m123_legal_refs = (
        "ley-35-2006:art-25",
        "ley-35-2006:art-99",
        "orden-eha-3435-2007:anexo-ii",
        "orden-hac-56-2024:art-1",
        "rd-439-2007:art-108",
        "rd-439-2007:art-90",
        "ley-35-2006:art-101",
    )
    autonomo_pays_salaries = TaxpayerProfile(
        tax_id="A4567890A",
        entity_type=EntityType.NATURAL_PERSON,
        irpf_income_categories=frozenset({IrpfIncomeCategory.ACTIVIDAD_ECONOMICA}),
        irpf_estimation_regime=IrpfEstimationRegime.DIRECTA_NORMAL,
        iva_regime=IVARegime.GENERAL,
        has_employees=True,
    )
    autonomo_pays_rent = TaxpayerProfile(
        tax_id="A4567890A",
        entity_type=EntityType.NATURAL_PERSON,
        irpf_income_categories=frozenset({IrpfIncomeCategory.ACTIVIDAD_ECONOMICA}),
        irpf_estimation_regime=IrpfEstimationRegime.DIRECTA_NORMAL,
        iva_regime=IVARegime.GENERAL,
        pays_rent_with_retencion=True,
    )
    autonomo_above_347_threshold = TaxpayerProfile(
        tax_id="A4567890A",
        entity_type=EntityType.NATURAL_PERSON,
        irpf_income_categories=frozenset({IrpfIncomeCategory.ACTIVIDAD_ECONOMICA}),
        irpf_estimation_regime=IrpfEstimationRegime.DIRECTA_NORMAL,
        iva_regime=IVARegime.GENERAL,
        third_party_transactions_above_347_threshold=True,
    )
    legal_entity_pays_professionals = TaxpayerProfile(
        tax_id="B12345674",
        entity_type=EntityType.LEGAL_ENTITY,
        legal_entity_form=LegalEntityForm.SL,
        iva_regime=IVARegime.GENERAL,
        pays_professionals_with_retencion=True,
    )
    legal_entity_pays_capital_income = TaxpayerProfile(
        tax_id="B12345674",
        entity_type=EntityType.LEGAL_ENTITY,
        legal_entity_form=LegalEntityForm.SL,
        iva_regime=IVARegime.GENERAL,
        pays_capital_income_with_retencion=True,
    )
    legal_entity_intracommunity = TaxpayerProfile(
        tax_id="B12345674",
        entity_type=EntityType.LEGAL_ENTITY,
        legal_entity_form=LegalEntityForm.SL,
        iva_regime=IVARegime.GENERAL,
        does_intracomunitario=True,
    )
    cases = (
        ("m111-salaries", autonomo_pays_salaries, "111", None),
        ("m111-professionals", legal_entity_pays_professionals, "111", None),
        ("m115-rent", autonomo_pays_rent, "115", None),
        ("m123-capital-income", legal_entity_pays_capital_income, "123", m123_legal_refs),
        ("m349-intracommunity", legal_entity_intracommunity, "349", None),
        ("m347-third-party-threshold", autonomo_above_347_threshold, "347", None),
    )

    for case_id, profile, modelo, expected_legal_refs in cases:
        result = derive_modelo_applicability(profile, modelo)
        assert result.verdict is ApplicabilityVerdict.APPLICABLE, case_id
        assert result.applicable is True, case_id
        if expected_legal_refs is not None:
            assert result.legal_refs == expected_legal_refs, case_id


def test_modelo_111_incomplete_when_payer_fact_not_declared() -> None:
    """When the taxpayer does not positively declare paying withheld
    income, Modelo 111 is INCOMPLETE — the boolean has no tri-state, so
    the engine refuses to guess a NOT_APPLICABLE it cannot justify."""

    result = derive_modelo_applicability(_autonomo(), "111")
    assert result.verdict is ApplicabilityVerdict.INCOMPLETE
    assert "depende de un hecho que el perfil no expresa con certeza" in result.reason
    # The undetermined rationale must not tell a declared operator to
    # declare their taxpayer type — the taxpayer model IS declared.
    assert "config profile edit" not in result.reason


def test_modelo_190_tracks_modelo_111_payer_fact() -> None:
    """Modelo 190 is the annual companion to Modelo 111: both gate on
    the same withholding-payer fact and carry the same verdict."""

    paying = TaxpayerProfile(
        tax_id="A4567890A",
        entity_type=EntityType.NATURAL_PERSON,
        irpf_income_categories=frozenset({IrpfIncomeCategory.ACTIVIDAD_ECONOMICA}),
        irpf_estimation_regime=IrpfEstimationRegime.DIRECTA_NORMAL,
        iva_regime=IVARegime.GENERAL,
        has_employees=True,
    )
    attribution_paying = _attribution_entity().model_copy(update={"has_employees": True})
    assert derive_modelo_applicability(paying, "190").verdict is (ApplicabilityVerdict.APPLICABLE)
    assert derive_modelo_applicability(attribution_paying, "190").verdict is (ApplicabilityVerdict.APPLICABLE)
    assert derive_modelo_applicability(_autonomo(), "190").verdict is (ApplicabilityVerdict.INCOMPLETE)
    assert derive_modelo_applicability(_attribution_entity(), "190").verdict is (ApplicabilityVerdict.INCOMPLETE)


def test_payer_fact_modelos_are_incomplete_when_required_fact_not_declared() -> None:
    """Payer-fact modelos stay INCOMPLETE when their specific fact is not declared."""

    for modelo in ("115", "123", "349", "347"):
        result = derive_modelo_applicability(_autonomo(), modelo)
        assert result.verdict is ApplicabilityVerdict.INCOMPLETE, modelo


def test_modelo_180_tracks_modelo_115_payer_fact() -> None:
    """Modelo 180 is the annual companion to Modelo 115: same rent
    payer fact, same verdict."""

    paying = TaxpayerProfile(
        tax_id="B12345674",
        entity_type=EntityType.LEGAL_ENTITY,
        legal_entity_form=LegalEntityForm.SL,
        iva_regime=IVARegime.GENERAL,
        pays_rent_with_retencion=True,
    )
    assert derive_modelo_applicability(paying, "180").verdict is (ApplicabilityVerdict.APPLICABLE)
    assert derive_modelo_applicability(_sociedad_limitada(), "180").verdict is (ApplicabilityVerdict.INCOMPLETE)


def test_attribution_entity_with_required_fact_owes_fact_gated_modelos() -> None:
    """Attribution entities can owe payer/informative modelos for their own facts."""

    cases = (
        ("115", {"pays_rent_with_retencion": True}),
        ("180", {"pays_rent_with_retencion": True}),
        ("123", {"pays_capital_income_with_retencion": True}),
        ("349", {"does_intracomunitario": True}),
        ("347", {"third_party_transactions_above_347_threshold": True}),
    )

    for modelo, payer_fact_update in cases:
        profile = _attribution_entity().model_copy(update=payer_fact_update)

        result = derive_modelo_applicability(profile, modelo)

        assert result.verdict is ApplicabilityVerdict.APPLICABLE, modelo


def test_attribution_entity_without_required_fact_is_incomplete_for_fact_gated_modelos() -> None:
    """Undeclared payer/trade facts stay INCOMPLETE for attribution entities."""

    for modelo in ("115", "180", "123", "349", "347"):
        result = derive_modelo_applicability(_attribution_entity(), modelo)

        assert result.verdict is ApplicabilityVerdict.INCOMPLETE, modelo


def test_undetermined_reason_distinct_from_undeclared_and_unruled() -> None:
    """The payer-fact INCOMPLETE rationale is structurally distinct from
    both the undeclared-taxpayer and the un-ruled-modelo rationales."""

    undetermined = derive_modelo_applicability(_autonomo(), "111")
    undeclared = derive_modelo_applicability(_undeclared(), "100")
    unruled = derive_modelo_applicability(_autonomo(), "232")

    assert undetermined.reason != undeclared.reason
    assert undetermined.reason != unruled.reason


# ---------------------------------------------------------------------
# Registry grounding — every seed legal_ref must resolve in the registry
# ---------------------------------------------------------------------


def test_seed_legal_refs_resolve_against_the_registry() -> None:
    """Every ``legal_refs`` key carried by the seed applicability table
    must point at a real, corpus-backed registry legal entity.

    Per ``.claude/rules/aeat-calculation-grounding.md``, every typed-ID
    reference must resolve against an existing registry entity — no
    invented BOE / AEAT slugs. This test loads the committed registry
    legal catalogue and asserts each seed key (rule table plus the
    undeclared-profile refs) is a member of it; a fabricated or
    law-only slug would fail loudly here.
    """

    registered_legal_ids = set(bundled_authority().catalogues.legal)
    assert registered_legal_ids, "registry legal catalogue is empty"

    seed_refs: set[str] = set()
    for profile, modelo in (
        (_undeclared(), "100"),
        (_autonomo(), "111"),
        (_autonomo(), "232"),
        (_attribution_entity(), "200"),
    ):
        seed_refs.update(derive_modelo_applicability(profile, modelo).legal_refs)
    for rule in iter_modelo_applicability_rules():
        seed_refs.update(rule.legal_refs)
    assert seed_refs, "seed table carries no legal_refs"

    unresolved = sorted(ref for ref in seed_refs if ref not in registered_legal_ids)
    assert not unresolved, f"seed legal_refs absent from the registry: {unresolved}"

    # Every seed key is a scoped article reference, not a bare law slug.
    for ref in sorted(seed_refs):
        assert ":" in ref, f"seed legal_ref is not in scoped article form: {ref!r}"

    legal_refs = {ref: bundled_authority().catalogues.legal[ref] for ref in sorted(seed_refs)}
    verify_legal_catalogue(legal_refs, source_root=bundled_path())
