"""The package-side conformance check holds the installed components to the package's declaration."""

from __future__ import annotations

import ast
import copy
import json
import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from dev._paths import REPO_ROOT

from .. import environment_facts
from ..application_environment import DECLARATION
from ..environment_conformance import (
    Reference,
    build_request,
    collect_facts,
    conformance_findings,
    gateway_profile,
    load_reference,
    reference_from_text,
    run,
)
from ..layout import load_layout

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SOURCE = (REPO_ROOT / DECLARATION).read_text(encoding="utf-8")
_TARGET = {"win32": "windows-x86-64", "darwin": "macos-arm64"}.get(sys.platform, "linux-x86-64")
_LAYOUT = load_layout(_TARGET)
_PACKAGE_KINDS = {
    "directory": "path",
    "file": "path",
    "executable": "path",
    "port": "integer",
    "integer": "integer",
    "boolean": "boolean",
    "text": "text",
}


@pytest.fixture(scope="module")
def reference() -> Reference:
    return load_reference(REPO_ROOT, _LAYOUT)


@pytest.fixture(scope="module")
def request_(reference: Reference) -> dict[str, Any]:
    return build_request(reference)


@pytest.fixture(scope="module")
def facts(request_: dict[str, Any]) -> dict[str, Any]:
    """The facts of the interpreter running these tests: the real command line, runtime and composer."""
    collected: dict[str, Any] = json.loads(json.dumps(environment_facts.collect(request_)))
    return collected


def _conforming_agent(reference: Reference, runtime: dict[str, Any]) -> dict[str, Any]:
    """Facts for an agent that agrees with the declaration, derived from the declaration alone."""
    declared = reference.agent
    gateway = gateway_profile(reference, runtime["gateway_arguments"])
    assert gateway is not None
    worker = next(
        profile
        for profile in reference.section["profiles"]
        if profile["image"] == declared["image"] and profile["name"] != gateway["name"]
    )
    admitted = [*worker["pass"], *(slot["name"] for slot in worker["slots"])]
    return {
        "prefix": declared["prefix"],
        "hosting_contract": declared["hosting_contract"],
        "settings": {
            name: _PACKAGE_KINDS[entry["kind"]]
            for name, entry in reference.declaration.names.items()
            if name.startswith(declared["prefix"])
        },
        "credentials": [name for name in worker["pass"] if name.endswith("INTERNAL_TOKEN")],
        "settings_file_variable": next(name for name in declared["never_admitted"] if name.endswith("ENV_FILE")),
        "worker_environment_writes": sorted(admitted),
    }


def _rendered(findings: list[Any]) -> list[str]:
    return [finding.render() for finding in findings]


def test_the_installed_components_conform_to_the_package_declaration(
    reference: Reference, request_: dict[str, Any], facts: dict[str, Any]
) -> None:
    findings = conformance_findings(reference, facts, request_["received"], require_agent=False)
    assert findings == [], _rendered(findings)


def test_an_agent_that_agrees_with_the_declaration_adds_no_finding(
    reference: Reference, request_: dict[str, Any], facts: dict[str, Any]
) -> None:
    facts = {**facts, "agent": _conforming_agent(reference, facts["runtime"])}
    findings = conformance_findings(reference, facts, request_["received"])
    assert findings == [], _rendered(findings)


def test_a_package_without_its_agent_is_a_finding_and_a_checkout_without_one_is_not(
    reference: Reference, request_: dict[str, Any], facts: dict[str, Any]
) -> None:
    assert facts["agent"] is None
    findings = conformance_findings(reference, facts, request_["received"])
    assert [(finding.check, finding.subject) for finding in findings] == [("agent-names", "bundled agent")]
    unchecked = conformance_findings(reference, facts, request_["received"], require_agent=False)
    assert unchecked == [], _rendered(unchecked)


def _first_non_slot_system_name(facts: dict[str, Any]) -> str:
    slots = set(facts["runtime"]["gateway_slots"])
    return str(
        next(
            name
            for name in facts["runtime"]["composed"]
            if name not in slots and name not in {"PATH", "TEMP", "TMP", "TMPDIR"}
        )
    )


_Mutation = Callable[[dict[str, Any]], None]


def _remove_setting(name: str) -> _Mutation:
    return lambda facts: facts["cli"]["settings"].pop(name)


def _set(path: tuple[str, ...], value: Any) -> _Mutation:
    def mutate(facts: dict[str, Any]) -> None:
        container = facts
        for key in path[:-1]:
            container = container[key]
        container[path[-1]] = value

    return mutate


def _composer_writes(name: str) -> _Mutation:
    return lambda facts: facts["runtime"]["composed"].append(name)


