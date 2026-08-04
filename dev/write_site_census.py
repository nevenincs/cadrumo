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

``--scope tests`` walks the test tree instead of production modules, for the
storage campaign's literal-corpus triage (``S78``). This answers a narrower
and different question than the production scope: not "is this write
enrolled" but "what root does this test-composed path trace back to". Read
the two things it can and cannot decide before trusting a bucket count:

**Decidable from the rooted symbol alone -- three of five outcomes:**

- ``fixture`` -- rooted at :data:`FIXTURE_MARKERS` (``FIXTURES_DIR``, the
  package's own exported fixture-tree constant, or ``bundled_path``, the
  canonical bundled-resource accessor every fixture alias eventually
  resolves through). A different namespace than the storage taxonomy;
  never chosen or written by the running application. Out of scope for
  enrollment, not a finding.
- ``temporary`` / ``pass_through`` -- rooted at ``tmp_path`` or a parameter
  the enclosing function was called with. The test itself supplied the
  root; there is no enrollment answer to give here, the same as
  :func:`classify`'s production meaning -- a caller-injected path has no
  answer of its own, the question relocates to the call site that chose it.
- ``taxonomy`` -- rooted at a real accessor or a ``cadrumo_``-prefixed
  settings field. Reaches a live, taxonomy-governed location.

**NOT decidable from the root alone -- the remaining two outcomes require
reading what the test measures, not where the expression is rooted:**

``pin`` (a deliberate independent oracle a test must hand-write to avoid
comparing the taxonomy against itself) and ``migrate`` (a hand-rolled
scaffold path that should route through the accessor instead) can be
**byte-identical expressions** -- ``storage_root / "buckets" / id / "db" /
"cadrumo.db"`` is a correct oracle in one module and a missing-accessor
smell in the next, and only the test's subject tells them apart. Both fall
into the ``local`` bucket here, alongside anything genuinely unresolved.

**This tool is therefore a triage that shrinks the hand-classified set, not
one that replaces it.** Treat ``local`` as "still needs a human read", never
as "everything else, safely ignorable" -- and read the reported unresolved
rate before trusting any bucket count, since test-tree tracing hits
``unresolved`` far more often than production (paths arrive via fixtures,
parametrize tuples, and helper returns that this scanner does not follow).

Usage::

    python -m dev.write_site_census <revision>
    python -m dev.write_site_census <revision> --json
    python -m dev.write_site_census <revision> --scope tests
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
#: Symbols that mean the path came from a bundled, committed, read-only test
#: resource -- a fixture tree -- rather than anything the running application
#: chooses or writes. ``FIXTURES_DIR`` is ``cadrumo.tests``'s own exported
#: constant; ``bundled_path`` is the canonical accessor for the packaged data
#: root every fixture-corpus alias (``_JUSTIFICANTE_CORPUS_ROOT``,
#: ``_DATA_ROOT``, a re-imported ``_FIXTURES_ROOT``, ...) eventually resolves
#: through, once :func:`_bindings` follows the aliasing import.
FIXTURE_MARKERS: Final[frozenset[str]] = frozenset({"FIXTURES_DIR", "bundled_path"})
SETTINGS_FIELD_PREFIX: Final[str] = "cadrumo_"
_MAX_TRACE_DEPTH: Final[int] = 6
#: Module sets :func:`census` can walk. ``tests`` is the storage campaign's
#: literal-corpus triage; see the module docstring for what it can and
#: cannot decide.
SCOPES: Final[frozenset[str]] = frozenset({"production", "tests"})


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


