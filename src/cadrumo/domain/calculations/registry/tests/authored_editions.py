"""Exercise coordinates read off the published authority instead of being spelled out.

A test about "the newest edition the registry authors", "the revision a source
grounds" or "the exercise a provision governs" asks this module for the year, so
it follows the registry when an edition is authored, retired or re-scoped rather
than silently pointing at whatever a hand-written year happens to name.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from functools import cache

from .....core.corpus_text import normalise_corpus_text
from .....core.resources.bundled_data import bundled_path
from ..authority import bundled_indexed_authority
from ..schema import ModeloRevision
from ..schema_references import SourceReference
from ..temporal import RevisionSelectionMetadata


def authored_revisions(modelo_id: str) -> tuple[RevisionSelectionMetadata, ...]:
    """Return every authored revision of one modelo, oldest first."""
    with bundled_indexed_authority().operation() as operation:
        return tuple(sorted(operation.modelo_directory(modelo_id).revisions, key=lambda revision: revision.valid_from))


def newest_authored_editions(modelo_id: str, count: int) -> tuple[int, ...]:
    """Return the first exercises of the ``count`` newest authored revisions, oldest first."""
    revisions = authored_revisions(modelo_id)
    if len(revisions) < count:
        raise LookupError(f"modelo {modelo_id}: {len(revisions)} authored revisions, {count} requested")
    return tuple(revision.valid_from.year for revision in revisions[-count:])


def newest_authored_edition(modelo_id: str) -> int:
    """Return the first exercise of the newest authored revision of one modelo."""
    return newest_authored_editions(modelo_id, 1)[0]


def single_exercise_editions(modelo_id: str) -> tuple[int, ...]:
    """Return the exercises of the revisions authored for exactly one calendar year."""
    return tuple(
        revision.valid_from.year
        for revision in authored_revisions(modelo_id)
        if revision.valid_to is not None and revision.valid_to.year == revision.valid_from.year
    )


def revision_first_exercise(modelo_id: str, revision_id: str) -> int:
    """Return the first exercise one authored revision governs."""
    return next(
        revision.valid_from.year for revision in authored_revisions(modelo_id) if str(revision.id) == revision_id
    )


def revision_last_exercise(modelo_id: str, revision_id: str) -> int:
    """Return the last exercise one closed authored revision governs."""
    revision = next(revision for revision in authored_revisions(modelo_id) if str(revision.id) == revision_id)
    if revision.valid_to is None:
        raise LookupError(f"modelo {modelo_id} revision {revision_id} is open-ended")
    return revision.valid_to.year


def authored_revisions_where(
    modelo_id: str,
    predicate: Callable[[ModeloRevision], bool],
) -> tuple[ModeloRevision, ...]:
    """Return the hydrated authored revisions of one modelo that satisfy ``predicate``, oldest first."""
    with bundled_indexed_authority().operation() as operation:
        return tuple(
            revision
            for metadata in sorted(operation.modelo_directory(modelo_id).revisions, key=lambda item: item.valid_from)
            if predicate(revision := operation.revision(modelo_id, str(metadata.id)))
        )


def source_exercise(source: SourceReference) -> int:
    """Return the one exercise a single-year source's applicability window covers."""
    if source.applies_from is None or source.applies_to is None:
        raise LookupError(f"source {source.id} declares no closed applicability window")
    if source.applies_from.year != source.applies_to.year:
        raise LookupError(f"source {source.id} applies across more than one exercise")
    return source.applies_from.year


@cache
def manual_editions_printing(manual_id: str, *phrases: str) -> tuple[int, ...]:
    """Return the exercises of the bundled AEAT manual editions whose text prints every phrase.

    Each edition directory carries a manifest naming the exercise it covers, and the
    committed corpus-text sidecar holds the edition's normalised text.
    """
    wanted = tuple(normalise_corpus_text(phrase) for phrase in phrases)
    corpus_root = bundled_path("corpus", "manuals", manual_id)
    text_root = bundled_path("manual_corpus_text", "manuals", manual_id)
    editions: set[int] = set()
    for manifest_path in sorted(corpus_root.glob("**/manifest.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        edition_dir = manifest_path.parent.relative_to(corpus_root)
        sidecar = text_root / edition_dir / f"{manifest['relative_pdf_path']}.corpus_text.json"
        if not sidecar.is_file():
            continue
        text = json.loads(sidecar.read_text(encoding="utf-8"))["normalised_text"]
        if all(phrase in text for phrase in wanted):
            editions.add(int(manifest["year"]))
    return tuple(sorted(editions))
