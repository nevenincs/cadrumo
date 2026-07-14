"""Committed light per-sequence golden store for ``cli-sequence`` runs.

One golden file per sequence at ``docs/_sequences/<page-path>/<sequence-id>.json``,
carrying per frame: the argv as executed, the exit code, the verbatim pre-mask
:class:`~cadrumo.core.json_contract.SchemaEnvelope` document for JSON frames or
the normalised verbatim text for text frames, and the capture bindings. These
are light, review-diffable data — the Pagefind commit boundary: commit the light
expectation, regenerate every heavy rendered surface.

Goldens are CLI-owned and never hand-edited: the ``refresh`` mode
re-executes the sequence in its sandbox and rewrites the file
through :func:`write_golden`; the author reviews the git diff — which IS the
behaviour-change review — and commits the golden with the CLI change that
legitimately moved it. A missing or hand-corrupted golden reads as an
instructive :class:`~dev.docs.sequences._errors.SequenceGoldenError` naming the
exact refresh invocation.

Storage policy per frame kind:

- **JSON frames** store the parsed envelope document verbatim, PRE-mask —
  capture raw, mask at compare — so the committed artifact never bakes the mask
  in and the mask set can evolve centrally.
- **Text frames** store the verbatim text AFTER the declared narrow
  normalisation (:func:`normalise_text_output`): the per-run sandbox paths are
  replaced by stable tokens and the centrally-masked surrogate ids by the mask
  sentinel. Unlike the JSON mask, this normalisation cannot be deferred to
  compare time — the writer run's sandbox paths are unknowable to a later
  reader, so the stored text must already be run-independent.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Annotated, Final, Literal

from pydantic import BaseModel, Field, JsonValue, StringConstraints, ValidationError, model_validator

from cadrumo.core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from cadrumo.core.observability import GOLDEN_MASK_FIELDS, MASK_SENTINEL

from ._errors import SequenceGoldenError
from ._runner import CapturedValue, EnvelopeSource, SequenceTranscript
from ._schema import FrameKind, SequenceId

__all__ = [
    "SANDBOX_STORAGE_ROOT_TOKEN",
    "SANDBOX_WORKDIR_TOKEN",
    "GoldenFrame",
    "SequenceGolden",
    "build_golden",
    "default_goldens_root",
    "golden_path",
    "masked_envelope_values",
    "normalise_text_output",
    "read_golden",
    "refresh_invocation",
    "write_golden",
]

_UTF_8: Final[str] = "utf-8"

#: Stable token replacing the per-run isolated storage root in text frames.
SANDBOX_STORAGE_ROOT_TOKEN: str = "<sandbox-storage-root>"  # noqa: S105 - a display placeholder, not a secret

#: Stable token replacing the per-run sandbox working directory in text frames.
SANDBOX_WORKDIR_TOKEN: str = "<sandbox-workdir>"  # noqa: S105 - a display placeholder, not a secret

#: A page identifier: the docname-style path of the enrolled docs page relative
#: to ``docs/`` (e.g. ``how-to/irpf-lifecycle`` or ``how-to/modelo-303``),
#: forward slashes, no suffix, no traversal.
PageId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=200,
        pattern=r"^[a-z0-9][a-z0-9._-]*(/[a-z0-9][a-z0-9._-]*)*$",
    ),
]

_PAGE_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*(/[a-z0-9][a-z0-9._-]*)*$")


class GoldenFrame(BaseModel):
    """One committed frame expectation.

    The two process streams are covered independently. ``envelope`` is the
    verbatim pre-mask JSON document with ``envelope_source`` naming the stream
    that carried it — ``stdout`` for a success envelope, ``stderr`` for a
    refusal's error document (both share the envelope spine). ``text`` is the
    normalised stdout when stdout did NOT carry the envelope; ``stderr_text``
    the normalised stderr when stderr did not. An empty stream stores ``None``
    (compared as equal to the empty string), so a frame whose only output is
    an exit code is a legitimate all-``None`` golden. ``captures`` are the
    values the frame bound at capture time, so an id drift is named directly
    in review diffs and check failures.
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
    def _streams_are_coherent(self) -> GoldenFrame:
        if (self.envelope is None) != (self.envelope_source is None):
            raise ValueError("'envelope' and 'envelope_source' are set together or not at all")
        if self.envelope_source == "stdout" and self.text is not None:
            raise ValueError("stdout carried the envelope; 'text' must be None")
        if self.envelope_source == "stderr" and self.stderr_text is not None:
            raise ValueError("stderr carried the envelope; 'stderr_text' must be None")
        return self


class SequenceGolden(BaseModel):
    """The committed golden expectation of one sequence, in frame order."""

    model_config = _STRICT_FROZEN

    golden_schema_version: Literal[1] = 1
    sequence_id: SequenceId
    frames: tuple[GoldenFrame, ...] = Field(min_length=1)


def default_goldens_root() -> Path:
    """Return the committed ``docs/_sequences/`` golden tree.

    Resolved relative to this module so the engine finds goldens regardless of
    the process working directory (the same anchoring as seeds and fixtures).
    """
    repo_root = Path(__file__).resolve().parents[3]
    return repo_root / "docs" / "_sequences"


def refresh_invocation(*, page: str | None = None, sequence_id: str | None = None) -> str:
    """Return the exact CLI invocation that (re)writes the addressed goldens."""
    command = "python -m dev.docs.sequences refresh"
    if sequence_id is not None:
        return f"{command} --sequence {sequence_id}"
    if page is not None:
        return f"{command} --page {page}"
    return command


