"""One owner for the canonical record encoding, enforced structurally.

A canonical *record* is JSON whose exact bytes carry meaning: they key a
digest, or they are what gets persisted and later compared byte-for-byte. The
encoding of those bytes -- UTF-8 rather than ASCII escapes, non-finite numbers
refused -- is ruled once in :mod:`cadrumo.core.hashing` and nowhere else,
because two encoders disagreeing on one record is not a style difference: the
same record hashes to two values, and a byte ceiling measured under one
spelling is wrong under the other.

The detected shape is a JSON serialisation whose result is immediately encoded
to bytes, excluding indented emits. The serialisation is matched on the called
NAME, so the module-level ``json.dumps``, an aliased module, a bare ``dumps``
from ``from json import dumps``, ``JSONEncoder(...).encode(...)`` and a
dynamically imported ``import_module("json").dumps`` all trip it alike. Reading
the name rather than resolving the module is deliberate: a dynamic import
builds its target from a string the AST cannot follow, so a scanner that
insisted on proving the module is ``json`` would be blind to precisely the
escape the next author reaches for.

The two remaining narrowings are load-bearing.

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
from typing import cast

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


def _callee_name(func: ast.expr) -> str:
    """Return the called name, however the callable was reached.

    Deliberately reads the trailing name rather than resolving the module, so
    ``json.dumps``, ``j.dumps`` under an alias, a bare ``dumps`` pulled in by
    ``from json import dumps``, and ``import_module("json").dumps`` all answer
    the same. A dynamic import builds its target from a string the AST cannot
    follow, so a scanner that insisted on proving the module is ``json`` would
    be blind to exactly the escape an author reaches for next.
    """
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


def _serialises_to_str(node: ast.expr) -> bool:
    """Report whether ``node`` is a JSON serialisation producing ``str``."""
    if not isinstance(node, ast.Call):
        return False
    if _callee_name(node.func) == "dumps":
        # An indented payload has already opted out of byte identity.
        return not any(keyword.arg == "indent" for keyword in node.keywords)
    # ``JSONEncoder(...).encode(payload)`` is the same serialiser reached
    # through its class rather than the module-level convenience wrapper.
    return _callee_name(node.func) == "encode" and (
        isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Call)
        and _callee_name(node.func.value.func) == "JSONEncoder"
    )


def _byte_producing_dumps(tree: ast.AST) -> list[tuple[int, str]]:
    """Return ``(lineno, enclosing function)`` for each JSON serialisation encoded to bytes."""
    owners = _enclosing_functions(tree)
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "encode"):
            continue
        if not _serialises_to_str(func.value):
            continue
        found.append((cast(ast.Call, func.value).lineno, owners.get(id(node), "<module>")))
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


#: How a ninth encoder could be spelled. Each must trip the detector.
_EVASIONS: dict[str, str] = {
    "module attribute": 'import json\ndef f(p): return json.dumps(p, sort_keys=True).encode("utf-8")',
    "aliased module": 'import json as j\ndef f(p): return j.dumps(p).encode("utf-8")',
    "dynamic import": (
        'from importlib import import_module\ndef f(p): return import_module("json").dumps(p).encode("utf-8")'
    ),
    "bare from-import": 'from json import dumps\ndef f(p): return dumps(p, sort_keys=True).encode("utf-8")',
    "encoder class": (
        'from json import JSONEncoder\ndef f(p): return JSONEncoder(sort_keys=True).encode(p).encode("utf-8")'
    ),
}

#: Shapes the detector must leave alone, or it stops describing the rule.
_PERMITTED: dict[str, str] = {
    "indented sidecar": 'import json\ndef f(p): return json.dumps(p, indent=2).encode("utf-8")',
    "text renderer": 'import json\ndef f(p): return json.dumps(p, sort_keys=True) + "\\n"',
    "delegating caller": (
        "from cadrumo.core.hashing import canonical_json_bytes\ndef f(p): return canonical_json_bytes(p)"
    ),
}


@pytest.mark.parametrize("spelling", sorted(_EVASIONS))
def test_the_detector_catches_every_spelling_of_a_ninth_encoder(spelling: str) -> None:
    """Assume the next author reaches for the escape, not the obvious form.

    A dynamic import is the one that matters most: its module target is a
    string the AST cannot follow, so it defeats any scanner that insists on
    proving the callable came from ``json``.
    """
    assert _byte_producing_dumps(ast.parse(_EVASIONS[spelling])) != [], (
        f"the {spelling} spelling of a canonical-record encoder evaded the gate"
    )


@pytest.mark.parametrize("spelling", sorted(_PERMITTED))
def test_the_detector_leaves_the_permitted_shapes_alone(spelling: str) -> None:
    """A gate that fires on correct code trains everyone to route around it."""
    assert _byte_producing_dumps(ast.parse(_PERMITTED[spelling])) == [], (
        f"the {spelling} shape is not a canonical-record encoder but tripped the gate"
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
