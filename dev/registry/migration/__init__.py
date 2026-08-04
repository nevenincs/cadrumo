"""Read-only source inventory primitives for the disposable registry migration.

This package deliberately owns only the migration source contract. It reads the
current registry compiler, records a content-addressed source tree, and indexes
the supported ``(modelo, revision)`` identities. It does not emit catalogues,
write migration artifacts, or expose a production registry mutation path.

See Also:
    :mod:`dev.registry.migration.manager`
        Strict records and the read-only inventory builder.
    :mod:`cadrumo.domain.calculations.registry`
        Canonical registry compiler used as the source of supported revisions.
"""

from __future__ import annotations

from .manager import (
    CandidateClassification,
    CanonicalOccurrenceCandidate,
    CanonicalOccurrenceCandidates,
    ClassifiedOccurrenceCandidate,
    ClassifiedOccurrenceCandidates,
    CorpusFileFingerprint,
    CorpusFingerprint,
    MigrationInventoryError,
    MigrationSourceInventory,
    ResolvedLocalizationEntry,
    ResolvedLocalizationMatrix,
    RevisionInventoryEntry,
    build_source_inventory,
    canonical_occurrence_key,
    classify_canonical_occurrence_candidates,
    extract_resolved_localization_matrix,
    fingerprint_registry_corpus,
    generate_canonical_occurrence_candidates,
)

__all__ = [
    "CandidateClassification",
    "CanonicalOccurrenceCandidate",
    "CanonicalOccurrenceCandidates",
    "ClassifiedOccurrenceCandidate",
    "ClassifiedOccurrenceCandidates",
    "CorpusFileFingerprint",
    "CorpusFingerprint",
    "MigrationInventoryError",
    "MigrationSourceInventory",
    "ResolvedLocalizationEntry",
    "ResolvedLocalizationMatrix",
    "RevisionInventoryEntry",
    "build_source_inventory",
    "canonical_occurrence_key",
    "classify_canonical_occurrence_candidates",
    "extract_resolved_localization_matrix",
    "fingerprint_registry_corpus",
    "generate_canonical_occurrence_candidates",
]
