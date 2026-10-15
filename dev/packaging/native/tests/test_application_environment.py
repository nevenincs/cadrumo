"""The application environment declaration validates, refuses malformed files and compiles in parity."""

from __future__ import annotations

import json
import re
import shutil
import tomllib
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT

from ..application_environment import (
    DECLARATION,
    ApplicationEnvironmentError,
    LaunchRefusedError,
    compile_section,
    load,
    parse,
    reference_select,
)
from ..generate import generate
from ..layout import load_layout

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SOURCE = (REPO_ROOT / DECLARATION).read_text(encoding="utf-8")


@pytest.mark.parametrize("family", ("windows", "posix"))
def test_operator_sign_in_accepts_metadata_but_not_flags_or_paths(family: str) -> None:
    declaration = load(REPO_ROOT)
    prefix = ("-m", "cadrumo_agent.cli.main", "auth", "login", "--provider")
    assert reference_select(declaration, family, "cadrumo-agent", (*prefix, "example_provider_2")) == "agent-auth"
    for invalid in ("", "--help", "../other", "a/b", "a\\b", "A", "a b", "a=key", "a" * 65):
        with pytest.raises(LaunchRefusedError):
            reference_select(declaration, family, "cadrumo-agent", (*prefix, invalid))
    with pytest.raises(LaunchRefusedError):
        reference_select(declaration, family, "cadrumo-agent", prefix)


def test_the_declaration_validates_and_covers_every_built_image() -> None:
    declaration = load(REPO_ROOT)
    for target in ("windows-x86-64", "linux-x86-64", "macos-arm64"):
        section = compile_section(declaration, load_layout(target))
        assert {profile["image"] for profile in section["profiles"]} == set(section["images"])
    windows = compile_section(declaration, load_layout("windows-x86-64"))
    python = next(profile for profile in windows["profiles"] if profile["name"] == "python")
    assert "SYSTEMROOT" in python["base"] and "HOME" not in python["base"]
    assert "CADRUMO_LOG_LEVEL" in python["operator"]
    runtime = next(profile for profile in windows["profiles"] if profile["name"] == "cadrumo-runtime")
    assert runtime["operator"] == [] and runtime["pins"]
    kdf = next(profile for profile in windows["profiles"] if profile["name"] == "kdf-child")
    assert kdf["inherit"] and kdf["invoked"] and not kdf["pins"] and not kdf["package_path"]


def _without(text: str, line: str) -> str:
    assert line in text
    return text.replace(line, "", 1)


_MALFORMED = {
    "not-toml": "schema = = 1\n",
    "schema-two": _SOURCE.replace("schema = 1", "schema = 2", 1),
    "unknown-kind": _SOURCE.replace(
        'CADRUMO_LOG_LEVEL = { kind = "text", role = "operator" }',
        'CADRUMO_LOG_LEVEL = { kind = "secret", role = "operator" }',
    ),
    "lowercase-name": _SOURCE.replace("CADRUMO_LOG_LEVEL = {", "cadrumo_log_level = {", 1),
    "group-undeclared-name": _SOURCE.replace('  "CADRUMO_LOG_LEVEL",\n', '  "CADRUMO_LOG_LEVELS",\n', 1),
    "group-admits-pin": _SOURCE.replace('package = ["CADRUMO_CLI_REVEAL_IDENTIFIERS",', 'package = ["TEMP",', 1),
    "unknown-profile-key": _SOURCE.replace(
        '[profiles.kdf-child]\nimage = "python"\n', '[profiles.kdf-child]\nimage = "python"\nselector = "env"\n', 1
    ),
    "inherit-with-pins": _SOURCE.replace('base = "inherit"\npins = false', 'base = "inherit"\npins = true', 1),
    "two-defaults": _SOURCE
    + '\n[profiles.python-two]\nimage = "python"\nbase = "groups"\nbase_groups = ["system"]\npins = true\n'
    'path = "package"\n',
    "invocation-undeclared-profile": _SOURCE.replace(
        'profile = "kdf-child"\nplatform = "windows"', 'profile = "kdf"\nplatform = "windows"', 1
    ),
    "argument-kind": _SOURCE.replace('{ slot = "request", kind = "handle" }', '{ slot = "request", kind = "pid" }', 1),
    "pair-undeclared-slot": _SOURCE.replace(
        'distinct = [["request", "result"]]\n\n[[invocations]]',
        'distinct = [["request", "bound"]]\n\n[[invocations]]',
        1,
    ),
    "windows-lowercase-base": _SOURCE.replace(
        '[base.windows]\nsystem = [\n  "SYSTEMROOT",', '[base.windows]\nsystem = [\n  "SystemRoot",', 1
    ),
    "missing-section": _without(_SOURCE, 'external = "CADRUMO_EXTERNAL_BIN_DIRS"\n'),
}

