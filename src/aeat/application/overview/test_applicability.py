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
  (corporate-entity ADR §2).
* An undeclared profile → ``incomplete`` with the undeclared rationale.
* A modelo with no seed rule → ``incomplete`` with the un-ruled
  rationale, distinct from the undeclared one even on a declared
  profile.

No mocks, no skips, no tautologies — every verdict is the real output
of :func:`derive_modelo_applicability` over a constructed profile.
"""

from __future__ import annotations

import pytest

from aeat.domain.deadlines import TaxpayerProfile
from aeat.domain.deadlines._models import (
    EntityType,
    IrpfEstimationRegime,
    IrpfIncomeCategory,
    IVARegime,
    LegalEntityForm,
)

from ._applicability import (
    _ATTRIBUTION_PASS_THROUGH_LEGAL_REFS,
    _INCOMPLETE_LEGAL_REFS,
    _INCOMPLETE_UNDECLARED_REASON,
    _INCOMPLETE_UNRULED_REASON,
    _MODELO_APPLICABILITY_RULES,
    ApplicabilityVerdict,
    TaxRoute,
    derive_modelo_applicability,
    derive_tax_route,
    taxpayer_model_is_declared,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


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
        tax_id="Z3456789A",
        entity_type=EntityType.NATURAL_PERSON,
        irpf_income_categories=frozenset({IrpfIncomeCategory.PENSION}),
        iva_regime=IVARegime.EXENTO,
    )


def _autonomo() -> TaxpayerProfile:
    """An autónomo en estimación directa: actividad económica."""

    return TaxpayerProfile(
        tax_id="A4567890B",
        entity_type=EntityType.NATURAL_PERSON,
        irpf_income_categories=frozenset({IrpfIncomeCategory.ACTIVIDAD_ECONOMICA}),
        irpf_estimation_regime=IrpfEstimationRegime.DIRECTA_NORMAL,
        iva_regime=IVARegime.GENERAL,
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

    return TaxpayerProfile(tax_id="C5678901C", iva_regime=IVARegime.GENERAL)


def _attribution_entity() -> TaxpayerProfile:
    """An attribution entity: comunidad de bienes / sociedad civil.

    A third entity type — neither persona física nor entidad jurídica —
    under the régimen de atribución de rentas.
    """

    return TaxpayerProfile(
        tax_id="E12345678",
        entity_type=EntityType.ATTRIBUTION_ENTITY,
        iva_regime=IVARegime.GENERAL,
    )


# ---------------------------------------------------------------------
# Landlord — Modelo 100, NOT 130 (wrong-guidance defect closed)
# ---------------------------------------------------------------------


def test_landlord_owes_modelo_100() -> None:
    """A pure landlord is a natural person and files the Renta."""

    result = derive_modelo_applicability(_landlord(), "100")
    assert result.verdict is ApplicabilityVerdict.APPLICABLE
    assert result.applicable is True
    assert result.legal_refs


def test_landlord_does_not_owe_modelo_130() -> None:
    """A landlord has no actividad económica and
    therefore no Modelo 130 obligation — verdict NOT_APPLICABLE, never
    'applicable and overdue'."""

    result = derive_modelo_applicability(_landlord(), "130")
    assert result.verdict is ApplicabilityVerdict.NOT_APPLICABLE
    assert result.applicable is False
    assert "actividades económicas" in result.reason


def test_landlord_does_not_owe_modelo_303() -> None:
    """A landlord with no actividad económica owes no periodic IVA."""

    result = derive_modelo_applicability(_landlord(), "303")
    assert result.verdict is ApplicabilityVerdict.NOT_APPLICABLE
    assert result.applicable is False


def test_landlord_does_not_owe_corporate_modelos() -> None:
    """A natural-person landlord never files the Impuesto sobre Sociedades."""

    for modelo in ("200", "202"):
        result = derive_modelo_applicability(_landlord(), modelo)
        assert result.verdict is ApplicabilityVerdict.NOT_APPLICABLE, modelo


# ---------------------------------------------------------------------
# Salaried-only — Modelo 100, no quarterly modelos
# ---------------------------------------------------------------------


def test_salaried_only_owes_modelo_100() -> None:
    result = derive_modelo_applicability(_salaried_only(), "100")
    assert result.verdict is ApplicabilityVerdict.APPLICABLE


def test_salaried_only_owes_no_quarterly_modelos() -> None:
    """A salaried-only taxpayer has no quarterly filing obligations."""

    for modelo in ("130", "303", "200", "202"):
        result = derive_modelo_applicability(_salaried_only(), modelo)
        assert result.verdict is ApplicabilityVerdict.NOT_APPLICABLE, modelo
        assert result.applicable is False


# ---------------------------------------------------------------------
# Pensioner — Modelo 100, no quarterly modelos
# ---------------------------------------------------------------------


def test_pensioner_owes_modelo_100() -> None:
    result = derive_modelo_applicability(_pensioner(), "100")
    assert result.verdict is ApplicabilityVerdict.APPLICABLE


def test_pensioner_owes_no_quarterly_modelos() -> None:
    """A pensioner has no quarterly filing obligations."""

    for modelo in ("130", "303", "200", "202"):
        result = derive_modelo_applicability(_pensioner(), modelo)
        assert result.verdict is ApplicabilityVerdict.NOT_APPLICABLE, modelo


# ---------------------------------------------------------------------
# Autónomo — 130 / 303 unchanged
# ---------------------------------------------------------------------


def test_autonomo_owes_modelo_130_and_303() -> None:
    """The autónomo persona is unchanged: 130 and 303 still apply."""

    profile = _autonomo()
    for modelo in ("130", "303"):
        result = derive_modelo_applicability(profile, modelo)
        assert result.verdict is ApplicabilityVerdict.APPLICABLE, modelo
        assert result.applicable is True


def test_autonomo_owes_modelo_100() -> None:
    """An autónomo is still a natural person and files the Renta."""

    result = derive_modelo_applicability(_autonomo(), "100")
    assert result.verdict is ApplicabilityVerdict.APPLICABLE


def test_autonomo_does_not_owe_corporate_modelos() -> None:
    """A natural-person autónomo never files corporate modelos."""

    for modelo in ("200", "202"):
        result = derive_modelo_applicability(_autonomo(), modelo)
        assert result.verdict is ApplicabilityVerdict.NOT_APPLICABLE, modelo


# ---------------------------------------------------------------------
# Sociedad limitada — 200 / 202, NOT 100 / 130
# ---------------------------------------------------------------------


def test_sociedad_limitada_owes_corporate_modelos() -> None:
    """An S.L. files the Impuesto sobre Sociedades: Modelo 200 and 202."""

    profile = _sociedad_limitada()
    for modelo in ("200", "202"):
        result = derive_modelo_applicability(profile, modelo)
        assert result.verdict is ApplicabilityVerdict.APPLICABLE, modelo
        assert result.applicable is True
        assert result.legal_refs


def test_sociedad_limitada_does_not_owe_irpf_modelos() -> None:
    """An S.L. is not an IRPF taxpayer: no Modelo 100, no Modelo 130."""

    profile = _sociedad_limitada()
    for modelo in ("100", "130"):
        result = derive_modelo_applicability(profile, modelo)
        assert result.verdict is ApplicabilityVerdict.NOT_APPLICABLE, modelo
        assert result.applicable is False


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
        tax_id="D6789012D",
        entity_type=EntityType.NATURAL_PERSON,
        iva_regime=IVARegime.GENERAL,
    )
    assert taxpayer_model_is_declared(profile) is False
    result = derive_modelo_applicability(profile, "130")
    assert result.verdict is ApplicabilityVerdict.INCOMPLETE


def test_modelo_without_seed_rule_is_incomplete() -> None:
    """A modelo outside the seed rule set has no derived rule yet:
    it reports incomplete (the deferred expansion completes coverage)
    rather than a confident guess."""

    result = derive_modelo_applicability(_autonomo(), "349")
    assert result.verdict is ApplicabilityVerdict.INCOMPLETE


# ---------------------------------------------------------------------
# INCOMPLETE rationale split — un-ruled modelo vs undeclared profile
# ---------------------------------------------------------------------


def test_unruled_modelo_on_declared_profile_uses_unruled_reason() -> None:
    """A fully declared profile asking about an un-ruled modelo (131)
    gets the *un-ruled* rationale — a statement about seed coverage, not
    a wrong instruction to declare the taxpayer type the operator has
    already declared."""

    profile = _landlord()
    assert taxpayer_model_is_declared(profile) is True

    result = derive_modelo_applicability(profile, "131")
    assert result.verdict is ApplicabilityVerdict.INCOMPLETE
    assert result.reason == _INCOMPLETE_UNRULED_REASON
    # The un-ruled rationale must NOT tell a declared operator to
    # declare their taxpayer type.
    assert "no está declarado" not in result.reason
    assert "config profile edit" not in result.reason
    assert result.legal_refs


def test_unruled_modelo_reason_differs_from_undeclared_reason() -> None:
    """The two INCOMPLETE causes carry structurally distinct prose."""

    assert _INCOMPLETE_UNRULED_REASON != _INCOMPLETE_UNDECLARED_REASON
    unruled = derive_modelo_applicability(_autonomo(), "131")
    undeclared = derive_modelo_applicability(_undeclared(), "100")
    assert unruled.reason != undeclared.reason


def test_undeclared_profile_still_uses_undeclared_reason() -> None:
    """The undeclared-taxpayer path keeps the 'declare your taxpayer
    type first' rationale — that guidance is correct when the profile
    itself is incomplete."""

    result = derive_modelo_applicability(_undeclared(), "100")
    assert result.verdict is ApplicabilityVerdict.INCOMPLETE
    assert result.reason == _INCOMPLETE_UNDECLARED_REASON
    assert "tipo de contribuyente" in result.reason
    assert "config profile edit" in result.reason


def test_natural_person_no_income_categories_uses_undeclared_reason() -> None:
    """A natural person with a category-gated modelo but no declared
    income category is an undeclared taxpayer model — it keeps the
    undeclared rationale, not the un-ruled one."""

    profile = TaxpayerProfile(
        tax_id="F6789012F",
        entity_type=EntityType.NATURAL_PERSON,
        iva_regime=IVARegime.GENERAL,
    )
    result = derive_modelo_applicability(profile, "130")
    assert result.verdict is ApplicabilityVerdict.INCOMPLETE
    assert result.reason == _INCOMPLETE_UNDECLARED_REASON


# ---------------------------------------------------------------------
# not_applicable rationale — entity-type-neutral wording
# ---------------------------------------------------------------------


def test_attribution_entity_cuota_modelos_are_pass_through() -> None:
    """An attribution entity asked about a cuota self-assessment
    (Modelo 100 / 130 / 200 / 202) gets the ATTRIBUTION_PASS_THROUGH
    verdict — it runs no IS and no IRPF cuota of its own. This is the
    honest answer to 'what is my cuota': none, the income is taxed in
    the members' returns (corporate-entity ADR §2)."""

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
    assert result.legal_refs == _ATTRIBUTION_PASS_THROUGH_LEGAL_REFS


