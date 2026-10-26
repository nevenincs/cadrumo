"""Generate and verify committed HTML and workbook corpus sidecars.

This is the single owner for the product-search sidecars derived from
normative HTML and AEAT record-design workbooks.  PDF corpus text has a
different schema and remains owned by :mod:`extract_manual_corpus_text`.

Run ``python -m dev.corpus.extract_corpus_sidecars`` to refresh every
enrolled derivative, or add ``--check`` to report drift without writing.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Final

from cadrumo.core.directory_scan import DirectoryEntryKind, scan_directory
from dev._paths import REPO_ROOT, UTF_8
from dev.docs.preprocess.normatives_html import build_outputs as build_html_outputs
from dev.docs.preprocess.normatives_html import extract_html
from dev.docs.preprocess.parts import part_stand_in_path
from dev.docs.preprocess.schema import PreprocessOutput
from dev.docs.preprocess.sidecar import EXTRACTED_JSON_SUFFIX, EXTRACTED_TEXT_SUFFIX, sidecar_paths_for
from dev.docs.preprocess.workbook import build_outputs as build_workbook_outputs
from dev.docs.preprocess.workbook import extract_workbook

_UTF_8: Final[str] = UTF_8
_REPO_ROOT: Final[Path] = REPO_ROOT
_CORPUS_ROOT: Final[Path] = _REPO_ROOT / "src" / "cadrumo" / "_data" / "corpus"
_WORKBOOK_SUFFIXES: Final[frozenset[str]] = frozenset({".xls", ".xlsm", ".xlsx"})
_OWNED_SOURCE_SUFFIXES: Final[frozenset[str]] = frozenset({".html", *_WORKBOOK_SUFFIXES})
_PART_INFIX: Final[re.Pattern[str]] = re.compile(r"\.part-[^.]*$")


def enrolled_sources(corpus_root: Path = _CORPUS_ROOT) -> list[Path]:
    """Return every authoritative source whose product sidecars this owns."""
    html_root = corpus_root / "normatives" / "html"
    workbook_root = corpus_root / "aeat_official" / "disenos_registro"
    html = scan_directory(html_root, pattern="*.html", recursive=True)
    workbooks = [
        path
        for path in scan_directory(workbook_root, recursive=True, select=DirectoryEntryKind.FILES)
        if path.suffix.lower() in _WORKBOOK_SUFFIXES
    ]
    return sorted([*html, *workbooks], key=lambda path: path.as_posix())


def _build_outputs(source: Path, *, repo_root: Path) -> list[PreprocessOutput]:
    if source.suffix.lower() == ".html":
        return build_html_outputs(source, repo_root=repo_root)
    return build_workbook_outputs(source, repo_root=repo_root)


def _extract(source: Path, *, repo_root: Path) -> list[Path]:
    if source.suffix.lower() == ".html":
        return extract_html(source, repo_root=repo_root)
    return extract_workbook(source, repo_root=repo_root)


def _expected_bytes(source: Path, *, repo_root: Path) -> dict[Path, bytes]:
    """Render the exact pair bytes the production writer would create."""
    expected: dict[Path, bytes] = {}
    outputs = _build_outputs(source, repo_root=repo_root)
    for index, output in enumerate(outputs):
        text_path, json_path = sidecar_paths_for(part_stand_in_path(source, index, len(outputs)))
        expected[text_path] = output.render_text().encode(_UTF_8)
        expected[json_path] = (json.dumps(output.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n").encode(
            _UTF_8,
        )
    return expected


def _owned_sidecar_payload_name(path: Path) -> str | None:
    """Return the source filename for an owned sidecar, else ``None``.

    The record-design root also contains PDF extraction sidecars. They belong
    to the separate PDF producer and must never be reported or removed here.
    Any ``.part-*`` spelling after an owned source suffix is included so that
    malformed multipart derivatives fail the structural check as orphans.
    """
    for suffix in (EXTRACTED_TEXT_SUFFIX, EXTRACTED_JSON_SUFFIX):
        if path.name.endswith(suffix):
            candidate = _PART_INFIX.sub("", path.name.removesuffix(suffix))
            return candidate if Path(candidate).suffix.lower() in _OWNED_SOURCE_SUFFIXES else None
    return None


def _existing_sidecars(corpus_root: Path) -> set[Path]:
    paths: set[Path] = set()
    for root in (corpus_root / "normatives" / "html", corpus_root / "aeat_official" / "disenos_registro"):
        for suffix in (EXTRACTED_TEXT_SUFFIX, EXTRACTED_JSON_SUFFIX):
            paths.update(
                path
                for path in scan_directory(root, pattern=f"*{suffix}", recursive=True)
                if _owned_sidecar_payload_name(path) is not None
            )
    return paths


def _relative(path: Path, repo_root: Path) -> str:
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()


def check_all(*, corpus_root: Path = _CORPUS_ROOT, repo_root: Path = _REPO_ROOT) -> list[str]:
    """Return deterministic failures for missing, stale, and orphaned sidecars."""
    expected: dict[Path, bytes] = {}
    for source in enrolled_sources(corpus_root):
        expected.update(_expected_bytes(source, repo_root=repo_root))

    failures: list[str] = []
    for path in sorted(expected, key=lambda item: item.as_posix()):
        if not path.is_file():
            failures.append(f"MISSING {_relative(path, repo_root)}")
        elif path.read_bytes() != expected[path]:
            failures.append(f"STALE   {_relative(path, repo_root)}")
    for path in sorted(_existing_sidecars(corpus_root) - expected.keys(), key=lambda item: item.as_posix()):
        failures.append(f"ORPHAN  {_relative(path, repo_root)}")
    return failures


def extract_all(*, check: bool = False, corpus_root: Path = _CORPUS_ROOT, repo_root: Path = _REPO_ROOT) -> int:
    """Generate all enrolled derivatives, or no-write check their exact bytes."""
    sources = enrolled_sources(corpus_root)
    if not sources:
        print(f"No enrolled corpus sources found under {corpus_root}", file=sys.stderr)
        return 1
    if check:
        failures = check_all(corpus_root=corpus_root, repo_root=repo_root)
        for failure in failures:
            print(failure)
        if failures:
            print(
                f"\n{len(failures)} corpus sidecar defect(s). Run: python -m dev.corpus.extract_corpus_sidecars",
                file=sys.stderr,
            )
            return len(failures)
        print(f"All {len(sources)} corpus sidecar source(s) are current.")
        return 0

    for source in sources:
        print(f"Extracting {_relative(source, repo_root)} ...")
        _extract(source, repo_root=repo_root)
    orphans = [
        failure for failure in check_all(corpus_root=corpus_root, repo_root=repo_root) if failure.startswith("ORPHAN")
    ]
    for orphan in orphans:
        print(orphan, file=sys.stderr)
    if orphans:
        print(
            f"\n{len(orphans)} orphaned corpus sidecar(s) remain; remove them explicitly before rerunning --check.",
            file=sys.stderr,
        )
        return len(orphans)
    print(f"\n{len(sources)} corpus sidecar source(s) generated.")
    return 0


def main() -> None:
    """Run the corpus-sidecar command-line interface."""
    parser = argparse.ArgumentParser(description="Generate or check enrolled corpus HTML and workbook sidecars.")
    parser.add_argument("--check", action="store_true", help="Report drift without writing any sidecars.")
    args = parser.parse_args()
    sys.exit(extract_all(check=args.check))


if __name__ == "__main__":
    main()
