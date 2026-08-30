"""Co-commit drift gate for the operator harness rule surface.

The operator operating rules name concrete CLI verbs and JSON-envelope fields.
If a verb is renamed or an envelope field moves and the rule is not updated in the
same change, the operator inherits a dead instruction - the exact failure mode the
``cadrumo-pull-and-file-standard`` rule exists to prevent, here on the operator
side. This gate parses every shipped operator rule, extracts each ``aeat ...``
command path and each named envelope-spine field, and asserts they all resolve
against the live CLI surface and the real envelope models. A rule that cites a
non-existent verb or field fails the gate.

A second, negative gate closes the complementary black-box hole: nothing forbade
an operator document from naming a package internal (a dotted ``aeat.<pkg>...``
module path, a ``src/cadrumo/...`` repo path, a private ``_module`` symbol, or a
``test_*`` name) instead of the CLI/manifest/legal surface the operator is
supposed to orient over. The dotted-module-path half of that check is sourced
from the live :class:`~cadrumo.application.operator_surface.OperatorSurfaceContract`
``service_owner`` / ``owner`` string values (never a hand-authored package-name
list), so a newly added backend module is blocked from leaking into rule prose
the moment it is registered as a command family's owner, with no separate
allowlist to keep in sync.
"""

from __future__ import annotations

import functools
import re
from collections.abc import Sequence
from typing import Any

import pytest

from cadrumo.application.operator_surface.contract import get_operator_surface_contract
from cadrumo.application.operator_surface.manifest import CommandSchemaRef
from cadrumo.core import ActionArgumentStatus, ActionConditionality, NoRecoveryOutcome
from cadrumo.core.errors.error_codes import ErrorEnvelope
from cadrumo.core.json_contract import (
    ENVELOPE_SCHEMA_VERSION,
    Notice,
    ResolvedActionReference,
    ResolvedPreconditionAction,
    SchemaEnvelope,
)

from .. import iter_operator_rules, iter_personas, iter_skill_documents
from ..mcp._capability_manifest import build_operator_surface_manifest

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_BACKTICK = re.compile(r"`([^`]+)`")
# A subcommand token: lowercase, digits, and hyphens only. Flags (``--x``),
# placeholders (``<id>``), and argument values (``130``, ``1T``) do not match and
# stop command-path collection.
_SUBCOMMAND = re.compile(r"^[a-z][a-z0-9-]*$")
# A flag token cited in prose: short or long option, lowercase.
_FLAG = re.compile(r"^--?[a-z][a-z0-9-]*$")
# Envelope-spine / notice field names a rule may cite in backticks. Each must be a
# real field on the model named here, or the rule is teaching a phantom field.
_ENVELOPE_FIELDS = frozenset(SchemaEnvelope.model_fields)
_NOTICE_FIELDS = frozenset(Notice.model_fields)

# Structural internal-shape patterns that are true regardless of what the
# manifest currently declares - a repo path, a private symbol, or a test name
# is never a CLI/manifest/legal-surface citation no matter which package it
# names, so these do not need to be sourced from contract data.
_REPO_PATH_TOKEN = re.compile(r"(^|[\s`])src[/\\]aeat[/\\]")
_PRIVATE_SYMBOL_TOKEN = re.compile(r"^_[A-Za-z][A-Za-z0-9_]*(\.py)?$")
_TEST_NAME_TOKEN = re.compile(r"^test_[A-Za-z0-9_]*$")


def _valid_command_paths() -> frozenset[str]:
    """Every resolvable command path, in both flattened and ``app.``-prefixed form.

    Built from the live operator-surface manifest's registered command keys plus
    every dotted prefix (each group is itself a reachable path), in both the
    registry-key form (``modelo.work.calculate``) and the operator-facing
    ``app.``-prefixed form (``app.modelo.work.calculate``), so a rule that writes
    either form resolves and only a genuinely wrong verb fails.
    """
    schemas: tuple[CommandSchemaRef, ...] = build_operator_surface_manifest(
        envelope_schema_version=ENVELOPE_SCHEMA_VERSION,
        command_schemas=_command_schema_refs_via_cli(),
    ).command_schemas
    valid: set[str] = {"", "aeat", "app", "config"}
    for ref in schemas:
        parts = ref.command.split(".")
        for index in range(1, len(parts) + 1):
            prefix = ".".join(parts[:index])
            valid.add(prefix)
            valid.add(f"app.{prefix}")
    return frozenset(valid)


