"""The Terminology Handbook: concept-oriented vocabulary for the docs.

This package owns the committed authoring tree under
``src/cadrumo/_data/terminology/`` and the strict loader that compiles it
into typed records. The Handbook is the middle layer between registry
compilation and the shipped documentation search surface: enrolment
sources (registry, legal catalogue, enums, CLI tree, locales) scaffold
concepts here, the concepts are curated, and the compiled records feed
the offline docs search and generated glossary.

The schema follows the TBX / ISO 30042 three-tier concept-oriented
model -- :class:`ConceptRecord` owns :class:`LanguageSection` per output
language, each owning :class:`TermSection` -- with SKOS relation and
label borrowings. ``narrower`` is derived by
:func:`load_terminology_handbook` from authored ``broader`` edges; it is
never authored on a fragment.

Closed value sets are typed: the four output languages reuse the
canonical :class:`~cadrumo.core.external_constants.OutputLanguage` and the
concept lifecycle reuses :class:`~cadrumo.core.ConceptLifecycle` (shared
with the shipped product terminology search), while the Handbook-local axes
:class:`ConceptDomain` and :class:`TermStatus` live in this package beside
the schema they constrain.
"""

from __future__ import annotations

from ._curation import (
    AuditReport,
    CurationError,
    audit_handbook,
    relate_concepts,
    remove_term,
    retire_concept,
    set_language_field,
    set_term,
)
from ._enrolment import EnrolmentCandidate, SeedLabel, collect_enrolment_candidates
from ._scaffold import (
    ScaffoldAction,
    ScaffoldEntry,
    ScaffoldPlan,
    apply_scaffold_plan,
    build_scaffold_plan,
    scaffold_handbook,
)
from ._seed_import import (
    SeedApplyResult,
    SeedEntry,
    SeedImportError,
    SeedLicenceError,
    SeedSource,
    SeedTerm,
    apply_seed_entries,
    assert_source_ingestible,
    parse_iate_tbx,
    parse_ubterm_csv,
    source_attribution,
)
from ._serialize import serialise_concept
from .enums import ConceptDomain, TermStatus
from .loader import (
    HandbookValidator,
    TerminologyHandbook,
    load_bundled_terminology_handbook,
    load_terminology_handbook,
    terminology_concepts_dir,
)
from .schema import (
    ConceptRecord,
    GrammaticalGender,
    LanguageSection,
    LanguageSource,
    PartOfSpeech,
    SeedProvenance,
    TermSection,
)
from .validators import (
    approved_completeness_validator,
    default_handbook_validators,
    id_uniqueness_validator,
    legal_refs_resolve_validator,
    lifecycle_replaced_by_validator,
    relation_integrity_validator,
)

__all__ = [
    "AuditReport",
    "ConceptDomain",
    "ConceptRecord",
    "CurationError",
    "EnrolmentCandidate",
    "GrammaticalGender",
    "HandbookValidator",
    "LanguageSection",
    "LanguageSource",
    "PartOfSpeech",
    "ScaffoldAction",
    "ScaffoldEntry",
    "ScaffoldPlan",
    "SeedApplyResult",
    "SeedEntry",
    "SeedImportError",
    "SeedLabel",
    "SeedLicenceError",
    "SeedProvenance",
    "SeedSource",
    "SeedTerm",
    "TermSection",
    "TermStatus",
    "TerminologyHandbook",
    "apply_scaffold_plan",
    "apply_seed_entries",
    "approved_completeness_validator",
    "assert_source_ingestible",
    "audit_handbook",
    "build_scaffold_plan",
    "collect_enrolment_candidates",
    "default_handbook_validators",
    "id_uniqueness_validator",
    "legal_refs_resolve_validator",
    "lifecycle_replaced_by_validator",
    "load_bundled_terminology_handbook",
    "load_terminology_handbook",
    "parse_iate_tbx",
    "parse_ubterm_csv",
    "relate_concepts",
    "relation_integrity_validator",
    "remove_term",
    "retire_concept",
    "scaffold_handbook",
    "serialise_concept",
    "set_language_field",
    "set_term",
    "source_attribution",
    "terminology_concepts_dir",
]
