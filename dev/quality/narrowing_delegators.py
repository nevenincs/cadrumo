"""Detector: an unreached function that narrows a sibling's result to one field.

Five of these were removed during the reachability campaign, and they failed the
same way each time. A shipped function whose whole body is
``return sibling(...).field`` returns strictly less than the sibling it calls:
the record's other fields go with it, and where one of those fields is a refusal,
a coverage manifest, or a ``superseded_by`` pointer, the caller that reached for
the shorter name got an answer where the product had a finding.

They survive because they read as convenience. The audit sees them as merely
unused; nothing said the narrowing was the hazard. So the shape is named here:
a function that is BOTH a bare narrowing of a same-module sibling AND unreferenced
by production code is the shape that was wrong five times, and the ledger has no
entry excusing it.

Deliberately narrow. It does not object to a narrowing that production calls --
a reached one is a real abstraction with a real caller -- nor to a function that
does anything besides the single return. Only the unreached bare narrowing.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Final

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]

SHIPPED_ROOT: Final[Path] = _REPO_ROOT / "src" / "cadrumo"

#: Every tree that ships a caller. Restricting the caller search to the tree that
#: ships the DEFINITIONS is the bug this constant exists to prevent: the first run
#: of this detector reported ``check_m303_annual_orden_manifest`` unreached while
#: ``dev/registry/analysis/m303_orden_anual.py`` imports and calls it. A design-time
#: consumer is a real consumer, and the ledger's taxonomy has classes for exactly
#: that readership.
CALLER_ROOTS: Final[tuple[Path, ...]] = (
    SHIPPED_ROOT,
    _REPO_ROOT / "src" / "cadrumo_harness",
    _REPO_ROOT / "dev",
)


def _narrowing_target(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    """Return the sibling called, when the body is one bare narrowing return.

    The body may carry a docstring; anything else -- a guard, a second statement,
    a bare call return with no field access -- is not this shape.
    """
    body = list(node.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]
    if len(body) != 1 or not isinstance(body[0], ast.Return) or body[0].value is None:
        return None
    value = body[0].value
    if not isinstance(value, ast.Attribute | ast.Subscript):
        return None
    inner = value.value
    if not isinstance(inner, ast.Call) or not isinstance(inner.func, ast.Name):
        return None
    return inner.func.id


def _owner_uses_it(tree: ast.Module, name: str) -> bool:
    """Whether the defining module itself references ``name`` outside its own ``def``.

    The owner module must be searched, not skipped. Excluding it is the single
    most productive false-positive source this detector has: on its first run it
    called ``generate_m303_annual_orden_manifest`` unreached while the sibling
    ``render_m303_annual_orden_manifest`` calls it four lines below, and made the
    same claim about ``read_total_system_memory_bytes``, whose caller is the very
    next function in the file. A same-module caller is a real caller.

    The name's own ``def`` and its ``__all__`` entry are not uses, so this walks
    load-context ``Name`` nodes rather than matching text.

    It deliberately does NOT count an attribute tail. A module-level function is
    reached from inside its own module by a bare name; ``reading.total_bytes`` is
    a field read on some object, and counting it would silence a narrowing that
    happens to share a name with a field -- which, for a detector whose whole
    subject is functions named after the field they return, is the likeliest
    collision there is. An over-broad owner check makes the gate quietly inert,
    a worse failure than the false positives it was added to prevent.
    """
    return any(
        isinstance(node, ast.Name) and node.id == name and isinstance(node.ctx, ast.Load)
        for node in ast.walk(tree)
    )


def _referenced_elsewhere(roots: tuple[Path, ...], name: str, owner: Path) -> bool:
    """Whether any non-test file besides the owner mentions ``name``."""
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*.py"):
            if path == owner or "tests" in path.parts or path.name.startswith("test_"):
                continue
            if name in path.read_text(encoding="utf-8", errors="ignore"):
                return True
    return False


def unreached_narrowings(root: Path, caller_roots: tuple[Path, ...] | None = None) -> list[str]:
    """Return ``module::function -> sibling`` for every offending shape."""
    caller_roots = (root,) if caller_roots is None else caller_roots
    offences: list[str] = []
    for path in sorted(root.rglob("*.py")):
        if "tests" in path.parts or path.name.startswith("test_"):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        defined = {n.name for n in tree.body if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)}
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            target = _narrowing_target(node)
            if target is None or target not in defined or target == node.name:
                continue
            if _owner_uses_it(tree, node.name) or _referenced_elsewhere(caller_roots, node.name, path):
                continue
            offences.append(f"{path.relative_to(root).as_posix()}::{node.name} -> {target}(...)")
    return offences


def main() -> int:
    """Report every offending shape and exit non-zero when any remains."""
    offences = unreached_narrowings(SHIPPED_ROOT, CALLER_ROOTS)
    for offence in offences:
        print(offence)
    if offences:
        print(
            f"\n{len(offences)} function(s) narrow a same-module sibling to one field and no shipped "
            "code calls them. Delete the narrowing and let callers read the whole record, or give it "
            "a production caller.",
        )
    return 1 if offences else 0


if __name__ == "__main__":
    raise SystemExit(main())
