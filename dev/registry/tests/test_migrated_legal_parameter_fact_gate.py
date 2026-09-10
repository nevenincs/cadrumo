"""Cross-slice gate for facts that displaced the retired legal-parameter provider."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.facts.resolution import (
    EntitySetFactQuery,
    ResolvedEntitySetFact,
    ResolvedScalarFact,
    ScalarFactQuery,
    resolve_governed_fact,
)
from cadrumo.domain.calculations.registry.facts.schema import GovernedFactCatalogue
from cadrumo.domain.calculations.registry.schema_base import DateAxis
from dev.registry.compiler.fact_providers import compile_registered_fact_providers
from dev.registry.compiler.fact_validation import migrated_legal_parameter_fact_failures
from dev.registry.compiler.loader import load_shared_catalogues
from dev.registry.compiler.validator import RegistryValidator

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _registry_root():
    return bundled_path("registry", "aeat")


def _catalogue() -> GovernedFactCatalogue:
    return compile_registered_fact_providers(_registry_root())


def _compiler_catalogues() -> RegistryCatalogues:
    root = _registry_root()
    catalogues = load_shared_catalogues(root)
    return catalogues.model_copy(update={"facts": compile_registered_fact_providers(root)})


def _resolve_scalar(fact_id: str, effective_date: date) -> ResolvedScalarFact:
    resolved = resolve_governed_fact(
        _catalogue(),
        ScalarFactQuery(
            fact_id=fact_id,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
        authority_digest="6" * 64,
    )
    assert isinstance(resolved, ResolvedScalarFact)
    return resolved


def _resolve_entities(fact_id: str, effective_date: date) -> ResolvedEntitySetFact:
    resolved = resolve_governed_fact(
        _catalogue(),
        EntitySetFactQuery(
            fact_id=fact_id,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
        authority_digest="6" * 64,
    )
    assert isinstance(resolved, ResolvedEntitySetFact)
    return resolved


def test_direct_canonical_compilation_closes_the_retired_legal_parameter_slices() -> None:
    root = _registry_root()
    shared = load_shared_catalogues(root)

    assert migrated_legal_parameter_fact_failures(_catalogue(), source_refs=shared.sources) == ()


def test_gate_detects_a_missing_fact_and_non_filing_date_axis() -> None:
    catalogue = _catalogue()
    missing = GovernedFactCatalogue(
        facts={
            fact_id: fact
            for fact_id, fact in catalogue.facts.items()
            if fact_id != "liva-art-161:recargo-rate-general"
        }
    )
    fact = catalogue.facts["liva-art-161:recargo-rate-general"]
    malformed_variant = fact.variants[0].model_copy(update={"date_axis": DateAxis.DEVENGO_DATE})
    malformed = fact.model_copy(update={"variants": (malformed_variant,)})
    wrong_axis = GovernedFactCatalogue(
        facts={**catalogue.facts, malformed.fact_id: malformed},
    )
    sources = load_shared_catalogues(_registry_root()).sources

    missing_failures = migrated_legal_parameter_fact_failures(missing, source_refs=sources)
    wrong_axis_failures = migrated_legal_parameter_fact_failures(wrong_axis, source_refs=sources)

    assert any("is not authored" in failure for failure in missing_failures)
    assert any("must use the filing_period date axis" in failure for failure in wrong_axis_failures)


def test_gate_detects_a_gap_in_source_grounded_temporal_coverage() -> None:
    catalogue = _catalogue()
    fact = catalogue.facts["liva-art-161:recargo-rate-general"]
    gapped_variant = fact.variants[0].model_copy(update={"valid_to": date(1996, 12, 30)})
    gapped_fact = fact.model_copy(update={"variants": (gapped_variant, *fact.variants[1:])})
    gapped = GovernedFactCatalogue(facts={**catalogue.facts, gapped_fact.fact_id: gapped_fact})

    failures = migrated_legal_parameter_fact_failures(
        gapped,
        source_refs=load_shared_catalogues(_registry_root()).sources,
    )

    assert any("has a gap in its source-grounded temporal coverage" in failure for failure in failures)


def test_canonical_compiler_validator_reports_a_missing_migrated_fact() -> None:
    catalogues = _compiler_catalogues()
    missing = GovernedFactCatalogue(
        facts={
            fact_id: fact
            for fact_id, fact in catalogues.facts.facts.items()
            if fact_id != "liva-art-161:recargo-rate-general"
        }
    )
    malformed_catalogues = catalogues.model_copy(update={"facts": missing})

    failures = RegistryValidator(malformed_catalogues, source_root=bundled_path())._validate_catalogues()

    assert "migrated legal-parameter fact 'liva-art-161:recargo-rate-general' is not authored" in failures


def test_real_resolution_tracks_known_legal_change_boundaries() -> None:
    assert _resolve_scalar("lirpf-art-101:retencion-administrador-reducida", date(2015, 1, 1)).payload.value == Decimal(
        "0.19"
    )
    professional_rate = "rirpf-art-95:retencion-actividades-profesionales-general"
    assert _resolve_scalar(professional_rate, date(2015, 1, 1)).payload.value == Decimal("0.18")
    assert _resolve_scalar(professional_rate, date(2015, 7, 12)).payload.value == Decimal("0.15")
    assert _resolve_scalar("liva-art-161:recargo-rate-general", date(2012, 8, 31)).payload.value == Decimal("0.04")
    assert _resolve_scalar("liva-art-161:recargo-rate-general", date(2012, 9, 1)).payload.value == Decimal("0.052")
    exclusion = "lirpf-dt-32:eo-exclusion-rendimientos-conjunto-eur"
    assert _resolve_scalar(exclusion, date(2024, 12, 31)).payload.value == Decimal("250000")
    assert _resolve_scalar(exclusion, date(2025, 1, 1)).payload.value == Decimal("150000")


def test_real_resolution_refuses_before_the_source_grounded_windows() -> None:
    with pytest.raises(RegistryValidationError, match="has no variant for the exact query context"):
        _resolve_scalar("lirpf-art-101:retencion-administrador-reducida", date(2014, 12, 31))
    with pytest.raises(RegistryValidationError, match="has no variant for the exact query context"):
        _resolve_entities("rirpf-art-95:selector-m036-actividades-profesionales", date(2026, 3, 25))
    with pytest.raises(RegistryValidationError, match="has no variant for the exact query context"):
        _resolve_entities("modelo-131:selector-m036-volumen-ingresos-agrario", date(2026, 3, 31))
