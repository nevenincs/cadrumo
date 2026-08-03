"""Census of file-producing call sites, and where each one's path comes from.

Answers the storage campaign's closure question -- *are all file-producing sites
enrolled in the storage taxonomy?* -- by quantifying over **write primitives in
the source**, never over the taxonomy. That direction is the whole point: a
census that iterates declared members cannot see an *un*enrolled site, because
absence from the declaration is exactly what is being asked about.

Reads ONE pinned revision through ``git show``. Resolving ``HEAD`` lazily while
peers commit mixes trees and reports a count that belongs to no single state.

Two selector corrections are recorded here because both were live defects whose
symptom was a confident wrong number, and a future maintainer widening the
primitive set will meet them again:

``.save`` is not a filesystem primitive.
    A first pass treated it as one and returned 138 of 235 matches. Spot-reading
    showed almost all were ``repository.save(...)`` -- encrypted SQL
    secure-object writes touching no file. It is admitted here only when the
    receiver names a workbook-shaped object, which is the ``openpyxl`` case that
    genuinely writes.

``.replace`` and ``.rename`` need arity to disambiguate.
    ``Path.replace(target)`` takes one argument; ``str.replace(old, new)`` takes
    two. An earlier census in this campaign counted every attribute call named
    ``replace`` and reported 267 sites where roughly 99 existed.

What this cannot reach, stated rather than assumed away:

- **Duck-typed method names.** Without type inference ``Path.touch()`` and
  ``Session.touch()`` are indistinguishable. The residual is small and
  enumerable -- :data:`AMBIGUOUS_PRIMITIVES` names it -- so a caller can read
  those sites rather than trust them.
- **Writes through a retained handle.** A log handler binds one stream and
  writes through it forever: one syntactic site, unbounded real writes.
- **Cross-module composition**, where one module returns a directory and
  another appends to it.

Counts from this scanner are therefore an UPPER BOUND at a named revision, and
should be cited as such -- with the revision -- rather than quoted bare.

Usage::

    python -m dev.write_site_census <revision>
    python -m dev.write_site_census <revision> --json
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Final

REPO_ROOT: Final[Path] = Path(__file__).resolve().parent.parent

#: The written path is the RECEIVER: ``path.write_text(...)``, ``path.mkdir()``.
RECEIVER_PRIMITIVES: Final[frozenset[str]] = frozenset(
    {"write_text", "write_bytes", "mkdir", "touch", "symlink_to", "hardlink_to"},
)
#: Receiver primitives whose single-argument form alone is the filesystem one.
ARITY_ONE_PRIMITIVES: Final[frozenset[str]] = frozenset({"replace", "rename"})
#: The written path is an ARGUMENT; the value is the destination argument index,
#: or ``None`` where the primitive mints its own location.
ARGUMENT_PRIMITIVES: Final[dict[str, int | None]] = {
    "makedirs": 0,
    "copytree": 1,
    "copyfile": 1,
    "copy": 1,
    "copy2": 1,
    "move": 1,
    "make_archive": 0,
    "mkstemp": None,
    "mkdtemp": None,
    "NamedTemporaryFile": None,
    "TemporaryDirectory": None,
}
#: Method names shared with non-filesystem objects. A site using one of these is
#: reported so a reader can clear it; it is never silently trusted.
AMBIGUOUS_PRIMITIVES: Final[frozenset[str]] = frozenset({"save", "touch", "rename", "replace"})
#: Receiver-name fragments that make a bare ``.save(path)`` a real file write.
WORKBOOK_RECEIVER_HINTS: Final[tuple[str, ...]] = ("workbook", "wb", "book", "fig", "canvas", "image", "doc")

#: Symbols that mean the path came from the storage taxonomy or its accessors.
TAXONOMY_MARKERS: Final[frozenset[str]] = frozenset(
    {
        "storage_path",
        "bucket_scoped_storage_path",
        "bucket_paths",
        "keystore_path",
        "keystore_sidecar_path",
        "effective_storage_root",
        "storage_location",
        "ensure_storage_tree",
        "root_dir",
        "_root_dir",
        "_store_dir",
        "store_dir",
        "blobs_dir",
        "audit_dir",
        "db_dir",
        "bucket_root",
    },
)
SETTINGS_FIELD_PREFIX: Final[str] = "cadrumo_"
_MAX_TRACE_DEPTH: Final[int] = 6


@dataclass(frozen=True, slots=True)
class WriteSite:
    """One file-producing call site and the origin of the path it writes."""

    module: str
    line: int
    primitive: str
    origin: str
    provenance: str

    @property
    def ambiguous(self) -> bool:
        """Whether this site's primitive name is shared with non-filesystem objects."""
        return self.primitive in AMBIGUOUS_PRIMITIVES


