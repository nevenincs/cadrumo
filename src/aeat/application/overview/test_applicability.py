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
* An attribution entity → ``not_applicable`` for 100 / 130 / 200 with
  entity-type-neutral rationale (it is neither persona física nor
  entidad jurídica).
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
    _INCOMPLETE_LEGAL_REFS,
    _INCOMPLETE_UNDECLARED_REASON,
    _INCOMPLETE_UNRULED_REASON,
    _MODELO_APPLICABILITY_RULES,
    ApplicabilityVerdict,
    derive_modelo_applicability,
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


def test_attribution_entity_modelo_200_reason_not_persona_fisica() -> None:
    """An attribution entity (comunidad de bienes / sociedad civil) is
    neither persona física nor entidad jurídica. Its Modelo 200
    not-applicable rationale must not mislabel it a persona física."""

    result = derive_modelo_applicability(_attribution_entity(), "200")
    assert result.verdict is ApplicabilityVerdict.NOT_APPLICABLE
    assert "persona física" not in result.reason
    assert "Impuesto sobre Sociedades" in result.reason


def test_attribution_entity_modelo_100_reason_not_persona_fisica() -> None:
    """Modelo 100's not-applicable rationale for an attribution entity
    must not assert the excluded taxpayer is an entidad jurídica or
    otherwise mislabel it."""

    result = derive_modelo_applicability(_attribution_entity(), "100")
    assert result.verdict is ApplicabilityVerdict.NOT_APPLICABLE
    assert "entidad jurídica" not in result.reason
    assert "personas físicas" in result.reason


def test_attribution_entity_modelo_130_reason_neutral() -> None:
    """Modelo 130's not-applicable rationale for an attribution entity
    must not assert it earns IRPF income categories it cannot have."""

    result = derive_modelo_applicability(_attribution_entity(), "130")
    assert result.verdict is ApplicabilityVerdict.NOT_APPLICABLE
    assert "capital inmobiliario" not in result.reason
    assert "actividades económicas" in result.reason


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
    from aeat.domain.calculations.registry._loader import load_registry_tree

    _modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    registered_legal_ids = set(catalogues.legal)
    assert registered_legal_ids, "registry legal catalogue is empty"

    seed_refs: set[str] = set(_INCOMPLETE_LEGAL_REFS)
    for rule in _MODELO_APPLICABILITY_RULES.values():
        seed_refs.update(rule.legal_refs)
    assert seed_refs, "seed table carries no legal_refs"

    unresolved = sorted(ref for ref in seed_refs if ref not in registered_legal_ids)
    assert not unresolved, f"seed legal_refs absent from the registry: {unresolved}"

    # Every seed key is a scoped article reference, not a bare law slug.
    for ref in sorted(seed_refs):
        assert ":" in ref, f"seed legal_ref is not in scoped article form: {ref!r}"
