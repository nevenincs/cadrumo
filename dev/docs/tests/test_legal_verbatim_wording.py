"""Only exact, anchored source wording may bypass ordinary spelling checks."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from docutils.core import publish_parts

from dev.docs.legal_catalogue import read_legal_provisions
from dev.docs.legal_page_rendering import verified_legal_wording_indices
from dev.docs.legal_reference import render_legal_reference
from dev.locales.signal_documentation_inventory import inventory_generated_document_file

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_OFFICIAL = "Una obligacion tributaria conserva su texto."
_UNVERIFIED = "Una palabra inventadísima permanece visible."


def _catalogue(tmp_path: Path, *, quotes: tuple[str, ...] = (_OFFICIAL, _UNVERIFIED)) -> tuple[Path, Path]:
    root = tmp_path / "src/cadrumo/_data"
    corpus = root / "corpus/normatives/html/example.html"
    corpus.parent.mkdir(parents=True)
    corpus.write_text("synthetic official corpus", encoding="utf-8")
    sidecar = corpus.with_name(corpus.name + ".extracted.json")
    sidecar.write_text(
        json.dumps(
            {
                "units": [
                    {"anchor": "a1", "text": f"Earlier. {_OFFICIAL} Later."},
                    {"anchor": "a2", "text": _UNVERIFIED},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    catalogue = root / "registry/aeat/legal/example.toml"
    catalogue.parent.mkdir(parents=True)
    catalogue.write_text(
        '[legal."ley-example:art-1"]\n'
        'kind = "ley"\n'
        'document_id = "BOE-A-2000-1"\n'
        'corpus_ref = "corpus/normatives/html/example.html#a1"\n'
        'permalink = "https://www.boe.es/buscar/act.php?id=BOE-A-2000-1#a1"\n'
        'article = "1"\n'
        'notes = "A neighboring misspeling remains ordinary prose."\n'
        f"required_text = {json.dumps(quotes, ensure_ascii=False)}\n",
        encoding="utf-8",
    )
    return catalogue, sidecar


def _generated_page(tmp_path: Path) -> Path:
    result = render_legal_reference(tmp_path, records=read_legal_provisions(tmp_path))
    page = result.pages[0]
    target = tmp_path / "docs" / page.output_relpath
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(page.rst, encoding="utf-8")
    return target


def _inventory(page: Path, root: Path) -> tuple[list[dict[str, object]], dict[str, dict[str, str]]]:
    findings: list[dict[str, object]] = []
    values: dict[str, dict[str, str]] = {}
    inventory_generated_document_file(page, root, Counter(), findings, values)
    return findings, values


def test_only_exact_anchored_wording_is_excluded_and_visible_output_is_unchanged(tmp_path: Path) -> None:
    _catalogue(tmp_path)
    page = _generated_page(tmp_path)
    rst = page.read_text(encoding="utf-8")
    assert '"verified": [0]' in rst
    findings, values = _inventory(page, tmp_path)
    assert findings == []
    assert any(_UNVERIFIED in text for text in values["es"].values())
    assert all(_OFFICIAL not in text for text in values["es"].values())
    assert any("misspeling" in text for text in values["en"].values())

    without_marker = "\n".join(line for line in rst.split("\n") if not line.startswith(".. cadrumo-legal-verbatim:"))
    rendered = BeautifulSoup(publish_parts(rst, writer_name="html5")["html_body"], "html.parser")
    original = BeautifulSoup(publish_parts(without_marker, writer_name="html5")["html_body"], "html.parser")
    assert rendered.get_text(" ", strip=True) == original.get_text(" ", strip=True)
    assert [(a.get("href"), a.get_text()) for a in rendered.find_all("a")] == [
        (a.get("href"), a.get_text()) for a in original.find_all("a")
    ]
    assert [span.get("id") for span in rendered.find_all("span", id=True)] == [
        span.get("id") for span in original.find_all("span", id=True)
    ]


@pytest.mark.parametrize(
    "altered", [_OFFICIAL.replace("obligacion", "obligación"), _OFFICIAL.lower(), _OFFICIAL.replace(".", ",")]
)
def test_case_accent_and_punctuation_changes_are_not_verbatim(tmp_path: Path, altered: str) -> None:
    _catalogue(tmp_path, quotes=(altered,))
    page = _generated_page(tmp_path)
    assert "cadrumo-legal-verbatim" not in page.read_text(encoding="utf-8")
    findings, values = _inventory(page, tmp_path)
    assert findings == []
    assert any(altered.rstrip(".,") in text for text in values["es"].values())


def test_marker_fails_closed_after_rendered_text_changes(tmp_path: Path) -> None:
    _catalogue(tmp_path)
    page = _generated_page(tmp_path)
    original = page.read_text(encoding="utf-8")
    page.write_text(original.replace(_OFFICIAL, _OFFICIAL.replace("obligacion", "obligación")), encoding="utf-8")
    findings, _ = _inventory(page, tmp_path)
    assert [item["kind"] for item in findings] == ["docs_generated_source_unreadable"]


def test_marker_fails_closed_when_the_anchored_source_changes(tmp_path: Path) -> None:
    _catalogue_path, sidecar = _catalogue(tmp_path)
    page = _generated_page(tmp_path)
    assert _inventory(page, tmp_path)[0] == []
    sidecar.write_text(json.dumps({"units": [{"anchor": "a1", "text": "Different source."}]}), encoding="utf-8")
    findings, _ = _inventory(page, tmp_path)
    assert [item["kind"] for item in findings] == ["docs_generated_source_unreadable"]


def test_marker_fails_closed_when_the_catalogue_changes_after_inventory(tmp_path: Path) -> None:
    catalogue, _sidecar = _catalogue(tmp_path)
    page = _generated_page(tmp_path)
    assert _inventory(page, tmp_path)[0] == []
    catalogue.write_text(catalogue.read_text(encoding="utf-8").replace(_OFFICIAL, _UNVERIFIED), encoding="utf-8")
    findings, _ = _inventory(page, tmp_path)
    assert [item["kind"] for item in findings] == ["docs_generated_source_unreadable"]


def test_malformed_marker_is_a_blocking_extraction_failure(tmp_path: Path) -> None:
    _catalogue(tmp_path)
    page = _generated_page(tmp_path)
    text = page.read_text(encoding="utf-8").replace('"verified": [0]', '"verified": [0,')
    page.write_text(text, encoding="utf-8")
    findings, _ = _inventory(page, tmp_path)
    assert [item["kind"] for item in findings] == ["docs_generated_source_unreadable"]


def test_fabricated_marker_does_not_authorize_a_different_quote(tmp_path: Path) -> None:
    _catalogue(tmp_path, quotes=(_UNVERIFIED,))
    page = _generated_page(tmp_path)
    text = page.read_text(encoding="utf-8")
    marker = '.. cadrumo-legal-verbatim: {"legal_id": "ley-example:art-1", "verified": [0]}\n\n'
    page.write_text(
        text.replace(
            '.. raw:: html\n\n   <div class="cadrumo-legal-wording">',
            marker + '.. raw:: html\n\n   <div class="cadrumo-legal-wording">',
        ),
        encoding="utf-8",
    )
    findings, _ = _inventory(page, tmp_path)
    assert [item["kind"] for item in findings] == ["docs_generated_source_unreadable"]


def test_real_bundled_deaccented_wording_is_proven_without_changing_it() -> None:
    from dev.paths import REPO_ROOT

    record = next(row for row in read_legal_provisions(REPO_ROOT) if row.legal_id == "trlirnr-rdleg-5-2004:art-24")
    index = next(i for i, text in enumerate(record.required_text) if "aplicacion" in text)
    assert index in verified_legal_wording_indices(record, REPO_ROOT)
    mutated = list(record.required_text)
    mutated[index] = mutated[index].replace("aplicacion", "aplicación")
    assert index not in verified_legal_wording_indices(replace(record, required_text=tuple(mutated)), REPO_ROOT)


def test_real_xml_source_requires_its_exact_anchored_wording() -> None:
    from dev.paths import REPO_ROOT

    record = next(row for row in read_legal_provisions(REPO_ROOT) if row.legal_id == "real-decreto-ley-8-2023:art-18")
    assert record.corpus_ref.endswith(".xml#a1-10")
    assert verified_legal_wording_indices(record, REPO_ROOT) == tuple(range(len(record.required_text)))
    mutated = replace(record, corpus_ref=record.corpus_ref.removesuffix("#a1-10") + "#unknown-unit")
    assert verified_legal_wording_indices(mutated, REPO_ROOT) == ()
