"""The bundled agent image: declared by the package and built from the interpreter host."""

from __future__ import annotations

import copy
import importlib.util
import json
import re
import sys
import types
from collections.abc import Iterator
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT

from ..application_environment import DECLARATION, ApplicationEnvironmentError, compile_section, load_for_build, parse
from ..generate import generate
from ..layout import bundled_image_files, bundled_images, load_layout

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_AGENT = "cadrumo-agent"
_SOURCE = (REPO_ROOT / DECLARATION).read_text(encoding="utf-8")


def test_the_layout_declares_the_agent_image_for_its_bundled_distribution() -> None:
    for target in ("windows-x86-64", "linux-x86-64", "macos-arm64"):
        layout = load_layout(target)
        assert bundled_images(layout) == {_AGENT: {"distribution": "cadrumo-agent", "description": "Cadrumo agent"}}
        assert bundled_image_files(layout) == {
            _AGENT: f"{layout['paths']['native']}/{_AGENT}{layout['entrypoint_suffix']}"
        }
        assert _AGENT not in layout["entrypoints"]


@pytest.mark.parametrize(
    ("declared", "message"),
    [
        pytest.param({"aeat": {"distribution": "cadrumo-agent", "description": "x"}}, "distinct", id="console-script"),
        pytest.param({"Agent": {"distribution": "cadrumo-agent", "description": "x"}}, "distinct", id="name"),
        pytest.param({_AGENT: {"distribution": "Cadrumo_Agent", "description": "x"}}, "canonical", id="distribution"),
        pytest.param({_AGENT: {"distribution": "cadrumo-agent"}}, "declare", id="missing-description"),
    ],
)
def test_the_layout_refuses_a_malformed_bundled_image(declared: dict[str, object], message: str) -> None:
    layout = copy.deepcopy(load_layout("windows-x86-64"))
    layout["bundled_images"] = declared
    with pytest.raises(ValueError, match=message):
        bundled_images(layout)


def _literals(*values: str) -> list[dict[str, str]]:
    return [{"literal": value} for value in values]


def _revision_option(flag: str, slot: str) -> dict[str, object]:
    return {"option": flag, "slot": slot, "kind": "revision", "minimum": 0}


_MODULE = ("-m", "cadrumo_agent.cli.main")
# The invocations the image admits and the profile each selects, written out independently of the file.
_INVOCATIONS = [
    ("agent-gateway", _literals(*_MODULE, "serve")),
    (
        "agent-gateway",
        _literals(*_MODULE, "stores-state"),
    ),
    ("agent-gateway", _literals(*_MODULE, "setup")),
    (
        "agent-gateway",
        [
            *_literals(*_MODULE, "migrate"),
            _revision_option("--expect-from", "expected_from"),
            _revision_option("--expect-head", "expected_head"),
        ],
    ),
    ("agent-gateway", _literals(*_MODULE, "version", "--json")),
    ("agent-worker", _literals("-m", "cadrumo_agent.worker")),
    ("agent-providers", _literals(*_MODULE, "providers", "--declared", "--json")),
    (
        "agent-auth",
        [*_literals(*_MODULE, "auth", "login", "--provider"), {"slot": "provider", "kind": "identifier", "minimum": 0}],
    ),
    ("agent-providers", _literals(*_MODULE, "auth", "providers", "--json")),
]


