"""Source-order preflight compares retained casilla identity, not row content."""

from __future__ import annotations

from pathlib import Path

import pytest

from ..casilla_order_review import (
    CasillaOrderReport,
    RevisionCasillaOrder,
    main,
    render_report,
    review_casilla_order,
)
from ..conformance.loader_directory_mode_support import write_standard_manifest

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_LEGAL_REF = "ley-58-2003:art-29"
_SOURCE_REF = "aeat-manual"


def _casilla_fragment(revision_id: str, rows: tuple[tuple[str, str], ...]) -> str:
    return "".join(
        f'[[revisions."{revision_id}".casillas]]\n'
        f'id = "{casilla_id}"\n'
        f'number = "{number}"\n'
        'section = ["liquidacion"]\n'
        'data_type = "money"\n'
        f'continuidad_id = "lineage-{casilla_id}"\n'
        f'legal_refs = ["{_LEGAL_REF}"]\n'
        f'source_refs = ["{_SOURCE_REF}"]\n\n'
        for casilla_id, number in rows
    )


def _write_revision(
    modelo_dir: Path,
    revision_id: str,
    *,
    rows: tuple[tuple[str, str], ...] | None,
    storage_baseline: str | None = None,
    positions: tuple[tuple[str, int], ...] = (),
) -> None:
    year = int(revision_id)
    revision_dir = modelo_dir / "revisions" / revision_id
    revision_dir.mkdir(parents=True)
    manifest = (
        f'[revisions."{revision_id}"]\n'
        f"valid_from = {year}-01-01\n"
        f"valid_to = {year}-12-31\n"
        f'period_selector = {{ years = [{year}], periods = ["0A"] }}\n'
        f'legal_refs = ["{_LEGAL_REF}"]\n'
        f'source_refs = ["{_SOURCE_REF}"]\n'
    )
    if storage_baseline is not None:
        manifest += f'casilla_storage_baseline = "{storage_baseline}"\n'
    for casilla_id, position in positions:
        manifest += f'\n[[revisions."{revision_id}".casilla_positions]]\nid = "{casilla_id}"\nposition = {position}\n'
    (revision_dir / "revision.toml").write_text(manifest, encoding="utf-8", newline="\n")
    if rows is not None:
        casillas_dir = revision_dir / "casillas"
        casillas_dir.mkdir()
        (casillas_dir / "0001-declarations.toml").write_text(
            _casilla_fragment(revision_id, rows), encoding="utf-8", newline="\n"
        )


def _modelo(
    root: Path,
    revisions: tuple[tuple[str, tuple[tuple[str, str], ...] | None, str | None, tuple[tuple[str, int], ...]], ...],
    *,
    modelo_id: str = "999",
) -> Path:
    modelo_dir = root / modelo_id
    modelo_dir.mkdir(parents=True)
    write_standard_manifest(modelo_dir, "Casilla order review")
    if modelo_id != "999":
        manifest = modelo_dir / "manifest.toml"
        manifest.write_text(
            manifest.read_text(encoding="utf-8").replace('id = "999"', f'id = "{modelo_id}"'),
            encoding="utf-8",
            newline="\n",
        )
    for revision_id, rows, baseline, positions in revisions:
        _write_revision(
            modelo_dir,
            revision_id,
            rows=rows,
            storage_baseline=baseline,
            positions=positions,
        )
    return modelo_dir


def _revision(
    revision_id: str,
    rows: tuple[tuple[str, str], ...] | None,
    *,
    baseline: str | None = None,
    positions: tuple[tuple[str, int], ...] = (),
) -> tuple[str, tuple[tuple[str, str], ...] | None, str | None, tuple[tuple[str, int], ...]]:
    return revision_id, rows, baseline, positions


def test_additions_removals_and_content_changes_do_not_hide_retained_order(tmp_path: Path) -> None:
    reference = _modelo(
        tmp_path / "accepted",
        (
            _revision("2024", (("0001", "1"), ("0002", "2"), ("0003", "3"))),
            _revision("2025", None, baseline="2024"),
        ),
    )
    candidate = _modelo(
        tmp_path / "candidate",
        (
            _revision("2024", (("0002", "20"), ("0003", "3"), ("0004", "4"))),
            _revision("2025", None, baseline="2024"),
        ),
    )

    report = review_casilla_order(reference, candidate)

    assert report.passed
    assert report.common_revisions == ("2024", "2025")
    for comparison in report.comparisons:
        assert comparison.retained_reference_ids == ("0002", "0003")
        assert comparison.retained_candidate_ids == ("0002", "0003")
        assert comparison.additions == ("0004",)
        assert comparison.removals == ("0001",)


def test_explicit_id_rename_keeps_the_retained_order_and_is_reported(tmp_path: Path) -> None:
    reference = _modelo(
        tmp_path / "accepted",
        (_revision("2024", (("0001", "1"), ("0002", "2"))),),
    )
    candidate = _modelo(
        tmp_path / "candidate",
        (_revision("2024", (("0004", "1"), ("0002", "2"))),),
    )

    report = review_casilla_order(reference, candidate, renames=(("0001", "0004"),))

    assert report.passed
    assert report.comparisons[0].applied_renames == (("0001", "0004"),)
    assert report.comparisons[0].retained_reference_ids == ("0004", "0002")
    assert report.comparisons[0].retained_candidate_ids == ("0004", "0002")


