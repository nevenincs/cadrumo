"""Read the shipped distribution and workspace entrypoint source population."""

from __future__ import annotations

import ast
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from cadrumo.core.toml import parse_toml
from dev._paths import REPO_ROOT, UTF_8
from dev.first_party_source import DEVELOPMENT_TOOLING, is_test_source
from dev.quality.source_import_analysis import (
    is_shipped_module,
    module_name_for,
    wheel_exclude_globs,
)
from dev.quality.unread_inputs import report_unread

from .unreachable_memo import parse_module
from .unreachable_models import ShippedModule
from .unreachable_policy import _DATA_GLOBS, _DEV_LABEL, _SKIPPED_DIRS


def _repository_console_scripts(repo_root: Path) -> tuple[Path, dict[str, str]]:
    """Repository console scripts."""
    pyproject = repo_root / "pyproject.toml"
    data = parse_toml(pyproject.read_text(encoding=UTF_8))
    project = data.get("project")
    if not isinstance(project, dict):
        raise ValueError(f"{pyproject} has no [project] table")
    raw_scripts = project.get("scripts", {})
    if not isinstance(raw_scripts, dict):
        raise ValueError(f"{pyproject} has an invalid [project.scripts] table")
    scripts: dict[str, str] = {}
    for name, spec in raw_scripts.items():
        if not isinstance(name, str) or not isinstance(spec, str):
            raise ValueError(f"{pyproject} has a non-text [project.scripts] entry")
        scripts[name] = spec
    if not scripts:
        msg = f"{pyproject} declares no [project.scripts]; the walk would have no roots"
        raise ValueError(msg)
    return pyproject, scripts


@dataclass(frozen=True)
class EntryPoint:
    """One ``module:attribute`` console-script target."""

    module: str
    attribute: str

    @property
    def spec(self) -> str:
        """The ``module:attribute`` spelling from the packaging table."""
        return f"{self.module}:{self.attribute}"

    @classmethod
    def parse(cls, spec: str) -> EntryPoint:
        """Parse a ``module:attribute`` console-script value."""
        module, separator, attribute = spec.partition(":")
        if not separator or not module or not attribute:
            msg = f"console script {spec!r} is not of the form module:attribute"
            raise ValueError(msg)
        return cls(module=module.strip(), attribute=attribute.strip())


@dataclass(frozen=True)
class OutsideCorpus:
    """A non-shipped tree whose references only label findings.

    Args:
        label: The word rendered after ``used by:``.
        root: Directory walked for ``*.py`` files.
        test_modules_only: When true, only test modules (``tests/`` trees,
            ``test_*.py``, ``conftest.py``) under ``root`` are read; the rest
            of the tree is the shipped universe and is scanned elsewhere.
    """

    label: str
    root: Path
    test_modules_only: bool = False


@dataclass(frozen=True)
class CompanionPackage:
    """A sibling workspace distribution that depends on the audited package.

    Its modules are not the audit's subject, but they are real consumers: an
    installed user running its console script executes them, and whatever they
    import from the audited package is reached. Walking them is the difference
    between "nothing in the product calls this" and "nothing in this one
    distribution calls this".

    Args:
        package: Top-level import name, for example ``cadrumo_harness``.
        src_root: Source root its modules are named relative to.
        entry_points: Its own ``[project.scripts]``.
    """

    package: str
    src_root: Path
    entry_points: tuple[EntryPoint, ...]


@dataclass(frozen=True)
class ShippedTreeSpec:
    """Everything the scan needs to know about one distribution.

    Args:
        repo_root: Paths in findings are rendered relative to this.
        src_root: The ``src/`` directory the package lives under.
        package: The top-level import name of the shipped package.
        entry_points: The console scripts the walk starts from.
        module_roots: Modules executable as ``python -m <module>``, discovered
            from shipped ``__main__.py`` files and exact top-level main guards.
            They are walk roots too: an installed user can run them without any
            packaging declaration.
        exclude_globs: Wheel exclude globs; a module they match is unshipped.
        outside: Non-shipped trees whose references label findings.
        data_globs: Shipped non-Python payloads, relative to the package root,
            whose identifier tokens clear a data-shaped member.
        companions: Sibling workspace distributions that consume this package.
    """

    repo_root: Path
    src_root: Path
    package: str
    entry_points: tuple[EntryPoint, ...]
    module_roots: tuple[str, ...] = ()
    exclude_globs: tuple[str, ...] = ()
    outside: tuple[OutsideCorpus, ...] = ()
    data_globs: tuple[str, ...] = ()
    companions: tuple[CompanionPackage, ...] = ()

    @classmethod
    def from_repository(cls, repo_root: Path = REPO_ROOT, *, extra_roots: tuple[str, ...] = ()) -> ShippedTreeSpec:
        """Read the shipped-tree facts from the repository's own packaging config.

        Console scripts and wheel excludes are read from ``pyproject.toml``
        rather than restated, so the audit keeps following the distribution
        as the packaging changes. ``extra_roots`` adds ``module:attribute``
        roots the packaging does not declare, such as a ``python -m`` surface,
        so a campaign can ask "what is dead even if that surface counts?".
        """
        pyproject, scripts = _repository_console_scripts(repo_root)
        src_root = repo_root / "src"
        package = "cadrumo"
        excludes = wheel_exclude_globs(pyproject)
        companions = _sibling_console_packages(src_root, scripts, audited_package=package)
        entry_points = tuple(
            EntryPoint.parse(spec) for spec in scripts.values() if spec.partition(":")[0].split(".")[0] == package
        ) + tuple(EntryPoint.parse(spec) for spec in extra_roots)
        module_roots = tuple(
            sorted(
                module_name_for(path, src_root=src_root)
                for path in (src_root / package).rglob("*.py")
                if _SKIPPED_DIRS.isdisjoint(path.parts)
                and not is_test_source(path, root=src_root)
                and is_shipped_module(path, src_root=src_root, exclude_globs=tuple(excludes))
                and is_module_execution_surface(path)
            ),
        )
        return cls(
            repo_root=repo_root,
            src_root=src_root,
            package=package,
            entry_points=entry_points,
            module_roots=module_roots,
            exclude_globs=tuple(excludes),
            outside=(
                OutsideCorpus(label="tests", root=src_root / package, test_modules_only=True),
                OutsideCorpus(label="tests", root=repo_root / "conftest.py"),
                OutsideCorpus(label=_DEV_LABEL, root=repo_root / DEVELOPMENT_TOOLING),
            ),
            data_globs=_DATA_GLOBS,
            companions=companions,
        )


