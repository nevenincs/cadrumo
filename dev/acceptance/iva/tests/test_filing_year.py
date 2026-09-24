"""The IVA journeys run only for a filing year the published authority authors for them.

Every case uses the real published authority the product reads.  The years are
taken from that authority's own support envelope and revision selection, never
from a fixed list, so these tests keep their meaning when a generation adds a year.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.authority import (
    IndexedRegistryAuthority,
    PinnedAuthorityOperation,
    bundled_authority_descriptor_path,
)
from cadrumo.domain.calculations.registry.errors import RegistryError
from cadrumo.domain.calculations.registry.schema_references import TemporalProjectionDirection

from ..annual_cli_journey import run_iva_annual_foundation_cli_journey, run_iva_annual_m390_cli_journey
from ..cli_journey import run_iva_m303_cli_journey
from ..filing_year import IvaFilingYearUnsupportedError, require_journey_year
from ..installed_m303_evidence_journey import run_journey
from ..installed_tui_capture_reopen import run_installed_tui_capture_reopen
from ..multirate_cli_journey import run_iva_multirate_cli_journey
from ..negative_4t_cli_journey import run_iva_negative_4t_cli_journey

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_QUARTERS = ("1T", "2T", "3T", "4T")
_M390_COORDINATES = (*(("303", quarter) for quarter in _QUARTERS), ("390", "0A"))

type JourneyCall = Callable[[Path, Path, int], object]
"""Run one journey with (authority root, empty scratch root, year); the executable never exists."""


def _cli_journey(run: Callable[..., object]) -> JourneyCall:
    def call(authority_root: Path, scratch: Path, year: int) -> object:
        return run(
            executable=scratch / "absent-aeat",
            authority_root=authority_root,
            storage_root=scratch / "secure-store",
            artifact_root=scratch / "private-source-artifacts",
            year=year,
        )

    return call


def _tui_capture_journey(authority_root: Path, scratch: Path, year: int) -> object:
    return run_installed_tui_capture_reopen(
        workspace_root=scratch / "absent-workspace",
        authority_root=authority_root,
        output_root=scratch / "output",
        year=year,
    )


def _m303_evidence_journey(authority_root: Path, scratch: Path, year: int) -> object:
    return run_journey(
        argparse.Namespace(
            year=year,
            authority_root=authority_root,
            output_root=scratch / "output",
            cli=scratch / "absent-aeat",
            python=scratch / "absent-python",
            wheel=scratch / "absent.whl",
            workspace_root=scratch / "absent-workspace",
            source_commit="0" * 40,
        )
    )


_JOURNEYS: dict[str, JourneyCall] = {
    "ordinary_m303": _cli_journey(run_iva_m303_cli_journey),
    "annual_foundation": _cli_journey(run_iva_annual_foundation_cli_journey),
    "annual_m390": _cli_journey(run_iva_annual_m390_cli_journey),
    "multirate": _cli_journey(run_iva_multirate_cli_journey),
    "negative_4t": _cli_journey(run_iva_negative_4t_cli_journey),
    "installed_tui_capture": _tui_capture_journey,
    "installed_m303_evidence": _m303_evidence_journey,
}


@pytest.fixture(scope="module")
def authority_root() -> Path:
    """The directory of the published authority descriptor the product itself reads."""
    return bundled_authority_descriptor_path().parent


@pytest.fixture(scope="module")
def operation(authority_root: Path) -> Iterator[PinnedAuthorityOperation]:
    authority = IndexedRegistryAuthority(authority_root / "authority.current.json")
    try:
        with authority.operation() as leased:
            yield leased
    finally:
        authority.close()


def _direction(
    operation: PinnedAuthorityOperation, modelo: str, year: int, period: str
) -> tuple[TemporalProjectionDirection, str] | None:
    """Return how the authority resolves a coordinate and the revision it selects, or ``None`` when it does not."""
    try:
        snapshot = operation.snapshot(modelo, filing_year=year, period=period)
    except RegistryError:
        return None
    return snapshot.revision_projection_direction, str(snapshot.revision.id)


def _authored(operation: PinnedAuthorityOperation, modelo: str, year: int, period: str) -> str | None:
    """Return the revision authored for the coordinate, or ``None`` when it is absent or only projected."""
    resolved = _direction(operation, modelo, year, period)
    if resolved is None or resolved[0] is not TemporalProjectionDirection.AUTHORED:
        return None
    return resolved[1]


def _candidate_years(operation: PinnedAuthorityOperation) -> range:
    support = operation.supported_filing_years()
    return range(support.floor, support.horizon + 3)


@pytest.mark.parametrize("journey", tuple(_JOURNEYS), ids=tuple(_JOURNEYS))
def test_a_year_below_the_support_floor_is_refused_before_any_side_effect(
    journey: str, authority_root: Path, operation: PinnedAuthorityOperation, tmp_path: Path
) -> None:
    """The refusal names Modelo 303 and the year, and no store, artifact or output directory is created."""
    year = operation.supported_filing_years().floor - 1

    with pytest.raises(IvaFilingYearUnsupportedError) as refused:
        _JOURNEYS[journey](authority_root, tmp_path, year)

    assert "modelo 303" in str(refused.value)
    assert str(year) in str(refused.value)
    assert list(tmp_path.iterdir()) == []


def test_the_annual_journey_refuses_a_year_whose_modelo_390_is_only_projected(
    authority_root: Path, operation: PinnedAuthorityOperation, tmp_path: Path
) -> None:
    """Every 303 quarter is authored for the year, but 390 resolves only from another year's edition."""
    year = next(
        (
            candidate
            for candidate in _candidate_years(operation)
            if all(_authored(operation, "303", candidate, quarter) for quarter in _QUARTERS)
            and (resolved := _direction(operation, "390", candidate, "0A")) is not None
            and resolved[0] is not TemporalProjectionDirection.AUTHORED
        ),
        None,
    )
    assert year is not None, "the published authority projects no Modelo 390 year beside authored 303 quarters"

    with pytest.raises(IvaFilingYearUnsupportedError) as refused:
        _JOURNEYS["annual_m390"](authority_root, tmp_path, year)

    assert f"modelo 390 filing year {year}" in str(refused.value)
    assert "projection" in str(refused.value)
    assert list(tmp_path.iterdir()) == []


