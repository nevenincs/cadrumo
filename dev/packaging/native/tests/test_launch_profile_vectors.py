"""Replay the declaration's launch-profile vectors through an independent Python reading of the profiles."""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

import pytest

from dev._paths import REPO_ROOT

from ..application_environment import load, load_for_build
from ..environment_compile import compile_section
from ..environment_models import ApplicationEnvironment
from ..environment_reference import LaunchRefusedError, reference_define, reference_select
from ..generate import generate
from ..layout import load_layout
from .google_identity import PUBLISHER_CLIENT_JSON

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_DECLARATION = load(REPO_ROOT, package_values={"CADRUMO_GOOGLE_OAUTH_CLIENT_JSON": PUBLISHER_CLIENT_JSON})
_PLACES = {
    "windows": ("C:\\launch-vector\\package", "C:\\launch-vector\\state", "windows-x86-64"),
    "posix": ("/launch-vector/package", "/launch-vector/state", "linux-x86-64"),
}


def _normal(family: str, value: str) -> str:
    return value.replace("\\", "/") if family == "windows" else value


def _existing_installation_dirs(
    declaration: ApplicationEnvironment,
    family: str,
    profile: str,
    ambient: Mapping[str, str],
) -> list[str]:
    """Materialize only declared defaults that exist on this host for the vector's roots."""
    # Read the vector's family before the host check below narrows it to this host's literal.
    windows = family == "windows"
    host_family = "windows" if os.name == "nt" else "posix"
    if family != host_family:
        return []
    selected = declaration.profiles[profile]
    if declaration.path_external not in {*selected["operator"], *selected["pass"]}:
        return []
    admitted_base = {name for group in selected["base_groups"] for name in declaration.base[family][group]}
    path_type = PureWindowsPath if windows else PurePosixPath
    existing: list[str] = []
    for default in declaration.external_path_defaults:
        if default.platform in {"windows", "posix"} and default.platform != family:
            continue
        if default.platform == "macos" and sys.platform != "darwin":
            continue
        if default.variable is None:
            candidate = path_type(default.path)
        else:
            if default.variable not in admitted_base:
                continue
            value = next(
                (
                    value
                    for name, value in ambient.items()
                    if (name.upper() == default.variable.upper() if windows else name == default.variable)
                ),
                None,
            )
            if value is None or not path_type(value).is_absolute():
                continue
            candidate = path_type(value).joinpath(*default.subpaths)
        if candidate.is_absolute() and Path(str(candidate)).is_dir():
            existing.append(str(candidate))
    return existing


