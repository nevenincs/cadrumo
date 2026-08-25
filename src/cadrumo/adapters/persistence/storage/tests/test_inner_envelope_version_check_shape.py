"""Structural gate: no persisted read path compares an inner envelope version with an inequality.

The inner-``Envelope`` contract is strict EQUALITY, held by
:func:`.._schema_lineage.inner_envelope_version_is_current`. An inequality
there accepts a below-current inner stamp silently, and a below-current inner
stamp is exactly what a half-written upgrader produces on a row the outer
layer has already re-stamped to current. Twenty read paths had drifted onto
the loose form before this gate existed; it is here so they cannot drift back.

**This gate resolves what a name IS, not how it is spelled.** Two structural
gates in this repository once reported green over live violations because each
matched a literal spelling, so any import alias walked straight past. The
detector below therefore resolves each module's own import bindings — absolute
*and* relative, aliased or not — before deciding whether a module reads the
storage ``Envelope`` at all, and tracks which local names hold an envelope
through those same bindings.

Alias resolution must never NARROW what a gate governs, so the bare
conventional handle name is seeded unconditionally
(:data:`_SEEDED_ENVELOPE_HANDLE_NAMES`). That seed is load-bearing rather than
belt-and-braces: ``application/live/snapshot_base.py`` builds its envelope
through ``self._envelope_cls()``, whose base name is ``self``, so binding
resolution alone cannot see it and the seed is what actually covers that site.

Two shapes no AST pass can see, stated here rather than left as an implied
guarantee: a comparison assembled at runtime (``operator.gt`` looked up from a
table, or a version fetched through ``getattr(envelope, name)``), and a handle
that reaches an envelope through a call this module cannot resolve to an
origin *and* is not spelled with a seeded name. Neither shape exists in the
tree today; both would evade this gate if introduced.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from .....tests import module_name, production_python_files, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_ENVELOPE_ORIGINS = frozenset(
    {
        "cadrumo.adapters.persistence.storage.Envelope",
        "cadrumo.adapters.persistence.storage.envelope.Envelope",
        "cadrumo.adapters.persistence.storage.envelope._envelope.Envelope",
    }
)
"""Every absolute origin that names the persisted inner-envelope class."""

_ENVELOPE_LOADER_ORIGINS = frozenset(
    {
        "cadrumo.adapters.persistence.storage.load_envelope",
        "cadrumo.adapters.persistence.storage.load_encrypted_envelope",
        "cadrumo.adapters.persistence.storage.envelope.load_envelope",
        "cadrumo.adapters.persistence.storage.envelope.load_encrypted_envelope",
    }
)
"""Loaders that return an ``Envelope``, so their result is an envelope handle."""

_SEEDED_ENVELOPE_HANDLE_NAMES = frozenset({"envelope"})
"""Handle names always treated as an envelope, so alias awareness cannot narrow the gate."""

_VERSION_ATTRIBUTE = "schema_version"

_ORDERING_OPERATORS = (ast.Lt, ast.LtE, ast.Gt, ast.GtE)


def _package_of(module_dotted: str, *, is_package: bool) -> list[str]:
    """Return the dotted parts of the package that owns ``module_dotted``."""
    parts = module_dotted.split(".")
    return parts if is_package else parts[:-1]


def _absolute_import_from(module_dotted: str, *, is_package: bool, node: ast.ImportFrom) -> str | None:
    """Return the absolute module an ``ImportFrom`` names, resolving relative levels.

    ``import_binding_map`` in the shared inventory deliberately skips relative
    imports because a single-tree walk cannot know the importing module's
    package position. This gate DOES know it, so it resolves them: every one of
    the twenty read paths this gate governs imports the envelope relatively, and
    a gate blind to relative imports would govern nothing at all.
    """
    if not node.level:
        return node.module
    package_parts = _package_of(module_dotted, is_package=is_package)
    if node.level - 1 > len(package_parts):
        return None
    base = package_parts[: len(package_parts) - (node.level - 1)]
    if node.module:
        base = [*base, *node.module.split(".")]
    return ".".join(base) if base else None


_ENVELOPE_SYMBOL = "Envelope"
"""Trailing symbol every governed origin ends in, used to screen before parsing."""


def _binds_an_envelope_origin(path: Path) -> bool:
    """Whether *path* binds one of the governed envelope origins.

    Screens on the symbol before parsing. Every origin in
    :data:`_ENVELOPE_ORIGINS` ends in ``Envelope``, so a module that binds one
    must spell that name; a module that never does cannot be governed and need
    not be parsed. The parse still decides which modules ARE governed -- a
    docstring mentioning the word is not a binding -- so this only chooses what
    is worth parsing.
    """
    source = path.read_text(encoding="utf-8", errors="replace")
    if _ENVELOPE_SYMBOL not in source:
        return False
    bindings = _origin_bindings(ast.parse(source), module_name(path), is_package=path.name == "__init__.py")
    return any(origin in _ENVELOPE_ORIGINS for origin in bindings.values())


def _origin_bindings(tree: ast.AST, module_dotted: str, *, is_package: bool) -> dict[str, str]:
    """Return local name -> absolute origin for every import binding in ``tree``.

    Covers module-level and function-local imports alike, since the read paths
    this gate governs import the envelope inside the reading function.
    """
    bindings: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                bindings[alias.asname or alias.name.split(".", 1)[0]] = alias.name
        elif isinstance(node, ast.ImportFrom):
            module = _absolute_import_from(module_dotted, is_package=is_package, node=node)
            if module is None:
                continue
            for alias in node.names:
                bindings[alias.asname or alias.name] = f"{module}.{alias.name}"
    return bindings


def _base_name(node: ast.AST) -> str | None:
    """Return the root ``Name`` of a call/attribute/subscript chain.

    ``Envelope[Payload].model_validate_json(raw)`` and its aliased twin
    ``_Env[Payload].model_validate_json(raw)`` both reduce to their root handle,
    which is what makes the two spellings collapse onto one comparable origin.
    """
    current = node
    while True:
        if isinstance(current, ast.Call):
            current = current.func
        elif isinstance(current, ast.Attribute | ast.Subscript):
            current = current.value
        elif isinstance(current, ast.Name):
            return current.id
        else:
            return None


def _envelope_handles(tree: ast.AST, bindings: dict[str, str]) -> set[str]:
    """Return local names holding an inner envelope, resolved through ``bindings``."""
    handles = set(_SEEDED_ENVELOPE_HANDLE_NAMES)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        else:
            continue
        root = _base_name(value)
        if root is None:
            continue
        origin = bindings.get(root)
        if origin not in _ENVELOPE_ORIGINS and origin not in _ENVELOPE_LOADER_ORIGINS:
            continue
        handles.update(target.id for target in targets if isinstance(target, ast.Name))
    return handles


def _is_envelope_version_read(node: ast.AST, handles: set[str]) -> bool:
    """Return whether ``node`` reads ``schema_version`` off a known envelope handle."""
    if not isinstance(node, ast.Attribute) or node.attr != _VERSION_ATTRIBUTE:
        return False
    return isinstance(node.value, ast.Name) and node.value.id in handles


def inner_envelope_inequality_violations(source: str, module_dotted: str, *, is_package: bool = False) -> list[int]:
    """Return line numbers where ``source`` orders an inner envelope's version.

    A pure function over source text so the controls below can feed it a
    planted violation directly — including one in the aliased form that
    spelling-matched gates miss — rather than asserting an empty list against a
    clean tree and calling that a passing gate.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    bindings = _origin_bindings(tree, module_dotted, is_package=is_package)
    if not any(origin in _ENVELOPE_ORIGINS for origin in bindings.values()):
        return []
    handles = _envelope_handles(tree, bindings)
    violations: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        if not any(isinstance(op, _ORDERING_OPERATORS) for op in node.ops):
            continue
        operands = [node.left, *node.comparators]
        if any(_is_envelope_version_read(operand, handles) for operand in operands):
            violations.append(node.lineno)
    return sorted(violations)


