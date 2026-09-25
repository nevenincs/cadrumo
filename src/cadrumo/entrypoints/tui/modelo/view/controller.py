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
from typing import Final

from .....application.modelo.workspace_models import (
    ModeloWorkspaceCursorV1,
    ModeloWorkspaceDomainRefusalV1,
    ModeloWorkspaceFacetName,
    ModeloWorkspaceGradedSnapshotResultV1,
    ModeloWorkspaceLifecycleProjectionV1,
    ModeloWorkspaceProjectionV1,
    ModeloWorkspaceRefusedResultV1,
    ModeloWorkspaceResultV1,
    ModeloWorkspaceStaticInspectionResultV1,
)
from .....core.errors.hierarchy import CadrumoError
from .models import (
    ModeloWorkspaceBoundedPageV1,
    ModeloWorkspaceCompletePageV1,
    ModeloWorkspacePageCompletenessV1,
)

SUPPORTED_WORKSPACE_CONTRACT_VERSION: Final[int] = 1
"""The one contract version this cohort reads.

Exact, never a floor: a future version may move a field this controller
narrows, so admitting ``>= 1`` would let a shape this code cannot read reach
a renderer. Refusing an unequal version is the forward-compatibility
posture, not a legacy one -- there is no older version to tolerate.
"""


class ModeloWorkspaceSessionAdmissionError(CadrumoError):
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
    lifecycle: ModeloWorkspaceLifecycleProjectionV1 | None = None
    lifecycle_actions: object | None = None
    graded_refusal: ModeloWorkspaceDomainRefusalV1 | None = None
    """The GRADED_SNAPSHOT refusal ``projection`` fell back from, when it did.

    ``None`` means ``projection`` IS the requested admission -- graded when a
    graded read was requested and static when only a static one was. A
    non-``None`` value means ``projection`` is a STATIC_INSPECTION admission
    standing in for a GRADED_SNAPSHOT that this refusal explains: the code,
    the resolved target where one exists, the safe facts and evidence behind
    it, and the catalogued action that advances it, exactly as the producer
    measured them. Never inferred here; always copied from the read that
    opened this session.
    """

    @property
    def output_language(self) -> str:
        """Return the language this session's text was actually resolved in."""
        return self.projection.locale.resolved_language.value

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


@dataclass(frozen=True, slots=True)
class ModeloWorkspaceRefusedReadV1:
    """The typed refusal a result carried instead of an admitted projection.

    A refusal is an ANSWER, not a failure: the producer measured the target and
    reported that a graded read of it is not possible yet, together with the
    condition that would change that and the catalogued step that reaches it.
    Represented as its own arm rather than as ``None`` or an exception so a
    caller has to decide what to do with it, and so the reason survives to
    whatever renders it.
    """

    refusal: ModeloWorkspaceDomainRefusalV1


type ModeloWorkspaceAdmissionV1 = ModeloWorkspaceReadSession | ModeloWorkspaceRefusedReadV1
"""The two outcomes admitting one workspace result can have."""


def admit_modelo_workspace_result(
    result: ModeloWorkspaceResultV1,
    *,
    lifecycle: ModeloWorkspaceLifecycleProjectionV1 | None = None,
    lifecycle_actions: object | None = None,
) -> ModeloWorkspaceAdmissionV1:
    """Match a producer result on its own outcome arm and admit or refuse accordingly.

    The one place this cohort turns a three-arm
    :data:`ModeloWorkspaceResultV1` into something a renderer can hold. Both
    successful arms open the identical session -- a static inspection and a
    graded snapshot differ in what the projection CARRIES, never in how a
    session is opened over it -- and the refused arm is returned as itself
    rather than flattened into ``None``, which would lose the code, the
    condition and the remedy the producer attached.
    """
    match result:
        case ModeloWorkspaceRefusedResultV1():
            return ModeloWorkspaceRefusedReadV1(refusal=result.refusal)
        case ModeloWorkspaceStaticInspectionResultV1() | ModeloWorkspaceGradedSnapshotResultV1():
            return open_workspace_read_session(
                result.projection,
                lifecycle=lifecycle,
                lifecycle_actions=lifecycle_actions,
            )


def open_workspace_read_session(
    projection: ModeloWorkspaceProjectionV1,
    *,
    lifecycle: ModeloWorkspaceLifecycleProjectionV1 | None = None,
    lifecycle_actions: object | None = None,
    graded_refusal: ModeloWorkspaceDomainRefusalV1 | None = None,
) -> ModeloWorkspaceReadSession:
    """Open the canonical immutable session from an already-admitted projection.

    Installed composition receives projections from its one captured generation,
    rather than re-wrapping them as synthetic application outcomes.  Both
    admission paths therefore share the exact version and semantic-identity
    checks before a renderer can receive the session.

    ``graded_refusal`` is the composing caller's own fact, not something this
    function infers from ``projection``: a STATIC_INSPECTION projection reads
    identically whether it was the only admission ever requested or a
    fallback from a refused GRADED_SNAPSHOT, so only whoever tried the graded
    read first -- and holds the refusal it got back -- can honestly pass one.
    """
    if projection.contract_version != SUPPORTED_WORKSPACE_CONTRACT_VERSION:
        raise ModeloWorkspaceSessionAdmissionError(
            f"workspace projection declares contract version {projection.contract_version}, "
            f"which this read cohort does not read; it reads exactly "
            f"{SUPPORTED_WORKSPACE_CONTRACT_VERSION}"
        )
    if lifecycle is not None and lifecycle.target != projection.target:
        raise ModeloWorkspaceSessionAdmissionError("lifecycle projection does not name this workspace target")
    if lifecycle_actions is not None and lifecycle is None:
        raise ModeloWorkspaceSessionAdmissionError("workspace lifecycle actions require a lifecycle projection")
    return ModeloWorkspaceReadSession(
        projection=projection,
        identity=semantic_identity(projection),
        lifecycle=lifecycle,
        lifecycle_actions=lifecycle_actions,
        graded_refusal=graded_refusal,
    )


__all__ = [
    "SUPPORTED_WORKSPACE_CONTRACT_VERSION",
    "ModeloWorkspaceAdmissionV1",
    "ModeloWorkspaceReadSession",
    "ModeloWorkspaceRefusedReadV1",
    "ModeloWorkspaceSemanticIdentityV1",
    "ModeloWorkspaceSessionAdmissionError",
    "admit_modelo_workspace_result",
    "open_workspace_read_session",
    "semantic_identity",
]
