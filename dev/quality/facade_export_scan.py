"""Facade export-integrity scan against the git object store.

A package facade (``__init__.py``) can name a symbol that does not exist. The
failure is asymmetric and that asymmetry is the whole reason this scanner reads
git rather than the filesystem: in a shared worktree every agent holds the
missing half locally, so the import succeeds for everyone running tests while
being broken for a clean checkout and for CI. It surfaces only at HEAD.

Two directions, because a facade can be wrong in two ways and the checks share
no code path:

FORWARD
    The facade imports or exports a name its target module does not define.
    ``from ._models import Thing`` where ``_models`` has no ``Thing``; or an
    ``__all__`` entry the facade never binds. Import of the package raises.

MIRROR
    A committed consumer imports a name from a package facade that the facade
    does not provide. Invisible to the forward direction: every module involved
    is internally consistent, and only the edge between them is broken.

Both directions are measured against ONE pinned revision read through
``git cat-file``. Reading the filesystem, or resolving ``HEAD`` lazily while
peers commit, silently mixes trees: an enumeration performed against a
partially-repaired tree reports the repaired symbols as sound and the run reads
as a clean HEAD audit. Every read here is pinned to the revision passed in.

Companion to :mod:`dev.quality.import_hygiene_scan`, which governs *which* module a
consumer may import a symbol from. This scanner asks the prior question --
whether the symbol exists at all.
"""

from __future__ import annotations

import ast
import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from dev._paths import REPO_ROOT, UTF_8

from .import_hygiene_scan import dunder_all_assignment_value

PKG_PREFIX = "src/cadrumo"
_UTF_8 = UTF_8


@dataclass(frozen=True)
class FacadeBreak:
    """One facade naming a symbol that does not exist at the scanned revision."""

    facade: str
    symbol: str
    target: str
    kind: str

    def describe(self) -> str:
        """Return a one-line rendering for a gate failure message."""
        return f"{self.kind}: {self.facade} -> {self.symbol} (target {self.target})"


@dataclass
class ModuleFacts:
    """Everything the scan needs from one module's AST."""

    bound: set[str] = field(default_factory=set)
    exported: list[str] | None = None
    lazy: set[str] = field(default_factory=set)
    has_lazy_getattr: bool = False
    star_import: bool = False


def _git(args: list[str], *, repo_root: Path) -> str:
    return subprocess.run(["git", *args], cwd=repo_root, capture_output=True, text=True, check=True).stdout


def read_python_blobs(rev: str, *, repo_root: Path = REPO_ROOT) -> dict[str, str]:
    """Return every tracked ``.py`` file's source at ``rev``, read from git.

    One ``git cat-file --batch`` call rather than a process per file; the tree
    is large enough that per-file invocation dominates the runtime.
    """
    listing = _git(["ls-tree", "-r", rev, "--name-only", PKG_PREFIX], repo_root=repo_root)
    names = [line for line in listing.splitlines() if line.endswith(".py")]
    spec = "".join(f"{rev}:{name}\n" for name in names)
    completed = subprocess.run(
        ["git", "cat-file", "--batch"],
        cwd=repo_root,
        input=spec.encode(_UTF_8),
        capture_output=True,
        check=True,
    )
    out = completed.stdout
    blobs: dict[str, str] = {}
    pos = 0
    for name in names:
        newline = out.index(b"\n", pos)
        size = int(out[pos:newline].decode(_UTF_8).split()[-1])
        body = out[newline + 1 : newline + 1 + size]
        blobs[name] = body.decode(_UTF_8, errors="replace")
        pos = newline + 1 + size + 1
    return blobs


def module_name_for_path(path: str) -> str:
    """Return the dotted module name for a repository-relative ``.py`` path.

    A package's ``__init__.py`` names the package itself, so the trailing
    segment is dropped -- otherwise every facade would be treated as a distinct
    module from the package consumers import.
    """
    parts = path[len("src/") :][: -len(".py")].split("/")
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _binding_package(path: str, module: str) -> str:
    """Base package a relative import inside ``path`` resolves against."""
    if path.endswith("__init__.py"):
        return module
    return module.rsplit(".", 1)[0] if "." in module else ""


def resolve_relative(base_package: str, level: int, module: str | None) -> str:
    """Resolve a relative import to its absolute dotted target.

    ``level`` is the leading-dot count: level 1 addresses ``base_package``
    itself, and each further dot strips one segment. ``module`` is the part
    after the dots, absent for ``from . import x``.
    """
    parts = base_package.split(".") if base_package else []
    if level > 1:
        parts = parts[: len(parts) - (level - 1)]
    target = ".".join(parts)
    if module:
        target = f"{target}.{module}" if target else module
    return target


