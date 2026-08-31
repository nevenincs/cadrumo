"""The Terminology Handbook concept lifecycle closed value set.

A Handbook concept fragment (``_data/terminology/concepts/*.toml``) declares
one ``lifecycle`` token, and that axis is read on both sides of the shipping
boundary: the build-time glossary generator and Pagefind card projector select
``approved`` concepts for publication, and the shipped product reader
(:func:`~application.corpus_search.search_terminology`) filters the runtime
terminology search on the same token. Only the value set lives here — deciding
which concepts *hold* which lifecycle stays an authoring judgement (the
``aeat-documentation`` discipline reserves ``approved`` for
taxpayer- and operator-facing vocabulary and keeps internal machinery concepts
``deprecated`` but dev-resolvable).

The set is declared as a :class:`enum.StrEnum` in ``core`` per the
core-authority discipline (closed axes live in ``core/``, hydrated at
boundaries, asserted as members in tests). ``core`` is the only home both
sides can reach: the terminology-handbook authoring tooling that
compiles the fragments is not shipped in the wheel, so a declaration living
beside that schema is unimportable from ``cadrumo``. This mirrors the
already-shared four-language axis
(:class:`~core.external_constants.OutputLanguage`), which the Handbook schema
likewise consumes from ``core`` rather than redeclaring. The
Handbook-internal axes with no shipped reader — ``ConceptDomain`` and
``TermStatus`` — stay declared beside the schema they constrain.

Each member's value is byte-identical to the token stored in the concept
fragments, so a stored ``lifecycle`` hydrates to its member and an unknown
token is refused at the boundary rather than silently filtered out.
"""

from __future__ import annotations

from enum import StrEnum


class ConceptLifecycle(StrEnum):
    """Four-state lifecycle of a Terminology Handbook concept.

    A concept moves ``DRAFT`` (scaffolded, curation pending) -> ``APPROVED``
    (curated, shippable) and may later be ``DEPRECATED`` (discouraged but
    still resolvable) or ``RETIRED`` (tombstoned). A ``RETIRED`` concept MUST
    carry ``replaced_by``; records are never deleted, only inactivated (the
    SNOMED immutable-id inactivation pattern the git-native Handbook borrows).

    Attributes:
        DRAFT: Scaffolded by the authoring tooling, curation pending. Excluded
            from the generated glossary, the shipped Pagefind index, and the
            product terminology search.
        APPROVED: Curated and ratified taxpayer- or operator-facing
            vocabulary. The only lifecycle that publishes and the only one the
            shipped search surfaces by default.
        DEPRECATED: Discouraged but still resolvable — the home of internal
            machinery concepts that stay available to the developer/agent
            corpus while excluded from the taxpayer glossary.
        RETIRED: Tombstoned, carrying a ``replaced_by`` successor.
    """

    DRAFT = "draft"
    APPROVED = "approved"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


__all__ = ["ConceptLifecycle"]
