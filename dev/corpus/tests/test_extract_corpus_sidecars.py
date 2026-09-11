"""Contract tests for the enrolled product corpus-sidecar owner."""

from __future__ import annotations

from pathlib import Path

import pytest
from openpyxl import Workbook

from dev.docs.preprocess.sidecar import EXTRACTED_JSON_SUFFIX, EXTRACTED_TEXT_SUFFIX

from ..extract_corpus_sidecars import check_all, enrolled_sources, extract_all

pytestmark = [pytest.mark.unit, pytest.mark.docs, pytest.mark.hex_core]


def _fixture_corpus(tmp_path: Path) -> tuple[Path, Path]:
    """Create the smallest real HTML/workbook enrolled corpus."""
    corpus = tmp_path / "corpus"
    html = corpus / "normatives" / "html" / "norma.html"
    html.parent.mkdir(parents=True)
    html.write_text(
        '<div id="textoxslt"><h5 class="articulo">Artículo 1.</h5><p>Texto legal.</p></div>',
        encoding="utf-8",
        newline="\n",
    )
    workbook_path = corpus / "aeat_official" / "disenos_registro" / "modelo.xlsx"
    workbook_path.parent.mkdir(parents=True)
    workbook = Workbook()
    workbook.active.title = "Datos"
    workbook.active.append(["Campo", "Descripción"])
    workbook.active.append(["01", "Importe"])
    workbook.save(workbook_path)
    return corpus, tmp_path


def _generated_fixture(tmp_path: Path) -> tuple[Path, Path]:
    corpus, repo_root = _fixture_corpus(tmp_path)
    assert extract_all(corpus_root=corpus, repo_root=repo_root) == 0
    return corpus, repo_root


def test_generation_is_source_derived_deterministic_and_check_is_clean(tmp_path: Path) -> None:
    corpus, repo_root = _fixture_corpus(tmp_path)

    sources = enrolled_sources(corpus)
    assert [source.relative_to(corpus).as_posix() for source in sources] == [
        "aeat_official/disenos_registro/modelo.xlsx",
        "normatives/html/norma.html",
    ]
    assert extract_all(corpus_root=corpus, repo_root=repo_root) == 0
    first = {path.relative_to(corpus).as_posix(): path.read_bytes() for path in corpus.rglob("*.extracted.*")}
    assert extract_all(corpus_root=corpus, repo_root=repo_root) == 0
    second = {path.relative_to(corpus).as_posix(): path.read_bytes() for path in corpus.rglob("*.extracted.*")}

    assert first == second
    assert check_all(corpus_root=corpus, repo_root=repo_root) == []
    assert extract_all(check=True, corpus_root=corpus, repo_root=repo_root) == 0


def test_check_is_no_write_and_detects_stale_and_absent_pairs(tmp_path: Path) -> None:
    corpus, repo_root = _generated_fixture(tmp_path)
    html = corpus / "normatives" / "html" / "norma.html"
    text = html.with_name(html.name + EXTRACTED_TEXT_SUFFIX)
    json_path = html.with_name(html.name + EXTRACTED_JSON_SUFFIX)
    before = {path: path.read_bytes() for path in corpus.rglob("*.extracted.*")}

    text.write_text("tampered\n", encoding="utf-8", newline="\n")
    json_path.unlink()
    failures = check_all(corpus_root=corpus, repo_root=repo_root)

    assert f"STALE   {text.relative_to(repo_root).as_posix()}" in failures
    assert f"MISSING {json_path.relative_to(repo_root).as_posix()}" in failures
    assert extract_all(check=True, corpus_root=corpus, repo_root=repo_root) == 2
    assert not json_path.exists(), "--check must not recreate an absent sidecar"
    assert text.read_text(encoding="utf-8") == "tampered\n", "--check must not repair stale output"
    assert before[text] != text.read_bytes()


def test_check_detects_orphan_and_unexpected_multipart_sidecars(tmp_path: Path) -> None:
    corpus, repo_root = _generated_fixture(tmp_path)
    html = corpus / "normatives" / "html" / "norma.html"
    orphan = html.parent / f"deleted.html{EXTRACTED_JSON_SUFFIX}"
    unexpected_part = html.parent / f"{html.name}.part-2{EXTRACTED_TEXT_SUFFIX}"
    malformed_part = html.parent / f"{html.name}.part-x{EXTRACTED_TEXT_SUFFIX}"
    zero_part = html.parent / f"{html.name}.part-0{EXTRACTED_JSON_SUFFIX}"
    orphan.write_text("{}\n", encoding="utf-8", newline="\n")
    unexpected_part.write_text("unexpected\n", encoding="utf-8", newline="\n")
    malformed_part.write_text("malformed\n", encoding="utf-8", newline="\n")
    zero_part.write_text("{}\n", encoding="utf-8", newline="\n")

    failures = check_all(corpus_root=corpus, repo_root=repo_root)

    assert f"ORPHAN  {orphan.relative_to(repo_root).as_posix()}" in failures
    assert f"ORPHAN  {unexpected_part.relative_to(repo_root).as_posix()}" in failures
    assert f"ORPHAN  {malformed_part.relative_to(repo_root).as_posix()}" in failures
    assert f"ORPHAN  {zero_part.relative_to(repo_root).as_posix()}" in failures
    assert extract_all(check=True, corpus_root=corpus, repo_root=repo_root) == 4
    assert extract_all(corpus_root=corpus, repo_root=repo_root) == 4
    assert orphan.is_file(), "normal refresh must not delete a discovered orphan"
    assert malformed_part.is_file(), "normal refresh must not delete malformed multipart output"


def test_check_leaves_pdf_sidecars_to_the_pdf_producer(tmp_path: Path) -> None:
    corpus, repo_root = _generated_fixture(tmp_path)
    workbook_dir = corpus / "aeat_official" / "disenos_registro"
    pdf_text = workbook_dir / f"reference.pdf{EXTRACTED_TEXT_SUFFIX}"
    pdf_json = workbook_dir / f"reference.pdf{EXTRACTED_JSON_SUFFIX}"
    pdf_text.write_text("PDF text\n", encoding="utf-8", newline="\n")
    pdf_json.write_text("{}\n", encoding="utf-8", newline="\n")

    assert check_all(corpus_root=corpus, repo_root=repo_root) == []
    assert extract_all(corpus_root=corpus, repo_root=repo_root) == 0
    assert pdf_text.is_file()
    assert pdf_json.is_file()