_FROM = '{ option = "--expect-from", slot = "expected_from", kind = "revision" }'
_HEAD = '{ option = "--expect-head", slot = "expected_head", kind = "revision" }'
# Each planted defect in the optional-argument syntax, with the reason the declaration is refused for it.
_MALFORMED_OPTIONS = {
    "option-takes-a-number": (
        _SOURCE.replace(_FROM, _FROM.replace('"revision" }', '"descriptor" }'), 1),
        "option kind",
    ),
    "option-is-not-a-flag": (_SOURCE.replace(_FROM, _FROM.replace("--expect-from", "expect-from"), 1), "double-dash"),
    "option-with-a-minimum": (_SOURCE.replace(_FROM, _FROM.replace(" }", ", minimum = 1 }"), 1), "unknown"),
    "option-flag-repeated": (_SOURCE.replace(_HEAD, _HEAD.replace("--expect-head", "--expect-from"), 1), "distinct"),
    "option-flag-is-a-literal": (
        _SOURCE.replace('{ literal = "migrate" },', '{ literal = "migrate" },\n  { literal = "--expect-from" },', 1),
        "distinct",
    ),
    "argument-after-the-options": (
        _SOURCE.replace(_HEAD + ",", _HEAD + ',\n  { literal = "trailing" },', 1),
        "options must follow",
    ),
    "pair-over-an-option-slot": (
        _SOURCE.replace(_HEAD + ",\n]\n", _HEAD + ',\n]\ndistinct = [["expected_from", "expected_head"]]\n', 1),
        "declared argument slots",
    ),
    "revision-with-a-minimum": (
        _SOURCE + '\n[[invocations]]\nprofile = "agent-gateway"\nplatform = "all"\n'
        'arguments = [{ literal = "-m" }, { slot = "revision", kind = "revision", minimum = 2 }]\n',
        "numeric",
    ),
    "identical-pattern-for-another-profile": (
        _SOURCE + '\n[[invocations]]\nprofile = "agent-worker"\nplatform = "all"\n'
        'arguments = [{ literal = "-m" }, { literal = "cadrumo_agent.cli.main" }, { literal = "serve" }]\n',
        "share one image and argument pattern",
    ),
}


@pytest.mark.parametrize("text", list(_MALFORMED.values()), ids=list(_MALFORMED))
def test_a_malformed_declaration_is_refused(text: str) -> None:
    assert text != _SOURCE
    with pytest.raises(ApplicationEnvironmentError):
        parse(text)


@pytest.mark.parametrize(("text", "reason"), list(_MALFORMED_OPTIONS.values()), ids=list(_MALFORMED_OPTIONS))
def test_a_malformed_optional_argument_is_refused_for_its_reason(text: str, reason: str) -> None:
    assert text != _SOURCE
    with pytest.raises(ApplicationEnvironmentError, match=reason):
        parse(text)


