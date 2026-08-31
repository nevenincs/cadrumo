"""The caller the runner was written for: drives real entry points, scores the result.

The harness package deliberately measures nothing on its own -- the runner takes
measured rows from a caller that drove the product. That caller did not exist
anywhere in the repository, so the instrument could not be pointed at anything:
``HarnessReport`` was constructed only in the harness's own tests. This is the
missing half.

**It reads through the product's own entry point and reimplements nothing.** A
409-line shadow parser was deleted from an earlier harness for exactly that
reason, and a harness that reimplements the reader measures itself. What this
adds is the plumbing between three shipped pieces: the reader, the corpus-to-draft
projection, and the scorer.

**The structured lane needs no model, and that is what makes this runnable
here.** A Facturae, UBL or CII document is read deterministically, so a
structured-lane run is reproducible on a machine with no inference runtime at
all and its numbers are stable across runs. The text and vision lanes reach a
model by design; this driver treats them identically and simply cannot be run
for them without one, which is a property of those lanes rather than of this
code.

**Stage is declared by the caller rather than inferred.** The runner refuses a
row whose declared stage cannot produce a slot the document authors, and that
refusal only means anything if the stage is stated honestly. Guessing it here --
from the file extension, say -- would let this module quietly satisfy a check
written to catch exactly that.

See Also:
    :class:`~dev.ingest_harness.HarnessReport`
        What the rows this builds are collected into.
    :func:`~dev.ingest_harness.score_emission`
        The verdict logic, which stays where it was.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ._field_mapping import expand_document_slots, project_emission
from ._key import CORPUS_ROOT, CorpusDocument
from ._result import EngineRoute, ModelTier, PipelineStage, ResultRow, Scored, build_result_row
from ._scoring import score_emission

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["DriverError", "measure_structured_document", "read_structured_draft"]


class DriverError(RuntimeError):
    """A document could not be driven through the product's entry point."""


def _document_path(document: CorpusDocument) -> Path:
    """Return the corpus document's path on disk, refusing an absent one."""
    path = CORPUS_ROOT / document.path
    if not path.is_file():
        raise DriverError(
            f"{document.doc_id}: the key names {document.path!r} but no such file is present under "
            f"the corpus root. A measurement over documents that are not there would report a "
            f"denominator nobody can reconstruct.",
        )
    return path


def read_structured_draft(document: CorpusDocument) -> dict[str, Any]:
    """Read one structured document through the product's own parser.

    Deterministic and model-free: the structured readers recover values from the
    format's own machine-readable elements, so this is reproducible on a machine
    with no inference runtime.

    Args:
        document: The corpus document to read.

    Returns:
        The draft as a plain mapping of field name to value, which is what the
        projection consumes. Values are left exactly as the reader produced
        them -- a malformed one stays malformed and is scored wrong, because a
        driver that tidied them would convert a reading failure into a match.

    Raises:
        DriverError: When the file is absent or the parser refuses it.
    """
    # Imported at call time: the product package is heavy and the harness's own
    # shape tests import this module without ever driving a document.
    from cadrumo.adapters.inbound.einvoice.parsers import parse_einvoice_document

    path = _document_path(document)
    try:
        parsed = parse_einvoice_document(path.read_bytes())
    except Exception as error:
        raise DriverError(f"{document.doc_id}: the structured reader refused it: {error}") from error

    return {
        name: getattr(parsed, name)
        for name in dir(parsed)
        if not name.startswith("_") and not callable(getattr(parsed, name, None))
    }


def measure_structured_document(
    document: CorpusDocument,
    *,
    key_sha256: str,
    model_identity: str = "deterministic-structured-reader",
    model_revision: str = "n/a",
) -> ResultRow:
    """Drive one structured document and return its scored row.

    Args:
        document: The corpus document to measure.
        key_sha256: The pinned key this row is scored against, so the report can
            refuse a row from another key.
        model_identity: Recorded on the row. Defaults to naming the
            deterministic reader, because no model answers on this lane and a
            row claiming one would misattribute the result.
        model_revision: Recorded alongside it.

    Returns:
        The :class:`ResultRow` for this document.

    Raises:
        DriverError: When the document cannot be driven.
        HarnessRefusalError: When the row cannot be honestly quoted -- a scored
            outcome over a document authoring no truth, or a denominator that is
            not the key's own.
    """
    expanded = expand_document_slots(document)
    emitted = project_emission(expanded, read_structured_draft(document))
    scoring = score_emission(document=expanded, emitted=emitted)

    return build_result_row(
        document=expanded,
        key_sha256=key_sha256,
        # Stated, never inferred. The structured reader recovers values from the
        # record's own elements and grounds them in one pass, so END_TO_END is
        # what actually ran -- and the runner's stage check is only meaningful
        # if this is honest.
        stage=PipelineStage.END_TO_END,
        # DETERMINISTIC rather than a local route: no model runs at all here,
        # and the enum carries a member for exactly that so a parser is not
        # filed under an inference route it never took.
        engine_route=EngineRoute.DETERMINISTIC,
        model_identity=model_identity,
        model_revision=model_revision,
        # The deterministic lane sets no acceptance floor for a MODEL: it
        # measures a parser, and a floor drawn from it would flatter every
        # model-read lane it was compared against.
        model_tier=ModelTier.UPPER_REFERENCE,
        outcome=Scored(
            scorable_field_count=len(expanded.scorable_fields),
            matched=scoring.matched,
            wrong=scoring.wrong,
            fabricated=scoring.fabricated,
        ),
    )
