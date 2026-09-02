"""The read-only session and controller behind the Modelo workspace destinations.

A session is one operator's read of one target. It holds what the producer
already settled and re-checks it; it resolves nothing itself, and it has no
mutation authority of any kind. Every judgement it makes is a comparison
between two projections the application layer produced.

The identity discipline is the whole point of this module. A workspace read
has TWO independent axes, and conflating them breaks both:

* the SEMANTIC axes -- ``target``, ``selected_revision_id`` and
  ``schema_identity`` -- name WHICH read this is;
* the LOCALE axes -- the locale summary and, through the contributor
  stamps, the baseline token -- name what LANGUAGE it was rendered in.

Two reads of the same target in different languages carry DIFFERENT
baselines, so staleness keys on the semantic axes ALONE. Keying it on the
baseline would make every language switch invalidate the whole session,
which would make a locale-only refresh impossible to express.

One measured caveat, because the obvious shortcut is wrong:
``baseline.locale_catalogue_digest`` is NOT a language discriminator. When
the requested language has no entry for a key, resolution falls back to
Spanish and reports the SPANISH shard's digest, so a Spanish read and an
English read that fell back carry the SAME digest. Spanish is the mandatory
source language for these catalogues, so that fallback is the common case
rather than an edge one. The locale SUMMARY is the honest axis: it keeps
``requested_language`` distinct from ``resolved_language`` precisely so the
fallback stays visible.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, assert_never

from .....application.modelo.workspace_models import (
    ModeloWorkspaceCursorV1,
    ModeloWorkspaceFacetName,
    ModeloWorkspaceGradedSnapshotResultV1,
    ModeloWorkspaceProjectionV1,
    ModeloWorkspaceRefusedResultV1,
    ModeloWorkspaceResultV1,
    ModeloWorkspaceStaticInspectionResultV1,
)
from .models import (
    ModeloWorkspaceBoundedPageV1,
    ModeloWorkspaceCompletePageV1,
    ModeloWorkspacePageCompletenessV1,
    ModeloWorkspaceRefusalViewV1,
    refusal_view,
)

SUPPORTED_WORKSPACE_CONTRACT_VERSION: Final[int] = 1
"""The one contract version this cohort reads.

Exact, never a floor: a future version may move a field this controller
narrows, so admitting ``>= 1`` would let a shape this code cannot read reach
a renderer. Refusing an unequal version is the forward-compatibility
posture, not a legacy one -- there is no older version to tolerate.
"""


class ModeloWorkspaceSessionAdmissionError(ValueError):
    """The result could not open a session and carried no typed refusal to explain it."""


@dataclass(frozen=True, slots=True)
class ModeloWorkspaceSemanticIdentityV1:
    """The three axes that say WHICH read this is, independent of language.

    Compared by value, so two reads agree exactly when they name the same
    target, the same law-selected revision, and the same registry schema.
    Deliberately excludes every locale-bearing field: a language switch must
    not read as a different workspace.
    """

    target_token: str
    selected_revision_id: str
    schema_identity_token: str


def semantic_identity(projection: ModeloWorkspaceProjectionV1) -> ModeloWorkspaceSemanticIdentityV1:
    """Read one projection's semantic identity, ignoring every locale axis."""
    return ModeloWorkspaceSemanticIdentityV1(
        target_token=projection.target.model_dump_json(),
        selected_revision_id=projection.target.law_selected_revision_id,
        schema_identity_token=projection.schema_identity.model_dump_json(),
    )