def test_an_image_without_a_profile_is_refused() -> None:
    text = _SOURCE.replace(
        '[profiles.cadrumo-runtime]\nimage = "cadrumo-runtime"', '[profiles.cadrumo-runtime]\nimage = "relay"', 1
    )
    with pytest.raises(ApplicationEnvironmentError, match="built images"):
        compile_section(parse(text), load_layout("windows-x86-64"))


def _source_tree(tmp_path: Path, declaration: str) -> Path:
    root = tmp_path / "source"
    for relative in (
        "pyproject.toml",
        ".python-version",
        "dev/packaging/release-python-version",
        "native/package-layout.json",
        "native/platforms",
    ):
        source, destination = REPO_ROOT / relative, root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, destination)
        else:
            shutil.copy2(source, destination)
    (root / DECLARATION).write_text(declaration, encoding="utf-8")
    return root


def test_generation_fails_on_a_malformed_declaration(tmp_path: Path) -> None:
    good = _source_tree(tmp_path / "good", _SOURCE)
    generate(good, tmp_path / "good-out", target="windows-x86-64")
    assert (tmp_path / "good-out" / "contract.json").is_file()
    bad = _source_tree(tmp_path / "bad", _MALFORMED["unknown-kind"])
    with pytest.raises(ApplicationEnvironmentError):
        generate(bad, tmp_path / "bad-out", target="windows-x86-64")
    assert not (tmp_path / "bad-out" / "contract.rs").exists()


_PROFILE_LINE = re.compile(r'^    LaunchProfile \{ name: "([^"]+)", image: "([^"]+)", (.*) \},$')


@pytest.mark.parametrize("target", ["windows-x86-64", "linux-x86-64"])
def test_file_contract_json_and_contract_rs_agree(tmp_path: Path, target: str) -> None:
    generate(REPO_ROOT, tmp_path, target=target)
    section = json.loads((tmp_path / "contract.json").read_text(encoding="utf-8"))["application_environment"]
    generated = (tmp_path / "contract.rs").read_text(encoding="utf-8")
    header = (tmp_path / "contract.h").read_text(encoding="utf-8")

    # The file's own reading, independent of the compiler, fixes the expected content.
    document = tomllib.loads(_SOURCE)
    family = "windows" if target.startswith("windows") else "posix"
    assert section["names"] == {name: document["names"][name] for name in sorted(document["names"])}
    assert [profile["name"] for profile in section["profiles"]] == list(document["profiles"])
    for profile in section["profiles"]:
        declared = document["profiles"][profile["name"]]
        assert profile["image"] == declared["image"]
        expected_base = [name for group in declared.get("base_groups", []) for name in document["base"][family][group]]
        assert profile["base"] == expected_base
        assert profile["operator"] == [
            name for group in declared.get("operator", []) for name in document["groups"][group]
        ]
    expected_invocations = [entry for entry in document["invocations"] if entry["platform"] in {family, "all"}]
    assert [invocation["profile"] for invocation in section["invocations"]] == [
        entry["profile"] for entry in expected_invocations
    ]
    for invocation, entry in zip(section["invocations"], expected_invocations, strict=True):
        assert [argument.get("literal") for argument in invocation["arguments"]] == [
            argument.get("literal") for argument in entry["arguments"]
        ]

    rust_profiles = [match.groups() for match in map(_PROFILE_LINE.match, generated.splitlines()) if match]
    assert [(name, image) for name, image, _ in rust_profiles] == [
        (profile["name"], profile["image"]) for profile in section["profiles"]
    ]
    for (_, _, body), profile in zip(rust_profiles, section["profiles"], strict=True):
        operator = re.search(r"operator: &\[([^\]]*)\]", body)
        assert operator is not None
        assert re.findall(r'"([^"]+)"', operator.group(1)) == profile["operator"]
        base = re.search(r"base: &\[([^\]]*)\]", body)
        assert base is not None
        assert re.findall(r'"([^"]+)"', base.group(1)) == profile["base"]
    assert generated.count("    LaunchInvocation {") == len(section["invocations"])
    for image in section["images"]:
        assert f'"{image}"' in header
