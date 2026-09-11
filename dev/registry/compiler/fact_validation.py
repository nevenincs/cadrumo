"""Catalogue-level validation for registry-governed facts."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from datetime import date, timedelta
from itertools import pairwise
from pathlib import Path

from cadrumo.core.corpus_text import normalise_corpus_text
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.facts.schema import GovernedFact, GovernedFactCatalogue, GovernedFactVariant
from cadrumo.domain.calculations.registry.schema_base import DateAxis
from cadrumo.domain.calculations.registry.schema_references import LegalReference, SourceReference

from ._validate_evidence import EvidenceValidator
from .legal_grounding import verify_legal_reference_grounding

__all__ = ["governed_fact_catalogue_failures", "migrated_legal_parameter_fact_failures"]


# These facts replaced the former global legal-parameter provider.  Keep the
# campaign boundary as identities rather than copying its legally operative
# values into Python: the fragments remain the one value authority.
_MIGRATED_LEGAL_PARAMETER_FACT_IDS = frozenset(
    {
        "lirpf-art-101:retencion-administrador-general",
        "lirpf-art-101:retencion-administrador-reducida",
        "lirpf-art-101:retencion-administrador-incn-umbral-eur",
        "rirpf-art-95:retencion-actividades-profesionales-general",
        "rirpf-art-95:retencion-actividades-profesionales-inicio",
        "rirpf-art-95:retencion-actividades-profesionales-colectivos-especificos",
        "rirpf-art-95:retencion-actividades-agricolas-ganaderas-general",
        "rirpf-art-95:retencion-actividades-ganaderas-engorde-porcino-avicultura",
        "rirpf-art-95:retencion-actividades-forestales",
        "rirpf-art-95:retencion-actividades-estimacion-objetiva",
        "rirpf-art-95:selector-m036-actividades-profesionales",
        "rirpf-art-95:selector-m036-actividades-agricolas-ganaderas",
        "rirpf-art-95:selector-m036-actividades-forestales",
        "rirpf-art-95:selector-m036-actividades-ganaderas-engorde-porcino-avicultura",
        "rd-439-2007-art-109:selector-m036-actividades-exencion-pago-fraccionado",
        "rd-439-2007-art-109:selector-m036-actividades-base-neta-de-subvenciones",
        "rd-439-2007-art-110:selector-m036-actividades-pago-fraccionado-agrarias-pesqueras",
        "modelo-131:selector-m036-volumen-ingresos-agrario",
        "liva-art-161:recargo-rate-general",
        "liva-art-161:recargo-rate-reducido",
        "liva-art-161:recargo-rate-super-reducido",
        "liva-art-161:recargo-rate-tabaco",
        "lirpf-dt-32:eo-exclusion-rendimientos-conjunto-eur",
        "lirpf-dt-32:eo-exclusion-rendimientos-factura-eur",
        "lirpf-art-31:eo-exclusion-rendimientos-agricolas-ganaderos-forestales-eur",
        "lirpf-dt-32:eo-exclusion-compras-eur",
    }
)


def governed_fact_catalogue_failures(
    catalogue: GovernedFactCatalogue,
    *,
    legal_ref_ids: Collection[str],
    source_ref_ids: Collection[str],
    legal_refs: Mapping[str, LegalReference] | None = None,
    source_refs: Mapping[str, SourceReference] | None = None,
    source_root: Path | None = None,
) -> tuple[str, ...]:
    """Return structural and evidence-grounding failures for every governed variant."""
    failures: list[str] = []
    verified_legal: set[str] = set()
    evidence = EvidenceValidator(
        legal_refs={} if legal_refs is None else legal_refs,
        source_refs={} if source_refs is None else source_refs,
        source_root=source_root,
    )
    for fact_id, fact in sorted(catalogue.facts.items()):
        failures.extend(_fact_precedence_failures(fact))
        for variant in fact.variants:
            if not variant.legal_refs and not variant.source_refs:
                failures.append(
                    f"governed fact {fact_id!r} variant {variant.variant_id!r} "
                    "must declare a complete legal or source evidence lane",
                )
            failures.extend(
                f"governed fact {fact_id!r} variant {variant.variant_id!r} references unknown legal id {ref!r}"
                for ref in variant.legal_refs
                if ref not in legal_ref_ids
            )
            failures.extend(
                f"governed fact {fact_id!r} variant {variant.variant_id!r} references unknown source id {ref!r}"
                for ref in variant.source_refs
                if ref not in source_ref_ids
            )
            cited = {citation.source_ref for citation in variant.source_citations}
            if cited != set(variant.source_refs):
                failures.append(
                    f"governed fact {fact_id!r} variant {variant.variant_id!r} citations must cover every source_ref",
                )
            if legal_refs is not None and source_root is not None:
                for ref_id in variant.legal_refs:
                    if ref_id in verified_legal:
                        continue
                    reference = legal_refs.get(ref_id)
                    if reference is None:
                        continue
                    try:
                        verify_legal_reference_grounding(reference, source_root=source_root)
                    except RegistryValidationError as exc:
                        failures.append(
                            f"governed fact {fact_id!r} variant {variant.variant_id!r} "
                            f"has invalid legal evidence {ref_id!r}: {exc}"
                        )
                    else:
                        verified_legal.add(ref_id)
            if source_refs is not None and source_root is not None:
                for citation in variant.source_citations:
                    reference = source_refs.get(citation.source_ref)
                    if reference is None:
                        continue
                    source_text = evidence.source_text(reference)
                    if source_text is None:
                        failures.append(
                            f"governed fact {fact_id!r} variant {variant.variant_id!r} "
                            f"cannot read source evidence {citation.source_ref!r}"
                        )
                        continue
                    for required_text in citation.required_text:
                        if normalise_corpus_text(required_text) not in source_text:
                            failures.append(
                                f"governed fact {fact_id!r} variant {variant.variant_id!r} source citation "
                                f"{citation.source_ref!r} missing text {required_text!r}"
                            )
    return tuple(failures)


def migrated_legal_parameter_fact_failures(
    catalogue: GovernedFactCatalogue,
    *,
    source_refs: Mapping[str, SourceReference],
) -> tuple[str, ...]:
    """Return closure failures for the bounded retired-parameter migration.

    The test-facing gate deliberately checks identities, filing-period
    coordinates, and source-backed windows only.  It must never become another
    declaration of rates, thresholds, or activity classifications.
    """
    failures: list[str] = []
    for fact_id in sorted(_MIGRATED_LEGAL_PARAMETER_FACT_IDS):
        fact = catalogue.facts.get(fact_id)
        if fact is None:
            failures.append(f"migrated legal-parameter fact {fact_id!r} is not authored")
            continue
        failures.extend(_temporal_coverage_failures(fact))
        for variant in fact.variants:
            context = f"migrated legal-parameter fact {fact_id!r} variant {variant.variant_id!r}"
            if variant.date_axis is not DateAxis.FILING_PERIOD:
                failures.append(f"{context} must use the filing_period date axis")
            if not variant.source_refs or not variant.source_citations:
                failures.append(f"{context} must retain source provenance")
                continue
            if not any(
                _source_window_covers_variant(source_refs.get(source_ref), variant)
                for source_ref in variant.source_refs
            ):
                failures.append(f"{context} has no cited source covering its temporal applicability window")
    return tuple(failures)


def _temporal_coverage_failures(fact: GovernedFact) -> tuple[str, ...]:
    """Require continuous coverage after the first source-grounded variant."""
    variants = tuple(sorted(fact.variants, key=lambda variant: variant.valid_from))
    failures: list[str] = []
    for current, successor in pairwise(variants):
        if current.valid_to is None or current.valid_to + timedelta(days=1) != successor.valid_from:
            failures.append(
                f"migrated legal-parameter fact {fact.fact_id!r} has a gap in its source-grounded temporal coverage",
            )
    if variants[-1].valid_to is not None:
        failures.append(
            f"migrated legal-parameter fact {fact.fact_id!r} must retain an open current applicability window",
        )
    return tuple(failures)


def _source_window_covers_variant(
    source: SourceReference | None,
    variant: GovernedFactVariant,
) -> bool:
    if source is None or source.applies_from > variant.valid_from:
        return False
    return source.applies_to is None or (variant.valid_to is not None and source.applies_to >= variant.valid_to)


def _fact_precedence_failures(fact: GovernedFact) -> tuple[str, ...]:
    edges = {variant.variant_id: variant.precedence_over for variant in fact.variants}
    failures: list[str] = []
    for variant in fact.variants:
        if _reaches(variant.variant_id, variant.variant_id, edges):
            failures.append(
                f"governed fact {fact.fact_id!r} variant {variant.variant_id!r} precedence graph contains a cycle",
            )
    for index, left in enumerate(fact.variants):
        for right in fact.variants[index + 1 :]:
            overlaps = _overlap(left, right)
            ordered = _reaches(left.variant_id, right.variant_id, edges) or _reaches(
                right.variant_id,
                left.variant_id,
                edges,
            )
            directly_ordered = right.variant_id in edges[left.variant_id] or left.variant_id in edges[right.variant_id]
            if overlaps and not ordered:
                failures.append(
                    f"governed fact {fact.fact_id!r} variants {left.variant_id!r} and {right.variant_id!r} "
                    "overlap without explicit precedence",
                )
            elif directly_ordered and not overlaps:
                failures.append(
                    f"governed fact {fact.fact_id!r} variants {left.variant_id!r} and {right.variant_id!r} "
                    "declare precedence across non-overlapping coordinates",
                )
    return tuple(failures)


def _selector_key(variant: GovernedFactVariant) -> tuple[tuple[str, str, str], ...]:
    return tuple(sorted((item.name, type(item.value).__name__, repr(item.value)) for item in variant.selectors))


def _overlap(left: GovernedFactVariant, right: GovernedFactVariant) -> bool:
    if left.date_axis != right.date_axis or _selector_key(left) != _selector_key(right):
        return False
    return left.valid_from <= (right.valid_to or date.max) and right.valid_from <= (left.valid_to or date.max)


def _reaches(start: str, target: str, edges: Mapping[str, tuple[str, ...]]) -> bool:
    pending = list(edges.get(start, ()))
    seen: set[str] = set()
    while pending:
        current = pending.pop()
        if current == target:
            return True
        if current not in seen:
            seen.add(current)
            pending.extend(edges.get(current, ()))
    return False
