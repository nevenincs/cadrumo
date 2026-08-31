"""Per-revision schema-family dispositions, projected from the revision alone.

This is the build-time half of coverage. It projects one
:class:`ModeloRevision` into one row per enrolled schema family and reads
nothing else: no snapshot is built, no review state is consulted, and no
representative filing year is chosen. That independence is why it reports on
every revision in the corpus rather than on the review-eligible subset, and it
is also what lets registry-build validation consume it.

It is deliberately separate from the cross-revision coverage AUDIT, which sits
above validation because it constructs validated snapshots. Housing both in one
module put a build-time projection behind a post-validation consumer, so
validation could not reach the projection without importing its own consumer.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, NonNegativeInt, TypeAdapter, computed_field, model_validator

from ....core.models import STRICT_FROZEN_CONFIG
from ....core.schema_family_disposition import (
    UNRESOLVED_SCHEMA_FAMILY_DISPOSITIONS,
    RegistrySchemaFamilyDisposition,
)
from .errors import RegistryValidationError
from .ids import LegalRefId, SourceRefId
from .schema import REVISION_SCHEMA_FAMILY_FIELDS, ModeloRevision


class CoverageModel(BaseModel):
    """Strict frozen base for coverage reports."""

    model_config = STRICT_FROZEN_CONFIG


class SchemaFamilyCoverageRow(CoverageModel):
    """One family's content disposition on one revision.

    Carries the populated count alongside the disposition so a reader can tell a
    family holding one row from one holding four hundred without re-deriving it,
    and so the disposition can be checked against the count rather than trusted.
    """

    family: str = Field(min_length=1)
    disposition: RegistrySchemaFamilyDisposition
    populated_count: NonNegativeInt
    reason: str | None = None
    legal_refs: tuple[LegalRefId, ...] = ()
    source_refs: tuple[SourceRefId, ...] = ()

    @model_validator(mode="after")
    def _validate_disposition_matches_content(self) -> SchemaFamilyCoverageRow:
        """Refuse a row whose disposition disagrees with what it reports.

        Every branch here is a way the projection could lie while still
        type-checking, and the row is the last place to catch it: a
        ``populated`` row with a zero count, or a ``blocked_pending_evidence``
        row quietly carrying the references that would have resolved it.
        """
        has_refs = bool(self.legal_refs or self.source_refs)
        if self.disposition is RegistrySchemaFamilyDisposition.POPULATED:
            if self.populated_count == 0:
                raise RegistryValidationError(f"family {self.family!r} is populated but reports no members")
            if self.reason is not None or has_refs:
                raise RegistryValidationError(
                    f"family {self.family!r} is populated and needs no inapplicability reason or refs",
                )
            return self
        if self.populated_count != 0:
            raise RegistryValidationError(
                f"family {self.family!r} reports {self.populated_count} members but is not populated",
            )
        if self.disposition is RegistrySchemaFamilyDisposition.NOT_APPLICABLE:
            if self.reason is None or not self.legal_refs or not self.source_refs:
                raise RegistryValidationError(
                    f"family {self.family!r} is declared not applicable, which requires a reason, "
                    f"legal refs and source refs",
                )
            return self
        if self.reason is not None or has_refs:
            raise RegistryValidationError(
                f"family {self.family!r} is blocked pending evidence and cannot carry a reason or refs; "
                f"declare it not applicable instead",
            )
        return self


class RevisionCoverageManifest(CoverageModel):
    """Every schema family of one revision, with its content disposition.

    Exhaustive by construction: one row per enrolled family, always. A family
    nobody has built appears as a ``blocked_pending_evidence`` row rather than
    as an absence, because an absence is what the reader has to notice and a row
    is what the reader can count.
    """

    modelo: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    rows: tuple[SchemaFamilyCoverageRow, ...]

    @model_validator(mode="after")
    def _rows_cover_every_enrolled_family_once(self) -> RevisionCoverageManifest:
        """Refuse a manifest that skips an enrolled family or reports one twice.

        Without this the manifest's exhaustiveness would be a property of the
        builder rather than of the type, and a family dropped on the way out
        would read as a revision with one fewer thing to answer for.
        """
        reported = [row.family for row in self.rows]
        if len(reported) != len(set(reported)):
            raise RegistryValidationError(
                f"revision {self.revision!r} coverage manifest reports a family more than once",
            )
        missing = REVISION_SCHEMA_FAMILY_FIELDS - set(reported)
        unknown = set(reported) - REVISION_SCHEMA_FAMILY_FIELDS
        if missing or unknown:
            raise RegistryValidationError(
                f"revision {self.revision!r} coverage manifest does not cover every enrolled "
                f"schema family exactly once (missing {sorted(missing)!r}, unknown {sorted(unknown)!r})",
            )
        return self

    @computed_field
    @property
    def unresolved(self) -> tuple[SchemaFamilyCoverageRow, ...]:
        """Return the rows whose disposition resolves nothing.

        Membership in the shared unresolved set, never equality against one
        member, so a disposition added later enrols itself into every consumer
        instead of needing each call site found and widened.
        """
        return tuple(row for row in self.rows if row.disposition in UNRESOLVED_SCHEMA_FAMILY_DISPOSITIONS)

    @computed_field
    @property
    def fully_resolved(self) -> bool:
        """Return whether every enrolled family is populated or reasoned inapplicable."""
        return not self.unresolved


def build_revision_coverage_manifest(*, modelo: str, revision: ModeloRevision) -> RevisionCoverageManifest:
    """Project one revision's schema families into their content dispositions.

    Reads the revision and nothing else. No snapshot is built, no review state
    is consulted and no representative filing year is chosen, so this reports on
    every revision in the corpus rather than on the review-eligible subset.

    Args:
        modelo: Identifier of the owning modelo, carried onto the manifest.
        revision: The revision to project.

    Returns:
        A manifest carrying exactly one row per enrolled schema family.
    """
    return RevisionCoverageManifest(
        modelo=modelo,
        revision=revision.id,
        rows=tuple(_schema_family_row(family, revision) for family in sorted(REVISION_SCHEMA_FAMILY_FIELDS)),
    )


_SCHEMA_FAMILY_MEMBERS_ADAPTER: TypeAdapter[tuple[object, ...]] = TypeAdapter(tuple[object, ...])


def _schema_family_row(family: str, revision: ModeloRevision) -> SchemaFamilyCoverageRow:
    """Return one family's row, defaulting an unexplained empty family to blocked."""
    members = _SCHEMA_FAMILY_MEMBERS_ADAPTER.validate_python(getattr(revision, family))
    if members:
        return SchemaFamilyCoverageRow(
            family=family,
            disposition=RegistrySchemaFamilyDisposition.POPULATED,
            populated_count=len(members),
        )
    declaration = revision.family_dispositions.get(family)
    if declaration is None:
        return SchemaFamilyCoverageRow(
            family=family,
            disposition=RegistrySchemaFamilyDisposition.BLOCKED_PENDING_EVIDENCE,
            populated_count=0,
        )
    return SchemaFamilyCoverageRow(
        family=family,
        disposition=RegistrySchemaFamilyDisposition.NOT_APPLICABLE,
        populated_count=0,
        reason=declaration.reason,
        legal_refs=declaration.legal_refs,
        source_refs=declaration.source_refs,
    )
