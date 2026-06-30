"""Freshness gate for committed extraction sidecars."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest
from dev.docs.preprocess import (
    EXTRACTED_JSON_SUFFIX,
    EXTRACTED_TEXT_SUFFIX,
    PreprocessOutput,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

# src/aeat/_data/corpus/tests/test_extraction_sidecar_freshness.py -> parents[5] is repo root.
_REPO_ROOT = Path(__file__).resolve().parents[5]
_CORPUS_ROOT = _REPO_ROOT / "src" / "aeat" / "_data" / "corpus"
_PART_SUFFIX = re.compile(r"\.part-\d+$")


def _sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _matches_origin_name(sidecar_name: str, origin_name: str) -> bool:
    stand_in_name = sidecar_name.removesuffix(EXTRACTED_JSON_SUFFIX)
    return stand_in_name == origin_name or _PART_SUFFIX.sub("", stand_in_name) == origin_name


def test_committed_extraction_sidecars_match_current_sources() -> None:
    """Every committed extraction sidecar still matches its source bytes."""
    failures: list[str] = []
    sidecars = sorted(_CORPUS_ROOT.rglob(f"*{EXTRACTED_JSON_SUFFIX}"))

    for json_path in sidecars:
        rel_json = json_path.relative_to(_REPO_ROOT).as_posix()
        output = PreprocessOutput.model_validate_json(json_path.read_text(encoding="utf-8"))
        origin = (_REPO_ROOT / output.source_relpath).resolve()
        rel_origin = output.source_relpath
        text_path = json_path.with_name(json_path.name.removesuffix(EXTRACTED_JSON_SUFFIX) + EXTRACTED_TEXT_SUFFIX)

        if output.source_relpath != Path(output.source_relpath).as_posix():
            failures.append(f"{rel_json}: source_relpath is not POSIX: {output.source_relpath!r}")
        if not origin.is_file():
            failures.append(f"{rel_json}: declared source is missing: {rel_origin}")
            continue
        if not origin.is_relative_to(_CORPUS_ROOT):
            failures.append(f"{rel_json}: declared source escapes corpus root: {rel_origin}")
        if json_path.parent != origin.parent or not _matches_origin_name(json_path.name, origin.name):
            failures.append(f"{rel_json}: sidecar is not paired with declared sibling source {rel_origin}")
        if output.source_sha256 != _sha256_of(origin):
            failures.append(f"{rel_json}: source_sha256 does not match current source bytes for {rel_origin}")
        if not text_path.is_file():
            failures.append(f"{rel_json}: text sidecar is missing: {text_path.relative_to(_REPO_ROOT).as_posix()}")
        elif text_path.read_text(encoding="utf-8") != output.render_text():
            failures.append(f"{rel_json}: text sidecar does not match rendered schema payload")

    assert sidecars, "no committed extraction sidecars found under src/aeat/_data/corpus"
    assert not failures, f"{len(failures)} stale or malformed extraction sidecars: {failures[:20]!r}"
