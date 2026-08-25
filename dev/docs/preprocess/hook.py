"""Upstream vaultspec-rag preprocess-hook adapter over the project extractors.

This is the ``command``-form preprocessor the repo-root
``.vaultragpreprocess.toml`` rules invoke (one subprocess per matched source
file, ``{path}`` substituted token-wise by the upstream runner). It routes the
source file to the existing extractor family by suffix, adapts the extractor's
:class:`~dev.docs.preprocess.PreprocessOutput` parts onto the upstream
``PreprocOutput`` contract (schema major pinned by
:data:`UPSTREAM_SCHEMA_VERSION`), and prints exactly one JSON document on
stdout — the contract ``vaultspec-rag preprocess run-one`` validates.

The adapter deliberately imports nothing from ``cadrumo``: the upstream runner
executes it inside the resident watcher's indexing path, so it must stay
CPU-only, dependency-light, and independent of application settings (which
refuse to construct on a workstation whose storage root carries retired
state).

Exit codes follow the upstream skip-and-report semantics: ``0`` with JSON on
stdout for a usable extraction; non-zero with a stderr line for an unmatched
suffix or an empty extraction, which the runner records as a per-file skip
rather than a crash.

Invoke as ``python -m dev.docs.preprocess.hook <path>`` (through
``uv run --no-sync`` in the rule command so the project environment resolves
on any OS).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final

from ..._paths import REPO_ROOT, UTF_8
from ._schema import ExtractionStatus, PreprocessOutput

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

#: The upstream ``PreprocOutput`` schema major this adapter emits. Pinned so an
#: upstream major bump is a deliberate adapter change, never silent drift; the
#: strict ``preprocess check`` repo gate catches the reverse direction.
UPSTREAM_SCHEMA_VERSION: Final[int] = 1

_EXIT_UNSUPPORTED: Final[int] = 2
_EXIT_EMPTY: Final[int] = 3
_UTF_8: Final[str] = UTF_8

__all__ = [
    "UPSTREAM_SCHEMA_VERSION",
    "adapt_outputs",
    "build_for_source",
    "main",
]


def _builders() -> dict[str, Callable[..., list[PreprocessOutput]]]:
    """Return the suffix-to-extractor dispatch, imported lazily.

    Lazy so ``preprocess check`` (which only shlex-parses the rule command)
    and the unsupported-suffix refusal never pay for pdfplumber/openpyxl
    imports.
    """
    from ._html import build_outputs as build_html
    from ._pdf import build_outputs as build_pdf
    from ._terminology import build_outputs as build_terminology
    from ._workbook import build_outputs as build_workbook

    return {
        ".html": build_html,
        ".pdf": build_pdf,
        ".xls": build_workbook,
        ".xlsm": build_workbook,
        ".xlsx": build_workbook,
        ".toml": build_terminology,
    }


def build_for_source(source: Path, *, repo_root: Path) -> list[PreprocessOutput]:
    """Run the matching extractor family for ``source``.

    Args:
        source: The file the upstream runner matched a rule against.
        repo_root: Repository root for relative provenance paths.

    Raises:
        LookupError: When no extractor family owns the source's suffix.
    """
    builder = _builders().get(source.suffix.lower())
    if builder is None:
        msg = f"no preprocess extractor for suffix {source.suffix!r}: {source}"
        raise LookupError(msg)
    return builder(source, repo_root=repo_root)


def _aggregate_status(outputs: Sequence[PreprocessOutput]) -> ExtractionStatus:
    """Fold per-part statuses into one document status (worst wins)."""
    statuses = {output.status for output in outputs}
    if ExtractionStatus.PARTIAL in statuses:
        return ExtractionStatus.PARTIAL
    if statuses == {ExtractionStatus.EMPTY}:
        return ExtractionStatus.EMPTY
    return ExtractionStatus.OK


def adapt_outputs(
    outputs: Sequence[PreprocessOutput],
    *,
    source: Path,
    repo_root: Path,
) -> dict[str, object]:
    """Adapt extractor part outputs onto one upstream ``PreprocOutput`` payload.

    Multi-part extractions (a large Diseños workbook split by the parts
    budget) collapse into a single upstream document: the upstream indexer
    re-chunks units itself, so parts were only ever a sidecar-size measure.
    Part provenance survives on per-unit ``metadata`` when more than one part
    contributed.

    Args:
        outputs: The extractor's part outputs, in order. Must be non-empty.
        source: The source file, for the upstream ``source_path`` field.
        repo_root: Repository root the relative source path is computed from.
    """
    if not outputs:
        msg = f"extractor produced no outputs for {source}"
        raise ValueError(msg)
    first = outputs[0]
    units: list[dict[str, object]] = []
    for part_index, output in enumerate(outputs):
        for unit in output.units:
            adapted: dict[str, object] = {"text": unit.text}
            if unit.title is not None:
                adapted["title"] = unit.title
            if unit.section is not None:
                adapted["section"] = unit.section
            if unit.anchor is not None:
                adapted["anchor"] = unit.anchor
            if len(outputs) > 1:
                adapted["metadata"] = {"part": part_index}
            units.append(adapted)
    source_bytes = source.read_bytes()
    return {
        "schema_version": UPSTREAM_SCHEMA_VERSION,
        "preprocessor_id": first.preprocessor_id,
        "preprocessor_version": first.preprocessor_version,
        "source_path": source.resolve().relative_to(repo_root.resolve()).as_posix(),
        "units": units,
        "metadata": {
            "source_kind": first.source_kind.value,
            "status": _aggregate_status(outputs).value,
            "attribution": first.attribution,
            "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
            "parts": len(outputs),
        },
    }


def main(argv: list[str] | None = None) -> int:
    """Adapt one source file and print the upstream JSON document on stdout."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Source file matched by a preprocess rule.")
    args = parser.parse_args(argv)
    source: Path = args.path
    repo_root = REPO_ROOT
    try:
        outputs = build_for_source(source, repo_root=repo_root)
    except LookupError as error:
        print(str(error), file=sys.stderr)
        return _EXIT_UNSUPPORTED
    if not outputs or all(not output.units for output in outputs):
        print(f"no extractable text in {source}", file=sys.stderr)
        return _EXIT_EMPTY
    payload = adapt_outputs(outputs, source=source, repo_root=repo_root)
    # Write UTF-8 bytes directly: the upstream runner decodes stdout as UTF-8,
    # while a Windows console python defaults to cp1252 for text-mode stdout.
    sys.stdout.buffer.write(json.dumps(payload, ensure_ascii=False).encode(_UTF_8))
    sys.stdout.buffer.write(b"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
