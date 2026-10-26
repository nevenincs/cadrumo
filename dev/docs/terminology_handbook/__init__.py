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
concept lifecycle reuses :class:`~cadrumo.core.concept_lifecycle.ConceptLifecycle` (shared
with the shipped product terminology search), while the Handbook-local axes
:class:`ConceptDomain` and :class:`TermStatus` live in this package beside
the schema they constrain.

Every symbol this package defines is imported from the module that defines it;
this initialiser is an inert namespace marker and forwards nothing.
"""