def test_modules(revision: str) -> list[str]:
    """Return every tracked test module at ``revision`` -- the inverse filter of :func:`production_modules`.

    Test-tree tracing answers the narrower, different question the module
    docstring states: where a test-composed path traces back to, not whether
    a write is enrolled. Read that caveat before treating any bucket from
    this walk as a verdict.
    """
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
        if entry.endswith(".py") and ("/tests/" in entry or Path(entry).name.startswith("test_"))
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
        # Exactly one positional argument AND no keywords. Counting positional
        # arity alone admitted three domain renames --
        # ``repository.rename(profile_id, new_label=...)`` and friends -- which
        # pass a bare ``len(args) == 1`` test. ``Path.rename`` / ``Path.replace``
        # never take keywords, so requiring their absence costs no true positive.
        return (name, func.value) if len(node.args) == 1 and not node.keywords else None
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
    """Map names and ``self`` attributes assigned in ``scope`` to their values.

    ``from X import Y as Z`` counts as a binding too: ``Z`` is a rebind of
    ``Y``, exactly like a plain assignment, and without following it an
    aliased import of a taxonomy or fixture marker (``FIXTURES_DIR as
    _FIXTURES_ROOT`` is the shape the test tree actually uses) resolves to
    nothing rather than to what it really names. The synthetic ``ast.Name``
    node carries only the original imported name; it has no real location,
    but :func:`origin_symbol` only ever reads ``.id`` off it.
    """
    bound: dict[str, ast.AST] = {}
    for node in ast.walk(scope):
        if isinstance(node, ast.Assign):
            targets, value = list(node.targets), node.value
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)) and node.value is not None:
            targets, value = [node.target], node.value
        elif isinstance(node, ast.withitem) and node.optional_vars is not None:
            targets, value = [node.optional_vars], node.context_expr
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.asname is not None:
                    bound.setdefault(alias.asname, ast.Name(id=alias.name))
            continue
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
    if symbol in TAXONOMY_MARKERS or symbol.startswith(SETTINGS_FIELD_PREFIX) or symbol in FIXTURE_MARKERS:
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
    if origin in FIXTURE_MARKERS:
        return "fixture"
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


def census(revision: str, *, scope: str = "production") -> list[WriteSite]:
    """Return every file-producing site in the chosen module set at ``revision``.

    Args:
        revision: Git revision to read; pin it, never pass a moving name.
        scope: One of :data:`SCOPES`. ``"production"`` (the default) preserves
            the campaign's original closure question and its guarantees;
            ``"tests"`` walks the test tree instead and answers a narrower,
            different question -- read the module docstring before trusting
            its buckets.

    Raises:
        ValueError: If ``scope`` is not a member of :data:`SCOPES`.
    """
    if scope not in SCOPES:
        raise ValueError(f"scope must be one of {sorted(SCOPES)}, got {scope!r}")
    module_lister = production_modules if scope == "production" else test_modules
    sites: list[WriteSite] = []
    for module in module_lister(revision):
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
    parser.add_argument(
        "--scope",
        choices=sorted(SCOPES),
        default="production",
        help="module set to walk; 'tests' answers a narrower question -- see the module docstring",
    )
    arguments = parser.parse_args(argv)

    sites = census(arguments.revision, scope=arguments.scope)
    unresolved_count = sum(1 for site in sites if site.provenance == "unresolved")
    unresolved_rate = (unresolved_count / len(sites)) if sites else 0.0
    if arguments.json:
        payload = {
            "revision": arguments.revision,
            "scope": arguments.scope,
            "site_count": len(sites),
            "unresolved_count": unresolved_count,
            "unresolved_rate": unresolved_rate,
            "ambiguous_count": sum(site.ambiguous for site in sites),
            "by_provenance": dict(Counter(site.provenance for site in sites)),
            "sites": [site.__dict__ for site in sites],
        }
        print(json.dumps(payload, indent=2))
        return 0

    print(f"revision {arguments.revision}")
    print(f"scope {arguments.scope}")
    print(f"file-producing sites (upper bound) {len(sites)}")
    # Headline, not a footnote: an unresolved bucket that quietly absorbs a
    # third of the corpus while the summary reads clean is the failure mode
    # this line exists to prevent, especially under --scope tests where
    # tracing hits it far more often than production.
    print(
        f"unresolved rate {unresolved_rate:.0%} ({unresolved_count} of {len(sites)}) "
        "-- read these, do not trust them",
    )
    for provenance, count in Counter(site.provenance for site in sites).most_common():
        print(f"  {provenance:14s} {count:4d}")
    ambiguous = [site for site in sites if site.ambiguous]
    print(f"\nambiguous primitives needing a read ({len(ambiguous)}):")
    for site in ambiguous:
        print(f"  {site.module}:{site.line}  {site.primitive}({site.origin})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