def _validated_page(page: str) -> str:
    stripped = page.strip().replace("\\", "/")
    if not _PAGE_RE.match(stripped) or ".." in stripped.split("/"):
        raise SequenceGoldenError(
            f"page identifier {page!r} must be the docname-style path of the enrolled "
            "page relative to docs/ (forward slashes, lowercase, no suffix, no traversal), "
            "e.g. 'how-to/irpf-lifecycle'",
        )
    return stripped


def golden_path(page: str, sequence_id: str, *, goldens_root: Path | None = None) -> Path:
    """Return the committed golden file path for ``(page, sequence_id)``."""
    root = goldens_root if goldens_root is not None else default_goldens_root()
    return root / _validated_page(page) / f"{sequence_id}.json"


def masked_envelope_values(transcript: SequenceTranscript) -> frozenset[str]:
    """Collect the transcript's centrally-masked surrogate-key values.

    Walks every JSON frame's envelope and gathers the string values stored under
    the :data:`GOLDEN_MASK_FIELDS` keys at any depth. Text normalisation replaces
    these values where they appear inline in text output — the "central masked
    ids where they appear inline" half of the text-normalisation policy.
    """
    values: set[str] = set()

    def _walk(node: object) -> None:
        if isinstance(node, Mapping):
            for key, item in node.items():
                if str(key) in GOLDEN_MASK_FIELDS and isinstance(item, str):
                    values.add(item)
                else:
                    _walk(item)
            return
        if isinstance(node, list | tuple):
            for item in node:
                _walk(item)

    for frame in transcript.frames:
        if frame.envelope is not None:
            _walk(frame.envelope)
    return frozenset(values)


def normalise_text_output(
    text: str,
    *,
    storage_root: str,
    workdir: str,
    masked_values: Iterable[str] = (),
) -> str:
    """Apply the declared narrow text normalisation.

    Exactly two token families are normalised — nothing else: the per-run
    sandbox paths (storage root and workdir, in both native and POSIX slash
    forms, longest first so nested paths collapse correctly) become stable
    tokens, and the centrally-masked surrogate-id values become the mask
    sentinel. No regex wildcards, no fuzzy matching: the result is compared by
    exact string equality.
    """
    replacements: list[tuple[str, str]] = []
    for raw, token in ((workdir, SANDBOX_WORKDIR_TOKEN), (storage_root, SANDBOX_STORAGE_ROOT_TOKEN)):
        native = str(raw)
        posix = native.replace("\\", "/")
        replacements.append((native, token))
        if posix != native:
            replacements.append((posix, token))
    for value in masked_values:
        if value:
            replacements.append((value, MASK_SENTINEL))

    normalised = text
    for needle, token in sorted(replacements, key=lambda pair: len(pair[0]), reverse=True):
        normalised = normalised.replace(needle, token)
    return normalised


def build_golden(transcript: SequenceTranscript) -> SequenceGolden:
    """Project an executed transcript into its committed golden expectation.

    The envelope (from whichever stream carried it) is kept verbatim
    (pre-mask); the non-envelope streams store their normalised text so the
    artifact is run-independent, with empty streams collapsing to ``None``.
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

    frames: list[GoldenFrame] = []
    for frame in transcript.frames:
        text = _normalised(frame.output) if frame.envelope_source != "stdout" else None
        stderr_text = _normalised(frame.stderr) if frame.envelope_source != "stderr" else None
        frames.append(
            GoldenFrame(
                kind=frame.kind,
                argv=frame.argv,
                exit_code=frame.exit_code,
                envelope=frame.envelope,
                envelope_source=frame.envelope_source,
                text=text,
                stderr_text=stderr_text,
                captures=frame.captured,
            ),
        )
    return SequenceGolden(sequence_id=transcript.sequence_id, frames=tuple(frames))


def write_golden(
    transcript: SequenceTranscript,
    *,
    page: str,
    goldens_root: Path | None = None,
) -> Path:
    """Write the transcript's golden expectation to its committed location.

    This is the ONLY sanctioned writer (the refresh CLI mode drives it); a
    hand-edited golden drifts from the executed truth and is overwritten by the
    next refresh. The file is canonical JSON — key-sorted, two-space indent,
    UTF-8, trailing newline — so review diffs are stable and minimal.
    """
    target = golden_path(page, transcript.sequence_id, goldens_root=goldens_root)
    golden = build_golden(transcript)
    document = golden.model_dump(mode="json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding=_UTF_8,
    )
    return target


def read_golden(
    page: str,
    sequence_id: str,
    *,
    goldens_root: Path | None = None,
) -> SequenceGolden:
    """Read and strictly validate a committed golden expectation.

    Raises:
        SequenceGoldenError: When the golden file is missing (naming the exact
            refresh invocation that creates it), is not valid JSON, or does not
            validate against the strict golden schema (the hand-edit signal).
    """
    target = golden_path(page, sequence_id, goldens_root=goldens_root)
    if not target.is_file():
        raise SequenceGoldenError(
            f"no committed golden for sequence {sequence_id!r} on page {page!r} "
            f"(expected {target}); generate it with: "
            f"{refresh_invocation(sequence_id=sequence_id)}",
        )
    try:
        raw = target.read_text(encoding=_UTF_8)
    except OSError as exc:
        raise SequenceGoldenError(f"cannot read golden {target}: {exc}") from exc
    try:
        return SequenceGolden.model_validate_json(raw)
    except ValidationError as exc:
        raise SequenceGoldenError(
            f"golden {target} does not validate against the golden schema — goldens "
            f"are CLI-owned and never hand-edited; regenerate it with: "
            f"{refresh_invocation(sequence_id=sequence_id)}\n{exc}",
        ) from exc
