"""Typed ``--json`` payload schemas for ``aeat app registry view-edition``.

``document`` is the complete edition rendered as TOML, the same text the text
format prints; ``rows`` and ``review_scope`` carry, as structured fields, the
provenance and review coverage that text marks in comments.

See Also:
    :class:`~application.registry.edition.RegistryEditionReport`
        Application report these payloads project.
    :mod:`~entrypoints.cli.registry`
        CLI command surface that emits these payload schemas.
"""

from __future__ import annotations

from ...application.registry.edition import EditionRowSource, ReviewCoverage
from ...core.json_contract import OutputSchema
from ...domain.calculations.registry.ids import RevisionId


class EditionCasillaRowPayload(OutputSchema):
    """One casilla row of the complete edition and the edition that states it."""

    casilla_id: str
    source: EditionRowSource
    inherited_from: RevisionId | None = None


class InheritedRowAttestationPayload(OutputSchema):
    """The edition whose own stamp attests a group of inherited rows."""

    revision_id: RevisionId
    row_count: int
    review_status: str


class EditionReviewScopePayload(OutputSchema):
    """How far the edition's own review stamp reaches over the complete edition."""

    declared_review_status: str
    coverage: ReviewCoverage
    reviewed_against: RevisionId | None = None
    rendered_review_status: str
    inherited_attestations: list[InheritedRowAttestationPayload] = []


class RegistryViewEditionResult(OutputSchema):
    """JSON envelope for ``aeat app registry view-edition``."""

    modelo: str
    revision_id: RevisionId
    inherits_from: RevisionId | None = None
    document: str
    rows: list[EditionCasillaRowPayload] = []
    review_scope: EditionReviewScopePayload


__all__ = [
    "EditionCasillaRowPayload",
    "EditionReviewScopePayload",
    "InheritedRowAttestationPayload",
    "RegistryViewEditionResult",
]
