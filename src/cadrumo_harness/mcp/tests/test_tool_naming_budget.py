"""Every prefixed MCP tool name fits the client budget without renaming a fitting tool.

A Claude plugin prepends ``mcp__plugin_<plugin>_<server>__`` to every tool name;
with the plugin and server both named ``cadrumo`` that prefix is 29 characters, so a
long command key can push the client-visible name past the practical 64-char
ceiling. Clients call tools by name, so a name that fits is a published identifier:
only an over-length name may be shortened, and the shortened form must depend on
its own command key alone.

This gate asserts, over the live command graph, that every name is within budget,
charset-valid, unique and reversible; that every name the frozen legacy rendering
already fitted is byte-identical; and that the digest fallback is stable and
separates siblings sharing a prefix.
"""

from __future__ import annotations

import hashlib
import re

import pytest
from mcp.shared.tool_name_validation import TOOL_NAME_REGEX

from ..command_surface import command_surface
from ..dispatch import (
    CLIENT_NAME_PREFIX,
    TOOL_NAME_BUDGET,
    command_key_for_tool,
    prefixed_tool_name_length,
    tool_name_for_command,
)
from ..tools import build_tool_descriptors

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

#: The client-visible tool-name pattern: the SDK admits ``.`` as well, but the
#: client-prefixed name clients enforce is letters, digits, ``_`` and ``-`` only.
_CLIENT_TOOL_NAME = re.compile(rf"^[A-Za-z0-9_-]{{1,{TOOL_NAME_BUDGET}}}$")

#: The segment short forms as they stood when tool names were first published.
#: A frozen oracle, deliberately not imported from the implementation: editing
#: the production table would rename a published tool, and this copy is what
#: detects that.
_LEGACY_SEGMENT_SHORT_FORMS: tuple[tuple[str, str], ...] = (
    ("profile_archive_reconcile", "prof_arch_recon"),
    ("spreadsheet", "sheet"),
    ("bienes_inversion", "binv"),
    ("encrypt_for_recipient", "enc_rcpt"),
    ("encrypt_feedback", "enc_feedback"),
    ("verify_signature", "verify_sig"),
    ("credential_source", "credsrc"),
    ("verification_report", "vreport"),
    ("invoice_catalogue", "invcat"),
    ("mark_delivered_to_payer", "payer_delivered"),
    ("mark_locally_completed", "local_done"),
    ("preview_maritime_exemption", "maritime"),
    ("certificate", "cert"),
    ("diagnostics", "diag"),
    ("capabilities", "caps"),
    ("descendiente", "desc"),
    ("participation", "part"),
    ("prorrata", "pror"),
    ("filing_record", "filerec"),
    ("compare_taxation", "tax_compare"),
    ("notifications", "notif"),
    ("iva_wallet", "ivaw"),
    ("apoderado", "apod"),
    ("recipient", "rcpt"),
    ("telemetry", "telem"),
    ("borrador", "draft"),
    ("sync_calc", "synccalc"),
    ("google", "g"),
    ("archive", "arc"),
    ("reset_progress", "resetprog"),
    ("observe_local", "observe"),
    ("scopes", "scope"),
    ("secret", "sec"),
    ("inventory", "inv"),
    ("valuation", "val"),
    ("movement", "mov"),
    ("sandbox", "sbx"),
    ("integrity", "intg"),
    ("review_package", "rpkg"),
    ("subject_access_request", "sar"),
    ("certificate_secret", "cert_secret"),
    ("closing-authority", "closeauth"),
    ("counterparty", "cparty"),
    ("attachment", "attach"),
    ("evidence", "evid"),
    ("consent", "cnst"),
    ("document", "doc"),
    ("complete", "cmpl"),
)

_DIGEST_HEX_LENGTH = 8


def _legacy_tool_name(command_key: str) -> str:
    """Reproduce the published rendering: underscore the key, apply the short forms, prefix it."""
    underscored = command_key.replace(".", "_")
    for long_form, short_form in _LEGACY_SEGMENT_SHORT_FORMS:
        underscored = underscored.replace(long_form, short_form)
    return f"cadrumo_{underscored}"


