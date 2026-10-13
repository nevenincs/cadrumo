"""Replay the declaration's launch-profile vectors through an independent Python reading of the profiles."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from dev._paths import REPO_ROOT

from ..application_environment import (
    ApplicationEnvironment,
    LaunchRefusedError,
    compile_section,
    load,
    reference_define,
    reference_select,
)
from ..generate import generate
from ..layout import load_layout

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_DECLARATION = load(REPO_ROOT)
_PLACES = {
    "windows": ("C:\\launch-vector\\package", "C:\\launch-vector\\state", "windows-x86-64"),
    "posix": ("/launch-vector/package", "/launch-vector/state", "linux-x86-64"),
}


def _normal(family: str, value: str) -> str:
    return value.replace("\\", "/") if family == "windows" else value


def _replay(declaration: ApplicationEnvironment, vector: Mapping[str, Any]) -> list[str]:
    """Return every disagreement between a vector and the reference reading."""
    family = vector["platform"]
    package, root, target = _PLACES[family]
    try:
        profile = reference_select(declaration, family, vector["image"], vector["arguments"])
        defined = reference_define(
            declaration,
            family,
            profile,
            vector["ambient"],
            package=package,
            root=root,
            layout_paths=load_layout(target)["paths"],
            suffix=load_layout(target)["entrypoint_suffix"],
        )
    except LaunchRefusedError as refused:
        expected = vector["refusal"]
        outcome = {"code": refused.code, "subject": refused.subject}
        return [] if outcome == expected else [f"refused {outcome}, expected {expected}"]
    if vector["refusal"] is not None:
        return [f"defined {profile}, expected refusal {vector['refusal']}"]
    problems = [] if profile == vector["profile"] else [f"selected {profile}, expected {vector['profile']}"]
    separator = ";" if family == "windows" else ":"
    actual = dict(defined)
    if vector["path"] is not None:
        path = [_normal(family, entry) for entry in actual.pop("PATH", "").split(separator)]
        if path != [_normal(family, entry) for entry in vector["path"]]:
            problems.append(f"PATH {path} != {vector['path']}")
    expected = {name: _normal(family, value) for name, value in vector["environment"].items()}
    actual = {name: _normal(family, value) for name, value in actual.items()}
    if actual != expected:
        problems.append(
            f"environment differs: extra {set(actual) - set(expected)}, missing {set(expected) - set(actual)}"
        )
        problems.extend(
            f"{name}: {actual[name]} != {value}" for name, value in expected.items() if actual.get(name, value) != value
        )
    return problems


@pytest.mark.parametrize("vector", _DECLARATION.launch_vectors, ids=lambda vector: vector["name"])
def test_python_reading_reproduces_every_launch_vector(vector: Mapping[str, Any]) -> None:
    assert _replay(_DECLARATION, vector) == []


def test_vectors_cover_the_closed_environment_and_the_kdf_child_on_both_families() -> None:
    by_family: dict[str, list[Mapping[str, Any]]] = {"windows": [], "posix": []}
    for vector in _DECLARATION.launch_vectors:
        by_family[vector["platform"]].append(vector)
    for vectors in by_family.values():
        assert {"python", "kdf-child"} <= {vector["profile"] for vector in vectors}
        closed = [vector for vector in vectors if vector["profile"] == "python" and vector["arguments"]]
        # The generic interpreter clears every name under the agent's prefix.
        agent = [name for vector in closed for name in vector["ambient"] if name.startswith("CADRUMO_AGENT_")]
        assert agent and not any(
            name.startswith("CADRUMO_AGENT_") for vector in closed for name in vector["environment"]
        )
        inherited = next(vector for vector in vectors if vector["profile"] == "kdf-child")
        assert inherited["environment"] == inherited["ambient"] and inherited["path"] is None


def test_the_replay_detects_a_planted_disagreement() -> None:
    vector = dict(next(vector for vector in _DECLARATION.launch_vectors if vector["profile"] == "python"))
    vector["environment"] = {**vector["environment"], "CADRUMO_AGENT_PORT": "0"}
    assert _replay(_DECLARATION, vector)
    vector = dict(next(vector for vector in _DECLARATION.launch_vectors if vector["profile"] == "kdf-child"))
    vector["profile"] = "python"
    assert _replay(_DECLARATION, vector)


@pytest.mark.parametrize("target", ["windows-x86-64", "linux-x86-64"])
def test_the_contract_carries_the_target_familys_vectors(tmp_path: Path, target: str) -> None:
    generate(REPO_ROOT, tmp_path, target=target)
    section = json.loads((tmp_path / "contract.json").read_text(encoding="utf-8"))["application_environment"]
    family = "windows" if target.startswith("windows") else "posix"
    expected = [vector["name"] for vector in _DECLARATION.launch_vectors if vector["platform"] == family]
    assert [vector["name"] for vector in section["vectors"]] == expected
    assert section == compile_section(_DECLARATION, load_layout(target))
    generated = (tmp_path / "contract.rs").read_text(encoding="utf-8")
    assert generated.count("    LaunchVector { name: ") == len(expected)
