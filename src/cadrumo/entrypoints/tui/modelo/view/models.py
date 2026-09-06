"""Frozen, callback-free view models for the Modelo workspace read destinations.

Every model here is a PRESENTATION NARROWING over a public Workspace V1
projection. Nothing in this module computes, derives, classifies or
re-verifies a tax value, a readiness verdict, a capability disposition or a
causal edge: each of those is a producer's answer, copied through and keyed
by the semantic identity the producer already assigned. A renderer consumes
these models alone, so a truth the projection declared cannot be
reclassified downstream of it.

Two shapes, following the tree's existing convention rather than a new one:
row structs are frozen slotted dataclasses (as
:class:`~cadrumo.entrypoints.tui.profile.sync_review.CensalFieldReviewRowV1`
and the ``status_projection`` rows are), and projection narrowings are
pydantic models on the canonical :data:`STRICT_FROZEN_CONFIG`.

Every model that narrows a producer record retains that record, so a
renderer can always reach the canonical truth rather than only this
module's reading of it. The pydantic narrowings additionally re-check their
derived fields against the retained source in a validator that deliberately
does NOT call the builder's helpers -- sharing them would make the check
agree with the builder by construction, so a defect inside a helper would
pass unseen. The remaining structs (section, constraint, action) carry no
retained record because they narrow a FIELD of a record rather than a
record, and there is nothing further to reach through to.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Final, Literal

from pydantic import BaseModel, model_validator

from .....application.modelo.workspace_models import (
    ModeloWorkspaceCapabilityDisposition,
    ModeloWorkspaceCapabilityName,
    ModeloWorkspaceCapabilityV1,
    ModeloWorkspaceConstraintReferenceV1,
    ModeloWorkspaceLocalizedTextV1,
    ModeloWorkspaceRecordLabelV1,
    ModeloWorkspaceRefusalV1,
    ModeloWorkspaceScalarMaterializationV1,
    ModeloWorkspaceVersionRefusalV1,
)
from .....core.models import STRICT_FROZEN_CONFIG

type ModeloWorkspaceDestinationIdV1 = Literal[
    "modelo.workspace.overview",
    "modelo.workspace.inputs",
    "modelo.workspace.results",
    "modelo.workspace.provenance",
    "modelo.workspace.verification",
    "modelo.workspace.filing",
]
"""The closed set of C2 read destinations, spelled as their route identities.

Declared here rather than beside the route registration so the destination
axis has exactly one definition: the route factory consumes this alias, and
a destination cannot be registered that no view model can address.
"""

type ModeloWorkspaceDispositionGlyphV1 = Literal["✓", "—", "✖", "?"]
"""A disposition's distinguishing mark, never its colour.

