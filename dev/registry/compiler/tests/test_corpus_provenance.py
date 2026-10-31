"""Fixture proofs for derived normative-corpus provenance."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.provenance import NormativeCorpusProvenance

from .. import corpus_provenance
from ..corpus_provenance import (
    classify_normative_corpus_provenance,
    corpus_digest_pass,
    resolve_normative_corpus_path,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _write_corpus_fixture(tmp_path: Path, name: str, payload: str) -> Path:
    path = tmp_path / "corpus" / "normatives" / "html" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8", newline="\n")
    return path


@pytest.mark.parametrize(
    ("payload", "case_id"),
    [
        pytest.param("<!-- Official BOE consolidated source excerpt -->", "excerpt-header"),
        pytest.param("<p>Document: BOE-A-2024-1526</p>", "boe-document-identifier"),
    ],
)
def test_attested_normative_text_is_classified_from_its_own_bytes(
    tmp_path: Path,
    payload: str,
    case_id: str,
) -> None:
    del case_id  # pytest's id is descriptive; the payload is the test input.
    _write_corpus_fixture(tmp_path, "attested.html", payload)

    assert (
        classify_normative_corpus_provenance(
            tmp_path,
            "corpus/normatives/html/attested.html#a1",
        )
        is NormativeCorpusProvenance.BOE_ATTESTED
    )


def test_boe_structural_markup_without_attribution_is_presumptive(tmp_path: Path) -> None:
    _write_corpus_fixture(
        tmp_path,
        "markup-only.html",
        '<h5 class="articulo">Artículo 1.</h5><p class="parrafo">Texto.</p>',
    )

    assert (
        classify_normative_corpus_provenance(
            tmp_path,
            "corpus/normatives/html/markup-only.html",
        )
        is NormativeCorpusProvenance.BOE_PRESUMPTIVE
    )


def test_text_without_boe_attribution_or_structure_is_authored(tmp_path: Path) -> None:
    _write_corpus_fixture(tmp_path, "authored.html", "<p>Texto redactado sin atribución.</p>")

    assert (
        classify_normative_corpus_provenance(
            tmp_path,
            "corpus/normatives/html/authored.html",
        )
        is NormativeCorpusProvenance.AUTHORED
    )


def test_non_normative_target_is_out_of_scope_and_never_read(
    tmp_path: Path,
) -> None:
    outside = tmp_path / "corpus" / "aeat_official" / "manual.html"
    outside.parent.mkdir(parents=True)
    outside.write_text("BOE-A-2024-1526", encoding="utf-8")

    assert resolve_normative_corpus_path(tmp_path, "corpus/aeat_official/manual.html") is None
    assert (
        classify_normative_corpus_provenance(
            tmp_path,
            "corpus/aeat_official/manual.html",
        )
        is NormativeCorpusProvenance.OUT_OF_SCOPE
    )


def test_packaged_data_target_is_resolved_when_source_root_is_repository(tmp_path: Path) -> None:
    packaged = tmp_path / "src" / "cadrumo" / "_data" / "corpus" / "normatives" / "html"
    packaged.mkdir(parents=True)
    (packaged / "attested.html").write_text(
        "<!-- Official BOE consolidated source excerpt -->",
        encoding="utf-8",
    )

    assert (
        classify_normative_corpus_provenance(
            tmp_path,
            "corpus/normatives/html/attested.html",
        )
        is NormativeCorpusProvenance.BOE_ATTESTED
    )


@pytest.mark.parametrize(
    "corpus_ref",
    [
        "corpus/normatives/../../outside.html",
        "corpus/normatives/html/missing.html",
    ],
)
def test_invalid_normative_target_is_rejected(tmp_path: Path, corpus_ref: str) -> None:
    with pytest.raises(RegistryValidationError):
        resolve_normative_corpus_path(tmp_path, corpus_ref)


def test_symlinked_normative_target_outside_tree_is_rejected(tmp_path: Path) -> None:
    outside = tmp_path / "outside.html"
    outside.write_text("<!-- Official BOE consolidated source excerpt -->", encoding="utf-8")
    link = tmp_path / "corpus" / "normatives" / "html" / "escape.html"
    link.parent.mkdir(parents=True)
    try:
        link.symlink_to(outside)
    except OSError as error:
        pytest.skip(f"symlinks are unavailable in this test environment: {error}")

    with pytest.raises(RegistryValidationError):
        resolve_normative_corpus_path(tmp_path, "corpus/normatives/html/escape.html")


def test_symlinked_normatives_directory_outside_source_root_is_rejected(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-normatives"
    (outside / "html").mkdir(parents=True)
    (outside / "html" / "attested.html").write_text(
        "<!-- Official BOE consolidated source excerpt -->",
        encoding="utf-8",
    )
    normatives = tmp_path / "corpus" / "normatives"
    normatives.parent.mkdir(parents=True)
    try:
        normatives.symlink_to(outside, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"symlinks are unavailable in this test environment: {error}")

    with pytest.raises(RegistryValidationError):
        resolve_normative_corpus_path(tmp_path, "corpus/normatives/html/attested.html")


def test_symlinked_packaged_data_directory_outside_source_root_is_rejected(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-packaged-data"
    (outside / "corpus" / "normatives" / "html").mkdir(parents=True)
    (outside / "corpus" / "normatives" / "html" / "attested.html").write_text(
        "<!-- Official BOE consolidated source excerpt -->",
        encoding="utf-8",
    )
    packaged_data = tmp_path / "src" / "cadrumo" / "_data"
    packaged_data.parent.mkdir(parents=True)
    try:
        packaged_data.symlink_to(outside, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"symlinks are unavailable in this test environment: {error}")

    with pytest.raises(RegistryValidationError):
        resolve_normative_corpus_path(tmp_path, "corpus/normatives/html/attested.html")


def test_normatives_directory_symlinked_to_source_root_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "attested.html").write_text(
        "<!-- Official BOE consolidated source excerpt -->",
        encoding="utf-8",
    )
    normatives = tmp_path / "corpus" / "normatives"
    normatives.parent.mkdir(parents=True)
    try:
        normatives.symlink_to(tmp_path, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"symlinks are unavailable in this test environment: {error}")

    with pytest.raises(RegistryValidationError):
        resolve_normative_corpus_path(tmp_path, "corpus/normatives/attested.html")


def test_packaged_normatives_directory_symlinked_to_data_root_is_rejected(tmp_path: Path) -> None:
    data_root = tmp_path / "src" / "cadrumo" / "_data"
    data_root.mkdir(parents=True)
    (data_root / "attested.html").write_text(
        "<!-- Official BOE consolidated source excerpt -->",
        encoding="utf-8",
    )
    normatives = data_root / "corpus" / "normatives"
    normatives.parent.mkdir(parents=True)
    try:
        normatives.symlink_to(data_root, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"symlinks are unavailable in this test environment: {error}")

    with pytest.raises(RegistryValidationError):
        resolve_normative_corpus_path(tmp_path, "corpus/normatives/attested.html")


def _count_reads(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    reads: list[Path] = []
    original = Path.read_bytes

    def counting_read_bytes(path: Path) -> bytes:
        reads.append(path)
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", counting_read_bytes)
    return reads


def test_one_file_cited_at_several_anchors_is_classified_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """References sharing a file share one read and one classification within a pass.

    Provenance is decided by the file's bytes but asked per REFERENCE, and the
    corpus is cited at many anchors per file. Re-reading per reference made one
    validation pass scan 415 MB of a 36.8 MB corpus.
    """
    path = _write_corpus_fixture(tmp_path, "ley.html", "<!-- Official BOE consolidated source excerpt -->")
    corpus_provenance._PROVENANCE_BY_CONTENT.clear()
    reads = _count_reads(monkeypatch)

    with corpus_digest_pass():
        verdicts = {
            classify_normative_corpus_provenance(tmp_path, f"corpus/normatives/html/ley.html#{anchor}")
            for anchor in ("art-1", "art-2", "art-3")
        }

    assert verdicts == {NormativeCorpusProvenance.BOE_ATTESTED}
    assert reads.count(path) == 2, "one digest read and one classifying read, however many anchors cite it"


def test_a_stat_preserving_rewrite_is_reclassified(tmp_path: Path) -> None:
    """The verdict is keyed on content, so a rewrite that forges size and mtime is not served stale."""
    path = _write_corpus_fixture(tmp_path, "ley.html", "<!-- Official BOE consolidated source excerpt -->")
    corpus_provenance._PROVENANCE_BY_CONTENT.clear()
    ref = "corpus/normatives/html/ley.html#art-1"
    original = path.stat()

    assert classify_normative_corpus_provenance(tmp_path, ref) is NormativeCorpusProvenance.BOE_ATTESTED

    path.write_bytes(b"<p>hand written summary</p>".ljust(original.st_size, b" "))
    os.utime(path, ns=(original.st_atime_ns, original.st_mtime_ns))
    forged = path.stat()
    assert (forged.st_size, forged.st_mtime_ns) == (original.st_size, original.st_mtime_ns)

    assert classify_normative_corpus_provenance(tmp_path, ref) is NormativeCorpusProvenance.AUTHORED


def test_an_out_of_scope_reference_reads_nothing(tmp_path: Path) -> None:
    """A path outside the normative tree is classified without reading any file."""
    corpus_provenance._PROVENANCE_BY_CONTENT.clear()

    assert (
        classify_normative_corpus_provenance(tmp_path, "corpus/manuals/renta/2025/part1/source.pdf")
        is NormativeCorpusProvenance.OUT_OF_SCOPE
    )
    assert not corpus_provenance._PROVENANCE_BY_CONTENT
