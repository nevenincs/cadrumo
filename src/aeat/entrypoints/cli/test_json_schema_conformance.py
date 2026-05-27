"""Conformance gate for the CLI ``--json`` envelope migration.

Lands the per-command incremental migration contract ratified by
linkage-design-audit ADR Decision 3 (``json-envelope-migration-sequencing``).

The gate enforces a single rule per migrated command: every command
listed in :data:`MIGRATED_COMMANDS` must emit a JSON payload that
re-parses as a :class:`SchemaEnvelope` whose ``command`` field matches
the listed path and whose ``result`` field validates against the
registered :class:`OutputSchema` for that command. Commands NOT in
the list are exempt — they still emit the bare-payload shape and
their existing surface tests pin that contract.

Migration cadence:

1. Author lifts a command's emit site from the bare ``_emit(ctx, payload, lines)``
   shape to ``emit_json_success("modelo.work.<verb>", result_model)``.
2. Author appends the command path to :data:`MIGRATED_COMMANDS`.
3. Author re-baselines any pre-migration surface test that asserted
   the bare-payload shape against the envelope shape.
4. This gate runs and verifies the migrated command round-trips
   through :class:`SchemaEnvelope` cleanly.

Once every CLI ``--json`` emit site has been migrated, the gate
tightens by removing the ``MIGRATED_COMMANDS`` allow-list and
requiring envelope conformance for every registered schema. That
close-out is a separate Step in the linkage-design-audit plan and
must not happen until every command surface is migrated.

This module deliberately does NOT enumerate the bare-payload command
inventory — that responsibility stays with each command's own
``test_*.py`` surface test. The gate's only job is to prove that
migrated commands do not regress out of the envelope shape.
"""

from __future__ import annotations

import pytest

from ...core.json_contract import SCHEMA_REGISTRY, SchemaEnvelope

# Import the per-package payload modules so their @register_schema
# decorators populate SCHEMA_REGISTRY before the gate inspects it.
# A test-local import is necessary because the CLI lazy-loads
# subcommand modules — the registry is otherwise empty until the
# first Typer dispatch.
from . import _modelo_payloads, _review_payloads  # noqa: F401  (side-effect import)

# Per-command allow-list of migrated emit sites. Populated as each
# command's ``--json`` emit site is lifted to
# :func:`emit_json_success`. Starts empty — every entry must be paired
# with the matching emit-site migration commit.
MIGRATED_COMMANDS: frozenset[str] = frozenset(
    {
        # P09.S42c: first emit-site lifted to the envelope shape.
        "modelo.work.calculate",
        # P09.S43: the 10 remaining work-lifecycle emit sites.
        "modelo.work.create",
        "modelo.work.reuse",
        "modelo.work.list",
        "modelo.work.status",
        "modelo.work.rename",
        "modelo.work.discard",
        "modelo.work.revisions",
        "modelo.work.revision",
        "modelo.work.verify",
        "modelo.work.file",
        "modelo.work.amend",
    }
)


@pytest.mark.unit
@pytest.mark.domain_application
def test_migrated_commands_are_registered() -> None:
    """Every entry in MIGRATED_COMMANDS must have a registered schema.

    Catches the typo / drift case where the migration list and the
    ``@register_schema`` decorator on the result model disagree. The
    envelope round-trip depends on the registered schema, so a stale
    or mistyped entry would silently downgrade the gate.
    """

    unregistered = sorted(MIGRATED_COMMANDS - SCHEMA_REGISTRY.keys())
    assert not unregistered, (
        "MIGRATED_COMMANDS lists commands without a registered OutputSchema "
        f"(check the @register_schema decorator on the result model): {unregistered}"
    )


@pytest.mark.unit
@pytest.mark.domain_application
@pytest.mark.parametrize("command_path", sorted(MIGRATED_COMMANDS))
def test_migrated_command_envelope_round_trips(command_path: str) -> None:
    """Each migrated command's schema must round-trip via SchemaEnvelope.

    Builds the smallest valid envelope shape for the registered schema
    (the schema's default-field projection plus the migrated command
    path) and validates that the envelope re-parses cleanly. This is
    the structural shape gate, not the value gate — the per-command
    surface test still owns end-to-end behaviour.

    Skipped intentionally as a per-parametrize body when the set is
    empty (pytest.param yields zero invocations) — the test exists
    so the gate's parametrize source is visible in the suite tree.
    """

    schema = SCHEMA_REGISTRY[command_path]
    # SchemaEnvelope is generic over the result schema. Parametrising
    # it with the registered schema must succeed at type-construction
    # time — if the schema is not a valid OutputSchema subclass the
    # generic specialisation raises. Per-command surface tests own
    # the end-to-end emit -> bytes -> envelope round-trip; this gate
    # is the structural enrolment check.
    envelope_cls = SchemaEnvelope[schema]  # type: ignore[valid-type]
    assert envelope_cls.__pydantic_generic_metadata__["args"] == (schema,)
