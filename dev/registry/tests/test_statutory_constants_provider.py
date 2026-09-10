"""Parity contracts for the statutory-constant provider adapter."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from cadrumo.core import external_constants as constants
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.facts.resolution import (
    MappingFactQuery,
    ResolvedMappingFact,
    ResolvedScalarFact,
    ScalarFactQuery,
    resolve_governed_fact,
)
from cadrumo.domain.calculations.registry.facts.schema import GovernedFactCatalogue, GovernedFactFamily
from cadrumo.domain.calculations.registry.schema_base import DateAxis
from dev.registry.compiler.statutory_constants import compile_statutory_constant_facts

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_statutory_provider_enrolls_every_governed_declaration_and_excludes_routing_sets() -> None:
    facts = compile_statutory_constant_facts(Path())
    fact_ids = {fact.fact_id for fact in facts}

    assert len(facts) == 32
    assert "lirpf-work-income-multiple-pagadores-reduced-limit" in fact_ids
    assert all(fact.family in {GovernedFactFamily.SCALAR, GovernedFactFamily.MAPPING} for fact in facts)


def test_statutory_provider_preserves_scalar_and_schedule_values_with_provenance() -> None:
    facts = compile_statutory_constant_facts(Path())
    catalogue = GovernedFactCatalogue(facts={fact.fact_id: fact for fact in facts})

    threshold = resolve_governed_fact(
        catalogue,
        ScalarFactQuery(
            fact_id="m347-counterparty-declaration-threshold",
            date_axis="filing_period",
            effective_date=date(2025, 12, 31),
        ),
        authority_digest="a" * 64,
    )
    schedule = resolve_governed_fact(
        catalogue,
        MappingFactQuery(
            fact_id="lirpf-work-income-multiple-pagadores-reduced-limit",
            date_axis="filing_period",
            effective_date=date(2025, 12, 31),
        ),
        authority_digest="b" * 64,
    )

    assert isinstance(threshold, ResolvedScalarFact)
    assert isinstance(schedule, ResolvedMappingFact)
    assert threshold.payload.value == constants.M347_THRESHOLD_EUR
    assert threshold.legal_refs == ("rd-1065-2007:art-33",)
    assert threshold.source_refs == ("boe-rd-1065-2007-statutory-facts",)
    assert dict((entry.key, entry.value) for entry in schedule.payload.entries) == dict(
        constants.WORK_INCOME_MULTIPLE_PAGADORES_REDUCED_LIMIT_EUR_BY_YEAR,
    )


def test_statutory_provider_uses_fact_specific_evidence_and_temporal_axes() -> None:
    facts = {fact.fact_id: fact for fact in compile_statutory_constant_facts(Path())}

    assert facts["m347-counterparty-declaration-threshold"].variants[0].source_citations[0].required_text == (
        "3.005,06 euros durante el año natural",
    )
    assert facts["iva-bien-inversion-escaso-valor-threshold"].variants[0].date_axis is DateAxis.TRANSACTION_DATE
    assert facts["rebeca-maritime-exemption-fraction"].variants[0].date_axis is DateAxis.DEVENGO_DATE
    assert facts["dehu-tacit-rejection-natural-days"].variants[0].date_axis is DateAxis.SUBMISSION_DATE


def test_reduced_multiple_payer_limit_fails_closed_after_last_grounded_year() -> None:
    facts = compile_statutory_constant_facts(Path())
    catalogue = GovernedFactCatalogue(facts={fact.fact_id: fact for fact in facts})

    with pytest.raises(RegistryValidationError, match="has no variant for the exact query context"):
        resolve_governed_fact(
            catalogue,
            MappingFactQuery(
                fact_id="lirpf-work-income-multiple-pagadores-reduced-limit",
                date_axis=DateAxis.FILING_PERIOD,
                effective_date=date(2027, 1, 1),
            ),
            authority_digest="c" * 64,
        )
