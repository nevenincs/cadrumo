"""Freshness gate for committed extraction sidecars."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import pytest

from cadrumo.core.corpus_text import normalise_corpus_text
from cadrumo.core.directory_scan import DirectoryEntryKind, scan_directory

from ...docs.preprocess import (
    EXTRACTED_JSON_SUFFIX,
    EXTRACTED_TEXT_SUFFIX,
    PreprocessOutput,
)
from ...docs.preprocess._html import HTML_EXTRACTOR_ID, build_outputs
from ..extract_manual_corpus_text import extract_raw_text

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# src/cadrumo/_data/corpus/tests/test_extraction_sidecar_freshness.py -> parents[5] is repo root.
_REPO_ROOT = Path(__file__).resolve().parents[5]
_CORPUS_ROOT = _REPO_ROOT / "src" / "cadrumo" / "_data" / "corpus"
_MANUAL_CORPUS_TEXT_ROOT = _REPO_ROOT / "src" / "cadrumo" / "_data" / "manual_corpus_text"
_CORPUS_TEXT_SUFFIX = ".corpus_text.json"
_PART_SUFFIX = re.compile(r"\.part-\d+$")
_SUPPORTED_CALENDAR_YEARS = range(2023, 2027)
_SUPPORTED_MANUAL_YEARS = range(2023, 2026)
_SUPPORTED_RENTA_PART2_YEARS = range(2024, 2026)
_SUPPORTED_SOCIETIES_MANUAL_YEARS = range(2024, 2026)
_PUBLICATION_BOUND_MANUAL_EXCEPTIONS = (
    ("iva", 2026, Path("manuals/iva/2026/source.pdf")),
    ("renta-part1", 2026, Path("manuals/renta/2026/part1/source.pdf")),
    (
        "renta-part2-deducciones-autonomicas",
        2026,
        Path("manuals/renta/2026/part2-deducciones-autonomicas/source.pdf"),
    ),
    (
        "sociedades",
        2026,
        Path("aeat_official/manuals/modelo_200/files/manual-sociedades-2026.pdf"),
    ),
)


def _sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _matches_origin_name(sidecar_name: str, origin_name: str) -> bool:
    stand_in_name = sidecar_name.removesuffix(EXTRACTED_JSON_SUFFIX)
    return stand_in_name == origin_name or _PART_SUFFIX.sub("", stand_in_name) == origin_name


def _is_legal_citation_evidence_sidecar(json_path: Path) -> bool:
    """A doubly-suffixed sidecar (``*.extracted.md.extracted.json``) is legal-citation evidence.

    ``verify_legal_reference`` resolves a ``corpus_ref`` whose path already ends in
    ``.extracted.md`` (a rendered corpus-text file, not an original source document)
    by appending ``.extracted.json`` to it (``_legal_corpus_text`` in
    ``domain.calculations.registry._legal``). The result is a small, hand-curated
    sidecar carrying only the anchored ``units`` a specific legal reference cites —
    consumed exclusively by ``resolve_anchored_extracted_unit``, which reads
    ``units`` directly and neither requires nor validates against the full
    ``PreprocessOutput`` schema. It is a distinct, narrower contract from the
    source-file sidecars this test polices, not drift from either.
    """
    return json_path.name.removesuffix(EXTRACTED_JSON_SUFFIX).endswith(EXTRACTED_TEXT_SUFFIX)


def test_normative_html_sources_use_canonical_lf_bytes() -> None:
    """Normative HTML hashes must be identical on Windows and Unix checkouts."""
    html_root = _CORPUS_ROOT / "normatives" / "html"
    sources = scan_directory(html_root, pattern="*.html")
    noncanonical = [source.name for source in sources if b"\r" in source.read_bytes()]

    assert sources, "no normative HTML sources found"
    assert not noncanonical, f"normative HTML contains non-LF line endings: {noncanonical!r}"


def test_normative_html_sidecars_equal_current_production_extraction() -> None:
    """Committed normative records are exact outputs of the live extractor."""
    html_root = _CORPUS_ROOT / "normatives" / "html"
    sources = scan_directory(html_root, pattern="*.html")
    failures: list[str] = []

    for source in sources:
        json_paths = [
            path
            for path in scan_directory(html_root, pattern=f"{source.name}*{EXTRACTED_JSON_SUFFIX}")
            if _matches_origin_name(path.name, source.name)
        ]
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
    sidecars = scan_directory(_CORPUS_ROOT, pattern=f"*{EXTRACTED_JSON_SUFFIX}", recursive=True)

    for json_path in sidecars:
        if _is_legal_citation_evidence_sidecar(json_path):
            continue
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
        if not output.units or any(not unit.text.strip() for unit in output.units):
            failures.append(f"{rel_json}: extraction contains no units or an empty unit")
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

    Ensures that dev/corpus/extract_manual_corpus_text.py was re-run after
    any corpus PDF changed, so the shipped sidecars are always in sync with
    the source PDFs that _validate_evidence._read_manual_pdf_sidecar reads.
    """
    sidecars = scan_directory(_MANUAL_CORPUS_TEXT_ROOT, pattern=f"*{_CORPUS_TEXT_SUFFIX}", recursive=True)
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
        extraction_platform = data.get("extraction_platform")

        if not isinstance(corpus_path, str) or not corpus_path.startswith("corpus/"):
            failures.append(f"{rel_sidecar}: missing or malformed corpus_path: {corpus_path!r}")
            continue
        if not isinstance(stored_sha256, str) or len(stored_sha256) != 64:
            failures.append(f"{rel_sidecar}: missing or malformed source_sha256")
            continue
        if not isinstance(normalised_text, str):
            failures.append(f"{rel_sidecar}: missing normalised_text field")
            continue
        if not normalised_text.strip():
            failures.append(f"{rel_sidecar}: normalised_text is empty")
            continue
        if schema_version != 2:
            failures.append(f"{rel_sidecar}: unexpected schema_version {schema_version!r}")
            continue
        if not isinstance(extraction_platform, str) or not extraction_platform:
            failures.append(f"{rel_sidecar}: missing or malformed extraction_platform")
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
                "run: uv run --no-sync python -m dev.corpus.extract_manual_corpus_text"
            )

    assert sidecars, f"no manual corpus text sidecars found under {_MANUAL_CORPUS_TEXT_ROOT}"
    assert not failures, f"{len(failures)} stale or malformed manual PDF sidecars:\n" + "\n".join(failures[:20])


