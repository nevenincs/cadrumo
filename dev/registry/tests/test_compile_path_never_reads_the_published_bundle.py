"""Structural gate: compiling a registry never reads the artifact it replaces.

``compile_validated_authority`` produces the published authority artifact. If
any module it reaches calls :func:`bundled_authority`, the compiler depends on
the artifact it is about to replace, and the registry becomes unpublishable the
moment a catalogue's schema changes: the old artifact no longer decodes against
the new model, so the compile that would fix it cannot run. The fix and the
thing needing fixing are the same file.

That deadlock was live in this repository. ``LegalReferenceKind`` resolved its
members lazily through a module ``__getattr__`` that called
``bundled_authority().resolve_governed_fact(...)``, so the compile path reached
the bundle on an ordinary attribute access -- ``LegalReferenceKind.ORDEN`` --
with nothing at the call site to suggest it. It stayed invisible until a
catalogue schema changed under it.

The vocabulary is a closed ``StrEnum`` again and the deadlock is gone. Nothing
prevents its return: the redesign that closed the enum was not undertaken to
keep the compile path clean, and the next lazily-resolved vocabulary
reintroduces the same defect just as quietly. This gate is the prevention.

The sweep is a static import closure rather than a live compile, deliberately.
The invariant is about which modules the compile path *can* reach, which is a
property of the source; asserting it statically holds even when the corpus is
mid-edit, needs no fixture registry, and does not depend on a compile that a
data error elsewhere can redden.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Final, NamedTuple

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REPO_ROOT: Final = Path(__file__).resolve().parents[3]
_COMPILE_ENTRY: Final = _REPO_ROOT / "dev" / "registry" / "compiler" / "authority.py"

# The forbidden name resolves the PUBLISHED artifact. ``compiled_bundled_authority``
# is a different function that compiles the bundled tree from source and is
# legitimate on this path; matching by AST node rather than by text is what keeps
# the two apart, and the detector proves it below.
_FORBIDDEN_CALLEE: Final = "bundled_authority"

# Only first-party registry source participates. A module outside these roots
# cannot be part of the compile path's own closure.
_CLOSURE_ROOTS: Final = (
    _REPO_ROOT / "dev" / "registry",
    _REPO_ROOT / "src" / "cadrumo" / "domain" / "calculations" / "registry",
)


class _Read(NamedTuple):
    """One call reaching the published artifact from the compile path."""

    path: Path
    line: int

    def __str__(self) -> str:
        return f"{self.path.relative_to(_REPO_ROOT).as_posix()}:{self.line}"


def _module_path(module: str) -> Path | None:
    """Resolve a dotted module to a first-party source file, if it is one."""
    relative = Path(*module.split("."))
    for candidate in (_REPO_ROOT / relative.with_suffix(".py"), _REPO_ROOT / relative / "__init__.py"):
        if candidate.is_file() and any(root in candidate.parents for root in _CLOSURE_ROOTS):
            return candidate
    return None


def _imported_modules(tree: ast.AST, *, module_parts: tuple[str, ...]) -> set[str]:
    """Return the dotted modules a parsed source imports, relative ones resolved."""
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = module_parts[: len(module_parts) - node.level]
                prefix = (*base, *(node.module.split(".") if node.module else ()))
            else:
                prefix = tuple(node.module.split(".")) if node.module else ()
            if not prefix:
                continue
            imported.add(".".join(prefix))
            # `from x import y` may name either an attribute or a submodule.
            imported.update(".".join((*prefix, alias.name)) for alias in node.names)
    return imported


def _compile_path_closure() -> dict[Path, ast.AST]:
    """Walk the static import closure of the compile entry point.

    Test modules are excluded: a test may legitimately compare a compiled
    authority against the published one, and no test is on the compile path.
    """
    closure: dict[Path, ast.AST] = {}
    pending = [_COMPILE_ENTRY]
    while pending:
        path = pending.pop()
        if path in closure or "tests" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        closure[path] = tree
        module_parts = path.relative_to(_REPO_ROOT).with_suffix("").parts
        for module in _imported_modules(tree, module_parts=module_parts):
            resolved = _module_path(module)
            if resolved is not None and resolved not in closure:
                pending.append(resolved)
    return closure


def _published_artifact_reads(tree: ast.AST, path: Path) -> tuple[_Read, ...]:
    """Return every call to the forbidden callee in one parsed source."""
    found: list[_Read] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = (
            func.id
            if isinstance(func, ast.Name)
            else func.attr
            if isinstance(func, ast.Attribute)
            else None
        )
        if name == _FORBIDDEN_CALLEE:
            found.append(_Read(path=path, line=node.lineno))
    return tuple(found)


def test_the_compile_path_never_reads_the_published_authority() -> None:
    closure = _compile_path_closure()
    assert len(closure) > 1, (
        "the import closure collapsed to the entry module alone; the walker is broken "
        "and would pass this gate no matter what the compile path does"
    )

    reads = tuple(
        read for path, tree in sorted(closure.items()) for read in _published_artifact_reads(tree, path)
    )

    assert not reads, (
        "the registry compile path reads the published authority artifact it is about to "
        f"replace, at {', '.join(str(read) for read in reads)}. A catalogue schema change "
        "then cannot be published: the old artifact stops decoding against the new model, "
        "and the compile that would replace it needs the old artifact to run. Resolve the "
        "value from the candidate being compiled instead of from bundled_authority()."
    )


def test_the_gate_detects_a_planted_read(tmp_path: Path) -> None:
    """Detector teeth: the defect this gate exists for must be caught."""
    planted = tmp_path / "planted.py"
    planted.write_text(
        "from cadrumo.domain.calculations.registry.authority import bundled_authority\n"
        "\n"
        "def kind():\n"
        "    return bundled_authority().resolve_governed_fact(None)\n",
        encoding="utf-8",
    )

    reads = _published_artifact_reads(ast.parse(planted.read_text(encoding="utf-8")), planted)

    assert [read.line for read in reads] == [4]


def test_the_gate_detects_a_read_through_an_attribute(tmp_path: Path) -> None:
    """The bundle is reachable as a module attribute as well as a bare name."""
    planted = tmp_path / "planted_attribute.py"
    planted.write_text(
        "from cadrumo.domain.calculations.registry import authority\n"
        "\n"
        "def kind():\n"
        "    return authority.bundled_authority()\n",
        encoding="utf-8",
    )

    reads = _published_artifact_reads(ast.parse(planted.read_text(encoding="utf-8")), planted)

    assert [read.line for read in reads] == [4]


def test_the_gate_allows_compiling_the_bundled_tree(tmp_path: Path) -> None:
    """``compiled_bundled_authority`` compiles from source and must not be flagged.

    It contains the forbidden name as a substring, so a text search fails this
    case. It is a real function on this path (``dev/registry/compiler/authority.py``),
    which is why the false positive is worth a test rather than a comment.
    """
    allowed = tmp_path / "allowed.py"
    allowed.write_text(
        "from ..authority import compiled_bundled_authority\n"
        "\n"
        "def snapshot():\n"
        "    return compiled_bundled_authority().snapshot('303', filing_year=2025, period='4T')\n",
        encoding="utf-8",
    )

    assert _published_artifact_reads(ast.parse(allowed.read_text(encoding="utf-8")), allowed) == ()


def test_the_closure_reaches_the_module_that_once_held_the_defect() -> None:
    """Anti-tautology: a closure that never reached the defect would pass vacuously.

    ``_m303_orden_legal`` is where ``LegalReferenceKind.ORDEN`` was evaluated
    when the deadlock was live. If the walker stops short of it, this gate
    proves nothing about the path that actually broke.
    """
    closure = _compile_path_closure()
    reached = {path.relative_to(_REPO_ROOT).as_posix() for path in closure}

    assert "dev/registry/compiler/_m303_orden_legal.py" in reached, (
        "the import closure no longer reaches the module that held the original defect; "
        f"the gate would pass vacuously. Reached {len(reached)} modules."
    )
