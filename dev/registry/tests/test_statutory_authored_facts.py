"""Acceptance contract for statutory facts authored in registry data."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.facts.resolution import (
    MappingFactQuery,
    ResolvedMappingFact,
    ResolvedScalarFact,
    ScalarFactQuery,
    resolve_governed_fact,
)
from cadrumo.domain.calculations.registry.facts.schema import GovernedFactFamily
from cadrumo.domain.calculations.registry.schema_base import DateAxis

from ..compiler.fact_loader import load_governed_facts
from ..compiler.fact_providers import compile_registered_fact_providers

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
        "lirpf-art-20-trabajo-reduccion-rnt-ceiling",
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

    assert len(statutory_facts) == 31
    assert "lirpf-art-81-maternity-post-birth-enrollment-annual-cap" not in facts
    assert {fact.family for fact in statutory_facts.values()} == {
        GovernedFactFamily.SCALAR,
        GovernedFactFamily.MAPPING,
    }
    assert sum(fact.family is GovernedFactFamily.SCALAR for fact in statutory_facts.values()) == 30


def test_authored_statutory_facts_preserve_values_and_provenance() -> None:
    catalogue = _catalogue()

    threshold = resolve_governed_fact(
        catalogue,
        ScalarFactQuery(
            fact_id="m347-counterparty-declaration-threshold",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=date(2025, 12, 31),
        ),
        authority_digest="a" * 64,
    )
    schedule = resolve_governed_fact(
        catalogue,
        MappingFactQuery(
            fact_id="lirpf-work-income-multiple-pagadores-reduced-limit",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=date(2025, 12, 31),
        ),
        authority_digest="b" * 64,
    )

    assert isinstance(threshold, ResolvedScalarFact)
    assert isinstance(schedule, ResolvedMappingFact)
    assert threshold.payload.value == Decimal("3005.06")
    assert threshold.legal_refs == ("rd-1065-2007:art-33",)
    assert threshold.source_refs == ("boe-rd-1065-2007-statutory-facts",)
    assert dict((entry.key, entry.value) for entry in schedule.payload.entries) == {
        2019: Decimal("14000"),
        2020: Decimal("14000"),
        2021: Decimal("14000"),
        2022: Decimal("14000"),
        2023: Decimal("15000"),
        2024: Decimal("15876"),
        2025: Decimal("15876"),
        2026: Decimal("15876"),
    }


def test_authored_statutory_facts_retain_fact_specific_evidence_and_temporal_axes() -> None:
    facts = _catalogue().facts

    assert facts["m347-counterparty-declaration-threshold"].variants[0].source_citations[0].required_text == (
        "3.005,06 euros durante el año natural",
    )
    assert facts["iva-bien-inversion-escaso-valor-threshold"].variants[0].date_axis is DateAxis.TRANSACTION_DATE
    assert facts["rebeca-maritime-exemption-fraction"].variants[0].date_axis is DateAxis.DEVENGO_DATE
    assert facts["dehu-tacit-rejection-natural-days"].variants[0].date_axis is DateAxis.SUBMISSION_DATE


def test_authored_reduced_multiple_payer_limit_projects_forward_after_last_grounded_year() -> None:
    resolved = resolve_governed_fact(
        _catalogue(),
        MappingFactQuery(
            fact_id="lirpf-work-income-multiple-pagadores-reduced-limit",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=date(2027, 1, 1),
        ),
        authority_digest="c" * 64,
    )

    assert isinstance(resolved, ResolvedMappingFact)
    assert resolved.projection_direction == "forward"
    assert resolved.projected_from_date == date(2026, 12, 31)
    assert resolved.variant_id.endswith("2019-2026")
    assert resolved.source_refs == ("boe-lirpf-statutory-facts",)
    assert dict((entry.key, entry.value) for entry in resolved.payload.entries) == {
        2019: Decimal("14000"),
        2020: Decimal("14000"),
        2021: Decimal("14000"),
        2022: Decimal("14000"),
        2023: Decimal("15000"),
        2024: Decimal("15876"),
        2025: Decimal("15876"),
        2026: Decimal("15876"),
    }


def test_spanish_tax_id_person_checks_remain_bound_to_official_algorithm_evidence() -> None:
    facts = load_governed_facts(bundled_path("registry", "aeat", "facts"))
    variant = next(fact for fact in facts if fact.fact_id == "spanish-tax-identifier-format").variants[0]
    entries = {entry.key: entry.value for entry in variant.payload.entries}
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
