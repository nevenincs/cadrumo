"""Every relative import must name a module that exists.

A relative import encodes its target as a dot count plus a name, and the
dot count is a fact about where the importing file sits. Move the file, or
rewrite the import mechanically, and the two can disagree -- ``from ..x``
becoming ``from ...x`` still parses, still lints, and still passes every
gate that reads source as text. It fails only when something imports that
module, which for a test module means at collection, and for a rarely
exercised branch means in front of an operator.

This campaign produced exactly that. A sweep repointing a retired
namespace's consumers processed one file twice, because the file happened
to contain the package's name in an unrelated import, and each pass added
a dot. The result named ``cadrumo.domain.aggregates``, a package that has
never existed, and nothing but running the test revealed it.

The check is cheap and total: parse every module, resolve every relative
import against the filesystem, and refuse any that lands nowhere. It reads
no import machinery and executes no module, so a package whose import has
side effects costs nothing here.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SRC = Path(__file__).resolve().parent.parent
_ROOT = _SRC.parent


def _resolved_target(module_path: Path, node: ast.ImportFrom) -> tuple[str, Path] | None:
    """The dotted target of one relative import, and the path it should occupy."""
    parts = module_path.relative_to(_ROOT).with_suffix("").parts
    package = parts[:-1]
    keep = len(package) - (node.level - 1)
    if keep < 0:
        return ("<above the package root>", _ROOT)
    dotted = ".".join(package[:keep])
    if node.module:
        dotted = f"{dotted}.{node.module}" if dotted else node.module
    return dotted, _ROOT / dotted.replace(".", "/")


def _unresolvable() -> list[str]:
    misses: list[str] = []
    for path in sorted(_SRC.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # a peer's mid-edit file is not this gate's finding
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or not node.level:
                continue
            resolved = _resolved_target(path, node)
            if resolved is None:
                continue
            dotted, target = resolved
            if target.with_suffix(".py").exists() or (target / "__init__.py").exists():
                continue
            relative = path.relative_to(_ROOT).as_posix()
            misses.append(f"{relative}:{node.lineno} -> {dotted}")
    return misses


def test_every_relative_import_names_a_module_that_exists() -> None:
    """A relative import whose dot count is wrong names nothing, and must not ship."""
    misses = _unresolvable()
    assert not misses, (
        "these relative imports resolve to no module on disk. The usual cause is a "
        "dot count that no longer matches the file's depth -- check the number of "
        "leading dots against the importing file's package before changing the name: "
        f"{misses}"
    )