def _violations_for(path: Path) -> list[int]:
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return inner_envelope_inequality_violations(
        source,
        module_name(path),
        is_package=path.name == "__init__.py",
    )


def test_no_production_read_path_orders_an_inner_envelope_version() -> None:
    """The live tree carries no inequality comparison of an inner envelope version."""
    offenders = [
        f"{repo_relative(path)}:{lineno}" for path in production_python_files() for lineno in _violations_for(path)
    ]
    assert offenders == [], (
        "persisted inner-envelope read paths must compare schema_version for EQUALITY via "
        "inner_envelope_version_is_current, not with an inequality: an inequality accepts a "
        f"below-current inner stamp silently, which is what a half-written upgrader writes; offenders: {offenders}"
    )


_PRE_CHANGE_SPELLING = """
from ..storage import Envelope, EnvelopeVersionError

_CATALOGUE_VERSION = 1

def load(record):
    envelope = Envelope[Payload].model_validate_json(record.payload.decode("utf-8"))
    if envelope.schema_version > _CATALOGUE_VERSION:
        raise EnvelopeVersionError("too new")
    return envelope.payload
"""

_ALIASED_EVASION = """
from ..storage import Envelope as _Env, EnvelopeVersionError

_CATALOGUE_VERSION = 1

def load(record):
    stored = _Env[Payload].model_validate_json(record.payload.decode("utf-8"))
    if stored.schema_version > _CATALOGUE_VERSION:
        raise EnvelopeVersionError("too new")
    return stored.payload
"""

_REVERSED_COMPARISON = """
from ..storage import Envelope, EnvelopeVersionError

_CATALOGUE_VERSION = 1

def load(record):
    envelope = Envelope[Payload].model_validate_json(record.payload.decode("utf-8"))
    if _CATALOGUE_VERSION < envelope.schema_version:
        raise EnvelopeVersionError("too new")
    return envelope.payload
"""

