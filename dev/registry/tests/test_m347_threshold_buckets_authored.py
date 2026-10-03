"""Authored contract of the Modelo 347 clave threshold-bucket fact.

Resolves the fact straight from the authored registry tree through a candidate
fact authority, so the bucket partition each filing period declares is proven
before publication: entregas (B, F) and adquisiciones (A, G) computed apart
(RD 1065/2007 art. 33.1), clave C on its own 300,51 EUR floor (arts. 32.c,
33.4), D apart, and clave E related whatever its amount only from the 2025
design onwards.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.facts.schema import GovernedFactCatalogue
from cadrumo.domain.calculations.registry.governed_fact_scope import CandidateFactAuthority
from cadrumo.domain.calculations.registry.m347_threshold import (
    M347ThresholdBuckets,
    m347_declarable_party_buckets,
    resolve_m347_threshold_buckets,
)

from ..compiler.fact_loader import load_governed_facts
from ..compiler.loader import load_shared_catalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_GENERAL_FLOOR_FACT = "m347-counterparty-declaration-threshold"
_CLAVE_C_FLOOR_FACT = "m347-clave-c-beneficiary-declaration-threshold"


def _authored_authority() -> CandidateFactAuthority:
    facts = load_governed_facts(bundled_path("registry", "aeat", "facts"))
    support = load_shared_catalogues(bundled_path("registry", "aeat")).require_supported_filing_years()
    return CandidateFactAuthority(GovernedFactCatalogue(facts={fact.fact_id: fact for fact in facts}), support)


def _floor_facts(buckets: M347ThresholdBuckets) -> dict[str, str | None]:
    return {
        clave: None if bucket.floor_fact is None else bucket.floor_fact.fact_id
        for bucket in buckets.buckets
        for clave in bucket.claves
    }


@pytest.mark.parametrize("filing_date", [date(2024, 12, 31), date(2025, 12, 31)])
def test_every_edition_separates_entregas_adquisiciones_c_and_d(filing_date: date) -> None:
    buckets = resolve_m347_threshold_buckets(effective_date=filing_date, authority=_authored_authority())

    assert buckets.bucket_of("B") is buckets.bucket_of("F")
    assert buckets.bucket_of("A") is buckets.bucket_of("G")
    assert len({buckets.bucket_of(clave).token for clave in ("A", "B", "C", "D", "E")}) == 5
    floors = _floor_facts(buckets)
    assert floors["A"] == floors["B"] == floors["D"] == _GENERAL_FLOOR_FACT
    assert floors["C"] == _CLAVE_C_FLOOR_FACT


def test_clave_e_keeps_the_general_floor_under_the_2011_design() -> None:
    buckets = resolve_m347_threshold_buckets(effective_date=date(2024, 12, 31), authority=_authored_authority())

    assert _floor_facts(buckets)["E"] == _GENERAL_FLOOR_FACT


def test_clave_e_has_no_floor_from_the_2025_design() -> None:
    buckets = resolve_m347_threshold_buckets(effective_date=date(2025, 12, 31), authority=_authored_authority())

    assert buckets.bucket_of("E").floor is None
    assert buckets.bucket_of("E").floor_fact is None


def test_the_authored_buckets_judge_each_direction_against_its_own_floor() -> None:
    authority = _authored_authority()
    declarable = m347_declarable_party_buckets(
        {
            ("B11111112", "B"): Decimal("2000.00"),
            ("B11111112", "A"): Decimal("2000.00"),
            ("C22222229", "B"): Decimal("4000.00"),
            ("C22222229", "A"): Decimal("2000.00"),
            ("D33333335", "C"): Decimal("500.00"),
            ("E44444441", "E"): Decimal("1000.00"),
        },
        effective_date=date(2025, 12, 31),
        authority=authority,
    )

    assert not declarable.admits("B11111112", "B")
    assert not declarable.admits("B11111112", "A")
    assert declarable.admits("C22222229", "B")
    assert not declarable.admits("C22222229", "A")
    assert declarable.admits("D33333335", "C")
    assert declarable.admits("E44444441", "E")

    before_2025 = m347_declarable_party_buckets(
        {("E44444441", "E"): Decimal("1000.00")},
        effective_date=date(2024, 12, 31),
        authority=authority,
    )
    assert not before_2025.admits("E44444441", "E")