def _fits(tool_name: str) -> bool:
    return len(CLIENT_NAME_PREFIX) + len(tool_name) <= TOOL_NAME_BUDGET


def _graph_keys() -> list[str]:
    return [ref.command for ref in command_surface().command_schema_refs()]


def _exposable_keys() -> list[str]:
    return [descriptor.command_key for descriptor in build_tool_descriptors()]


def test_every_prefixed_tool_name_is_within_budget() -> None:
    over = [key for key in _exposable_keys() if prefixed_tool_name_length(key) > TOOL_NAME_BUDGET]
    assert over == [], f"tool names over the {TOOL_NAME_BUDGET}-char client budget: {over}"


def test_every_graph_tool_name_is_in_budget_charset_valid_and_unique() -> None:
    keys = _graph_keys()
    assert len(set(keys)) == len(keys)
    names = {key: tool_name_for_command(key) for key in keys}
    invalid = {
        key: name
        for key, name in names.items()
        if not _fits(name)
        or TOOL_NAME_REGEX.fullmatch(name) is None
        or _CLIENT_TOOL_NAME.fullmatch(CLIENT_NAME_PREFIX + name) is None
    }
    assert invalid == {}
    assert len(set(names.values())) == len(names)


def test_every_name_the_legacy_rendering_fitted_is_unchanged() -> None:
    keys = _graph_keys()
    fitting = [key for key in keys if _fits(_legacy_tool_name(key))]
    renamed = {
        key: tool_name_for_command(key) for key in fitting if tool_name_for_command(key) != _legacy_tool_name(key)
    }
    assert renamed == {}
    # Positive control: the live graph does carry over-length keys, so the
    # fallback is exercised here rather than only on a synthetic key.
    overflowing = [key for key in keys if not _fits(_legacy_tool_name(key))]
    assert overflowing
    for key in overflowing:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:_DIGEST_HEX_LENGTH]
        name = tool_name_for_command(key)
        assert name.endswith(f"_{digest}"), (key, name)
        assert _legacy_tool_name(key).startswith(name.removesuffix(f"_{digest}")), (key, name)


def test_every_tool_name_reverses_to_its_command_key() -> None:
    descriptors = build_tool_descriptors()
    keys = [descriptor.command_key for descriptor in descriptors]
    for descriptor in descriptors:
        assert descriptor.name == tool_name_for_command(descriptor.command_key)
        assert command_key_for_tool(descriptor.name, command_keys=keys) == descriptor.command_key


def test_an_over_length_key_gets_a_stable_digest_name_distinct_from_its_sibling() -> None:
    # Deliberately not registered commands: only the derivation is proven here.
    deep = "modelo.work.some_very_long_new_subcommand_that_would_overflow_the_budget"
    sibling = "modelo.work.some_very_long_new_subcommand_that_would_overflow_the_budget_too"
    assert not _fits(_legacy_tool_name(deep))
    assert not _fits(_legacy_tool_name(sibling))

    first, second = tool_name_for_command(deep), tool_name_for_command(deep)
    other = tool_name_for_command(sibling)
    assert first == second
    assert prefixed_tool_name_length(deep) == len(CLIENT_NAME_PREFIX) + len(first) <= TOOL_NAME_BUDGET
    assert first != other
    digest_width = len("_") + _DIGEST_HEX_LENGTH
    assert first[:-digest_width] == other[:-digest_width]
    assert first.endswith("_" + hashlib.sha256(deep.encode("utf-8")).hexdigest()[:_DIGEST_HEX_LENGTH])
    assert command_key_for_tool(first, command_keys=[sibling, deep]) == deep
    assert command_key_for_tool(other, command_keys=[deep, sibling]) == sibling

    assert tool_name_for_command("modelo.work.calculate") == "cadrumo_modelo_work_calculate"
