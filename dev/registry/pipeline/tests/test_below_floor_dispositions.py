"""Proofs for the below-supported-floor generated-tree disposition class.

A below-floor row describes a runtime selection limit: every filing year its
revision declares lies under the registry-wide floor. An exact official source
can still support a separately validated historical static target without
granting a filing snapshot. A row must be pinned to the legal floor and retire
when its claimed publication impediment is repaired.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import rtoml
from pydantic import ValidationError

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import FilingYearOutsideSupportEnvelopeError
from cadrumo.domain.calculations.registry.temporal import select_revision
from cadrumo.domain.calculations.registry.tests.authored_editions import authored_revisions

from ...compiler.authority import compiled_bundled_authority
from ...compiler.loader import load_modelo_directory
from ..generated_tree_dispositions import (
    GeneratedTreeBelowSupportedFilingYearsDisposition,
    below_floor_dispositions,
    disposition_ledger_from_path,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: Modelo 232's oldest authored revision, whose every filing year lies under the floor.
_M232_REVISION = str(authored_revisions("232")[0].id)


def _declared_floor() -> int:
    return compiled_bundled_authority().supported_filing_years().floor


def _row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "kind": "below_floor",
        "modelo": "232",
        "revision": _M232_REVISION,
        "source_ref": "aeat-dr-232-2016",
        "source_sha256": "a" * 64,
        "supported_filing_years_floor": _declared_floor(),
        "revision_last_filing_year": _declared_floor() - 1,
        "reason": "every declared filing year lies below the floor",
        "reconsideration_condition": "the floor is lowered or the revision is retired",
    }
    row.update(overrides)
    return row


def test_a_row_whose_revision_reaches_the_floor_is_refused() -> None:
    """The tooth: an exclusion that no longer holds cannot be declared."""
    with pytest.raises(ValidationError, match="is not below supported_filing_years_floor"):
        GeneratedTreeBelowSupportedFilingYearsDisposition.model_validate(
            _row(revision_last_filing_year=_declared_floor()),
        )


def test_a_row_below_the_floor_validates() -> None:
    """The supported shape stands, so the refusal above is not a blanket one."""
    row = GeneratedTreeBelowSupportedFilingYearsDisposition.model_validate(_row())
    assert row.subject == f"232/{_M232_REVISION}"


def test_a_dormant_row_is_refused_through_the_ledger_loader(tmp_path: Path) -> None:
    """The refusal reaches the ledger boundary, proven on an isolated fixture."""
    fixture = tmp_path / "generated_tree_dispositions.toml"
    fixture.write_text(
        rtoml.dumps(
            {"schema_version": 4, "dispositions": [_row(revision_last_filing_year=_declared_floor() + 1)]}, pretty=True
        ),
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


def test_repaired_m232_static_target_needs_no_drift_row_or_runtime_filing_admission() -> None:
    """The enrolled static tree reproduces its source while private filing stays below floor."""
    from ..generated_tree_inventory import generated_export_trees

    m232 = load_modelo_directory(bundled_path("registry", "aeat", "modelos", "232"))
    assert max(m232.revisions[_M232_REVISION].period_selector.years) < _declared_floor()
    assert all(row.subject != f"232/{_M232_REVISION}" for row in below_floor_dispositions())
    trees = [tree for tree in generated_export_trees() if (tree.modelo, tree.revision) == ("232", _M232_REVISION)]
    assert len(trees) == 1
    assert (trees[0].period, trees[0].historical_static) == ("0A", True)
    assert trees[0].filing_year < _declared_floor()
    authority = compiled_bundled_authority()
    with pytest.raises(FilingYearOutsideSupportEnvelopeError):
        select_revision(
            authority.modelo("232"),
            filing_year=trees[0].filing_year,
            period="0A",
            support=authority.catalogues.supported_filing_years,
        )
