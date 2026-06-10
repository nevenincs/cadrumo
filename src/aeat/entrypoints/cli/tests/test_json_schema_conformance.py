"""Conformance gate for the CLI ``--json`` envelope contract.

Every leaf command exposed by the ``aeat`` CLI MUST emit its result
through :class:`SchemaEnvelope`, which means its payload model MUST
be registered under a stable command-path string in
:data:`SCHEMA_REGISTRY` via :func:`register_schema`.

This module enumerates the Typer command tree, derives the canonical
command-path string for every leaf, and asserts an exact match against
the registered schema keys. There is no allowlist: a leaf without a
schema fails the gate, and a registry key without a matching leaf
fails the gate. Either side surfaces a structural regression that
must be fixed before the suite goes green.
"""

from __future__ import annotations

from typing import TypeGuard, cast

import click
import pytest
import typer
from typer.main import get_command as _typer_get_command

from ....core.json_contract import SCHEMA_REGISTRY, SchemaEnvelope

# Import the per-package payload modules so their @register_schema
# decorators populate SCHEMA_REGISTRY before the gate inspects it.
# The CLI loads these lazily at dispatch time, so without an explicit
# import here the registry is empty when this test module collects.
from .. import _config_payloads as _config_payloads

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

# ---------------------------------------------------------------------
# Canonical command-path normalisation
# ---------------------------------------------------------------------
#
# A leaf-command Typer path is a tuple of group/command names walked
# from the ``aeat`` root, e.g. ``("aeat", "app", "modelo", "work",
# "calculate")``. Registry keys are dot-joined strings without the
# ``aeat`` root, e.g. ``"modelo.work.calculate"``.
#
# Most registry keys also drop the ``app`` group segment that owns the
# operational subtrees (``modelo``, ``ledger``, ``review``, ...). The
# ``app.live.*`` family keeps its ``app.`` prefix because the live
# observation surface is itself addressable as a contract namespace.
# Root-level meta commands register under ``root.*``.
#
# The normaliser below applies the same rule the live ``_emit_envelope``
# call sites use:
#
#  * Strip the leading ``aeat`` token.
#  * Replace dashes with underscores so Typer command names with hyphens
#    (e.g. ``iva-wallet``) align with the registry key
#    (``iva_wallet``).
#  * Dot-join the remainder.
#  * Strip a leading ``app.`` for subtrees that operate as standalone
#    contract namespaces (``ledger``, ``modelo``, ``overview``,
#    ``registry``, ``review``).
#  * Keep the ``app.`` prefix for ``app.live.*`` because that surface
#    registers under the prefixed form.
#
# When a future subtree disagrees with this rule, the registry key and
# the normalised CLI path will diverge and the gate will surface both
# sides in its failure diagnostic.

_APP_NAMESPACE_PASSTHROUGH = frozenset({"live"})
_APP_NAMESPACE_FLATTEN = frozenset({"ledger", "modelo", "overview", "registry", "review"})


def _normalise_command_path(path: tuple[str, ...]) -> str:
    """Project a Typer leaf-command path onto the registry key convention."""
    tokens = [token.replace("-", "_") for token in path]
    if tokens and tokens[0] == "aeat":
        tokens = tokens[1:]
    if len(tokens) >= 2 and tokens[0] == "app":
        head = tokens[1]
        if head in _APP_NAMESPACE_FLATTEN:
            tokens = tokens[1:]
        elif head in _APP_NAMESPACE_PASSTHROUGH:
            pass  # keep ``app.`` prefix
    return ".".join(tokens)


# ---------------------------------------------------------------------
# Typer-tree walking
# ---------------------------------------------------------------------


def _force_load_lazy_subcommands(app: typer.Typer) -> None:
    """Materialise every lazily-registered subcommand on ``app`` and its descendants.

    The CLI registers heavy subtrees via :func:`register_lazy_subcommand`
    to keep ``aeat --version`` / ``aeat --help`` off the registry-parse
    path. The lazy entries live in a process-global table keyed by group
    name and are only imported when an operator dispatches into them.
    The conformance gate needs the full tree available at collection
    time, so we walk every materialised group and force-load every lazy
    entry registered under its name.
    """
    from .._command_suggestions import _LAZY_REGISTRY

    seen: set[int] = set()
    pending: list[typer.Typer] = [app]
    while pending:
        node = pending.pop()
        if id(node) in seen:
            continue
        seen.add(id(node))
        group_name = node.info.name or ""
        for lazy in _LAZY_REGISTRY.get(group_name, {}).values():
            lazy.load()
        for group in node.registered_groups:
            if group.typer_instance is not None:
                pending.append(group.typer_instance)


