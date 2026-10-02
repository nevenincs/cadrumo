"""Modelo 222's explicit root stores its payload against the edition before it.

``aeat-dr-222-2025`` restructures the 2023-2024 record, so the edition it governs
declares no predecessor. That decides legal continuity only: the casillas both
designs lay out are stored as overrides of the earlier edition, and the edition
states in full only the boxes the earlier design lacks. Their order on the 2025
record is kept by explicit positions, since storage reuse appends what it adds.
"""

from __future__ import annotations

import shutil
from collections.abc import Mapping
from pathlib import Path

import pytest
import tomlkit

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.revision_contracts import NoPredecessor, NoPredecessorCause
from cadrumo.domain.calculations.registry.revision_order import ordered_revisions
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition

from ..compiler.loader import load_modelo_declarations, load_modelo_directory
from ..edition_delta_migration import assess_migration_state

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO_ID = "222"
#: Every unnumbered Informacion adicional slot moves by the space the six added
#: tier boxes take on DR22202, which is what makes the root's structure differ.
_INFORMACION_ADICIONAL_SHIFT = 78


def _modelo_dir() -> Path:
    return Path(bundled_path("registry", "aeat", "modelos", _MODELO_ID))


def _root_and_baseline(modelo: ModeloDefinition) -> tuple[ModeloRevision, ModeloRevision]:
    ordered = ordered_revisions(modelo)
    roots = [
        (position, revision)
        for position, revision in enumerate(ordered)
        if position and isinstance(revision.predecessor, NoPredecessor)
    ]
    assert len(roots) == 1, [str(revision.id) for _, revision in roots]
    position, root = roots[0]
    return root, ordered[position - 1]


def _ids(revision: ModeloRevision) -> list[str]:
    return [str(casilla.id) for casilla in revision.casillas]


def _casilla(revision: ModeloRevision, casilla_id: str) -> CasillaDefinition:
    return next(casilla for casilla in revision.casillas if str(casilla.id) == casilla_id)


def test_the_root_keeps_its_structural_cause_and_reuses_the_edition_before_it() -> None:
    root, baseline = _root_and_baseline(load_modelo_directory(_modelo_dir()))
    assert isinstance(root.predecessor, NoPredecessor)
    assert root.predecessor.cause is NoPredecessorCause.official_structure_differs
    assert str(root.casilla_storage_baseline) == str(baseline.id)
    assert str(root.family_storage_baseline) == str(baseline.id)


def test_the_root_states_only_the_casillas_its_baseline_lacks() -> None:
    root, baseline = _root_and_baseline(load_modelo_directory(_modelo_dir()))
    revisions = load_modelo_declarations(_modelo_dir())["revisions"]
    assert isinstance(revisions, Mapping)
    raw_root = revisions[str(root.id)]
    assert isinstance(raw_root, Mapping)
    rows = raw_root["casillas"]
    assert isinstance(rows, list | tuple)
    stated = [str(row["id"]) for row in rows if isinstance(row, Mapping)]
    assert len(stated) == len(rows)
    new_on_root = [casilla_id for casilla_id in _ids(root) if casilla_id not in set(_ids(baseline))]
    assert new_on_root
    assert sorted(stated) == sorted(new_on_root)


def test_the_root_keeps_its_record_order_over_the_reused_storage() -> None:
    root, baseline = _root_and_baseline(load_modelo_directory(_modelo_dir()))
    order = _ids(root)
    shared = set(_ids(baseline))
    assert [casilla_id for casilla_id in order if casilla_id in shared] == _ids(baseline)
    # aeat-dr-222-2025 prints [67] after [06] on DR22201 and the tier 3 and 4
    # boxes [61] to [66] after [25] on DR22202.
    assert order[order.index("06") + 1] == "67"
    after_25 = order.index("25") + 1
    assert order[after_25 : after_25 + 6] == ["61", "62", "63", "64", "65", "66"]


def test_shared_casillas_carry_the_root_design_where_it_differs() -> None:
    root, baseline = _root_and_baseline(load_modelo_directory(_modelo_dir()))
    slots = [casilla for casilla in baseline.casillas if "informacion_adicional" in casilla.section]
    assert slots
    for slot in slots:
        base_start, base_end = (int(bound) for bound in str(slot.number).split("-"))
        root_start, root_end = (int(bound) for bound in str(_casilla(root, str(slot.id)).number).split("-"))
        assert (root_start - base_start, root_end - base_end) == (_INFORMACION_ADICIONAL_SHIFT,) * 2, slot.id
    # The 2023-2024 instructions compute [23] as [19] - [20]; from 2025 [19] sums
    # the four tier bases, so [23] is filer input.
    assert _casilla(baseline, "23").formula is not None
    assert _casilla(root, "23").formula is None
    assert _casilla(root, "23").input_kind == "manual"


def test_the_live_root_restates_nothing_it_could_inherit() -> None:
    assessment = assess_migration_state(_modelo_dir())
    assert assessment.blocked_work == ()
    assert assessment.unresolved_duplication == ()


def test_an_override_restating_its_baseline_is_detected(tmp_path: Path) -> None:
    modelo = load_modelo_directory(_modelo_dir())
    root, baseline = _root_and_baseline(modelo)
    copy = tmp_path / _MODELO_ID
    shutil.copytree(_modelo_dir(), copy)
    manifest = copy / "revisions" / str(root.id) / "revision.toml"
    document = tomlkit.parse(manifest.read_text(encoding="utf-8"))
    overrides = document["revisions"][str(root.id)]["casilla_overrides"]
    target = next(override for override in overrides if override["selector"]["id"] == "01")
    target["fields"]["number"] = str(_casilla(baseline, "01").number)
    manifest.write_text(tomlkit.dumps(document), encoding="utf-8", newline="\n")

    findings = [
        (item.get("member"), item.get("fields"), item.get("reason"))
        for item in assess_migration_state(copy).unresolved_duplication
    ]
    assert findings == [("01", ["number"], "authored override equals hydrated baseline")]
