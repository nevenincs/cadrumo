r"""Enforce that SHIPPED `cadrumo` modules never import the unshipped `dev` tree.

`dev/` is development tooling. It is excluded from both distribution targets
in `pyproject.toml`, it is not a dependency of the wheel, and it does not exist
on an installed consumer's machine. So a shipped `cadrumo` module that imports
`dev.anything` is not a style problem — it is an `ImportError` for every user
of the distribution, and one that no amount of running the suite from a repo
checkout can surface, because from a checkout `dev/` is importable and the
import resolves happily.

That is the whole reason this gate lives HERE, on the `dev` side, and cannot
live under `src/cadrumo/`. The scan's subject is the shipped package, and a
scanner is not allowed to be a member of its own subject: a gate placed inside
`src/cadrumo/` would either import `dev` itself (becoming the very violation it
detects) or force this logic to be duplicated on the shipped side, which then
ships to users who have no use for it. The dependency direction is one-way by
construction — `dev` may read `cadrumo`, never the reverse.

What "shipped" means is READ FROM THE PACKAGING CONFIG, never restated
--------------------------------------------------------------------
The file set is derived from `[tool.hatch.build.targets.wheel]`'s own
`packages` and `exclude` keys. A hand-maintained mirror of that list is the
obvious implementation and it is wrong: the exclusions are what makes today's
tree compliant (every current `dev` import under `src/cadrumo/` sits in a
`tests/` directory that both distribution targets drop), so a copy that fell
out of step would keep passing while the packaging config admitted a whole
directory back into the wheel. Reading the real key means a change to
packaging automatically re-scopes the gate, in the direction that tightens it.

Deferred imports are reported, not excused
------------------------------------------
A function-local `import dev.x` is flagged exactly like a module-level one. It
fails later rather than at import time, which makes it worse to diagnose, not
more acceptable. `importlib.import_module("dev.x")` is flagged too: the AST
cannot see through a computed string, but it can see a literal one, and a
literal one is the same statement wearing a disguise.

Intended invocation:

* `python -m dev.quality.shipped_package_boundary` — full scan, non-zero exit
  on any violation.
* `dev/quality/tests/test_shipped_package_boundary.py` — the gate.
"""

from __future__ import annotations

import ast
import fnmatch
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Final

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
PYPROJECT: Final[Path] = REPO_ROOT / "pyproject.toml"

#: Import roots that exist only in a repository checkout. `dev` is the sole
#: top-level first-party package outside the shipped tree; it is named rather
#: than discovered so that a stray `__init__.py` appearing at the repo root
#: cannot silently widen what this gate refuses.
UNSHIPPED_IMPORT_ROOTS: Final[frozenset[str]] = frozenset({"dev"})

_IMPORT_MODULE_FUNCTIONS: Final[frozenset[str]] = frozenset({"import_module", "importorskip"})


@dataclass(frozen=True)
class BoundaryViolation:
    """One shipped module importing an unshipped root."""

    path: Path
    line: int
    statement: str

    def render(self) -> str:
        """Return the one-line `file:line` report a reader can jump to.

        A repo-relative path is the readable form, but the absolute path is the
        honest fallback rather than an error: a reporter that raises while
        reporting a violation converts a legible failure into a traceback, and
        this one is reached from `main` precisely when something is already
        wrong.
        """
        try:
            location = self.path.relative_to(REPO_ROOT).as_posix()
        except ValueError:
            location = self.path.as_posix()
        return f"{location}:{self.line}: {self.statement}"


def _wheel_build_config() -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return the wheel target's (packages, exclude) globs from `pyproject.toml`."""
    config = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    wheel = config["tool"]["hatch"]["build"]["targets"]["wheel"]
    return tuple(wheel["packages"]), tuple(wheel.get("exclude", ()))


