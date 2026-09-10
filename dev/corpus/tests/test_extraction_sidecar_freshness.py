"""Freshness gate for committed extraction sidecars."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Final, cast

import pytest
from cadrumo.domain.calculations.registry.loader import load_shared_catalogues

from cadrumo.core.corpus_text import normalise_corpus_text
from cadrumo.core.directory_scan import scan_directory
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.schema import SociedadesAnnualManualCoverageStatus

from ..extract_corpus_sidecars import check_all as check_corpus_sidecars
from ..extract_manual_corpus_text import extract_raw_text

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# dev/corpus/tests/test_extraction_sidecar_freshness.py -> parents[3] is repo root.
# The depth is stated here because it silently retargets on a move: this file
# was relocated out of src/cadrumo/_data/corpus/tests, where parents[5] was
# right, and the arithmetic then named two directories ABOVE the repository.
_REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(autouse=True)
def _repository_root_resolved() -> None:
    """Fail this module's tests if the depth arithmetic retargeted.

    Checked per test rather than at import. Collection must stay side-effect
    free, and a guard that raises during collection reports a broken module
    rather than a named gate that lost its root, which is harder to act on.
    """
    assert (_REPO_ROOT / "src" / "cadrumo").is_dir(), f"corpus freshness gate lost the repository root: {_REPO_ROOT}"


_CORPUS_ROOT = _REPO_ROOT / "src" / "cadrumo" / "_data" / "corpus"
_MANUAL_CORPUS_TEXT_ROOT = _REPO_ROOT / "src" / "cadrumo" / "_data" / "manual_corpus_text"
_CORPUS_TEXT_SUFFIX = ".corpus_text.json"


def _canonical_supported_filing_years() -> tuple[int, ...]:
    """Return the registry's sole declaration of supported filing years.

    The support horizon is NOT a fact this gate owns.
    ``registry/aeat/legal/supported-filing-years.toml`` is the one registry-wide
    declaration, and it admits a year only after the coverage audit enumerates that
    year's prerequisites. Restating it here as a literal ``range`` is what let the
    corpus matrix drift: each family had grown its own narrower window
    (manuals 2023-2025, Sociedades 2024-2025) that quietly redefined "supported"
    as "whatever happens to be on disk", so a family missing a year the product
    actually supports read as full coverage.
    """
    catalogues = load_shared_catalogues(bundled_path("registry", "aeat"))
    declaration = catalogues.supported_filing_years
    assert declaration is not None, "the bundled registry declares no supported filing years"
    return declaration.years


# (family, path template, substring the extracted text must carry).
_MANUAL_FAMILIES: Final[tuple[tuple[str, str, str], ...]] = (
    ("iva", "manuals/iva/{year}/source.pdf", "iva"),
    ("renta-part1", "manuals/renta/{year}/part1/source.pdf", "renta"),
    (
        "renta-part2-deducciones-autonomicas",
        "manuals/renta/{year}/part2-deducciones-autonomicas/source.pdf",
        "renta",
    ),
    ("sociedades", "manuals/sociedades/{year}/source.pdf", "sociedades"),
)

# AEAT has not published these volumes yet, so their absence is lawful.
_PUBLICATION_BOUND_MANUAL_GAPS: Final[frozenset[tuple[str, int]]] = frozenset(
    {
        ("iva", 2026),
        ("renta-part1", 2026),
        ("renta-part2-deducciones-autonomicas", 2026),
    },
)

# Published by AEAT, inside the canonical support horizon, and NOT in the corpus.
# These are real coverage holes rather than lawful absences. They are named here so
# binding the matrix to the registry horizon does not silently narrow itself back to
# the on-disk inventory; each entry is a standing acquisition debt, and the staleness
# check below turns it red the moment the volume lands.
_UNACQUIRED_MANUAL_GAPS: Final[frozenset[tuple[str, int]]] = frozenset(
    {
        ("renta-part2-deducciones-autonomicas", 2022),
        ("renta-part2-deducciones-autonomicas", 2023),
    },
)


def _sociedades_annual_manual_statuses() -> dict[int, SociedadesAnnualManualCoverageStatus]:
    """Return Sociedades availability from the registry coverage contract.

    The corpus gate must not carry an independent exception list for this
    annual family.  The registry catalogue is the authoritative statement of
    whether a supported year is locally available, still unacquired, or not
    yet published; this physical-artifact gate verifies that the declared
    outcome matches the shipped PDF and runtime text sidecar.
    """
    catalogues = load_shared_catalogues(bundled_path("registry", "aeat"))
    coverage = catalogues.sociedades_annual_manual_coverage
    assert coverage is not None, "the registry declares no Sociedades annual-manual coverage catalogue"
    statuses = {disposition.year: disposition.status for disposition in coverage.dispositions}
    assert tuple(statuses) == catalogues.supported_filing_years.years, (
        "Sociedades annual-manual coverage must declare every supported filing year"
    )
    return statuses


def test_enrolled_corpus_html_trees_use_canonical_lf_bytes() -> None:
    """Enrolled HTML trees must hash identically on Windows and Unix checkouts.

    A CR in a hash-pinned corpus file makes its ``sha256`` depend on how the
    checkout materialised the bytes, so the registry pin stops being a
    platform-independent integrity claim. That is why this gate exists.

    ``aeat_official/calendars`` is enrolled because a CRLF file did slip into it
    (``calendario-contribuyente-2026-hasta-2-febrero.html``) while three siblings
    were LF, leaving one directory with two byte conventions and pins that could
    not be reproduced by the same command.

    The remaining ``aeat_official`` HTML trees are deliberately NOT enrolled yet:
    36 files under ``instructions/`` and ``renta_web_open/`` still carry CR, so
    enrolling them here would land this gate red on material this tree does not
    own. Add a tree to the tuple in the same change that canonicalises it and
    re-pins its sources -- never before.
    """
    enrolled = (Path("normatives") / "html", Path("aeat_official") / "calendars")
    noncanonical: list[str] = []
    scanned = 0

    for relative_tree in enrolled:
        tree = _CORPUS_ROOT / relative_tree
        assert tree.is_dir(), f"enrolled canonical-LF tree is missing: {relative_tree.as_posix()}"
        sources = scan_directory(tree, pattern="*.html", recursive=True)
        assert sources, f"no HTML sources found under enrolled tree {relative_tree.as_posix()}"
        scanned += len(sources)
        noncanonical.extend(
            source.relative_to(_CORPUS_ROOT).as_posix() for source in sources if b"\r" in source.read_bytes()
        )

    assert scanned, "canonical-LF gate scanned no HTML at all"
    assert not noncanonical, f"enrolled corpus HTML contains non-LF line endings: {sorted(noncanonical)!r}"


def test_enrolled_html_and_workbook_sidecars_match_the_owner_check() -> None:
    """The producer-owned check proves complete enrolled derivative parity."""
    failures = check_corpus_sidecars()
    assert not failures, "enrolled corpus sidecar defects:\n" + "\n".join(failures)


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
            data = cast(
                "dict[str, object]",
                json.loads(sidecar_path.read_text(encoding="utf-8")),
            )
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


def test_supported_taxpayer_calendars_ship_pdf_corpus_text() -> None:
    """Every supported campaign year ships its official calendar PDF and text sidecar."""
    calendar_root = _CORPUS_ROOT / "aeat_official" / "calendars" / "files"
    calendar_sidecar_root = _MANUAL_CORPUS_TEXT_ROOT / "aeat_official" / "calendars" / "files"
    missing: list[str] = []

    for year in _canonical_supported_filing_years():
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
    """Every manual family covers the canonical horizon, or declares the hole.

    Sociedades dispositions come from the typed registry catalogue, while the
    other manual families retain their independent publication/acquisition
    debt declarations until each has an equivalent catalogue.
    """
    supported_years = _canonical_supported_filing_years()
    declared_gaps = _PUBLICATION_BOUND_MANUAL_GAPS | _UNACQUIRED_MANUAL_GAPS
    known_families = {family for family, _template, _token in _MANUAL_FAMILIES}
    sociedades_statuses = _sociedades_annual_manual_statuses()

    missing: list[str] = []
    stale: list[str] = []

    for family, template, token in _MANUAL_FAMILIES:
        for year in supported_years:
            relative_pdf = Path(template.format(year=year))
            pdf_path = _CORPUS_ROOT / relative_pdf
            sidecar_path = (_MANUAL_CORPUS_TEXT_ROOT / relative_pdf).with_name(
                pdf_path.name + _CORPUS_TEXT_SUFFIX,
            )

            sociedades_gap = family == "sociedades" and sociedades_statuses[year] in {
                SociedadesAnnualManualCoverageStatus.UNACQUIRED,
                SociedadesAnnualManualCoverageStatus.UNPUBLISHED,
            }
            if sociedades_gap or (family, year) in declared_gaps:
                if pdf_path.exists() or sidecar_path.exists():
                    if family == "sociedades":
                        stale.append(
                            f"{family} {year}: local artefacts contradict its "
                            f"{sociedades_statuses[year].value!r} coverage disposition",
                        )
                    else:
                        stale.append(f"{family} {year}: volume has landed -- remove its declared gap entry")
                continue

            if not pdf_path.is_file():
                missing.append(pdf_path.relative_to(_REPO_ROOT).as_posix())
            if not sidecar_path.is_file():
                missing.append(sidecar_path.relative_to(_REPO_ROOT).as_posix())
                continue
            normalised_text = json.loads(sidecar_path.read_text(encoding="utf-8"))["normalised_text"]
            if token not in normalised_text or str(year) not in normalised_text:
                missing.append(
                    f"{sidecar_path.relative_to(_REPO_ROOT).as_posix()}: missing {token!r} or {year}",
                )

    # A gap may only be declared against a coordinate the matrix actually spans,
    # so a gap entry cannot be used to excuse a family or year off the horizon.
    orphaned = sorted(
        f"{family} {year}"
        for family, year in declared_gaps
        if family not in known_families or year not in supported_years
    )

    assert not orphaned, "declared manual gaps outside the canonical matrix:\n" + "\n".join(orphaned)
    assert not stale, "declared manual gaps that are no longer gaps:\n" + "\n".join(stale)
    assert not missing, "supported tax-manual corpus artifacts are missing:\n" + "\n".join(missing)