def _lazy_resolvable_names(tree: ast.Module) -> set[str]:
    """Names a PEP 562 ``__getattr__`` can resolve.

    The shipped pattern dispatches on string comparisons against ``name``
    (``name == "X"``, ``name in ("A", "B")``), so every string constant in the
    body is a candidate. Treating a lazy facade as opaque instead -- waving
    through every name because the module *has* a ``__getattr__`` -- makes the
    scan blind to precisely the facades that use the pattern, which in this
    tree includes ``cadrumo.core``.

    A second shipped shape keeps the names in a module-level container and
    tests membership against it (``if name in _REGISTRY_CONTRACT_EXPORTS``).
    Harvesting only the function body reads those facades as resolving NOTHING
    and reports every one of their exports as unbound -- measured, nineteen
    such reports across ``cadrumo.domain.user_profile`` and
    ``cadrumo.entrypoints.cli``, each of which a real interpreter resolves.
    So the containers ``__getattr__`` actually references are harvested too,
    which is narrower than trusting any module-level string set: a container
    the function never consults still contributes nothing.
    """
    getattr_defs = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "__getattr__"]
    inline = {
        sub.value
        for node in getattr_defs
        for sub in ast.walk(node)
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str)
    }
    referenced = {
        sub.id for node in getattr_defs for sub in ast.walk(node) if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load)
    }
    return inline | _module_level_strings(tree, referenced)


def _module_level_strings(tree: ast.Module, wanted: set[str]) -> set[str]:
    """Return string constants held by module-level bindings named in ``wanted``."""
    harvested: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets = {t.id for t in node.targets if isinstance(t, ast.Name)}
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            targets = {node.target.id}
        else:
            continue
        if not (targets & wanted) or node.value is None:
            continue
        harvested |= {
            sub.value for sub in ast.walk(node.value) if isinstance(sub, ast.Constant) and isinstance(sub.value, str)
        }
    return harvested


def _exported_names(tree: ast.Module) -> list[str] | None:
    """Return ``__all__`` for a module, or ``None`` when it declares none.

    Delegates the assignment-shape question to
    :func:`dev.quality.import_hygiene_scan.dunder_all_assignment_value`, which is the
    project's one authority on it and already handles the annotated form
    ``__all__: list[str] = [...]``. Re-deriving that here is how the two
    scanners would drift: an ``__all__`` read as absent makes every mirror
    check against that facade silently vacuous.
    """
    for node in tree.body:
        value = dunder_all_assignment_value(node)
        if isinstance(value, ast.List | ast.Tuple | ast.Set):
            return [elt.value for elt in value.elts if isinstance(elt, ast.Constant) and isinstance(elt.value, str)]
    return None