@dataclass(frozen=True, slots=True)
class ModeloWorkspaceReadSession:
    """One pinned, read-only workspace session over one admitted projection.

    Frozen: a refresh produces a NEW session rather than mutating this one,
    so a renderer holding a session can never observe it change underneath
    it mid-render. The previous session stays valid for comparison, which is
    what makes the locale-only and staleness judgements expressible at all.
    """

    projection: ModeloWorkspaceProjectionV1
    identity: ModeloWorkspaceSemanticIdentityV1

    @property
    def output_language(self) -> str:
        """Return the language this session's text was actually resolved in."""
        return self.projection.locale.resolved_language.value

    @property
    def baseline_token(self) -> str:
        """Return this session's baseline token, which is language-scoped."""
        return self.projection.baseline.token

    def cursor_for(self, facet: ModeloWorkspaceFacetName) -> ModeloWorkspaceCursorV1 | None:
        """Return the continuation this facet declared, or ``None`` when complete.

        Custody only. This controller does NOT turn the page: no public
        application entry point accepts a cursor today, and the one
        client-side shortcut -- re-resolving and taking a later page --
        would defeat the cursor's purpose, because a fresh resolve captures
        a new baseline and the held cursor is stale against it by
        construction. Returning the cursor honestly, and refusing to fake
        traversal, is the correct behaviour until that entry point exists.
        """
        facets = {
            ModeloWorkspaceFacetName.SCHEMA: self.projection.schema_facet,
            ModeloWorkspaceFacetName.MATERIALIZATION: self.projection.materialization_facet,
            ModeloWorkspaceFacetName.PROVENANCE: self.projection.provenance_facet,
        }
        bounded = facets.get(facet)
        return None if bounded is None else bounded.next_cursor

    def has_more(self, facet: ModeloWorkspaceFacetName) -> bool:
        """Report whether the producer bounded this facet short of the whole set."""
        return self.cursor_for(facet) is not None

    def page_completeness(self, facet: ModeloWorkspaceFacetName) -> ModeloWorkspacePageCompletenessV1:
        """Return whether this facet's page IS the whole set, as a closed two-arm answer.

        Boundedness disclosure is part of this session's contract, not a
        courtesy the destinations may each decide to offer. Until a
        page-turn entry point exists, an over-cap facet shows its first page
        and stops -- so a destination that renders a bounded page as though
        it were complete turns a truncation the producer declared into one
        the operator cannot see.

        Returned as the discriminated pair rather than a bool for the reason
        the pair exists: a caller must handle both arms, where a
        ``has_more`` flag can simply not be read. That matters most for
        provenance, where one source reference fans out to one row per
        casilla it names, so a page can overflow without the revision
        growing and row count tells an operator nothing about completeness.
        """
        facets = {
            ModeloWorkspaceFacetName.SCHEMA: self.projection.schema_facet,
            ModeloWorkspaceFacetName.MATERIALIZATION: self.projection.materialization_facet,
            ModeloWorkspaceFacetName.PROVENANCE: self.projection.provenance_facet,
        }
        bounded = facets.get(facet)
        if bounded is None or not bounded.has_more:
            return ModeloWorkspaceCompletePageV1()
        return ModeloWorkspaceBoundedPageV1(shown=len(bounded.records), page_size=bounded.page_size)

    def is_stale_against(self, projection: ModeloWorkspaceProjectionV1) -> bool:
        """Report whether a later read names a DIFFERENT workspace than this session.

        Whole-session, never per-facet: the semantic axes are shared by
        every facet in a projection, so if they moved, no facet of this
        session is still describing the same thing. Invalidating one facet
        and keeping the rest would leave a screen showing two workspaces at
        once.
        """
        return semantic_identity(projection) != self.identity

    def is_locale_only_refresh(self, projection: ModeloWorkspaceProjectionV1) -> bool:
        """Report whether a later read is the same workspace in another language.

        Both halves are required. The semantic axes must be IDENTICAL, and
        a locale axis must have MOVED. Asserting only the first half would
        hold just as well if the refresh had done nothing at all, so it
        would prove the axes separable without ever separating them.

        The moved axis is the locale SUMMARY, never
        ``baseline.locale_catalogue_digest``. That digest is not a reliable
        discriminator: when the requested language has no entry for the key,
        resolution falls back to Spanish and reports the SPANISH shard's
        digest, so a Spanish read and an English read that fell back carry
        the SAME digest while genuinely differing in requested language.
        The summary keeps ``requested_language`` distinct from
        ``resolved_language`` precisely so the fallback stays visible, which
        is what makes it the honest axis to compare.
        """
        if semantic_identity(projection) != self.identity:
            return False
        return projection.locale != self.projection.locale


def admit_workspace_session(
    result: ModeloWorkspaceResultV1,
) -> tuple[ModeloWorkspaceReadSession | None, ModeloWorkspaceRefusalViewV1 | None]:
    """Open a session from a result, or surface the refusal that prevented one.

    Returns exactly one populated half. A refusal is a first-class outcome
    here, not an exception: the projection's own contract makes every
    refusal typed and carrying its owner and reconsideration condition, and
    raising would discard facts a destination is required to display.
    """
    # Dispatch over a closed union rather than re-testing a type the first arm
    # already excluded. The catch-all is `assert_never`, not a runtime refusal:
    # the union is exhausted here, so a new member should break the BUILD rather
    # than reach an admission error nobody sees until production.
    match result:
        case ModeloWorkspaceRefusedResultV1():
            return None, refusal_view(result.refusal)
        case ModeloWorkspaceStaticInspectionResultV1() | ModeloWorkspaceGradedSnapshotResultV1():
            projection = result.projection
        case _:
            assert_never(result)
    if projection.contract_version != SUPPORTED_WORKSPACE_CONTRACT_VERSION:
        raise ModeloWorkspaceSessionAdmissionError(
            f"workspace projection declares contract version {projection.contract_version}, "
            f"which this read cohort does not read; it reads exactly "
            f"{SUPPORTED_WORKSPACE_CONTRACT_VERSION}"
        )
    return ModeloWorkspaceReadSession(projection=projection, identity=semantic_identity(projection)), None


__all__ = [
    "SUPPORTED_WORKSPACE_CONTRACT_VERSION",
    "ModeloWorkspaceReadSession",
    "ModeloWorkspaceSemanticIdentityV1",
    "ModeloWorkspaceSessionAdmissionError",
    "admit_workspace_session",
    "semantic_identity",
]