Follows the shared ``RequirementBadge`` discipline -- two operators
comparing a greyscale screenshot and a colour one must reach the same
conclusion -- but over this cohort's own enum. ``RequirementStatus`` is
deliberately NOT reused: it has no ``refused`` and no ``unmeasured`` member,
so mapping onto it would render a producer's active refusal, or an
unmeasured axis nobody read, as whichever requirement state looked closest.
That is an under-declaration performed by the presentation layer, on
exactly the axis where the filing destination has nothing else to say.
"""

_DISPOSITION_GLYPH: Final[dict[ModeloWorkspaceCapabilityDisposition, ModeloWorkspaceDispositionGlyphV1]] = {
    ModeloWorkspaceCapabilityDisposition.AVAILABLE: "✓",
    ModeloWorkspaceCapabilityDisposition.NOT_APPLICABLE: "—",
    ModeloWorkspaceCapabilityDisposition.REFUSED: "✖",
    ModeloWorkspaceCapabilityDisposition.UNMEASURED: "?",
}


def _require_total_glyph_table() -> None:
    """Refuse a glyph table that does not cover every disposition exactly once."""
    if set(_DISPOSITION_GLYPH) != set(ModeloWorkspaceCapabilityDisposition):
        raise ValueError("workspace disposition glyph table must cover each disposition exactly once")
    if len(set(_DISPOSITION_GLYPH.values())) != len(_DISPOSITION_GLYPH):
        raise ValueError("workspace disposition glyphs must be distinguishable from one another")


_require_total_glyph_table()


def disposition_glyph(disposition: ModeloWorkspaceCapabilityDisposition) -> ModeloWorkspaceDispositionGlyphV1:
    """Return the distinguishing mark this disposition is rendered by.

    Public because the mark is part of what this module promises: a caller
    proving that two dispositions stay distinguishable, or a destination
    rendering one outside a capability row, needs the mapping without
    reaching for a private table.
    """
    return _DISPOSITION_GLYPH[disposition]


class _ViewModel(BaseModel):
    """The common strict, frozen, default-validating posture for C2 view models."""

    model_config = STRICT_FROZEN_CONFIG


@dataclass(frozen=True, slots=True)
class ModeloWorkspaceDisplayTextV1:
    """One display string that says honestly whether a translation happened.

    ``translated`` is read from the label's own discriminator, never guessed
    from whether the text looks like prose: a registry identifier shown as
    itself is not a translation that happened, and
    :class:`ModeloWorkspaceTechnicalLabelV1` exists to say so.
    """

    text: str
    translated: bool


def display_text(label: ModeloWorkspaceRecordLabelV1) -> ModeloWorkspaceDisplayTextV1:
    """Narrow a canonical record label to its display string and honesty flag."""
    if isinstance(label, ModeloWorkspaceLocalizedTextV1):
        return ModeloWorkspaceDisplayTextV1(text=label.value, translated=True)
    return ModeloWorkspaceDisplayTextV1(text=label.identifier, translated=False)


@dataclass(frozen=True, slots=True)
class ModeloWorkspaceScalarRowV1:
    """One materialized casilla value, keyed by its canonical casilla identity.

    ``value`` stays the canonical typed scalar rather than a formatted
    string: how a figure is rendered belongs to the widget and its locale,
    and baking a format here would fix one presentation of a filing-grade
    number inside a model several destinations share.

    The producer's record is retained whole rather than reduced to a
    provenance COUNT. A count would be actively misleading here: one source
    reference fans out to one provenance record per casilla it names, so the
    number says nothing an operator can reason about, while dropping the
    records themselves would put the provenance destination in the position
    of re-deriving what it was already handed.
    """

    casilla_id: str
    value: Decimal | str | bool | None
    source: ModeloWorkspaceScalarMaterializationV1


@dataclass(frozen=True, slots=True)
class ModeloWorkspaceSectionV1:
    """One schema record-family label, presented as a grouping key.

    The path is the projection's own ``record_family``; this model groups by
    it and never synthesises a grouping a revision did not declare.
    """

    path: tuple[str, ...]


class ModeloWorkspaceCompletePageV1(_ViewModel):
    """A page that is the whole set: nothing was left unrendered."""

    kind: Literal["complete"] = "complete"


class ModeloWorkspaceBoundedPageV1(_ViewModel):
    """A page the producer bounded: more rows exist beyond what is shown.

    Carried as its own arm rather than a nullable "next" field so a renderer
    cannot show a bounded page as though it were the complete set. That
    distinction is load-bearing for provenance in particular, where one
    source reference fans out to one row per casilla it names -- so a page
    can overflow without the revision growing at all, and record count tells
    an operator nothing about completeness.
    """

    kind: Literal["bounded"] = "bounded"
    shown: int
    page_size: int

    @model_validator(mode="after")
    def _require_a_real_bound(self) -> ModeloWorkspaceBoundedPageV1:
        if self.shown > self.page_size:
            raise ValueError("a bounded workspace page cannot show more rows than its page size")
        return self


type ModeloWorkspacePageCompletenessV1 = ModeloWorkspaceCompletePageV1 | ModeloWorkspaceBoundedPageV1


class ModeloWorkspaceCapabilityRowV1(_ViewModel):
    """One capability answer, keyed by capability, with its distinguishing glyph.

    Copies the producer's disposition; never infers one. ``glyph`` is the
    only derived field and is re-checked below against the disposition read
    straight off the retained source.
    """

    capability: ModeloWorkspaceCapabilityName
    disposition: ModeloWorkspaceCapabilityDisposition
    glyph: ModeloWorkspaceDispositionGlyphV1
    producer_owner: str
    producer: str
    source: ModeloWorkspaceCapabilityV1

    @model_validator(mode="after")
    def _mirror_the_source_capability(self) -> ModeloWorkspaceCapabilityRowV1:
        # Read every mirrored field off the retained source directly rather
        # than through the builder's helper. Sharing that helper would make
        # this check agree with the builder by construction, so a defect in
        # the helper itself would pass unseen.
        if self.capability is not self.source.capability:
            raise ValueError("capability row must mirror the producer's capability")
        if self.disposition is not self.source.disposition:
            raise ValueError("capability row must mirror the producer's disposition")
        if self.producer_owner != self.source.producer_owner or self.producer != self.source.producer:
            raise ValueError("capability row must mirror the producer's attribution")
        if self.glyph != _DISPOSITION_GLYPH[self.source.disposition]:
            raise ValueError("capability row glyph must be the one this disposition declares")
        return self


def capability_row(capability: ModeloWorkspaceCapabilityV1) -> ModeloWorkspaceCapabilityRowV1:
    """Narrow one canonical capability answer to its presentation row."""
    return ModeloWorkspaceCapabilityRowV1(
        capability=capability.capability,
        disposition=capability.disposition,
        glyph=_DISPOSITION_GLYPH[capability.disposition],
        producer_owner=capability.producer_owner,
        producer=capability.producer,
        source=capability,
    )


type ModeloWorkspaceRefusalKindV1 = Literal["unsupported_version", "revision_assertion_mismatch", "domain"]


class ModeloWorkspaceRefusalViewV1(_ViewModel):
    """One refusal presented with the facts it already carries, and no more.

    ``responsible_owner`` and ``reconsideration_condition`` are ``None`` only
    for the pre-parse version refusal, which structurally has neither -- it
    is produced before a target is parsed. They are never defaulted to a
    placeholder: a refusal that cannot name an owner must not appear to.
    """

    kind: ModeloWorkspaceRefusalKindV1
    responsible_owner: str | None
    reconsideration_condition: str | None
    source: ModeloWorkspaceRefusalV1

    @model_validator(mode="after")
    def _mirror_the_source_refusal(self) -> ModeloWorkspaceRefusalViewV1:
        source = self.source
        if self.kind != source.kind:
            raise ValueError("refusal view must mirror the refusal's own discriminator")
        if isinstance(source, ModeloWorkspaceVersionRefusalV1):
            if self.responsible_owner is not None or self.reconsideration_condition is not None:
                raise ValueError("a pre-parse version refusal carries no owner or reconsideration condition")
            return self
        if self.responsible_owner != source.responsible_owner:
            raise ValueError("refusal view must mirror the refusal's responsible owner")
        if self.reconsideration_condition != source.reconsideration_condition:
            raise ValueError("refusal view must mirror the refusal's reconsideration condition")
        return self


def refusal_view(refusal: ModeloWorkspaceRefusalV1) -> ModeloWorkspaceRefusalViewV1:
    """Narrow any refusal arm to the presentation facts it actually carries."""
    if isinstance(refusal, ModeloWorkspaceVersionRefusalV1):
        return ModeloWorkspaceRefusalViewV1(
            kind=refusal.kind,
            responsible_owner=None,
            reconsideration_condition=None,
            source=refusal,
        )
    return ModeloWorkspaceRefusalViewV1(
        kind=refusal.kind,
        responsible_owner=refusal.responsible_owner,
        reconsideration_condition=refusal.reconsideration_condition,
        source=refusal,
    )


type ModeloWorkspaceConstraintDisclosureV1 = Literal["unmeasured", "none_declared", "declared"]
"""Three states, because the producer distinguishes three and a bool cannot.

