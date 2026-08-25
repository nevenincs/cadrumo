"""Real-behaviour tests for the terminology curation-backlog ratchet."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from .. import (
    check_curation_backlog_ratchet,
    load_curation_backlog_ratchet_baseline,
)
from ..cli import app
from ..errors import TerminologyLoadError

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_APPROVED = """
[concept]
concept_id = "prorrata"
domain = "concepto"
lifecycle = "approved"
legal_refs = ["ley-37-1992:art-104"]
created_at = 2024-01-02
updated_at = 2026-05-01

[language.es]
short_description = "Porcentaje de IVA deducible en actividad mixta."
definition = "Regla que determina la parte deducible del IVA soportado."

[language.es.source]
citation = "Articulo 104 LIVA."
authority = "boe"

[[language.es.term]]
label = "prorrata"
term_status = "preferred"
"""

_DRAFT = """
[concept]
concept_id = "modelo-303"
domain = "modelo"
lifecycle = "draft"
domain_refs = ["modelo:303"]
created_at = 2026-06-01
updated_at = 2026-06-01

[language.es]
short_description = "(sin curar) draft pendiente de definicion"
"""


def _tree(tmp_path: Path, fragments: dict[str, str]) -> Path:
    concepts = tmp_path / "concepts"
    concepts.mkdir()
    for name, content in fragments.items():
        (concepts / name).write_text(content, encoding="utf-8")
    return concepts


def _baseline(tmp_path: Path, *, drafts: int, empty_short_descriptions: int) -> Path:
    path = tmp_path / "curation-ratchet.json"
    path.write_text(
        json.dumps(
            {
                "draft_count": drafts,
                "empty_short_description_count": empty_short_descriptions,
                "recorded_at": "2026-06-11",
                "review_cadence": "Review after every Terminology Handbook curation pass.",
                "source": "test fixture audit baseline",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def test_bundled_handbook_curation_backlog_does_not_exceed_committed_baseline() -> None:
    result = check_curation_backlog_ratchet()

    assert result.passed
    assert result.violations == ()
    assert result.report.draft_count == result.baseline.draft_count
    assert len(result.report.empty_short_description) == result.baseline.empty_short_description_count


def test_ratchet_allows_curation_progress(tmp_path: Path) -> None:
    concepts = _tree(tmp_path, {"prorrata.toml": _APPROVED})
    baseline = _baseline(tmp_path, drafts=1, empty_short_descriptions=1)

    result = check_curation_backlog_ratchet(concepts_dir=concepts, baseline_path=baseline)

    assert result.passed
    assert result.draft_delta == -1
    assert result.empty_short_description_delta == -1


def test_ratchet_rejects_draft_count_growth(tmp_path: Path) -> None:
    concepts = _tree(tmp_path, {"modelo-303.toml": _DRAFT})
    baseline = _baseline(tmp_path, drafts=0, empty_short_descriptions=1)

    result = check_curation_backlog_ratchet(concepts_dir=concepts, baseline_path=baseline)

    assert not result.passed
    assert result.violations == ("draft_count grew from 0 to 1",)


def test_ratchet_rejects_empty_short_description_growth(tmp_path: Path) -> None:
    concepts = _tree(tmp_path, {"modelo-303.toml": _DRAFT})
    baseline = _baseline(tmp_path, drafts=1, empty_short_descriptions=0)

    result = check_curation_backlog_ratchet(concepts_dir=concepts, baseline_path=baseline)

    assert not result.passed
    assert result.violations == ("empty_short_description count grew from 0 to 1",)


def test_baseline_loader_rejects_missing_counter(tmp_path: Path) -> None:
    path = tmp_path / "curation-ratchet.json"
    path.write_text(
        json.dumps(
            {
                "draft_count": 0,
                "recorded_at": "2026-06-11",
                "review_cadence": "Review after every Terminology Handbook curation pass.",
                "source": "test fixture audit baseline",
            },
        ),
        encoding="utf-8",
    )

    with pytest.raises(TerminologyLoadError, match="missing key"):
        load_curation_backlog_ratchet_baseline(path)


def test_audit_ratchet_check_cli_reports_clean_for_bundled_handbook() -> None:
    result = CliRunner().invoke(app, ["audit", "--ratchet-check"])

    assert result.exit_code == 0
    assert "curation ratchet: clean" in result.stdout
