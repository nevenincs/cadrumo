"""Nothing removes a deletion tombstone without verifying it first.

``remove_profile_custody_deletion_tombstone`` deletes a directory tree. The
adapter-level guards that decide WHICH tree may be destroyed live in
``verify_profile_custody_deletion_tombstone``, and they are only worth anything
if the removal is actually preceded by that verification on the live path.

That ordering is the whole protection, and it is invisible to the adapter tests:
they exercise the verifier and the remover in isolation, so dropping the verify
call from the service would leave every one of them green while the product
deleted a tree nobody checked. The invariant is lexical -- verify appears before
remove inside one function body -- so it is asserted against the source rather
than by observing a run, which would need the flow to reach the destructive step
before it could report anything.

The gate is scoped to the removal it names rather than generalised into "every
destructive call needs a matching verify", because the pairing is a property of
this protocol and a broader rule would need its own inventory of what counts.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_REMOVE = "remove_profile_custody_deletion_tombstone"
_VERIFY = "verify_profile_custody_deletion_tombstone"

#: The application package whose delete flow owns the ordering.
_PACKAGE = Path(__file__).resolve().parents[1]

#: A delete step that destroys without checking, used to prove the detector.
_UNGUARDED_SAMPLE = (
    "def remove_step(self):\n"
    "    self._adapters.remove_profile_custody_deletion_tombstone(profile_id=1)\n"
)

#: The same step with the verification restored ahead of it.
_GUARDED_SAMPLE = (
    "def remove_step(self):\n"
    "    self._adapters.verify_profile_custody_deletion_tombstone(profile_id=1)\n"
    "    self._adapters.remove_profile_custody_deletion_tombstone(profile_id=1)\n"
)


def _called_names(node: ast.AST) -> list[tuple[int, str]]:
    """Return ``(line, callee)`` for every call under ``node``."""
    calls: list[tuple[int, str]] = []
    for inner in ast.walk(node):
        if not isinstance(inner, ast.Call):
            continue
        target = inner.func
        name = target.attr if isinstance(target, ast.Attribute) else getattr(target, "id", None)
        if name:
            calls.append((inner.lineno, name))
    return calls


def _unverified_removals(tree: ast.AST) -> list[int]:
    """Return the line of every removal not preceded by a verification.

    Preceded is judged inside the enclosing function: the verification has to
    appear on an earlier line of the same body, which is exactly how the delete
    step is written and the only arrangement that guarantees the check ran.
    """
    offending: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        calls = _called_names(node)
        removals = [line for line, name in calls if name == _REMOVE]
        verifications = [line for line, name in calls if name == _VERIFY]
        offending.extend(
            line for line in removals if not any(seen < line for seen in verifications)
        )
    return offending


def _production_modules() -> list[Path]:
    """Return the package's production modules, excluding its own tests."""
    return [
        path
        for path in _PACKAGE.rglob("*.py")
        if "tests" not in path.parts and path.name != "conftest.py"
    ]


def _removal_sites() -> list[tuple[Path, int]]:
    """Return every production call site of the destructive removal."""
    sites: list[tuple[Path, int]] = []
    for path in _production_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        sites.extend((path, line) for line, name in _called_names(tree) if name == _REMOVE)
    return sites


def test_no_production_removal_runs_without_a_preceding_verification() -> None:
    """DISCRIMINATING: the ordering every adapter guard depends on."""
    offenders = [
        f"{path.name}:{line}"
        for path in _production_modules()
        for line in _unverified_removals(ast.parse(path.read_text(encoding="utf-8")))
    ]

    assert not offenders, (
        f"these calls to {_REMOVE} are not preceded by {_VERIFY} in the same function: "
        f"{offenders}. The removal deletes a directory tree, and the verification is what "
        "decides the tree is the one this transaction owns."
    )


def test_the_live_delete_flow_is_actually_the_thing_being_checked() -> None:
    """ANTI-VACUITY: a scan that found no call site would pass for free.

    The gate's value is entirely in the emptiness of its offender list, and an
    empty file list produces that emptiness without checking anything. The real
    call site is pinned to the module that owns the delete transaction.
    """
    sites = _removal_sites()

    assert sites, "no production call site found; the gate is checking nothing"
    assert {path.name for path, _line in sites} == {"_custody_service.py"}


def test_the_detector_flags_an_unguarded_removal() -> None:
    """ANTI-TAUTOLOGY: proven on source carrying the shape, no tracked file touched."""
    assert _unverified_removals(ast.parse(_UNGUARDED_SAMPLE)) == [2]


def test_the_detector_accepts_a_verified_removal() -> None:
    """The other direction: a correct ordering must not be reported.

    A detector that flagged everything would satisfy the gate above only while
    the tree happened to be empty of removals, and would fail the moment the
    real call site was read.
    """
    assert _unverified_removals(ast.parse(_GUARDED_SAMPLE)) == []