def _git_show(revision: str, path: str) -> str:
    # Bytes then explicit UTF-8: ``text=True`` decodes as cp1252 on Windows and
    # mangles non-ASCII source, which fails the parse far from its cause.
    raw = subprocess.run(  # noqa: S603 - fixed argv, revision supplied by the maintainer
        ["git", "show", f"{revision}:{path}"],  # noqa: S607
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
    ).stdout
    return raw.decode("utf-8")


def production_modules(revision: str) -> list[str]:
    """Return every tracked production module at ``revision``, tests excluded."""
    listing = subprocess.run(  # noqa: S603
        ["git", "ls-tree", "-r", "--name-only", revision, "src/cadrumo/"],  # noqa: S607
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    return [
        entry
        for entry in listing
        if entry.endswith(".py") and "/tests/" not in entry and not Path(entry).name.startswith("test_")
    ]


def origin_symbol(node: ast.AST | None) -> str:
    """Reduce a path expression to the symbol it is rooted in."""
    if node is None:
        return "<absent>"
    while True:
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            node = node.left
        elif isinstance(node, ast.Call):
            node = node.func
        elif isinstance(node, ast.Attribute):
            if node.attr in TAXONOMY_MARKERS or node.attr.startswith(SETTINGS_FIELD_PREFIX):
                return node.attr
            node = node.value
        elif isinstance(node, ast.Subscript):
            node = node.value
        else:
            break
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Constant):
        return f"<literal {node.value!r}>"
    return f"<{type(node).__name__}>"


def write_target(node: ast.Call) -> tuple[str, ast.AST | None] | None:
    """Return ``(primitive, path expression)`` when ``node`` produces a file."""
    func = node.func
    if isinstance(func, ast.Name) and func.id == "open":
        return ("open", node.args[0] if node.args else None) if _opens_for_write(node) else None
    if not isinstance(func, ast.Attribute):
        return None
    name = func.attr
    if name in RECEIVER_PRIMITIVES:
        return name, func.value
    if name in ARITY_ONE_PRIMITIVES:
        return (name, func.value) if len(node.args) == 1 else None
    if name == "open":
        return ("open", func.value) if _opens_for_write(node, receiver_form=True) else None
    if name == "save":
        receiver = origin_symbol(func.value).lower()
        if any(hint in receiver for hint in WORKBOOK_RECEIVER_HINTS):
            return "save", node.args[0] if node.args else None
        return None
    if name in ARGUMENT_PRIMITIVES:
        index = ARGUMENT_PRIMITIVES[name]
        if index is None:
            return name, None
        return name, node.args[index] if len(node.args) > index else None
    return None


def _opens_for_write(node: ast.Call, *, receiver_form: bool = False) -> bool:
    """Whether an ``open`` call requests a writing mode."""
    mode: str | None = None
    mode_index = 0 if receiver_form else 1
    if len(node.args) > mode_index and isinstance(node.args[mode_index], ast.Constant):
        mode = str(node.args[mode_index].value)
    for keyword in node.keywords:
        if keyword.arg == "mode" and isinstance(keyword.value, ast.Constant):
            mode = str(keyword.value.value)
    return bool(mode) and any(flag in mode for flag in "wax")


def _bindings(scope: ast.AST) -> dict[str, ast.AST]:
    """Map names and ``self`` attributes assigned in ``scope`` to their values."""
    bound: dict[str, ast.AST] = {}
    for node in ast.walk(scope):
        if isinstance(node, ast.Assign):
            targets, value = list(node.targets), node.value
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)) and node.value is not None:
            targets, value = [node.target], node.value
        elif isinstance(node, ast.withitem) and node.optional_vars is not None:
            targets, value = [node.optional_vars], node.context_expr
        else:
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                bound.setdefault(target.id, value)
            elif isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self":
                bound.setdefault(f"self.{target.attr}", value)
    return bound


