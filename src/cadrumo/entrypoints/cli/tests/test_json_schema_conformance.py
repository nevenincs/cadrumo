"""Conformance gate for the CLI schema-envelope contract.

Every leaf command exposed by the Cadrumo CLI MUST emit its result
through :class:`SchemaEnvelope`, which means its payload model MUST
be registered under a stable command-path string in
:data:`SCHEMA_REGISTRY` via :func:`register_schema`.

This module enumerates the Typer command tree, derives the canonical
command-path string for every leaf, and asserts an exact match against
the registered schema keys. There is no allowlist: a leaf without a
schema fails the gate, and a registry key without a matching leaf
fails the gate. Either side surfaces a structural regression that
must be fixed before the suite goes green.

The scope here is deliberately STRUCTURAL: it settles which command owns
which schema, never what constraints that schema publishes. A field
retyped from a plain ``str`` onto a canonical identifier alias changes the
advertised ``minLength`` / ``maxLength`` / ``pattern`` without moving a
single registry key, so this gate stays green through it. The
CONTENT of those advertised constraints is pinned separately, across both
the CLI envelope and the MCP ``output_schema`` built from the same
registry, by
``cadrumo_harness.mcp.tests.test_identifier_schema_contract_pin``. Read the two
together: a loosening caught by neither would be a genuine gap in the
published operator contract.
"""

from __future__ import annotations

import ast
import subprocess
import sys
import textwrap
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Protocol, TypeGuard, cast, get_args

import click
import pytest
import typer
from pydantic import BaseModel, TypeAdapter
from typer.main import get_command as _typer_get_command

# ``config.profile.create`` / ``config.profile.edit`` register in
# application.wizard._results (their real producer), not a CLI payload
# module; import it here for the same reason as the two imports below —
# without it SCHEMA_REGISTRY lacks both keys at collection time and
# test_registered_schema_envelope_round_trips silently skips them.
from ....application import wizard as wizard
from ....application.ledger import (
    LedgerCatalogueResetReport,
    LedgerRemovalBlocker,
    LedgerTransactionRemovalReport,
)
from ....core import PRODUCT_IDENTITY, STR_KEYED_MAPPING_ADAPTER, scan_directory
from ....core.json_contract import SCHEMA_REGISTRY, OutputSchema, SchemaEnvelope
from ...schema_surface import (
    GROUP_CALLBACK_SCHEMA_KEYS,
    RESULT_SCHEMA_MODULES,
    normalise_cli_path_to_schema_key,
)

# Import the per-package payload modules so their @register_schema
# decorators populate SCHEMA_REGISTRY before the gate inspects it.
# The CLI loads these lazily at dispatch time, so without an explicit
# import here the registry is empty when this test module collects.
#
# Every ``app.*`` family is enrolled. Before any of them were, every
# parametrised case was a ``config`` or root key and no ``app`` command was
# inside this gate at all -- which is not something a passing run could reveal,
# since a gate only checks what is registered when it collects. The families
# were enrolled in two measured batches: live first (33 keys), then the
# remaining four together (52 keys, of which quickfile contributes 49).
from .. import _app_live_payloads as _app_live_payloads
from .. import _app_maintenance_payloads as _app_maintenance_payloads
from .. import _app_quickfile_payloads as _app_quickfile_payloads
from .. import _config_bucket_history_payloads as _config_bucket_history_payloads
from .. import _config_descendiente_payloads as _config_descendiente_payloads
from .. import _config_payloads as _config_payloads
from .._command_suggestions import materialise_lazy_subcommands
from .._verb_input_schema import DECLARED_UNIMPLEMENTED_SURFACES

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

# ---------------------------------------------------------------------
# Canonical command-path normalisation
# ---------------------------------------------------------------------
#
# A leaf-command Typer path is a tuple of group/command names walked
# from the executable root, e.g. ``("aeat", "app", "modelo", "work",
# "calculate")``. Registry keys are dot-joined strings without the
# executable root, e.g. ``"modelo.work.calculate"``.
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
#  * Strip the leading canonical executable token.
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


class _PayloadWithStaleDraftRefs(Protocol):
    stale_draft_revision_references: Sequence[object]


type _LedgerReport = LedgerTransactionRemovalReport | LedgerCatalogueResetReport
type _LedgerReportFactory = Callable[[], _LedgerReport]
type _LedgerPayloadClass = type[OutputSchema]


# Intentional, asserted command-path → registry-key divergences.
#
# The append-only event-history verb moved from ``config bucket history`` to
# ``config profile history`` (D1 family rename: the operator means their
# profile, not the storage bucket). The JSON envelope token
# ``config.bucket.history`` is a STABLE MACHINE API and is deliberately kept
# unchanged so existing machine consumers are not broken by the operator-facing
# verb relocation. The leaf path therefore diverges from its registry key by
# design; this map records the divergence so the no-allowlist gate stays exact
# without silently masking an accidental mismatch elsewhere.
_normalise_command_path = normalise_cli_path_to_schema_key


# ---------------------------------------------------------------------
# Typer-tree walking
# ---------------------------------------------------------------------


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
        # Materialise the synthetic root context so CadrumoTyperGroup's
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
#  * ``cadrumo`` (root callback) emits ``root.status`` for the landing /
#    help surface.
#  * ``aeat app`` (group callback) emits ``root.app`` for the
#    ``aeat app`` landing / help surface.
#
# When a future group callback adds an envelope emit, register its key
# here so the gate continues to model the actual reach of the CLI tree.
#  * ``aeat app ledger participation`` (group callback) emits
#    ``ledger.participation`` for the inverse audit lookup invoked as
#    ``participation <transaction-id>`` (the group is ``invoke_without_command``);
#    the ``rebuild`` subcommand is a reachable leaf with its own key.
_GROUP_CALLBACK_EMIT_KEYS: frozenset[str] = GROUP_CALLBACK_SCHEMA_KEYS