def _is_command_group(command: click.Command) -> TypeGuard[click.Group]:
    """Return True when ``command`` is a Click group / multi-command.

    Typer vendors its own Click (``typer._click``), so commands returned by
    ``typer.main.get_command`` are NOT instances of the top-level ``click.Group``
    this module imports — an ``isinstance(command, click.Group)`` check silently
    fails for every group and collapses the walk to the root leaf. Duck-typing on
    the group interface (``list_commands`` + ``get_command``) is version- and
    vendor-robust. The ``TypeGuard`` narrows the structurally-identical vendored
    group to ``click.Group`` so the group-only ``list_commands`` / ``get_command``
    accesses below type-check.
    """
    return callable(getattr(command, "list_commands", None)) and callable(getattr(command, "get_command", None))


def _click_leaf_paths(command: click.Command, prefix: tuple[str, ...]) -> set[tuple[str, ...]]:
    """Return the set of leaf-command paths reachable from ``command``."""
    leaves: set[tuple[str, ...]] = set()
    name = command.name or ""
    path = (*prefix, name) if name else prefix
    if _is_command_group(command):
        # Materialise the synthetic root context so AeatTyperGroup's
        # lazy ``get_command`` resolves every registered subcommand,
        # including those that live behind a LazySubcommand loader.
        with click.Context(command, info_name=name or None) as ctx:
            for child_name in command.list_commands(ctx):
                child = command.get_command(ctx, child_name)
                if child is None:
                    continue
                leaves.update(_click_leaf_paths(child, path))
    else:
        leaves.add(path)
    return leaves


# ---------------------------------------------------------------------
# Group-callback emit sites
# ---------------------------------------------------------------------
#
# A handful of group callbacks legitimately emit a typed envelope when
# invoked with no subcommand (or with ``--help``). These are NOT leaf
# commands and so :func:`_click_leaf_paths` cannot reach them, but they
# are real emission sites with stable schemas registered in the
# registry. They are enumerated here so the conformance gate models the
# walker's reach accurately:
#
#  * ``aeat`` (root callback) emits ``root.status`` for the landing /
#    help surface.
#  * ``aeat app`` (group callback) emits ``root.app`` for the
#    ``aeat app`` landing / help surface.
#
# When a future group callback adds an envelope emit, register its key
# here so the gate continues to model the actual reach of the CLI tree.
_GROUP_CALLBACK_EMIT_KEYS: frozenset[str] = frozenset(
    {
        "root.status",
        "root.app",
    }
)


def _walk_cli_command_paths(app: typer.Typer) -> set[str]:
    """Enumerate every registered envelope key reachable from ``app``.

    Forces every lazy subtree to materialise so the resulting set is
    exhaustive — no lazy import elides a leaf — then projects each
    leaf path through :func:`_normalise_command_path` to obtain the
    canonical registry-key string. Group-callback emit sites are added
    via :data:`_GROUP_CALLBACK_EMIT_KEYS` because the click leaf walk
    cannot reach a callback that does not register as a subcommand.
    """
    _force_load_lazy_subcommands(app)
    root = _typer_get_command(app)
    root.name = app.info.name or "aeat"
    # typer.main.get_command is typed to return typer's vendored
    # ``typer._click.core.Command``; it is the same click runtime object the
    # walk consumes as a top-level ``click.Command``. Bridge the vendored→real
    # nominal gap once at the boundary.
    leaf_paths = _click_leaf_paths(cast(click.Command, root), prefix=())
    keys = {_normalise_command_path(path) for path in leaf_paths}
    keys.update(_GROUP_CALLBACK_EMIT_KEYS)
    return keys


# ---------------------------------------------------------------------
# Conformance gate
# ---------------------------------------------------------------------


def _live_app() -> typer.Typer:
    from .. import app as live_app

    return live_app