def _trace(symbol: str, scopes: list[dict[str, ast.AST]], depth: int = 0) -> str:
    """Follow assignments until the symbol stops resolving to something else."""
    if depth >= _MAX_TRACE_DEPTH or symbol.startswith("<"):
        return symbol
    if symbol in TAXONOMY_MARKERS or symbol.startswith(SETTINGS_FIELD_PREFIX):
        return symbol
    for scope in scopes:
        if symbol in scope:
            following = origin_symbol(scope[symbol])
            return symbol if following == symbol else _trace(following, scopes, depth + 1)
    return symbol


def classify(origin: str, *, local_params: set[str], module_params: set[str]) -> str:
    """Name where the written path came from."""
    if origin.startswith("<literal"):
        return "literal"
    if origin in TAXONOMY_MARKERS or origin.startswith(SETTINGS_FIELD_PREFIX):
        return "taxonomy"
    lowered = origin.lower()
    if "tmp" in lowered or "temp" in lowered:
        return "temporary"
    if origin in local_params or origin == "self" or origin.startswith("self.") or origin in module_params:
        # The caller chose the path, so this site has no enrollment answer of
        # its own -- the question relocates to every call site.
        return "pass_through"
    if origin.startswith("<"):
        return "unresolved"
    return "local"


def census(revision: str) -> list[WriteSite]:
    """Return every file-producing site in production code at ``revision``."""
    sites: list[WriteSite] = []
    for module in production_modules(revision):
        try:
            tree = ast.parse(_git_show(revision, module))
        except SyntaxError:
            continue
        module_params = {
            argument.arg
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            for argument in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)
        }
        class_bindings: dict[int, dict[str, ast.AST]] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                shared = _bindings(node)
                for child in ast.walk(node):
                    class_bindings.setdefault(id(child), shared)
        module_bindings = _bindings(tree)

        seen: set[int] = set()
        for scope_node in ast.walk(tree):
            local_params: set[str] = set()
            if isinstance(scope_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                arguments = scope_node.args
                local_params = {
                    argument.arg for argument in (*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs)
                }
            scopes = [_bindings(scope_node), class_bindings.get(id(scope_node), {}), module_bindings]
            for node in ast.walk(scope_node):
                if not isinstance(node, ast.Call) or node.lineno in seen:
                    continue
                found = write_target(node)
                if found is None:
                    continue
                primitive, path_expression = found
                origin = _trace(origin_symbol(path_expression), scopes)
                seen.add(node.lineno)
                sites.append(
                    WriteSite(
                        module=module,
                        line=node.lineno,
                        primitive=primitive,
                        origin=origin,
                        provenance=classify(origin, local_params=local_params, module_params=module_params),
                    ),
                )
    return sorted(sites, key=lambda site: (site.module, site.line))


def main(argv: list[str] | None = None) -> int:
    """Print the census for one pinned revision, as text or JSON."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("revision", help="git revision to read; pin it, never pass a moving name")
    parser.add_argument("--json", action="store_true", help="emit machine-readable output")
    arguments = parser.parse_args(argv)

    sites = census(arguments.revision)
    if arguments.json:
        payload = {
            "revision": arguments.revision,
            "site_count": len(sites),
            "ambiguous_count": sum(site.ambiguous for site in sites),
            "by_provenance": dict(Counter(site.provenance for site in sites)),
            "sites": [site.__dict__ for site in sites],
        }
        print(json.dumps(payload, indent=2))
        return 0

    print(f"revision {arguments.revision}")
    print(f"file-producing sites (upper bound) {len(sites)}")
    for provenance, count in Counter(site.provenance for site in sites).most_common():
        print(f"  {provenance:14s} {count:4d}")
    ambiguous = [site for site in sites if site.ambiguous]
    print(f"\nambiguous primitives needing a read ({len(ambiguous)}):")
    for site in ambiguous:
        print(f"  {site.module}:{site.line}  {site.primitive}({site.origin})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
