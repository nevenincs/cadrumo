"""Gate: every secure store production reads must have a production writer.

An encrypted repository the shipped application reads but never writes is
indistinguishable, from every reader's side, from a store that happens to be
empty. The read succeeds, the iteration yields nothing, and the caller renders
a zero. Nothing is red: the repository imports, its own tests pass because they
save through it directly, and the namespace is registered exactly like every
store that does get filled.

That is the shape ``no-silent-under-declaration`` exists to refuse. "The
operator has no filing drafts" and "this application never stores a filing
draft" are different facts, and a count rendered from an unwritten store
reports the first while meaning the second. Where the store feeds an
aggregation rather than a display, the same absence becomes a zero inside a
filing-grade total.

The property is read from the live tree rather than declared, so it cannot go
stale. A repository is WRITTEN when some production module calls a mutating
method on a value bound to it, and READ when a production module outside the
repository's own defining module calls anything else on one. The owner
exclusion is deliberate and applies to reads only: a repository whose write
helper lives beside the class is written by every caller of that helper, while
a repository only its own module reads is not yet wired to anything.

Binding follows the three shapes the codebase actually uses -- assignment from
a construction, a parameter annotated with the repository type, and an instance
attribute -- and unwraps ``x if x is not None else Repository()`` and
``x or Repository()``, the canonical inject-or-default idiom. Without that
unwrapping the gate reports the most carefully written repositories in the
tree, because taking an injected repository is what a testable one does.

Mutation is recognised by verb rather than by an exact method name: the stores
here expose ``save``, ``save_period``, ``save_observation`` and
``persist_*`` for the same operation, and a name list would quietly reclassify
a store as unwritten the next time one was added.

The verdict is set equality against ``secure_store_write_path.toml`` in both
directions, for the reason every baseline in this tree is:

* a read-only store the declaration does not name is new debt -- a store was
  wired for reading before anything filled it;
* a declared store that now has a writer is a spent entry, and the declaration
  must shrink to record that the debt was paid.

Only the second direction keeps the file honest. Without it the declaration
accumulates, and a later reader cannot tell an accepted exception from a line
nobody removed.
"""

from __future__ import annotations

import ast
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Final

_REPO_BASE: Final = "SecureBoundRepository"
_SOURCE_ROOT: Final = Path(__file__).resolve().parents[2] / "src" / "cadrumo"
_DECLARATION: Final = Path(__file__).resolve().parent / "secure_store_write_path.toml"

#: A method mutates the store when any snake_case token of its name is one of
#: these verbs. ``save``, ``save_period``, ``save_observation`` and
#: ``to_secure_object_write`` are all the same operation under four names.
_MUTATOR_VERBS: Final = (
    "save",
    "store",
    "persist",
    "write",
    "delete",
    "remove",
    "upsert",
    "put",
    "clear",
    "record",
    "append",
    "replace",
    "commit",
)

_READ_ONLY_KINDS: Final = frozenset({"custody_carry_only", "awaiting_writer"})


class SecureStoreWritePathError(RuntimeError):
    """The declaration and the live tree disagree about which stores are filled."""


@dataclass(frozen=True, slots=True)
class StoreUsage:
    """Where one secure repository is read and where it is written."""

    name: str
    owner: str
    read_by: tuple[str, ...]
    written_by: tuple[str, ...]

    @property
    def is_read_only(self) -> bool:
        """Return whether production reads this store and nothing fills it."""
        return bool(self.read_by) and not self.written_by


def _called_name(func: ast.expr) -> str | None:
    """Return the bare name a call expression invokes.

    ``getattr(func, "id", None)`` would read the same two attributes, but it
    erases the type: the result widens to ``Any`` and the narrowing this
    module relies on stops meaning anything.
    """
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _is_mutator(method: str) -> bool:
    """Return whether a method name declares a mutating operation.

    Matched on whole snake_case tokens rather than a prefix, because a write
    is not always the leading verb: a repository that participates in an
    atomic commit exposes ``to_secure_object_write``, which builds the write
    the committer applies, and a prefix rule reads that as a query.
    """
    return bool(set(method.split("_")) & set(_MUTATOR_VERBS))


def _production_modules(root: Path) -> dict[Path, ast.Module]:
    """Parse every shipped module, skipping tests and caches."""
    trees: dict[Path, ast.Module] = {}
    for path in sorted(root.rglob("*.py")):
        if "tests" in path.parts or "__pycache__" in path.parts or path.name.startswith("test_"):
            continue
        try:
            trees[path] = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
    return trees


def _repository_classes(trees: dict[Path, ast.Module], root: Path) -> dict[str, str]:
    """Return each secure repository class mapped to its defining module path."""
    owners: dict[str, str] = {}
    for path, tree in trees.items():
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and any(_REPO_BASE in ast.unparse(base) for base in node.bases):
                owners[node.name] = path.relative_to(root).as_posix()
    return owners


def _annotated_repositories(annotation: ast.expr | None, repositories: frozenset[str]) -> set[str]:
    """Return the repository names an annotation mentions."""
    if annotation is None:
        return set()
    mentioned = {node.id for node in ast.walk(annotation) if isinstance(node, ast.Name)}
    mentioned |= {node.attr for node in ast.walk(annotation) if isinstance(node, ast.Attribute)}
    return mentioned & repositories