def test_the_ordinary_journey_refuses_a_record_design_whose_export_header_it_cannot_check(
    authority_root: Path, operation: PinnedAuthorityOperation, tmp_path: Path
) -> None:
    """A year with an authored 303 1T but another record design is refused, since its DP30300 positions are unheld."""
    checked = require_journey_year(authority_root=authority_root, year=2025, coordinates=(("303", "1T"),))
    year = next(
        (
            candidate
            for candidate in _candidate_years(operation)
            if (revision := _authored(operation, "303", candidate, "1T")) is not None
            and revision != checked.revision("303", "1T")
        ),
        None,
    )
    assert year is not None, "the published authority authors no second Modelo 303 1T record design"

    with pytest.raises(IvaFilingYearUnsupportedError) as refused:
        _JOURNEYS["ordinary_m303"](authority_root, tmp_path, year)

    assert f"modelo 303 filing year {year}" in str(refused.value)
    assert "DP30300" in str(refused.value)
    assert list(tmp_path.iterdir()) == []


def test_a_supported_year_is_admitted_with_its_own_authored_revisions_and_calendar(
    authority_root: Path, operation: PinnedAuthorityOperation
) -> None:
    """A year other than the default admits the annual coordinates and dates every value inside itself."""
    year = next(
        (
            candidate
            for candidate in _candidate_years(operation)
            if candidate != 2025
            and all(_authored(operation, modelo, candidate, period) for modelo, period in _M390_COORDINATES)
        ),
        None,
    )
    assert year is not None, "the published authority authors no second year for the annual coordinates"

    admitted = require_journey_year(authority_root=authority_root, year=year, coordinates=_M390_COORDINATES)

    assert admitted.year == year
    assert tuple((modelo, period) for modelo, period, _revision in admitted.revisions) == _M390_COORDINATES
    for modelo, period, revision in admitted.revisions:
        assert revision == _authored(operation, modelo, year, period)
    # The months and days the journeys use, carried into the admitted year unchanged.
    for month, day in ((2, 10), (2, 15), (2, 18), (3, 5), (5, 12), (8, 15), (11, 20), (12, 15), (12, 18)):
        assert admitted.iso_date(month, day) == f"{year}-{month:02d}-{day:02d}"
    assert admitted.noon_utc(12, 31) == f"{year}-12-31T12:00:00+00:00"


@pytest.mark.parametrize("journey", tuple(_JOURNEYS), ids=tuple(_JOURNEYS))
def test_the_year_the_installed_tests_run_clears_every_journey_gate(
    journey: str, authority_root: Path, tmp_path: Path
) -> None:
    """2025 is admitted, so each journey goes on to create its roots and stops only at the absent product."""
    with pytest.raises(FileNotFoundError):
        _JOURNEYS[journey](authority_root, tmp_path, 2025)

    assert list(tmp_path.iterdir()) != []