def _composer_omits_a_system_name(facts: dict[str, Any]) -> None:
    facts["runtime"]["composed"].remove(_first_non_slot_system_name(facts))


def _runtime_adds_a_slot(facts: dict[str, Any]) -> None:
    facts["runtime"]["gateway_slots"].append("EXTRA_SLOT")


def _runtime_drops_a_slot(facts: dict[str, Any]) -> None:
    facts["runtime"]["gateway_slots"].pop(0)


def _composer_omits_a_slot(facts: dict[str, Any]) -> None:
    facts["runtime"]["composed"].remove(facts["runtime"]["gateway_slots"][0])


def _overlap(facts: dict[str, Any]) -> None:
    facts["runtime"]["reserved_exit_codes"].append({"owner": "planted", "first": 124, "last": 130})


def _second_native_range(facts: dict[str, Any]) -> None:
    facts["runtime"]["reserved_exit_codes"].append({"owner": "native_host", "first": 7, "last": 8})


def _widen_range(facts: dict[str, Any]) -> None:
    owned = next(item for item in facts["runtime"]["reserved_exit_codes"] if item["owner"] == "native_host")
    owned["last"] = 127


def _reorder_refusals(facts: dict[str, Any]) -> None:
    facts["runtime"]["native_refusals"].reverse()


def _other_root_candidate(facts: dict[str, Any]) -> None:
    facts["cli"]["root"]["installed_defaults"][0]["candidates"][0]["variable"] = "APPDATA"


_PLANTED_FACTS: list[tuple[str, _Mutation, str, str]] = [
    ("setting-unread", _remove_setting("CADRUMO_LOG_LEVEL"), "command-line-names", "reads no such"),
    (
        "setting-secret",
        _set(("cli", "settings", "CADRUMO_LOG_LEVEL"), "secret"),
        "command-line-names",
        "holds a credential",
    ),
    (
        "setting-narrower",
        _set(("cli", "settings", "CADRUMO_AUTH_TIMEOUT_MS"), "boolean"),
        "command-line-names",
        "wider than",
    ),
    (
        "setting-without-a-field",
        _set(("cli", "settings", "CADRUMO_LOG_LEVEL"), None),
        "command-line-names",
        "without a settings field",
    ),
    (
        "temporary-variables",
        _set(("cli", "temporary_variables"), ["TEMP"]),
        "command-line-names",
        "temporary variables",
    ),
    (
        "authority",
        _set(("cli", "authority_variables"), ["SOMETHING_ELSE"]),
        "command-line-names",
        "authority",
    ),
    ("slot-dropped-by-the-runtime", _runtime_drops_a_slot, "runtime-launch", "does not fill"),
    ("slot-added-by-the-runtime", _runtime_adds_a_slot, "runtime-launch", "does not declare"),
    ("composer-writes-a-credential", _composer_writes("ANTHROPIC_API_KEY"), "runtime-launch", "does not admit it"),
    ("composer-omits-a-slot", _composer_omits_a_slot, "runtime-launch", "composer does not write"),
    ("composer-omits-a-system-name", _composer_omits_a_system_name, "runtime-launch", "composer omits"),
    (
        "gateway-invocation",
        _set(("runtime", "gateway_arguments"), ["-m", "elsewhere", "serve"]),
        "runtime-launch",
        "no declared invocation",
    ),
    (
        "agent-variable",
        _set(("runtime", "agent_variable"), "SOMETHING_ELSE"),
        "runtime-launch",
        "not fixed as the path of a bundled agent",
    ),
    (
        "relay-variable",
        _set(("runtime", "relay_variable"), "SOMETHING_ELSE"),
        "runtime-launch",
        "not fixed as the path of an entrypoint",
    ),
    ("native-range-widened", _widen_range, "native-host", "the runtime reserves"),
    ("native-range-doubled", _second_native_range, "native-host", "2 ranges"),
    ("native-range-overlapped", _overlap, "native-host", "overlaps"),
    (
        "refused-status",
        _set(("runtime", "launch_profile_refused"), 124),
        "native-host",
        "launch_profile_refused",
    ),
    ("refusals-reordered", _reorder_refusals, "native-host", "refusal codes"),
    ("root-variable", _set(("cli", "root", "variable"), "SOMETHING_ELSE"), "storage-root", "variable"),
    ("root-candidate", _other_root_candidate, "storage-root", "installed_defaults"),
    (
        "root-product-directory",
        _set(("cli", "root", "channel", "product_directory"), "elsewhere"),
        "storage-root",
        "channel",
    ),
    (
        "root-channel-directory",
        _set(("cli", "channel_directories", "preview"), "cadrumo_preview"),
        "storage-root",
        "channel preview",
    ),
    (
        "root-default",
        _set(("cli", "default_root"), {"root": "elsewhere"}),
        "storage-root",
        "installed default",
    ),
    (
        "root-refused",
        _set(("cli", "default_root"), {"refusal": "installed_base_unavailable"}),
        "storage-root",
        "installed default",
    ),
    ("log-default", _set(("cli", "log", "default"), "diagnostics"), "log-location", "default"),
    ("log-relocation", _set(("cli", "log", "relocated"), "logs/relocated-logs"), "log-location", "relative value"),
    ("log-file", _set(("cli", "log", "file_name"), "other.log"), "log-location", "log file"),
]