def test_attribution_entity_owes_modelo_184() -> None:
    """Modelo 184 (declaración informativa de atribución de rentas) is
    the attribution entity's OWN obligation — applicable, not a
    pass-through (corporate-entity ADR §2)."""

    result = derive_modelo_applicability(_attribution_entity(), "184")
    assert result.verdict is ApplicabilityVerdict.APPLICABLE
    assert result.applicable is True
    assert result.legal_refs


def test_natural_person_does_not_owe_modelo_184() -> None:
    """Modelo 184 is informational, not cuota-bearing: a natural person
    asked about it gets a plain NOT_APPLICABLE, never a pass-through."""

    result = derive_modelo_applicability(_landlord(), "184")
    assert result.verdict is ApplicabilityVerdict.NOT_APPLICABLE
    assert result.applicable is False


def test_legal_entity_does_not_owe_modelo_184() -> None:
    """A sociedad limitada is not an attribution entity: Modelo 184
    does not apply, and the verdict is a plain NOT_APPLICABLE."""

    result = derive_modelo_applicability(_sociedad_limitada(), "184")
    assert result.verdict is ApplicabilityVerdict.NOT_APPLICABLE


def test_attribution_entity_modelo_100_reason_not_persona_fisica() -> None:
    """The Modelo 100 pass-through rationale for an attribution entity
    must not mislabel it a persona física or an entidad jurídica."""

    result = derive_modelo_applicability(_attribution_entity(), "100")
    assert result.verdict is ApplicabilityVerdict.ATTRIBUTION_PASS_THROUGH
    assert "persona física" not in result.reason
    assert "entidad jurídica" not in result.reason


