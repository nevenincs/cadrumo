from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind
from cadrumo.domain.calculations.registry.authority import bundled_authority

from ..analysis import m200_2024_sibling_remediation as remediation
from ..analysis import m200_semantic_casilla_candidates as subject
from ..pipeline._semantic_map_loader import load_semantic_map

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


def test_m200_2024_dp200018_00588_is_qualified_independently_of_dp200014b() -> None:
    """A repeated printed box number resolves through its 2024 source segment."""
    snapshot = bundled_authority().snapshot("200", filing_year=2024, period="0A")
    semantic_map = load_semantic_map(Path("dev/registry/mappings/modelo_200/2024"))
    entry = next(item for item in semantic_map.entries if item.export_field_id == "m200-2024.dp200018.f0172")

    assert entry.casilla_id == "DP200018:00588"
    assert {"DP200018:00588", "DP200014B:00588"} <= set(snapshot.casillas)


def test_current_printed_identity_beats_sibling_casilla_identity() -> None:
    target_field = SimpleNamespace(
        normalized_description="Importe [02971]",
        aeat_type="Num",
    )
    sibling_field = SimpleNamespace()
    sibling_entry = SimpleNamespace(kind=CasillaFieldKind.CASILLA, casilla_id="00355")

    disposition, reason, proposed_id, _kind = subject._classify_sibling(
        target_field,
        sibling_field,
        sibling_entry,
        authored_token="2971",  # noqa: S106 - official casilla token
        target_ids_by_number={"00355": ("00355",)},
    )

    assert disposition is subject.M200CasillaDisposition.REVISION_MISSING_DECLARATION
    assert reason == "current official printed identity is absent from the target revision"
    assert proposed_id == "02971"


def test_current_2024_casilla_identity_beats_later_sibling_filler() -> None:
    target_field = SimpleNamespace(normalized_description="Importe [01683]", aeat_type="Num")
    sibling_entry = SimpleNamespace(kind=CasillaFieldKind.FILLER, casilla_id=None)

    disposition, reason, proposed_id, _kind = subject._classify_sibling(
        target_field,
        SimpleNamespace(),
        sibling_entry,
        authored_token="1683",  # noqa: S106 - official casilla token
        target_ids_by_number={},
    )

    assert disposition is subject.M200CasillaDisposition.REVISION_MISSING_DECLARATION
    assert reason == "current official printed identity is absent from the target revision"
    assert proposed_id == "01683"


def test_m200_2024_sibling_remediation_refuses_target_first_restoration_gaps() -> None:
    """Sibling payload cannot replace the current design's printed identity."""
    proposals = remediation.load_bundled_m200_2024_sibling_remediation()
    counts = {
        disposition: sum(item.disposition is disposition for item in proposals)
        for disposition in remediation.M200RemediationDisposition
    }

    assert proposals
    assert counts[remediation.M200RemediationDisposition.DERIVE_DECLARATION] == 0
    assert counts[remediation.M200RemediationDisposition.CORRECT_SEMANTIC_MAP] == 0
    assert counts[remediation.M200RemediationDisposition.UNRESOLVED] == len(proposals)
