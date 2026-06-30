"""Co-commit drift gate for the operator harness rule surface.

The operator operating rules name concrete CLI verbs and JSON-envelope fields.
If a verb is renamed or an envelope field moves and the rule is not updated in the
same change, the operator inherits a dead instruction - the exact failure mode the
``aeat-cli-pull-and-file-standard`` rule exists to prevent, here on the operator
side. This gate parses every shipped operator rule, extracts each ``aeat ...``
command path and each named envelope-spine field, and asserts they all resolve
against the live CLI surface and the real envelope models. A rule that cites a
non-existent verb or field fails the gate.
"""

from __future__ import annotations

import re

import pytest

from ...application.operator_surface import (
    CommandSchemaRef,
    build_operator_surface_manifest,
)
from ...core.json_contract import ENVELOPE_SCHEMA_VERSION, Notice, SchemaEnvelope
from .. import iter_operator_rules, iter_personas, iter_skill_documents

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_BACKTICK = re.compile(r"`([^`]+)`")
# A subcommand token: lowercase, digits, and hyphens only. Flags (``--x``),
# placeholders (``<id>``), and argument values (``130``, ``1T``) do not match and
# stop command-path collection.
_SUBCOMMAND = re.compile(r"^[a-z][a-z0-9-]*$")
# Envelope-spine / notice field names a rule may cite in backticks. Each must be a
# real field on the model named here, or the rule is teaching a phantom field.
_ENVELOPE_FIELDS = frozenset(SchemaEnvelope.model_fields)
_NOTICE_FIELDS = frozenset(Notice.model_fields)


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
    # the surface an operator's `aeat app contract` would.
    from ...entrypoints.cli._app_contract import _command_schema_refs

    return _command_schema_refs()


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


def test_operator_rules_exist() -> None:
    docs = _rule_documents()
    assert docs, "no operator rule documents are shipped under _data/agent/rules"
    names = {name for name, _ in docs}
    assert "operator-operating-rules.md" in names


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


def test_cited_envelope_spine_fields_still_exist() -> None:
    # The rules instruct the operator to read specific envelope/notice fields.
    # Assert each still exists on the live model, so a spine rename cannot leave
    # the rules teaching a field that moved.
    failures: list[str] = []
    for spine_field in ("schema_version", "command", "status", "result", "notices"):
        if spine_field not in _ENVELOPE_FIELDS:
            failures.append(f"envelope spine field '{spine_field}' no longer on SchemaEnvelope")
    for notice_field in ("severity", "code", "message", "suggestion", "context"):
        if notice_field not in _NOTICE_FIELDS:
            failures.append(f"notice field '{notice_field}' no longer on Notice")
    assert not failures, "\n".join(failures)
