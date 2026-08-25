"""Thin writer/loader for the interim ``*.extracted`` sidecar pair.

Each preprocessed source file gains two committed siblings:

* ``<stem>.extracted.md`` -- the rendered plain text the ``vaultspec-rag``
  walker indexes (``.md`` is in the walker's supported-extension set, so no
  upstream change is needed to pick it up).
* ``<stem>.extracted.json`` -- the serialised :class:`PreprocessOutput`
  provenance record (origin path, origin sha256, extractor id/version,
  source kind, status, attribution, pre-chunked units).

The format-specific extractors (normatives HTML, Disenos de Registro
workbooks, corpus PDFs, the unsupported-text tail) build the
:class:`PreprocessOutput` and call :func:`write_sidecar`; this module owns
only the serialisation and the round-trip, not the extraction. The text
sidecar is the indexed surface; the json sidecar is provenance, named so
the walker (which does not index ``.json`` for this corpus path) treats it
as inert metadata while a gate can cross-check ``source_sha256`` against the
live origin file to catch staleness.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Final

from ..._paths import UTF_8
from ._schema import PreprocessOutput

_UTF_8: Final[str] = UTF_8

#: Suffix of the indexable rendered-text sidecar (walker indexes ``.md``).
EXTRACTED_TEXT_SUFFIX = ".extracted.md"

#: Suffix of the provenance sidecar carrying the serialised record.
EXTRACTED_JSON_SUFFIX = ".extracted.json"


class PreprocessSidecarError(RuntimeError):
    """Raised when a sidecar pair cannot be written or loaded."""


def sidecar_paths_for(source: Path) -> tuple[Path, Path]:
    """Return the ``(text, json)`` sidecar paths for a source file.

    The sidecars are named from the source's full filename (suffix
    included) so two sources that differ only by extension -- the same
    Disenos de Registro design shipped as both ``.xls`` and ``.txt`` --
    never collide on one sidecar.

    Args:
        source: The origin file being preprocessed.

    Returns:
        A ``(text_sidecar, json_sidecar)`` tuple of sibling paths.
    """
    base = source.name
    return (
        source.with_name(base + EXTRACTED_TEXT_SUFFIX),
        source.with_name(base + EXTRACTED_JSON_SUFFIX),
    )


def sha256_of(path: Path) -> str:
    """Return the hex sha256 of a file's bytes (the staleness key).

    Args:
        path: File to hash.

    Returns:
        Lower-case hex sha256 digest.

    Raises:
        PreprocessSidecarError: If the file cannot be read.
    """
    try:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise PreprocessSidecarError(f"cannot hash source {path}: {exc}") from exc
    return digest


def write_sidecar(source: Path, output: PreprocessOutput) -> tuple[Path, Path]:
    """Write the ``*.extracted.md`` + ``*.extracted.json`` sidecar pair.

    Args:
        source: The origin file the sidecars sit beside.
        output: The extraction record to serialise. Its ``source_relpath``
            and ``source_sha256`` are trusted as authored by the extractor;
            callers compute ``source_sha256`` via :func:`sha256_of`.

    Returns:
        The ``(text_sidecar, json_sidecar)`` paths written.

    Raises:
        PreprocessSidecarError: If either sidecar cannot be written.
    """
    text_path, json_path = sidecar_paths_for(source)
    payload = output.model_dump(mode="json")
    # Write LF newlines explicitly (newline="") so the on-disk bytes are
    # deterministic across platforms: Python text mode would otherwise
    # translate "\n" to the OS line ending, churning the committed sidecars
    # against the repo's eol=lf normalisation on Windows.
    try:
        text_path.write_text(output.render_text(), encoding=_UTF_8, newline="")
        json_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding=_UTF_8,
            newline="",
        )
    except OSError as exc:
        raise PreprocessSidecarError(f"cannot write sidecar for {source}: {exc}") from exc
    return text_path, json_path


def load_sidecar(source: Path) -> PreprocessOutput:
    """Load and validate the provenance sidecar for a source file.

    Recomputes the origin file's sha256 and cross-checks it against the
    sidecar's recorded ``source_sha256`` so a sidecar left behind by an edit
    to the source (without re-running the extractor) is refused rather than
    silently served as current.

    Args:
        source: The origin file whose ``*.extracted.json`` is read.

    Returns:
        The validated :class:`PreprocessOutput`.

    Raises:
        PreprocessSidecarError: If the sidecar is missing, unreadable, not
            valid JSON, fails schema validation (including an unknown
            ``schema_version``), or its recorded ``source_sha256`` no longer
            matches the origin file's live content hash.
    """
    text_path, json_path = sidecar_paths_for(source)
    try:
        raw = json_path.read_text(encoding=_UTF_8)
    except OSError as exc:
        raise PreprocessSidecarError(f"sidecar missing or unreadable for {source}: {exc}") from exc
    # Parse through pydantic's JSON path so strict-mode coercion treats the
    # JSON document as a JSON document (StrEnum from its string value, tuple
    # from a JSON array) rather than refusing it as it would a raw dict.
    try:
        output = PreprocessOutput.model_validate_json(raw)
    except ValueError as exc:
        raise PreprocessSidecarError(f"sidecar for {source} failed to load or validate: {exc}") from exc
    live_sha256 = sha256_of(source)
    if output.source_sha256 != live_sha256:
        raise PreprocessSidecarError(
            f"sidecar for {source} is stale: recorded source_sha256={output.source_sha256} "
            f"but the source file now hashes to {live_sha256}"
        )
    try:
        rendered_text = text_path.read_text(encoding=_UTF_8)
    except OSError as exc:
        raise PreprocessSidecarError(f"text sidecar missing or unreadable for {source}: {exc}") from exc
    if rendered_text != output.render_text():
        raise PreprocessSidecarError(f"sidecar pair for {source} has divergent rendered text")
    return output
