"""Every fully-qualified ``cadrumo.*`` docstring reference must resolve.

This check has now been misled by prose three times, each in a different
way, and each time the prose named something:

- ``safe_repository_id`` described a two-layer path contract whose second layer
  had been deleted with the module that needed it;
- two docstrings cited a CLI-side lazy-import gate that nobody had written
  back, each pointing at the other as corroboration;
- ``_section_rows`` named ``ProfileCapsuleLifecycle.edit_fields`` as the write
  door judging a whole fact batch -- a method that does not exist, on a class
  that owns no field-editing method at all.

The shipped firmware already applies this discipline to its own prose: a name
in an always-on mandate must resolve to a real artifact, because a dangling
name degrades every session that reads it. The same argument holds here. A
docstring is the first thing a reader consults about a boundary, and one that
names a function, class or module confidently is trusted more than an absence
would be -- so a stale name is worse than no name.

**Scope is deliberate.** Only FULLY-QUALIFIED ``cadrumo.*`` targets are
checked, and only in the packages covered by this check. A bare
``:class:`BucketPaths``` is ambiguous by design -- the docs build's
missing-reference resolver is what turns it into a link, and guessing at its
answer here would fight that decision. A dotted ``cadrumo.`` path is not
ambiguous: it names exactly one thing, so it either resolves or it is wrong.

**Resolution is by import, not by name matching.** An earlier version of this
scan compared leaf names against every symbol defined anywhere in the tree; it
produced both false positives (stdlib and third-party names) and, worse, false
NEGATIVES -- three real dangling references survived it because their leaf name
existed somewhere else entirely. Importing the longest importable prefix and
walking the remainder with ``getattr`` is what makes the answer exact, and it
is also the only method that respects the PEP 562 lazy facades this package
tree uses: a name reached through ``__getattr__`` is absent from the module's
source but present on the module object.
"""

from __future__ import annotations

import ast
import re
from importlib.util import find_spec, resolve_name
from pathlib import Path

import pytest

from .inventory import SRC_CADRUMO, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: The packages covered by this check.
_SCOPED_PACKAGES = (
    "adapters/persistence/storage",
    "application/user_profile",
    "entrypoints/cli/_config",
)

#: A Sphinx role naming a fully-qualified project target.
_QUALIFIED_ROLE = re.compile(r":(?:func|class|meth|data|attr|exc|mod):`~?(cadrumo\.[\w.]+)`")


def _resolves(target: str) -> bool:
    """Report whether ``target`` names something that exists.

    Walks back from the longest dotted prefix because the split between module
    path and attribute path is not knowable from the string alone:
    ``cadrumo.core.Modelo.M303`` is a module, a class and a member.
    """
    parts = target.split(".")
    for cut in range(len(parts), 0, -1):
        module = ".".join(parts[:cut])
        source = _module_source(module)
        if source is None:
            continue
        return _source_path_resolves(source, module, parts[cut:])
    return False


def _module_source(module: str) -> Path | None:
    """Return a module's source path through import metadata only."""
    try:
        spec = find_spec(module)
    except (ImportError, ModuleNotFoundError, ValueError):
        return None
    origin = None if spec is None else spec.origin
    if origin is None or origin in {"built-in", "frozen"}:
        return None
    path = Path(origin)
    return path if path.is_file() else None


def _literal_string(node: ast.AST) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _lazy_target(tree: ast.Module, name: str) -> tuple[str, str | None] | None:
    """Read the source mapping used by a module-level ``__getattr__`` hook."""
    has_getattr = any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "__getattr__" for node in tree.body
    )
    if not has_getattr:
        return None
    for node in tree.body:
        value = node.value if isinstance(node, ast.Assign) else node.value if isinstance(node, ast.AnnAssign) else None
        if not isinstance(value, ast.Dict):
            continue
        for key, item in zip(value.keys, value.values, strict=False):
            if _literal_string(key) != name:
                continue
            if isinstance(item, (ast.Tuple, ast.List)) and item.elts:
                module = _literal_string(item.elts[0])
                symbol = _literal_string(item.elts[1]) if len(item.elts) > 1 else None
            else:
                module, symbol = _literal_string(item), None
            if module is not None:
                return module, symbol
    return None