@pytest.mark.parametrize(
    ("mutate", "check", "fragment"), [pytest.param(*case[1:], id=case[0]) for case in _PLANTED_FACTS]
)
def test_a_component_that_drifts_from_the_declaration_is_found(
    reference: Reference,
    request_: dict[str, Any],
    facts: dict[str, Any],
    mutate: _Mutation,
    check: str,
    fragment: str,
) -> None:
    planted = copy.deepcopy(facts)
    mutate(planted)
    assert planted != facts
    findings = conformance_findings(reference, planted, request_["received"], require_agent=False)
    assert findings, "the drift was not found"
    assert {finding.check for finding in findings} == {check}, _rendered(findings)
    assert any(fragment in finding.render() for finding in findings), _rendered(findings)


def _planted_agent(reference: Reference, runtime: dict[str, Any], change: Callable[[dict[str, Any]], None]) -> Any:
    agent = _conforming_agent(reference, runtime)
    change(agent)
    return agent


def _first_agent_name(agent: dict[str, Any], kind: str) -> str:
    return str(next(name for name, label in agent["settings"].items() if label == kind))


_PLANTED_AGENTS: list[tuple[str, Callable[[dict[str, Any]], None], str]] = [
    ("another-prefix", lambda agent: agent.update(prefix="OTHER_"), "prefix"),
    ("another-contract", lambda agent: agent.update(hosting_contract=2), "hosting contract"),
    ("setting-file-admitted", lambda agent: agent.update(settings_file_variable="SOMETHING_ELSE"), "is admitted"),
    ("no-worker-handover", lambda agent: agent.update(worker_environment_writes=[]), "found no environment"),
    (
        "worker-write-unadmitted",
        lambda agent: agent["worker_environment_writes"].append("UNADMITTED_NAME"),
        "does not admit",
    ),
    (
        "setting-gone",
        lambda agent: agent["settings"].pop(_first_agent_name(agent, "integer")),
        "reads no such setting",
    ),
    (
        "setting-narrower",
        lambda agent: agent["settings"].update({_first_agent_name(agent, "integer"): "boolean"}),
        "wider than the agent",
    ),
    (
        "credential-admitted-to-the-gateway",
        lambda agent: agent["credentials"].append(_first_agent_name(agent, "path")),
        "is a credential the agent holds",
    ),
]


@pytest.mark.parametrize(
    ("change", "fragment"), [pytest.param(case[1], case[2], id=case[0]) for case in _PLANTED_AGENTS]
)
def test_an_agent_that_drifts_from_the_declaration_is_found(
    reference: Reference,
    request_: dict[str, Any],
    facts: dict[str, Any],
    change: Callable[[dict[str, Any]], None],
    fragment: str,
) -> None:
    planted = {**facts, "agent": _planted_agent(reference, facts["runtime"], change)}
    findings = conformance_findings(reference, planted, request_["received"])
    assert findings, "the drift was not found"
    assert {finding.check for finding in findings} == {"agent-names"}, _rendered(findings)
    assert any(fragment in finding.render() for finding in findings), _rendered(findings)


_Edit = Callable[[str], str]


def _replace(old: str, new: str, *, count: int = 1) -> _Edit:
    def edit(text: str) -> str:
        edited = text.replace(old, new, count)
        assert edited != text, old
        return edited

    return edit


def _all(*edits: _Edit) -> _Edit:
    def edit(text: str) -> str:
        for each in edits:
            text = each(text)
        return text

    return edit


def _without_the_gateways_relay_slot(text: str) -> str:
    edited = re.sub(
        r'(\[profiles\.agent-gateway\].*?)\n  \{ name = "[A-Z_]+HOSTED_RELAY_EXECUTABLE", required = false \},',
        r"\1",
        text,
        count=1,
        flags=re.DOTALL,
    )
    assert edited != text
    return edited