@pytest.mark.parametrize("target", ["windows-x86-64", "linux-x86-64"])
def test_the_contract_compiles_exactly_the_declared_invocations_of_the_agent_image(tmp_path: Path, target: str) -> None:
    generate(REPO_ROOT, tmp_path, target=target)
    section = json.loads((tmp_path / "contract.json").read_text(encoding="utf-8"))["application_environment"]
    generated = (tmp_path / "contract.rs").read_text(encoding="utf-8")
    layout = load_layout(target)
    assert _AGENT in section["images"]
    assert f'"{_AGENT}{layout["entrypoint_suffix"]}"' in generated.split("pub const ENTRYPOINT_FILES")[1].split("\n")[0]
    invocations = [
        (invocation["profile"], invocation["arguments"])
        for invocation in section["invocations"]
        if invocation["image"] == _AGENT
    ]
    assert invocations == _INVOCATIONS
    profiles = {profile["name"]: profile for profile in section["profiles"]}
    assert all(profile["invoked"] for profile in profiles.values() if profile["image"] == _AGENT)
    # The store and version invocations run in the gateway's environment, so they select its profile: no
    # copy of the gateway's environment can drift from it. The provider catalog has its own minimal profile.
    assert {name for name, profile in profiles.items() if profile["image"] == _AGENT} == {
        "agent-gateway",
        "agent-worker",
        "agent-providers",
        "agent-auth",
    }
    assert generated.count('LaunchInvocation { profile: "agent-gateway"') == 5
    assert 'LaunchArgument { literal: None, option: Some("--expect-from"), slot: Some("expected_from"), ' in generated
    assert 'kind: Some("revision"), minimum: 0 }' in generated
    assert '"cadrumo-agent"' in (tmp_path / "contract.h").read_text(encoding="utf-8")
    for retired in (
        "CADRUMO_AGENT_ENV_FILE",
        "CADRUMO_AGENT_HOSTED_CLI_EXECUTABLE",
        "CADRUMO_AGENT_HOSTED_PYTHON_EXECUTABLE",
    ):
        for profile in profiles.values():
            assert retired not in [*profile["operator"], *profile["pass"], *(slot["name"] for slot in profile["slots"])]
            # A profile that admits the agent's prefix refuses each of them by name.
            assert (retired in profile["prefix_refused"]) == bool(profile["prefix"]), (retired, profile["name"])
        assert retired not in section["names"]


def test_agent_names_reach_the_gateway_and_worker_by_prefix_and_no_other_profile() -> None:
    declaration = load_for_build(REPO_ROOT)
    section = compile_section(declaration, load_layout("windows-x86-64"))
    by_prefix = {profile["name"] for profile in section["profiles"] if profile["prefix"]}
    assert by_prefix == {"agent-gateway", "agent-worker"}
    for profile in section["profiles"]:
        admitted = [
            *profile["base"],
            *profile["operator"],
            *profile["pass"],
            *(slot["name"] for slot in profile["slots"]),
        ]
        agent_names = [name for name in admitted if name.startswith("CADRUMO_AGENT_")]
        if profile["image"] != _AGENT:
            assert agent_names == [], profile["name"]
        # No profile lists an agent setting, provider or credential: the prefix admits them, or nothing does.
        assert [name for name in profile["pass"] if name.startswith("CADRUMO_AGENT_")] == [], profile["name"]
        assert profile["prefix"] in {"", "CADRUMO_AGENT_"}, profile["name"]
    # The worker's IPC token travels on its standard input; the file names no credential to admit or refuse.
    assert not [name for name in section["names"] if name.endswith("_TOKEN")]
    providers = next(profile for profile in section["profiles"] if profile["name"] == "agent-providers")
    assert (providers["slots"], providers["pins"], providers["prefix"], providers["fixed"]) == ([], [], "", [])
    assert providers["base"] == list(declaration.base["windows"]["system"])
    assert providers["package_path"]
    gateway = next(profile for profile in section["profiles"] if profile["name"] == "agent-gateway")
    assert {slot["name"]: slot["kind"] for slot in gateway["slots"]} == {
        "CADRUMO_LOCAL_STORAGE_ROOT": "directory",
        "CADRUMO_AGENT_HOSTED_ROOT": "directory",
        "CADRUMO_AGENT_PORT": "port",
        "CADRUMO_AGENT_WORKER_PORT": "port",
    }
    # The gateway and its worker each receive their parent's storage root as an optional slot
    # they do not pin, which the agent forwards to the programs it starts. A slot is admitted
    # by its kind alone: whoever the caller is, the compiled slot names no parent.
    worker = next(profile for profile in section["profiles"] if profile["name"] == "agent-worker")
    for profile in (gateway, worker):
        root_slot = next(slot for slot in profile["slots"] if slot["name"] == "CADRUMO_LOCAL_STORAGE_ROOT")
        assert root_slot == {"name": "CADRUMO_LOCAL_STORAGE_ROOT", "kind": "directory", "required": False}
        assert all(set(slot) == {"name", "kind", "required"} for slot in profile["slots"])
        assert "root" not in profile["pins"]
    runtime = next(profile for profile in section["profiles"] if profile["name"] == "cadrumo-runtime")
    assert runtime["fixed"] == []
    service = next(profile for profile in section["profiles"] if profile["name"] == "cadrumo-agent-service")
    assert {(value["name"], value["value"]) for value in service["fixed"]} == {
        ("CADRUMO_PACKAGE_AGENT_EXECUTABLE", _AGENT),
        ("CADRUMO_PACKAGE_RELAY_EXECUTABLE", "cadrumo-mcp"),
        ("CADRUMO_PACKAGE_AEAT_EXECUTABLE", "aeat"),
        ("CADRUMO_PACKAGE_PYTHON_EXECUTABLE", "python"),
    }