def _sibling_console_packages(
    src_root: Path, scripts: dict[str, str], *, audited_package: str
) -> tuple[CompanionPackage, ...]:
    """Group the console scripts that start in a package other than the audited one.

    Read from the declared scripts rather than from workspace membership, so a
    sibling distribution folded into this one keeps contributing its roots. A
    script whose package is not present under ``src/`` is skipped: it cannot be
    walked, and guessing would silently shrink the reachable set.
    """
    grouped: dict[str, list[EntryPoint]] = {}
    for spec in scripts.values():
        entry = EntryPoint.parse(spec)
        package = entry.module.split(".")[0]
        if package == audited_package or not (src_root / package).is_dir():
            continue
        grouped.setdefault(package, []).append(entry)
    return tuple(
        CompanionPackage(package=package, src_root=src_root, entry_points=tuple(entries))
        for package, entries in sorted(grouped.items())
    )


def iter_python_files(root: Path) -> Iterator[Path]:
    """Yield every ``*.py`` file under ``root``, or ``root`` itself when it is one.

    A root that exists and holds no Python files yields nothing, which is a
    true answer. A root that does not exist yielded the same nothing, and
    every caller then analysed an empty corpus: the reference walk sees no
    references and reports live code dead, the test walk sees no tests and
    reports none. Absence and emptiness were the same event here, so the
    absent case now says so.
    """
    if root.is_file():
        if root.suffix == ".py":
            yield root
        return
    if not root.is_dir():
        report_unread(
            "unreachable-code enumeration",
            "it does not exist, so every walk over it analysed an empty corpus",
            [str(root)],
        )
        return
    for path in sorted(root.rglob("*.py")):
        if _SKIPPED_DIRS.isdisjoint(path.parts):
            yield path


def is_module_execution_surface(path: Path) -> bool:
    """Return whether an installed user can execute the module with ``python -m``."""
    if path.name == "__main__.py":
        return True
    source = path.read_text(encoding=UTF_8)
    if "__main__" not in source:
        return False
    tree = ast.parse(source, filename=str(path))
    return any(_is_module_main_guard(statement) for statement in tree.body)


def _is_resource_anchor(path: Path, tree: ast.Module, src_root: Path) -> bool:
    """True for an empty ``__init__.py`` whose package holds no Python at all.

    ``importlib.resources.files()`` needs a package marker to address a data
    directory. Such a marker is not code and can never be "called"; reporting
    it as unreachable is noise that buries real findings.
    """
    if path.name != "__init__.py" or tree.body:
        return False
    return not any(
        sibling.name != "__init__.py" and not is_test_source(sibling, root=src_root)
        for sibling in path.parent.rglob("*.py")
    )


def _load_package(root: Path, src_root: Path, *, exclude_globs: tuple[str, ...]) -> dict[str, ShippedModule]:
    modules: dict[str, ShippedModule] = {}
    for path in iter_python_files(root):
        if is_test_source(path, root=src_root):
            continue
        if exclude_globs and not is_shipped_module(path, src_root=src_root, exclude_globs=exclude_globs):
            continue
        tree = parse_module(path)
        if _is_resource_anchor(path, tree, src_root):
            continue
        name = module_name_for(path, src_root=src_root)
        modules[name] = ShippedModule(name=name, path=path, is_package=path.name == "__init__.py", tree=tree)
    return modules


def shipped_modules(spec: ShippedTreeSpec) -> dict[str, ShippedModule]:
    """Every module in the audited package, plus the companion distributions that consume it."""
    modules = _load_package(spec.src_root / spec.package, spec.src_root, exclude_globs=spec.exclude_globs)
    for companion in spec.companions:
        modules.update(
            _load_package(companion.src_root / companion.package, companion.src_root, exclude_globs=()),
        )
    return modules


# ---------------------------------------------------------------------------
# Composition
# ---------------------------------------------------------------------------


def relative_to_repo(path: Path, spec: ShippedTreeSpec) -> str:
    """Render ``path`` the way a finding reports it, relative to the repository root."""
    return path.relative_to(spec.repo_root).as_posix()


def _is_module_main_guard(statement: ast.stmt) -> bool:
    """Recognize an exact equality main guard without widening executable roots."""
    if not isinstance(statement, ast.If) or not isinstance(statement.test, ast.Compare):
        return False
    comparison = statement.test
    if len(comparison.ops) != 1 or not isinstance(comparison.ops[0], ast.Eq):
        return False
    if len(comparison.comparators) != 1:
        return False
    left, right = comparison.left, comparison.comparators[0]
    operands = (left, right)
    return _main_guard_operands(operands)


def _main_guard_operands(operands: tuple[ast.expr, ast.expr]) -> bool:
    """Require both the __name__ identifier and literal __main__ operands."""
    return any(isinstance(node, ast.Name) and node.id == "__name__" for node in operands) and any(
        isinstance(node, ast.Constant) and node.value == "__main__" for node in operands
    )
