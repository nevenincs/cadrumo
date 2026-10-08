"""Lineage stage refusals and one-to-one writes at their owning package boundary."""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.casilla_lineage import CasillaLineageOrigin
from cadrumo.domain.calculations.registry.revision_order import ordered_revisions
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_references import PeriodSelector
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition

from ...compiler.loader import load_shared_catalogues
from ..casilla_lineage_seed_absence import classify_absence
from ..casilla_lineage_seed_chain_writing import write_chain
from ..casilla_lineage_seed_design import DesignOracle
from ..casilla_lineage_seed_modelo_planner import _ModeloPlanner
from ..casilla_lineage_seed_pair_walk import walk_pair
from ..casilla_lineage_seed_ruling_application import apply_ruling
from ..casilla_lineage_seed_stamp_settlement import partial_stamp_records, settle_partial_stamps
from ..casilla_lineage_seed_types import (
    Ruling,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _casilla(**updates: object) -> CasillaDefinition:
    payload: dict[str, object] = {
        "id": "01",
        "number": "01",
        "localization_keys": ("modelo.schema.test.casilla.01.label",),
        "section": ("liquidacion",),
        "semantic_role": "base_imponible",
        "legal_refs": ("ley-35-2006:art-25",),
        "source_refs": ("aeat-dr-123-2024-v20",),
    }
    payload.update(updates)
    return CasillaDefinition.model_validate(payload)


_PLANTED = "999"


def _oracle() -> DesignOracle:
    return DesignOracle(load_shared_catalogues(bundled_path("registry", "aeat")).sources)


_NO_PREDECESSOR = {
    "none": {
        "reason": "a parallel scheme variant taking effect alongside its siblings",
        "legal_refs": ("ley-58-2003:art-29",),
        "source_refs": ("aeat-manual",),
    },
}


def _revision(
    revision_id: str,
    valid_from: date,
    valid_to: date | None,
    years: tuple[int, ...],
    casillas: tuple[CasillaDefinition, ...],
    *,
    no_predecessor: bool = False,
) -> ModeloRevision:
    payload: dict[str, object] = {
        "id": revision_id,
        "localization_key": f"modelo.schema.test.revision.{revision_id}.label",
        "valid_from": valid_from,
        "valid_to": valid_to,
        "period_selector": PeriodSelector(years=years, periods=("0A",)),
        "legal_refs": ("ley-58-2003:art-29",),
        "source_refs": ("aeat-manual",),
        "casillas": casillas,
    }
    if no_predecessor:
        payload["predecessor"] = _NO_PREDECESSOR
    return ModeloRevision.model_validate(payload)


def _planted_modelo(*revisions: ModeloRevision) -> ModeloDefinition:
    return ModeloDefinition.model_validate(
        {
            "id": _PLANTED,
            "title_localization_key": "modelo.schema.test.modelo.title",
            "official_name_localization_key": "modelo.schema.test.modelo.official_name",
            "tax_domain": "irpf",
            "cadence": "annual",
            "jurisdiction": "ES-AEAT",
            "legal_refs": ("ley-58-2003:art-29",),
            "source_refs": ("aeat-manual",),
            "revisions": {revision.id: revision for revision in revisions},
        },
    )


def test_split_lineage_stages_preserve_refusal_and_one_to_one_chain_boundaries() -> None:
    """The extracted public stages enforce their own evidence and cardinality guards."""
    previous = _revision("2023", date(2023, 1, 1), date(2023, 12, 31), (2023,), (_casilla(),))
    successor = _revision("2024", date(2024, 1, 1), None, (2024,), (_casilla(),))
    planner = _ModeloPlanner(_PLANTED, _planted_modelo(previous, successor), _oracle(), [], frozenset())
    claimed: set[str] = set()
    assert (
        write_chain(
            planner,
            previous.casillas[0],
            successor.casillas[0],
            ("2023", "2024"),
            CasillaLineageOrigin.SEEDED,
            None,
            claimed,
        )
        is None
    )
    assert set(planner.plan.edits) == {("2023", "01"), ("2024", "01")}
    repeated_refusal = write_chain(
        planner,
        previous.casillas[0],
        successor.casillas[0],
        ("2023", "2024"),
        CasillaLineageOrigin.SEEDED,
        None,
        claimed,
    )
    assert repeated_refusal is not None and "one-to-one" in repeated_refusal
    assert settle_partial_stamps(planner) == frozenset()
    assert partial_stamp_records(planner, frozenset()) == ()

    missing = _absence_modelo(origin=None)
    before, after = ordered_revisions(missing)
    before = before.model_copy(update={"casillas": ()})
    after = after.model_copy(update={"casillas": (after.casillas[-1],)})
    missing = _planted_modelo(before, after)
    walker = _ModeloPlanner(_PLANTED, missing, _oracle(), [], frozenset())
    walk_pair(walker, before, after)
    assert walker.plan.refusals and not walker.plan.edits
    direct = _ModeloPlanner(_PLANTED, missing, _oracle(), [], frozenset())
    classify_absence(direct, before, after, after.casillas[0], "unreadable", "unreadable", "unreadable")
    assert direct.plan.refusals and not direct.plan.edits

    held = _held_modelo(origin=None)
    held_before, held_after = ordered_revisions(held)
    ruled = _ModeloPlanner(_PLANTED, held, _oracle(), [], frozenset())
    handled = apply_ruling(
        ruled, _held_pair_ruling(str(held_before.id), str(held_after.id)), held_before, held_after, set()
    )
    assert handled
    assert ruled.plan.refusals and not ruled.plan.edits


_HELD_STEM = "planted-held"
_HELD_ROW = f"{_HELD_STEM}-02"


_HELD_REASON = "a positional convention the record design cannot settle"


_NEW_EVIDENCE = "disenos_registro/modelo_999/files/2024.txt:12 box [02] first printed in the successor design"


def _held_modelo(*, origin: CasillaLineageOrigin | None) -> ModeloDefinition:
    """Two editions where the successor adds one row matching a held stem, with or without an origin."""
    updates: dict[str, object] = {"id": _HELD_ROW, "number": "02", "semantic_role": "importe_planted"}
    if origin is not None:
        updates["continuidad_origin"] = origin.value
        updates["continuidad_evidence"] = _NEW_EVIDENCE
    return _planted_modelo(
        _revision("2023", date(2023, 1, 1), date(2023, 12, 31), (2023,), (_casilla(),)),
        _revision("2024", date(2024, 1, 1), date(2024, 12, 31), (2024,), (_casilla(), _casilla(**updates))),
    )


def _held_pair_ruling(predecessor: str, successor: str) -> Ruling:
    """The same hold, named as one adjudicated pair rather than by stem."""
    return Ruling(
        predecessor=predecessor,
        successor=successor,
        refuse_bare=False,
        rationale="planted for this gate",
        grounded=(),
        new_on_form=frozenset(),
        new_on_form_stems=frozenset(),
        not_on_form=frozenset(),
        held=(("01", _HELD_ROW),),
        held_stems=frozenset(),
        held_reason=_HELD_REASON,
        withheld=(),
        withheld_reason="",
        merged=(),
        merged_reason="",
        discontinued=frozenset(),
    )


_ABSENT_ROW = "planted-absent"


_ABSENT_EVIDENCE = "disenos_registro/modelo_999/files/2023.txt:7 box [02] printed; the 2023 edition declares no row"


def _absence_modelo(*, origin: CasillaLineageOrigin | None) -> ModeloDefinition:
    """Two editions where the successor adds a row with no predecessor and no printed box."""
    updates: dict[str, object] = {
        "id": _ABSENT_ROW,
        # A byte range is not a printed box, so no record design can classify the absence.
        "number": "0001-0010",
        "semantic_role": "importe_planted",
    }
    if origin is not None:
        updates["continuidad_origin"] = origin.value
        updates["continuidad_evidence"] = _ABSENT_EVIDENCE
    return _planted_modelo(
        _revision("2023", date(2023, 1, 1), date(2023, 12, 31), (2023,), (_casilla(),)),
        _revision("2024", date(2024, 1, 1), date(2024, 12, 31), (2024,), (_casilla(), _casilla(**updates))),
    )
