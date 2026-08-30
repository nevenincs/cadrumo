"""CI gate: production code uses the :class:`Modelo` enum, not bare code strings.

Walks every production module under ``src/cadrumo`` (tests excluded) and fails if a
bare three-digit modelo-code **string literal** appears in an identifier
position — a comparison, a dict key/value, a call argument, an assignment — where
it should instead reference a :class:`~cadrumo.core.Modelo` member.

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
from collections.abc import Mapping
from pathlib import Path

import pytest

from ...tests import SRC_CADRUMO, aeat_relative, production_ast_items
from ..modelo import Modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: Canonical modelo-code value set.
_CODES: frozenset[str] = frozenset(m.value for m in Modelo)

#: Production modules that own a bare code string for a documented reason.
#: Keyed by (``src/cadrumo``-relative POSIX path, code) → reason. Kept deliberately
#: small; every entry is a judgement call recorded during the Modelo-enum sweep.
_ALLOWLIST: dict[tuple[str, str], str] = {
    ("domain/calculations/registry/_citation_blocklist.py", "100"): (
        "FALSE POSITIVE: RIRPF *article* 100 (urban-rental withholding), not Modelo 100."
    ),
    ("application/filing/_export_parity.py", "111"): (
        "FALSE POSITIVE: M303 *casilla* 111, constructed through validated_casilla_id "
        "and named _M303_CASILLA_111. The casilla number collides with Modelo 111's code."
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


_SKIP_FILES: frozenset[str] = frozenset({"core/_modelo.py"})
"""The enum's own declaration module, where the code strings are the values."""


def bare_modelo_code_offenders(relative: str, tree: ast.Module) -> list[str]:
    """Return ``path:line`` offender strings for one module's bare modelo codes.

    Pure over ``(relative path, tree)`` so the discrimination tests below can
    feed it a synthetic violating module and prove it fires. Allowlisted
    ``(path, code)`` pairs are excluded here; the caller reconciles staleness.
    """
    if relative in _SKIP_FILES:
        return []
    return _offenders_ignoring_skip(relative, tree)


def _offenders_ignoring_skip(relative: str, tree: ast.Module) -> list[str]:
    """Detection body with ``_SKIP_FILES`` deliberately not consulted.

    Split out so the skip-liveness test can ask the real detector what a
    skipped module *would* report, which is the only way to tell a skip that is
    still needed from one that has become dead weight.
    """
    excluded = _docstring_const_ids(tree) | _decimal_arg_ids(tree) | _literal_ids(tree)
    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        if node.value not in _CODES or id(node) in excluded:
            continue
        if (relative, node.value) in _ALLOWLIST:
            continue
        offenders.append(
            f'src/cadrumo/{relative}:{node.lineno}: bare modelo code "{node.value}"; use Modelo.M{node.value}'
        )
    return offenders