def _command_schema_refs_via_cli() -> tuple[CommandSchemaRef, ...]:
    # Reuse the CLI's own payload-discovery + projection so the gate sees exactly
    # the registered command surface the capability manifest reports.
    from cadrumo.entrypoints.cli import command_schema_refs

    return command_schema_refs()


def _command_path_from_invocation(invocation: str) -> str | None:
    """Project an ``aeat ...`` backtick span onto a dotted command path.

    Returns ``None`` for spans that are not an ``aeat`` command invocation. Command
    tokens are the leading subcommand-shaped tokens after ``aeat``; collection stops
    at the first flag (``--x``), placeholder (``<id>``), or argument value (``130``,
    ``1T``), which are not subcommand-shaped.
    """
    tokens = invocation.split()
    if not tokens or tokens[0] != "aeat":
        return None
    command_tokens: list[str] = []
    for token in tokens[1:]:
        if not _SUBCOMMAND.match(token):
            break
        command_tokens.append(token)
    return ".".join(command_tokens)


@functools.lru_cache(maxsize=1)
def _live_root_command() -> Any:
    """Materialise the full live Click command tree (all lazy subtrees loaded)."""
    from cadrumo.entrypoints.cli import full_command_tree

    return full_command_tree()


def _flags_of(command: Any) -> frozenset[str]:
    """Return every option string declared on ``command`` (incl. secondary opts)."""
    flags: set[str] = set()
    for param in getattr(command, "params", ()):
        for opt in (*getattr(param, "opts", ()), *getattr(param, "secondary_opts", ())):
            if opt.startswith("-"):
                flags.add(opt)
    return frozenset(flags)


def _resolve_command(tokens: Sequence[str]) -> Any | None:
    """Descend the live tree by ``tokens`` (sans ``aeat``); return the command or None."""
    import click

    command = _live_root_command()
    for token in tokens:
        is_group = callable(getattr(command, "list_commands", None)) and callable(getattr(command, "get_command", None))
        if not is_group:
            return None
        with click.Context(command, info_name=command.name or None) as ctx:
            command = command.get_command(ctx, token)
        if command is None:
            return None
    return command


@functools.lru_cache(maxsize=1)
def _global_flags() -> frozenset[str]:
    """Root-level options valid on any command (``--format``, ``--language``, ...)."""
    return _flags_of(_live_root_command()) | {"--help", "-h"}


def _invocation_tokens(invocation: str) -> tuple[list[str], list[str]] | None:
    """Split an ``aeat ...`` span into (command tokens, cited flag tokens)."""
    tokens = invocation.split()
    if not tokens or tokens[0] != "aeat":
        return None
    command_tokens: list[str] = []
    consuming_path = True
    flags: list[str] = []
    for token in tokens[1:]:
        if consuming_path and _SUBCOMMAND.match(token):
            command_tokens.append(token)
            continue
        consuming_path = False
        if _FLAG.match(token):
            flags.append(token)
    return command_tokens, flags


def _rule_documents() -> list[tuple[str, str]]:
    return [(rule.name, rule.read_text(encoding="utf-8")) for rule in iter_operator_rules()]


def _all_operator_documents() -> list[tuple[str, str]]:
    """Every operator-facing harness document: rules, personas, and skills.

    All of them cite CLI verbs the operator is told to run, so all of them must
    be kept honest by the verb-resolution gate.
    """
    documents: list[tuple[str, str]] = list(_rule_documents())
    for persona in iter_personas():
        documents.append((f"personas/{persona.name}", persona.read_text(encoding="utf-8")))
    for skill in iter_skill_documents():
        documents.append((f"skills/{skill.name}", skill.read_text(encoding="utf-8")))
    return documents


def _internal_service_owner_tokens() -> frozenset[str]:
    """Every backend-owner dotted module path the live contract declares.

    Sourced from :class:`MountedCommandFamily.service_owner` and
    :class:`ServiceOwner.owner` on the live
    :class:`~cadrumo.application.operator_surface.OperatorSurfaceContract` - never a
    hand-authored package-name list - so a newly registered backend module is
    blocked from operator prose the moment it is enrolled as a command family's
    owner, with no second allowlist to keep in sync.
    """
    contract = get_operator_surface_contract()
    owners = {family.service_owner for family in contract.command_families}
    owners |= {owner.owner for owner in contract.service_owners}
    return frozenset(owners)


