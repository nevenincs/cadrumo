"""Fail-closed cross-domain evidence and resolution gate for governed facts.

The development compiler is the only authority available to this gate.  The
product authority deliberately reads a published authority and must refuse when
that publication is unavailable; this analyser never replaces that boundary
with an authoring-tree fallback.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from pathlib import Path

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.facts.resolution import (
    EntitySetFactQuery,
    EventFactQuery,
    GovernedFactQuery,
    MappingFactQuery,
    OverrideFactQuery,
    ScalarFactQuery,
)
from cadrumo.domain.calculations.registry.facts.schema import FactSelector
from cadrumo.domain.calculations.registry.schema_base import DateAxis

from ..compiler.authority import compiled_bundled_authority
from ..compiler.legal_grounding import verify_legal_reference_grounding
from ..compiler.validate_evidence import EvidenceValidator

__all__ = [
    "CROSS_DOMAIN_FACT_PROBES",
    "CrossDomainFactFinding",
    "CrossDomainFactFindingKind",
    "CrossDomainFactProbe",
    "cross_domain_fact_findings",
    "main",
]


class CrossDomainFactFindingKind(StrEnum):
    """Distinct cross-domain failure modes that require a refusal."""

    RESOLUTION_FAILED = "resolution_failed"
    PROVENANCE_MISSING = "provenance_missing"
    LEGAL_REFERENCE_UNREGISTERED = "legal_reference_unregistered"
    SOURCE_REFERENCE_UNREGISTERED = "source_reference_unregistered"
    SOURCE_CITATION_INVALID = "source_citation_invalid"
    CORPUS_GROUNDING_FAILED = "corpus_grounding_failed"
    UNSUPPORTED_APPLICABILITY_ACCEPTED = "unsupported_applicability_accepted"


@dataclass(frozen=True, slots=True)
class CrossDomainFactFinding:
    """One fail-closed finding produced by the cross-domain authority gate."""

    kind: CrossDomainFactFindingKind
    domain: str
    fact_id: str
    detail: str


@dataclass(frozen=True, slots=True)
class CrossDomainFactProbe:
    """One independently selected legal-domain coordinate and its refusal case."""

    domain: str
    query: GovernedFactQuery
    unsupported_query: GovernedFactQuery


CROSS_DOMAIN_FACT_PROBES = (
    CrossDomainFactProbe(
        domain="modelo-347-threshold",
        query=ScalarFactQuery(
            fact_id="declarations.m347.counterparty-annual-threshold",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=date(2025, 12, 31),
            selectors=(
                FactSelector(name="modelo", value="347"),
                FactSelector(name="parameter_id", value="modelo-347-tercero-anual-threshold-eur"),
            ),
        ),
        unsupported_query=ScalarFactQuery(
            fact_id="declarations.m347.counterparty-annual-threshold",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=date(1900, 1, 1),
            selectors=(
                FactSelector(name="modelo", value="347"),
                FactSelector(name="parameter_id", value="modelo-347-tercero-anual-threshold-eur"),
            ),
        ),
    ),
    CrossDomainFactProbe(
        domain="renta-family-window",
        query=ScalarFactQuery(
            fact_id="lirpf-art-58-descendant-ordinary-maximum-age",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=date(2025, 12, 31),
        ),
        unsupported_query=ScalarFactQuery(
            fact_id="lirpf-art-58-descendant-ordinary-maximum-age",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=date(2006, 12, 31),
        ),
    ),
    CrossDomainFactProbe(
        domain="iva-rate",
        query=MappingFactQuery(
            fact_id="iva-rate-schedule",
            date_axis=DateAxis.DEVENGO_DATE,
            effective_date=date(2025, 1, 1),
            selectors=(
                FactSelector(name="member_state", value="es"),
                FactSelector(name="kind", value="general"),
                FactSelector(name="rate_role", value="ordinary"),
            ),
        ),
        unsupported_query=MappingFactQuery(
            fact_id="iva-rate-schedule",
            date_axis=DateAxis.DEVENGO_DATE,
            effective_date=date(2025, 1, 1),
            selectors=(
                FactSelector(name="member_state", value="es"),
                FactSelector(name="kind", value="general"),
                FactSelector(name="rate_role", value="unsupported-role"),
            ),
        ),
    ),
    CrossDomainFactProbe(
        domain="iva-recargo",
        query=MappingFactQuery(
            fact_id="iva-recargo-by-applied-rate",
            date_axis=DateAxis.DEVENGO_DATE,
            effective_date=date(2024, 5, 1),
            selectors=(FactSelector(name="applied_rate", value=Decimal("0.05")),),
        ),
        unsupported_query=MappingFactQuery(
            fact_id="iva-recargo-by-applied-rate",
            date_axis=DateAxis.DEVENGO_DATE,
            effective_date=date(2025, 1, 1),
            selectors=(FactSelector(name="applied_rate", value=Decimal("0.05")),),
        ),
    ),
    CrossDomainFactProbe(
        domain="irnr-convenio",
        query=OverrideFactQuery(
            fact_id="irnr.convenio.override",
            date_axis=DateAxis.DEVENGO_DATE,
            effective_date=date(2025, 1, 1),
            selectors=(
                FactSelector(name="country_code", value="DE"),
                FactSelector(name="tipo_renta", value="dividend"),
            ),
        ),
        unsupported_query=OverrideFactQuery(
            fact_id="irnr.convenio.override",
            date_axis=DateAxis.DEVENGO_DATE,
            effective_date=date(2024, 12, 31),
            selectors=(
                FactSelector(name="country_code", value="DE"),
                FactSelector(name="tipo_renta", value="dividend"),
            ),
        ),
    ),
    CrossDomainFactProbe(
        domain="deadline-holiday",
        query=EventFactQuery(
            fact_id="deadlines.public-holiday",
            date_axis=DateAxis.SUBMISSION_DATE,
            effective_date=date(2025, 1, 1),
            selectors=(FactSelector(name="jurisdiction", value="national"),),
        ),
        unsupported_query=EventFactQuery(
            fact_id="deadlines.public-holiday",
            date_axis=DateAxis.SUBMISSION_DATE,
            effective_date=date(2025, 1, 2),
            selectors=(FactSelector(name="jurisdiction", value="national"),),
        ),
    ),
    CrossDomainFactProbe(
        domain="modelo-131-income-exclusion",
        query=EntitySetFactQuery(
            fact_id="rd-439-2007-art-110:conceptos-ingreso-excluidos-volumen-agrario",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=date(2018, 12, 23),
        ),
        unsupported_query=EntitySetFactQuery(
            fact_id="rd-439-2007-art-110:conceptos-ingreso-excluidos-volumen-agrario",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=date(2018, 12, 22),
        ),
    ),
)
"""One exact authority coordinate per migrated legal domain.

