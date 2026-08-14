"""One owner for the canonical record encoding, enforced structurally.

A canonical *record* is JSON whose exact bytes carry meaning: they key a
digest, or they are what gets persisted and later compared byte-for-byte. The
encoding of those bytes -- UTF-8 rather than ASCII escapes, non-finite numbers
refused -- is ruled once in :mod:`cadrumo.core.hashing` and nowhere else,
because two encoders disagreeing on one record is not a style difference: the
same record hashes to two values, and a byte ceiling measured under one
spelling is wrong under the other.

The detected shape is a ``json.dumps(...)`` whose result is immediately encoded
to bytes, excluding indented emits. Both narrowings are load-bearing.

Requiring *bytes* is deliberately narrower than "any compact ``json.dumps``":
rendering JSON *text* -- an NDJSON log line, a CLI envelope on stdout, a
generated file -- is a different job with no byte-identity contract, and
sweeping it in here would bury the one rule that matters under a dozen
judgement calls about display code. Bytes are what a digest and a persisted row
actually consume.

Excluding ``indent=`` is not a loophole, because the canonical encoding is
compact by definition. An indented payload has already opted out of byte
identity: it cannot be the input to a digest anyone reproduces, so a writer
reaching for ``indent=`` to slip past this gate has, in the same move, stopped
writing the thing the gate protects. The two local sidecars that legitimately
do this -- the login-throttle state and the wrapped bucket-DEK document -- are
read back through ``model_validate_json`` and never digested or byte-compared;
their indentation is a deliberate operator-readability choice.

The companion behavioural contract for the encoding itself lives in
``core/tests/test_hashing.py``.
"""

from __future__ import annotations

import ast

import pytest

from . import SRC_CADRUMO, aeat_relative, production_ast_items

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: The sole module entitled to build canonical-record bytes from scratch.
_OWNER = "core/hashing.py"

#: Byte-producing ``json.dumps`` sites that are not canonical records.
#: Keyed by (``src/cadrumo``-relative POSIX path, enclosing function) -> reason.
#: Keyed by function rather than line so an unrelated edit above cannot silently
#: move an entry off its site. Every entry states why the owner is wrong for it,
#: never that it has not been migrated yet.
_ALLOWLIST: dict[tuple[str, str], str] = {
    ("adapters/outbound/aeat/auth/_clave_movil_page_flow.py", "_dump_diagnostic"): (
        "NOT a canonical record: a best-effort encrypted diagnostic snapshot whose "
        "payload deliberately carries `default=str` so an un-serialisable Playwright "
        "value degrades to its repr instead of losing the whole capture. The owner "
        "refuses such a value by design, which is right for a record and wrong for a "
        "diagnostic. Nothing digests or byte-compares these bytes."
    ),
}


def _enclosing_functions(tree: ast.AST) -> dict[int, str]:
    """Map each node id to the name of the function lexically enclosing it."""
    owners: dict[int, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for descendant in ast.walk(node):
            owners.setdefault(id(descendant), node.name)
    return owners


def _byte_producing_dumps(tree: ast.AST) -> list[tuple[int, str]]:
    """Return ``(lineno, enclosing function)`` for each compact ``json.dumps(...).encode(...)``."""
    owners = _enclosing_functions(tree)
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "encode"):
            continue
        inner = func.value
        if not (isinstance(inner, ast.Call) and isinstance(inner.func, ast.Attribute) and inner.func.attr == "dumps"):
            continue
        if any(keyword.arg == "indent" for keyword in inner.keywords):
            continue
        found.append((inner.lineno, owners.get(id(node), "<module>")))
    return found


def test_no_production_module_builds_canonical_record_bytes_outside_the_owner() -> None:
    """A ninth encoder is a fork of the record format, so it fails here first."""
    offenders: list[str] = []
    for path, tree in production_ast_items():
        relative = aeat_relative(path)
        if relative == _OWNER:
            continue
        for lineno, function in _byte_producing_dumps(tree):
            if (relative, function) in _ALLOWLIST:
                continue
            offenders.append(f"  {relative}:{lineno} (in {function})")
    assert not offenders, (
        "Canonical record bytes must come from cadrumo.core.hashing "
        "(canonical_json_bytes / bounded_canonical_json_bytes), not an inline "
        "json.dumps(...).encode(...):\n" + "\n".join(sorted(offenders))
    )


def test_canonical_record_allowlist_has_no_stale_entries() -> None:
    """An allowlist that outlives its site stops describing the tree."""
    live: set[tuple[str, str]] = set()
    for path, tree in production_ast_items():
        relative = aeat_relative(path)
        live.update((relative, function) for _, function in _byte_producing_dumps(tree))
    stale = sorted(set(_ALLOWLIST) - live)
    assert not stale, "Stale _ALLOWLIST entries no longer present in the source; remove them:\n" + "\n".join(
        f"  {path}: {function}" for path, function in stale
    )


def test_every_allowlist_entry_states_a_reason() -> None:
    """The allowlist is where the judgement moves, so it must carry the judgement."""
    unexplained = sorted(key for key, reason in _ALLOWLIST.items() if len(reason.strip()) < 40)
    assert not unexplained, f"Allowlist entries without a substantive reason: {unexplained}"


def test_the_owner_module_is_where_this_gate_thinks_it_is() -> None:
    """A rename of the owner must red this gate rather than pass it vacuously."""
    owner_path = SRC_CADRUMO / _OWNER
    assert owner_path.is_file(), f"canonical-record owner missing at {_OWNER}"
    source = owner_path.read_text(encoding="utf-8")
    assert "def canonical_json_bytes(" in source
    assert "def bounded_canonical_json_bytes(" in source
    assert "ensure_ascii=False" in source
    assert "allow_nan=False" in source