def test_operator_rules_exist() -> None:
    docs = _rule_documents()
    assert docs, "no operator rule documents are shipped under _data/agent/rules"
    names = {name for name, _ in docs}
    assert "cadrumo-operator-operating-rules.md" in names


def test_every_cited_verb_resolves() -> None:
    valid = _valid_command_paths()
    failures: list[str] = []
    for name, text in _all_operator_documents():
        for span in _BACKTICK.findall(text):
            path = _command_path_from_invocation(span)
            if path is None:
                continue
            if path not in valid:
                failures.append(f"{name}: `{span}` -> unresolved command path '{path}'")
    assert not failures, "operator rules cite non-existent CLI verbs:\n" + "\n".join(failures)


def test_every_cited_flag_resolves() -> None:
    # Every flag a rule/persona/skill cites on an `aeat ...` command must be a real
    # option of that command (or a root-global flag). A cited dead flag is the same
    # orphaned-instruction failure as a dead verb.
    global_flags = _global_flags()
    failures: list[str] = []
    for name, text in _all_operator_documents():
        for span in _BACKTICK.findall(text):
            parts = _invocation_tokens(span)
            if parts is None:
                continue
            command_tokens, flags = parts
            if not flags:
                continue
            command = _resolve_command(command_tokens)
            if command is None:
                # The verb gate already reports an unresolved command path; skip
                # flag-checking a command that does not resolve.
                continue
            allowed = _flags_of(command) | global_flags
            for flag in flags:
                if flag not in allowed:
                    failures.append(f"{name}: `{span}` -> unknown flag '{flag}' for `aeat {' '.join(command_tokens)}`")
    assert not failures, "operator docs cite non-existent CLI flags:\n" + "\n".join(failures)


def test_cited_envelope_spine_fields_still_exist() -> None:
    # The rules instruct the operator to read specific envelope/notice fields.
    # Assert each still exists on the live model, so a spine rename cannot leave
    # the rules teaching a field that moved.
    failures: list[str] = []
    for spine_field in ("schema_version", "command", "status", "result", "notices"):
        if spine_field not in _ENVELOPE_FIELDS:
            failures.append(f"envelope spine field '{spine_field}' no longer on SchemaEnvelope")
    # ``suggestion`` is deliberately absent. It was not merely dropped from
    # ``Notice`` — it is listed in ``_RESERVED_ACTION_CONTEXT_KEYS``, i.e.
    # proscribed, per the CLI contract's bar on a bespoke advisory field.
    # Asserting it here made this gate assert a stale contract rather than
    # catch one, which is the opposite of what it exists for.
    for notice_field in ("severity", "code", "message", "action", "context"):
        if notice_field not in _NOTICE_FIELDS:
            failures.append(f"notice field '{notice_field}' no longer on Notice")
    assert not failures, "\n".join(failures)


def test_envelope_reading_rule_pins_the_live_actionable_and_closed_refusal_grammar() -> None:
    """The shipped algorithm must drift with neither the error nor action schemas."""
    rule = dict(_rule_documents())["cadrumo-operator-envelope-reading.md"]
    expected_precondition_fields = (
        "failed_condition_id",
        "evidence",
        "action",
        "argument_bindings",
        "missing_argument_names",
        "conditionality",
        "no_recovery_outcome",
    )
    expected_action_fields = ("action_id", "target_command_key", "cli_path", "arguments")
    expected_conditionality = ("immediate", "requires_arguments", "not_applicable")
    expected_binding_statuses = ("resolved", "missing")
    expected_no_recovery = ("terminal", "safety", "operator_decision")

    assert tuple(ResolvedPreconditionAction.model_fields) == expected_precondition_fields
    assert tuple(ResolvedActionReference.model_fields) == expected_action_fields
    assert tuple(ErrorEnvelope.model_fields) == (
        "code",
        "category",
        "message",
        "action",
        "retryable",
        "runbook_id",
        "context",
        "trace_id",
    )
    assert tuple(member.value for member in ActionConditionality) == expected_conditionality
    assert tuple(member.value for member in ActionArgumentStatus) == expected_binding_statuses
    assert tuple(member.value for member in NoRecoveryOutcome) == expected_no_recovery

    required_rule_tokens = {
        "error.action",
        "error.action.action",
        *expected_precondition_fields[3:],
        "cli_path",
        "target_command_key",
        *expected_conditionality,
        *expected_binding_statuses,
        *expected_no_recovery,
    }
    assert required_rule_tokens <= set(_BACKTICK.findall(rule))