# The same real installed components, held to a declaration that says something else.
_PLANTED_DECLARATIONS: list[tuple[str, _Edit, str, str]] = [
    ("native-range-start", _replace("first = 120", "first = 119"), "native-host", "reserves 119-125"),
    (
        "kind-wider-than-the-setting",
        _replace(
            'CADRUMO_AUTH_TIMEOUT_MS = { kind = "integer", role = "operator" }',
            'CADRUMO_AUTH_TIMEOUT_MS = { kind = "text", role = "operator" }',
        ),
        "command-line-names",
        "CADRUMO_AUTH_TIMEOUT_MS",
    ),
    (
        "operator-name-the-command-line-does-not-read",
        _replace("CADRUMO_LOG_LEVEL", "CADRUMO_LOG_LEVELS", count=-1),
        "command-line-names",
        "CADRUMO_LOG_LEVELS",
    ),
    (
        "log-directory",
        _all(
            _replace('logs = "logs"', 'logs = "diagnostics"'),
            _replace('log_file = "logs/cadrumo.log"', 'log_file = "diagnostics/cadrumo.log"'),
        ),
        "log-location",
        "diagnostics",
    ),
    (
        "installed-default-base",
        _replace(
            'candidates = [{ variable = "LOCALAPPDATA", subpath = [] }]',
            'candidates = [{ variable = "APPDATA", subpath = [] }]',
        ),
        "storage-root",
        "installed_defaults",
    ),
    (
        "channel-separator",
        _replace(
            'channel = { product_directory = "cadrumo", stable = "stable", separator = "-" }',
            'channel = { product_directory = "cadrumo", stable = "stable", separator = "--" }',
        ),
        "storage-root",
        "channel preview",
    ),
    ("gateway-slot-dropped", _without_the_gateways_relay_slot, "runtime-launch", "does not declare"),
]


@pytest.mark.parametrize(
    ("edit", "check", "fragment"), [pytest.param(*case[1:], id=case[0]) for case in _PLANTED_DECLARATIONS]
)
def test_a_declaration_that_drifts_from_the_installed_components_is_found(
    facts: dict[str, Any], edit: _Edit, check: str, fragment: str
) -> None:
    planted = reference_from_text(edit(_SOURCE), _LAYOUT)
    findings = conformance_findings(planted, facts, build_request(planted)["received"], require_agent=False)
    assert findings, "the drift was not found"
    assert check in {finding.check for finding in findings}, _rendered(findings)
    assert any(fragment in finding.render() for finding in findings), _rendered(findings)


def test_a_declaration_naming_another_hosting_contract_is_found(
    request_: dict[str, Any], facts: dict[str, Any]
) -> None:
    planted = reference_from_text(_replace("hosting_contract = 1", "hosting_contract = 2")(_SOURCE), _LAYOUT)
    agent = _conforming_agent(load_reference(REPO_ROOT, _LAYOUT), facts["runtime"])
    findings = conformance_findings(planted, {**facts, "agent": agent}, request_["received"])
    assert [finding.check for finding in findings] == ["agent-names"]
    assert "hosting contract" in findings[0].render()


def test_the_facts_are_reported_by_the_interpreter_asked(
    request_: dict[str, Any], facts: dict[str, Any], tmp_path: Path
) -> None:
    reported = collect_facts(Path(sys.executable), request_, cwd=tmp_path)
    assert reported == facts


def test_the_facts_module_runs_by_path_so_it_imports_no_packaging_tool() -> None:
    source = Path(environment_facts.__file__).read_text(encoding="utf-8")
    imported: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom):
            assert node.level == 0, "a relative import cannot run by path"
            imported.add(str(node.module).split(".")[0])
        elif isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
    assert imported <= set(sys.stdlib_module_names) | {"pydantic", "cadrumo", "cadrumo_agent"}, imported


def _package(tmp_path: Path) -> Path:
    package = tmp_path / "package"
    manifest = package / "data" / "package-manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"layout": _LAYOUT}), encoding="utf-8")
    return package


def test_the_check_reports_each_disagreement_and_exits_one(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # This interpreter has no bundled agent: that alone is the one disagreement reported.
    status = run(_package(tmp_path), "data/package-manifest.json", REPO_ROOT, python=Path(sys.executable))
    output = capsys.readouterr().out.splitlines()
    assert status == 1
    assert output[0] == "[agent-names] bundled agent: is not installed in the interpreter under test"
    assert output[-1].endswith("1 disagreement(s)")


def test_the_check_exits_two_when_the_package_interpreter_cannot_be_asked(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    package = _package(tmp_path)
    assert run(package, "data/package-manifest.json", REPO_ROOT) == 2
    assert capsys.readouterr().out == ""
