"""Read one registry edition as the complete edition it stands for.

An edition that names a predecessor states only the casillas that are new or
that differ, so its files are a fragment of what the registry compiles. This
service resolves the edition through
:func:`~cadrumo.domain.calculations.registry.edition_materialisation.materialise_edition`
and reports, beside the complete raw table, where every casilla row comes from
and how far the edition's review stamp reaches.

A delta edition's stamp covers only the rows it states, judged against the
predecessor it names; each inherited row is attested by the stamp of the
edition that states it. The complete table therefore carries no review claim
of its own, and the report names the stamp it set aside and every edition
whose stamp the inherited rows rest on instead.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel

from ...core.models import STRICT_FROZEN_CONFIG
from ...core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from ...core.resources.bundled_data import bundled_path
from dev.registry.compiler.edition_materialisation import MaterialisedEdition, materialise_edition
from ...domain.calculations.registry.errors import RegistryLoadError
from ...domain.calculations.registry.ids import RevisionId
from ...domain.calculations.registry.loader_cache import ModeloSource, discover_modelo_sources
from .errors import RegistryPreconditionCondition, registry_terminal_refusal

__all__ = [
    "EditionCasillaRow",
    "EditionReviewScope",
    "EditionRowSource",
    "InheritedRowAttestation",
    "RegistryEditionReport",
    "ReviewCoverage",
    "read_registry_edition",
]

_CASILLAS = "casillas"
_REVIEW_STATUS = "review_status"
_PENDING_REVIEW = "pending_review"


class EditionRowSource(StrEnum):
    """Where one casilla row of a complete edition is stated."""

    STATED = "stated"
    INHERITED = "inherited"


class ReviewCoverage(StrEnum):
    """What the edition's own review stamp covers."""

    COMPLETE_EDITION = "complete_edition"
    STATED_ROWS = "stated_rows"


class EditionCasillaRow(BaseModel):
    """One casilla row of the complete edition, with the edition that states it."""

    model_config = STRICT_FROZEN_CONFIG

    casilla_id: str
    source: EditionRowSource
    inherited_from: RevisionId | None


class InheritedRowAttestation(BaseModel):
    """The edition whose own stamp attests a group of inherited rows."""

    model_config = STRICT_FROZEN_CONFIG

    revision_id: RevisionId
    row_count: int
    review_status: str


class EditionReviewScope(BaseModel):
    """How far the edition's review stamp reaches over the complete edition.

    ``declared_review_status`` is the status the edition's own files declare.
    ``rendered_review_status`` is the status the complete table carries: equal
    to the declared one when the edition states every row, and
    ``pending_review`` for a delta edition, whose stamp never covered the rows
    it inherits.
    """

    model_config = STRICT_FROZEN_CONFIG

    declared_review_status: str
    coverage: ReviewCoverage
    reviewed_against: RevisionId | None
    rendered_review_status: str
    inherited_attestations: tuple[InheritedRowAttestation, ...]


class RegistryEditionReport(BaseModel):
    """One edition of one modelo resolved into the complete edition it stands for.

    ``table`` is the raw ``[revisions."<id>"]`` table in the shape the source
    files declare, naming no predecessor. ``rows`` is aligned with its casilla
    rows.
    """

    model_config = STRICT_FROZEN_CONFIG

    modelo: str
    revision_id: RevisionId
    inherits_from: RevisionId | None
    table: dict[str, object]
    rows: tuple[EditionCasillaRow, ...]
    review_scope: EditionReviewScope


def read_registry_edition(
    modelo: str,
    revision_id: str,
    *,
    registry_root: Path | None = None,
) -> RegistryEditionReport:
    """Resolve one edition of one modelo into the complete edition a reader inspects.

    Raises:
        RegistryApplicationInputError: When the registry declares no such
            modelo, or the modelo declares no such edition.
        RegistryLoadError: When the modelo's editions cannot be resolved, for
            example because the predecessor graph is invalid.
    """
    source = _modelo_source(registry_root or bundled_path("registry", "aeat"), modelo)
    editions = sorted(str(revision.revision_id) for revision in source.revision_sources)
    if revision_id not in editions:
        raise registry_terminal_refusal(
            condition=RegistryPreconditionCondition.EDITION_REVISION_DECLARED,
            translated_message="application.registry.errors.edition_revision_undeclared",
            context={"modelo": source.modelo_id, "revision": revision_id, "available_revisions": ", ".join(editions)},
            facts={
                "modelo": source.modelo_id,
                "revision_id": revision_id,
                "revision_declared": False,
                "candidate_revision_count": len(editions),
            },
            provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
            outcome=NoRecoveryOutcome.OPERATOR_DECISION,
        )
    edition = materialise_edition(source.path, revision_id)
    rows = _casilla_rows(edition)
    return RegistryEditionReport(
        modelo=edition.modelo_id,
        revision_id=edition.revision_id,
        inherits_from=edition.inherits_from,
        table=dict(edition.table),
        rows=rows,
        review_scope=_review_scope(source.path, edition, rows),
    )