def test_every_cli_leaf_has_a_registered_schema() -> None:
    """Every CLI leaf command must have a registered OutputSchema.

    The gate compares the canonicalised set of Typer leaf-command paths
    against the keys of :data:`SCHEMA_REGISTRY`. Symmetric difference
    must be empty:

    * **Unregistered leaves** — a CLI command that has no
      :func:`register_schema` decorator on its result model. These are
      the structural regressions to fix by lifting the command's emit
      site onto :class:`SchemaEnvelope`.
    * **Orphan registry keys** — a registered schema whose command-path
      does not surface as any reachable CLI leaf. These point at dead
      contract entries that must either be wired to a CLI leaf or
      removed from the registry.

    The diagnostic prints both sides so a regression run names the
    work without further investigation.
    """
    cli_paths = _walk_cli_command_paths(_live_app())
    registry_keys = set(SCHEMA_REGISTRY.keys())

    unregistered = sorted(cli_paths - registry_keys)
    orphans = sorted(registry_keys - cli_paths)

    diagnostic_lines: list[str] = []
    if unregistered:
        diagnostic_lines.append(f"CLI leaves missing a registered OutputSchema ({len(unregistered)}):")
        diagnostic_lines.extend(f"  - {path}" for path in unregistered)
    if orphans:
        diagnostic_lines.append(f"Registry keys with no matching CLI leaf ({len(orphans)}):")
        diagnostic_lines.extend(f"  - {key}" for key in orphans)

    assert not diagnostic_lines, "\n".join(diagnostic_lines)


@pytest.mark.parametrize("command_path", sorted(SCHEMA_REGISTRY.keys()))
def test_registered_schema_envelope_round_trips(command_path: str) -> None:
    """Each registered schema must specialise :class:`SchemaEnvelope` cleanly.

    Structural-shape gate, not a value gate. Per-command surface tests
    own end-to-end emit -> bytes -> envelope round-trips; this gate
    verifies that the registered schema is a valid envelope result
    type at construction time.
    """
    schema = SCHEMA_REGISTRY[command_path]
    # Subscripting the generic with a runtime variable is exactly what this gate
    # exercises (the registry maps each command to its schema at runtime); both
    # checkers reject a runtime value in a type-subscript position.
    envelope_cls = SchemaEnvelope[schema]  # type: ignore[valid-type]  # ty: ignore[invalid-type-form]
    assert envelope_cls.__pydantic_generic_metadata__["args"] == (schema,)


# ---------------------------------------------------------------------
# Zero-bare-emit gate for the envelope-schema contract.
# ---------------------------------------------------------------------

# Production CLI sites that legitimately emit through the bare ``_emit``
# helper rather than the OutputSchema-gated ``_emit_envelope``. Each
# entry carries a durable constraint-shape rationale about which
# surfaces are typed payloads versus unstructured operator-facing prose.
_BARE_EMIT_EXEMPTIONS: frozenset[tuple[str, str]] = frozenset(
    {
        (
            "src/aeat/entrypoints/cli/_config/__init__.py",
            "help-document prose is operator-facing text, not an OutputSchema payload",
        ),
        (
            "src/aeat/entrypoints/cli/_config/__init__.py",
            "repair-report passthrough emits an already validated ConfigRepairReport",
        ),
        (
            "src/aeat/entrypoints/cli/_config/_repair_cli.py",
            "repair-report passthrough after config repair extraction",
        ),
    }
)

_BARE_EMIT_EXEMPTION_PATHS: frozenset[str] = frozenset(path for path, _rationale in _BARE_EMIT_EXEMPTIONS)


def test_zero_bare_emit_sites_outside_exemption_set() -> None:
    """Production CLI modules must use ``_emit_envelope``, not bare ``_emit``.

    Walks every Python file under ``src/aeat/entrypoints/cli/`` (excluding
    tests + the ``_common`` helper module that DEFINES ``_emit``) and
    counts call sites matching ``_emit(ctx`` outside the documented
    exemption set. Any new bare-emit site fails the gate so the
    OutputSchema envelope contract stays the canonical CLI emit path.
    """
    from pathlib import Path

    root = Path("src/aeat/entrypoints/cli")
    violations: list[str] = []
    for path in sorted(root.rglob("*.py")):
        if path.name.startswith("test_") or path.name == "conftest.py":
            continue
        if path.name == "_common.py":
            continue  # canonical definition of _emit lives here
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if "_emit(ctx" not in line:
                continue
            relative = path.as_posix()
            if relative in _BARE_EMIT_EXEMPTION_PATHS:
                continue
            violations.append(f"{relative}:{lineno}: {line.strip()}")
    assert violations == [], (
        "New bare _emit(ctx call site detected outside the exemption set; "
        "every CLI command emit must route through _emit_envelope with a "
        "registered OutputSchema. Violations:\n  " + "\n  ".join(violations)
    )
