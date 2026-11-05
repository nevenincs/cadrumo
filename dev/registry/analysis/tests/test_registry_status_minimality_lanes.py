"""The status report gates delta minimality and the all-family assessment as lanes.

Each lane must pass on the shipped source and fail on a defect planted in an
isolated copy of a real modelo tree, so a gate that stopped examining, or that
cannot see the defect it exists for, is caught here rather than read as clean.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.schema import ModeloDefinition

from ...compiler.loader import load_modelo_directory
from ...conformance.stamp import bundled_registry_root
from ..delta_minimality import definition_findings
from ..edition_minimality_lanes import (
    definitions_minimality_reasons,
    delta_minimality_reasons,
    edition_assessment_reasons,
)
from ..registry_status import RegistryStatus, registry_status_payload

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: Modelo 131 states each 2025 casilla as an override of its 2024 row; dropping
#: one override leaves a row the loader proves the edition would inherit.
_DELTA_MODELO = "131"
_OVERRIDE = (
    '[[revisions."2025".casilla_overrides]]\n'
    'selector = { revision = "2024", id = "modulos-epigrafe" }\n'
    'fields = { legal_refs = ["ley-35-2006:art-31", "orden-hac-1347-2024:art-4"] }\n'
    "removed_fields = []\n\n"
)

#: Modelo 216 states its verification expectation as an override of the 2020-2023
#: member; adding a leaf equal to that member's own value makes it redundant.
_ASSESSED_MODELO = "216"
_OVERRIDE_LEAF = 'tolerance = "0.01", source_refs'
_REDUNDANT_LEAF = 'tolerance = "0.01", rounding = "money-2", source_refs'


def _registry_copy(destination: Path, modelo: str) -> Path:
    """Copy one modelo and the catalogues it loads against; return the registry root."""
    bundled_root = bundled_registry_root()
    registry_root = destination / "aeat"
    for catalogue in ("facts", "legal"):
        shutil.copytree(bundled_root / catalogue, registry_root / catalogue)
    shutil.copytree(bundled_root / "modelos" / modelo, registry_root / "modelos" / modelo)
    return registry_root


def _rewrite(path: Path, old: str, new: str) -> None:
    current = path.read_text(encoding="utf-8")
    assert old in current, f"{path} no longer states {old!r}"
    path.write_text(current.replace(old, new, 1), encoding="utf-8")


def _status(*, minimality: tuple[str, ...] = (), assessment: tuple[str, ...] = ()) -> RegistryStatus:
    return RegistryStatus(
        valid=True,
        oracles=True,
        targets=(("current", 1), ("stale", 0), ("drifted", 0), ("never-committed", 0), ("unreadable", 0)),
        target_findings=(),
        authority="current",
        authority_recorded_digest=None,
        authority_candidate_digest=None,
        loadable=True,
        informational_bindings=(),
        details=(),
        delta_minimality_reasons=minimality,
        edition_assessment_reasons=assessment,
    )


def _lanes(payload: dict[str, object]) -> dict[str, str]:
    lanes = payload["lanes"]
    assert isinstance(lanes, dict)
    return {str(name): str(state) for name, state in lanes.items()}


def _restating_131(tmp_path: Path) -> ModeloDefinition:
    """Modelo 131 with its 2025 edition stating a row the loader proves it would inherit."""
    modelo_dir = _registry_copy(tmp_path, _DELTA_MODELO) / "modelos" / _DELTA_MODELO
    _rewrite(modelo_dir / "revisions" / "2025" / "revision.toml", _OVERRIDE, "")
    inheriting = load_modelo_directory(modelo_dir)
    assert definition_findings(inheriting, modelo_id=_DELTA_MODELO) == ()
    successor = inheriting.revisions["2025"]
    row = next(item for item in successor.casillas if str(item.id) == "modulos-epigrafe")
    assert row.inherited_from == "2024"
    stated = row.model_copy(update={"inherited_from": None})
    rows = tuple(stated if item is row else item for item in successor.casillas)
    return inheriting.model_copy(
        update={"revisions": {**inheriting.revisions, "2025": successor.model_copy(update={"casillas": rows})}}
    )


def test_the_shipped_source_holds_both_standing_gates() -> None:
    assert edition_assessment_reasons(bundled_registry_root()) == ()
    payload = registry_status_payload(_status(), blocking=True)
    assert _lanes(payload)["delta_minimality"] == "passed"
    assert _lanes(payload)["edition_delta_assessment"] == "passed"


def test_a_restated_inherited_row_fails_the_delta_minimality_lane(tmp_path: Path) -> None:
    restating = _restating_131(tmp_path)
    reasons = definitions_minimality_reasons({_DELTA_MODELO: restating})
    assert len(reasons) == 1
    assert _DELTA_MODELO in reasons[0]

    payload = registry_status_payload(_status(minimality=reasons), blocking=True)
    assert _lanes(payload)["delta_minimality"] == "failed"
    assert payload["failed_lanes"] == ["delta_minimality"]
    assert payload["result"] == "failed"


def test_a_registry_that_did_not_validate_or_judged_nothing_fails_the_delta_minimality_lane() -> None:
    assert delta_minimality_reasons(None) == (
        "the registry did not validate, so casilla delta minimality was not measured",
    )
    assert definitions_minimality_reasons({}) == ("no casilla row was judged, so minimality was not measured",)


def test_a_redundant_override_leaf_fails_the_assessment_lane_and_removing_it_clears_it(tmp_path: Path) -> None:
    registry_root = _registry_copy(tmp_path, _ASSESSED_MODELO)
    assert edition_assessment_reasons(registry_root) == ()

    revision = registry_root / "modelos" / _ASSESSED_MODELO / "revisions" / "2024-y-siguientes" / "revision.toml"
    _rewrite(revision, _OVERRIDE_LEAF, _REDUNDANT_LEAF)
    reasons = edition_assessment_reasons(registry_root)
    assert len(reasons) == 1
    assert f"modelo {_ASSESSED_MODELO}" in reasons[0]

    payload = registry_status_payload(_status(assessment=reasons), blocking=True)
    assert _lanes(payload)["edition_delta_assessment"] == "failed"
    assert payload["failed_lanes"] == ["edition_delta_assessment"]

    _rewrite(revision, _REDUNDANT_LEAF, _OVERRIDE_LEAF)
    assert edition_assessment_reasons(registry_root) == ()


def test_an_empty_registry_root_fails_the_assessment_lane(tmp_path: Path) -> None:
    (tmp_path / "modelos").mkdir()
    assert edition_assessment_reasons(tmp_path) == (
        "no modelo tree was assessed, so edition delta minimality was not measured",
    )
