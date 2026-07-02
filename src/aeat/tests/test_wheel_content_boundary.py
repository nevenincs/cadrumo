"""Packaging content-boundary gate: the wheel sheds tests and keeps payload.

The build config excludes
every ``tests/`` tree from the installed wheel — those modules and fixtures
serve no installed consumer, since the suites run from the repository tree.
This gate proves the boundary end-to-end by building the real wheel and
asserting it both ways:

1. No ``tests/`` member ships (the exclude took effect), so the ~11 MB fixture
   payload no longer reaches consumers.
2. The required functional payload still ships — the ``_data`` roots (corpus,
   registry, terminology, agent harness), the ``py.typed`` marker, the BIP-39
   recovery wordlist, and ``external_constants.toml`` — so the exclude cannot
   silently strip something the installed package needs.

The exclude alone is build config that can silently rot; this post-build
assertion is what makes the boundary an executable contract. No mocks, fakes,
or skips: the real ``uv build`` pipeline runs, and a missing ``uv`` binary
fails loudly.
"""

from __future__ import annotations

import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

from ._inventory import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_WHEEL_PREFIX = "aeat"
_WHEEL_DATA_PREFIX = "aeat/_data"

# Required functional payload that MUST survive the tests exclude. Each entry is
# a wheel-archive path (or, for the data roots, a directory prefix probed below).
_REQUIRED_DATA_ROOTS = (
    "corpus",
    "registry",
    "terminology",
    "agent",
)
_REQUIRED_MEMBERS = (
    f"{_WHEEL_PREFIX}/py.typed",
    f"{_WHEEL_PREFIX}/adapters/persistence/storage/master_key/_bip39_wordlist.txt",
    f"{_WHEEL_PREFIX}/core/external_constants.toml",
)


@pytest.fixture(scope="module")
def wheel_members(tmp_path_factory: pytest.TempPathFactory) -> frozenset[str]:
    """Build the project wheel and return the set of archive member paths."""

    if shutil.which("uv") is None:
        raise AssertionError(
            "uv binary not found on PATH; the packaging content-boundary gate "
            "cannot run without the project's build driver",
        )
    out_dir = tmp_path_factory.mktemp("wheel-out")
    subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(out_dir)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    wheels = sorted(out_dir.glob("aeat-*.whl"))
    if len(wheels) != 1:
        raise AssertionError(f"expected exactly one aeat-*.whl in {out_dir}; got {[w.name for w in wheels]!r}")
    with zipfile.ZipFile(wheels[0]) as archive:
        return frozenset(info.filename for info in archive.infolist())


def _test_members(members: frozenset[str]) -> list[str]:
    """Return every wheel member that lives under a ``tests`` package."""

    offenders: list[str] = []
    for name in members:
        parts = Path(name).parts
        if any(part == "tests" for part in parts):
            offenders.append(name)
    return sorted(offenders)


def test_wheel_excludes_every_test_member(wheel_members: frozenset[str]) -> None:
    """No file under any ``tests/`` package ships in the wheel."""

    offenders = _test_members(wheel_members)
    assert not offenders, (
        f"the wheel ships {len(offenders)} test member(s) the data-budget exclude should have shed; "
        f"first ten: {offenders[:10]!r}"
    )


def test_wheel_keeps_required_data_roots(wheel_members: frozenset[str]) -> None:
    """Every functional ``_data`` root still ships after the tests exclude."""

    missing_roots = [
        root
        for root in _REQUIRED_DATA_ROOTS
        if not any(name.startswith(f"{_WHEEL_DATA_PREFIX}/{root}/") for name in wheel_members)
    ]
    assert not missing_roots, (
        f"the wheel is missing required _data root(s) {missing_roots!r}; the tests exclude stripped functional payload"
    )


def test_wheel_keeps_required_functional_members(wheel_members: frozenset[str]) -> None:
    """The py.typed marker, BIP-39 wordlist, and external_constants.toml still ship."""

    missing = sorted(member for member in _REQUIRED_MEMBERS if member not in wheel_members)
    assert not missing, (
        f"the wheel is missing required functional member(s) {missing!r}; the tests exclude stripped functional payload"
    )
