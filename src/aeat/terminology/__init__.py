"""The Terminology Handbook: concept-oriented vocabulary for the docs.

This package owns the committed authoring tree under
``src/aeat/_data/terminology/`` and the strict loader that compiles it
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
canonical :class:`~aeat.core.external_constants.OutputLanguage`, while
the Handbook-local axes :class:`ConceptDomain`, :class:`ConceptLifecycle`,
and :class:`TermStatus` live in this package beside the schema they
constrain.
"""

from __future__ import annotations

from ._enums import ConceptDomain, ConceptLifecycle, TermStatus
from ._errors import TerminologyError, TerminologyLoadError, TerminologyValidationError
from ._loader import (
    HandbookValidator,
    TerminologyHandbook,
    load_bundled_terminology_handbook,
    load_terminology_handbook,
    terminology_concepts_dir,
)
from ._schema import (
    ConceptRecord,
    GrammaticalGender,
    LanguageSection,
    LanguageSource,
    PartOfSpeech,
    SeedProvenance,
    TermSection,
)
from ._validators import (
    approved_completeness_validator,
    default_handbook_validators,
    id_uniqueness_validator,
    legal_refs_resolve_validator,
    lifecycle_replaced_by_validator,
    relation_integrity_validator,
)

__all__ = [
    "ConceptDomain",
    "ConceptLifecycle",
    "ConceptRecord",
    "GrammaticalGender",
    "HandbookValidator",
    "LanguageSection",
    "LanguageSource",
    "PartOfSpeech",
    "SeedProvenance",
    "TermSection",
    "TermStatus",
    "TerminologyError",
    "TerminologyHandbook",
    "TerminologyLoadError",
    "TerminologyValidationError",
    "approved_completeness_validator",
    "default_handbook_validators",
    "id_uniqueness_validator",
    "legal_refs_resolve_validator",
    "lifecycle_replaced_by_validator",
    "load_bundled_terminology_handbook",
    "load_terminology_handbook",
    "relation_integrity_validator",
    "terminology_concepts_dir",
]