def _allowlist_keys_present(relative: str, tree: ast.Module) -> set[tuple[str, str]]:
    """Return the allowlist keys this module's source actually still carries."""
    if relative in _SKIP_FILES:
        return set()
    excluded = _docstring_const_ids(tree) | _decimal_arg_ids(tree) | _literal_ids(tree)
    return {
        (relative, node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value in _CODES
        and id(node) not in excluded
        and (relative, node.value) in _ALLOWLIST
    }


def test_no_bare_modelo_code_strings_in_production_identifiers(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """No production module carries a bare modelo-code string where ``Modelo`` belongs.

    Self-verifying: the code set is recomputed from the live :class:`Modelo` enum
    and the worklist is recomputed from each module's AST on every run, so the
    gate ratchets — it cannot pass with a stale baseline.
    """
    offenders: list[str] = []
    stale_allowlist: set[tuple[str, str]] = set(_ALLOWLIST)

    for path, tree in production_ast_items(source_tree_ast):
        assert isinstance(tree, ast.Module), f"Expected a module AST for {path}, got {type(tree).__name__}"
        rel = aeat_relative(path)
        offenders.extend(bare_modelo_code_offenders(rel, tree))
        stale_allowlist -= _allowlist_keys_present(rel, tree)

    assert not offenders, (
        "Bare modelo-code string literals found in production identifier positions; "
        "import and use the Modelo enum (cadrumo.core.Modelo) instead:\n" + "\n".join(offenders)
    )
    assert not stale_allowlist, "Stale _ALLOWLIST entries no longer present in the source; remove them:\n" + "\n".join(
        f"  {path}: {code}" for path, code in sorted(stale_allowlist)
    )


@pytest.mark.parametrize(
    ("source", "expected_offenders"),
    (
        pytest.param('if unit.modelo != "303":\n    raise ValueError(unit)\n', 1, id="comparison"),
        pytest.param('ROUTES = {"347": handle_347, "349": handle_349}\n', 2, id="dict-keys"),
        pytest.param('register(modelo="130")\n', 1, id="call-keyword-argument"),
        pytest.param('SUPPORTED = frozenset({"100"})\n', 1, id="set-member"),
        pytest.param('DEFAULT_MODELO: str = "390"\n', 1, id="annotated-assignment-without-literal"),
    ),
)
def test_detector_fires_on_a_planted_bare_modelo_code(source: str, expected_offenders: int) -> None:
    """Anti-tautology proof: the detector really catches a planted violation.

    A gate whose only assertion is ``offenders == []`` against a clean tree is
    indistinguishable from a gate that always passes. Each case plants a bare
    code in a real identifier position and asserts the live detector fires.
    Sources are parsed in memory: no violation enters the tree.
    """
    offenders = bare_modelo_code_offenders("application/synthetic/_planted.py", ast.parse(source))

    assert len(offenders) == expected_offenders, f"detector missed the planted violation in:\n{source}"
    assert all("use Modelo.M" in offender for offender in offenders)


@pytest.mark.parametrize(
    "source",
    (
        pytest.param('"""Handles modelo 303 filings."""\n', id="module-docstring"),
        pytest.param('from decimal import Decimal\n\nPERCENT = Decimal("100")\n', id="decimal-scale"),
        pytest.param(
            'from typing import Literal\n\ndef run(modelo: Literal["303"]) -> None:\n    del modelo\n',
            id="literal-annotation",
        ),
        pytest.param(
            'from typing import Literal\n\nmodelo: Literal["100"] = "100"\n',
            id="literal-pinned-default",
        ),
        pytest.param(
            "from ... import Modelo\n\nif unit.modelo != Modelo.M303:\n    raise ValueError(unit)\n", id="enum-member"
        ),
    ),
)
def test_detector_ignores_the_structurally_excluded_shapes(source: str) -> None:
    """The documented exclusions must hold, or authors route around the gate by noise.

    Each shape is a non-identifier occurrence the gate excludes structurally
    rather than by allowlist; a regression here would flood the gate with false
    positives and pressure real entries into ``_ALLOWLIST``.
    """
    assert bare_modelo_code_offenders("application/synthetic/_clean.py", ast.parse(source)) == []


def test_every_skip_file_still_needs_its_skip() -> None:
    """A skipped module must still exist and still carry a bare modelo code.

    ``_ALLOWLIST`` is reconciled by the main scan above, but ``_SKIP_FILES``
    short-circuits :func:`bare_modelo_code_offenders` before any detection runs,
    so nothing else observes it. Presence is not liveness: a skip whose module
    was deleted, renamed, or since converted to the enum keeps exempting the
    path and silently pre-authorises whatever later takes it.

    The check is redundancy, not existence -- drop the skip, re-run the real
    detector over the module, and require it to still fire.
    """
    stale: list[str] = []
    for rel in sorted(_SKIP_FILES):
        path = SRC_CADRUMO / rel
        if not path.is_file():
            stale.append(f"{rel} (file absent)")
            continue
        tree = ast.parse(path.read_bytes().decode("utf-8"))
        if not _offenders_ignoring_skip(rel, tree):
            stale.append(f"{rel} (no bare modelo code remains; drop the skip)")
    assert not stale, "Stale _SKIP_FILES entries; remove them:\n" + "\n".join(f"  {entry}" for entry in stale)


def test_detector_honours_the_allowlist_only_for_its_own_module() -> None:
    """An allowlist entry is keyed by ``(path, code)``, never by code alone.

    Were the key just the code, one documented false positive would silence
    that code across the whole tree.
    """
    allowlisted_path, allowlisted_code = next(iter(_ALLOWLIST))
    source = f'MODELO = "{allowlisted_code}"\n'

    assert bare_modelo_code_offenders(allowlisted_path, ast.parse(source)) == []
    assert len(bare_modelo_code_offenders("application/elsewhere/_x.py", ast.parse(source))) == 1
