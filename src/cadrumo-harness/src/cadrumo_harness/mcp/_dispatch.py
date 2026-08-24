"""Map MCP tool calls to Cadrumo CLI invocations.

Pure name and argv mapping: an MCP tool name round-trips to its registry command
key, and a command key plus operator-supplied arguments project onto the CLI argv
the server runs. The actual invocation lives in the server shell; this module is
deterministic and unit-tested.

The live serving path builds its argv from the command's per-verb input schema
via :func:`~entrypoints.cli._verb_input_schema.cli_argv_for` (named arguments in,
resolved CLI path out); :func:`tool_request_argv` remains the pure
``(command_key, cli_tokens) -> argv`` mapper the determinism-replay eval uses to
reconstruct a recorded raw-token call.
"""

from __future__ import annotations

from collections.abc import Iterable

_TOOL_PREFIX = "cadrumo_"

# The client-side namespace prefix a Claude plugin prepends to every tool name
# (``mcp__plugin_<plugin>_<server>__``). The plugin and the server are both named
# ``cadrumo``, so the budget accounts for both canonical product segments and
# the over-length verbs carry declared short forms.
CLIENT_NAME_PREFIX = "mcp__plugin_cadrumo_cadrumo__"
# The practical prefixed-name ceiling clients enforce.
TOOL_NAME_BUDGET = 64

# Declared short forms for the command-key segments that would otherwise overflow
# the budget. Applied to the underscored key; each is unambiguous (no two keys
# collapse to one name) and reversible through the forward-match resolver below.
_SEGMENT_ABBREVIATIONS: tuple[tuple[str, str], ...] = (
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

    ``modelo.work.calculate`` becomes ``cadrumo_modelo_work_calculate``. Declared
    short forms shrink the few command keys that would otherwise overflow the
    client-prefixed name budget (P4), e.g. ``modelo.review_package.verify.signature``
    becomes ``cadrumo_modelo_rpkg_verify_signature``.
    """
    underscored = command_key.replace(".", "_")
    for long_form, short_form in _SEGMENT_ABBREVIATIONS:
        underscored = underscored.replace(long_form, short_form)
    return _TOOL_PREFIX + underscored


def prefixed_tool_name_length(command_key: str) -> int:
    """Return the length of a command's tool name including the client prefix."""
    return len(CLIENT_NAME_PREFIX) + len(tool_name_for_command(command_key))


def command_key_for_tool(tool_name: str, *, command_keys: Iterable[str]) -> str | None:
    """Reverse a tool name to its registry command key.

    Segment-internal underscores (``iva_wallet``) make a naive ``_`` -> ``.``
    inverse ambiguous, so the reverse is resolved against the known command-key
    set: the unique key whose forward mapping equals ``tool_name``.
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
    :func:`~entrypoints.cli._verb_input_schema.cli_argv_for`; this mapper serves
    the determinism-replay eval, which records raw CLI-token calls.
    """
    return ["--format", "json", *_cli_path_tokens(command_key), *args]