# ---------------------------------------------------------------------
# Tax-routing contract — entity_type selects the tax (ADR §4)
# ---------------------------------------------------------------------


def test_natural_person_routes_to_irpf() -> None:
    """A natural-person profile routes to the IRPF tax branch."""

    assert derive_tax_route(_landlord()) is TaxRoute.IRPF
    assert derive_tax_route(_autonomo()) is TaxRoute.IRPF


def test_legal_entity_routes_to_impuesto_sociedades() -> None:
    """A legal-entity profile routes to the Impuesto sobre Sociedades
    branch — never the IRPF tarifa (corporate-entity ADR §4)."""

    assert derive_tax_route(_sociedad_limitada()) is TaxRoute.IMPUESTO_SOCIEDADES


def test_attribution_entity_routes_to_pass_through() -> None:
    """An attribution-entity profile routes to the member pass-through —
    no IS and no IRPF cuota of its own."""

    assert derive_tax_route(_attribution_entity()) is TaxRoute.ATTRIBUTION_PASS_THROUGH


def test_undeclared_entity_type_routes_incomplete() -> None:
    """An undeclared entity_type yields an INCOMPLETE route — the engine
    never defaults a tax (corporate-entity ADR §4 safe default)."""

    assert derive_tax_route(_undeclared()) is TaxRoute.INCOMPLETE


