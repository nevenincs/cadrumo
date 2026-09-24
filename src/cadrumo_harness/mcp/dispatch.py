"""Map MCP tool calls to Cadrumo CLI invocations.

Pure name and argv mapping: an MCP tool name round-trips to its registry command
key, and a command key plus operator-supplied arguments project onto the CLI argv
the server runs. The actual invocation lives in the server shell; this module is
deterministic and unit-tested.

The live serving path builds its argv from the command's per-verb input schema
via the application command port (named arguments in,
resolved CLI path out); :func:`tool_request_argv` remains the pure
``(command_key, cli_tokens) -> argv`` mapper the determinism-replay eval uses to
reconstruct a recorded raw-token call.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable

_TOOL_PREFIX = "cadrumo_"

# The client-side namespace prefix a Claude plugin prepends to every tool name
# (``mcp__plugin_<plugin>_<server>__``). The plugin and the server are both named
# ``cadrumo``, so the budget accounts for both canonical product segments.
CLIENT_NAME_PREFIX = "mcp__plugin_cadrumo_cadrumo__"
# The practical prefixed-name ceiling clients enforce.
TOOL_NAME_BUDGET = 64
# The longest server-side tool name that still fits the client budget.
_TOOL_NAME_LIMIT = TOOL_NAME_BUDGET - len(CLIENT_NAME_PREFIX)
# Hex digits of the command-key digest that disambiguate a shortened name.
_DIGEST_HEX_LENGTH = 8
_DIGEST_SEPARATOR = "_"

# Short forms for command-key segments, applied to the underscored key. Clients
# call tools by name, so these are frozen: editing one renames every tool that
# already fits the budget. A new over-length key needs no entry here; the digest
# fallback in :func:`tool_name_for_command` shortens it.
_SEGMENT_ABBREVIATIONS: tuple[tuple[str, str], ...] = (
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


def tool_name_for_command(command_key: str) -> str:
    """Render a registry command key as a namespaced MCP tool name.

    ``modelo.work.calculate`` becomes ``cadrumo_modelo_work_calculate``, with the
    frozen segment short forms applied, e.g. ``modelo.review_package.verify.signature``
    becomes ``cadrumo_modelo_rpkg_verify_signature``. When that rendering would
    overflow the client-prefixed budget, it is cut to a prefix and suffixed with
    the first hex digits of the SHA-256 of the command key, so the name depends on
    that key alone and stays within budget.
    """
    underscored = command_key.replace(".", "_")
    for long_form, short_form in _SEGMENT_ABBREVIATIONS:
        underscored = underscored.replace(long_form, short_form)
    rendered = _TOOL_PREFIX + underscored
    if len(rendered) <= _TOOL_NAME_LIMIT:
        return rendered
    digest = hashlib.sha256(command_key.encode("utf-8")).hexdigest()[:_DIGEST_HEX_LENGTH]
    stem = rendered[: _TOOL_NAME_LIMIT - len(_DIGEST_SEPARATOR) - _DIGEST_HEX_LENGTH].rstrip("_-")
    return f"{stem}{_DIGEST_SEPARATOR}{digest}"


def prefixed_tool_name_length(command_key: str) -> int:
    """Return the length of a command's tool name including the client prefix."""
    return len(CLIENT_NAME_PREFIX) + len(tool_name_for_command(command_key))


def command_key_for_tool(tool_name: str, *, command_keys: Iterable[str]) -> str | None:
    """Reverse a tool name to its registry command key.

    Segment-internal underscores (``iva_wallet``), short forms, and digest-shortened
    names make a textual inverse impossible, so the reverse is resolved against the
    known command-key set: the unique key whose forward mapping equals ``tool_name``.
    """
    return next((key for key in command_keys if tool_name_for_command(key) == tool_name), None)


def _cli_path_tokens(command_key: str) -> list[str]:
    """Project a registry command key onto its CLI path tokens.

    ``config.*`` and ``app.live.*`` keys carry their own leading root segment;
    every other key is a child of ``app``.
    """
    tokens = command_key.split(".")
    if tokens[0] in {"config", "app"}:
        return tokens
    return ["app", *tokens]


def tool_request_argv(command_key: str, args: Iterable[str]) -> list[str]:
    """Build the CLI argv for a recorded raw-token tool call.

    ``--format json`` is a root option (it precedes the command path), so the
    machine envelope is always requested. The pre-resolved ``args`` tokens are
    appended after the command path. The live serving path instead builds its
    argv from the per-verb schema via
    application command-port projection; this mapper serves
    the determinism-replay eval, which records raw CLI-token calls.
    """
    return ["--format", "json", *_cli_path_tokens(command_key), *args]
