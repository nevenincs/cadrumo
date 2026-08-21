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
_SESSION_CLASS = "BucketSession"
_OPEN = "open"


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
            if _opens_a_session(scope):
                found.add((repo_relative(path), scope.name))
    return found


def _session_class_aliases(scope: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """Return local names bound to the session CLASS, e.g. ``S = BucketSession``."""
    aliases: set[str] = set()
    for node in ast.walk(scope):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Name):
            continue
        if node.value.id != _SESSION_CLASS:
            continue
        aliases.update(target.id for target in node.targets if isinstance(target, ast.Name))
    return aliases


def _opener_aliases(scope: ast.FunctionDef | ast.AsyncFunctionDef, classes: set[str]) -> set[str]:
    """Return local names bound to the opener, e.g. ``opener = BucketSession.open``."""
    aliases: set[str] = set()
    for node in ast.walk(scope):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Attribute):
            continue
        if node.value.attr != _OPEN:
            continue
        base = node.value.value
        base_name = base.attr if isinstance(base, ast.Attribute) else getattr(base, "id", None)
        if base_name in classes:
            aliases.update(target.id for target in node.targets if isinstance(target, ast.Name))
    return aliases


def _opens_a_session(scope: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Whether ``scope`` opens a bucket session, however the call is spelled.

    Four spellings, because the attribute call alone is what an ordinary
    refactor walks out of: the direct call, the class bound to a local first,
    the opener bound to a local, and ``getattr``. The last three were MISSED
    until they were probed for -- the same weakness found in the
    composing-write gate, on the surface where the cost is a real taxpayer's
    records written under a published deterministic key.
    """
    classes = {_SESSION_CLASS, *_session_class_aliases(scope)}
    openers = _opener_aliases(scope, classes)
    for node in ast.walk(scope):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == _OPEN:
            base = func.value
            base_name = base.attr if isinstance(base, ast.Attribute) else getattr(base, "id", None)
            if base_name in classes:
                return True
        if isinstance(func, ast.Name) and func.id in openers:
            return True
        if (
            isinstance(func, ast.Call)
            and isinstance(func.func, ast.Name)
            and func.func.id == "getattr"
            and len(func.args) >= 2
            and isinstance(func.args[1], ast.Constant)
            and func.args[1].value == _OPEN
        ):
            base = func.args[0]
            base_name = base.attr if isinstance(base, ast.Attribute) else getattr(base, "id", None)
            if base_name in classes:
                return True
    return False


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

def _scope(*lines: str) -> ast.FunctionDef:
    """Parse a snippet holding exactly one function and return it."""
    tree = ast.parse("\n".join(lines) + "\n")
    scopes = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
    assert len(scopes) == 1, "fixture must hold exactly one function"
    return scopes[0]


def test_a_session_opened_through_an_alias_is_still_seen() -> None:
    """DISCRIMINATING: three spellings that used to walk out of this gate.

    Each is an ordinary refactor -- binding the class, binding the opener,
    reaching through getattr -- and each reported the function as opening no
    session, so the canary requirement never applied to it. On this surface
    the cost of that miss is a real taxpayer's records written under a
    published deterministic key.
    """
    bound_class = _scope(
        "def open_it():",
        "    S = BucketSession",
        "    return S.open(bucket_id='b', unsecured_backend=True)",
    )
    bound_opener = _scope(
        "def open_it():",
        "    opener = BucketSession.open",
        "    return opener(bucket_id='b', unsecured_backend=True)",
    )
    dynamic = _scope(
        "def open_it():",
        "    return getattr(BucketSession, 'open')(bucket_id='b', unsecured_backend=True)",
    )

    assert _opens_a_session(bound_class)
    assert _opens_a_session(bound_opener)
    assert _opens_a_session(dynamic)


def test_an_unrelated_open_is_not_mistaken_for_a_session() -> None:
    """ANTI-TAUTOLOGY: widening must not make every ``.open`` a session.

    ``open`` is among the most common method names there is -- a file, a
    connection, a lock. A detector that flagged them would fill this gate with
    functions that never touch a bucket session, and the requirement it
    enforces would be dismissed as noise rather than read.
    """
    unrelated = _scope(
        "def read_config(store):",
        "    handle = store.open('config.json')",
        "    return handle.read()",
    )
    resumed = _scope(
        "def resume(dek):",
        "    return BucketSession.open_resumed(bucket_id='b', dek=dek)",
    )

    assert not _opens_a_session(unrelated)
    assert not _opens_a_session(resumed)
