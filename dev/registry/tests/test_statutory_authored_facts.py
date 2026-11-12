"""Acceptance contract for statutory facts authored in registry data."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.facts.payloads import GovernedFactFamily, MappingFactPayload
from cadrumo.domain.calculations.registry.facts.resolution import (
    MappingFactQuery,
    ResolvedMappingFact,
    ResolvedScalarFact,
    ScalarFactQuery,
    resolve_governed_fact,
)
from cadrumo.domain.calculations.registry.schema_base import DateAxis
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

from ..compiler.fact_loader import load_governed_facts
from ..compiler.fact_providers import compile_registered_fact_providers
from .profile_schema_support import committed_supported_filing_years

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


_STATUTORY_FACT_IDS = frozenset(
    {
        "m347-counterparty-declaration-threshold",
        "m347-clave-c-beneficiary-declaration-threshold",
        "iva-bien-inversion-escaso-valor-threshold",
        "iae-cifra-negocios-exemption-threshold",
        "lirpf-art-7p-exemption-cap",
        "lirpf-multiple-pagadores-secondary-threshold",
        "lirpf-work-income-general-declaration-limit",
        "lis-art-40-3-incn-threshold",
        "lirpf-art-52-individual-contribution-sublimit",
        "rebeca-maritime-exemption-fraction",
        "lirpf-art-81-maternity-monthly-amount",
        "lirpf-art-81-maternity-annual-cap",
        "lirpf-art-81-maternity-post-birth-enrollment-increment",
        "lirpf-art-81-maternity-post-birth-enrollment-effective-year",
        "lirpf-art-81-contribution-ceiling-retired-effective-year",
        "lirpf-art-58-descendant-ordinary-maximum-age",
        "lirpf-art-58-under-three-maximum-age",
        "lirpf-art-61-shared-custody-proration-factor",
        "lirpf-art-81-adoption-entry-window-years",
        "madrid-birth-adoption-following-periods",
        "lirpf-dt12-rescate-reduction-rate",
        "lirpf-dt12-general-window-following-years",
        "lirpf-dt12-transitional-contingency-first-year",
        "lirpf-dt12-transitional-contingency-last-year",
        "lirpf-dt12-transitional-window-following-years",
        "lirpf-dt12-cliff-last-year",
        "sal-special-reserve-allocation-rate",
        "sal-special-reserve-capital-multiple",
        "dehu-tacit-rejection-natural-days",
        "lirpf-work-income-multiple-pagadores-reduced-limit",
    },
)

_SPANISH_TAX_ID_PERSON_CHECKS = {
    "tax_id.check.nif_letters": "TRWAGMYFPDXBNJZSQVHLCKE",
    "tax_id.check.nie_prefix.X": "0",
    "tax_id.check.nie_prefix.Y": "1",
    "tax_id.check.nie_prefix.Z": "2",
}


def _catalogue():
    return compile_registered_fact_providers(bundled_path("registry", "aeat"))


def test_authored_statutory_facts_enroll_every_retired_declaration() -> None:
    facts = _catalogue().facts
    statutory_facts = {fact_id: facts[fact_id] for fact_id in _STATUTORY_FACT_IDS}

    assert len(statutory_facts) == 30
    assert "lirpf-art-81-maternity-post-birth-enrollment-annual-cap" not in facts
    assert {fact.family for fact in statutory_facts.values()} == {
        GovernedFactFamily.SCALAR,
        GovernedFactFamily.MAPPING,
    }
    assert sum(fact.family is GovernedFactFamily.SCALAR for fact in statutory_facts.values()) == 29


#: The reduced multiple-payer limit as the authored table states it, oldest year first:
#: the oracle is the ordered sequence of annual amounts, whatever calendar years the table spans.
_REDUCED_LIMIT_AMOUNTS = (
    *(Decimal("14000"),) * 4,
    Decimal("15000"),
    *(Decimal("15876"),) * 3,
)


def _schedule_by_year(resolved: ResolvedMappingFact) -> tuple[tuple[int, Decimal], ...]:
    schedule: list[tuple[int, Decimal]] = []
    for entry in resolved.payload.entries:
        assert isinstance(entry.key, int) and isinstance(entry.value, Decimal), entry
        schedule.append((entry.key, entry.value))
    return tuple(sorted(schedule))


def test_authored_statutory_facts_preserve_values_and_provenance() -> None:
    catalogue = _catalogue()
    effective = date(filing_year_envelope().floor, 12, 31)

    threshold = resolve_governed_fact(
        catalogue,
        ScalarFactQuery(
            fact_id="m347-counterparty-declaration-threshold",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective,
        ),
        authority_digest="a" * 64,
        support=committed_supported_filing_years(),
    )
    schedule = resolve_governed_fact(
        catalogue,
        MappingFactQuery(
            fact_id="lirpf-work-income-multiple-pagadores-reduced-limit",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective,
        ),
        authority_digest="b" * 64,
        support=committed_supported_filing_years(),
    )

    assert isinstance(threshold, ResolvedScalarFact)
    assert isinstance(schedule, ResolvedMappingFact)
    assert threshold.payload.value == Decimal("3005.06")
    assert threshold.legal_refs == ("rd-1065-2007:art-33",)
    assert threshold.source_refs == ("boe-rd-1065-2007-statutory-facts",)
    by_year = _schedule_by_year(schedule)
    years = tuple(year for year, _ in by_year)
    assert years == tuple(range(years[0], years[0] + len(_REDUCED_LIMIT_AMOUNTS)))
    assert tuple(amount for _, amount in by_year) == _REDUCED_LIMIT_AMOUNTS


def test_authored_statutory_facts_retain_fact_specific_evidence_and_temporal_axes() -> None:
    facts = _catalogue().facts

    assert facts["m347-counterparty-declaration-threshold"].variants[0].source_citations[0].required_text == (
        "3.005,06 euros durante el año natural",
    )
    assert facts["iva-bien-inversion-escaso-valor-threshold"].variants[0].date_axis is DateAxis.TRANSACTION_DATE
    assert facts["rebeca-maritime-exemption-fraction"].variants[0].date_axis is DateAxis.DEVENGO_DATE
    assert facts["dehu-tacit-rejection-natural-days"].variants[0].date_axis is DateAxis.SUBMISSION_DATE


def test_authored_reduced_multiple_payer_limit_projects_forward_after_last_grounded_year() -> None:
    fact_id = "lirpf-work-income-multiple-pagadores-reduced-limit"
    grounded = resolve_governed_fact(
        _catalogue(),
        MappingFactQuery(
            fact_id=fact_id,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=date(filing_year_envelope().floor, 12, 31),
        ),
        authority_digest="c" * 64,
        support=committed_supported_filing_years(),
    )
    assert isinstance(grounded, ResolvedMappingFact)
    first_year, last_year = (_schedule_by_year(grounded)[index][0] for index in (0, -1))
    resolved = resolve_governed_fact(
        _catalogue(),
        MappingFactQuery(
            fact_id=fact_id,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=date(last_year + 1, 1, 1),
        ),
        authority_digest="c" * 64,
        support=committed_supported_filing_years(),
    )

    assert isinstance(resolved, ResolvedMappingFact)
    assert resolved.projection_direction == "forward"
    assert resolved.projected_from_date == date(last_year, 12, 31)
    assert resolved.variant_id.endswith(f"{first_year}-{last_year}")
    assert resolved.source_refs == ("boe-lirpf-statutory-facts",)
    assert tuple(amount for _, amount in _schedule_by_year(resolved)) == _REDUCED_LIMIT_AMOUNTS


def test_spanish_tax_id_person_checks_remain_bound_to_official_algorithm_evidence() -> None:
    facts = load_governed_facts(bundled_path("registry", "aeat", "facts"))
    variant = next(fact for fact in facts if fact.fact_id == "spanish-tax-identifier-format").variants[0]
    payload = variant.payload
    assert isinstance(payload, MappingFactPayload)
    entries = {entry.key: entry.value for entry in payload.entries}
    citations = {citation.source_ref: citation.required_text for citation in variant.source_citations}

    assert {key: entries[key] for key in _SPANISH_TAX_ID_PERSON_CHECKS} == _SPANISH_TAX_ID_PERSON_CHECKS
    assert variant.source_refs == (
        "aeat-modelo-036-procedure",
        "aeat-nif-personas-fisicas",
        "aeat-nif-personas-juridicas",
        "dgoj-nif-nie-control",
    )
    assert citations["dgoj-nif-nie-control"] == (
        "Se divide el número entre 23 y el resto se sustituye por una letra",
        "RESTO 0 1 2 3 4 5 6 7 8 9 10 11 LETRA T R W A G M Y F P D X B",
        "RESTO 12 13 14 15 16 17 18 19 20 21 22 LETRA N J Z S Q V H L C K E",
        "X → 0 Y → 1 Z → 2",
        "se aplica el mismo algoritmo que para el NIF",
    )
