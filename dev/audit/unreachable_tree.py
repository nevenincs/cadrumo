"""Read the shipped distribution and workspace entrypoint source population."""

from __future__ import annotations

import ast
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from cadrumo.core.toml import parse_toml
from dev._paths import REPO_ROOT, UTF_8
from dev.first_party_source import DEVELOPMENT_TOOLING, PACKAGING_HOOKS, SOURCE_PACKAGES, is_test_source
from dev.quality.source_import_analysis import (
    is_shipped_module,
    module_name_for,
    wheel_exclude_globs,
)

from .unreachable_memo import parse_module
from .unreachable_models import ShippedModule
from .unreachable_policy import DATA_GLOBS, DEV_LABEL, PACKAGING_LABEL, SKIPPED_DIRS


def _repository_console_scripts(repo_root: Path) -> tuple[Path, dict[str, str]]:
    """Repository console scripts."""
    pyproject = repo_root / "pyproject.toml"
    data = parse_toml(pyproject.read_text(encoding=UTF_8))
    project = data.get("project")
    if not isinstance(project, dict):
        raise ValueError(f"{pyproject} has no [project] table")
    project_table = cast(dict[str, object], project)
    raw_scripts = project_table.get("scripts", {})
    if not isinstance(raw_scripts, dict):
        raise ValueError(f"{pyproject} has an invalid [project.scripts] table")
    scripts: dict[str, str] = {}
    for name, spec in cast(dict[str, object], raw_scripts).items():
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
class ShippedTreeSpec:
    """Everything the scan needs to know about one distribution.

    Every package of the distribution is audited in one walk. They ship in
    one wheel and import one another, so a module is alive when any console
    script or ``python -m`` surface of the distribution reaches it, whichever
    package defines the caller.

    Args:
        repo_root: Paths in findings are rendered relative to this.
        src_root: The ``src/`` directory the packages live under.
        packages: The top-level import names of the shipped packages, each of
            which is the audit's subject.
        entry_points: The console scripts the walk starts from.
        module_roots: Modules executable as ``python -m <module>``, discovered
            from shipped ``__main__.py`` files and exact top-level main guards.
            They are walk roots too: an installed user can run them without any
            packaging declaration.
        exclude_globs: Wheel exclude globs; a module they match is unshipped.
        outside: Non-shipped trees whose references label findings.
        data_globs: Shipped non-Python payloads, relative to each package root,
            whose identifier tokens clear a data-shaped member.
    """

    repo_root: Path
    src_root: Path
    packages: tuple[str, ...]
    entry_points: tuple[EntryPoint, ...]
    module_roots: tuple[str, ...] = ()
    exclude_globs: tuple[str, ...] = ()
    outside: tuple[OutsideCorpus, ...] = ()
    data_globs: tuple[str, ...] = ()

    @property
    def package_roots(self) -> tuple[Path, ...]:
        """The directory of every audited package."""
        return tuple(self.src_root / package for package in self.packages)

    def audits(self, module: str) -> bool:
        """Whether the dotted ``module`` belongs to an audited package."""
        return any(module == package or module.startswith(f"{package}.") for package in self.packages)

    @classmethod
    def from_repository(cls, repo_root: Path = REPO_ROOT, *, extra_roots: tuple[str, ...] = ()) -> ShippedTreeSpec:
        """Read the shipped-tree facts from the repository's own packaging config.

        Console scripts and wheel excludes are read from ``pyproject.toml``
        rather than restated, so the audit keeps following the distribution
        as the packaging changes. The audited packages are the declared
        :data:`~dev.first_party_source.SOURCE_PACKAGES` present in the tree.
        ``extra_roots`` adds ``module:attribute`` roots the packaging does not
        declare, such as a ``python -m`` surface, so a campaign can ask "what
        is dead even if that surface counts?".
        """
        pyproject, scripts = _repository_console_scripts(repo_root)
        src_root = repo_root / "src"
        packages = _source_packages(repo_root, src_root)
        excludes = tuple(wheel_exclude_globs(pyproject))
        declared = tuple(EntryPoint.parse(spec) for spec in scripts.values())
        outside_scripts = sorted(entry.spec for entry in declared if entry.module.split(".")[0] not in packages)
        if outside_scripts:
            msg = f"console script(s) target no audited source package: {', '.join(outside_scripts)}"
            raise ValueError(msg)
        module_roots = _module_execution_roots(src_root, packages, excludes)
        return cls(
            repo_root=repo_root,
            src_root=src_root,
            packages=packages,
            entry_points=declared + tuple(EntryPoint.parse(spec) for spec in extra_roots),
            module_roots=module_roots,
            exclude_globs=excludes,
            outside=(
                *(
                    OutsideCorpus(label="tests", root=src_root / package, test_modules_only=True)
                    for package in packages
                ),
                OutsideCorpus(label="tests", root=repo_root / "conftest.py"),
                OutsideCorpus(label=DEV_LABEL, root=repo_root / DEVELOPMENT_TOOLING),
                OutsideCorpus(label=PACKAGING_LABEL, root=repo_root / PACKAGING_HOOKS),
            ),
            data_globs=DATA_GLOBS,
        )


def _module_execution_roots(src_root: Path, packages: tuple[str, ...], excludes: tuple[str, ...]) -> tuple[str, ...]:
    module_roots = tuple(
        sorted(
            module_name_for(path, src_root=src_root)
            for package in packages
            for path in (src_root / package).rglob("*.py")
            if SKIPPED_DIRS.isdisjoint(path.parts)
            and not is_test_source(path, root=src_root)
            and is_shipped_module(path, src_root=src_root, exclude_globs=excludes)
            and is_module_execution_surface(path)
        ),
    )
    return module_roots


def _source_packages(repo_root: Path, src_root: Path) -> tuple[str, ...]:
    """The declared source packages present under ``src/``, refusing an undeclared one.

    A declared package absent from the tree is not audited: there is nothing
    to walk. A package present under ``src/`` but missing from the declared
    scope is refused, because auditing around it would report its consumers'
    code reachable or dead without the audit ever saying it stopped short.
    """
    packages = _present_declared_packages(repo_root, src_root)
    present = (
        sorted(child.name for child in src_root.iterdir() if (child / "__init__.py").is_file())
        if src_root.is_dir()
        else []
    )
    undeclared = [name for name in present if name not in packages]
    if undeclared:
        raise ValueError(f"src/ holds package(s) outside the declared source scope: {', '.join(undeclared)}")
    if not packages:
        raise ValueError(f"no declared source package exists under {src_root}")
    return tuple(packages)


def _present_declared_packages(repo_root: Path, src_root: Path) -> list[str]:
    packages: list[str] = []
    for source_root in SOURCE_PACKAGES:
        directory = repo_root / source_root
        if directory.parent != src_root:
            raise ValueError(f"source package {source_root} does not live directly under {src_root}")
        if directory.is_dir():
            packages.append(directory.name)
    return packages


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
        raise FileNotFoundError(f"unreachable-code corpus {root} does not exist; coverage is unproven")
    for path in sorted(root.rglob("*.py")):
        if SKIPPED_DIRS.isdisjoint(path.parts):
            yield path


def is_module_execution_surface(path: Path) -> bool:
    """Return whether an installed user can execute the module with ``python -m``."""
    if path.name == "__main__.py":
        return True
    source = path.read_bytes()
    if b"__main__" not in source:
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
    """Every shipped module of every audited package."""
    modules: dict[str, ShippedModule] = {}
    for root in spec.package_roots:
        modules.update(_load_package(root, spec.src_root, exclude_globs=spec.exclude_globs))
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
