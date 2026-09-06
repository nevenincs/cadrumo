"""Independent contracts for streamed packaging artifact hashing."""

from __future__ import annotations

import ast
import hashlib
import importlib
import subprocess
import sys
from pathlib import Path
from typing import Final

import pytest

from ..._paths import REPO_ROOT
from .._hashing import sha256_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


_REHOMED_STREAMED_DIGEST_SITES: Final[tuple[str, ...]] = (
    "dev/packaging/cohort_manifest.py",
    "dev/packaging/smoke_homebrew.py",
    "dev/corpus/sync_aeat_record_design_corpus.py",
)


def test_sha256_path_hashes_real_multichunk_bytes(tmp_path: Path) -> None:
    """A file crossing the stream boundary has the standard-library digest."""
    payload = b"cohort-byte-contract\n" * 60_000
    artifact = tmp_path / "cohort-artifact.bin"
    artifact.write_bytes(payload)

    assert sha256_path(artifact) == hashlib.sha256(payload).hexdigest()


#: Both spellings of a function definition. A private digest helper written
#: ``async def`` is a duplicate exactly as a sync one is, and reading only the
#: sync form leaves the absence claim below satisfied because the helper was
#: never looked at.
_FUNCTION_DEFINITIONS: Final = (ast.FunctionDef, ast.AsyncFunctionDef)


def _builds_sha256_digest(node: ast.AST) -> bool:
    """Is this a ``sha256(...)`` call, however the name was imported?

    ``hashlib.sha256(...)`` leaves an attribute callee; ``from hashlib import
    sha256`` leaves a bare name. Matching only the attribute form let the
    second spelling build a private accumulator invisibly, and it is the
    spelling a helper reaches for when it wants one line instead of two.
    """
    if not isinstance(node, ast.Call):
        return False
    callee = node.func
    if isinstance(callee, ast.Attribute):
        return callee.attr == "sha256" and isinstance(callee.value, ast.Name) and callee.value.id == "hashlib"
    return isinstance(callee, ast.Name) and callee.id == "sha256"


def _streams_sha256(function: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Report whether ``function`` builds its own ``sha256`` accumulator.

    A hash of in-memory bytes or text is not a duplicate of the streamed-file
    owner. The duplicate requires both a ``sha256`` call and a file handle
    ``read`` in the same helper, and that conjunction is what keeps the bare
    spelling above from matching an unrelated function of the same name.
    """
    builds_digest = any(_builds_sha256_digest(node) for node in ast.walk(function))
    streams_file = any(
        isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "read"
        for node in ast.walk(function)
    )
    return builds_digest and streams_file


#: Floor for the parsed surface behind the absence claim below. Live: the
#: three re-homed sites define 8, 20 and 21 functions. A floor, not a count.
_MINIMUM_SITE_FUNCTIONS = 3


_PLANTED_PRIVATE_HELPERS: Final = {
    "attribute callee": "def _digest(path):"
    + chr(10)
    + "    d = hashlib.sha256()"
    + chr(10)
    + "    d.update(path.read())"
    + chr(10)
    + "    return d",
    "bare imported callee": "def _digest(path):"
    + chr(10)
    + "    d = sha256()"
    + chr(10)
    + "    d.update(path.read())"
    + chr(10)
    + "    return d",
    "async attribute callee": "async def _digest(path):"
    + chr(10)
    + "    d = hashlib.sha256()"
    + chr(10)
    + "    d.update(path.read())"
    + chr(10)
    + "    return d",
    "async bare callee": "async def _digest(path):"
    + chr(10)
    + "    d = sha256()"
    + chr(10)
    + "    d.update(path.read())"
    + chr(10)
    + "    return d",
}


@pytest.mark.parametrize("label", sorted(_PLANTED_PRIVATE_HELPERS))
def test_a_private_streamed_digest_helper_is_detected_however_it_is_written(label: str) -> None:
    """Teeth: the absence claim is only as wide as the spellings it can parse.

    Each of these is a private streamed-file digest helper, the exact duplicate
    the gate forbids, and each was once invisible: the walk read only ``def``
    and the accumulator matched only ``hashlib.sha256``.
    """
    tree = ast.parse(_PLANTED_PRIVATE_HELPERS[label] + chr(10))
    defined = [node for node in ast.walk(tree) if isinstance(node, _FUNCTION_DEFINITIONS)]

    assert [node.name for node in defined if _streams_sha256(node)] == ["_digest"], label


def test_an_in_memory_digest_is_not_a_streamed_duplicate() -> None:
    """The conjunction is what keeps the bare spelling from over-matching.

    Hashing bytes already in hand is not the streamed-file owner's job, so a
    helper with no file read must stay unflagged however it names sha256.
    """
    tree = ast.parse("def _digest(payload):" + chr(10) + "    return sha256(payload).hexdigest()" + chr(10))
    defined = [node for node in ast.walk(tree) if isinstance(node, _FUNCTION_DEFINITIONS)]

    assert [node.name for node in defined if _streams_sha256(node)] == []


@pytest.mark.parametrize("relative_path", _REHOMED_STREAMED_DIGEST_SITES)
def test_rehomed_digest_site_declares_no_private_digest_helper(relative_path: str) -> None:
    """Every production streamed-file digest resolves through the one owner.

    The claim is an absence over the functions the site defines, so a module
    gutted to a stub carries no private helper for the same reason it carries
    nothing at all. These are RE-HOMED sites in a repository actively moving
    symbols between modules, which is precisely how a file becomes a shell
    while keeping its path and passing this gate.
    """
    repository_root = REPO_ROOT
    tree = ast.parse((repository_root / relative_path).read_text(encoding="utf-8"))
    defined = [node for node in ast.walk(tree) if isinstance(node, _FUNCTION_DEFINITIONS)]

    assert len(defined) >= _MINIMUM_SITE_FUNCTIONS, (
        f"{relative_path} defines only {len(defined)} function(s); below this it declares no "
        "private digest helper because it declares almost nothing"
    )

    streaming_helpers = [node.name for node in defined if _streams_sha256(node)]

    assert streaming_helpers == []


@pytest.mark.parametrize("module_name", ("cohort_manifest", "smoke_homebrew"))
def test_rehomed_digest_module_uses_the_canonical_helper(module_name: str) -> None:
    """The re-homed module resolves file digests through the one owner."""
    module = importlib.import_module(f"dev.packaging.{module_name}")

    assert module.sha256_path is sha256_path


@pytest.mark.parametrize(
    "relative_path",
    ("dev/packaging/smoke_homebrew.py", "dev/corpus/sync_aeat_record_design_corpus.py"),
)
def test_standalone_digest_entrypoint_starts_from_a_bare_script_path(relative_path: str) -> None:
    """Standalone lanes load the canonical owner without package invocation."""
    repository_root = REPO_ROOT
    completed = subprocess.run(  # noqa: S603 - fixed repository script paths exercised with --help.
        [sys.executable, str(repository_root / relative_path), "--help"],
        cwd=repository_root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert completed.returncode == 0, completed.stderr
