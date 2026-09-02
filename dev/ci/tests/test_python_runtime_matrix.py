"""Detector-teeth tests for the explicit CPython runtime inventory."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from ..python_runtime_matrix import (
    RuntimeMatrixError,
    RuntimePhase,
    github_matrix,
    load_runtime_inventory,
    main,
    parse_runtime_inventory,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_INVENTORY_PATH = Path(__file__).parents[1] / "python-runtime-matrix.json"


def _live_payload() -> dict[str, Any]:
    """Load the checked-in declaration as the valid control specimen."""
    return json.loads(_INVENTORY_PATH.read_text(encoding="utf-8"))


def test_live_inventory_is_complete_and_emits_one_canary() -> None:
    """The real declaration covers the floor-to-current sequence plus one next row."""
    inventory = load_runtime_inventory(_INVENTORY_PATH)

    assert inventory.minimum_minor == "3.13"
    assert inventory.current_stable_minor == "3.14"
    assert [row.minor for row in inventory.stable] == ["3.13", "3.14"]
    assert inventory.next.minor == "3.15"
    assert inventory.next.phase is RuntimePhase.PRERELEASE
    assert inventory.next.blocking is False
    assert inventory.next.classifier_eligible is False


def test_matrix_projection_keeps_stable_and_canary_verdict_dimensions() -> None:
    """GitHub receives every declared row and does not lose its lifecycle flags."""
    matrix = github_matrix(parse_runtime_inventory(_live_payload()))

    rows = matrix["include"]
    assert [row["runtime-id"] for row in rows] == ["cp313", "cp314", "cp315-next"]
    assert [row["python-version"] for row in rows] == ["3.13", "3.14", "3.15.0-rc.2"]
    assert [row["phase"] for row in rows] == ["stable", "stable", "prerelease"]
    assert [row["blocking"] for row in rows] == [True, True, False]
    assert [row["classifier-eligible"] for row in rows] == [True, False, False]


def test_missing_stable_minor_is_refused() -> None:
    """Deleting a released row cannot make the matrix silently under-declared."""
    payload = _live_payload()
    payload["stable"].pop(0)

    with pytest.raises(RuntimeMatrixError, match="must list every released minor"):
        parse_runtime_inventory(payload)


def test_duplicate_stable_row_is_refused() -> None:
    """Repeating a row is not an alternative proof of the same interpreter."""
    payload = _live_payload()
    payload["stable"].append(copy.deepcopy(payload["stable"][0]))

    with pytest.raises(RuntimeMatrixError, match="must list every released minor"):
        parse_runtime_inventory(payload)


def test_duplicate_identifier_is_refused_before_matrix_emission() -> None:
    """Two different minors may not share a runtime identity."""
    payload = _live_payload()
    payload["stable"][1]["id"] = payload["stable"][0]["id"]

    with pytest.raises(RuntimeMatrixError, match="stable ids must follow"):
        parse_runtime_inventory(payload)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda payload: payload.pop("next"), "missing"),
        (lambda payload: payload.update(extra=True), "unknown"),
        (lambda payload: payload.__setitem__("schema", "other.v1"), "schema"),
        (lambda payload: payload.__setitem__("minimum_minor", "3.14"), "must list every released minor"),
        (lambda payload: payload["stable"][0].__setitem__("phase", "prerelease"), "phase"),
        (lambda payload: payload["stable"][0].__setitem__("blocking", 1), "boolean"),
        (lambda payload: payload["stable"][0].__setitem__("implementation", "PyPy"), "CPython"),
        (lambda payload: payload["next"].__setitem__("blocking", True), "cannot block"),
        (
            lambda payload: (
                payload["next"].__setitem__("minor", "3.16"),
                payload["next"].__setitem__("selector", "3.16.0-rc.1"),
            ),
            "immediately follow",
        ),
        (lambda payload: payload["next"].__setitem__("selector", "3.15-rc"), "selector"),
    ],
    ids=(
        "missing-next",
        "unknown-top-level-key",
        "unknown-schema",
        "floor-above-listed-row",
        "stable-phase-downgrade",
        "non-boolean-blocking",
        "alternative-implementation",
        "blocking-canary",
        "canary-gap",
        "malformed-selector",
    ),
)
def test_invalid_inventory_states_are_detector_teeth(
    mutation: Any,
    message: str,
) -> None:
    """Each representative declaration defect must be rejected explicitly."""
    payload = _live_payload()
    mutation(payload)

    with pytest.raises(RuntimeMatrixError, match=message):
        parse_runtime_inventory(payload)


def test_cli_returns_nonzero_for_invalid_inventory(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The command surface reports an invalid declaration instead of emitting a matrix."""
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps({"schema": "wrong"}), encoding="utf-8")

    assert main(["--inventory", str(path)]) == 2
    assert "runtime inventory invalid" in capsys.readouterr().err
