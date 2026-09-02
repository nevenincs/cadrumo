from __future__ import annotations

from pathlib import Path

import pytest

from ..analysis import m200_2024_sibling_remediation as remediation
from ..analysis import m200_semantic_casilla_candidates as subject

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _candidate() -> subject.M200CasillaCandidate:
    return subject.M200CasillaCandidate(
        export_field_id="m200-2024.dp200018.f0172",
        authored_token="588",  # noqa: S106 - official casilla token, not a credential
        disposition=subject.M200CasillaDisposition.SEGMENT_QUALIFIED_IDENTITY,
        reason="segment ownership cannot be inferred",
        source_ref="aeat-dr-200-2024",
        source_sha256="a" * 64,
        sibling_source_ref="aeat-dr-200-2025",
        sibling_source_sha256="b" * 64,
        sheet="DP200018",
        record_identity="DP200018",
        source_row=177,
        source_cell="A177",
        ordinal="172",
        offset=1,
        length=5,
        aeat_type="Num",
        label="[00588]",
        proposed_casilla_id="DP200014B:00588",
    )


def test_review_toml_is_deterministic_and_serializes_disposition() -> None:
    rendered = subject.render_m200_casilla_candidates_toml((_candidate(),))

    assert rendered == subject.render_m200_casilla_candidates_toml((_candidate(),))
    assert "disposition = 'segment_qualified_identity'" in rendered
    assert "registry_data_type" not in rendered
    assert "legal_refs" not in rendered


def test_cli_writes_then_checks_explicit_review_path(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(subject, "_load_bundled_candidates", lambda: (_candidate(),))
    output = tmp_path / "review.toml"

    assert subject.main(["--output", str(output)]) == 0
    assert subject.main(["--output", str(output), "--check"]) == 0


def test_cli_check_refuses_stale_review_without_writing(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(subject, "_load_bundled_candidates", lambda: (_candidate(),))
    output = tmp_path / "review.toml"
    output.write_text("stale", encoding="utf-8")

    assert subject.main(["--output", str(output), "--check"]) == 1
    assert output.read_text(encoding="utf-8") == "stale"


def test_m200_2024_sibling_remediation_evaluates_only_known_candidate_classes() -> None:
    """The direct bundled loader is proposal-only: it must not publish registry data."""
    proposals = remediation.load_bundled_m200_2024_sibling_remediation()
    counts = {
        disposition: sum(item.disposition is disposition for item in proposals)
        for disposition in remediation.M200RemediationDisposition
    }

    assert len(proposals) == 68
    assert counts[remediation.M200RemediationDisposition.DERIVE_DECLARATION] == 50
    assert counts[remediation.M200RemediationDisposition.CORRECT_SEMANTIC_MAP] == 3
    assert counts[remediation.M200RemediationDisposition.UNRESOLVED] == 15
