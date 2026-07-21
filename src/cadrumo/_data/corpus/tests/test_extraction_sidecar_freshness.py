"""Freshness gate for committed extraction sidecars."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest
from dev.docs.preprocess import (
    EXTRACTED_JSON_SUFFIX,
    EXTRACTED_TEXT_SUFFIX,
    PreprocessOutput,
)
from dev.docs.preprocess._html import HTML_EXTRACTOR_ID, build_outputs

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# src/cadrumo/_data/corpus/tests/test_extraction_sidecar_freshness.py -> parents[5] is repo root.
_REPO_ROOT = Path(__file__).resolve().parents[5]
_CORPUS_ROOT = _REPO_ROOT / "src" / "cadrumo" / "_data" / "corpus"
_MANUAL_CORPUS_TEXT_ROOT = _REPO_ROOT / "src" / "cadrumo" / "_data" / "manual_corpus_text"
_CORPUS_TEXT_SUFFIX = ".corpus_text.json"
_PART_SUFFIX = re.compile(r"\.part-\d+$")
_SUPPORTED_CALENDAR_YEARS = range(2023, 2027)


def _sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _matches_origin_name(sidecar_name: str, origin_name: str) -> bool:
    stand_in_name = sidecar_name.removesuffix(EXTRACTED_JSON_SUFFIX)
    return stand_in_name == origin_name or _PART_SUFFIX.sub("", stand_in_name) == origin_name


def test_normative_html_sources_use_canonical_lf_bytes() -> None:
    """Normative HTML hashes must be identical on Windows and Unix checkouts."""
    html_root = _CORPUS_ROOT / "normatives" / "html"
    sources = sorted(html_root.glob("*.html"))
    noncanonical = [source.name for source in sources if b"\r" in source.read_bytes()]

    assert sources, "no normative HTML sources found"
    assert not noncanonical, f"normative HTML contains non-LF line endings: {noncanonical!r}"


def test_normative_html_sidecars_equal_current_production_extraction() -> None:
    """Committed normative records are exact outputs of the live extractor."""
    html_root = _CORPUS_ROOT / "normatives" / "html"
    sources = sorted(html_root.glob("*.html"))
    failures: list[str] = []

    for source in sources:
        json_paths = sorted(
            path
            for path in html_root.glob(f"{source.name}*{EXTRACTED_JSON_SUFFIX}")
            if _matches_origin_name(path.name, source.name)
        )
        if not json_paths:
            continue
        committed = [PreprocessOutput.model_validate_json(path.read_text(encoding="utf-8")) for path in json_paths]
        expected = build_outputs(source, repo_root=_REPO_ROOT)
        if committed != expected:
            failures.append(source.relative_to(_REPO_ROOT).as_posix())

    assert sources, "no normative HTML sources found"
    assert not failures, f"normative HTML sidecars differ from the production extractor: {failures[:20]!r}"


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
        if origin.suffix == ".html" and output.preprocessor_id != HTML_EXTRACTOR_ID:
            failures.append(
                f"{rel_json}: normative HTML sidecar declares retired or unknown "
                f"preprocessor_id {output.preprocessor_id!r}",
            )
        if not text_path.is_file():
            failures.append(f"{rel_json}: text sidecar is missing: {text_path.relative_to(_REPO_ROOT).as_posix()}")
        elif text_path.read_text(encoding="utf-8") != output.render_text():
            failures.append(f"{rel_json}: text sidecar does not match rendered schema payload")

    assert sidecars, "no committed extraction sidecars found under src/cadrumo/_data/corpus"
    assert not failures, f"{len(failures)} stale or malformed extraction sidecars: {failures[:20]!r}"


def test_manual_pdf_corpus_text_sidecars_exist_and_match_source_sha256() -> None:
    """Every committed manual-PDF corpus text sidecar matches its source PDF bytes.

    Ensures that dev/packaging/extract_manual_corpus_text.py was re-run after
    any corpus PDF changed, so the shipped sidecars are always in sync with
    the source PDFs that _validate_evidence._read_manual_pdf_sidecar reads.
    """
    sidecars = sorted(_MANUAL_CORPUS_TEXT_ROOT.rglob(f"*{_CORPUS_TEXT_SUFFIX}"))
    failures: list[str] = []

    for sidecar_path in sidecars:
        rel_sidecar = sidecar_path.relative_to(_REPO_ROOT).as_posix()
        try:
            data: dict[str, object] = json.loads(sidecar_path.read_text(encoding="utf-8"))
        except Exception as exc:
            failures.append(f"{rel_sidecar}: cannot parse JSON: {exc}")
            continue

        corpus_path = data.get("corpus_path")
        stored_sha256 = data.get("source_sha256")
        normalised_text = data.get("normalised_text")
        schema_version = data.get("schema_version")

        if not isinstance(corpus_path, str) or not corpus_path.startswith("corpus/"):
            failures.append(f"{rel_sidecar}: missing or malformed corpus_path: {corpus_path!r}")
            continue
        if not isinstance(stored_sha256, str) or len(stored_sha256) != 64:
            failures.append(f"{rel_sidecar}: missing or malformed source_sha256")
            continue
        if not isinstance(normalised_text, str):
            failures.append(f"{rel_sidecar}: missing normalised_text field")
            continue
        if schema_version != 1:
            failures.append(f"{rel_sidecar}: unexpected schema_version {schema_version!r}")
            continue

        # Derive the expected source PDF path from corpus_path.
        relative = corpus_path[len("corpus/") :]
        source_path = _CORPUS_ROOT / Path(relative)
        if not source_path.is_file():
            failures.append(f"{rel_sidecar}: source PDF missing: {corpus_path}")
            continue

        actual_sha256 = hashlib.sha256(source_path.read_bytes()).hexdigest()
        if actual_sha256 != stored_sha256:
            failures.append(
                f"{rel_sidecar}: sha256 mismatch for {corpus_path} "
                f"(stored {stored_sha256[:8]}…, actual {actual_sha256[:8]}…) — "
                "run: uv run --no-sync python -m dev.packaging.extract_manual_corpus_text"
            )

    assert sidecars, f"no manual corpus text sidecars found under {_MANUAL_CORPUS_TEXT_ROOT}"
    assert not failures, f"{len(failures)} stale or malformed manual PDF sidecars:\n" + "\n".join(failures[:20])


def test_supported_taxpayer_calendars_ship_pdf_corpus_text() -> None:
    """Every supported campaign year ships its official calendar PDF and text sidecar."""
    calendar_root = _CORPUS_ROOT / "aeat_official" / "calendars" / "files"
    calendar_sidecar_root = _MANUAL_CORPUS_TEXT_ROOT / "aeat_official" / "calendars" / "files"
    missing: list[str] = []

    for year in _SUPPORTED_CALENDAR_YEARS:
        pdf_name = f"calendario-contribuyente-{year}.pdf"
        pdf_path = calendar_root / pdf_name
        sidecar_path = calendar_sidecar_root / f"{pdf_name}{_CORPUS_TEXT_SUFFIX}"
        if not pdf_path.is_file():
            missing.append(pdf_path.relative_to(_REPO_ROOT).as_posix())
        if not sidecar_path.is_file():
            missing.append(sidecar_path.relative_to(_REPO_ROOT).as_posix())
            continue

        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        expected_title = f"calendario del contribuyente {year}"
        if expected_title not in sidecar["normalised_text"]:
            missing.append(f"{sidecar_path.relative_to(_REPO_ROOT).as_posix()}: missing {expected_title!r}")

    assert not missing, "supported taxpayer calendar corpus artifacts are missing:\n" + "\n".join(missing)