def _construction_source(value: ast.expr, repositories: frozenset[str], bound: dict[str, str]) -> str | None:
    """Resolve the repository an assigned expression yields, if any.

    ``x if x is not None else Repository()`` and ``x or Repository()`` are the
    inject-or-default idiom; both branches are candidates, so the construction
    is found whichever side carries it.
    """
    pending: list[ast.expr] = [value]
    while pending:
        node = pending.pop()
        if isinstance(node, ast.IfExp):
            pending.extend((node.body, node.orelse))
            continue
        if isinstance(node, ast.BoolOp):
            pending.extend(node.values)
            continue
        if isinstance(node, ast.Call):
            called = _called_name(node.func)
            if called is not None and called in repositories:
                return called
        elif isinstance(node, ast.Name) and node.id in bound:
            return bound[node.id]
    return None


def _bindings(
    tree: ast.Module,
    repositories: frozenset[str],
) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    """Return the local names, instance attributes, and accessors bound to a repository.

    An accessor is a function whose return annotation names a repository, so
    ``self._drafts().save(draft)`` and ``_draft_repo().save(draft)`` resolve to
    the store they hand back. Without it a lazily resolved repository -- the
    shape used wherever construction must wait for a bucket -- is invisible on
    both sides, and the gate reports a store that is written every run.
    """
    names: dict[str, str] = {}
    attributes: dict[str, str] = {}
    accessors: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            arguments = node.args
            for argument in (*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs):
                for repository in _annotated_repositories(argument.annotation, repositories):
                    names[argument.arg] = repository
            for repository in _annotated_repositories(node.returns, repositories):
                accessors[node.name] = repository
        elif isinstance(node, ast.AnnAssign):
            for repository in _annotated_repositories(node.annotation, repositories):
                if isinstance(node.target, ast.Name):
                    names[node.target.id] = repository
                elif isinstance(node.target, ast.Attribute):
                    attributes[node.target.attr] = repository
        elif isinstance(node, ast.Assign):
            source = _construction_source(node.value, repositories, names)
            if source is None:
                continue
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names[target.id] = source
                elif isinstance(target, ast.Attribute):
                    attributes[target.attr] = source
    return names, attributes, accessors


def _receiver_repository(
    receiver: ast.expr,
    *,
    repositories: frozenset[str],
    names: dict[str, str],
    attributes: dict[str, str],
    accessors: dict[str, str],
) -> str | None:
    """Return the repository a call's receiver refers to, if any."""
    if isinstance(receiver, ast.Call):
        called = _called_name(receiver.func)
        if called is None:
            return None
        if called in repositories:
            return called
        return accessors.get(called)
    if isinstance(receiver, ast.Name):
        return names.get(receiver.id)
    if isinstance(receiver, ast.Attribute):
        return attributes.get(receiver.attr)
    return None


def collect_store_usage(root: Path = _SOURCE_ROOT) -> tuple[StoreUsage, ...]:
    """Return read and write sites for every secure repository in the tree."""
    trees = _production_modules(root)
    owners = _repository_classes(trees, root)
    repositories = frozenset(owners)
    reads: dict[str, set[str]] = {name: set() for name in repositories}
    writes: dict[str, set[str]] = {name: set() for name in repositories}
    for path, tree in trees.items():
        names, attributes, accessors = _bindings(tree, repositories)
        module = path.relative_to(root).as_posix()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            repository = _receiver_repository(
                node.func.value,
                repositories=repositories,
                names=names,
                attributes=attributes,
                accessors=accessors,
            )
            if repository is None:
                continue
            target = writes if _is_mutator(node.func.attr) else reads
            target[repository].add(module)
    return tuple(
        StoreUsage(
            name=name,
            owner=owners[name],
            # a store its own module reads is not yet wired to anything; the
            # same exclusion on writes would hide every write helper sited
            # beside its repository, which is where they belong
            read_by=tuple(sorted(reads[name] - {owners[name]})),
            written_by=tuple(sorted(writes[name])),
        )
        for name in sorted(repositories)
    )


def _declared_read_only(declaration: Path = _DECLARATION) -> dict[str, str]:
    """Return the declared read-only stores mapped to their rationale."""
    if not declaration.exists():
        return {}
    document = tomllib.loads(declaration.read_text(encoding="utf-8"))
    declared: dict[str, str] = {}
    for entry in document.get("read_only", ()):
        name = str(entry.get("name", "")).strip()
        kind = str(entry.get("kind", "")).strip()
        rationale = str(entry.get("rationale", "")).strip()
        if not name:
            raise SecureStoreWritePathError("a read_only entry declares no name")
        if kind not in _READ_ONLY_KINDS:
            raise SecureStoreWritePathError(f"{name} declares unknown kind {kind!r}")
        if not rationale:
            raise SecureStoreWritePathError(f"{name} declares no rationale")
        declared[name] = rationale
    return declared


def evaluate(root: Path = _SOURCE_ROOT, declaration: Path = _DECLARATION) -> tuple[str, ...]:
    """Return the verdict lines; an empty tuple is a pass."""
    usage = collect_store_usage(root)
    observed = {store.name for store in usage if store.is_read_only}
    declared = _declared_read_only(declaration)
    problems: list[str] = []
    for name in sorted(observed - set(declared)):
        store = next(entry for entry in usage if entry.name == name)
        readers = ", ".join(store.read_by)
        problems.append(
            f"+ {name}: production reads this secure store and nothing writes it ({readers}). "
            "Wire the writer, or declare it read_only with its kind and rationale.",
        )
    for name in sorted(set(declared) - observed):
        problems.append(
            f"- {name}: declared read_only, but the tree now writes it. Remove the spent entry.",
        )
    return tuple(problems)


def main() -> int:
    """Print the verdict and return the process exit status."""
    usage = collect_store_usage()
    problems = evaluate()
    declared = _declared_read_only()
    print(f"{len(usage)} secure store(s); {len(declared)} declared read-only.")
    for name, rationale in sorted(declared.items()):
        print(f"  = {name}: {rationale}")
    for problem in problems:
        print(f"  {problem}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