def _replay(declaration: ApplicationEnvironment, vector: Mapping[str, Any]) -> list[str]:
    """Return every disagreement between a vector and the reference reading."""
    family = vector["platform"]
    package, root, target = _PLACES[family]
    try:
        profile = reference_select(declaration, family, vector["image"], vector["arguments"])
        existing_dirs = _existing_installation_dirs(declaration, family, profile, vector["ambient"])
        defined = reference_define(
            declaration,
            family,
            profile,
            vector["ambient"],
            package=package,
            root=root,
            layout_paths=load_layout(target)["paths"],
            suffix=load_layout(target)["entrypoint_suffix"],
            existing_dirs=existing_dirs,
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
        expected_path = list(vector["path"])
        system_count = 1 if family == "windows" else len(declaration.posix_system)
        insertion = max(0, len(expected_path) - system_count)
        expected_path[insertion:insertion] = existing_dirs
        if path != [_normal(family, entry) for entry in expected_path]:
            problems.append(f"PATH {path} != {expected_path}")
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
        assert inherited["environment"] == {**inherited["ambient"], **_DECLARATION.package_values}
        assert inherited["path"] is None


_AGENT = "cadrumo-agent"
_AGENT_SLOTS = {
    "CADRUMO_LOCAL_STORAGE_ROOT",
    "CADRUMO_AGENT_HOSTED_ROOT",
    "CADRUMO_AGENT_PORT",
    "CADRUMO_AGENT_WORKER_PORT",
}
_STORE_INVOCATIONS = {
    ("stores-state",),
    ("setup",),
    ("version", "--json"),
    ("migrate",),
    ("migrate", "--expect-from", "0001"),
    ("migrate", "--expect-head", "0002_next"),
    ("migrate", "--expect-from", "0001", "--expect-head", "0002_next"),
}


def test_vectors_admit_each_store_and_version_invocation_with_the_gateways_slots_on_both_families() -> None:
    for family in ("windows", "posix"):
        admitted = {
            tuple(vector["arguments"][2:]): vector
            for vector in _DECLARATION.launch_vectors
            if vector["platform"] == family and vector["image"] == _AGENT and vector["profile"] == "agent-gateway"
        }
        assert set(admitted) >= _STORE_INVOCATIONS, family
        for tail in _STORE_INVOCATIONS:
            vector = admitted[tail]
            assert vector["arguments"][:2] == ["-m", "cadrumo_agent.cli.main"]
            # The hosted root, both ports and the storage root all arrive, as for serve.
            assert set(vector["environment"]) >= _AGENT_SLOTS, vector["name"]
            # What the gateway never admits does not arrive under these arguments either, and a name
            # under the agent's prefix that the declaration does not list does.
            never = set(_DECLARATION.profiles["agent-gateway"]["prefix_refused"])
            assert never & set(vector["ambient"]), vector["name"]
            assert not (never | {"ANTHROPIC_API_KEY"}) & set(vector["environment"]), vector["name"]
            assert _unlisted_agent_names(vector["environment"]), vector["name"]


def _unlisted_agent_names(environment: Mapping[str, str]) -> set[str]:
    """Return the names under the agent's prefix that the declaration names nowhere."""
    return {
        name
        for name in environment
        if name.upper().startswith("CADRUMO_AGENT_") and name.upper() not in _DECLARATION.names
    }


def test_vectors_admit_the_agent_prefix_whole_except_the_never_admitted_names_on_both_families() -> None:
    for family in ("windows", "posix"):
        for profile in ("agent-gateway", "agent-worker"):
            vectors = [
                vector
                for vector in _DECLARATION.launch_vectors
                if vector["platform"] == family and vector["profile"] == profile
            ]
            # Some vector of each profile carries an unlisted agent name through, so no list decides it.
            assert any(_unlisted_agent_names(vector["environment"]) for vector in vectors), (family, profile)
            never = {name.upper() for name in _DECLARATION.profiles[profile]["prefix_refused"]}
            for vector in vectors:
                assert not never & {name.upper() for name in vector["environment"]}, vector["name"]


def test_vectors_give_the_declared_provider_catalog_the_system_base_only_on_both_families() -> None:
    arguments = ["-m", "cadrumo_agent.cli.main", "providers", "--declared", "--json"]
    for family in ("windows", "posix"):
        admitted = [
            vector
            for vector in _DECLARATION.launch_vectors
            if vector["platform"] == family and vector["arguments"] == arguments
        ]
        assert [vector["profile"] for vector in admitted] == ["agent-providers"], family
        vector = admitted[0]
        system = {name.upper() for name in _DECLARATION.base[family]["system"]}
        assert any(name.startswith("CADRUMO_") for name in vector["ambient"]), vector["name"]
        assert {name.upper() for name in vector["environment"]} <= system | set(_DECLARATION.package_values), vector[
            "name"
        ]
        refused = [
            candidate["arguments"]
            for candidate in _DECLARATION.launch_vectors
            if candidate["platform"] == family
            and candidate["image"] == _AGENT
            and candidate["refusal"] is not None
            and candidate["arguments"][2:3] == ["providers"]
        ]
        assert refused, family


def test_browser_handoff_executable_is_scoped_to_gui_auth_and_dropped_from_provider_catalog() -> None:
    variable = "CADRUMO_AGENT_AUTH_BROWSER_EXECUTABLE"
    auth_slots = _DECLARATION.profiles["agent-auth"]["slots"]
    assert any(slot.name == variable and slot.kind == "executable" and not slot.required for slot in auth_slots)
    assert all(slot.name != variable for slot in _DECLARATION.profiles["agent-providers"]["slots"])

    auth_vectors = [
        vector
        for vector in _DECLARATION.launch_vectors
        if vector["profile"] == "agent-auth" and variable in vector["ambient"]
    ]
    assert len(auth_vectors) == 4
    browser_code = [vector for vector in auth_vectors if "browser-code" in vector["arguments"]]
    assert {vector["platform"] for vector in browser_code} == {"windows", "posix"}
    assert all(
        vector["environment"]["CADRUMO_AGENT_HOSTED_ROOT"] == vector["ambient"]["CADRUMO_AGENT_HOSTED_ROOT"]
        for vector in browser_code
    )
    for vector in auth_vectors:
        assert vector["environment"].get(variable) == vector["ambient"][variable]

    catalog_vectors = [
        vector
        for vector in _DECLARATION.launch_vectors
        if vector["profile"] == "agent-providers" and variable in vector["ambient"]
    ]
    assert len(catalog_vectors) == 4
    assert all(variable not in vector["environment"] for vector in catalog_vectors)


def test_vectors_refuse_each_other_arrangement_of_the_agent_invocations_on_both_families() -> None:
    for family in ("windows", "posix"):
        refused = [
            vector["arguments"]
            for vector in _DECLARATION.launch_vectors
            if vector["platform"] == family
            and vector["image"] == _AGENT
            and vector["refusal"] == {"code": "invocation_undeclared", "subject": _AGENT}
        ]
        assert ["-m", "cadrumo_agent.cli.main", "stores-state", "--json"] in refused  # an extra argument
        assert ["cadrumo_agent.cli.main", "-m", "stores-state"] in refused  # a reordered command line
        assert ["-m", "cadrumo_agent.cli.main", "status"] in refused  # a verb the image does not declare
        assert ["-m", "cadrumo_agent.cli.main", "migrate", "--compact"] in refused  # an option it does not declare
        assert ["-m", "cadrumo_agent.cli.main", "migrate", "--expect-from"] in refused  # a flag without its value
        assert [  # options out of their declared order
            "-m",
            "cadrumo_agent.cli.main",
            "migrate",
            "--expect-head",
            "0002_next",
            "--expect-from",
            "0001",
        ] in refused
        assert ["-m", "cadrumo_agent.cli.main", "migrate", "--expect-from", "0001;rm"] in refused  # a malformed value


def _selection(arguments: list[str], family: str = "windows") -> str | None:
    try:
        return reference_select(_DECLARATION, family, _AGENT, ["-m", "cadrumo_agent.cli.main", *arguments])
    except LaunchRefusedError as refused:
        assert (refused.code, refused.subject) == ("invocation_undeclared", _AGENT)
        return None


@pytest.mark.parametrize("family", ["windows", "posix"])
def test_the_python_reading_admits_exactly_the_declared_option_patterns(family: str) -> None:
    longest, too_long = "a" * 128, "a" * 129
    for admitted in (
        ["serve"],
        ["migrate"],
        ["migrate", "--expect-from", "_0001.x-y"],
        ["migrate", "--expect-head", longest],
        ["migrate", "--expect-from", "0", "--expect-head", "9"],
    ):
        assert _selection(admitted, family) == "agent-gateway", admitted
    for refused in (
        [],
        ["migrate", "--expect-from"],
        ["migrate", "--expect-head"],
        ["migrate", "--expect-from", "0001", "--expect-head"],
        ["migrate", "--expect-from", "--expect-head", "0002"],
        ["migrate", "--expect-head", "0002", "--expect-from", "0001"],
        ["migrate", "--expect-from", "0001", "--expect-from", "0002"],
        ["migrate", "--expect-from=0001"],
        ["migrate", "0001"],
        ["migrate", "--expect-from", "0001", "--expect-head", "0002", "extra"],
        ["migrate", "--expect-from", ""],
        ["migrate", "--expect-from", "-0001"],
        ["migrate", "--expect-from", ".hidden"],
        ["migrate", "--expect-from", "0001 0002"],
        ["migrate", "--expect-from", "a/b"],
        ["migrate", "--expect-from", "réf"],
        ["migrate", "--expect-from", "0001\n"],
        ["migrate", "--expect-from", too_long],
        ["stores-state", "--json"],
        ["version"],
        ["version", "--json", "extra"],
        ["--json", "version"],
    ):
        assert _selection(refused, family) is None, refused


def test_the_replay_detects_a_planted_disagreement() -> None:
    providers = dict(next(vector for vector in _DECLARATION.launch_vectors if vector["profile"] == "agent-providers"))
    planted_agent = next(name for name in providers["ambient"] if name.startswith("CADRUMO_AGENT_"))
    providers["environment"] = {**providers["environment"], planted_agent: providers["ambient"][planted_agent]}
    assert _replay(_DECLARATION, providers)
    gateway = dict(
        next(
            vector
            for vector in _DECLARATION.launch_vectors
            if vector["profile"] == "agent-gateway"
            and set(vector["ambient"]) & set(_DECLARATION.profiles["agent-gateway"]["prefix_refused"])
        )
    )
    never = next(
        name for name in gateway["ambient"] if name in _DECLARATION.profiles["agent-gateway"]["prefix_refused"]
    )
    gateway["environment"] = {**gateway["environment"], never: gateway["ambient"][never]}
    assert _replay(_DECLARATION, gateway)
    vector = dict(next(vector for vector in _DECLARATION.launch_vectors if vector["profile"] == "python"))
    vector["environment"] = {**vector["environment"], "CADRUMO_AGENT_PORT": "0"}
    assert _replay(_DECLARATION, vector)
    vector = dict(next(vector for vector in _DECLARATION.launch_vectors if vector["profile"] == "kdf-child"))
    vector["profile"] = "python"
    assert _replay(_DECLARATION, vector)
    # A vector that expects a reordered migrate to be admitted, or a malformed revision, is found out.
    admitted = next(
        vector
        for vector in _DECLARATION.launch_vectors
        if vector["platform"] == "windows" and vector["arguments"][2:] == ["migrate", "--expect-from", "0001"]
    )
    for tail in (["--expect-head", "0002", "--expect-from", "0001"], ["--expect-from", "0001;rm"]):
        planted = {**admitted, "arguments": ["-m", "cadrumo_agent.cli.main", "migrate", *tail]}
        assert _replay(_DECLARATION, planted)
    # So is a vector that expects a declared invocation to be refused.
    refused = {
        **admitted,
        "profile": None,
        "environment": {},
        "refusal": {"code": "invocation_undeclared", "subject": _AGENT},
    }
    assert _replay(_DECLARATION, refused)


@pytest.mark.parametrize("target", ["windows-x86-64", "linux-x86-64"])
def test_the_contract_carries_the_target_familys_vectors(tmp_path: Path, target: str) -> None:
    generate(REPO_ROOT, tmp_path, target=target)
    section = json.loads((tmp_path / "contract.json").read_text(encoding="utf-8"))["application_environment"]
    family = "windows" if target.startswith("windows") else "posix"
    expected = [vector["name"] for vector in _DECLARATION.launch_vectors if vector["platform"] == family]
    assert [vector["name"] for vector in section["vectors"]] == expected
    assert section == compile_section(load_for_build(REPO_ROOT), load_layout(target))
    generated = (tmp_path / "contract.rs").read_text(encoding="utf-8")
    assert generated.count("    LaunchVector { name: ") == len(expected)
