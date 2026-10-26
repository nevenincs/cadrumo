"""Canonical support-year validation and candidate behavior for the audit sweep."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from cadrumo.core.toml import TomlDecodeError

from .. import registry_temporal_range_sweep as temporal_sweep

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _write_authority(repo: Path, declaration: str) -> None:
    path = repo / temporal_sweep.AUTHORITY
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(declaration, encoding="utf-8")


@pytest.mark.parametrize(
    ("declaration", "expected"),
    [
        (
            "[supported_filing_years]\nfloor = 2022\nhorizon = 2026\n",
            (2022, 2026, None),
        ),
        (
            "[supported_filing_years]\nfloor = 2022\nhorizon = 2026\nhard_ceiling = 2030\n",
            (2022, 2026, 2030),
        ),
    ],
)
def test_canonical_bounds_reads_open_and_closed_real_toml_declarations(
    tmp_path: Path,
    declaration: str,
    expected: tuple[int, int, int | None],
) -> None:
    _write_authority(tmp_path, declaration)

    assert temporal_sweep._canonical_bounds(tmp_path) == expected


@pytest.mark.parametrize(
    "declaration",
    [
        "supported_filing_years = 'not a table'\n",
        "[supported_filing_years]\nfloor = true\nhorizon = 2026\n",
        "[supported_filing_years]\nfloor = 2022\nhorizon = '2026'\n",
        "[supported_filing_years]\nfloor = 2022\nhorizon = 2026\nhard_ceiling = 2030.0\n",
        "[supported_filing_years]\nfloor = 2022\nhorizon = 2026\nyears = [2022, 2023, 2024]\n",
        "[supported_filing_years]\nfloor = 1999\nhorizon = 2026\n",
        "[supported_filing_years]\nfloor = 2022\nhorizon = 2100\n",
        "[supported_filing_years]\nfloor = 2024\nhorizon = 2022\n",
        "[supported_filing_years]\nfloor = 2022\nhorizon = 2026\nhard_ceiling = 2025\n",
    ],
)
def test_canonical_bounds_refuses_malformed_or_noncanonical_real_toml(
    tmp_path: Path,
    declaration: str,
) -> None:
    _write_authority(tmp_path, declaration)

    with pytest.raises(ValidationError):
        temporal_sweep._canonical_bounds(tmp_path)


def test_canonical_bounds_preserves_toml_syntax_refusal(tmp_path: Path) -> None:
    _write_authority(tmp_path, "[supported_filing_years\nfloor = 2022\n")

    with pytest.raises(TomlDecodeError):
        temporal_sweep._canonical_bounds(tmp_path)


def test_sweep_keeps_candidate_results_for_a_miniature_tree(tmp_path: Path) -> None:
    _write_authority(
        tmp_path,
        "[supported_filing_years]\nfloor = 2022\nhorizon = 2024\n",
    )
    source = tmp_path / "src" / "sample.py"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("SUPPORTED_YEARS = [2022, 2023, 2024]\n", encoding="utf-8")

    assert temporal_sweep.sweep(tmp_path, (Path("src"),)) == [
        temporal_sweep.Finding(
            path=Path("src/sample.py"),
            line=1,
            kind="enumerated-year-container",
            years=(2022, 2023, 2024),
            context="SUPPORTED_YEARS = [2022, 2023, 2024]",
        ),
        temporal_sweep.Finding(
            path=Path("src/sample.py"),
            line=1,
            kind="policy-named-assignment",
            years=(2022, 2023, 2024),
            context="SUPPORTED_YEARS = [2022, 2023, 2024]",
        ),
    ]
