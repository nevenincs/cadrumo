"""Fixture proofs for derived normative-corpus provenance."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.provenance import NormativeCorpusProvenance
from dev.registry.compiler.corpus_provenance import (
    classify_normative_corpus_provenance,
    resolve_normative_corpus_path,
)
from cadrumo.domain.calculations.registry.errors import RegistryValidationError

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
