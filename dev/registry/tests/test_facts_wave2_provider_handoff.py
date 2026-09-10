"""Machine contract for the Wave 2 governed-fact provider handoff."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.facts.modelo_projections import ModeloParameterFact
from cadrumo.domain.calculations.registry.facts.schema import FactSelector
from dev.registry.compiler.fact_providers import (
    FACT_PROVIDER_REGISTRATIONS,
    compile_registered_fact_providers,
)
from dev.registry.compiler.statutory_constants import compile_statutory_constant_facts

_ROOT = Path(__file__).resolve().parents[3]
_MANIFEST = _ROOT / "dev/registry/analysis/facts_wave2_provider_handoff.toml"
_PLAN = _ROOT / ".vault/plan/2026-09-09-facts-registry-plan.md"
pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _manifest() -> dict[str, Any]:
    return tomllib.loads(_MANIFEST.read_text(encoding="utf-8"))


def test_handoff_covers_exact_live_provider_and_fact_family_denominator() -> None:
    manifest = _manifest()
    contracts = manifest["contracts"]
    registrations = {registration.provider_id: registration for registration in FACT_PROVIDER_REGISTRATIONS}

    assert {contract["provider_id"] for contract in contracts} == registrations.keys()
    assert len(contracts) == 11
    assert all(contract.get("fact_ids") or contract.get("denominator_source") for contract in contracts)
    assert all(contract["remaining_conditions"] for contract in contracts)

    direct_catalogue = compile_registered_fact_providers(bundled_path("registry", "aeat"))
    projected_ids = {fact.value for fact in ModeloParameterFact}
    for contract in contracts:
        assert contract["query_type"] in {
            "GovernedFactQuery",
            "ScalarFactQuery",
            "MappingFactQuery",
            "EntitySetFactQuery",
            "OverrideFactQuery",
            "EventFactQuery",
        }
        for fact_id in contract.get("fact_ids", ()):
            if contract["provider_id"] == "modelo-parameter-projections":
                assert fact_id in projected_ids
                continue
            fact = direct_catalogue.facts[fact_id]
            assert fact.family.value == contract["family"]
            assert {variant.date_axis.value for variant in fact.variants} == {contract["temporal_axis"]}
            assert all(_selectors_match(contract["required_selectors"], variant.selectors) for variant in fact.variants)


def test_handoff_targets_live_wave3_steps_files_and_wave1_ledgers() -> None:
    manifest = _manifest()
    plan = _PLAN.read_text(encoding="utf-8")
    for contract in manifest["contracts"]:
        for step in contract["consumer_step"].split(","):
            assert re.search(rf"`{re.escape(step)}`", plan)
        assert all((_ROOT / path).exists() for path in contract["consumer_files"])
        denominator = contract.get("denominator_source")
        if denominator:
            assert (_ROOT / denominator.split(":", maxsplit=1)[0]).exists()

    external = tomllib.loads(
        (_ROOT / manifest["external_constants_ledger"]).read_text(encoding="utf-8"),
    )
    external_fact_ids = {
        row["destination_id"] for row in external["classifications"] if row["kind"] == "governed_fact"
    }
    statutory_fact_ids = {fact.fact_id for fact in compile_statutory_constant_facts(bundled_path("registry", "aeat"))}
    assert statutory_fact_ids == external_fact_ids - {"iva-general-rate"}

    iva = tomllib.loads((_ROOT / manifest["iva_ledger"]).read_text(encoding="utf-8"))
    assert {lane["destination_id"] for lane in iva["lanes"][:2]} == {
        "iva-rate-schedule",
        "iva-recargo-by-applied-rate",
    }


def test_explicit_non_enrollments_remain_fail_closed() -> None:
    manifest = _manifest()
    non_enrollments = {row["identity"]: row for row in manifest["non_enrollments"]}
    provider_ids = {registration.provider_id for registration in FACT_PROVIDER_REGISTRATIONS}

    assert set(non_enrollments) == {"apoderamientos-scopes", "holiday-calendar-2026"}
    assert "apoderamientos-scopes" not in provider_ids
    holiday = compile_registered_fact_providers(bundled_path("registry", "aeat")).facts["deadlines.public-holiday"]
    assert 2026 not in {variant.valid_from.year for variant in holiday.variants}
    assert "external authority evidence" in non_enrollments["apoderamientos-scopes"]["remaining_conditions"][0]
    assert "official BOE publication" in non_enrollments["holiday-calendar-2026"]["remaining_conditions"][0]


def _selectors_match(required: list[str], selectors: tuple[FactSelector, ...]) -> bool:
    actual = {selector.name for selector in selectors}
    alternatives = [part.split("|") for part in required]
    return all(any(name in actual for name in names if name != "none") or "none" in names for names in alternatives)