def test_no_seed_not_applicable_reason_asserts_excluded_taxpayer_type() -> None:
    """No seed rule's not-applicable rationale may positively assert
    what *other* entity type the excluded taxpayer is — an attribution
    entity is a third type that any such assertion would mislabel."""

    forbidden = (
        "Una persona física tributa",
        "Una entidad jurídica tributa",
    )
    for rule in _MODELO_APPLICABILITY_RULES.values():
        for phrase in forbidden:
            assert phrase not in rule.not_applicable_reason, rule.modelo


# ---------------------------------------------------------------------
# Registry grounding — every seed legal_ref must resolve in the registry
# ---------------------------------------------------------------------


def test_seed_legal_refs_resolve_against_the_registry() -> None:
    """Every ``legal_refs`` key carried by the seed applicability table
    must point at a real registry legal entity.

    Per ``.claude/rules/aeat-calculation-grounding.md``, every typed-ID
    reference must resolve against an existing registry entity — no
    invented BOE / AEAT slugs. This test loads the committed registry
    legal catalogue and asserts each seed key (rule table plus the
    undeclared-profile refs) is a member of it; a fabricated or
    law-only slug would fail loudly here.
    """

    from aeat.core.resources import bundled_path
    from aeat.domain.calculations.registry import ValidatedRegistryAuthority

    authority = ValidatedRegistryAuthority.load(
        bundled_path("registry", "aeat"), source_root=bundled_path()
    )
    registered_legal_ids = set(authority.catalogues.legal)
    assert registered_legal_ids, "registry legal catalogue is empty"

    seed_refs: set[str] = set(_INCOMPLETE_LEGAL_REFS)
    seed_refs.update(_ATTRIBUTION_PASS_THROUGH_LEGAL_REFS)
    for rule in _MODELO_APPLICABILITY_RULES.values():
        seed_refs.update(rule.legal_refs)
    assert seed_refs, "seed table carries no legal_refs"

    unresolved = sorted(ref for ref in seed_refs if ref not in registered_legal_ids)
    assert not unresolved, f"seed legal_refs absent from the registry: {unresolved}"

    # Every seed key is a scoped article reference, not a bare law slug.
    for ref in sorted(seed_refs):
        assert ":" in ref, f"seed legal_ref is not in scoped article form: {ref!r}"