def test_every_corpus_pdf_has_a_corpus_text_sidecar() -> None:
    """Every bundled PDF is represented in the shipped searchable text corpus."""
    pdfs = scan_directory(_CORPUS_ROOT, pattern="*.pdf", recursive=True)
    missing: list[str] = []

    for pdf_path in pdfs:
        relative_pdf = pdf_path.relative_to(_CORPUS_ROOT)
        sidecar_path = (_MANUAL_CORPUS_TEXT_ROOT / relative_pdf).with_name(pdf_path.name + _CORPUS_TEXT_SUFFIX)
        if not sidecar_path.is_file():
            missing.append(sidecar_path.relative_to(_REPO_ROOT).as_posix())

    assert pdfs, f"no corpus PDFs found under {_CORPUS_ROOT}"
    assert not missing, "corpus PDFs without searchable text sidecars:\n" + "\n".join(missing)


def test_pdf_corpus_text_sidecars_equal_current_production_extraction() -> None:
    """Committed sidecar text is an exact output of the live extractor.

    pypdfium2 bundles a per-OS native pdfium binary whose text extraction
    differs subtly across platforms, so exact byte-equality of a re-extraction
    only holds on the platform that generated the sidecar (its stamped
    ``extraction_platform``).  On any other platform this test still enforces
    the platform-independent staleness guard — the stored ``source_sha256``
    must match the current PDF bytes, so a changed PDF with an un-regenerated
    sidecar fails on every platform — plus non-empty text; only the
    platform-variant exact re-extraction comparison is scoped to the
    generation platform.  Runtime (``_read_manual_pdf_sidecar``) reads the
    committed text directly on every platform, so cross-platform extraction
    variance never reaches the product.
    """
    failures: list[str] = []
    sidecars = scan_directory(_MANUAL_CORPUS_TEXT_ROOT, pattern=f"*{_CORPUS_TEXT_SUFFIX}", recursive=True)

    for sidecar_path in sidecars:
        rel_sidecar = sidecar_path.relative_to(_REPO_ROOT).as_posix()
        data = json.loads(sidecar_path.read_text(encoding="utf-8"))
        corpus_path = data["corpus_path"]
        source_path = _CORPUS_ROOT / Path(corpus_path.removeprefix("corpus/"))
        extraction_platform = data.get("extraction_platform")
        if not isinstance(extraction_platform, str) or not extraction_platform:
            failures.append(f"{rel_sidecar}: missing extraction_platform stamp — regenerate the sidecar")
            continue

        # Platform-independent staleness guard: the sidecar is keyed by the
        # source PDF's bytes; a changed PDF must fail on EVERY platform.
        actual_sha256 = hashlib.sha256(source_path.read_bytes()).hexdigest()
        if data["source_sha256"] != actual_sha256:
            failures.append(f"{rel_sidecar}: source_sha256 does not match current PDF bytes for {corpus_path}")
            continue
        normalised_text = data["normalised_text"]
        if not isinstance(normalised_text, str) or not normalised_text.strip():
            failures.append(f"{rel_sidecar}: normalised_text is empty or malformed")
            continue

        if sys.platform != extraction_platform:
            # Exact re-extraction equality is platform-variant (native pdfium
            # differences); it is enforced on the generation platform only.
            continue

        expected = normalise_corpus_text(extract_raw_text(source_path))
        if normalised_text != expected:
            failures.append(rel_sidecar)

    assert sidecars
    assert not failures, "PDF corpus text differs from production extraction:\n" + "\n".join(failures)


