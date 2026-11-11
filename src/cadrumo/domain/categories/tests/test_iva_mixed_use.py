"""Each category's IVA treatment of MIXED use is its own datum, grounded in IVA law.

The IRPF home-office factor of LIRPF art. 30.2, regla 5.ª b) once reached the IVA
cuota because a row's single share carried both taxes. These tests hold the
separation at the boundary where it is declared: the shipped profiles of every
supported year, the model that refuses an IVA treatment grounded in IRPF sources,
and the loader that refuses a verified Manual quotation the registry build never
checked against its bundled edition.

No mocks: the real published authority and the real loader.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core.citation_grounding import CitationGrounding
from ....tests.aeat_literal_fixtures import manual_practicos_url
from ...calculations.registry.authority import PinnedAuthorityOperation
from ...calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ...calculations.registry.facts.variants import FactSelector
from ...calculations.registry.schema_base import DateAxis
from ...calculations.registry.tests.authored_editions import filing_year_envelope, manual_editions_printing
from ...calculations.registry.tests.published_authority import PublishedGovernedFactSource
from ..errors import CategoryValidationError
from ..proportionality import (
    IVA_CITATION_SOURCES,
    CategoryCitation,
    CategoryCitationSource,
    IvaMixedUseRule,
    IvaMixedUseShare,
    parse_http_url,
)
from ..registry import (
    CATEGORY_PROFILE_FACT_ID,
    profile_from_authority_fact,
    resolve_category_profile,
    resolve_category_profiles,
)
from ..spending_category_catalogue import require_spending_category

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ENVELOPE = filing_year_envelope()
#: Editions of the bundled Manual práctico IVA that print the home-office supply rule.
_SUMINISTROS_MANUAL_EDITIONS = manual_editions_printing(
    "iva",
    "La cuota soportada en los suministros será deducible en la parte en que el inmueble esté afecta a la actividad profesional.",
)
#: The newest bundled Manual práctico IVA and Renta editions.
_IVA_MANUAL = _SUMINISTROS_MANUAL_EDITIONS[-1]
_RENTA_MANUAL = manual_editions_printing("renta")[-1]

_SUPPORTED_YEARS = PublishedGovernedFactSource().supported_filing_years().years

_DEGREE_OF_USE_CATEGORIES = (
    "suministros_home_office_luz",
    "suministros_home_office_agua",
    "suministros_home_office_gas",
    "suministros_home_office_internet",
    "telefonia_fija",
)
_BOE_URL = "https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740"
_MANUAL_URL = manual_practicos_url(f"IVA/Manual_IVA_{_IVA_MANUAL}.pdf")


def _liva_citation(source: CategoryCitationSource = CategoryCitationSource.LEY_IVA) -> CategoryCitation:
    return CategoryCitation(
        source=source,
        reference="Ley 37/1992",
        locator="art. 95.Uno",
        url=parse_http_url(_BOE_URL),
        quote="Texto autoritativo de prueba.",
        legal_ref="ley-37-1992:art-95",
        valid_from=date(_ENVELOPE.floor, 1, 1),
        valid_to=date(_ENVELOPE.horizon, 12, 31),
    )


@pytest.mark.parametrize("year", _SUPPORTED_YEARS)
@pytest.mark.parametrize("category_id", _DEGREE_OF_USE_CATEGORIES)
def test_home_office_suministros_deduct_iva_at_the_degree_of_use(
    operation: PinnedAuthorityOperation,
    category_id: str,
    year: int,
) -> None:
    """DISCRIMINATING. Every supported year, 2022 included, declares the use-proportional share."""
    rule = resolve_category_profile(require_spending_category(category_id), year, operation=operation).proportionality

    assert rule.iva_mixed_use is not None
    assert rule.iva_mixed_use.share is IvaMixedUseShare.DEGREE_OF_USE
    assert {c.legal_ref for c in rule.iva_mixed_use.citations} >= {"ley-37-1992:art-95-3", "ley-37-1992:art-95-4"}
    # The IRPF factor stays on the IRPF rule; nothing about it is cited for IVA.
    assert rule.statutory_multiplier is not None
    assert all(c.source in IVA_CITATION_SOURCES for c in rule.iva_mixed_use.citations)


@pytest.mark.parametrize("year", _SUPPORTED_YEARS)
def test_a_mixed_use_mobile_phone_deducts_no_iva(operation: PinnedAuthorityOperation, year: int) -> None:
    rule = resolve_category_profile(require_spending_category("telefonia_movil"), year, operation=operation)

    assert rule.proportionality.iva_mixed_use is not None
    assert rule.proportionality.iva_mixed_use.share is IvaMixedUseShare.NOT_DEDUCTIBLE


@pytest.mark.parametrize("year", _SUMINISTROS_MANUAL_EDITIONS)
def test_suministros_cite_the_manual_edition_of_their_own_year(operation: PinnedAuthorityOperation, year: int) -> None:
    """The bundled Manual práctico IVA editions that print the rule are each cited by their own year."""
    rule = resolve_category_profile(
        require_spending_category("suministros_home_office_luz"), year, operation=operation
    ).proportionality
    assert rule.iva_mixed_use is not None
    manuals = [c for c in rule.iva_mixed_use.citations if c.source is CategoryCitationSource.MANUAL_IVA]

    assert manuals
    assert {c.source_ref for c in manuals} == {f"aeat-manual-iva-{year}"}
    assert all(c.grounding is CitationGrounding.VERIFIED for c in manuals)


def test_the_bundled_renta_manual_is_cited_as_verified_not_unbundled(operation: PinnedAuthorityOperation) -> None:
    """DISCRIMINATING. The newest bundled Manual de Renta is bundled, so its citation is read, not excused."""
    rule = resolve_category_profile(
        require_spending_category("suministros_home_office_luz"), _RENTA_MANUAL, operation=operation
    ).proportionality
    manual = [c for c in rule.citations if c.source is CategoryCitationSource.MANUAL_RENTA]

    assert len(manual) == 1
    assert manual[0].grounding is CitationGrounding.VERIFIED
    assert manual[0].source_ref == f"aeat-renta-{_RENTA_MANUAL}-manual-parte1"
    assert "30 por 100" in manual[0].quote


@pytest.mark.parametrize("year", _SUPPORTED_YEARS)
def test_every_category_declares_its_iva_treatment_of_mixed_use(operation: PinnedAuthorityOperation, year: int) -> None:
    """DISCRIMINATING. No category leaves a MIXED row's IVA to the row's own share by omission."""
    profiles = resolve_category_profiles(year, operation=operation)

    missing = sorted(
        category.value for category, profile in profiles.items() if profile.proportionality.iva_mixed_use is None
    )
    assert missing == []


_VEHICLE_RUNNING_COSTS = ("vehiculo_combustible", "vehiculo_mantenimiento", "vehiculo_peaje", "vehiculo_parking")


@pytest.mark.parametrize("year", _SUPPORTED_YEARS)
@pytest.mark.parametrize("category_id", _VEHICLE_RUNNING_COSTS)
def test_vehicle_running_costs_carry_the_fifty_per_cent_presumption(
    operation: PinnedAuthorityOperation,
    category_id: str,
    year: int,
) -> None:
    """LIVA art. 95.Tres.2.ª presumes a turismo 50 per cent affected; 95.Cuatro extends it to its running costs."""
    rule = resolve_category_profile(require_spending_category(category_id), year, operation=operation).proportionality

    assert rule.iva_mixed_use is not None
    assert rule.iva_mixed_use.share is IvaMixedUseShare.VEHICLE_PRESUMPTION
    assert rule.iva_mixed_use.presumed_share == Decimal("0.50")
    assert {c.locator for c in rule.iva_mixed_use.citations} >= {"art. 95.Tres.2.ª", "art. 95.Cuatro"}


@pytest.mark.parametrize("category_id", ("hardware_amortizable", "mobiliario_amortizable"))
def test_equipment_deducts_iva_by_use_only_as_a_bien_de_inversion(
    operation: PinnedAuthorityOperation, category_id: str
) -> None:
    rule = resolve_category_profile(
        require_spending_category(category_id), _ENVELOPE.horizon, operation=operation
    ).proportionality

    assert rule.iva_mixed_use is not None
    assert rule.iva_mixed_use.share is IvaMixedUseShare.BIEN_INVERSION_DEGREE_OF_USE
    assert "ley-37-1992:art-108" in {c.legal_ref for c in rule.iva_mixed_use.citations}


def test_a_vehicle_presumption_must_state_its_presumed_share() -> None:
    with pytest.raises(ValidationError, match="must state its presumed share"):
        IvaMixedUseRule(share=IvaMixedUseShare.VEHICLE_PRESUMPTION, citations=(_liva_citation(),))


def test_only_a_vehicle_presumption_states_a_presumed_share() -> None:
    with pytest.raises(ValidationError, match="only a vehicle presumption states a presumed share"):
        IvaMixedUseRule(
            share=IvaMixedUseShare.DEGREE_OF_USE,
            presumed_share=Decimal("0.50"),
            citations=(_liva_citation(),),
        )


def test_no_bundled_renta_manual_citation_is_excused_as_unbundled(operation: PinnedAuthorityOperation) -> None:
    """DISCRIMINATING. The newest Manual de Renta is bundled, so no category may cite it unread."""
    profiles = resolve_category_profiles(_RENTA_MANUAL, operation=operation)

    unread = sorted(
        category.value
        for category, profile in profiles.items()
        for citation in profile.proportionality.citations
        if citation.source is CategoryCitationSource.MANUAL_RENTA
        and citation.grounding is not CitationGrounding.VERIFIED
    )
    assert unread == []


def test_an_iva_treatment_grounded_in_an_irpf_source_is_refused() -> None:
    with pytest.raises(ValidationError, match="IVA sources only"):
        IvaMixedUseRule(
            share=IvaMixedUseShare.DEGREE_OF_USE,
            citations=(_liva_citation(CategoryCitationSource.LEY_IRPF),),
        )


def test_an_iva_treatment_without_a_citation_is_refused() -> None:
    with pytest.raises(ValidationError):
        IvaMixedUseRule(share=IvaMixedUseShare.NOT_DEDUCTIBLE, citations=())


def test_a_verified_edition_citation_must_name_its_bundled_edition() -> None:
    with pytest.raises(ValidationError, match="must name the bundled edition"):
        CategoryCitation(
            source=CategoryCitationSource.MANUAL_IVA,
            reference=f"Manual práctico IVA {_ENVELOPE.horizon}",
            locator="Deducciones",
            url=parse_http_url(_MANUAL_URL),
            quote="Texto autoritativo de prueba.",
            valid_from=date(_ENVELOPE.horizon, 1, 1),
            valid_to=date(_ENVELOPE.horizon, 12, 31),
        )


def test_a_statutory_citation_may_not_name_an_edition() -> None:
    with pytest.raises(ValidationError, match="must not carry source_ref"):
        CategoryCitation(
            source=CategoryCitationSource.LEY_IVA,
            reference="Ley 37/1992",
            locator="art. 95",
            url=parse_http_url(_BOE_URL),
            quote="Texto autoritativo de prueba.",
            legal_ref="ley-37-1992:art-95",
            source_ref=f"aeat-manual-iva-{_ENVELOPE.horizon}",
            valid_from=date(_ENVELOPE.floor, 1, 1),
            valid_to=date(_ENVELOPE.horizon, 12, 31),
        )


def test_the_loader_refuses_a_manual_quotation_the_build_did_not_check(operation: PinnedAuthorityOperation) -> None:
    """DISCRIMINATING. Dropping the variant's source citation leaves the quotation unread."""
    category = require_spending_category("suministros_home_office_luz")
    fact = operation.resolve_governed_fact(
        MappingFactQuery(
            fact_id=CATEGORY_PROFILE_FACT_ID,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=date(_IVA_MANUAL, 12, 31),
            selectors=(FactSelector(name="category", value=category.value),),
        )
    )
    assert isinstance(fact, ResolvedMappingFact)
    unchecked = fact.model_copy(
        update={
            "source_citations": tuple(
                c for c in fact.source_citations if c.source_ref != f"aeat-manual-iva-{_IVA_MANUAL}"
            ),
        }
    )

    with pytest.raises(CategoryValidationError, match="no source citation of its variant carries that text"):
        profile_from_authority_fact(unchecked, operation=operation, year=_IVA_MANUAL)