def _is_excluded(relative_posix: str, exclude_globs: tuple[str, ...]) -> bool:
    """Report whether hatch's exclude globs drop ``relative_posix`` from the wheel.

    ``fnmatch`` treats ``*`` as matching separators too, which is exactly the
    semantics wanted here: every exclusion in this project's config is either a
    directory prefix or a ``**`` recursive form, and both are satisfied by the
    looser match. A pattern that under-matched would silently shrink the
    scanned set, so erring toward matching MORE excludes is the safe direction
    only for correctness of the exclusion itself — which is why the gate
    additionally asserts the resulting shipped set is non-empty and contains
    known modules.
    """
    return any(fnmatch.fnmatch(relative_posix, pattern) for pattern in exclude_globs)


def shipped_python_files() -> tuple[Path, ...]:
    """Return every `*.py` file the wheel actually carries.

    Derived from the packaging config rather than restated, so a change to what
    ships re-scopes this gate automatically.
    """
    packages, exclude_globs = _wheel_build_config()
    found: list[Path] = []
    for package in packages:
        root = REPO_ROOT / package
        for path in sorted(root.rglob("*.py")):
            relative = path.relative_to(REPO_ROOT).as_posix()
            if not _is_excluded(relative, exclude_globs):
                found.append(path)
    return tuple(found)


def _root_of(module: str | None) -> str | None:
    """Return the top-level package of a dotted module path."""
    if not module:
        return None
    return module.split(".", 1)[0]


def _literal_module_arguments(node: ast.Call) -> tuple[str, ...]:
    """Return literal string module names passed to a dynamic-import call.

    Only a bare `import_module("dev.x")` / `importorskip("dev.x")` shape is
    read. A computed target is genuinely invisible to an AST scan, and this
    module's docstring says so rather than pretending otherwise.
    """
    function = node.func
    name = function.attr if isinstance(function, ast.Attribute) else getattr(function, "id", None)
    if name not in _IMPORT_MODULE_FUNCTIONS:
        return ()
    return tuple(arg.value for arg in node.args if isinstance(arg, ast.Constant) and isinstance(arg.value, str))


def scan_file(path: Path) -> tuple[BoundaryViolation, ...]:
    """Return every unshipped-root import in one shipped module.

    Walks the whole tree rather than the module body, so a deferred
    function-local import is reported identically to a top-level one.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations: list[BoundaryViolation] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _root_of(alias.name) in UNSHIPPED_IMPORT_ROOTS:
                    violations.append(BoundaryViolation(path, node.lineno, f"import {alias.name}"))
        elif isinstance(node, ast.ImportFrom):
            # `level` > 0 is a relative import, which can never reach `dev`
            # from inside the shipped package.
            if node.level == 0 and _root_of(node.module) in UNSHIPPED_IMPORT_ROOTS:
                names = ", ".join(alias.name for alias in node.names)
                violations.append(BoundaryViolation(path, node.lineno, f"from {node.module} import {names}"))
        elif isinstance(node, ast.Call):
            for module in _literal_module_arguments(node):
                if _root_of(module) in UNSHIPPED_IMPORT_ROOTS:
                    violations.append(BoundaryViolation(path, node.lineno, f'import_module("{module}")'))

    return tuple(violations)


def scan() -> tuple[BoundaryViolation, ...]:
    """Return every unshipped-root import across the whole shipped package."""
    return tuple(violation for path in shipped_python_files() for violation in scan_file(path))


def main() -> int:
    """Report violations; exit non-zero when the boundary is crossed.

    Silent on success, matching its sibling static checks. That the scan
    reached a real file set is asserted by the gate rather than announced
    here, so a clean run adds no noise to the per-push log.
    """
    violations = scan()
    if not violations:
        return 0

    print(f"{len(violations)} shipped module(s) import the unshipped dev tree:", file=sys.stderr)
    for violation in violations:
        print(f"  {violation.render()}", file=sys.stderr)
    print(
        "\n`dev/` is excluded from both distribution targets, so each of these is an "
        "ImportError on an installed consumer's machine. Move the shared code into "
        "`src/cadrumo/`, or move the consumer out of the shipped tree.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
