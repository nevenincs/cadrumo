"""Immutable Modelo 303 filing-evidence CLI boundary checks."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import typer

from ....core import Period
from .._m303_filing_evidence_input import m303_filing_instance_evidence_from_cli
from ._m303_filing_evidence_support import default_insolvency_fact, write_m303_filing_evidence

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _write_evidence(path: Path, period: Period, *, joint_return_elected: bool = True) -> None:
    write_m303_filing_evidence(
        path,
        period,
        joint_return_elected=joint_return_elected,
        insolvency=default_insolvency_fact(),
    )


def test_cli_loads_complete_m303_evidence_before_revision_creation(tmp_path: Path) -> None:
    period = Period.from_year_and_code(2026, "1T")
    evidence_path = tmp_path / "m303-filing-evidence.json"
    _write_evidence(evidence_path, period)

    evidence = m303_filing_instance_evidence_from_cli(
        modelo="303",
        period=period,
        evidence_file=evidence_path,
    )

    assert evidence is not None
    assert evidence.m303.period == period
    assert evidence.m303.joint_return_elected is True
    assert evidence.m303.insolvency is not None
    assert evidence.m303.insolvency.judicial_order_date == date(2026, 2, 3)


def test_m303_creation_refuses_an_absent_evidence_document() -> None:
    with pytest.raises(typer.BadParameter):
        m303_filing_instance_evidence_from_cli(
            modelo="303",
            period=Period.from_year_and_code(2026, "1T"),
            evidence_file=None,
        )