def test_only_an_image_that_does_not_pin_its_root_may_take_it_as_a_slot() -> None:
    planted = _SOURCE.replace(
        'pins = ["temporary", "authority"]\nagent_names = true',
        "pins = true\nagent_names = true",
        1,
    )
    assert planted != _SOURCE
    with pytest.raises(ApplicationEnvironmentError, match="slot"):
        parse(planted)


def test_the_declaration_refuses_an_agent_name_outside_the_agent_image() -> None:
    planted = _SOURCE.replace(
        '[profiles.python]\nimage = "python"\n',
        '[profiles.python]\nimage = "python"\npass = ["CADRUMO_AGENT_PORT"]\n',
        1,
    )
    assert planted != _SOURCE
    with pytest.raises(ApplicationEnvironmentError):
        parse(planted)
    port = 'CADRUMO_AGENT_PORT = { kind = "port", role = "slot" }\n'
    declared = _SOURCE.replace(port, port + 'CADRUMO_AGENT_ENV_FILE = { kind = "file", role = "pass" }\n', 1)
    assert declared != _SOURCE
    with pytest.raises(ApplicationEnvironmentError, match="never_admitted"):
        parse(declared)


_GATEWAY_PINS = 'pins = ["temporary", "authority"]\nagent_names = true'


def _without_the_agent_table() -> str:
    """Drop the agent table, from its header to the end of its never-admitted list."""
    start = _SOURCE.index("\n[agent]\n")
    end = _SOURCE.index("]\n", _SOURCE.index("never_admitted", start)) + len("]\n")
    return _SOURCE[:start] + _SOURCE[end:]


@pytest.mark.parametrize(
    ("planted", "message"),
    [
        pytest.param(
            _SOURCE.replace(
                '[profiles.python]\nimage = "python"\n',
                '[profiles.python]\nimage = "python"\nagent_names = true\n',
                1,
            ),
            "outside the cadrumo-agent image",
            id="prefix-outside-the-agent-image",
        ),
        pytest.param(
            _SOURCE.replace(_GATEWAY_PINS, 'pins = ["temporary", "authority"]\nagent_names = "yes"', 1),
            "boolean",
            id="prefix-switch-not-a-boolean",
        ),
        pytest.param(
            _SOURCE.replace(
                'CADRUMO_AGENT_PORT = { kind = "port", role = "slot" }\n',
                'CADRUMO_AGENT_PORT = { kind = "port", role = "slot" }\n'
                'CADRUMO_AGENT_LISTED = { kind = "text", role = "pass" }\n',
                1,
            ).replace(
                'pass = ["CADRUMO_EXTERNAL_BIN_DIRS"]\n' + _GATEWAY_PINS,
                'pass = ["CADRUMO_EXTERNAL_BIN_DIRS", "CADRUMO_AGENT_LISTED"]\n' + _GATEWAY_PINS,
                1,
            ),
            "admits them by prefix only",
            id="listed-agent-name",
        ),
        pytest.param(
            _without_the_agent_table(),
            "has no agent table",
            id="prefix-without-an-agent-table",
        ),
    ],
)
def test_the_declaration_admits_agent_names_by_the_prefix_alone(planted: str, message: str) -> None:
    assert planted != _SOURCE
    with pytest.raises(ApplicationEnvironmentError, match=message):
        parse(planted)