_COMPLIANT_EQUALITY = """
from ..storage import Envelope, EnvelopeVersionError, inner_envelope_version_is_current

_CATALOGUE_VERSION = 1

def load(record):
    envelope = Envelope[Payload].model_validate_json(record.payload.decode("utf-8"))
    if not inner_envelope_version_is_current(envelope.schema_version, _CATALOGUE_VERSION):
        raise EnvelopeVersionError("not current")
    return envelope.payload
"""

_OUTER_ROW_UPGRADE_PATH = """
from ..storage import Envelope
from .._schema_lineage import upgrade_secure_object_payload

def decode(row, max_supported_version):
    envelope = Envelope
    if row.schema_version < max_supported_version:
        return upgrade_secure_object_payload(row.payload)
    return row.payload
"""

_LAYER_ONE_GATE = """
from .errors import EnvelopeVersionError

def ensure_schema_version_readable(*, schema_version, current_version):
    if schema_version > current_version:
        raise EnvelopeVersionError("from future")
"""

_CONSUMER_MODULE = "cadrumo.adapters.persistence.profile.catalogue"


def test_detector_flags_the_exact_pre_change_spelling() -> None:
    """Positive control: the shape all twenty read paths carried before the sweep."""
    assert inner_envelope_inequality_violations(_PRE_CHANGE_SPELLING, _CONSUMER_MODULE) == [8]


def test_detector_flags_an_aliased_envelope_handle() -> None:
    """Positive control: the alias form that walks past a spelling-matched gate.

    Neither the import name nor the handle name is spelled conventionally here,
    so only binding resolution can reach this violation.
    """
    assert inner_envelope_inequality_violations(_ALIASED_EVASION, _CONSUMER_MODULE) == [8]


def test_detector_flags_a_reversed_comparison() -> None:
    """Positive control: the constant on the left is the same defect."""
    assert inner_envelope_inequality_violations(_REVERSED_COMPARISON, _CONSUMER_MODULE) == [8]


def test_detector_ignores_the_compliant_equality_form() -> None:
    """Negative control: the shape the sweep landed must not be flagged."""
    assert inner_envelope_inequality_violations(_COMPLIANT_EQUALITY, _CONSUMER_MODULE) == []


def test_detector_ignores_an_ordering_compare_on_a_non_envelope_receiver() -> None:
    """Near-miss negative control: the outer-row below-current upgrade branch.

    ``row.schema_version < max_supported_version`` in the row codec is layer
    one deciding whether to chain-upgrade, and is correct. A gate that keyed on
    the attribute name alone would red it, in a module that does bind
    ``Envelope``.
    """
    assert inner_envelope_inequality_violations(_OUTER_ROW_UPGRADE_PATH, _CONSUMER_MODULE) == []


def test_detector_ignores_a_module_that_does_not_read_the_inner_envelope() -> None:
    """Near-miss negative control: the layer-one ceiling is a deliberate inequality."""
    assert (
        inner_envelope_inequality_violations(
            _LAYER_ONE_GATE,
            "cadrumo.adapters.persistence.storage._schema_lineage",
        )
        == []
    )


def test_relative_import_levels_resolve_to_the_real_storage_package() -> None:
    """The twenty governed read paths all import the envelope relatively.

    Pinned directly because a resolver that silently returned ``None`` here
    would make :func:`inner_envelope_inequality_violations` return an empty
    list for every real module — a gate that governs nothing while reporting
    green, which is the failure class this whole gate exists to refuse.
    """
    node = ast.parse("from ..storage import Envelope").body[0]
    assert isinstance(node, ast.ImportFrom)
    resolved = _absolute_import_from(
        "cadrumo.adapters.persistence.profile.usage_ratios",
        is_package=False,
        node=node,
    )
    assert resolved == "cadrumo.adapters.persistence.storage"


def test_the_governed_surface_is_not_empty() -> None:
    """At least the swept read paths must actually be in scope.

    The gate's clean result is only evidence if the scan reaches the modules it
    is meant to govern. This asserts the module filter admits real read paths
    rather than excluding everything and passing vacuously.
    """
    governed = [path for path in production_python_files() if _binds_an_envelope_origin(path)]
    names = {path.name for path in governed}
    # ``_observation_store.py`` was in this set until its four hand-rolled
    # envelope reads moved onto SecureBoundRepository; the kernel that now
    # performs that check for it — ``_secure_enveloped_document.py`` — takes its
    # place here, so the sede observation reads stay represented in the scope
    # anchor rather than dropping out of it unnoticed.
    # ``_snapshot_base.py`` was in this set until ``SecureSnapshotRepository``
    # (the class carrying the ``Envelope`` / ``EnvelopeVersionError`` reads)
    # relocated to the persistence adapter as
    # ``adapters.persistence.profile.snapshots.SecureSnapshotRepository``;
    # ``snapshots.py`` takes its place here so the live-snapshot envelope
    # reads stay represented in the scope anchor.
    assert {
        "usage_ratios.py",
        "transactions.py",
        "_secure_enveloped_document.py",
        "snapshots.py",
    } <= names, f"gate scope lost real read paths; governed modules found: {sorted(names)}"
