"""Proofs for the below-supported-floor generated-tree disposition class.

A below-floor row explains a tree nobody can regenerate: every filing year its
revision declares lies under the registry-wide floor, so revision selection
admits no coordinate and the publisher refuses before comparing anything. The
row must therefore be pinned to the floor the legal tree actually declares, and
must fail the day that exclusion stops holding.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import rtoml
from pydantic import ValidationError

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.core.toml import parse_toml

from ..compiler.loader import load_modelo_directory
from .generated_tree_dispositions import (
    GeneratedTreeBelowSupportedFilingYearsDisposition,
    below_floor_dispositions,
    disposition_ledger_from_path,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _declared_floor() -> int:
    payload = parse_toml(
        bundled_path("registry", "aeat", "legal", "supported-filing-years.toml").read_text("utf-8"),
    )
    return int(payload["supported_filing_years"]["floor"])


def _row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "kind": "below_floor",
        "modelo": "232",
        "revision": "2016-2017",
        "source_ref": "aeat-dr-232-2016",
        "source_sha256": "a" * 64,
        "supported_filing_years_floor": 2022,
        "revision_last_filing_year": 2017,
        "reason": "every declared filing year lies below the floor",
        "reconsideration_condition": "the floor is lowered or the revision is retired",
    }
    row.update(overrides)
    return row


def test_a_row_whose_revision_reaches_the_floor_is_refused() -> None:
    """The tooth: an exclusion that no longer holds cannot be declared."""
    with pytest.raises(ValidationError, match="is not below supported_filing_years_floor"):
        GeneratedTreeBelowSupportedFilingYearsDisposition.model_validate(
            _row(revision_last_filing_year=2022),
        )


def test_a_row_below_the_floor_validates() -> None:
    """The supported shape stands, so the refusal above is not a blanket one."""
    row = GeneratedTreeBelowSupportedFilingYearsDisposition.model_validate(_row())
    assert row.subject == "232/2016-2017"


def test_a_dormant_row_is_refused_through_the_ledger_loader(tmp_path: Path) -> None:
    """The refusal reaches the ledger boundary, proven on an isolated fixture."""
    fixture = tmp_path / "generated_tree_dispositions.toml"
    fixture.write_text(
        rtoml.dumps({"schema_version": 4, "dispositions": [_row(revision_last_filing_year=2030)]}, pretty=True),
        encoding="utf-8",
    )
    with pytest.raises(ValidationError, match="is not below supported_filing_years_floor"):
        disposition_ledger_from_path(fixture)

    fixture.write_text(
        rtoml.dumps({"schema_version": 4, "dispositions": [_row()]}, pretty=True),
        encoding="utf-8",
    )
    assert len(disposition_ledger_from_path(fixture)) == 1


def test_every_shipped_below_floor_row_names_the_declared_floor_and_its_revision() -> None:
    """A shipped row pins the live floor and the revision's own newest filing year."""
    floor = _declared_floor()
    for row in below_floor_dispositions():
        assert row.supported_filing_years_floor == floor, (
            f"{row.subject}: row pins floor {row.supported_filing_years_floor}, the registry declares {floor}"
        )
        modelo = load_modelo_directory(
            bundled_path("registry", "aeat", "modelos", row.modelo),
        )
        revision = modelo.revisions[row.revision]
        declared_years = tuple(revision.period_selector.years)
        assert max(declared_years) == row.revision_last_filing_year, (
            f"{row.subject}: row pins {row.revision_last_filing_year}, the revision declares {declared_years}"
        )
        assert max(declared_years) < floor, f"{row.subject}: the revision is no longer below the floor"
