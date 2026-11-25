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
from cadrumo.domain.calculations.registry.tests.authored_editions import open_ended_revision

from ...compiler.loader import load_modelo_directory
from ...conformance.stamp import bundled_registry_root
from ..delta_minimality import definition_findings, edition_predecessors
from ..edition_minimality_lanes import (
    definitions_minimality_reasons,
    delta_minimality_reasons,
    edition_assessment_reasons,
)
from ..registry_status import RegistryStatus, registry_status_payload

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: Modelo 131 states each casilla of an edition as an override of its predecessor's
#: row; dropping one override leaves a row the loader proves the edition would inherit.
_DELTA_MODELO = "131"
_OVERRIDDEN_ROW = "modulos-epigrafe"

#: Modelo 216 states its verification expectation as an override of the earlier
#: member; adding a leaf equal to that member's own value makes it redundant.
_ASSESSED_MODELO = "216"
_OVERRIDE_LEAF = 'tolerance = "0.01", source_refs'
_REDUNDANT_LEAF = 'tolerance = "0.01", rounding = "money-2", source_refs'


def _stated_override(successor: str, prior: str, revision_toml: str) -> str | None:
    """Return the override block the successor edition states against ``prior`` for the row, if any."""
    header = f'[[revisions."{successor}".casilla_overrides]]\n'
    selector = f'selector = {{ revision = "{prior}", id = "{_OVERRIDDEN_ROW}" }}\n'
    start = revision_toml.find(header + selector)
    if start < 0:
        return None
    end_marker = "removed_fields = []\n\n"
    end = revision_toml.find(end_marker, start)
    return None if end < 0 else revision_toml[start : end + len(end_marker)]


def _delta_editions() -> tuple[str, str, str]:
    """Return the newest edition of modelo 131 declaring a predecessor and overriding its row: prior, own, block."""
    revisions_root = bundled_registry_root() / "modelos" / _DELTA_MODELO / "revisions"
    definition = load_modelo_directory(revisions_root.parent)
    for edition in reversed(edition_predecessors(definition)):
        if edition.predecessor is None:
            continue
        text = (revisions_root / edition.revision / "revision.toml").read_text(encoding="utf-8")
        block = _stated_override(edition.revision, edition.predecessor, text)
        if block is not None:
            return edition.predecessor, edition.revision, block
    raise LookupError(f"modelo {_DELTA_MODELO} states no edition as an override of its predecessor")


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
    """Modelo 131 with its newest overriding edition stating a row the loader proves it would inherit."""
    prior, successor_id, override = _delta_editions()
    modelo_dir = _registry_copy(tmp_path, _DELTA_MODELO) / "modelos" / _DELTA_MODELO
    _rewrite(modelo_dir / "revisions" / successor_id / "revision.toml", override, "")
    inheriting = load_modelo_directory(modelo_dir)
    assert definition_findings(inheriting, modelo_id=_DELTA_MODELO) == ()
    successor = inheriting.revisions[successor_id]
    row = next(item for item in successor.casillas if str(item.id) == _OVERRIDDEN_ROW)
    assert row.inherited_from == prior
    stated = row.model_copy(update={"inherited_from": None})
    rows = tuple(stated if item is row else item for item in successor.casillas)
    return inheriting.model_copy(
        update={"revisions": {**inheriting.revisions, successor_id: successor.model_copy(update={"casillas": rows})}}
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

    revision = (
        registry_root
        / "modelos"
        / _ASSESSED_MODELO
        / "revisions"
        / open_ended_revision(_ASSESSED_MODELO).id
        / "revision.toml"
    )
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