Each negative coordinate is intentionally not a nearest-match query.  It
proves that a source window or selector outside the legally authored surface
cannot silently resolve through a neighbouring variant.
"""


def cross_domain_fact_findings(
    authority: ValidatedRegistryAuthority,
    *,
    source_root: Path,
    probes: tuple[CrossDomainFactProbe, ...] = CROSS_DOMAIN_FACT_PROBES,
) -> tuple[CrossDomainFactFinding, ...]:
    """Return every cross-domain authority, evidence, or refusal defect."""
    findings: list[CrossDomainFactFinding] = []
    evidence = EvidenceValidator(
        legal_refs=authority.catalogues.legal,
        source_refs=authority.catalogues.sources,
        source_root=source_root,
    )
    for probe in probes:
        try:
            resolved = authority.resolve_governed_fact(probe.query)
        except RegistryValidationError as error:
            findings.append(
                CrossDomainFactFinding(
                    CrossDomainFactFindingKind.RESOLUTION_FAILED,
                    probe.domain,
                    probe.query.fact_id,
                    str(error),
                )
            )
            continue

        if not resolved.legal_refs and not resolved.source_refs:
            findings.append(
                CrossDomainFactFinding(
                    CrossDomainFactFindingKind.PROVENANCE_MISSING,
                    probe.domain,
                    resolved.fact_id,
                    "resolved fact carries neither legal nor source provenance",
                )
            )
        for legal_ref_id in resolved.legal_refs:
            reference = authority.catalogues.legal.get(legal_ref_id)
            if reference is None:
                findings.append(
                    CrossDomainFactFinding(
                        CrossDomainFactFindingKind.LEGAL_REFERENCE_UNREGISTERED,
                        probe.domain,
                        resolved.fact_id,
                        f"resolved legal reference {legal_ref_id!r} is not registered",
                    )
                )
                continue
            try:
                verify_legal_reference_grounding(reference, source_root=source_root)
            except RegistryValidationError as error:
                findings.append(
                    CrossDomainFactFinding(
                        CrossDomainFactFindingKind.CORPUS_GROUNDING_FAILED,
                        probe.domain,
                        resolved.fact_id,
                        f"legal reference {legal_ref_id!r}: {error}",
                    )
                )
        source_ref_ids = set(authority.catalogues.sources)
        for source_ref_id in resolved.source_refs:
            if source_ref_id not in source_ref_ids:
                findings.append(
                    CrossDomainFactFinding(
                        CrossDomainFactFindingKind.SOURCE_REFERENCE_UNREGISTERED,
                        probe.domain,
                        resolved.fact_id,
                        f"resolved source reference {source_ref_id!r} is not registered",
                    )
                )
                continue
            citations = tuple(
                citation for citation in resolved.source_citations if citation.source_ref == source_ref_id
            )
            failures = evidence.validate_source_citations(
                "cross-domain governed fact",
                f"{resolved.fact_id}:{resolved.variant_id}",
                (source_ref_id,),
                citations,
                str(authority.catalogues.sources[source_ref_id].evidence_tier),
            )
            for failure in failures:
                findings.append(
                    CrossDomainFactFinding(
                        CrossDomainFactFindingKind.SOURCE_CITATION_INVALID,
                        probe.domain,
                        resolved.fact_id,
                        failure,
                    )
                )

        try:
            authority.resolve_governed_fact(probe.unsupported_query)
        except RegistryValidationError:
            continue
        findings.append(
            CrossDomainFactFinding(
                CrossDomainFactFindingKind.UNSUPPORTED_APPLICABILITY_ACCEPTED,
                probe.domain,
                probe.query.fact_id,
                "unsupported applicability coordinate resolved instead of refusing",
            )
        )
    return tuple(findings)


def main(argv: list[str] | None = None) -> int:
    """Run the development-only cross-domain governed-fact authority gate."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--source-root", type=Path, default=bundled_path())
    args = parser.parse_args(argv)
    findings = cross_domain_fact_findings(compiled_bundled_authority(), source_root=args.source_root)
    for finding in findings:
        sys.stdout.write(f"{finding.kind} domain={finding.domain} fact={finding.fact_id} detail={finding.detail}\n")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
