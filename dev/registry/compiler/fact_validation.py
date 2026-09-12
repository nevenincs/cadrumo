"""Catalogue-level validation for registry-governed facts."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from datetime import timedelta
from itertools import pairwise
from pathlib import Path

from cadrumo.core.corpus_text import normalise_corpus_text
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.facts.schema import GovernedFact, GovernedFactCatalogue, GovernedFactVariant
from cadrumo.domain.calculations.registry.schema_base import DateAxis
from cadrumo.domain.calculations.registry.schema_references import LegalReference, SourceReference

from . import fact_providers
from .legal_grounding import verify_legal_reference_grounding
from .validate_evidence import EvidenceValidator

__all__ = ["governed_fact_catalogue_failures", "retired_fact_provider_closure_failures"]


# These facts replaced the retired global provider. Keep the
# campaign boundary as identities rather than copying its legally operative
# values into Python: the fragments remain the one value authority.
_RETIRED_FACT_PROVIDER_IDS = frozenset(
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
        "rd-439-2007-art-110:conceptos-ingreso-excluidos-volumen-agrario",
        "rd-439-2007-art-109:conceptos-ingreso-excluidos-base-agraria",
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


def retired_fact_provider_closure_failures(
    catalogue: GovernedFactCatalogue,
    *,
    source_refs: Mapping[str, SourceReference],
) -> tuple[str, ...]:
    """Return closure failures for the bounded retired-parameter migration.

    The test-facing gate deliberately checks identities, filing-period
    coordinates, and source-backed windows only.  It must never become another
    declaration of rates, thresholds, or activity classifications.

    The gate stops where the migration does. The retired parameters became
    governed facts, so the obligation to author them exists only in a registry
    that enrolls governed-fact providers. A registry that enrolls no fact
    providers has no migration to close and yields no failure. Enrollment is
    read from the canonical provider declaration at call time, never from a
    path or a modelo.
    """
    if not fact_providers.FACT_PROVIDER_REGISTRATIONS:
        return ()
    failures: list[str] = []
    for fact_id in sorted(_RETIRED_FACT_PROVIDER_IDS):
        fact = catalogue.facts.get(fact_id)
        if fact is None:
            failures.append(f"retired-provider fact {fact_id!r} is not authored")
            continue
        failures.extend(_temporal_coverage_failures(fact))
        for variant in fact.variants:
            context = f"retired-provider fact {fact_id!r} variant {variant.variant_id!r}"
            if variant.date_axis is not DateAxis.FILING_PERIOD:
                failures.append(f"{context} must use the filing_period date axis")
            if not variant.source_refs or not variant.source_citations:
                failures.append(f"{context} must retain source provenance")
                continue
            if not any(
                _source_window_covers_variant(fact, source_refs.get(source_ref), variant)
                for source_ref in variant.source_refs
            ):
                failures.append(f"{context} has no cited source covering its temporal applicability window")
    return tuple(failures)


def _temporal_coverage_failures(fact: GovernedFact) -> tuple[str, ...]:
    """Require continuous coverage independently on every exact temporal track."""
    windows = fact.materialized_windows()
    tracks: dict[tuple[object, ...], list[GovernedFactVariant]] = {}
    for variant in fact.variants:
        tracks.setdefault(fact.track_key(variant), []).append(variant)
    failures: list[str] = []
    for track, variants in tracks.items():
        ordered = tuple(sorted(variants, key=lambda variant: windows[variant.variant_id].valid_from))
        for current, successor in pairwise(ordered):
            current_window = windows[current.variant_id]
            successor_window = windows[successor.variant_id]
            if (
                current_window.valid_to is None
                or current_window.valid_to + timedelta(days=1) != successor_window.valid_from
            ):
                failures.append(
                    f"retired-provider fact {fact.fact_id!r} track {track!r} has a gap in its "
                    "source-grounded temporal coverage",
                )
        if windows[ordered[-1].variant_id].valid_to is not None and fact.support is None:
            failures.append(
                f"retired-provider fact {fact.fact_id!r} track {track!r} must retain an open current "
                "applicability window or declare bounded support",
            )
    return tuple(failures)


def _source_window_covers_variant(
    fact: GovernedFact,
    source: SourceReference | None,
    variant: GovernedFactVariant,
) -> bool:
    window = fact.validity_window(variant)
    if source is None or source.applies_from is None or source.applies_from > window.valid_from:
        return False
    return source.applies_to is None or (window.valid_to is not None and source.applies_to >= window.valid_to)
