"""Exercise coordinates read off the published authority instead of being spelled out.

A test about "the newest edition the registry authors", "the revision a source
grounds" or "the exercise a provision governs" asks this module for the year, so
it follows the registry when an edition is authored, retired or re-scoped rather
than silently pointing at whatever a hand-written year happens to name.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from functools import cache
from itertools import pairwise
from pathlib import PurePosixPath

from .....core.corpus_text import normalise_corpus_text
from .....core.resources.bundled_data import bundled_path
from ..authority import bundled_authority_descriptor_path, bundled_indexed_authority
from ..authority_artifact import AuthorityComponentKind, ReferenceComponentQuery
from ..authority_store import SQLiteAuthorityReader
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


def _published_source_references() -> tuple[SourceReference, ...]:
    """Return every public-source declaration the published authority carries."""
    reader = SQLiteAuthorityReader(bundled_authority_descriptor_path())
    try:
        source_ids = tuple(
            query.reference_id
            for query in reader.component_queries()
            if isinstance(query, ReferenceComponentQuery) and query.kind is AuthorityComponentKind.SOURCE_REFERENCE
        )
    finally:
        reader.close()
    with bundled_indexed_authority().operation() as operation:
        return tuple(operation.source_reference(source_id) for source_id in source_ids)


@cache
def _manual_edition_texts(manual_id: str) -> tuple[tuple[int, str], ...]:
    # The registry declares each manual part as a public source whose applicability
    # window is the exercise its edition covers, and the committed corpus-text
    # sidecar holds that part's normalised text, pinned to the same source bytes.
    parts = sorted(
        (
            source
            for source in _published_source_references()
            if source.corpus_path.startswith(f"corpus/manuals/{manual_id}/")
        ),
        key=lambda source: source.corpus_path,
    )
    if not parts:
        raise LookupError(f"the published authority declares no {manual_id} manual part")
    texts: list[tuple[int, str]] = []
    for source in parts:
        relative = PurePosixPath(source.corpus_path).relative_to("corpus")
        sidecar = bundled_path("manual_corpus_text", *relative.parent.parts, f"{relative.name}.corpus_text.json")
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        if payload["source_sha256"] != source.sha256:
            raise LookupError(f"the corpus-text sidecar of source {source.id} was extracted from other bytes")
        texts.append((source_exercise(source), payload["normalised_text"]))
    return tuple(texts)


def manual_editions_printing(manual_id: str, *phrases: str) -> tuple[int, ...]:
    """Return the exercises of the bundled AEAT manual editions one of whose parts prints every phrase."""
    wanted = tuple(normalise_corpus_text(phrase) for phrase in phrases)
    return tuple(
        sorted({edition for edition, text in _manual_edition_texts(manual_id) if all(p in text for p in wanted)})
    )


def manual_edition_matches(manual_id: str, pattern: str) -> Mapping[int, re.Match[str]]:
    """Return, per bundled manual edition, the first match of ``pattern`` in its normalised text.

    The pattern is matched against the normalised corpus text, so it is written in the
    lower-case, accent-free form that normalisation produces. Editions that do not
    print it are absent.
    """
    compiled = re.compile(pattern)
    matches: dict[int, re.Match[str]] = {}
    for edition, text in _manual_edition_texts(manual_id):
        if edition not in matches and (match := compiled.search(text)) is not None:
            matches[edition] = match
    return dict(sorted(matches.items()))


def deadline_source_with_sha256(modelo_id: str, sha256: str) -> SourceReference:
    """Return the one source the authored deadline windows of a modelo cite whose bytes hash to ``sha256``.

    A deadline test whose expected days are the ones a pinned official calendar prints
    finds that calendar by its content hash, and reads the exercise it covers from the
    catalogued applicability rather than from its identifier.
    """
    cited = {
        ref
        for revision in authored_revisions(modelo_id)
        for window in revision.deadline_windows
        for ref in window.source_refs
    }
    with bundled_indexed_authority().operation() as operation:
        matches = [source for ref in sorted(cited) if (source := operation.source_reference(ref)).sha256 == sha256]
    if len(matches) != 1:
        raise LookupError(f"modelo {modelo_id}: expected one deadline source pinned to {sha256}, found {len(matches)}")
    return matches[0]


def open_ended_revision(modelo_id: str) -> RevisionSelectionMetadata:
    """Return the one authored revision of a modelo that has no end date."""
    (revision,) = (revision for revision in authored_revisions(modelo_id) if revision.valid_to is None)
    return revision


def split_exercise_revisions(modelo_id: str) -> tuple[RevisionSelectionMetadata, RevisionSelectionMetadata]:
    """Return the early and late revisions of the one exercise two authored designs split."""
    revisions = authored_revisions(modelo_id)
    split = [
        (earlier, later) for earlier, later in pairwise(revisions) if earlier.valid_from.year == later.valid_from.year
    ]
    if len(split) != 1:
        raise LookupError(f"modelo {modelo_id}: expected one exercise split across two designs, found {len(split)}")
    return split[0]


def revision_covering(modelo_id: str, exercise: int) -> RevisionSelectionMetadata:
    """Return the one authored revision of a modelo whose window covers ``exercise``."""
    (revision,) = (
        revision
        for revision in authored_revisions(modelo_id)
        if revision.valid_from.year <= exercise and (revision.valid_to is None or exercise <= revision.valid_to.year)
    )
    return revision


def revision_before_first_declaring(modelo_id: str, casilla_id: str) -> RevisionSelectionMetadata:
    """Return the authored revision right before the first one that declares ``casilla_id``."""
    revisions = authored_revisions(modelo_id)
    with bundled_indexed_authority().operation() as operation:
        first = next(
            index
            for index, metadata in enumerate(revisions)
            if casilla_id in {casilla.id for casilla in operation.revision(modelo_id, str(metadata.id)).casillas}
        )
    if first == 0:
        raise LookupError(f"modelo {modelo_id}: casilla {casilla_id} is declared by the oldest revision")
    return revisions[first - 1]