def test_only_the_service_pins_the_agent_location_and_generic_hosts_take_no_agent_slot() -> None:
    section = compile_section(load_for_build(REPO_ROOT), load_layout("windows-x86-64"))
    profiles = {profile["name"]: profile for profile in section["profiles"]}
    service_fixed = {value["name"] for value in profiles["cadrumo-agent-service"]["fixed"]}
    agent_location = "CADRUMO_PACKAGE_AGENT_EXECUTABLE"
    assert agent_location in service_fixed
    for profile_name in ("cadrumo-runtime", "python"):
        assert profiles[profile_name]["fixed"] == []
        assert profiles[profile_name]["slots"] == []
    # The image that fixes a package fact cannot also take it from its parent.
    relay = '  { name = "CADRUMO_PACKAGE_PYTHON_EXECUTABLE", image = "python" },\n]\n'
    planted = _SOURCE.replace(
        relay, relay + 'slots = [{ name = "CADRUMO_PACKAGE_AGENT_EXECUTABLE", required = false }]\n', 1
    )
    assert planted != _SOURCE
    with pytest.raises(ApplicationEnvironmentError, match="slot"):
        parse(planted)


@pytest.fixture
def bootstrap() -> Iterator[types.ModuleType]:
    """Load the shipped bootstrap source; only its native import-time module is absent here."""
    sys.modules["_cadrumo_native"] = types.ModuleType("_cadrumo_native")
    spec = importlib.util.spec_from_file_location(
        "_cadrumo_agent_bootstrap", REPO_ROOT / "native/interpreter/bootstrap.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
        yield module
    finally:
        del sys.modules["_cadrumo_native"]


def test_the_agent_image_as_its_own_interpreter_finds_its_package(
    bootstrap: types.ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    layout = load_layout("windows-x86-64")
    monkeypatch.setattr(bootstrap, "LAYOUT", layout)
    package = tmp_path / "package"
    monkeypatch.setattr(sys, "executable", str(package / layout["paths"]["native"] / f"{_AGENT}.exe"))
    assert bootstrap._package_root() == package.resolve()
    monkeypatch.setattr(sys, "executable", str(package / layout["paths"]["executable"]))
    assert bootstrap._package_root() == package.resolve()
    # Only a declared bundled image maps out of the native directory.
    monkeypatch.setattr(sys, "executable", str(package / layout["paths"]["native"] / "other.exe"))
    assert bootstrap._package_root() == (package / layout["paths"]["native"]).resolve()


def test_the_agent_image_keeps_itself_as_the_interpreter_and_is_never_frozen() -> None:
    interpreter = REPO_ROOT / "native/interpreter"
    sources = [
        *interpreter.glob("*.c"),
        *interpreter.glob("*.py"),
        *interpreter.glob("*/*.c"),
        *interpreter.glob("*/*.py"),
    ]
    assert sources
    for source in sources:
        # Nothing sets sys.frozen: no assignment and no PySys_SetObject("frozen", ...).
        assert not re.search(r'"frozen"|\bfrozen\s*=(?!=)', source.read_text(encoding="utf-8")), source
    assert re.search(r'"frozen"|\bfrozen\s*=(?!=)', 'PySys_SetObject("frozen", Py_True);')
    for host in (interpreter / "windows/host.c", interpreter / "posix/host.c"):
        text = host.read_text(encoding="utf-8")
        bundled = text.split("defined(CADRUMO_BUNDLED_IMAGE)\n", 2)[2].split("#else", 1)[0]
        # The bundled image runs its own arguments with its own path; only an entrypoint swaps paths[2].
        assert "run(argc, argv," in bundled and "paths[2]" not in bundled
