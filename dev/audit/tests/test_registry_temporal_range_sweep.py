"""Canonical support-year validation and candidate behavior for the audit sweep."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import ValidationError

from cadrumo.core.toml import TomlDecodeError
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

from .. import registry_temporal_range_sweep as temporal_sweep

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _write_authority(repo: Path, declaration: str) -> None:
    path = repo / temporal_sweep.AUTHORITY
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(declaration, encoding="utf-8")


def _declaration(floor: object, horizon: object, extra: str = "") -> str:
    return f"[supported_filing_years]\nfloor = {floor}\nhorizon = {horizon}\n{extra}"


@pytest.mark.parametrize("closed", [False, True])
def test_canonical_bounds_reads_open_and_closed_real_toml_declarations(tmp_path: Path, closed: bool) -> None:
    envelope = filing_year_envelope()
    ceiling = envelope.horizon + 4 if closed else None
    extra = f"hard_ceiling = {ceiling}\n" if closed else ""
    _write_authority(tmp_path, _declaration(envelope.floor, envelope.horizon, extra))

    assert temporal_sweep.canonical_bounds(tmp_path) == (envelope.floor, envelope.horizon, ceiling)


#: Each malformed declaration, built from the support bounds, keyed by what is wrong with it.
_NONCANONICAL: dict[str, Callable[[int, int], str]] = {
    "not a table": lambda floor, horizon: "supported_filing_years = 'not a table'\n",
    "boolean floor": lambda floor, horizon: _declaration("true", horizon),
    "text horizon": lambda floor, horizon: _declaration(floor, f"'{horizon}'"),
    "fractional ceiling": lambda floor, horizon: _declaration(floor, horizon, f"hard_ceiling = {horizon + 4}.0\n"),
    "year list": lambda floor, horizon: _declaration(floor, horizon, f"years = [{floor}, {floor + 1}, {floor + 2}]\n"),
    "three digit floor": lambda floor, horizon: _declaration(999, horizon),
    "five digit horizon": lambda floor, horizon: _declaration(floor, 10000),
    "floor above horizon": lambda floor, horizon: _declaration(horizon, floor),
    "ceiling below horizon": lambda floor, horizon: _declaration(floor, horizon, f"hard_ceiling = {horizon - 1}\n"),
}


@pytest.mark.parametrize("kind", sorted(_NONCANONICAL))
def test_canonical_bounds_refuses_malformed_or_noncanonical_real_toml(tmp_path: Path, kind: str) -> None:
    envelope = filing_year_envelope()
    _write_authority(tmp_path, _NONCANONICAL[kind](envelope.floor, envelope.horizon))

    with pytest.raises(ValidationError):
        temporal_sweep.canonical_bounds(tmp_path)


def test_canonical_bounds_preserves_toml_syntax_refusal(tmp_path: Path) -> None:
    _write_authority(tmp_path, f"[supported_filing_years\nfloor = {filing_year_envelope().floor}\n")

    with pytest.raises(TomlDecodeError):
        temporal_sweep.canonical_bounds(tmp_path)


def test_sweep_keeps_candidate_results_for_a_miniature_tree(tmp_path: Path) -> None:
    first = filing_year_envelope().floor
    years = (first, first + 1, first + 2)
    _write_authority(tmp_path, _declaration(first, years[-1]))
    source = tmp_path / "src" / "sample.py"
    source.parent.mkdir(parents=True, exist_ok=True)
    context = f"SUPPORTED_YEARS = [{years[0]}, {years[1]}, {years[2]}]"
    source.write_text(context + "\n", encoding="utf-8")

    assert temporal_sweep.sweep(tmp_path, (Path("src"),)) == [
        temporal_sweep.Finding(
            path=Path("src/sample.py"),
            line=1,
            kind="enumerated-year-container",
            years=years,
            context=context,
        ),
        temporal_sweep.Finding(
            path=Path("src/sample.py"),
            line=1,
            kind="policy-named-assignment",
            years=years,
            context=context,
        ),
    ]
