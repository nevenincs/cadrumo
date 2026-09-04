"""Modelo 840's applicability follows TRLRHL art. 82, not the shape of the form.

The Impuesto sobre Actividades Económicas taxes the mere exercise of a business,
professional or artistic activity in Spanish territory (TRLRHL art. 78), and
Modelo 840 is how a sujeto pasivo declares its alta, variación or baja in the
impuesto's matrícula (art. 90; Orden HAC/2572/2003, apartado primero).

The rule that decides who this modelo reaches is the EXEMPTION article, read from
the bundled consolidated text: art. 82.1.c) exempts "las personas físicas, sean o
no residentes en territorio español" with no turnover condition attached, so a
natural person never causes alta through this modelo however large the activity.
The same letter exempts IS taxpayers and art. 35.4 LGT entities only while their
importe neto de la cifra de negocios stays below 1.000.000 euros -- a conditional
exemption on an axis the taxpayer profile does not carry, which is why the rule
scopes on entity type and leaves the turnover cut to be resolved elsewhere.

These are real-profile verdicts through the production derivation, so a rule
edited to a shape the engine reads differently fails here rather than merely
loading.
"""

from __future__ import annotations

import pytest

from ....deadlines.models import (
    FiscalResidency,
    IrpfIncomeCategory,
    IVARegime,
    TaxpayerProfile,
)
from ....contribuyente.entity_type import EntityType, LegalEntityForm
from ..applicability import ApplicabilityVerdict, derive_modelo_applicability
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO = "840"


def _sociedad() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="B12345674",
        entity_type=EntityType.LEGAL_ENTITY,
        legal_entity_form=LegalEntityForm.SL,
        fiscal_residency=FiscalResidency.RESIDENT_IRPF,
        iva_regime=IVARegime.GENERAL,
    )


def _comunidad_de_bienes() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="E12345674",
        entity_type=EntityType.ATTRIBUTION_ENTITY,
        fiscal_residency=FiscalResidency.RESIDENT_IRPF,
        iva_regime=IVARegime.GENERAL,
    )


def _persona_fisica() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="A45678901",
        entity_type=EntityType.NATURAL_PERSON,
        fiscal_residency=FiscalResidency.RESIDENT_IRPF,
        # A natural person carrying on an economic activity is the case the
        # exemption actually has to answer: art. 82.1.c) exempts them anyway.
        # Without an income category the engine reports INCOMPLETE rather
        # than judging, so this profile must declare one for the verdict to
        # be about the exemption at all.
        irpf_income_categories=frozenset({IrpfIncomeCategory.ACTIVIDAD_ECONOMICA}),
        iva_regime=IVARegime.GENERAL,
    )


def test_a_sociedad_is_a_sujeto_pasivo_of_the_iae() -> None:
    result = derive_modelo_applicability(_sociedad(), _MODELO)
    assert result.verdict is ApplicabilityVerdict.APPLICABLE
    assert result.applicable is True


def test_an_attribution_entity_is_a_sujeto_pasivo_of_the_iae() -> None:
    """Art. 35.4 LGT entities are sujetos pasivos in their own right.

    The IAE is not an income tax, so the attribution of income to the members
    does not carry the activity out of the entity: the entity exercises it and
    the entity causes alta in the matrícula.
    """
    result = derive_modelo_applicability(_comunidad_de_bienes(), _MODELO)
    assert result.verdict is ApplicabilityVerdict.APPLICABLE


def test_a_natural_person_is_exempt_and_gets_a_plain_not_applicable() -> None:
    """Art. 82.1.c) exempts natural persons outright, with no turnover condition.

    The verdict must be a plain NOT_APPLICABLE and never ATTRIBUTION_PASS_THROUGH:
    that verdict is reserved for a cuota SELF-ASSESSMENT whose income is taxed in
    the members' returns, and Modelo 840 assesses no cuota at all.
    """
    result = derive_modelo_applicability(_persona_fisica(), _MODELO)
    assert result.verdict is ApplicabilityVerdict.NOT_APPLICABLE
    assert result.applicable is False


def test_the_rule_is_not_a_cuota_self_assessment() -> None:
    """The IAE cuota is liquidated by the administration from the matrícula.

    Modelo 840 declares census facts (alta, variación, baja); it does not
    self-assess a cuota, which is what ``cuota_bearing`` marks. Declaring it
    cuota-bearing would also change the natural-person verdict above for
    attribution entities, so the flag is load-bearing rather than decorative.
    """
    modelo, _catalogues = _committed_modelo(_MODELO)
    revision = modelo.revisions["2003-y-siguientes"]
    rules = revision.applicability
    assert len(rules) == 1, [rule.id for rule in rules]

    rule = rules[0]
    assert rule.cuota_bearing is False
    assert set(rule.applicable_entity_types) == {"legal_entity", "attribution_entity"}
    assert EntityType.NATURAL_PERSON.value not in rule.applicable_entity_types


def test_the_rule_cites_the_articles_its_prose_relies_on() -> None:
    """Every article the reasons argue from must be a resolvable citation.

    The exemption text carries the whole verdict, so a rule that argued from art.
    82 without citing it would leave the operator-facing reason ungrounded.
    """
    modelo, catalogues = _committed_modelo(_MODELO)
    rule = modelo.revisions["2003-y-siguientes"].applicability[0]

    assert "rdl-2-2004:art-82" in rule.legal_refs, rule.legal_refs
    assert "rdl-2-2004:art-78" in rule.legal_refs, rule.legal_refs
    for ref in rule.legal_refs:
        assert ref in catalogues.legal, f"{ref} does not resolve in the legal catalogue"

    exemption = catalogues.legal["rdl-2-2004:art-82"]
    assert exemption.corpus_ref, "art. 82 must point at bundled corpus text"
    # The figure the prose states is the one the catalogue entry is validated
    # against, so the reason cannot drift from the corpus behind its citation.
    assert "1.000.000" in " ".join(exemption.required_text)


def test_residency_scope_matches_what_the_profile_can_answer() -> None:
    """The non-resident route is deliberately out of scope, and says why.

    Art. 82.1.c) makes the IRNR exemption conditional on operating through an
    establecimiento permanente. The profile carries no such axis, so asserting a
    verdict for a non-resident would be answering a question the model cannot
    ask -- the same reason Modelo 200 gives for its own residency scope.
    """
    modelo, _catalogues = _committed_modelo(_MODELO)
    rule = modelo.revisions["2003-y-siguientes"].applicability[0]

    assert set(rule.applicable_fiscal_residencies) == {FiscalResidency.RESIDENT_IRPF.value}
    assert "establecimiento permanente" in rule.not_applicable_reason
