"""CI gate: production code uses the :class:`Modelo` enum, not bare code strings.

Walks every production module under ``src/aeat`` (tests excluded) and fails if a
bare three-digit modelo-code **string literal** appears in an identifier
position — a comparison, a dict key/value, a call argument, an assignment — where
it should instead reference a :class:`~aeat.core.Modelo` member.

The code set is derived from the :class:`Modelo` enum itself, so it stays in sync
as members are added (a new modelo dir → a new enum member → tracked here with no
edit to this gate).

Non-identifier occurrences are excluded structurally, not by hand:

* **docstrings** — module / class / function docstring constants;
* **percentages / scales** — a string that is the sole argument of a
  ``Decimal(...)`` call (``Decimal("100")`` is the percent divisor, never a
  modelo);
* **typed closed-value annotations** — a string inside a ``Literal[...]``
  subscript, and a redundant default whose annotation is ``Literal[<same>]``
  (``x: Literal["100"] = "100"`` is already constrained to that exact value).

Three residual sites are genuine judgement calls and live in
:data:`_ALLOWLIST` with a stated reason: two are false positives (a digit-set
membership test and a regulatory **article** number that happen to read as a
modelo code) and one is a CLI command-name token (a user-facing surface literal,
not program logic).

This is the committed companion to the AST gates in ``test_external_constants.py``
and the registry-parity gate in ``test_modelo.py``.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from .._modelo import Modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: Repo-relative ``src/aeat`` root and the canonical modelo-code value set.
_AEAT_ROOT = Path(__file__).parents[2]
_CODES: frozenset[str] = frozenset(m.value for m in Modelo)

#: Production modules that own a bare code string for a documented reason.
#: Keyed by (``src/aeat``-relative POSIX path, code) → reason. Kept deliberately
#: small; every entry is a judgement call recorded during the Modelo-enum sweep.
_ALLOWLIST: dict[tuple[str, str], str] = {
    ("domain/calculations/registry/_citation_blocklist.py", "100"): (
        "FALSE POSITIVE: RIRPF *article* 100 (urban-rental withholding), not "
        "Modelo 100."
    ),
    ("entrypoints/cli/_app_live_borrador_cli.py", "100"): (
        "Typer command-name token (`name=\"100\"`): a CLI surface literal naming "
        "the borrador-100 subgroup, not program logic."
    ),
}


def _docstring_const_ids(tree: ast.Module) -> set[int]:
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                ids.add(id(body[0].value))
    return ids


def _decimal_arg_ids(tree: ast.Module) -> set[int]:
    """Ids of string constants passed to a ``Decimal(...)`` call (percentages/scales)."""
    ids: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else (func.attr if isinstance(func, ast.Attribute) else "")
        if name == "Decimal":
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    ids.add(id(arg))
    return ids


def _literal_string_values(subscript: ast.Subscript) -> set[str]:
    base = subscript.value
    base_name = base.id if isinstance(base, ast.Name) else (base.attr if isinstance(base, ast.Attribute) else "")
    if base_name != "Literal":
        return set()
    return {n.value for n in ast.walk(subscript.slice) if isinstance(n, ast.Constant) and isinstance(n.value, str)}


def _literal_ids(tree: ast.Module) -> set[int]:
    """Ids of string constants that are typed closed values.

    Covers two shapes: a string inside a ``Literal[...]`` subscript, and a
    redundant default whose annotation is ``Literal[<same value>]`` (e.g.
    ``modelo: Literal["100"] = "100"`` — the default is already pinned to that
    exact value by the annotation).
    """
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript):
            for sub in ast.walk(node.slice):
                if isinstance(sub, ast.Constant) and isinstance(sub.value, str) and _literal_string_values(node):
                    ids.add(id(sub))
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            annotation = node.annotation
            value = node.value
            if (
                isinstance(annotation, ast.Subscript)
                and isinstance(value, ast.Constant)
                and isinstance(value.value, str)
                and value.value in _literal_string_values(annotation)
            ):
                ids.add(id(value))
    return ids


def _is_test_path(path: Path) -> bool:
    return "tests" in path.parts or path.name.startswith("test_") or path.name.endswith("_test.py")


def test_no_bare_modelo_code_strings_in_production_identifiers() -> None:
    """No production module carries a bare modelo-code string where ``Modelo`` belongs.

    Self-verifying: the code set is recomputed from the live :class:`Modelo` enum
    and the worklist is recomputed from each module's AST on every run, so the
    gate ratchets — it cannot pass with a stale baseline.
    """
    skip_files = {_AEAT_ROOT / "core" / "_modelo.py"}
    offenders: list[str] = []
    stale_allowlist: set[tuple[str, str]] = set(_ALLOWLIST)

    for path in sorted(_AEAT_ROOT.rglob("*.py")):
        if _is_test_path(path) or path in skip_files:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        excluded = _docstring_const_ids(tree) | _decimal_arg_ids(tree) | _literal_ids(tree)
        rel = path.relative_to(_AEAT_ROOT).as_posix()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            if node.value not in _CODES or id(node) in excluded:
                continue
            key = (rel, node.value)
            if key in _ALLOWLIST:
                stale_allowlist.discard(key)
                continue
            offenders.append(
                f"src/aeat/{rel}:{node.lineno}: bare modelo code \"{node.value}\"; "
                f"use Modelo.M{node.value}"
            )

    assert not offenders, (
        "Bare modelo-code string literals found in production identifier positions; "
        "import and use the Modelo enum (aeat.core.Modelo) instead:\n" + "\n".join(offenders)
    )
    assert not stale_allowlist, (
        "Stale _ALLOWLIST entries no longer present in the source; remove them:\n"
        + "\n".join(f"  {path}: {code}" for path, code in sorted(stale_allowlist))
    )
