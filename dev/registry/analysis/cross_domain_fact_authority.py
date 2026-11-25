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
from datetime import date, timedelta
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
    ResolvedGovernedFact,
    ScalarFactQuery,
)
from cadrumo.domain.calculations.registry.facts.variants import FactSelector, GovernedFactVariant
from cadrumo.domain.calculations.registry.schema_base import DateAxis

from ..compiler.authority import compiled_bundled_authority
from ..compiler.legal_grounding import verify_legal_reference_grounding
from ..compiler.validate_evidence import EvidenceValidator

__all__ = [
    "CrossDomainFactFinding",
    "CrossDomainFactFindingKind",
    "CrossDomainFactProbe",
    "cross_domain_fact_findings",
    "cross_domain_fact_probes",
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


def cross_domain_fact_probes(authority: ValidatedRegistryAuthority) -> tuple[CrossDomainFactProbe, ...]:
    """Return one authority coordinate per migrated legal domain, read from the authority.

    Each positive coordinate sits inside the supported envelope and inside the
    window of the variant it probes. Each negative coordinate is intentionally
    not a nearest-match query: it is the day just outside an authored variant
    window, or a selector no variant declares, so it proves that a coordinate
    outside the legally authored surface cannot silently resolve through a
    neighbouring variant.
    """
    support = authority.catalogues.require_supported_filing_years()
    supported_date = date(support.horizon, 12, 31)
    floor_date = date(support.floor, 1, 1)
    m347 = _earliest_variant_reaching(authority, "m347-counterparty-declaration-threshold", (), supported_date)
    family = _earliest_variant_reaching(authority, "lirpf-art-58-descendant-ordinary-maximum-age", (), supported_date)
    iva_rate_track = (
        FactSelector(name="member_state", value="es"),
        FactSelector(name="kind", value="general"),
    )
    recargo_track = (FactSelector(name="applied_rate", value=Decimal("0.05")),)
    recargo = _only_variant(authority, "iva-recargo-by-applied-rate", recargo_track)
    convenio_track = (
        FactSelector(name="country_code", value="DE"),
        FactSelector(name="tipo_renta", value="dividend"),
    )
    convenio = _only_variant(authority, "irnr.convenio.override", convenio_track)
    holiday_track = (FactSelector(name="jurisdiction", value="national"),)
    holiday, working_day = _first_event_and_next_working_day(
        authority, "deadlines.public-holiday", holiday_track, support.horizon
    )
    return (
        CrossDomainFactProbe(
            domain="modelo-347-threshold",
            query=ScalarFactQuery(
                fact_id="m347-counterparty-declaration-threshold",
                date_axis=DateAxis.FILING_PERIOD,
                effective_date=supported_date,
            ),
            unsupported_query=ScalarFactQuery(
                fact_id="m347-counterparty-declaration-threshold",
                date_axis=DateAxis.FILING_PERIOD,
                effective_date=_eve_of(m347),
            ),
        ),
        CrossDomainFactProbe(
            domain="renta-family-window",
            query=ScalarFactQuery(
                fact_id="lirpf-art-58-descendant-ordinary-maximum-age",
                date_axis=DateAxis.FILING_PERIOD,
                effective_date=supported_date,
            ),
            unsupported_query=ScalarFactQuery(
                fact_id="lirpf-art-58-descendant-ordinary-maximum-age",
                date_axis=DateAxis.FILING_PERIOD,
                effective_date=_eve_of(family),
            ),
        ),
        CrossDomainFactProbe(
            domain="iva-rate",
            query=MappingFactQuery(
                fact_id="iva-rate-schedule",
                date_axis=DateAxis.DEVENGO_DATE,
                effective_date=supported_date,
                selectors=(*iva_rate_track, FactSelector(name="rate_role", value="ordinary")),
            ),
            unsupported_query=MappingFactQuery(
                fact_id="iva-rate-schedule",
                date_axis=DateAxis.DEVENGO_DATE,
                effective_date=supported_date,
                selectors=(*iva_rate_track, FactSelector(name="rate_role", value="unsupported-role")),
            ),
        ),
        CrossDomainFactProbe(
            domain="iva-recargo",
            query=MappingFactQuery(
                fact_id="iva-recargo-by-applied-rate",
                date_axis=DateAxis.DEVENGO_DATE,
                effective_date=max(recargo.valid_from or floor_date, floor_date),
                selectors=recargo_track,
            ),
            unsupported_query=MappingFactQuery(
                fact_id="iva-recargo-by-applied-rate",
                date_axis=DateAxis.DEVENGO_DATE,
                effective_date=_morrow_of(recargo),
                selectors=recargo_track,
            ),
        ),
        CrossDomainFactProbe(
            domain="irnr-convenio",
            query=OverrideFactQuery(
                fact_id="irnr.convenio.override",
                date_axis=DateAxis.DEVENGO_DATE,
                effective_date=max(convenio.valid_from or floor_date, floor_date),
                selectors=convenio_track,
            ),
            unsupported_query=OverrideFactQuery(
                fact_id="irnr.convenio.override",
                date_axis=DateAxis.DEVENGO_DATE,
                effective_date=_eve_of(convenio),
                selectors=convenio_track,
            ),
        ),
        CrossDomainFactProbe(
            domain="deadline-holiday",
            query=EventFactQuery(
                fact_id="deadlines.public-holiday",
                date_axis=DateAxis.SUBMISSION_DATE,
                effective_date=holiday,
                selectors=holiday_track,
            ),
            unsupported_query=EventFactQuery(
                fact_id="deadlines.public-holiday",
                date_axis=DateAxis.SUBMISSION_DATE,
                effective_date=working_day,
                selectors=holiday_track,
            ),
        ),
        CrossDomainFactProbe(
            domain="modelo-131-income-exclusion",
            # The authored variant opens below the floor and never closes, so the
            # coordinate that reaches it has to sit inside the SUPPORTED span: a
            # query below the floor is refused for being out of support, which says
            # nothing about the fact. The negative therefore cannot be "one day
            # earlier" here -- that date is below the floor too -- so it is a
            # selector the variant does not declare, which is the other half of what
            # this table proves.
            query=EntitySetFactQuery(
                fact_id="rd-439-2007-art-110:conceptos-ingreso-excluidos-volumen-agrario",
                date_axis=DateAxis.FILING_PERIOD,
                effective_date=supported_date,
            ),
            unsupported_query=EntitySetFactQuery(
                fact_id="rd-439-2007-art-110:conceptos-ingreso-excluidos-volumen-agrario",
                date_axis=DateAxis.FILING_PERIOD,
                effective_date=supported_date,
                selectors=(FactSelector(name="jurisdiction", value="no-such-jurisdiction"),),
            ),
        ),
    )


def _track_variants(
    authority: ValidatedRegistryAuthority, fact_id: str, track: tuple[FactSelector, ...]
) -> tuple[GovernedFactVariant, ...]:
    """Return the authored variants whose selectors are exactly ``track``."""
    wanted = {(selector.name, selector.value) for selector in track}
    return tuple(
        variant
        for variant in authority.catalogues.facts.facts[fact_id].variants
        if {(selector.name, selector.value) for selector in variant.selectors} == wanted
    )


def _only_variant(
    authority: ValidatedRegistryAuthority, fact_id: str, track: tuple[FactSelector, ...]
) -> GovernedFactVariant:
    variants = _track_variants(authority, fact_id, track)
    if len(variants) != 1:
        raise RegistryValidationError(
            f"cross-domain probe for {fact_id!r} expects one authored variant on its track, found {len(variants)}"
        )
    return variants[0]


def _earliest_variant_reaching(
    authority: ValidatedRegistryAuthority, fact_id: str, track: tuple[FactSelector, ...], on: date
) -> GovernedFactVariant:
    """Return a track's earliest variant, refusing a track that does not reach ``on``."""
    variants = sorted(_track_variants(authority, fact_id, track), key=lambda variant: variant.valid_from or date.min)
    if not any(_covers(variant, on) for variant in variants):
        raise RegistryValidationError(f"cross-domain probe for {fact_id!r} has no authored variant covering {on}")
    return variants[0]


def _covers(variant: GovernedFactVariant, on: date) -> bool:
    opens = variant.valid_from is None or variant.valid_from <= on
    return opens and (variant.valid_to is None or on <= variant.valid_to)


def _eve_of(variant: GovernedFactVariant) -> date:
    """Return the day before a variant's authored opening."""
    if variant.valid_from is None:
        raise RegistryValidationError(f"variant {variant.variant_id!r} authors no opening to probe before")
    return variant.valid_from - timedelta(days=1)


def _morrow_of(variant: GovernedFactVariant) -> date:
    """Return the day after a variant's authored closing."""
    if variant.valid_to is None:
        raise RegistryValidationError(f"variant {variant.variant_id!r} authors no closing to probe after")
    return variant.valid_to + timedelta(days=1)


def _first_event_and_next_working_day(
    authority: ValidatedRegistryAuthority, fact_id: str, track: tuple[FactSelector, ...], year: int
) -> tuple[date, date]:
    """Return the first authored event of ``year`` and the first later day that is no event."""
    events = {variant.valid_from for variant in _track_variants(authority, fact_id, track) if variant.valid_from}
    in_year = sorted(day for day in events if day.year == year)
    if not in_year:
        raise RegistryValidationError(f"cross-domain probe for {fact_id!r} finds no authored event in {year}")
    following = in_year[0] + timedelta(days=1)
    while following in events:
        following += timedelta(days=1)
    return in_year[0], following


def cross_domain_fact_findings(
    authority: ValidatedRegistryAuthority,
    *,
    source_root: Path,
    probes: tuple[CrossDomainFactProbe, ...] | None = None,
) -> tuple[CrossDomainFactFinding, ...]:
    """Return every cross-domain authority, evidence, or refusal defect."""
    evidence = EvidenceValidator(
        legal_refs=authority.catalogues.legal,
        source_refs=authority.catalogues.sources,
        source_root=source_root,
    )
    findings = (
        finding
        for probe in (cross_domain_fact_probes(authority) if probes is None else probes)
        for finding in _probe_findings(probe, authority=authority, evidence=evidence, source_root=source_root)
    )
    return tuple(findings)


def _probe_findings(
    probe: CrossDomainFactProbe,
    *,
    authority: ValidatedRegistryAuthority,
    evidence: EvidenceValidator,
    source_root: Path,
) -> tuple[CrossDomainFactFinding, ...]:
    """Check one supported coordinate, retaining findings in contract order."""
    try:
        resolved = authority.resolve_governed_fact(probe.query)
    except RegistryValidationError as error:
        return (
            CrossDomainFactFinding(
                CrossDomainFactFindingKind.RESOLUTION_FAILED,
                probe.domain,
                probe.query.fact_id,
                str(error),
            ),
        )

    findings: list[CrossDomainFactFinding] = []
    if not resolved.legal_refs and not resolved.source_refs:
        findings.append(
            CrossDomainFactFinding(
                CrossDomainFactFindingKind.PROVENANCE_MISSING,
                probe.domain,
                resolved.fact_id,
                "resolved fact carries neither legal nor source provenance",
            )
        )
    findings.extend(_legal_reference_findings(probe, resolved, authority=authority, source_root=source_root))
    findings.extend(_source_reference_findings(probe, resolved, authority=authority, evidence=evidence))
    unsupported_finding = _unsupported_query_finding(probe, authority=authority)
    if unsupported_finding is not None:
        findings.append(unsupported_finding)
    return tuple(findings)


def _legal_reference_findings(
    probe: CrossDomainFactProbe,
    resolved: ResolvedGovernedFact,
    *,
    authority: ValidatedRegistryAuthority,
    source_root: Path,
) -> tuple[CrossDomainFactFinding, ...]:
    findings: list[CrossDomainFactFinding] = []
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
    return tuple(findings)


def _source_reference_findings(
    probe: CrossDomainFactProbe,
    resolved: ResolvedGovernedFact,
    *,
    authority: ValidatedRegistryAuthority,
    evidence: EvidenceValidator,
) -> tuple[CrossDomainFactFinding, ...]:
    findings: list[CrossDomainFactFinding] = []
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
        citations = tuple(citation for citation in resolved.source_citations if citation.source_ref == source_ref_id)
        failures = evidence.validate_source_citations(
            "cross-domain governed fact",
            f"{resolved.fact_id}:{resolved.variant_id}",
            (source_ref_id,),
            citations,
            str(authority.catalogues.sources[source_ref_id].evidence_tier),
        )
        findings.extend(
            CrossDomainFactFinding(
                CrossDomainFactFindingKind.SOURCE_CITATION_INVALID,
                probe.domain,
                resolved.fact_id,
                failure,
            )
            for failure in failures
        )
    return tuple(findings)


def _unsupported_query_finding(
    probe: CrossDomainFactProbe,
    *,
    authority: ValidatedRegistryAuthority,
) -> CrossDomainFactFinding | None:
    try:
        authority.resolve_governed_fact(probe.unsupported_query)
    except RegistryValidationError:
        return None
    return CrossDomainFactFinding(
        CrossDomainFactFindingKind.UNSUPPORTED_APPLICABILITY_ACCEPTED,
        probe.domain,
        probe.query.fact_id,
        "unsupported applicability coordinate resolved instead of refusing",
    )


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
