"""Hard-cut regression gate for the retired Modelo 303 revision."""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable
from pathlib import Path

import pytest

from .....core.resources import resources
from .....tests import SRC_CADRUMO, package_python_files, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _retired_identifier_from_single_refusal_assertion() -> str:
    """Return the retired identifier while proving this gate names it once only."""
    path = Path(__file__).resolve()
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    expected = f"{2023}-y-siguientes"
    mentions: list[str] = []
    for assertion in (node for node in ast.walk(tree) if isinstance(node, ast.Assert)):
        mentions.extend(
            node.value
            for node in ast.walk(assertion.test)
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value == expected
        )
    assert mentions == [expected]
    assert source.count(expected) == 1
    return expected


def _cutover_surface_files() -> tuple[Path, ...]:
    """Return executable, test, fixture, and locale surfaces outside registry data."""
    package_files = package_python_files()
    locale_files = tuple(sorted((SRC_CADRUMO / "locales").glob("*.yml")))
    return tuple(sorted((*package_files, *locale_files)))


def _static_string(node: ast.AST) -> str | None:
    """Evaluate only literal string concatenations that can disguise a retired id."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _static_string(node.left)
        right = _static_string(node.right)
        if left is not None and right is not None:
            return left + right
    return None


def _retired_identifier_locations(paths: Iterable[Path], *, retired_identifier: str) -> tuple[str, ...]:
    """Find retired identifiers only where their enclosing subject is Modelo 303."""
    self_path = Path(__file__).resolve()
    locations: list[str] = []
    for path in paths:
        if path.resolve() == self_path:
            continue
        source = path.read_text(encoding="utf-8", errors="replace")
        if path.suffix == ".yml":
            locations.extend(_m303_locale_retired_identifier_locations(path, source, retired_identifier))
        elif path.suffix == ".py":
            try:
                tree = ast.parse(source, filename=str(path))
            except SyntaxError:
                tree = None
            for line_number, line in enumerate(source.splitlines(), start=1):
                if retired_identifier not in line:
                    continue
                if tree is None:
                    nearby = "\n".join(source.splitlines()[max(0, line_number - 6) : line_number + 5])
                    is_m303_context = bool(_M303_CONTEXT.search(nearby))
                else:
                    is_m303_context = _is_m303_source_line(tree, source, line_number)
                if is_m303_context:
                    locations.append(f"{repo_relative(path)}:{line_number}")
    return tuple(sorted(set(locations)))


_M303_CONTEXT = re.compile(r"(?:m303|modelo[_ ]303|model 303|[\"']303[\"'])", re.IGNORECASE)


def _is_m303_source_line(tree: ast.AST, source: str, line_number: int) -> bool:
    """Return whether a source line belongs to one M303-specific test or module claim."""
    functions = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef))
        and node.lineno <= line_number <= (node.end_lineno or node.lineno)
    ]
    if functions:
        innermost = min(functions, key=lambda node: (node.end_lineno or node.lineno) - node.lineno)
        scope = ast.get_source_segment(source, innermost) or ""
        return bool(_M303_CONTEXT.search(scope))
    lines = source.splitlines()
    lower = max(0, line_number - 6)
    upper = min(len(lines), line_number + 5)
    return bool(_M303_CONTEXT.search("\n".join(lines[lower:upper])))


def _m303_locale_retired_identifier_locations(path: Path, source: str, retired_identifier: str) -> tuple[str, ...]:
    """Find retired keys and prose only inside the Modelo 303 locale subtree."""
    locations: list[str] = []
    in_modelo_303 = False
    lines = source.splitlines()
    for line_number, line in enumerate(lines, start=1):
        if re.match(r"^    '303':\s*$", line):
            in_modelo_303 = True
            continue
        if in_modelo_303 and re.match(r"^    '[0-9]{3}':\s*$", line):
            in_modelo_303 = False
        if retired_identifier not in line:
            continue
        nearby = "\n".join(lines[max(0, line_number - 6) : min(len(lines), line_number + 5)])
        if in_modelo_303 or _M303_CONTEXT.search(nearby):
            locations.append(f"{repo_relative(path)}:{line_number}")
    return tuple(locations)


def _m303_selector_redeclaration_locations(paths: Iterable[Path], *, revision_ids: frozenset[str]) -> tuple[str, ...]:
    """Reject dict/branch copies that map Modelo 303 to a revision outside the selector."""
    locations: list[str] = []
    for path in paths:
        if path.suffix != ".py" or path.resolve() == Path(__file__).resolve():
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=str(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Dict, ast.If, ast.IfExp)):
                continue
            strings = {
                value
                for descendant in ast.walk(node)
                if isinstance(descendant, ast.Constant) and isinstance(descendant.value, str)
                for value in (descendant.value,)
            }
            if "303" in strings and strings.intersection(revision_ids):
                locations.append(f"{repo_relative(path)}:{node.lineno}")
    return tuple(sorted(set(locations)))


def test_m303_retired_revision_is_refused_and_cannot_reenter_source_surfaces() -> None:
    """The deleted revision has no runtime, fixture, locale, alias, or selector path."""
    retired_identifier = _retired_identifier_from_single_refusal_assertion()
    modelo = resources().modelos.authority.modelo("303")
    assert "2023-y-siguientes" not in modelo.revisions

    surface_files = _cutover_surface_files()
    legacy_locations = _retired_identifier_locations(surface_files, retired_identifier=retired_identifier)
    assert legacy_locations == (), "retired Modelo 303 revision reappeared:\n  " + "\n  ".join(legacy_locations)

    selector_locations = _m303_selector_redeclaration_locations(
        surface_files,
        revision_ids=frozenset(modelo.revisions),
    )
    assert selector_locations == (), "Modelo 303 revision selection was redeclared:\n  " + "\n  ".join(selector_locations)

    construct_key = "modelo.schema.303.construct.modelo-303-iva-autoliquidacion.field.title"
    for revision_id in ("2023", "2024-hasta-08-y-2t", "2024-desde-09-y-3t", "2025", "2026-y-siguientes"):
        construct = next(
            item
            for item in modelo.revisions[revision_id].constructs
            if item.id == "modelo-303-iva-autoliquidacion"
        )
        assert construct.localization_key == construct_key
