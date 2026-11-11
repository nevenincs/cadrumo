"""Small presentation primitives shared by command frontends."""

from __future__ import annotations

import contextlib
import io
import json
import sys
from typing import TYPE_CHECKING

import typer

from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.redaction.rules import redact_for_cli_output
from cadrumo.core.terminal_encoding import encode_terminal_text

if TYPE_CHECKING:
    from cadrumo.core.json_contract import ResolvedPreconditionAction

_PRECONDITION_ACTION_FIELDS = (
    "failed_condition_id",
    "evidence",
    "action",
    "argument_bindings",
    "missing_argument_names",
    "conditionality",
    "no_recovery_outcome",
)
_PRECONDITION_ALTERNATIVE_ACTIONS_FIELD = "alternative_actions"


def write_stderr(text: str, *, stream: io.TextIOBase | None = None) -> None:
    """Write a redacted, terminal-encoded line with a UTF-8 fallback when the stream supports it."""
    target = sys.stderr if stream is None else stream
    safe = encode_terminal_text(redact_for_cli_output(text))
    reconfigure = getattr(target, "reconfigure", None)
    if callable(reconfigure):
        with contextlib.suppress(Exception):
            reconfigure(encoding="utf-8", errors="strict")
    try:
        target.write(safe + "\n")
        target.flush()
    except UnicodeEncodeError:
        buffer = getattr(target, "buffer", None)
        if buffer is not None:
            buffer.write((safe + "\n").encode("utf-8", errors="replace"))
            buffer.flush()
        else:
            target.write(safe.encode("ascii", errors="replace").decode("ascii") + "\n")
            target.flush()


def activate_subcommand_output_language(ctx: typer.Context, language: OutputLanguage | None) -> None:
    """Apply a subcommand-supplied ``--output-language`` to the render path.

    ``--output-language`` on a subcommand short-circuits the root
    callback's ``--language`` flow; rather than re-parsing, override the
    Settings field directly and drop the cached language so any ``tr()``
    fired during the verb body resolves to the requested locale. The override
    is entered through ``ctx.with_resource`` so it unwinds with the command callback.
    """
    if language is None:
        return
    from cadrumo.core.config import override_settings
    from cadrumo.core.i18n.render import clear_output_language_cache

    ctx.with_resource(override_settings(cadrumo_output_language=language))
    clear_output_language_cache()


def precondition_action_lines(action: ResolvedPreconditionAction | None) -> tuple[str, ...]:
    """Render the exact resolved action DTO as stable machine-readable rows, without synthesising recovery prose.

    The primary action's rows come first. The ordered alternative actions add
    one row after them, and only when the verdict offers any.
    """
    if action is None:
        return ()
    document = action.model_dump(mode="json")
    field_names = (
        (*_PRECONDITION_ACTION_FIELDS, _PRECONDITION_ALTERNATIVE_ACTIONS_FIELD)
        if action.alternative_actions
        else _PRECONDITION_ACTION_FIELDS
    )
    return tuple(
        f"precondition_action.{field_name}\t"
        f"{json.dumps(document[field_name], ensure_ascii=False, sort_keys=True, separators=(',', ':'))}"
        for field_name in field_names
    )
