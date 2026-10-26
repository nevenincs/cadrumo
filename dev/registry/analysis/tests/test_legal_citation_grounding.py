"""Every required_text quote is classified by the folding that finds it in its excerpt."""

from __future__ import annotations

from pathlib import Path

import pytest

from ..legal_citation_grounding import CITATION_CLASSES, Finding, main, scan

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_EXCERPT = "Los artículos del modelo\N{NO-BREAK SPACE}390 regulan la DECLARACIÓN resumen anual."


def _plant(root: Path, quotes: list[str]) -> tuple[Path, Path]:
    data = root / "data"
    legal = root / "legal"
    (data / "corpus").mkdir(parents=True)
    legal.mkdir()
    (data / "corpus" / "excerpt.html").write_text(_EXCERPT, encoding="utf-8")
    rendered = ", ".join(f'"{quote}"' for quote in quotes)
    (legal / "catalogue.toml").write_text(
        f'[legal.cited]\ncorpus_ref = "corpus/excerpt.html#art"\nrequired_text = [{rendered}]\n',
        encoding="utf-8",
    )
    return data, legal


def test_each_defect_class_is_named_and_a_verbatim_quote_is_not(tmp_path: Path) -> None:
    quotes = [
        "Los artículos",
        "modelo 390",
        "Los articulos",
        "declaración resumen",
        "una frase ausente",
    ]
    data, legal = _plant(tmp_path, quotes)

    findings = {finding.quote: finding.kind for finding in scan(data, legal)}

    assert findings == {
        "modelo 390": "whitespace",
        "Los articulos": "diacritic",
        "declaración resumen": "case",
        "una frase ausente": "absent",
    }
    assert set(findings.values()) == set(CITATION_CLASSES)


def test_a_citation_whose_excerpt_is_missing_is_not_reported(tmp_path: Path) -> None:
    data, legal = _plant(tmp_path, ["una frase ausente"])
    (data / "corpus" / "excerpt.html").unlink()

    assert list(scan(data, legal)) == []


def test_the_live_corpus_scan_reports_only_named_classes(capsys: pytest.CaptureFixture[str]) -> None:
    findings = tuple(scan())

    assert all(isinstance(finding, Finding) and finding.kind in CITATION_CLASSES for finding in findings)
    assert main(["--json"]) == 0
    assert '"counts"' in capsys.readouterr().out
