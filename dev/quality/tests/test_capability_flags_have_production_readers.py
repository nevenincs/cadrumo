"""Gate: a declared capability or safety flag must have a production reader.

A field or constant named like ``*_supported``, ``*_enabled``, ``*allowed*``,
``*_blocked``, ``*_permitted`` or ``can_*`` reads as a switch that gates
something. When nothing outside its declaration and tests reads it, the
declaration asserts a restriction the product never applies: a row flagged
unexportable is exported anyway, a work unit flagged disallowed is created
anyway. This gate refuses the next such declaration in the domain and
application layers.

Reads are matched by name, so a flag whose name another class also reads passes
even if its own class is never read. The gate catches the flag nobody reads at
all, which is the failure it exists for; it does not prove each read targets the
declaring class.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Final

import pytest

from dev.quality.repository_sources import production_sources

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_FLAG_NAME: Final[re.Pattern[str]] = re.compile(
    r"(_supported$|_enabled$|allowed|_blocked$|_permitted$|^can_)",
    re.IGNORECASE,
)
_DECLARING_LAYERS: Final[tuple[str, ...]] = ("src/cadrumo/domain/", "src/cadrumo/application/")

#: Known unread flags awaiting their owners. Each is a defect, not a data-only
#: field: the reason names what the flag claims to gate and that nothing does.
_KNOWN_UNREAD: Final[Mapping[tuple[str, str], str]] = dict[tuple[str, str], str]()


@dataclass(frozen=True, slots=True)
class _Declaration:
    path: str
    name: str
    line: int
    module_level: bool


def _assigned_names(node: ast.stmt) -> Iterable[str]:
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        yield node.target.id
    elif isinstance(node, ast.Assign):
        yield from (target.id for target in node.targets if isinstance(target, ast.Name))


def _declarations(path: str, tree: ast.Module) -> list[_Declaration]:
    """Return module constants and class fields in ``tree`` whose names read as flags."""
    found: list[_Declaration] = []
    for node in tree.body:
        found.extend(
            _Declaration(path, name, node.lineno, module_level=True)
            for name in _assigned_names(node)
            if _FLAG_NAME.search(name)
        )
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                found.extend(
                    _Declaration(path, name, item.lineno, module_level=False)
                    for name in _assigned_names(item)
                    if _FLAG_NAME.search(name)
                )
    return found


def unread_flags(sources: Iterable[tuple[str, str]]) -> list[_Declaration]:
    """Return flag declarations in the declaring layers that no given source reads.

    An attribute load reads a field or a constant; a bare name load reads a
    module constant. Assignments and keyword arguments are writes, not reads.
    """
    declarations: list[_Declaration] = []
    attribute_reads: set[str] = set()
    name_reads: set[str] = set()
    for path, text in sources:
        tree = ast.parse(text, filename=path)
        if path.startswith(_DECLARING_LAYERS):
            declarations.extend(_declarations(path, tree))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
                attribute_reads.add(node.attr)
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                name_reads.add(node.id)
    return [
        declaration
        for declaration in declarations
        if declaration.name not in attribute_reads and not (declaration.module_level and declaration.name in name_reads)
    ]


@pytest.fixture(scope="module")
def production() -> tuple[tuple[str, str], ...]:
    return production_sources()


def test_the_declaring_population_is_not_empty(production: tuple[tuple[str, str], ...]) -> None:
    """With no flag declarations in scope the gate below would pass vacuously."""
    declared = [
        declaration
        for path, text in production
        if path.startswith(_DECLARING_LAYERS)
        for declaration in _declarations(path, ast.parse(text, filename=path))
    ]
    assert len(declared) > len(_KNOWN_UNREAD)


def test_every_declared_flag_has_a_production_reader(production: tuple[tuple[str, str], ...]) -> None:
    """A flag nobody reads claims a restriction the product never applies."""
    unexplained = [
        f"{declaration.path}:{declaration.line} {declaration.name}"
        for declaration in unread_flags(production)
        if (declaration.path, declaration.name) not in _KNOWN_UNREAD
    ]
    assert unexplained == []


def test_every_known_unread_entry_is_still_declared_and_unread(production: tuple[tuple[str, str], ...]) -> None:
    """An entry whose flag was deleted or gained a reader is stale and must be removed."""
    still_unread = {(declaration.path, declaration.name) for declaration in unread_flags(production)}
    assert sorted(set(_KNOWN_UNREAD) - still_unread) == []


def test_a_synthetic_unread_flag_is_detected_and_a_read_one_is_not() -> None:
    """Teeth: the same scan flags a field nobody reads and passes one a production module reads."""
    declaring = (
        "src/cadrumo/application/example/rows.py",
        "class Row:\n    export_supported: bool = False\n    retry_enabled: bool = True\n",
    )
    reader = (
        "src/cadrumo/application/example/consumer.py",
        "def consume(row):\n    return row.retry_enabled\n",
    )

    assert [(item.name, item.line) for item in unread_flags((declaring, reader))] == [("export_supported", 2)]
    constant = ("src/cadrumo/domain/example/limits.py", "EXPORT_ALLOWED = False\n")
    assert [item.name for item in unread_flags((constant,))] == ["EXPORT_ALLOWED"]
    assert unread_flags((constant, ("src/cadrumo/domain/example/use.py", "x = EXPORT_ALLOWED\n"))) == []
