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
"""

from __future__ import annotations

import ast
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Protocol, TypeGuard, cast

import click
import pytest
import typer
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
from ....core import PRODUCT_IDENTITY
from ....core.json_contract import SCHEMA_REGISTRY, OutputSchema, SchemaEnvelope
from ...schema_surface import GROUP_CALLBACK_SCHEMA_KEYS, SCHEMA_KEY_BY_CLI_PATH

# Import the per-package payload modules so their @register_schema
# decorators populate SCHEMA_REGISTRY before the gate inspects it.
# The CLI loads these lazily at dispatch time, so without an explicit
# import here the registry is empty when this test module collects.
from .. import _config_payloads as _config_payloads
from .. import _config_sandbox_payloads as _config_sandbox_payloads
from ._lazy_command_tree import materialise_lazy_subcommands

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

_APP_NAMESPACE_PASSTHROUGH = frozenset({"live"})
_APP_NAMESPACE_FLATTEN = frozenset({"diagnostics", "ledger", "modelo", "overview", "registry", "review"})


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
def _normalise_command_path(path: tuple[str, ...]) -> str:
    """Project a Typer leaf-command path onto the registry key convention."""
    tokens = [token.replace("-", "_") for token in path]
    if tokens and tokens[0] == PRODUCT_IDENTITY.cli_executable:
        tokens = tokens[1:]
    if len(tokens) >= 2 and tokens[0] == "app":
        head = tokens[1]
        if head in _APP_NAMESPACE_FLATTEN:
            tokens = tokens[1:]
        elif head in _APP_NAMESPACE_PASSTHROUGH:
            pass  # keep ``app.`` prefix
    normalised = ".".join(tokens)
    return SCHEMA_KEY_BY_CLI_PATH.get(normalised, normalised)


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

    Drives the real ``config profile create`` flow to mint a profile with a
    known display label, then runs a profile-bound non-wizard command
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

    label = "Erika"
    dispose_engine()
    with isolated_profile_storage_root(tmp_path=tmp_path):
        try:
            created = invoke_cached_cli(
                [
                    "config",
                    "profile",
                    "create",
                    label,
                    "--quiet",
                    "--accept-defaults",
                    "--tax-id",
                    "12345678Z",
                    "--entity-type",
                    "natural_person",
                    "--name",
                    "Erika",
                    "--surnames",
                    "Identity",
                    "--activity",
                    "design",
                ],
            )
            assert created.exit_code == 0, created.output
            pointer = read_profile_bucket(label)
            assert pointer is not None, "the created profile must resolve by its label"
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
    for path in sorted(root.rglob("*.py")):
        if path.name.startswith("test_") or path.name == "conftest.py":
            continue
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
    for root in roots:
        for path in sorted(root.rglob("*.py")):
            if path.name.startswith("test_") or path.name == "conftest.py":
                continue
            relative = path.as_posix()
            if relative in _EMIT_JSON_SUCCESS_ALLOWED_MODULES:
                continue
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
    assert violations == [], (
        "Bare emit_json_success route detected outside "
        "application.operator_output.emit_operator_json_success; every operator-facing "
        "JSON success must route through that funnel so the sandbox-active notice "
        "cannot be dropped. Violations:\n  " + "\n  ".join(violations)
    )


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
# ``aeat-roundtrip-discipline``, including a non-empty
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
