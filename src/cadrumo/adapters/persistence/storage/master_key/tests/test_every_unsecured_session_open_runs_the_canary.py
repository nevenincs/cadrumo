"""Every production path that opens a bucket session runs the NIF canary.

The unsecured backend wraps the bucket DEK with a PUBLISHED deterministic
key, so a bucket opened under it offers zero confidentiality. The one thing
standing between that and a real taxpayer's records is
:func:`refuse_unsecured_bucket_with_real_profile`, which refuses the moment
the bucket's profile cannot be proven synthetic.

That guard does NOT check ``session.unsecured_backend`` itself. It trusts its
caller to invoke it, and its own docstring states the obligation in prose:
every path that opens a session outside ``_provider_enter`` "must run exactly
this guard rather than re-deriving it". Prose is the wrong holder for a
fail-open safety obligation -- forgetting it is silent, and what it admits is
real tax data written under a key anyone can read.

This gate moves the obligation into the tree. It enumerates every
``BucketSession.open(...)`` call in production code and requires the enclosing
function to run the canary. ``open_resumed`` is deliberately NOT covered: it
hardcodes ``unsecured_backend=False`` because a resumed session comes from
per-profile password custody, which the unsecured backend never participates
in, so there is no unsecured session for a canary to refuse.

The gate enumerates rather than pattern-matches for a reason recorded across
this campaign: four successive shape-hunting detectors for a different defect
each went green over live instances of it. An enumeration cannot be defeated
by a shape nobody imagined; it can only be defeated by someone writing down an
exemption, which is visible.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ......tests import non_test_package_python_files, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_CANARY = "refuse_unsecured_bucket_with_real_profile"


def _functions_opening_a_session() -> set[tuple[str, str]]:
    """Return every ``(module, function)`` calling ``BucketSession.open``."""
    found: set[tuple[str, str]] = set()
    for path in non_test_package_python_files():
        try:
            tree = ast.parse(Path(path).read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):  # pragma: no cover - unparsable file is its own failure
            continue
        for scope in ast.walk(tree):
            if not isinstance(scope, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            for node in ast.walk(scope):
                if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                    continue
                if node.func.attr != "open":
                    continue
                target = node.func.value
                name = target.attr if isinstance(target, ast.Attribute) else getattr(target, "id", None)
                if name == "BucketSession":
                    found.add((repo_relative(path), scope.name))
    return found


def _runs_the_canary(module: str, function: str) -> bool:
    """Whether ``function`` in ``module`` calls the canary anywhere inside it."""
    tree = ast.parse(Path(module).read_text(encoding="utf-8"))
    for scope in ast.walk(tree):
        if not isinstance(scope, ast.FunctionDef | ast.AsyncFunctionDef) or scope.name != function:
            continue
        for node in ast.walk(scope):
            if isinstance(node, ast.Call):
                called = node.func
                leaf = called.attr if isinstance(called, ast.Attribute) else getattr(called, "id", None)
                if leaf == _CANARY:
                    return True
    return False


def test_a_production_session_open_is_actually_found() -> None:
    """ANTI-TAUTOLOGY: an empty enumeration would pass the gate below vacuously.

    If the AST walk stops matching -- a rename, a moved constructor, a call
    spelled through an alias -- every assertion here goes green while nothing
    is being checked at all. This is the same vacuous shape that hid an empty
    remote-mirror manifest elsewhere in this campaign.
    """
    assert _functions_opening_a_session(), "no production BucketSession.open call found; the walk has stopped matching"


def test_every_production_session_open_runs_the_canary() -> None:
    """A new session-opening path cannot skip the published-key refusal."""
    unguarded = sorted(
        site for site in _functions_opening_a_session() if not _runs_the_canary(site[0], site[1])
    )

    assert not unguarded, (
        f"these functions open a BucketSession without running {_CANARY}: {unguarded}. An unsecured "
        "session wraps the bucket DEK with a published deterministic key, so a path that opens one "
        "without the canary will write a real taxpayer's records under a key anyone can read. Call "
        "the guard, or use BucketSession.open_resumed, which cannot produce an unsecured session."
    )


def test_the_detector_notices_an_unguarded_open() -> None:
    """DISCRIMINATING: prove the checker can fail, not only pass.

    Without this, a checker that never returns False would hold the gate green
    over exactly the defect it exists to catch.
    """
    source = (
        "def open_a_bucket(bucket_id, kek, dek):\n"
        "    return BucketSession.open(bucket_id=bucket_id, kek=kek, dek=dek, unsecured_backend=True)\n"
    )
    tree = ast.parse(source)
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "open"
    ]

    assert calls, "fixture did not produce a session open"
    assert not any(
        isinstance(n, ast.Call)
        and (n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", None)) == _CANARY
        for n in ast.walk(tree)
    )
