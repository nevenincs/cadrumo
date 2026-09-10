"""Focused handoff contract for the complete Wave 2 fact-provider set."""

from __future__ import annotations

from dataclasses import replace

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, RegistryCatalogues
from dev.registry import maintenance_support as maintenance_support_module
from dev.registry.compiler import fact_providers as provider_module
from dev.registry.compiler.fact_providers import FACT_PROVIDER_REGISTRATIONS, compile_registered_fact_providers
from dev.registry.maintenance_support import reset_registry_caches

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_WAVE2_PROVIDER_IDS = (
    "authored-facts",
    "category-profiles",
    "convenio-overrides",
    "iva-rate-schedule",
    "legal-holiday-calendars",
    "statutory-constants",
    "modelo-parameter-projections",
)


def test_every_wave2_provider_compiles_into_the_validated_authority(
    registry_tree: tuple[tuple[ModeloDefinition, ...], RegistryCatalogues],
) -> None:
    root = bundled_path("registry", "aeat")
    modelos, _catalogues = registry_tree

    assert tuple(registration.provider_id for registration in FACT_PROVIDER_REGISTRATIONS) == _WAVE2_PROVIDER_IDS
    for registration in FACT_PROVIDER_REGISTRATIONS:
        registration.compile(root)

    projected_fact_ids = {
        "declarations.m347.counterparty-annual-threshold",
        "renta.maternity.monthly-deduction",
        "renta.maternity.annual-cap",
        "renta.maternity.post-enrollment-increment",
    }
    catalogue = compile_registered_fact_providers(root, modelos=modelos)
    assert projected_fact_ids <= catalogue.facts.keys()


def test_every_wave2_fact_variant_retains_its_declared_provenance() -> None:
    facts = compile_registered_fact_providers(bundled_path("registry", "aeat")).facts.values()

    assert facts
    for fact in facts:
        for variant in fact.variants:
            assert {citation.source_ref for citation in variant.source_citations} == set(variant.source_refs)
            assert all(citation.required_text for citation in variant.source_citations)


def test_wave2_provider_fingerprints_cover_every_file_backed_provider() -> None:
    root = bundled_path("registry", "aeat")

    for registration in FACT_PROVIDER_REGISTRATIONS:
        fingerprints = registration.collect_fingerprints(root)
        if registration.owned_directories != ("facts",) and registration.owned_directories:
            assert fingerprints, f"{registration.provider_id} contributes no authority fingerprint"


def test_authority_reset_invokes_every_wave2_provider_reset(monkeypatch: pytest.MonkeyPatch) -> None:
    resets: list[str] = []
    registrations = tuple(
        replace(registration, reset=lambda provider_id=registration.provider_id: resets.append(provider_id))
        for registration in FACT_PROVIDER_REGISTRATIONS
    )
    monkeypatch.setattr(provider_module, "FACT_PROVIDER_REGISTRATIONS", registrations)
    monkeypatch.setattr(maintenance_support_module, "_invalidate_authority_generations", lambda: None)

    reset_registry_caches()

    assert resets == list(_WAVE2_PROVIDER_IDS)
