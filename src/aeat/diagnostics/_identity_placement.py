"""AST-walking helpers for the typed-id placement enforcement test.

The helpers parse every Python module under :mod:`aeat` with the
standard-library :mod:`ast` module and surface structural violations of
the typed-id alias placement rule. Discovery is text-only: the helper
never imports application, domain, adapter, or entrypoint code so the
test surface cannot pull side effects from the modules it inspects.

The detectors expose four checks, one per clause of the placement rule:

* :func:`find_sibling_domain_id_imports` — a ``domain.<a>`` module
  importing a name from ``domain.<b>._ids`` for ``a != b`` other than the
  registry-aliases exception.
* :func:`find_private_id_imports` — an adapter, application, or
  entrypoint module importing a leading-underscore name from any
  ``_ids.py`` module.
* :func:`find_misplaced_hex_length_constants` — an ``_HEX_*_LENGTH``
  module-level constant declared outside the owning ``_ids.py``.
* :func:`find_bare_str_typed_id_fields` — a pydantic-``BaseModel``
  subclass declaring a ``<owner>_id`` field as bare ``str`` (or
  ``str | None``) when a typed alias for that owner exists in the
  alias inventory.

Every detector returns a list of :class:`Finding` records; the test
surface asserts the list is empty. The detectors do not raise on
malformed source: a parse error becomes a finding so the test surface
reports a precise location rather than aborting at collection.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

__all__ = (
    "AEAT_ROOT",
    "AliasInventory",
    "Finding",
    "build_alias_inventory",
    "find_bare_str_typed_id_fields",
    "find_misplaced_hex_length_constants",
    "find_private_id_imports",
    "find_sibling_domain_id_imports",
    "iter_aeat_modules",
)

_CONSUMER_LAYER_ROOTS = ("aeat.adapters", "aeat.application", "aeat.entrypoints")

AEAT_ROOT = Path(__file__).resolve().parent.parent
"""Filesystem root of the :mod:`aeat` package (``src/aeat``)."""

_SKIP_DIR_NAMES = frozenset({"__pycache__", ".pytest_cache", ".mypy_cache"})

_HEX_LENGTH_CONSTANT_RE = re.compile(r"^_HEX_[A-Z0-9_]+_LENGTH$")


@dataclass(frozen=True)
class Finding:
    """One structural violation surfaced by an AST-walking detector."""

    path: Path
    line: int
    message: str

    def render(self) -> str:
        try:
            rel = self.path.relative_to(AEAT_ROOT.parent)
        except ValueError:
            rel = self.path
        return f"{rel.as_posix()}:{self.line}: {self.message}"


@dataclass(frozen=True)
class AliasInventory:
    """Discovered typed-id alias inventory.

    ``aliases_by_owner`` maps the snake-case owner prefix (e.g.
    ``work_unit`` for ``WorkUnitId``) to the alias name. The mapping is
    used by the bare-string field detector to decide whether a
    ``<owner>_id`` field on a pydantic model has a typed alias it could
    consume instead of bare ``str``.

    ``alias_modules`` is the set of module dotted paths where any typed
    alias was discovered; the private-name import detector consults this
    set to recognise an ``_ids.py``-equivalent re-export module such as
    ``aeat.core.identity``.
    """

    aliases_by_owner: dict[str, str]
    alias_modules: frozenset[str]


def iter_aeat_modules(root: Path = AEAT_ROOT) -> Iterator[Path]:
    """Yield every ``.py`` file under ``root`` excluding cache dirs."""

    for path in root.rglob("*.py"):
        if any(part in _SKIP_DIR_NAMES for part in path.parts):
            continue
        yield path


def _module_dotted_path(path: Path) -> str:
    """Return the ``aeat.<...>`` dotted path for ``path``."""

    rel = path.relative_to(AEAT_ROOT.parent).with_suffix("")
    parts = list(rel.parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _parse(path: Path) -> tuple[ast.Module | None, Finding | None]:
    """Parse ``path`` into an AST, returning a finding on syntax error."""

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - filesystem error
        return None, Finding(path, 0, f"unreadable source: {exc}")
    try:
        return ast.parse(text, filename=str(path)), None
    except SyntaxError as exc:
        return None, Finding(path, exc.lineno or 0, f"syntax error: {exc.msg}")


def _camel_to_snake(name: str) -> str:
    """Convert a CamelCase identifier to ``snake_case``."""

    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _module_alias_names(tree: ast.Module) -> list[str]:
    """Return module-level identifiers that name a typed-id alias.

    A typed alias may appear as a bare ``Assign`` (``WorkUnitId =
    Annotated[...]``), an ``AnnAssign`` with a type annotation, a PEP 695
    ``TypeAlias`` statement (``type CasillaId = Annotated[...]``), or as
    an ``ImportFrom`` re-export (``from ._bucket import BucketId``).
    The detector accepts any module-level name ending in ``Id`` whose
    first character is uppercase, mirroring the ADR Rule 4 naming
    convention.
    """

    names: list[str] = []
    for node in tree.body:
        candidates: list[str] = []
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    candidates.append(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            candidates.append(node.target.id)
        elif isinstance(node, ast.TypeAlias) and isinstance(node.name, ast.Name):
            candidates.append(node.name.id)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imported = alias.asname or alias.name
                candidates.append(imported)
        for candidate in candidates:
            if (
                candidate.endswith("Id")
                and candidate[:1].isupper()
                and not candidate.startswith("_")
            ):
                names.append(candidate)
    return names


def _is_alias_module(path: Path) -> bool:
    """Return whether ``path`` is the alias-declaring module for a package.

    The ADR pattern places typed aliases in ``_ids.py``. The
    :mod:`aeat.core.identity` package aggregates aliases through its
    package ``__init__`` (re-exporting from ``_bucket.py``,
    ``_profile.py``, ``_snapshot.py``), so a package ``__init__`` that
    re-exports typed aliases is also recognised.
    """

    name = path.name
    if name == "_ids.py":
        return True
    if name == "__init__.py" and path.parent.name == "identity":
        return True
    return False


def build_alias_inventory(root: Path = AEAT_ROOT) -> AliasInventory:
    """Discover typed-id aliases declared under ``root``."""

    by_owner: dict[str, str] = {}
    alias_modules: set[str] = set()
    for path in iter_aeat_modules(root):
        if not _is_alias_module(path):
            continue
        tree, _err = _parse(path)
        if tree is None:
            continue
        names = _module_alias_names(tree)
        if not names:
            continue
        alias_modules.add(_module_dotted_path(path))
        for alias in names:
            owner = _camel_to_snake(alias[:-2])  # strip trailing ``Id``
            by_owner.setdefault(owner, alias)
    return AliasInventory(
        aliases_by_owner=dict(sorted(by_owner.items())),
        alias_modules=frozenset(alias_modules),
    )


# --- Clause 1: sibling-domain ``_ids`` import -----------------------------


_REGISTRY_IDS_MODULE = "aeat.domain.calculations.registry._ids"


def _domain_root(dotted: str) -> str | None:
    """Return the ``domain.<root>`` segment for ``dotted`` if any."""

    parts = dotted.split(".")
    if len(parts) >= 3 and parts[0] == "aeat" and parts[1] == "domain":
        return parts[2]
    return None


def _resolve_relative_import(consumer: str, module: str | None, level: int) -> str | None:
    """Resolve a ``from .x import y`` style module to an absolute path."""

    if level == 0:
        return module
    consumer_parts = consumer.split(".")
    if level > len(consumer_parts):
        return None
    base = consumer_parts[:-level]
    if module:
        base.extend(module.split("."))
    return ".".join(base) if base else None


def _iter_import_from(tree: ast.Module) -> Iterator[ast.ImportFrom]:
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            yield node


def find_sibling_domain_id_imports(root: Path = AEAT_ROOT) -> list[Finding]:
    """Detect ``domain.<a>`` importing from ``domain.<b>._ids`` for ``a != b``."""

    findings: list[Finding] = []
    for path in iter_aeat_modules(root):
        dotted = _module_dotted_path(path)
        consumer_domain = _domain_root(dotted)
        if consumer_domain is None:
            continue
        tree, err = _parse(path)
        if err is not None:
            findings.append(err)
            continue
        assert tree is not None
        for node in _iter_import_from(tree):
            target = _resolve_relative_import(dotted, node.module, node.level)
            if target is None:
                continue
            if target == _REGISTRY_IDS_MODULE:
                continue
            target_domain = _domain_root(target)
            if target_domain is None or target_domain == consumer_domain:
                continue
            if not (target.endswith("._ids") or target.split(".")[-1] == "_ids"):
                continue
            imported = ", ".join(alias.name for alias in node.names)
            findings.append(
                Finding(
                    path,
                    node.lineno,
                    (
                        f"sibling-domain _ids import: aeat.domain.{consumer_domain} "
                        f"imports {imported!r} from {target}"
                    ),
                )
            )
    return findings


# --- Clause 2: private-name import from any ``_ids.py`` -------------------


def _is_consumer_layer(dotted: str) -> bool:
    return any(dotted == root or dotted.startswith(root + ".") for root in _CONSUMER_LAYER_ROOTS)


def find_private_id_imports(root: Path = AEAT_ROOT) -> list[Finding]:
    """Detect leading-underscore imports from any ``_ids.py`` module.

    An adapter, application, or entrypoint module may consume the public
    typed-id aliases exported by an ``_ids.py`` module. It MUST NOT
    reach into the underlying regex constants, length constants, or
    private re-aliases that the ``_ids.py`` module uses to construct
    them. The public alias names are the cross-layer contract; the
    private constants are an implementation detail.
    """

    findings: list[Finding] = []
    for path in iter_aeat_modules(root):
        dotted = _module_dotted_path(path)
        if not _is_consumer_layer(dotted):
            continue
        tree, err = _parse(path)
        if err is not None:
            findings.append(err)
            continue
        assert tree is not None
        for node in _iter_import_from(tree):
            target = _resolve_relative_import(dotted, node.module, node.level)
            if target is None:
                continue
            if not target.endswith("._ids"):
                continue
            for alias in node.names:
                if alias.name.startswith("_"):
                    findings.append(
                        Finding(
                            path,
                            node.lineno,
                            (
                                f"private-name import from {target}: {alias.name!r} "
                                f"is an internal constant; consume the public alias instead"
                            ),
                        )
                    )
    return findings


# --- Clause 3: ``_HEX_*_LENGTH`` constant outside owning ``_ids.py`` ------


def _iter_module_assignments(tree: ast.Module) -> Iterator[tuple[str, int]]:
    """Yield ``(name, lineno)`` for every module-level name assignment."""

    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    yield target.id, node.lineno
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            yield node.target.id, node.lineno


def find_misplaced_hex_length_constants(root: Path = AEAT_ROOT) -> list[Finding]:
    """Detect ``_HEX_*_LENGTH`` constants declared outside an ``_ids.py``."""

    findings: list[Finding] = []
    for path in iter_aeat_modules(root):
        if path.name == "_ids.py":
            continue
        tree, err = _parse(path)
        if err is not None:
            findings.append(err)
            continue
        assert tree is not None
        for name, lineno in _iter_module_assignments(tree):
            if _HEX_LENGTH_CONSTANT_RE.match(name):
                findings.append(
                    Finding(
                        path,
                        lineno,
                        (
                            f"misplaced shape constant {name!r}: hex-length constants "
                            f"belong only in the owning _ids.py module"
                        ),
                    )
                )
    return findings
