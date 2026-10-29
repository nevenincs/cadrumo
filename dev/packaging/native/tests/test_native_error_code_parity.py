"""The host error codes are spelled identically by the Rust enum and both hand-kept mirrors."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT

from ..package_health_facts import NATIVE_ERROR_CODES

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_ENUM_SOURCE = REPO_ROOT / "native/application/src/error/application.rs"
_CONTRACT_SOURCE = REPO_ROOT / "native/desktop/frontend/src/ipc/contract.ts"

_RUST_ENUM = re.compile(
    r"(?P<attributes>(?:[ \t]*#\[[^\n]*\]\s*)*)pub\s+enum\s+ErrorCode\s*\{(?P<body>.*?)\n\}",
    re.DOTALL,
)
_TS_UNION = re.compile(r"export\s+type\s+HostErrorCode\s*=(?P<body>[^;]*);")
_TS_MEMBER = re.compile(r'\|\s*"([^"]*)"')


def _snake_case(variant: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", variant).lower()


def rust_wire_codes(source: str) -> set[str]:
    """Return the wire spellings of the `ErrorCode` enum, refusing any spelling serde would change."""
    match = _RUST_ENUM.search(source)
    assert match is not None, "ErrorCode enum not found"
    assert 'rename_all = "snake_case"' in match["attributes"], "ErrorCode no longer serializes as snake_case"
    variants: set[str] = set()
    for raw in match["body"].splitlines():
        line = raw.strip()
        if not line or line.startswith("//"):
            continue
        assert not line.startswith("#"), f"per-variant attribute alters the wire spelling: {line}"
        assert re.fullmatch(r"[A-Z][A-Za-z0-9]*,", line), f"unrecognised ErrorCode variant line: {line}"
        variants.add(_snake_case(line.removesuffix(",")))
    return variants


def typescript_wire_codes(source: str) -> set[str]:
    """Return the string members of the `HostErrorCode` union."""
    match = _TS_UNION.search(source)
    assert match is not None, "HostErrorCode union not found"
    members = _TS_MEMBER.findall(match["body"])
    assert len(members) == len(set(members)), "HostErrorCode repeats a member"
    return set(members)


def drift(enum: set[str], mirrors: dict[str, set[str]]) -> dict[str, tuple[set[str], set[str]]]:
    """Return, per mirror, the codes it lacks and the codes the enum no longer has."""
    return {name: (enum - codes, codes - enum) for name, codes in mirrors.items() if codes != enum}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_the_enum_and_both_mirrors_spell_the_same_codes() -> None:
    enum = rust_wire_codes(_read(_ENUM_SOURCE))
    mirrors = {
        "contract.ts HostErrorCode": typescript_wire_codes(_read(_CONTRACT_SOURCE)),
        "package_health_facts NATIVE_ERROR_CODES": set(NATIVE_ERROR_CODES),
    }
    assert "child_failed" in enum
    assert drift(enum, mirrors) == {}


_ENUM_FIXTURE = """\
#[derive(Clone, Copy)]
#[serde(rename_all = "snake_case")]
pub enum ErrorCode {
    InvalidArguments,
    // a note
    ChildFailed,
    CliWaitTimedOut,
}
"""
_UNION_FIXTURE = """\
export type HostErrorCode =
  | "invalid_arguments"
  | "child_failed"
  | "cli_wait_timed_out";
"""


def test_the_fixture_readers_agree_when_nothing_drifted() -> None:
    enum = rust_wire_codes(_ENUM_FIXTURE)
    assert enum == {"invalid_arguments", "child_failed", "cli_wait_timed_out"}
    assert typescript_wire_codes(_UNION_FIXTURE) == enum


def test_the_gate_names_a_code_missing_from_one_mirror() -> None:
    enum = rust_wire_codes(_ENUM_FIXTURE)
    union = typescript_wire_codes(_UNION_FIXTURE.replace('  | "child_failed"\n', ""))
    health = {"invalid_arguments", "child_failed", "cli_wait_timed_out"}
    assert drift(enum, {"ts": union, "health": health}) == {"ts": ({"child_failed"}, set())}


def test_the_gate_names_a_mirror_code_the_enum_no_longer_has() -> None:
    enum = rust_wire_codes(_ENUM_FIXTURE.replace("    ChildFailed,\n", ""))
    union = typescript_wire_codes(_UNION_FIXTURE)
    assert drift(enum, {"ts": union}) == {"ts": (set(), {"child_failed"})}


@pytest.mark.parametrize(
    "mutation",
    [
        ('rename_all = "snake_case"', 'rename_all = "camelCase"'),
        ("    ChildFailed,", '    #[serde(rename = "child")]\n    ChildFailed,'),
        ("    ChildFailed,", "    ChildFailed(String),"),
    ],
)
def test_the_enum_reader_refuses_a_change_to_the_wire_spelling(mutation: tuple[str, str]) -> None:
    with pytest.raises(AssertionError):
        rust_wire_codes(_ENUM_FIXTURE.replace(*mutation))
