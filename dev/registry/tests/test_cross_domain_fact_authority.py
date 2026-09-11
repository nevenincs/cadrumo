"""Cross-domain consumer and corpus proof for the governed-fact authority."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from cadrumo.core.concepto_ingreso import ConceptoIngreso
from cadrumo.core.irnr import TipoRentaIrnr
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry._m347_threshold import resolve_m347_counterparty_annual_threshold
from cadrumo.domain.calculations.registry.facts.resolution import ResolvedMappingFact
from cadrumo.domain.contribuyente.family_fact_context import FamilyFactResolutionContext
from cadrumo.domain.iva.rates import iva_rate_record_from_fact
from cadrumo.domain.iva.recargo_equivalencia import (
    recargo_rate_record_from_fact,
    resolve_recargo_rate_for_applied_rate,
)
from cadrumo.domain.transactions.volumen_ingresos import counts_toward_volumen_de_ingresos
from dev.registry.analysis.cross_domain_fact_authority import (
    CROSS_DOMAIN_FACT_PROBES,
    CrossDomainFactFindingKind,
    cross_domain_fact_findings,
)
from dev.registry.compiler.convenio import convenio_authority_from_facts

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _probe(domain: str):
    return next(probe for probe in CROSS_DOMAIN_FACT_PROBES if probe.domain == domain)


def test_live_cross_domain_facts_resolve_with_grounded_evidence_and_refuse_unsupported_applicability(
    registry_authority,
) -> None:
    """The complete cross-domain slice uses one validated development authority."""
    assert cross_domain_fact_findings(registry_authority, source_root=bundled_path()) == ()


def test_cross_domain_consumers_preserve_the_authority_result_without_parallel_resolution(
    registry_authority,
) -> None:
    """Each domain projection retains the exact resolved fact it consumes."""
    m347 = _probe("modelo-347-threshold")
    assert resolve_m347_counterparty_annual_threshold(
        effective_date=m347.query.effective_date,
        authority=registry_authority,
    ) == registry_authority.resolve_governed_fact(m347.query)

    family = _probe("renta-family-window")
    family_context = FamilyFactResolutionContext(
        authority=registry_authority,
        filing_period=family.query.effective_date,
        devengo_date=family.query.effective_date,
    )
    assert family_context.resolved_scalar(family.query.fact_id) == registry_authority.resolve_governed_fact(
        family.query
    )
    assert family_context.integer(family.query.fact_id) == 25

    iva_rate = registry_authority.resolve_governed_fact(_probe("iva-rate").query)
    assert isinstance(iva_rate, ResolvedMappingFact)
    projected_rate = iva_rate_record_from_fact(iva_rate)
    assert projected_rate.pct == Decimal("21")
    assert projected_rate.legal_refs == iva_rate.legal_refs
    assert projected_rate.source_refs == iva_rate.source_refs

    recargo = resolve_recargo_rate_for_applied_rate(
        Decimal("0.05"),
        date(2024, 5, 1),
        authority=registry_authority,
    )
    assert recargo == registry_authority.resolve_governed_fact(_probe("iva-recargo").query)
    assert recargo_rate_record_from_fact(recargo).recargo_rate == Decimal("0.0062")

    income_exclusion = registry_authority.resolve_governed_fact(_probe("modelo-131-income-exclusion").query)
    assert counts_toward_volumen_de_ingresos(
        ConceptoIngreso.SUBVENCION_CAPITAL,
        effective_date=date(2018, 12, 23),
        authority=registry_authority,
    ) is (ConceptoIngreso.SUBVENCION_CAPITAL.value not in income_exclusion.payload.entities)

    projected_convenio = convenio_authority_from_facts(
        registry_authority.catalogues.facts,
        registry_authority.catalogues.legal,
    )
    assert projected_convenio == registry_authority.catalogues.convenio
    convenio = registry_authority.resolve_governed_fact(_probe("irnr-convenio").query)
    convenio_row = registry_authority.catalogues.convenio.resolve("DE", TipoRentaIrnr.DIVIDEND, 2025)
    assert convenio_row is not None
    assert convenio_row.kind.value == convenio.payload.override_code
    assert convenio_row.rate == Decimal(str(convenio.payload.value))
    assert convenio_row.legal_refs == convenio.legal_refs


def test_gate_detects_broken_corpus_binding_and_a_non_refusing_negative_probe(
    registry_authority,
) -> None:
    """DETECTOR TEETH: neither missing legal binding nor fallback is accepted."""
    family = _probe("renta-family-window")
    resolved = registry_authority.resolve_governed_fact(family.query)
    fact = registry_authority.catalogues.facts.facts[family.query.fact_id]
    matching_variant = next(variant for variant in fact.variants if variant.variant_id == resolved.variant_id)
    malformed_variant = matching_variant.model_copy(
        update={"legal_refs": ("missing-legal-reference",)},
    )
    malformed_fact = fact.model_copy(
        update={
            "variants": tuple(
                malformed_variant if variant.variant_id == resolved.variant_id else variant for variant in fact.variants
            )
        },
    )
    malformed_facts = registry_authority.catalogues.facts.model_copy(
        update={"facts": {**registry_authority.catalogues.facts.facts, fact.fact_id: malformed_fact}},
    )
    malformed_catalogues = registry_authority.catalogues.model_copy(update={"facts": malformed_facts})
    malformed_authority = replace(registry_authority, catalogues=malformed_catalogues)

    grounding_findings = cross_domain_fact_findings(
        malformed_authority,
        source_root=bundled_path(),
        probes=(family,),
    )
    assert {finding.kind for finding in grounding_findings} == {
        CrossDomainFactFindingKind.LEGAL_REFERENCE_UNREGISTERED,
    }

    malformed_citations = fact.model_copy(
        update={
            "variants": tuple(
                variant.model_copy(update={"source_citations": ()})
                if variant.variant_id == resolved.variant_id
                else variant
                for variant in fact.variants
            )
        },
    )
    citation_catalogues = registry_authority.catalogues.model_copy(
        update={
            "facts": registry_authority.catalogues.facts.model_copy(
                update={"facts": {**registry_authority.catalogues.facts.facts, fact.fact_id: malformed_citations}},
            )
        }
    )
    citation_findings = cross_domain_fact_findings(
        replace(registry_authority, catalogues=citation_catalogues),
        source_root=bundled_path(),
        probes=(family,),
    )
    assert {finding.kind for finding in citation_findings} == {
        CrossDomainFactFindingKind.SOURCE_CITATION_INVALID,
    }

    fallback_findings = cross_domain_fact_findings(
        registry_authority,
        source_root=bundled_path(),
        probes=(replace(family, unsupported_query=family.query),),
    )
    assert {finding.kind for finding in fallback_findings} == {
        CrossDomainFactFindingKind.UNSUPPORTED_APPLICABILITY_ACCEPTED,
    }
