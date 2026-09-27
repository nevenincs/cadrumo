"""Exercise coordinates read off the compiled registry instead of being spelled out.

A test about "the newest edition the registry authors", "the design a pinned hash
names" or "the manual edition that prints an example" asks this module for the
year, so it follows the registry and its evidence when an edition is authored,
retired or re-scoped rather than silently pointing at a hand-written year.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from functools import cache
from pathlib import Path

from cadrumo.core.corpus_text import normalise_corpus_text
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_references import LegalReference, SourceReference
from dev.corpus.manual_corpus_sidecar import MANUAL_CORPUS_TEXT_SIDECAR_SUFFIX, ManualCorpusTextSidecar

from ..compiler.authority import compiled_bundled_authority
from ..compiler.legal_grounding import published_legal_evidence_text


def authored_revisions(modelo_id: str) -> tuple[ModeloRevision, ...]:
    """Return every authored revision of one modelo, oldest first."""
    modelo = compiled_bundled_authority().modelo(modelo_id)
    return tuple(sorted(modelo.revisions.values(), key=lambda revision: revision.valid_from))


def newest_authored_editions(modelo_id: str, count: int) -> tuple[int, ...]:
    """Return the first exercises of the ``count`` newest authored revisions, oldest first."""
    revisions = authored_revisions(modelo_id)
    if len(revisions) < count:
        raise LookupError(f"modelo {modelo_id}: {len(revisions)} authored revisions, {count} requested")
    return tuple(revision.valid_from.year for revision in revisions[-count:])


def newest_authored_edition(modelo_id: str) -> int:
    """Return the first exercise of the newest authored revision of one modelo."""
    return newest_authored_editions(modelo_id, 1)[0]


def oldest_authored_edition(modelo_id: str) -> int:
    """Return the first exercise of the oldest authored revision of one modelo."""
    return authored_revisions(modelo_id)[0].valid_from.year


def authored_revisions_where(
    modelo_id: str,
    predicate: Callable[[ModeloRevision], bool],
) -> tuple[ModeloRevision, ...]:
    """Return the authored revisions of one modelo that satisfy ``predicate``, oldest first."""
    return tuple(revision for revision in authored_revisions(modelo_id) if predicate(revision))


def source_reference(source_id: str) -> SourceReference:
    """Return one compiled source declaration."""
    return compiled_bundled_authority().catalogues.sources[source_id]


def legal_reference(legal_id: str) -> LegalReference:
    """Return one compiled legal declaration."""
    return compiled_bundled_authority().catalogues.legal[legal_id]


def legal_text_match(legal_id: str, pattern: str) -> re.Match[str]:
    """Return the first match of ``pattern`` in the anchored corpus text of one legal citation.

    The text is the normalised provision the compiled citation anchors, so a test whose
    expectation is a statutory window reads it from the provision's own wording.
    """
    text = published_legal_evidence_text(legal_reference(legal_id), source_root=bundled_path())
    match = re.search(pattern, text)
    if match is None:
        raise LookupError(f"{legal_id}: the anchored text does not match {pattern!r}")
    return match


def revision_covering(modelo_id: str, exercise: int) -> ModeloRevision:
    """Return the one authored revision of a modelo whose window covers ``exercise``."""
    (revision,) = (
        revision
        for revision in authored_revisions(modelo_id)
        if revision.valid_from.year <= exercise and (revision.valid_to is None or exercise <= revision.valid_to.year)
    )
    return revision


def source_with_sha256(sha256: str) -> SourceReference:
    """Return the one catalogued source whose pinned bytes hash to ``sha256``."""
    matches = [source for source in compiled_bundled_authority().catalogues.sources.values() if source.sha256 == sha256]
    if len(matches) != 1:
        raise LookupError(f"expected one source pinned to {sha256}, found {len(matches)}")
    return matches[0]


def sources_where(predicate: Callable[[SourceReference], bool]) -> tuple[SourceReference, ...]:
    """Return every catalogued source that satisfies ``predicate``, ordered by applicability."""
    matches = [source for source in compiled_bundled_authority().catalogues.sources.values() if predicate(source)]
    return tuple(sorted(matches, key=lambda source: (source.applies_from is None, source.applies_from, source.id)))


def source_exercise(source: SourceReference) -> int:
    """Return the first exercise a source's applicability window covers."""
    if source.applies_from is None:
        raise LookupError(f"source {source.id} declares no applicability start")
    return source.applies_from.year


@cache
def manual_editions_printing(manual_id: str, *phrases: str) -> tuple[int, ...]:
    """Return the exercises of the bundled AEAT manual editions whose text prints every phrase.

    The manual corpus stores one directory per edition with a manifest naming the
    exercise it covers; the committed text sidecar is the edition's normalised text.
    """
    wanted = tuple(normalise_corpus_text(phrase) for phrase in phrases)
    corpus_root = bundled_path("corpus", "manuals", manual_id)
    text_root = bundled_path("manual_corpus_text", "manuals", manual_id)
    editions: list[int] = []
    for manifest_path in sorted(corpus_root.glob("**/manifest.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        edition_dir = manifest_path.parent.relative_to(corpus_root)
        sidecar = _sidecar(
            text_root / edition_dir / f"{manifest['relative_pdf_path']}{MANUAL_CORPUS_TEXT_SIDECAR_SUFFIX}"
        )
        if sidecar is not None and all(phrase in sidecar.normalised_text for phrase in wanted):
            editions.append(int(manifest["year"]))
    return tuple(sorted(set(editions)))


def _sidecar(path: Path) -> ManualCorpusTextSidecar | None:
    if not path.is_file():
        return None
    return ManualCorpusTextSidecar.model_validate_json(path.read_text(encoding="utf-8"))


def manual_oracle_payloads(modelo_id: str, scenario: str) -> dict[int, str]:
    """Return, per exercise, the bundled manual-oracle payload file of one worked-example scenario.

    A payload declares the modelo and the exercise its manual edition prints the
    example for, and names its scenario ``m<modelo>-<exercise>-<scenario>``.
    """
    payloads: dict[int, str] = {}
    for path in sorted(bundled_path("corpus", "manual_oracles").glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        exercise = payload.get("filing_year")
        if payload.get("modelo") == modelo_id and payload.get("scenario_id") == f"m{modelo_id}-{exercise}-{scenario}":
            payloads[int(exercise)] = path.name
    return payloads