def test_every_record_design_workbook_has_extraction_sidecars() -> None:
    workbook_suffixes = {".xls", ".xlsm", ".xlsx"}
    missing: list[str] = []
    workbook_root = _CORPUS_ROOT / "aeat_official" / "disenos_registro"

    for source in scan_directory(workbook_root, recursive=True, select=DirectoryEntryKind.FILES):
        if source.suffix.lower() not in workbook_suffixes:
            continue
        json_sidecars = scan_directory(source.parent, pattern=f"{source.name}*.extracted.json")
        if not json_sidecars or any(not path.with_suffix(".md").is_file() for path in json_sidecars):
            missing.append(source.relative_to(_REPO_ROOT).as_posix())

    assert not missing, "record-design workbooks without extraction sidecars:\n" + "\n".join(missing)


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


def test_supported_tax_manual_matrix_ships_pdf_corpus_text() -> None:
    expected: list[tuple[str, int, Path]] = []
    for year in _SUPPORTED_MANUAL_YEARS:
        expected.extend(
            (
                ("iva", year, Path("manuals") / "iva" / str(year) / "source.pdf"),
                ("renta", year, Path("manuals") / "renta" / str(year) / "part1" / "source.pdf"),
            ),
        )
    expected.extend(
        (
            "renta",
            year,
            Path("manuals") / "renta" / str(year) / "part2-deducciones-autonomicas" / "source.pdf",
        )
        for year in _SUPPORTED_RENTA_PART2_YEARS
    )
    expected.extend(
        (
            "sociedades",
            year,
            Path("aeat_official") / "manuals" / "modelo_200" / "files" / f"manual-sociedades-{year}.pdf",
        )
        for year in _SUPPORTED_SOCIETIES_MANUAL_YEARS
    )

    missing: list[str] = []
    for family, year, relative_pdf in expected:
        pdf_path = _CORPUS_ROOT / relative_pdf
        sidecar_path = (_MANUAL_CORPUS_TEXT_ROOT / relative_pdf).with_name(pdf_path.name + _CORPUS_TEXT_SUFFIX)
        if not pdf_path.is_file():
            missing.append(pdf_path.relative_to(_REPO_ROOT).as_posix())
        if not sidecar_path.is_file():
            missing.append(sidecar_path.relative_to(_REPO_ROOT).as_posix())
            continue
        normalised_text = json.loads(sidecar_path.read_text(encoding="utf-8"))["normalised_text"]
        if family not in normalised_text or str(year) not in normalised_text:
            missing.append(
                f"{sidecar_path.relative_to(_REPO_ROOT).as_posix()}: missing {family!r} or {year}",
            )

    for family, year, relative_pdf in _PUBLICATION_BOUND_MANUAL_EXCEPTIONS:
        pdf_path = _CORPUS_ROOT / relative_pdf
        sidecar_path = (_MANUAL_CORPUS_TEXT_ROOT / relative_pdf).with_name(pdf_path.name + _CORPUS_TEXT_SUFFIX)
        if pdf_path.exists() or sidecar_path.exists():
            missing.append(f"remove stale {family} {year} publication exception")

    assert not missing, "supported tax-manual corpus artifacts are missing:\n" + "\n".join(missing)