def _modelo_source(registry_root: Path, modelo: str) -> ModeloSource:
    sources = discover_modelo_sources(registry_root / "modelos")
    by_id = {source.modelo_id: source for source in sources}
    source = by_id.get(modelo)
    if source is None:
        raise registry_terminal_refusal(
            condition=RegistryPreconditionCondition.EDITION_MODELO_DECLARED,
            translated_message="application.registry.errors.edition_modelo_undeclared",
            context={"modelo": modelo, "available_modelos": ", ".join(sorted(by_id))},
            facts={"modelo": modelo, "modelo_declared": False, "candidate_modelo_count": len(by_id)},
            provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
            outcome=NoRecoveryOutcome.OPERATOR_DECISION,
        )
    return source


def _casilla_rows(edition: MaterialisedEdition) -> tuple[EditionCasillaRow, ...]:
    raw_rows = edition.table.get(_CASILLAS, ())
    if not isinstance(raw_rows, list | tuple):
        raise RegistryLoadError(
            f"modelo {edition.modelo_id!r} edition {edition.revision_id!r}: casillas must be an array"
        )
    origins = edition.label_origins or (None,) * len(raw_rows)
    if len(origins) != len(raw_rows):
        raise RegistryLoadError(
            f"modelo {edition.modelo_id!r} edition {edition.revision_id!r}: {len(origins)} row origins "
            f"for {len(raw_rows)} casilla rows",
        )
    return tuple(
        EditionCasillaRow(
            casilla_id=_row_id(edition, row),
            source=EditionRowSource.STATED if origin is None else EditionRowSource.INHERITED,
            inherited_from=origin,
        )
        for row, origin in zip(raw_rows, origins, strict=True)
    )


def _row_id(edition: MaterialisedEdition, row: object) -> str:
    row_id = row.get("id") if isinstance(row, Mapping) else None
    if not isinstance(row_id, str):
        raise RegistryLoadError(
            f"modelo {edition.modelo_id!r} edition {edition.revision_id!r}: every casilla row must declare a string id",
        )
    return row_id


def _review_scope(
    modelo_directory: Path,
    edition: MaterialisedEdition,
    rows: tuple[EditionCasillaRow, ...],
) -> EditionReviewScope:
    rendered = _declared_status(edition.table)
    if edition.inherits_from is None:
        return EditionReviewScope(
            declared_review_status=rendered,
            coverage=ReviewCoverage.COMPLETE_EDITION,
            reviewed_against=None,
            rendered_review_status=rendered,
            inherited_attestations=(),
        )
    declared = edition.withdrawn_review_status or rendered
    # The schema requires a delta edition's review claim to name the
    # predecessor it was judged against, and to equal the declared one.
    reviewed_against = None if declared == _PENDING_REVIEW else edition.inherits_from
    counts = Counter(row.inherited_from for row in rows if row.inherited_from is not None)
    return EditionReviewScope(
        declared_review_status=declared,
        coverage=ReviewCoverage.STATED_ROWS,
        reviewed_against=reviewed_against,
        rendered_review_status=rendered,
        inherited_attestations=tuple(
            InheritedRowAttestation(
                revision_id=origin,
                row_count=count,
                review_status=_edition_review_status(modelo_directory, origin),
            )
            for origin, count in sorted(counts.items())
        ),
    )


def _edition_review_status(modelo_directory: Path, revision_id: str) -> str:
    """Return the review status an edition's own files declare."""
    edition = materialise_edition(modelo_directory, revision_id)
    return edition.withdrawn_review_status or _declared_status(edition.table)


def _declared_status(table: Mapping[str, object]) -> str:
    status = table.get(_REVIEW_STATUS, _PENDING_REVIEW)
    return status if isinstance(status, str) else str(status)
