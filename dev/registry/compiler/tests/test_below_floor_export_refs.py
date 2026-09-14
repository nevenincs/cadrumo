"""Teeth for the below-floor downgrade of export binding-reference refusals.

Every case runs the REAL export validator over the shipped Modelo 232 tree and
the REAL disposition ledger loader over a COPY of the shipped ledger, so the
honoured row, the refusals it covers, and the conditions that retire it are the
live ones. Modelo 232's ``2016-2017`` revision is the carrier: its only filing
years are 2016 and 2017 against a declared floor of 2022, and its shipped export
tree quotes binding spellings the revision no longer declares.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import rtoml

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.revision_context import build_revision_validation_context
from cadrumo.domain.calculations.registry.schema import ModeloRevision

from ...conformance.stamp import bundled_registry_root
from ...pipeline.generated_tree_dispositions import disposition_ledger_from_path
from ..loader import load_modelo_directory, load_shared_catalogues
from ..validate_below_floor_export_refs import (
    below_floor_export_reference_advisories,
    declared_supported_filing_years_floor,
)
from ..validate_evidence import EvidenceValidator
from ..validate_exports import validate_export_layout_section

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO = "232"
_REVISION = "2016-2017"
_LEDGER = Path(__file__).resolve().parents[2] / "pipeline" / "generated_tree_dispositions.toml"


def _shipped_revision() -> ModeloRevision:
    """Return the shipped below-floor revision through the real loader."""
    return load_modelo_directory(bundled_registry_root() / "modelos" / _MODELO).revisions[_REVISION]


def _export_failures(revision: ModeloRevision) -> list[str]:
    """Return the real export-section failures for one revision, undowngraded."""
    catalogues = load_shared_catalogues(bundled_registry_root())
    context = build_revision_validation_context(revision)
    return validate_export_layout_section(
        prefix=f"modelo {_MODELO} revision {_REVISION}",
        revision=revision,
        casillas=context.casillas,
        bindings=context.bindings,
        casilla_by_id=context.casilla_by_id,
        legal_refs=catalogues.legal,
        source_refs=catalogues.sources,
        evidence=EvidenceValidator(
            legal_refs=catalogues.legal,
            source_refs=catalogues.sources,
            source_root=bundled_path(),
        ),
        source_root=bundled_path(),
    )


def _ledger_copy(tmp_path: Path) -> Path:
    """Copy the shipped disposition ledger into an isolated tree."""
    copied = tmp_path / "generated_tree_dispositions.toml"
    shutil.copyfile(_LEDGER, copied)
    return copied


def _rewritten_below_floor_row(tmp_path: Path, **changes: object) -> Path:
    """Copy the ledger, re-declaring the carrier's below-floor row, or dropping it."""
    data = rtoml.load(_LEDGER)
    rows = []
    for row in data["dispositions"]:
        is_carrier = row.get("kind") == "below_floor" and row["modelo"] == _MODELO and row["revision"] == _REVISION
        if not is_carrier:
            rows.append(row)
            continue
        if changes:
            rows.append({**row, **changes})
    data["dispositions"] = rows
    written = tmp_path / "generated_tree_dispositions.toml"
    written.write_text(rtoml.dumps(data), encoding="utf-8")
    return written


def test_the_shipped_row_downgrades_every_dangling_export_reference_and_counts_it() -> None:
    """The honoured row must move the refusals onto one advisory that states how many."""
    failures = _export_failures(_shipped_revision())
    dangling = [line for line in failures if "references unknown binding" in line]
    assert dangling

    kept, advisories = below_floor_export_reference_advisories(
        failures,
        modelo_id=_MODELO,
        revision_id=_REVISION,
        ledger_path=_LEDGER,
    )

    assert [line for line in kept if "references unknown binding" in line] == []
    assert len(advisories) == 1
    assert f"export tree of {_MODELO}/{_REVISION} is below the supported-filing-years floor" in advisories[0]
    assert f"({declared_supported_filing_years_floor()})" in advisories[0]
    assert f"{len(dangling)} references to superseded binding spellings are not a refusal" in advisories[0]


def test_without_the_row_the_same_revision_still_refuses(tmp_path: Path) -> None:
    """The downgrade must come from the declaration, not from the revision being old."""
    failures = _export_failures(_shipped_revision())
    dangling = [line for line in failures if "references unknown binding" in line]

    kept, advisories = below_floor_export_reference_advisories(
        failures,
        modelo_id=_MODELO,
        revision_id=_REVISION,
        ledger_path=_rewritten_below_floor_row(tmp_path),
    )

    assert advisories == ()
    assert [line for line in kept if "references unknown binding" in line] == dangling


def test_a_row_pinned_to_a_floor_the_registry_no_longer_declares_is_not_honoured(tmp_path: Path) -> None:
    """A stale floor describes a registry that no longer exists, so the refusals return.

    The recorded floor is lowered to 2018, which the ledger loader still accepts
    because 2017 stays below it. What retires the row here is the live
    declaration: the legal tree says 2022, and a row written against a different
    floor no longer explains this registry.
    """
    failures = _export_failures(_shipped_revision())
    dangling = [line for line in failures if "references unknown binding" in line]
    ledger_path = _rewritten_below_floor_row(tmp_path, supported_filing_years_floor=2018)
    assert disposition_ledger_from_path(ledger_path)

    kept, advisories = below_floor_export_reference_advisories(
        failures,
        modelo_id=_MODELO,
        revision_id=_REVISION,
        ledger_path=ledger_path,
    )

    assert advisories == ()
    assert [line for line in kept if "references unknown binding" in line] == dangling


def test_a_row_whose_revision_the_floor_no_longer_excludes_is_refused_by_the_ledger(tmp_path: Path) -> None:
    """Lowering the floor under the revision retires the row at the loader itself."""
    ledger_path = _rewritten_below_floor_row(tmp_path, supported_filing_years_floor=2017)

    with pytest.raises(ValueError, match="must be retired rather than kept"):
        disposition_ledger_from_path(ledger_path)


def test_the_downgrade_leaves_unrelated_export_failures_standing() -> None:
    """Only the binding-reference lines are covered; anything else still refuses."""
    unrelated = f"modelo {_MODELO} revision {_REVISION}: export field 'x' literal length 4 exceeds declared length 2"

    kept, advisories = below_floor_export_reference_advisories(
        [*_export_failures(_shipped_revision()), unrelated],
        modelo_id=_MODELO,
        revision_id=_REVISION,
        ledger_path=_LEDGER,
    )

    assert len(advisories) == 1
    assert unrelated in kept