def module_facts(tree: ast.Module) -> ModuleFacts:
    """Collect the names a module binds, exports, and can lazily resolve."""
    facts = ModuleFacts()

    def _absorb_import(node: ast.Import | ast.ImportFrom) -> None:
        for alias in node.names:
            if alias.name == "*":
                facts.star_import = True
            elif isinstance(node, ast.Import):
                facts.bound.add(alias.asname or alias.name.split(".")[0])
            else:
                facts.bound.add(alias.asname or alias.name)

    for node in tree.body:
        match node:
            case ast.FunctionDef() | ast.AsyncFunctionDef() | ast.ClassDef():
                facts.bound.add(node.name)
            case ast.Assign():
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        facts.bound.add(target.id)
                    elif isinstance(target, ast.Tuple | ast.List):
                        facts.bound.update(elt.id for elt in target.elts if isinstance(elt, ast.Name))
            case ast.AnnAssign() if isinstance(node.target, ast.Name):
                facts.bound.add(node.target.id)
            # PEP 695 ``type X = ...`` is ast.TypeAlias, not ast.Assign. Reading
            # it as an assignment reports every type alias as undefined.
            case ast.TypeAlias() if isinstance(node.name, ast.Name):
                facts.bound.add(node.name.id)
            case ast.Import() | ast.ImportFrom():
                _absorb_import(node)
            case ast.If() | ast.Try():
                # TYPE_CHECKING blocks and guarded imports still bind names.
                for sub in ast.walk(node):
                    if isinstance(sub, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                        facts.bound.add(sub.name)
                    elif isinstance(sub, ast.Import | ast.ImportFrom):
                        _absorb_import(sub)

    facts.exported = _exported_names(tree)
    facts.lazy = _lazy_resolvable_names(tree)
    facts.has_lazy_getattr = any(isinstance(node, ast.FunctionDef) and node.name == "__getattr__" for node in tree.body)
    return facts


@dataclass(frozen=True)
class ScanResult:
    """Both directions plus the population each was measured over."""

    forward: list[FacadeBreak]
    mirror: list[FacadeBreak]
    facade_count: int
    module_count: int
    syntax_errors: list[str]
    missing_modules: list[FacadeBreak]


def scan(rev: str, *, repo_root: Path = REPO_ROOT) -> ScanResult:
    """Scan one pinned revision for facade export breaks in both directions."""
    blobs = read_python_blobs(rev, repo_root=repo_root)

    trees: dict[str, ast.Module] = {}
    syntax_errors: list[str] = []
    for path, source in blobs.items():
        try:
            trees[path] = ast.parse(source, filename=path)
        except SyntaxError as exc:
            syntax_errors.append(f"{path}: {exc}")

    module_of = {path: module_name_for_path(path) for path in trees}
    path_of = {module: path for path, module in module_of.items()}
    facts = {module_of[path]: module_facts(tree) for path, tree in trees.items()}
    packages = {module_of[path] for path in trees if path.endswith("__init__.py")}

    def _normalise(target: str) -> str:
        """Collapse an explicit ``pkg.__init__`` target onto the package itself."""
        return target[: -len(".__init__")] if target.endswith(".__init__") else target

    # ``from pkg import sub`` where ``pkg.sub`` is a real module is a SUBMODULE
    # import: legal, and it needs neither a definition nor an ``__all__`` entry.
    # Without modelling it the scan reports every such import as a break.
    submodules: dict[str, set[str]] = defaultdict(set)
    for module in path_of:
        if "." in module:
            parent, leaf = module.rsplit(".", 1)
            submodules[parent].add(leaf)

    forward: list[FacadeBreak] = []
    for path, tree in trees.items():
        if not path.endswith("__init__.py"):
            continue
        facade = module_of[path]
        base = _binding_package(path, facade)
        for node in tree.body:
            if not isinstance(node, ast.ImportFrom) or node.level == 0:
                continue
            target = resolve_relative(base, node.level, node.module)
            target_facts = facts.get(target)
            if target_facts is None or target_facts.star_import:
                continue
            for alias in node.names:
                if alias.name == "*" or alias.name in target_facts.bound:
                    continue
                if alias.name in submodules.get(target, set()):
                    continue
                if target_facts.has_lazy_getattr and alias.name in target_facts.lazy:
                    continue
                forward.append(FacadeBreak(facade, alias.name, target, "import-not-defined"))

        facade_facts = facts[facade]
        if facade_facts.exported and not facade_facts.star_import:
            for name in facade_facts.exported:
                if name in facade_facts.bound or name in facade_facts.lazy:
                    continue
                if name in submodules.get(facade, set()):
                    continue
                forward.append(FacadeBreak(facade, name, facade, "exported-not-bound"))

    mirror: list[FacadeBreak] = []
    missing_modules: list[FacadeBreak] = []
    for path, tree in trees.items():
        consumer = module_of[path]
        base = _binding_package(path, consumer)
        for node in tree.body:
            if not isinstance(node, ast.ImportFrom):
                continue
            if node.level:
                target = resolve_relative(base, node.level, node.module)
            elif node.module and node.module.split(".")[0] == "cadrumo":
                target = node.module
            else:
                continue
            target = _normalise(target)
            # A committed import of a module that does not exist at this
            # revision breaks the same way a missing symbol does, and arrives by
            # the same route: the module is present in every working tree while
            # still untracked, so the consumer looks committed and sound. The
            # symbol-level checks cannot see it -- there is no target module to
            # compare a name against -- so it is reported separately.
            if target not in facts:
                missing_modules.append(
                    FacadeBreak(consumer, node.module or ".", target, "module-not-at-revision"),
                )
                continue
            if target not in packages or target == consumer:
                continue
            target_facts = facts[target]
            if target_facts.star_import or target_facts.exported is None:
                continue
            available = (
                set(target_facts.exported) | target_facts.bound | target_facts.lazy | submodules.get(target, set())
            )
            for alias in node.names:
                if alias.name == "*" or alias.name.startswith("__"):
                    continue
                if alias.name not in available:
                    mirror.append(FacadeBreak(consumer, alias.name, target, "imported-not-available"))

    return ScanResult(
        forward=sorted(forward, key=lambda b: (b.facade, b.symbol)),
        mirror=sorted(mirror, key=lambda b: (b.target, b.symbol, b.facade)),
        facade_count=len(packages),
        module_count=len(trees),
        syntax_errors=syntax_errors,
        missing_modules=sorted(missing_modules, key=lambda b: (b.facade, b.target)),
    )


def main() -> int:
    """Print a scan of ``HEAD`` for interactive use."""
    result = scan("HEAD")
    print(f"modules {result.module_count}  facades {result.facade_count}")
    print(f"syntax errors: {len(result.syntax_errors)}")
    print(f"forward breaks: {len(result.forward)}")
    for item in result.forward:
        print(f"  {item.describe()}")
    print(f"mirror breaks: {len(result.mirror)}")
    for item in result.mirror:
        print(f"  {item.describe()}")
    return 1 if (result.forward or result.mirror or result.syntax_errors) else 0


if __name__ == "__main__":
    raise SystemExit(main())