def _source_path_resolves(path: Path, module: str, attrs: list[str]) -> bool:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError):
        return False
    owner: ast.AST = tree
    for index, attr in enumerate(attrs):
        candidates = [node for node in ast.iter_child_nodes(owner) if getattr(node, "name", None) == attr]
        if not candidates:
            candidates = [
                node
                for node in ast.walk(owner)
                if isinstance(node, (ast.Import, ast.ImportFrom))
                and any((alias.asname or alias.name.split(".", 1)[0]) == attr for alias in node.names)
            ]
        if not candidates:
            lazy = _lazy_target(tree, attr) if owner is tree else None
            if lazy is None:
                return False
            target_module, target_name = lazy
            if target_module.startswith("."):
                package = module if path.name == "__init__.py" else module.rpartition(".")[0]
                target_module = resolve_name(target_module, package)
            target = ".".join(part for part in (target_module, target_name, *attrs[index + 1 :]) if part)
            return _resolves(target)
        owner = candidates[0]
    return True


def _references() -> list[tuple[str, int, str]]:
    """Return every ``(path, line, target)`` in the scoped packages."""
    found: list[tuple[str, int, str]] = []
    for package in _SCOPED_PACKAGES:
        for path in (SRC_CADRUMO / package).rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="replace")
            for match in _QUALIFIED_ROLE.finditer(text):
                line = text[: match.start()].count("\n") + 1
                found.append((repo_relative(path), line, match.group(1)))
    return found


def test_no_qualified_reference_names_something_that_does_not_exist() -> None:
    """DISCRIMINATING: a confident name is trusted more than an absence would be."""
    dangling = [f"{path}:{line}: {target}" for path, line, target in _references() if not _resolves(target)]

    assert not dangling, (
        "these docstrings name a fully-qualified target that does not resolve:\n  "
        + "\n  ".join(sorted(dangling))
        + "\n\nEither the artifact moved -- point the reference at where it lives now -- or it "
        "was deleted, in which case say so rather than leaving its name standing. If the "
        "symbol SHOULD be reachable at the cited path, export it there; that is the fix the "
        "citation was already assuming."
    )


def test_the_scan_reaches_a_real_population() -> None:
    """ANTI-VACUITY: an empty reference list would clear every package for free.

    The gate's whole content is that the list resolves. A regex that matched
    nothing -- a role spelling change, a package move -- would report a clean
    tree forever.
    """
    references = _references()

    assert len(references) > 100, f"expected the scoped packages to carry many references, got {len(references)}"
    assert len({path for path, _, _ in references}) > 20


def test_the_resolver_reports_a_missing_target() -> None:
    """ANTI-TAUTOLOGY: the resolver must be able to say no.

    A resolver that returned ``True`` unconditionally -- an over-broad
    ``except``, say -- would satisfy the assertion above against any tree.
    """
    assert _resolves("cadrumo.application.user_profile.ProfileCapsuleLifecycle.edit_fields") is False
    assert _resolves("cadrumo.domain.submission.SubmissionRepository") is False
    assert _resolves("cadrumo.this.module.does.not.exist") is False


def test_the_resolver_counts_a_pydantic_field_as_present() -> None:
    """A model field is declared, not attributed, and must not read as dangling.

    ``getattr(Invoice, "operation_date")`` is nothing in pydantic v2 -- the
    field lives in ``model_fields``. Without this the gate would report every
    correct ``:attr:`Model.field``` reference in the tree as stale, and the
    honest response to that would be to delete the gate.
    """
    assert _resolves("cadrumo.domain.invoices.Invoice.operation_date") is True
    assert _resolves("cadrumo.domain.invoices.Invoice.no_such_field_at_all") is False


def test_the_resolver_accepts_real_targets_including_lazy_ones() -> None:
    """The other direction, and the reason resolution is by import.

    ``CommittedProfileView`` is reached through the package's PEP 562
    ``__getattr__``: it is absent from the facade's own source text, so any
    scan reading source rather than importing would call it dangling and be
    wrong.
    """
    assert _resolves("cadrumo.application.user_profile.CommittedProfileView") is True
    assert _resolves("cadrumo.application.user_profile.apply_profile_fact_changes") is True
    assert _resolves("cadrumo.core") is True
