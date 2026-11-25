"""The seed's carry lane decides which prior-year facts it brings in, and brings each in once.

The installed CLI is replaced by a recorder here: these tests pin the seed's own
sequencing, not the product's answer to it.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any, override

import pytest

from dev.acceptance.installed_cli import InstalledCli

from ..scenario import YEARS
from ..seed import carried_years
from ..seed_campaign import Seeder
from ..seed_contracts import SeedReceipt

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_ALL_STAGES = ("ledger", "amortization", "withholding", "modelos")
_PRIOR_YEAR, _SEEDED_YEAR = YEARS[-2], YEARS[-1]


class _RecordingCli(InstalledCli):
    """Answers every command with success and keeps the argv it was given."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    @override
    def run(
        self,
        args: Sequence[str],
        *,
        authenticated: bool = True,
        allow_error: bool = False,
        stdin_payload: str | None = None,
        command: str | None = None,
    ) -> dict[str, Any]:
        self.calls.append(tuple(args))
        return {"status": "success", "result": {"provenance": "operator_seed"}}


def _seeder(cli: InstalledCli, tmp_path: Path) -> Seeder:
    receipt_path = tmp_path / "seed-receipt.json"
    receipt = SeedReceipt.load(receipt_path) or SeedReceipt(
        scenario="test", authority_generation="test", executable_sha256="test", carry_evidence="synthetic_csv_register"
    )
    return Seeder(
        cli, receipt=receipt, receipt_path=receipt_path, artifact_dir=tmp_path / "evidence", first_year=_SEEDED_YEAR
    )


def test_the_honest_lane_carries_no_prior_year_evidence() -> None:
    assert carried_years((_SEEDED_YEAR,), stages=_ALL_STAGES, carry_evidence="none") == ()


def test_the_synthetic_lane_carries_only_into_a_year_whose_predecessor_is_not_seeded() -> None:
    assert carried_years((_SEEDED_YEAR,), stages=_ALL_STAGES, carry_evidence="synthetic_csv_register") == (
        _SEEDED_YEAR,
    )
    assert carried_years((_PRIOR_YEAR, _SEEDED_YEAR), stages=_ALL_STAGES, carry_evidence="synthetic_csv_register") == (
        _PRIOR_YEAR,
    )
    assert carried_years((_SEEDED_YEAR,), stages=("ledger",), carry_evidence="synthetic_csv_register") == ()


def test_the_prior_fourth_quarter_compensation_is_declared_as_a_proven_zero(tmp_path: Path) -> None:
    # The prior year's 4T is 879.90 a ingresar, so it leaves nothing to compensate: 0.00, not an absent value.
    cli = _RecordingCli()

    _seeder(cli, tmp_path).carry_m303_compensation(_SEEDED_YEAR)

    assert cli.calls == [
        (
            "app",
            "modelo",
            "iva-wallet",
            "seed",
            "--filing-year",
            str(_PRIOR_YEAR),
            "--period",
            "4T",
            "--amount",
            "0.00",
            "--confirm",
        )
    ]


def test_a_resumed_seed_does_not_declare_the_opening_balance_twice(tmp_path: Path) -> None:
    first, resumed = _RecordingCli(), _RecordingCli()
    _seeder(first, tmp_path).carry_m303_compensation(_SEEDED_YEAR)

    _seeder(resumed, tmp_path).carry_m303_compensation(_SEEDED_YEAR)

    assert len(first.calls) == 1
    assert resumed.calls == []