def _walk_cli_command_paths(app: typer.Typer) -> set[str]:
    """Enumerate every registered envelope key reachable from ``app``.

    Forces every lazy subtree to materialise so the resulting set is
    exhaustive — no lazy import elides a leaf — then projects each
    leaf path through :func:`_normalise_command_path` to obtain the
    canonical registry-key string. Group-callback emit sites are added
    via :data:`_GROUP_CALLBACK_EMIT_KEYS` because the click leaf walk
    cannot reach a callback that does not register as a subcommand.
    """
    materialise_lazy_subcommands(app)
    root = _typer_get_command(app)
    root.name = app.info.name or PRODUCT_IDENTITY.cli_executable
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


def test_every_emitted_command_identifier_is_registered() -> None:
    """Every ``command=`` string a handler emits must be a registered key.

    The leaf gate below derives the command path from the Typer tree and checks
    it is registered. That leaves one route open, and a live defect took it:
    ``ledger.invoice.add`` was registered while the handler emitted
    ``ledger.invoice.create``. Both halves of the leaf gate
    agreed, so it stayed green, and ``aeat --format json app ledger invoice
    add`` refused at runtime with "no registered output schema" -- a
    JSON-emitting verb that could not emit.

    Deriving the path and emitting it are two separate acts, so a rename applied
    to one is invisible to a gate that only reads the other. This walks the
    literal strings actually passed at every emit site.

    Scoped to the emitters that actually consult the registry. The low-level
    ``emit_json_success`` stays a transport primitive for metadata and
    diagnostic surfaces whose identifiers are deliberately not registered, so
    including it would flag those by design.
    """
    # Both sides are read by AST rather than from the live SCHEMA_REGISTRY.
    # The registry is populated by IMPORTING payload modules, which the CLI
    # defers to dispatch, so a gate that imported them to fill it would leave
    # the extra keys behind in a process-global mapping and break the sibling
    # tests that assert the registry's exact contents. Reading the decorators
    # is side-effect free and answers the same question.
    validating_emitters = {"_emit_envelope", "emit_operator_json_success"}
    registered = {
        node.args[0].value
        for source in scan_directory(Path("src/cadrumo"), pattern="*.py", recursive=True)
        for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"), filename=str(source)))
        if isinstance(node, ast.Call)
        and (node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", None)) == "register_schema"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    }
    assert registered, "found no @register_schema literals; the decorator scan is not reaching the tree"

    root = Path("src/cadrumo/entrypoints/cli")
    violations: list[str] = []
    emitted = 0
    for path in scan_directory(root, pattern="*.py", recursive=True):
        if path.name.startswith("test_") or path.name == "conftest.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            called = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", None)
            if called not in validating_emitters:
                continue
            for keyword in node.keywords:
                if keyword.arg != "command":
                    continue
                if not isinstance(keyword.value, ast.Constant) or not isinstance(keyword.value.value, str):
                    # A computed identifier cannot be checked here; the leaf
                    # gate still covers the path it resolves to.
                    continue
                identifier = keyword.value.value
                emitted += 1
                if identifier not in registered:
                    violations.append(f"{path.as_posix()}:{keyword.value.lineno}: emits unregistered {identifier!r}")

    assert emitted > 0, "found no literal command= emit sites; the walk is not reaching the CLI"
    assert violations == [], "emitted command identifiers with no registered schema:\n" + "\n".join(violations)


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

    Keys listed in :data:`DECLARED_UNIMPLEMENTED_SURFACES` are excluded
    from the orphan side, because that mapping IS the sanctioned way to
    declare "this schema is deliberately held while its verb is absent",
    and each entry carries the reason. Excluding them here is not a
    weakening: it makes this gate agree with
    :func:`assert_schema_coverage`, which has always honoured the same
    declaration. Two gates disagreeing about the same four keys meant one
    of them was red for a state the other called legal, and a red that
    cannot be cleared teaches everyone to ignore the gate.

    The companion assertion below keeps the teeth: a declared entry whose
    verb has since landed is itself a failure, because every entry's
    stated exit condition is that restoring the verb removes it.
    """
    cli_paths = _walk_cli_command_paths(_live_app())
    registry_keys = set(SCHEMA_REGISTRY.keys())

    unregistered = sorted(cli_paths - registry_keys)
    orphans = sorted(registry_keys - cli_paths - set(DECLARED_UNIMPLEMENTED_SURFACES))

    diagnostic_lines: list[str] = []
    if unregistered:
        diagnostic_lines.append(f"CLI leaves missing a registered OutputSchema ({len(unregistered)}):")
        diagnostic_lines.extend(f"  - {path}" for path in unregistered)
    if orphans:
        diagnostic_lines.append(f"Registry keys with no matching CLI leaf ({len(orphans)}):")
        diagnostic_lines.extend(f"  - {key}" for key in orphans)

    assert not diagnostic_lines, "\n".join(diagnostic_lines)


def test_no_declared_unimplemented_surface_outlives_its_absent_verb() -> None:
    """A declared gap whose verb has landed must be removed, not left standing.

    The teeth for the exclusion above. Every
    :data:`DECLARED_UNIMPLEMENTED_SURFACES` entry states the same exit
    condition in its own reason -- restoring the verb removes the entry --
    and nothing enforced it, so a landed verb could leave its "this verb is
    knowingly absent" declaration in place indefinitely, telling every later
    reader a capability is missing when it ships.

    That is the failure class this campaign keeps meeting: prose that was
    true when written, that nothing re-derives, and that the next reader
    inherits rather than checks.
    """
    cli_paths = _walk_cli_command_paths(_live_app())
    landed = sorted(set(DECLARED_UNIMPLEMENTED_SURFACES) & cli_paths)

    assert not landed, (
        "DECLARED_UNIMPLEMENTED_SURFACES names verb(s) that now resolve against the live "
        "command tree; delete each entry, per its own stated exit condition:\n"
        + "\n".join(f"  - {key}" for key in landed)
    )


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
    # exercises: the registry maps each command to its schema at runtime.
    envelope_cls = cast(Any, SchemaEnvelope)[schema]
    assert envelope_cls.__pydantic_generic_metadata__["args"] == (schema,)


# ---------------------------------------------------------------------
# Zero-bare-emit gate for the envelope-schema contract.
# ---------------------------------------------------------------------

# ---------------------------------------------------------------------
# Shared-spine + notices-channel conformance.
# ---------------------------------------------------------------------

#: The success envelope's outer spine. Shared (minus ``result`` vs
#: ``error``) with the stderr error document so one shape describes
#: success, warning, and error outcomes. ``active_profile`` is the
#: identity anchor (the active taxpayer profile's human label, or null),
#: resolved at the CLI transport boundary and injected into the core
#: emitters.
_EXPECTED_SUCCESS_SPINE_KEYS = frozenset(
    {"schema_version", "command", "active_profile", "status", "result", "notices"},
)

#: Top-level result-schema field names that must never reappear: warnings,
#: advisories, and next-step hints belong on the envelope ``notices``
#: channel, not smuggled into a command's ``result`` payload. ``next_due`` /
#: ``next_action`` / ``next_label`` are legitimate structured data (a due
#: date, a per-finding action, a label) and are intentionally NOT forbidden;
#: only the bare ``next`` hint and the ``*_advisory`` smuggling are.
_FORBIDDEN_NOTICE_FIELD_NAMES = frozenset(
    {"next", "suggestion", "suggestions", "hint", "hints", "advisory", "advisories", "source_advisories"},
)


def _is_forbidden_notice_field(name: str) -> bool:
    """Return True when ``name`` is a bespoke notice/advisory result field."""
    return name in _FORBIDDEN_NOTICE_FIELD_NAMES or name.endswith("_advisory") or name.endswith("_advisories")


def test_success_envelope_carries_shared_spine() -> None:
    """:class:`SchemaEnvelope` must expose exactly the shared outer spine.

    Locks the spine so a future edit cannot silently drop ``status`` /
    ``notices`` or reintroduce the removed free-form ``warnings`` list.
    """
    assert set(SchemaEnvelope.model_fields) == set(_EXPECTED_SUCCESS_SPINE_KEYS)


@pytest.mark.parametrize("command_path", sorted(SCHEMA_REGISTRY.keys()))
def test_registered_schema_has_no_bespoke_notice_field(command_path: str) -> None:
    """No result schema may re-implement a notice / advisory / next-step field.

    Warnings, advisories, and next-step hints are the envelope
    ``notices`` channel's responsibility. A top-level result field named
    ``next``, ``suggestion``, ``*_advisory`` (etc.) is exactly the
    bespoke per-command smuggling the notice-standardisation removed; the
    gate fails loudly if one regrows so the uniform channel stays the only
    sanctioned diagnostic surface.
    """
    schema = SCHEMA_REGISTRY[command_path]
    fields = getattr(schema, "model_fields", {})
    offending = sorted(name for name in fields if _is_forbidden_notice_field(name))
    assert offending == [], (
        f"{command_path} ({schema.__module__}.{schema.__name__}) carries bespoke "
        f"notice/advisory field(s) {offending}; emit these on the envelope `notices` "
        f"channel via `_emit_envelope(..., notices=[...])` instead of a result field."
    )


def test_error_document_shares_the_success_spine() -> None:
    """The stderr error document carries the same outer spine as success.

    Renders a representative error and asserts the spine keys
    (``schema_version`` / ``command`` / ``status`` / ``notices``) sit
    alongside the nested ``error`` body, so a machine consumer reads one
    shape across success, warning, and error outcomes.
    """
    import json as _json

    from ....core.errors import render_error_json
    from ....core.locks_errors import LockAcquisitionError

    document = _json.loads(render_error_json(LockAcquisitionError()))
    assert set(document) >= {"schema_version", "command", "active_profile", "status", "error", "notices"}
    assert document["status"] == "error"
    assert document["command"] is None
    # The identity anchor is present on the error spine; null when the
    # boundary resolves no active profile (as here, with no injected label).
    assert document["active_profile"] is None
    assert isinstance(document["notices"], list)


def test_profile_bound_command_populates_active_profile_label(tmp_path: Path) -> None:
    """A real profile-bound command stamps the active profile's LABEL on the spine.

    Mints a profile with a known display label through the credential
    registration door -- the only creation door -- then runs a profile-bound
    non-wizard command
    (``app ledger list``, which funnels through ``_emit_envelope`` — never
    the wizard emit path) under ``--format json`` with that profile active.
    The outer envelope's ``active_profile`` must carry the human LABEL — the
    identity anchor an operator reconciles — resolved at the CLI transport
    boundary and injected into the core emitter. It must equal the stored
    manifest label and never surface the redacted profile/bucket UUID.

    Self-contained storage isolation (rather than an autouse module fixture)
    so the registry-walk conformance tests above are undisturbed.
    """
    import json as _json

    from ....adapters.persistence.storage.sql.engine import dispose_engine
    from ....application.workflow import read_profile_bucket
    from ....core.config import override_settings
    from ....tests.cli_runner import invoke_cached_cli
    from ....tests.secure_sql import isolated_profile_storage_root
    from ....tests.user_profile import register_cli_profile

    label = "Erika"
    dispose_engine()
    with isolated_profile_storage_root(tmp_path=tmp_path):
        try:
            register_cli_profile(
                label=label,
                facts={
                    "identity.tax_id": "12345678Z",
                    "taxpayer_type.entity_type": "natural_person",
                    "identity.name": "Erika",
                    "identity.surnames": "Identity",
                    "activities.description": "design",
                },
            )
            pointer = read_profile_bucket(label)
            assert pointer is not None, "the registered profile must resolve by its label"
            uuid = pointer.bucket_id
            assert uuid != label, "the bucket id must be a minted UUID, not the label"

            with override_settings(cadrumo_active_profile=uuid):
                listed = invoke_cached_cli(["--format", "json", "app", "ledger", "list"])

            assert listed.exit_code == 0, listed.output
            document = _json.loads(listed.output)
            assert document["active_profile"] == pointer.label, document
            # UUID redaction is unchanged: the spine carries the label, not the UUID.
            assert document["active_profile"] != uuid, document
        finally:
            dispose_engine()


def test_cli_has_no_bare_emit_definition_import_or_call() -> None:
    """The CLI has no structural route around the typed envelope boundary.

    AST inspection catches definitions, imports, direct calls, aliased calls,
    and attribute calls regardless of whitespace or multiline formatting. A
    text search for ``_emit(ctx`` could miss every one of those variants.
    """
    root = Path("src/cadrumo/entrypoints/cli")
    violations: list[str] = []
    scanned = 0
    for path in scan_directory(root, pattern="*.py", recursive=True):
        if path.name.startswith("test_") or path.name == "conftest.py":
            continue
        scanned += 1
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        relative = path.as_posix()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "_emit":
                violations.append(f"{relative}:{node.lineno}: defines _emit")
                continue
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name == "_emit":
                        violations.append(f"{relative}:{node.lineno}: imports _emit")
                continue
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name) and node.func.id == "_emit":
                violations.append(f"{relative}:{node.lineno}: calls _emit")
            elif isinstance(node.func, ast.Attribute) and node.func.attr == "_emit":
                violations.append(f"{relative}:{node.lineno}: calls attribute _emit")
    assert scanned > 50, (
        f"scanned only {scanned} CLI modules under {root}; the scan corpus collapsed (a package "
        "relocation or rename), so an empty violation list would mean 'nothing was checked' "
        "rather than 'nothing is wrong'"
    )
    assert violations == [], (
        "Bare CLI emit route detected; every CLI result must route through "
        "_emit_envelope with a registered OutputSchema. Violations:\n  " + "\n  ".join(violations)
    )


# ---------------------------------------------------------------------
# emit_json_success bypass gate
# ---------------------------------------------------------------------
#
# test_cli_has_no_bare_emit_definition_import_or_call (above) catches a
# bespoke ``_emit`` re-implementation, but it is scoped to
# ``entrypoints/cli`` and matches only the literal name ``_emit`` — it
# cannot see a command surface OUTSIDE that root calling
# core.json_contract.emit_json_success directly under its real name. The
# setup wizard (application.wizard._commands) did exactly that: it built a
# raw dict and called emit_json_success itself, bypassing both the
# sandbox-active notice _emit_envelope injects for every other command and
# the strict registered OutputSchema validation. emit_json_success itself
# cannot carry the sandbox notice — core.json_contract must not import the
# adapters that read a bucket manifest — so
# application.operator_output.emit_operator_json_success is the one
# funnel that resolves and injects it before delegating to the low-level
# primitive. This gate scans both entrypoints/cli AND application (every
# layer that can emit CLI JSON) for a bare emit_json_success import or
# call outside that one funnel and its one documented exception.
_EMIT_JSON_SUCCESS_ALLOWED_MODULES: frozenset[str] = frozenset(
    {
        # The sanctioned funnel: the only place a bare call is the
        # implementation, not a bypass.
        "src/cadrumo/application/operator_output/_emit.py",
        # The CLI transport's own --help / --version metadata-invocation
        # fast path deliberately skips sandbox/active-profile resolution
        # entirely for performance (see _emit_envelope); this is its one
        # direct low-level call, forcing active_profile to None itself
        # rather than routing through the funnel.
        "src/cadrumo/entrypoints/cli/_common.py",
    }
)


def test_no_bare_emit_json_success_call() -> None:
    """Only the sanctioned funnel (and its one documented exception) may call ``emit_json_success``.

    AST-scans every non-test module under ``entrypoints/cli`` and
    ``application`` for a bare import or call of
    ``emit_json_success`` (by name, attribute, or aliased import) outside
    :data:`_EMIT_JSON_SUCCESS_ALLOWED_MODULES`. This is the structural
    guarantee that the sandbox-active indicator cannot be dropped by a
    future command surface that forgets to ask for it: there is exactly
    one legitimate way to reach :class:`SchemaEnvelope` for an
    operator-facing result.
    """
    roots = (Path("src/cadrumo/entrypoints/cli"), Path("src/cadrumo/application"))
    violations: list[str] = []
    scanned = 0
    for root in roots:
        for path in scan_directory(root, pattern="*.py", recursive=True):
            if path.name.startswith("test_") or path.name == "conftest.py":
                continue
            relative = path.as_posix()
            if relative in _EMIT_JSON_SUCCESS_ALLOWED_MODULES:
                continue
            scanned += 1
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        if alias.name == "emit_json_success":
                            violations.append(f"{relative}:{node.lineno}: imports emit_json_success")
                    continue
                if not isinstance(node, ast.Call):
                    continue
                if isinstance(node.func, ast.Name) and node.func.id == "emit_json_success":
                    violations.append(f"{relative}:{node.lineno}: calls emit_json_success")
                elif isinstance(node.func, ast.Attribute) and node.func.attr == "emit_json_success":
                    violations.append(f"{relative}:{node.lineno}: calls attribute emit_json_success")
    assert scanned > 200, (
        f"scanned only {scanned} modules under entrypoints/cli and application; the scan corpus "
        "collapsed (a package relocation or rename), so an empty violation list would mean "
        "'nothing was checked' rather than 'nothing is wrong'"
    )
    assert violations == [], (
        "Bare emit_json_success route detected outside "
        "application.operator_output.emit_operator_json_success; every operator-facing "
        "JSON success must route through that funnel so the sandbox-active notice "
        "cannot be dropped. Violations:\n  " + "\n  ".join(violations)
    )


def test_every_emit_json_success_exemption_is_still_live() -> None:
    """Each allowed module must exist and still reach ``emit_json_success``.

    The scan above skips these paths before parsing them, so nothing else ever
    observes the entries. Presence is not liveness: an entry whose module was
    deleted or renamed, or which stopped touching ``emit_json_success``, leaves
    a path permanently exempt from the funnel guard, and whatever later occupies
    that path inherits an exemption nobody granted it.

    The check is redundancy rather than existence -- run the same detection the
    gate would have run had the path not been skipped, and require it to still
    find the import or call the entry exists to permit.
    """
    stale: list[str] = []
    for relative in sorted(_EMIT_JSON_SUCCESS_ALLOWED_MODULES):
        path = Path(relative)
        if not path.is_file():
            stale.append(f"{relative} (file absent)")
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        reaches = any(
            (isinstance(node, ast.ImportFrom) and any(alias.name == "emit_json_success" for alias in node.names))
            or (
                isinstance(node, ast.Call)
                and (
                    (isinstance(node.func, ast.Name) and node.func.id == "emit_json_success")
                    or (isinstance(node.func, ast.Attribute) and node.func.attr == "emit_json_success")
                )
            )
            for node in ast.walk(tree)
        )
        if not reaches:
            stale.append(f"{relative} (no longer imports or calls emit_json_success; drop the entry)")
    assert not stale, "Stale _EMIT_JSON_SUCCESS_ALLOWED_MODULES entries:\n" + "\n".join(f"  {entry}" for entry in stale)


# ---------------------------------------------------------------------
# Domain-report ↔ CLI payload mirror parity
# ---------------------------------------------------------------------
#
# Several CLI handlers round-trip a backend report onto its CLI
# ``OutputSchema`` mirror via ``Payload.model_validate(report.model_dump(
# mode="json"))``. Because ``OutputSchema`` is ``extra="forbid"``, a field
# added to the backend report but not mirrored onto the payload raises a
# ``ValidationError`` at dispatch time — a runtime break the per-schema
# round-trip gate above cannot catch (it never feeds a real report dump
# through the payload). This table-driven gate constructs a fully-populated
# backend report (every defaultable field set non-default per
# ``aeat-quality-gates``, including a non-empty
# ``stale_draft_revision_references``), validates the payload mirror against
# its JSON dump, and asserts the mirror carries the stale-draft advisory.
# It reds when a report grows a field its paired payload lacks and greens
# once the mirror catches up — the regression that broke ``aeat app ledger
# remove`` when ``stale_draft_revision_references`` landed on the report
# alone.

_HEX_64_A = "a" * 64
_HEX_64_B = "b" * 64
_HEX_64_C = "c" * 64
_HEX_64_D = "d" * 64


def _populated_removal_blocker() -> LedgerRemovalBlocker:
    """Build a fully-populated ``LedgerRemovalBlocker`` with every field non-default."""

    return LedgerRemovalBlocker(
        work_unit_id=_HEX_64_A,
        calculation_revision_id=_HEX_64_B,
        revision_state="borrador",
        modelo="130",
        filing_year=2026,
        period="1T",
    )


def _populated_removal_report() -> LedgerTransactionRemovalReport:
    """Build a ``LedgerTransactionRemovalReport`` with every defaultable field non-default."""

    return LedgerTransactionRemovalReport(
        bucket_id="bucket-parity",
        transaction_id=_HEX_64_C,
        removed=True,
        dry_run=False,
        actor="operator-parity",
        reason="parity-gate",
        cascaded_purchase_invoice_evidence_ids=("evidence-1",),
        cascaded_attachment_ids=("attachment-1",),
        blocking_modelo_references=(_populated_removal_blocker(),),
        stale_draft_revision_references=(_populated_removal_blocker(),),
        bucket_event_ids=(_HEX_64_D,),
    )


def _populated_reset_report() -> LedgerCatalogueResetReport:
    """Build a ``LedgerCatalogueResetReport`` with every defaultable field non-default."""

    return LedgerCatalogueResetReport(
        bucket_id="bucket-parity",
        removed_transaction_ids=(_HEX_64_C,),
        reset=True,
        dry_run=False,
        actor="operator-parity",
        reason="parity-gate",
        cascaded_purchase_invoice_evidence_ids=("evidence-1",),
        cascaded_attachment_ids=("attachment-1",),
        blocking_modelo_references=(_populated_removal_blocker(),),
        stale_draft_revision_references=(_populated_removal_blocker(),),
        bucket_event_ids=(_HEX_64_D,),
    )


def _report_payload_mirror_pairs() -> tuple[tuple[_LedgerReportFactory, _LedgerPayloadClass, str], ...]:
    """Known ``(report_factory, payload_class, label)`` mirror pairs.

    Each payload's docstring declares it mirrors the report via
    ``model_dump(mode="json")``; the handler round-trips the dump under
    ``extra="forbid"``, so a missing mirrored field is a runtime break.
    """
    from .. import _ledger_payloads

    return (
        (_populated_removal_report, _ledger_payloads.LedgerRemoveResult, "ledger.remove"),
        (_populated_reset_report, _ledger_payloads.LedgerResetResult, "ledger.reset"),
    )


@pytest.mark.parametrize(
    ("report_factory", "payload_class", "label"),
    [pytest.param(factory, payload, label, id=label) for factory, payload, label in _report_payload_mirror_pairs()],
)
def test_report_payload_mirror_accepts_full_dump(
    report_factory: _LedgerReportFactory,
    payload_class: _LedgerPayloadClass,
    label: str,
) -> None:
    """The CLI payload mirror ``model_validate``s its report's full JSON dump.

    Constructs a fully-populated backend report (including a non-empty
    ``stale_draft_revision_references``) and validates the ``OutputSchema``
    mirror against ``report.model_dump(mode="json")``. Under ``extra="forbid"``
    this raises if the report carries a field the payload does not mirror —
    exactly the regression that broke ``aeat app ledger remove`` when the
    stale-draft advisory landed on the report but not its payload. Asserts the
    round-tripped payload carries the stale-draft advisory so a silent drop is
    also caught.
    """
    report = report_factory()
    dump = report.model_dump(mode="json")
    assert dump["stale_draft_revision_references"], (
        f"{label} fixture must populate stale_draft_revision_references so the parity "
        "gate exercises the field that broke the round-trip"
    )
    payload = cast(_PayloadWithStaleDraftRefs, payload_class.model_validate(dump))
    assert payload.stale_draft_revision_references, (
        f"{label} payload {payload_class.__name__} dropped stale_draft_revision_references "
        "on the round-trip; mirror the field so the advisory reaches the JSON envelope"
    )
    assert len(payload.stale_draft_revision_references) == len(report.stale_draft_revision_references)


# ---------------------------------------------------------------------
# Custody contract gate: exact keys, exclusivity, and secret-free results
# ---------------------------------------------------------------------

#: Field names that would *be* a secret value rather than describe one.
#:
#: Derived from the confidentiality contract, not from the current tree: a
#: result field under one of these names carries key material, a passphrase,
#: or recovery words onto an operator envelope. Metadata *about* a secret
#: (``has_secret``, ``secret_store_dir``, ``recovery_fingerprint``) is not a
#: secret and is deliberately absent from this set.
_SECRET_BEARING_FIELD_NAMES = frozenset(
    {
        "passphrase",
        "new_passphrase",
        "old_passphrase",
        "current_passphrase",
        "password",
        "mnemonic",
        "recovery_mnemonic",
        "recovery_code",
        "recovery_codes",
        "recovery_words",
        "recovery_phrase",
        "seed_phrase",
        "secret",
        "secret_value",
        "private_key",
        "master_key",
        "key_material",
        "plaintext",
    }
)

#: Accepted custody and reset schema keys and their exact declared field sets.
#:
#: Enrolment gate: every field on a custody envelope must be non-secret by
#: inspection, so adding a field to one of these results must fail here and be
#: reviewed rather than silently reaching an operator envelope.
_CUSTODY_SCHEMA_FIELDS: dict[str, frozenset[str]] = {
    "config.reset.start": frozenset({"operation"}),
    "config.reset.status": frozenset({"operation"}),
    "config.reset.resume": frozenset({"operation"}),
}

#: Command-result keys retired by the accepted verb grammar.
#:
#: These commands were removed outright with no alias, so a registration under
#: any of these keys is a resurrected contract for a door that no longer exists.
_REMOVED_SCHEMA_KEYS = frozenset(
    {
        "config.lock",
        "config.unlock",
        "config.rekey",
        "config.show-recovery",
        "config.show_recovery",
        "config.verify-recovery",
        "config.verify_recovery",
        "config.reset",
        "config.profile.sandbox.use",
        "modelo.audit.replay",
    }
)


def _nested_model_types(annotation: object) -> tuple[type[BaseModel], ...]:
    """Return every pydantic model reachable from one field annotation.

    Unwraps ``Optional``/union, list, tuple, and mapping parameters so a
    secret nested inside a container or an optional sub-payload is still
    reached by the recursive scan.
    """
    found: list[type[BaseModel]] = []
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        found.append(annotation)
    for argument in get_args(annotation):
        found.extend(_nested_model_types(argument))
    return tuple(found)


def _secret_bearing_field_paths(model: type[BaseModel]) -> tuple[str, ...]:
    """Return dotted paths of every secret-bearing field reachable from ``model``.

    Recurses through nested payload models so a secret cannot hide one level
    below the registered result. Cycles are broken by a visited set.
    """
    offending: list[str] = []
    stack: list[tuple[type[BaseModel], str]] = [(model, model.__name__)]
    visited: set[type[BaseModel]] = set()
    while stack:
        current, prefix = stack.pop()
        if current in visited:
            continue
        visited.add(current)
        for field_name, field in current.model_fields.items():
            if field_name.lower() in _SECRET_BEARING_FIELD_NAMES:
                offending.append(f"{prefix}.{field_name}")
            for nested in _nested_model_types(field.annotation):
                stack.append((nested, f"{prefix}.{field_name}"))
    return tuple(sorted(offending))


def test_no_registered_schema_serialises_secret_material() -> None:
    """No registered result schema may carry key material onto an envelope.

    Scans every registered :class:`OutputSchema` — and every payload model
    nested inside one — for a field named as a secret *value*. A passphrase,
    recovery phrase, or private key reaching a ``--json`` envelope is a hard
    confidentiality defect: envelopes are printed to terminals, piped into
    agent transcripts, and captured in operator logs.

    The registry is materialised through the live command tree first, so a
    lazily-imported payload module cannot hide a secret behind a partially
    populated registry (an empty scan would otherwise read as a clean pass).
    """
    _walk_cli_command_paths(_live_app())

    offenders: dict[str, tuple[str, ...]] = {}
    for command_path, schema in sorted(SCHEMA_REGISTRY.items()):
        paths = _secret_bearing_field_paths(schema)
        if paths:
            offenders[command_path] = paths

    assert not offenders, "Registered schemas serialise secret material:\n" + "\n".join(
        f"  - {command_path}: {', '.join(paths)}" for command_path, paths in sorted(offenders.items())
    )


def test_secret_field_scan_detects_a_planted_secret() -> None:
    """The secret scan must fail when a secret field is actually present.

    Anti-tautology proof for :func:`test_no_registered_schema_serialises_secret_material`.
    A name-based scan passes trivially if the predicate never matches, so plant
    a secret both directly and one level down a nested payload and require the
    scan to report each. Without this, a broken matcher would render the
    confidentiality gate silently vacuous.
    """

    class _PlantedNested(BaseModel):
        mnemonic: str

    class _PlantedResult(BaseModel):
        recovery_path: str
        passphrase: str
        nested: _PlantedNested | None = None

    found = _secret_bearing_field_paths(_PlantedResult)

    assert "_PlantedResult.passphrase" in found, f"direct secret field not detected; scan returned {found}"
    assert any(path.endswith(".mnemonic") for path in found), f"nested secret field not detected; scan returned {found}"


def test_custody_schema_keys_are_registered_with_distinct_schemas() -> None:
    """Each accepted custody and reset key resolves to its own result schema.

    Exclusivity matters because these keys are the operator contract for
    distinct custody operations: two keys sharing one schema class would let a
    ``verify`` result be read as a ``rotate`` result, and a missing key means a
    custody door emits no documented envelope at all.
    """
    _walk_cli_command_paths(_live_app())

    missing = sorted(key for key in _CUSTODY_SCHEMA_FIELDS if key not in SCHEMA_REGISTRY)
    assert not missing, f"accepted custody/reset schema keys are not registered: {missing}"

    by_schema: dict[str, list[str]] = {}
    for key in _CUSTODY_SCHEMA_FIELDS:
        by_schema.setdefault(SCHEMA_REGISTRY[key].__name__, []).append(key)
    shared = {name: sorted(keys) for name, keys in by_schema.items() if len(keys) > 1}
    assert not shared, f"custody keys share a result schema, collapsing distinct contracts: {shared}"


def test_custody_result_fields_are_enrolled() -> None:
    """Every field on a custody envelope is explicitly enrolled and non-secret.

    Change-detection gate on the confidentiality-critical surface: a new field
    added to a passphrase, recovery, or reset result must fail here and be
    reviewed before it can reach an operator envelope. The enrolled sets are
    the audited secret-free shapes; a drift in either direction is reported.
    """
    _walk_cli_command_paths(_live_app())

    drift: list[str] = []
    for key, expected in sorted(_CUSTODY_SCHEMA_FIELDS.items()):
        schema = SCHEMA_REGISTRY[key]
        actual = frozenset(schema.model_fields)
        if actual != expected:
            added = sorted(actual - expected)
            removed = sorted(expected - actual)
            drift.append(f"  - {key} ({schema.__name__}): unenrolled={added} missing={removed}")

    assert not drift, "custody result field sets drifted from their enrolled secret-free shapes:\n" + "\n".join(drift)


def test_removed_command_schema_keys_are_absent() -> None:
    """No result schema may be registered under a retired command key.

    The lock, rekey, flat scoped reset, legacy show/verify-recovery,
    sandbox-use, and modelo audit replay doors were removed with no alias.
    A registration under one of those keys resurrects a contract for a command
    an operator cannot invoke, and would hand an agent a dead instruction.
    """
    _walk_cli_command_paths(_live_app())

    resurrected = sorted(_REMOVED_SCHEMA_KEYS & set(SCHEMA_REGISTRY))
    assert not resurrected, f"retired command keys are registered again: {resurrected}"


# ---------------------------------------------------------------------
# Canonical wizard-schema owner guard (fresh subprocess)
# ---------------------------------------------------------------------
#
# ``config.profile.create`` / ``config.profile.edit`` are declared by their
# application producer and imported through the canonical result-schema module
# declaration. This keeps command startup cold while allowing the capability
# surface to discover schemas at their actual producer, without a CLI
# forwarding module.
#
# The in-process gates in this file CANNOT catch that: this module imports the
# wizard package at the top to seed the registry itself (see the module header
# import), so the two schemas are present regardless of the canonical
# result-schema module declaration. Only a FRESH
# interpreter that never imports the wizard package can measure the real
# dependency, which is why this guard runs in a subprocess. Measured: the MCP
# surface may seed the schemas through unrelated imports; the CLI-contract/manifest
# surface therefore needs a fresh-process guard scoped to its canonical declared
# owner.
_PROFILE_SCHEMA_KEYS = ("config.profile.create", "config.profile.edit")


def _canonical_profile_schema_owner() -> str:
    """Derive the declared module that owns every profile schema under test."""
    missing = sorted(set(_PROFILE_SCHEMA_KEYS) - set(SCHEMA_REGISTRY))
    assert not missing, f"profile schemas are absent from the seeded registry: {missing}"

    declared_profile_owners = frozenset(
        module
        for module in RESULT_SCHEMA_MODULES
        if all(SCHEMA_REGISTRY[key].__module__ == module for key in _PROFILE_SCHEMA_KEYS)
    )
    assert declared_profile_owners, (
        "no canonical result-schema module owns every profile schema under test; registered owners: "
        f"{sorted({SCHEMA_REGISTRY[key].__module__ for key in _PROFILE_SCHEMA_KEYS})}"
    )
    return next(iter(declared_profile_owners))


def _probe_script(
    *,
    block_schema_owner: bool,
    profile_schema_keys: tuple[str, ...],
    schema_owner: str,
    storage_root: Path,
) -> str:
    """Render the fresh-interpreter probe script that builds the CLI manifest.

    ``storage_root`` is the caller's own ``tmp_path``-derived directory rather
    than a ``tempfile.mkdtemp()`` minted inside the subprocess: a directory
    the subprocess mints itself outlives that process with nothing to remove
    it, while a directory the outer test owns is reclaimed by pytest's normal
    ``tmp_path`` teardown.
    """
    return (
        textwrap.dedent(
            """
        import json, os, sys
        for _k in [_k for _k in os.environ if _k.startswith(("CADRUMO_", "AEAT_"))]:
            del os.environ[_k]
        os.environ["CADRUMO_LOCAL_STORAGE_ROOT"] = {storage_root!r}
        os.environ["CADRUMO_ACTIVE_PROFILE"] = " "
        schema_owner = {schema_owner!r}
        profile_schema_keys = {profile_schema_keys!r}
        if {block!r} == "block":
            class _Block:
                def find_spec(self, name, path, target=None):
                    if name == schema_owner:
                        raise ModuleNotFoundError("blocked for the schema-owner guard")
                    return None
            sys.meta_path.insert(0, _Block())
        # Warm the lazy core exports so a cold-start config resolution does not hit
        # the unrelated `pointer_path` circular import (identical in every case).
        from cadrumo.core import pointer_path, read_pointer  # noqa: F401
        from cadrumo.entrypoints.cli._command_schema import command_schema_refs

        # The guard must not import the wizard package itself: building the
        # contract entrypoint must leave it unimported, so any later wizard
        # import comes from the canonical declared owner rather than from the
        # guard seeding its own subject.
        wizard_before_walk = "cadrumo.application.wizard" in sys.modules
        commands = {ref.command for ref in command_schema_refs()}
        present = [key for key in profile_schema_keys if key in commands]
        print("RESULT " + json.dumps({"present": present, "wizard_before_walk": wizard_before_walk}))
        """
        )
        .replace("{storage_root!r}", repr(str(storage_root)))
        .replace("{profile_schema_keys!r}", repr(profile_schema_keys))
        .replace("{schema_owner!r}", repr(schema_owner))
        .replace("{block!r}", repr("block" if block_schema_owner else "keep"))
    )


def _profile_schema_keys_in_fresh_process(
    *, block_schema_owner: bool, storage_root: Path
) -> tuple[frozenset[str], bool]:
    """Build the CLI capability manifest in a clean interpreter and report the result.

    Returns ``(present_profile_keys, wizard_package_self_seeded)``. The subprocess
    never imports the wizard package, so the canonical results module is the sole
    registrar of the two profile schemas on this surface. ``block_schema_owner``
    simulates a failed declared-module import via a meta-path finder rather than touching a
    file that every peer would see.
    """
    schema_owner = _canonical_profile_schema_owner()
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            _probe_script(
                block_schema_owner=block_schema_owner,
                profile_schema_keys=_PROFILE_SCHEMA_KEYS,
                schema_owner=schema_owner,
                storage_root=storage_root,
            ),
        ],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert completed.returncode == 0, f"probe subprocess failed:\n{completed.stdout}\n{completed.stderr}"
    line = next(
        (row for row in reversed(completed.stdout.splitlines()) if row.startswith("RESULT ")),
        None,
    )
    assert line is not None, f"probe emitted no RESULT line:\n{completed.stdout}\n{completed.stderr}"
    payload = STR_KEYED_MAPPING_ADAPTER.validate_json(line.removeprefix("RESULT "))
    present = TypeAdapter(frozenset[str]).validate_python(payload["present"])
    return present, bool(payload["wizard_before_walk"])


def test_wizard_profile_schemas_reach_the_manifest_from_their_canonical_owner(tmp_path: Path) -> None:
    """The wizard-owned profile schemas reach the manifest from their producer.

    Runs in a fresh interpreter that does NOT import the wizard package, so
    the declared producer module is the sole registrar of the profile schemas
    on the capability-manifest surface. The guard first
    proves it did not self-seed the wizard package (a guard that seeds its own
    subject is the very defect it exists to catch), then that both schemas are
    present. If the canonical declaration omits their producer module, both
    keys silently vanish and this reds.
    """
    present, wizard_before_walk = _profile_schema_keys_in_fresh_process(
        block_schema_owner=False, storage_root=tmp_path / "storage"
    )

    assert not wizard_before_walk, (
        "the guard imported the wizard package before building the contract, so it seeds its own "
        "subject and can no longer prove the declared owner is load-bearing; the CLI-contract path must reach "
        "the profile schemas through their canonical producer module during contract construction"
    )
    missing = sorted(key for key in _PROFILE_SCHEMA_KEYS if key not in present)
    assert not missing, (
        f"wizard-owned profile schemas absent from the CLI capability manifest: {missing}. The "
        f"canonical result-schema declaration must import `{_canonical_profile_schema_owner()}` so the "
        "producer's decorators register both profile verbs during contract construction"
    )


def test_missing_canonical_schema_owner_drops_both_profile_schemas(tmp_path: Path) -> None:
    """Anti-tautology proof: without the canonical owner, both schemas disappear.

    Blocks the canonical owner in a fresh interpreter and confirms both keys drop
    from the CLI manifest. Without this, the guard above could pass on a registry
    seeded some other way and carry no information; this proves the explicit lazy
    declared-owner import is load-bearing and that the guard reds on its removal.
    """
    present, _ = _profile_schema_keys_in_fresh_process(block_schema_owner=True, storage_root=tmp_path / "storage")

    unexpected = sorted(set(_PROFILE_SCHEMA_KEYS) & present)
    assert not unexpected, (
        f"profile schemas survived the canonical owner's removal: {unexpected}; "
        "the guard cannot detect a declared-owner omission"
    )