def test_baseline_addition_can_expose_successor_position_drift(tmp_path: Path) -> None:
    positions = (("0002", 1), ("0003", 2))
    reference = _modelo(
        tmp_path / "accepted",
        (
            _revision("2024", (("0001", "1"), ("0002", "2"), ("0003", "3"))),
            _revision("2025", None, baseline="2024", positions=positions),
        ),
    )
    candidate = _modelo(
        tmp_path / "candidate",
        (
            _revision("2024", (("0004", "4"), ("0001", "1"), ("0002", "2"), ("0003", "3"))),
            _revision("2025", None, baseline="2024", positions=positions),
        ),
    )

    report = review_casilla_order(reference, candidate)

    assert report.status == "drift"
    assert report.comparisons[0].order_matches
    successor = report.comparisons[1]
    assert successor.additions == ("0004",)
    assert successor.retained_reference_ids == ("0001", "0002", "0003")
    assert successor.retained_candidate_ids == ("0002", "0003", "0001")
    assert not successor.order_matches


@pytest.mark.parametrize(
    "renames",
    [
        (("9999", "0004"),),
        (("0001", "0004"), ("0002", "0004")),
        (("0001", "0002"), ("0002", "0003")),
    ],
)
def test_unknown_or_ambiguous_rename_maps_are_refused(tmp_path: Path, renames: tuple[tuple[str, str], ...]) -> None:
    reference = _modelo(
        tmp_path / "accepted",
        (_revision("2024", (("0001", "1"), ("0002", "2"))),),
    )
    candidate = _modelo(
        tmp_path / "candidate",
        (_revision("2024", (("0003", "3"), ("0004", "4"))),),
    )

    with pytest.raises(ValueError):
        review_casilla_order(reference, candidate, renames=renames)


def test_rename_that_collides_with_a_member_in_the_same_revision_is_refused(tmp_path: Path) -> None:
    reference = _modelo(
        tmp_path / "accepted",
        (_revision("2024", (("0001", "1"), ("0004", "4"))),),
    )
    candidate = _modelo(
        tmp_path / "candidate",
        (_revision("2024", (("0004", "4"), ("0002", "2"))),),
    )

    with pytest.raises(ValueError, match="collides in reference revision"):
        review_casilla_order(reference, candidate, renames=(("0001", "0004"),))


def test_missing_reference_revision_makes_coverage_incomplete(tmp_path: Path) -> None:
    reference = _modelo(
        tmp_path / "accepted",
        (
            _revision("2024", (("0001", "1"),)),
            _revision("2025", (("0002", "2"),)),
        ),
    )
    candidate = _modelo(
        tmp_path / "candidate",
        (_revision("2024", (("0001", "1"),)),),
    )

    report = review_casilla_order(reference, candidate)

    assert report.status == "incomplete"
    assert not report.passed
    assert report.missing_candidate_revisions == ("2025",)


def test_nonempty_revision_with_no_retained_members_is_incomplete_even_with_a_later_rename(
    tmp_path: Path,
) -> None:
    reference = _modelo(
        tmp_path / "accepted",
        (
            _revision("2024", (("0001", "1"),)),
            _revision("2025", (("0001", "1"),)),
        ),
    )
    candidate = _modelo(
        tmp_path / "candidate",
        (
            _revision("2024", (("0003", "3"),)),
            _revision("2025", (("0004", "4"),)),
        ),
    )

    report = review_casilla_order(reference, candidate, renames=(("0001", "0004"),))

    assert report.status == "incomplete"
    assert not report.comparisons[0].coverage_complete
    assert report.comparisons[0].retained_reference_ids == ()
    assert report.comparisons[1].retained_reference_ids == ("0004",)


def test_modelo_identity_mismatch_is_refused(tmp_path: Path) -> None:
    reference = _modelo(
        tmp_path / "accepted",
        (_revision("2024", (("0001", "1"),)),),
        modelo_id="999",
    )
    candidate = _modelo(
        tmp_path / "candidate",
        (_revision("2024", (("0001", "1"),)),),
        modelo_id="998",
    )

    with pytest.raises(ValueError, match="does not match candidate"):
        review_casilla_order(reference, candidate)


def test_cli_accepts_repeatable_rename_syntax(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    reference = _modelo(
        tmp_path / "accepted",
        (_revision("2024", (("0001", "1"),)),),
    )
    candidate = _modelo(
        tmp_path / "candidate",
        (_revision("2024", (("0004", "4"),)),),
    )

    result = main(["--reference", str(reference), "--candidate", str(candidate), "--rename", "0001=0004"])

    assert result == 0
    assert "casilla-order status=pass" in capsys.readouterr().out


def test_cli_report_bounds_large_drift_details() -> None:
    reference_ids = tuple(f"{index:04d}" for index in range(2000))
    candidate_ids = (reference_ids[1], reference_ids[0], *reference_ids[2:])
    comparison = RevisionCasillaOrder(
        revision_id="2025",
        reference_ids=reference_ids,
        mapped_reference_ids=reference_ids,
        candidate_ids=candidate_ids,
        retained_reference_ids=reference_ids,
        retained_candidate_ids=candidate_ids,
        additions=(),
        removals=(),
        applied_renames=(),
        order_matches=False,
        coverage_complete=True,
        coverage_note=None,
    )
    report = CasillaOrderReport(
        reference_modelo_id="999",
        candidate_modelo_id="999",
        reference_directory="accepted",
        candidate_directory="candidate",
        scope="casilla-id-order-only",
        renames=(),
        common_revisions=("2025",),
        missing_candidate_revisions=(),
        candidate_only_revisions=(),
        comparisons=(comparison,),
        status="drift",
    )

    rendered = render_report(report)

    assert len(rendered) < 2000
    assert "order_mismatches=2" in rendered
    assert "position=0 reference='0000' candidate='0001'" in rendered