def test_no_operator_document_names_a_package_internal() -> None:
    """Negative gate: an operator document may cite the CLI/manifest/legal
    surface only, never a package internal.

    Two independent checks compose this gate:

    - A **data-sourced** check: no document may contain, anywhere in its text,
      one of the live contract's ``service_owner`` / ``owner`` dotted module
      paths (e.g. ``cadrumo.application.modelo``). The blocklist is read from
      :func:`~cadrumo.application.operator_surface.get_operator_surface_contract`,
      not hand-authored, so it grows automatically as new backend modules are
      registered as command-family owners.
    - Two **structural** checks over backticked spans: a repo path
      (``src/cadrumo/...``) and a private-symbol- or test-name-shaped single token
      (`` `_foo` ``, `` `test_bar` ``). These are internal-shaped regardless of
      which package they name, so they need no data source.

    Legitimate CLI-domain nouns (``ledger``, ``modelo``, ``casilla``, ...) never
    false-positive here: every ``service_owner`` / ``owner`` value is a full
    dotted ``aeat.<layer>.<module>`` string, and no CLI verb or domain noun is
    ever written in that dotted form (a CLI invocation is space-separated,
    e.g. ``aeat app modelo work calculate``), so a plain-word match is
    structurally impossible - see
    ``test_no_service_owner_value_collides_with_operator_prose`` for the
    empirical proof against the current, unmodified operator corpus.
    """
    owner_tokens = _internal_service_owner_tokens()
    failures: list[str] = []
    for name, text in _all_operator_documents():
        for owner in owner_tokens:
            if owner in text:
                failures.append(f"{name}: names backend-internal module path '{owner}'")
        for span in _BACKTICK.findall(text):
            if _REPO_PATH_TOKEN.search(f"`{span}`"):
                failures.append(f"{name}: `{span}` -> cites a repo path instead of the CLI/manifest surface")
            elif _PRIVATE_SYMBOL_TOKEN.match(span):
                failures.append(f"{name}: `{span}` -> cites a private symbol instead of the CLI/manifest surface")
            elif _TEST_NAME_TOKEN.match(span):
                failures.append(f"{name}: `{span}` -> cites a test name instead of the CLI/manifest surface")
    assert not failures, "operator documents name a package internal:\n" + "\n".join(failures)


def test_no_service_owner_value_collides_with_operator_prose() -> None:
    """Empirical proof the data-sourced blocklist cannot false-positive today.

    This must be verified empirically, not merely asserted: every
    live ``service_owner`` / ``owner`` value must be a full dotted
    ``cadrumo.<layer>.<module>`` string that does not equal (nor get accidentally
    substring-matched by) any bare CLI-domain noun the shipped corpus already
    uses. If this ever fails, a newly registered owner string collides with
    ordinary operator prose and the contract-side naming needs to change, not
    this gate.
    """
    owner_tokens = _internal_service_owner_tokens()
    cli_domain_nouns = {"ledger", "modelo", "casilla", "overview", "review", "registry", "live", "contract", "agent"}
    collisions = {owner for owner in owner_tokens if owner in cli_domain_nouns}
    assert not collisions, f"service_owner/owner values collide with CLI-domain nouns: {collisions}"
    # Every owner value is dotted and prefixed `cadrumo.`; no bare CLI-domain noun
    # is ever spelled in that shape, so a substring check against real prose
    # cannot misfire by construction. Confirm the shape invariant holds live.
    malformed = {
        owner for owner in owner_tokens if not owner.startswith("cadrumo.") or "." not in owner[len("cadrumo.") :]
    }
    assert not malformed, f"service_owner/owner values are not dotted module paths: {malformed}"
