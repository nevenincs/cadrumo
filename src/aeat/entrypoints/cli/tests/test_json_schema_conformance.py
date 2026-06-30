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

from collections.abc import Callable, Sequence
from typing import Any, Protocol, TypeGuard, cast

import click
import pytest
import typer
from typer.main import get_command as _typer_get_command

from ....application.ledger._models import (
    LedgerCatalogueResetReport,
    LedgerRemovalBlocker,
    LedgerTransactionRemovalReport,
)
from ....core.json_contract import SCHEMA_REGISTRY, OutputSchema, SchemaEnvelope

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
_PATH_KEY_OVERRIDES: dict[str, str] = {
    "config.profile.history": "config.bucket.history",
}


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
    normalised = ".".join(tokens)
    return _PATH_KEY_OVERRIDES.get(normalised, normalised)


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
#  * ``aeat app ledger participation`` (group callback) emits
#    ``ledger.participation`` for the inverse audit lookup invoked as
#    ``participation <transaction-id>`` (the group is ``invoke_without_command``);
#    the ``rebuild`` subcommand is a reachable leaf with its own key.
_GROUP_CALLBACK_EMIT_KEYS: frozenset[str] = frozenset(
    {
        "root.status",
        "root.app",
        "ledger.participation",
    },
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
    # exercises: the registry maps each command to its schema at runtime.
    envelope_cls = cast(Any, SchemaEnvelope)[schema]
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
    },
)

_BARE_EMIT_EXEMPTION_PATHS: frozenset[str] = frozenset(path for path, _rationale in _BARE_EMIT_EXEMPTIONS)


# ---------------------------------------------------------------------
# Shared-spine + notices-channel conformance.
# ---------------------------------------------------------------------

#: The success envelope's outer spine. Shared (minus ``result`` vs
#: ``error``) with the stderr error document so one shape describes
#: success, warning, and error outcomes.
_EXPECTED_SUCCESS_SPINE_KEYS = frozenset({"schema_version", "command", "status", "result", "notices"})

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
    assert set(document) >= {"schema_version", "command", "status", "error", "notices"}
    assert document["status"] == "error"
    assert document["command"] is None
    assert isinstance(document["notices"], list)


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
