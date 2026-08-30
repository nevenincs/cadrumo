"""An attribute reached through a package namespace must actually be there.

Retiring a package's PEP 562 export map makes its namespace inert. That is the
campaign's intent, and the import statements that name a SYMBOL are repointed
as part of the retirement. What survives the sweep unnoticed is the other
shape: a module that binds the PACKAGE itself and reaches through it.

    from . import crypto          # still resolves -- crypto is a real package
    ...
    crypto.encrypt_record(...)    # AttributeError, once the map is gone

Nothing catches that. The import is valid, the module imports cleanly, and only
the attribute access fails -- at runtime, on whichever code path happens to
reach it. The crypto retirement left exactly one such consumer behind and every
profile passphrase encryption raised until it was repointed.

This gate closes that class. It resolves each relative import that binds a
package name, collects every attribute read through that binding, and asserts
the name is reachable on the package: defined in its ``__init__``, imported
there, or listed as a key of a still-live lazy export map. A package whose map
is retired therefore fails the moment a consumer still reaches through it,
which is when the retirement is landing rather than when a taxpayer's
calculation runs.

The check is deliberately about REACHABILITY, not about whether reaching
through a namespace is good style. `aeat-architecture-boundaries` already
forbids the latter; this gate exists so a retirement cannot half-land.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SRC = Path(__file__).resolve().parent.parent

#: Maps whose keys are reachable through ``__getattr__`` while they still ship.
_LAZY_MAP_NAMES = frozenset({"_LAZY_EXPORTS", "_EXPORT_MODULES", "_LAZY_NAMES", "_LAZY_REPOSITORY_NAMES"})


def _is_package(path: Path) -> bool:
    """Whether *path* is a package directory, matched case-sensitively.

    The case check matters: this repository is developed on a case-insensitive
    filesystem, where a class named ``Envelope`` imported beside an
    ``envelope`` package resolves to the directory and reads as a namespace
    binding it is not.
    """
    if not (path.is_dir() and (path / "__init__.py").is_file()):
        return False
    return path.name in {entry.name for entry in path.parent.iterdir()}


def _resolve_relative(module_path: Path, level: int, module: str | None) -> Path:
    base = module_path.parent
    for _ in range(level - 1):
        base = base.parent
    if module:
        for part in module.split("."):
            base = base / part
    return base


def _reachable_names(package_init: Path) -> set[str]:
    """Names an attribute read on this package can resolve to."""
    try:
        tree = ast.parse(package_init.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):  # a peer's mid-edit file is not our finding
        return set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            names.add(node.name)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            names.update(targets)
            if set(targets) & _LAZY_MAP_NAMES:
                names.update(
                    element.value
                    for element in ast.walk(node.value)
                    if isinstance(element, ast.Constant) and isinstance(element.value, str)
                )
        elif isinstance(node, ast.ImportFrom):
            names.update(alias.asname or alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            names.update((alias.asname or alias.name).split(".")[0] for alias in node.names)
    return names


def _unreachable_attribute_reads() -> dict[str, list[str]]:
    findings: dict[str, list[str]] = {}
    for path in sorted(_SRC.rglob("*.py")):
        relative = path.relative_to(_SRC).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        bound_packages: dict[str, Path] = {}
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or not node.level:
                continue
            target = _resolve_relative(path, node.level, node.module)
            for alias in node.names:
                candidate = target / alias.name
                if _is_package(candidate):
                    bound_packages[alias.asname or alias.name] = candidate
        if not bound_packages:
            continue
        reads: dict[str, set[str]] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in bound_packages:
                reads.setdefault(node.value.id, set()).add(node.attr)
        for binding, attributes in reads.items():
            package = bound_packages[binding]
            reachable = _reachable_names(package / "__init__.py")
            missing = sorted(
                attribute
                for attribute in attributes
                if attribute not in reachable and not attribute.startswith("__")
            )
            if missing:
                package_name = package.relative_to(_SRC).as_posix()
                findings.setdefault(relative, []).extend(f"{package_name}.{attribute}" for attribute in missing)
    return findings


def test_no_attribute_is_read_through_a_namespace_that_lacks_it() -> None:
    """A package binding may not reach a name its namespace does not carry."""
    findings = _unreachable_attribute_reads()
    assert not findings, (
        "these modules read an attribute through a package namespace that does "
        "not expose it, which raises AttributeError only when the path runs. Test modules are scanned too: a test reaching through a retired namespace fails at collection, which is the same defect arriving one step earlier, and three such reads survived a retirement because this check used to skip them. "
        "Import the owning submodule directly: "
        f"{findings}"
    )


def _dynamic_attribute_reads() -> dict[str, list[str]]:
    """Attributes read straight off a dynamically imported cadrumo module.

    ``import_module("cadrumo.x.y").Thing`` is not an import statement, so the
    static resolution above cannot see it and neither can a repointer that
    rewrites import lines. This shape is what survived the contribuyente
    retirement and broke roughly forty tests: the module still resolved, and
    only the attribute was gone.

    Only literal targets are checked. A computed module name is a dispatch
    mechanism whose targets are not knowable here, and pretending otherwise
    would make this check lie about its coverage.
    """
    findings: dict[str, list[str]] = {}
    for path in sorted(_SRC.rglob("*.py")):
        relative = path.relative_to(_SRC).as_posix()
        if "tests" in path.relative_to(_SRC).parts or path.name.startswith("test_"):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Attribute) or not isinstance(node.value, ast.Call):
                continue
            call = node.value
            func = call.func
            name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
            if name != "import_module" or not call.args:
                continue
            target = call.args[0]
            if not (isinstance(target, ast.Constant) and isinstance(target.value, str)):
                continue
            if not target.value.startswith("cadrumo."):
                continue
            module_path = _SRC.parent / Path(target.value.replace(".", "/"))
            init = module_path / "__init__.py"
            source = init if init.is_file() else module_path.with_suffix(".py")
            if not source.is_file():
                findings.setdefault(relative, []).append(f"{target.value} (module not found)")
                continue
            if node.attr not in _reachable_names(source):
                findings.setdefault(relative, []).append(f"{target.value}.{node.attr}")
    return findings


def test_no_attribute_is_read_off_a_dynamically_imported_module_that_lacks_it() -> None:
    """A string import hides a broken reach from every static check."""
    findings = _dynamic_attribute_reads()
    assert not findings, (
        "these modules read an attribute off a dynamically imported module that "
        "does not expose it. A string import resolves at runtime, so this fails "
        "only on the path that runs it: name the owning module instead. "
        f"{findings}"
    )


def test_the_detector_sees_a_package_binding_at_all() -> None:
    """A detector that resolves no bindings would pass by finding nothing.

    The check above is a negative assertion, so it holds trivially if the
    import resolution silently stops working -- a moved tree root or a changed
    relative-import shape would make it vacuous rather than red. This anchors
    it: the repository does bind package names relatively, and the resolver
    must still see them.
    """
    seen = 0
    for path in sorted(_SRC.rglob("*.py")):
        if "tests" in path.relative_to(_SRC).parts or path.name.startswith("test_"):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level:
                target = _resolve_relative(path, node.level, node.module)
                seen += sum(1 for alias in node.names if _is_package(target / alias.name))
    assert seen, "the package-binding resolver found nothing, so the reachability check is vacuous"