``ModeloWorkspaceSchemaRecordV1.constraints`` is ``None`` when this
admission's producer never carries constraint declarations for this
reference kind, and an empty tuple when it does and none are declared. The
schema record's own docstring defends that distinction: a static inspection
has no ``CasillaDefinition`` to check, so it cannot honestly claim "no
constraints declared" the way an empty tuple would. Collapsing the two into
one Boolean would make an unmeasured axis read as a satisfied one -- the
same under-declaration-by-presentation the glyph table refuses.
"""


def constraint_disclosure(
    constraints: tuple[ModeloWorkspaceConstraintReferenceV1, ...] | None,
) -> ModeloWorkspaceConstraintDisclosureV1:
    """Narrow the producer's three-state constraint field without flattening it."""
    if constraints is None:
        return "unmeasured"
    return "declared" if constraints else "none_declared"


class ModeloWorkspaceChromeV1(_ViewModel):
    """The frame around one destination: which it is, and what it is showing.

    Address disclosure is carried as the resolved coordinates the projection
    already settled -- never re-resolved here, and never a revision
    chronology, which Workspace V1 does not expose.
    """

    destination: ModeloWorkspaceDestinationIdV1
    modelo: str
    filing_year: int
    period_token: str
    law_selected_revision_id: str
    work_unit_id: str | None = None

    @model_validator(mode="after")
    def _require_honest_address(self) -> ModeloWorkspaceChromeV1:
        if not self.law_selected_revision_id:
            raise ValueError("workspace chrome must disclose the law-selected revision it is showing")
        return self


__all__ = [
    "ModeloWorkspaceBoundedPageV1",
    "ModeloWorkspaceCapabilityRowV1",
    "ModeloWorkspaceChromeV1",
    "ModeloWorkspaceCompletePageV1",
    "ModeloWorkspaceConstraintDisclosureV1",
    "ModeloWorkspaceDestinationIdV1",
    "ModeloWorkspaceDisplayTextV1",
    "ModeloWorkspaceDispositionGlyphV1",
    "ModeloWorkspacePageCompletenessV1",
    "ModeloWorkspaceRefusalKindV1",
    "ModeloWorkspaceRefusalViewV1",
    "ModeloWorkspaceScalarRowV1",
    "ModeloWorkspaceSectionV1",
    "capability_row",
    "constraint_disclosure",
    "display_text",
    "disposition_glyph",
    "refusal_view",
]
