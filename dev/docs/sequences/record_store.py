"""Regenerated per-sequence transcript records and their committed fingerprints.

A record is the full, run-independent output of one executed sequence: per
frame the argv, exit code and captures, and for reader-facing frames the
path-normalised pre-mask JSON envelope or the normalised stdout and stderr
text. It is exactly what a docs page renders. It is derived output, so it lives
in the development cache (:func:`default_records_root`), never in Git.

The committed golden (:mod:`~dev.docs.sequences.golden_store`) is the
fingerprint of a record: :func:`golden_from_record` keeps each frame's kind,
argv, exit code, captures and envelope stream, and replaces its output with the
SHA-256 and byte size of the form the check compares (:func:`compared_form`).
Because the fingerprint is computed from the record, a record is trustworthy
exactly when its fingerprint equals the committed golden:
:func:`read_verified_record` is the only way a renderer obtains one.

Records are written by the refresh CLI and by a clean check. A check whose live
run diverges writes its record under :data:`DIVERGED_RECORDS_DIR` instead, so the
last verified record survives as the baseline the next divergence is diffed
against.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Final, Literal, cast

from pydantic import BaseModel, Field, JsonValue, ValidationError, model_validator

from cadrumo.core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from cadrumo.tests.golden_comparison import canonicalise, mask_document
from dev._paths import UTF_8
from dev.cache_root import dev_cache_dir

from .errors import SequenceGoldenError
from .golden_store import (
    GoldenFrame,
    SequenceGolden,
    golden_path,
    mask_host_conditional_details,
    masked_envelope_values,
    normalise_document_paths,
    normalise_text_output,
    read_golden,
    refresh_invocation,
)
from .runner import CapturedValue, EnvelopeSource, SequenceTranscript
from .schema import FrameKind, SequenceId

__all__ = [
    "DIVERGED_RECORDS_DIR",
    "RECORDS_DIR_ENV",
    "RecordFrame",
    "SequenceRecord",
    "build_record",
    "compared_form",
    "default_records_root",
    "diverged_record_path",
    "golden_from_record",
    "read_verified_record",
    "record_path",
    "recorded_output_bytes",
    "verified_baseline",
    "write_record",
]

_UTF_8: Final[str] = UTF_8

#: Development-cache family holding the records.
_RECORDS_CACHE_NAME: Final[str] = "docs-sequence-records"

#: Environment variable relocating the records alone, ahead of the shared cache root.
RECORDS_DIR_ENV: Final[str] = "CADRUMO_DOCS_SEQUENCE_RECORDS_DIR"

#: Sub-directory of the records root holding the live records of divergent runs.
DIVERGED_RECORDS_DIR: Final[str] = "_diverged"


class RecordFrame(BaseModel):
    """One executed frame's run-independent output.

    ``envelope`` is the path-normalised pre-mask JSON document and
    ``envelope_source`` names the stream that carried it. ``text`` is the
    normalised stdout when stdout did not carry the envelope; ``stderr_text``
    the normalised stderr when stderr did not. An empty stream is ``None``. A
    setup frame records no output: readers never see it and later frames
    consume only its captures.
    """

    model_config = _STRICT_FROZEN

    kind: FrameKind
    argv: tuple[str, ...] = Field(min_length=1)
    exit_code: int
    envelope: dict[str, JsonValue] | None = None
    envelope_source: EnvelopeSource | None = None
    text: str | None = None
    stderr_text: str | None = None
    captures: tuple[CapturedValue, ...] = Field(default=())

    @model_validator(mode="after")
    def _streams_are_coherent(self) -> RecordFrame:
        if self.kind is FrameKind.SETUP and (
            self.envelope is not None
            or self.envelope_source is not None
            or self.text is not None
            or self.stderr_text is not None
        ):
            raise ValueError("a setup frame records only its argv, exit code and captures")
        if (self.envelope is None) != (self.envelope_source is None):
            raise ValueError("'envelope' and 'envelope_source' are set together or not at all")
        if self.envelope_source == "stdout" and self.text is not None:
            raise ValueError("stdout carried the envelope; 'text' must be None")
        if self.envelope_source == "stderr" and self.stderr_text is not None:
            raise ValueError("stderr carried the envelope; 'stderr_text' must be None")
        return self


class SequenceRecord(BaseModel):
    """The regenerated output of one sequence, in executed-frame order."""

    model_config = _STRICT_FROZEN

    record_schema_version: Literal[1] = 1
    sequence_id: SequenceId
    frames: tuple[RecordFrame, ...] = Field(min_length=1)


def default_records_root() -> Path:
    """Return the directory holding the records.

    :data:`RECORDS_DIR_ENV` wins when set and non-blank; otherwise the records
    live in the development cache. A child interpreter scrubs ``CADRUMO_*``
    variables, so a parent launching one passes the resolved root explicitly.
    """
    override = os.environ.get(RECORDS_DIR_ENV, "").strip()
    if override:
        return Path(override)
    return dev_cache_dir(_RECORDS_CACHE_NAME)


def build_record(transcript: SequenceTranscript) -> SequenceRecord:
    """Project an executed transcript into its run-independent record.

    The writer run's sandbox and checkout paths are unknowable to a later
    reader, so they are baked out here: envelope string values are
    path-normalised (:func:`normalise_document_paths`) and the other streams
    are normalised text (:func:`normalise_text_output`). Field masking is not
    applied; it happens when the record is compared or rendered.
    """
    masked_values = masked_envelope_values(transcript)

    def _normalised(raw: str) -> str | None:
        if not raw:
            return None
        return normalise_text_output(
            raw,
            storage_root=transcript.storage_root,
            workdir=transcript.workdir,
            masked_values=masked_values,
        )

    frames: list[RecordFrame] = []
    for frame in transcript.frames:
        if frame.kind is FrameKind.SETUP:
            frames.append(
                RecordFrame(kind=frame.kind, argv=frame.argv, exit_code=frame.exit_code, captures=frame.captured)
            )
            continue
        envelope = (
            normalise_document_paths(frame.envelope, storage_root=transcript.storage_root, workdir=transcript.workdir)
            if frame.envelope is not None
            else None
        )
        frames.append(
            RecordFrame(
                kind=frame.kind,
                argv=frame.argv,
                exit_code=frame.exit_code,
                envelope=envelope,
                envelope_source=frame.envelope_source,
                text=_normalised(frame.output) if frame.envelope_source != "stdout" else None,
                stderr_text=_normalised(frame.stderr) if frame.envelope_source != "stderr" else None,
                captures=frame.captured,
            ),
        )
    return SequenceRecord(sequence_id=transcript.sequence_id, frames=tuple(frames))


def _masked_envelope(frame: RecordFrame) -> str | None:
    """Return the canonical envelope under the central mask and host carve-out, if any."""
    if frame.envelope is None:
        return None
    return canonicalise(cast("dict[str, object]", mask_host_conditional_details(mask_document(frame.envelope))))


def compared_form(frame: RecordFrame) -> str:
    """Return the exact string a frame's output is compared and fingerprinted on.

    The envelope is masked with the central field mask and the host-conditional
    carve-out, then canonicalised; the non-envelope streams contribute their
    normalised text, an absent stream reading as empty. Two frames whose outputs
    a reader could tell apart, other than through a centrally masked value,
    never share a compared form.
    """
    return json.dumps(
        {"envelope": _masked_envelope(frame), "stdout": frame.text or "", "stderr": frame.stderr_text or ""},
        ensure_ascii=False,
        sort_keys=True,
    )


def recorded_output_bytes(frame: RecordFrame) -> int:
    """Measure a frame's output as a page shows it, in UTF-8 bytes.

    The masked canonical JSON of its envelope plus its stdout text plus its
    stderr text, absent streams counting as empty. Measuring the masked form
    keeps the size as run-independent as the digest, so equal digests always
    carry equal sizes. This is the size the reader-facing output advisory
    judges.
    """
    return sum(
        len(part.encode(_UTF_8)) for part in (_masked_envelope(frame) or "", frame.text or "", frame.stderr_text or "")
    )


def golden_from_record(record: SequenceRecord) -> SequenceGolden:
    """Fingerprint a record into the golden that is committed for it."""
    frames: list[GoldenFrame] = []
    for frame in record.frames:
        if frame.kind is FrameKind.SETUP:
            frames.append(
                GoldenFrame(kind=frame.kind, argv=frame.argv, exit_code=frame.exit_code, captures=frame.captures)
            )
            continue
        frames.append(
            GoldenFrame(
                kind=frame.kind,
                argv=frame.argv,
                exit_code=frame.exit_code,
                captures=frame.captures,
                envelope_source=frame.envelope_source,
                output_sha256=hashlib.sha256(compared_form(frame).encode(_UTF_8)).hexdigest(),
                output_bytes=recorded_output_bytes(frame),
            ),
        )
    return SequenceGolden(sequence_id=record.sequence_id, frames=tuple(frames))


def record_path(page: str, sequence_id: str, *, records_root: Path | None = None) -> Path:
    """Return the record file path for ``(page, sequence_id)``."""
    root = records_root if records_root is not None else default_records_root()
    return golden_path(page, sequence_id, goldens_root=root)


def diverged_record_path(page: str, sequence_id: str, *, records_root: Path | None = None) -> Path:
    """Return where a divergent check run leaves its live record for inspection."""
    root = records_root if records_root is not None else default_records_root()
    return golden_path(page, sequence_id, goldens_root=root / DIVERGED_RECORDS_DIR)


def write_record(record: SequenceRecord, *, target: Path) -> Path:
    """Write ``record`` to ``target`` as key-sorted UTF-8 JSON, atomically.

    Concurrent builds can share one records root, so a reader must see either
    the previous record or the new one, never a partial file.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    staging.write_text(
        json.dumps(record.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding=_UTF_8,
        newline="\n",
    )
    staging.replace(target)
    return target


def _read_record(target: Path) -> SequenceRecord | None:
    """Read a record, or ``None`` when it is absent or does not validate."""
    try:
        return SequenceRecord.model_validate_json(target.read_text(encoding=_UTF_8))
    except (OSError, ValidationError):
        return None


def verified_baseline(
    page: str,
    golden: SequenceGolden,
    *,
    records_root: Path | None = None,
) -> SequenceRecord | None:
    """Return the cached record for ``golden`` when its fingerprint equals it, else ``None``."""
    record = _read_record(record_path(page, golden.sequence_id, records_root=records_root))
    if record is None or golden_from_record(record) != golden:
        return None
    return record


def read_verified_record(
    page: str,
    sequence_id: str,
    *,
    goldens_root: Path | None = None,
    records_root: Path | None = None,
) -> SequenceRecord:
    """Return the record a page may render: one whose fingerprint is the committed golden.

    Raises:
        SequenceGoldenError: When the golden is missing or malformed, or when no
            record matching it is cached. Either way the page must not render,
            and the message names the check that produces the record.
    """
    golden = read_golden(page, sequence_id, goldens_root=goldens_root)
    record = verified_baseline(page, golden, records_root=records_root)
    if record is None:
        raise SequenceGoldenError(
            f"no verified record for sequence {sequence_id!r} on page {page!r}: the cached output "
            f"({record_path(page, sequence_id, records_root=records_root)}) is missing or does not "
            f"match the committed golden; produce it with: python -m dev.docs.sequences check --page {page} "
            f"(or, when the golden itself is stale, {refresh_invocation(sequence_id=sequence_id)})",
        )
    return record
