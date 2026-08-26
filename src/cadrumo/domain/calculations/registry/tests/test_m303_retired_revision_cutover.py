"""Hard-cut regression gate for the retired Modelo 303 revision."""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable
from pathlib import Path

import pytest

from .....core.directory_scan import scan_directory
from .....tests import SRC_CADRUMO, package_python_files, repo_relative
from ..authority import bundled_authority

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
    locale_files = scan_directory(SRC_CADRUMO / "locales", pattern="*.yml")
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
            for line_number, line in enumerate(source.splitlines(), start=1):
                if retired_identifier not in line:
                    continue
                if _is_m303_source_line(source, line_number):
                    locations.append(f"{repo_relative(path)}:{line_number}")
    return tuple(sorted(set(locations)))


_M303_CONTEXT = re.compile(r"(?:m303|modelo[_ ]303|model 303|[\"']303[\"'])", re.IGNORECASE)
_MODELO_MARKER = re.compile(
    r"(?:\bm(\d{3})(?!\d)|modelo[_ ](\d{3})|model (\d{3})|[\"'](\d{3})[\"'])",
    re.IGNORECASE,
)


def _is_m303_source_line(source: str, line_number: int) -> bool:
    """Return whether the NEAREST modelo named around this line is Modelo 303.

    Attribution is by proximity rather than by enclosing scope because the
    retired identifier is a legitimate, current revision id for sibling modelos
    -- Modelo 180 and Modelo 721 both ship one. A scope-wide search flags a
    Modelo 180 assertion whenever anything else in the same function happens to
    mention Modelo 303, which is how a passing corpus reads as a violation.
    """
    lines = source.splitlines()
    nearest: tuple[int, int, str] | None = None
    for index, line in enumerate(lines, start=1):
        for match in _MODELO_MARKER.finditer(line):
            modelo = next(group for group in match.groups() if group)
            candidate = (abs(index - line_number), 0 if index <= line_number else 1, modelo)
            if nearest is None or candidate[:2] < nearest[:2]:
                nearest = candidate
    return nearest is not None and nearest[2] == "303"


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


def _constant_strings(node: ast.AST) -> set[str]:
    """Return every string constant appearing anywhere beneath one node."""
    return {
        descendant.value
        for descendant in ast.walk(node)
        if isinstance(descendant, ast.Constant) and isinstance(descendant.value, str)
    }


def _m303_selector_redeclaration_locations(paths: Iterable[Path], *, revision_ids: frozenset[str]) -> tuple[str, ...]:
    """Reject dict/branch copies that MAP Modelo 303 onto one of its revisions.

    A redeclaration answers "which revision applies to Modelo 303", so the
    modelo token has to sit in the deciding position: a dict KEY whose value
    carries a revision id, or a branch whose TEST compares against ``"303"``
    and whose arms yield one. Merely carrying both tokens is what every
    work-unit, receipt and report fixture in the tree does, and several of the
    modelo's live revision ids are bare four-digit years, so a
    both-tokens-present rule reads the whole corpus as a selector.
    """
    locations: list[str] = []
    for path in paths:
        if path.suffix != ".py" or path.resolve() == Path(__file__).resolve():
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=str(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Dict):
                mapped = any(
                    isinstance(key, ast.Constant) and key.value == "303" and _constant_strings(value) & revision_ids
                    for key, value in zip(node.keys, node.values, strict=True)
                    if key is not None
                )
            elif isinstance(node, (ast.If, ast.IfExp)):
                arms: list[ast.AST] = (
                    [node.body, node.orelse] if isinstance(node, ast.IfExp) else [*node.body, *node.orelse]
                )
                mapped = "303" in _constant_strings(node.test) and any(
                    _constant_strings(arm) & revision_ids for arm in arms
                )
            else:
                continue
            if mapped:
                locations.append(f"{repo_relative(path)}:{node.lineno}")
    return tuple(sorted(set(locations)))


def test_m303_retired_revision_is_refused_and_cannot_reenter_source_surfaces() -> None:
    """The deleted revision has no runtime, fixture, locale, alias, or selector path."""
    retired_identifier = _retired_identifier_from_single_refusal_assertion()
    modelo = bundled_authority().modelo("303")
    assert "2023-y-siguientes" not in modelo.revisions

    surface_files = _cutover_surface_files()
    legacy_locations = _retired_identifier_locations(surface_files, retired_identifier=retired_identifier)
    assert legacy_locations == (), "retired Modelo 303 revision reappeared:\n  " + "\n  ".join(legacy_locations)

    selector_locations = _m303_selector_redeclaration_locations(
        surface_files,
        revision_ids=frozenset(modelo.revisions),
    )
    assert selector_locations == (), "Modelo 303 revision selection was redeclared:\n  " + "\n  ".join(
        selector_locations
    )

    construct_key = "modelo.schema.303.construct.modelo-303-iva-autoliquidacion.field.title"
    for revision_id in ("2023", "2024-hasta-08-y-2t", "2024-desde-09-y-3t", "2025", "2026-y-siguientes"):
        construct = next(
            item for item in modelo.revisions[revision_id].constructs if item.id == "modelo-303-iva-autoliquidacion"
        )
        assert construct.localization_key == construct_key
