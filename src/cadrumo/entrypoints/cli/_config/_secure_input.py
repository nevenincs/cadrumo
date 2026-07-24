"""Secure operator secret input for custody commands.

Secrets reach the custody verbs through exactly two channels, never the
command line: interactive no-echo prompts on the controlling terminal, or a
single bounded strict-JSON object read from standard input under
``--secrets-stdin``. No secret value is ever accepted as an ``argv`` option, so
passphrases and recovery mnemonics never appear in the process table, shell
history, or logs.

The stdin channel reads at most :data:`_MAX_SECRETS_STDIN_BYTES` and validates
the parsed object against a strict ``extra="forbid"`` pydantic model whose secret
fields are :class:`~pydantic.SecretStr`, so a missing/extra field refuses and the
values never render in a repr. This module wraps
:class:`~cadrumo.adapters.persistence.storage.master_key` custody flows such as
``config passphrase change`` and ``config recovery verify`` / ``config recover``.
"""

from __future__ import annotations

import getpass
import json
import sys
import warnings

from pydantic import BaseModel, ValidationError

from ....core.external_constants import UTF_8_ENCODING
from .._errors import CliRefusedBoundaryError as _CliRefusedBoundaryError

_MAX_SECRETS_STDIN_BYTES = 8192
"""Upper bound on a ``--secrets-stdin`` payload; a larger read refuses.

A recovery-key + passphrase JSON object is a few hundred bytes; the cap keeps a
malformed or hostile stream from being read unboundedly into memory.
"""


def read_secrets_stdin[SecretsModelT: BaseModel](model: type[SecretsModelT]) -> SecretsModelT:
    """Read one bounded strict-JSON object from stdin and validate it against ``model``.

    The payload must be a single JSON object carrying exactly the fields ``model``
    declares (``extra="forbid"``). A payload larger than
    :data:`_MAX_SECRETS_STDIN_BYTES`, invalid UTF-8, non-object JSON, malformed
    JSON, or a missing/unexpected field refuses with a localised
    :class:`CliRefusedBoundaryError`; the raw bytes are never echoed or logged.
    """
    raw = sys.stdin.buffer.read(_MAX_SECRETS_STDIN_BYTES + 1)
    if len(raw) > _MAX_SECRETS_STDIN_BYTES:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.custody.errors.secrets_stdin_too_large",
        )
    try:
        decoded = raw.decode(UTF_8_ENCODING)
        payload = json.loads(decoded)
    except (ValueError, UnicodeDecodeError) as exc:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.custody.errors.secrets_stdin_invalid_json",
        ) from exc
    if not isinstance(payload, dict):
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.custody.errors.secrets_stdin_invalid_json",
        )
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.custody.errors.secrets_stdin_missing_fields",
        ) from exc


def write_to_controlling_terminal(text: str) -> None:
    """Write ``text`` directly to the controlling terminal, never a redirected stream.

    Used by the recovery ``create`` / ``rotate`` verbs to display a candidate
    recovery code exactly once: the words must reach the operator's terminal
    and MUST NOT ride stdout (a redirected stdout, a JSON envelope, or a log
    would serialize the secret). Refuses cleanly when no interactive terminal
    is attached, mirroring :func:`prompt_secret_no_echo`.
    """
    if not sys.stdin.isatty():
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.custody.errors.non_interactive_secret_required",
        )
    device = "CONOUT$" if sys.platform == "win32" else "/dev/tty"
    try:
        with open(device, "w", encoding=UTF_8_ENCODING) as terminal:
            terminal.write(text)
            terminal.flush()
    except OSError as exc:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.custody.errors.non_interactive_secret_required",
        ) from exc


def prompt_secret_no_echo(prompt: str) -> str:
    """Read one secret from the controlling terminal with echo suppressed.

    ``prompt`` is the already-localised prompt text (callers pass ``tr(...)`` so
    the catalogue key stays statically discoverable). The typed value is never
    echoed: when echo suppression cannot be guaranteed this refuses
    (``REFUSED``, exit 2) rather than degrading to a visible read.

    :func:`getpass.getpass` silently falls back to an *echoing* read
    (``fallback_getpass``) whenever it cannot control the terminal — on Windows
    when ``sys.stdin`` has been rebound away from ``sys.__stdin__`` or ``msvcrt``
    is unavailable, and on POSIX when the descriptor cannot be resolved or
    ``termios`` refuses. Two guards close that: the ``sys.__stdin__`` identity
    precondition (checked where the stdlib itself branches on it), and promoting
    :class:`getpass.GetPassWarning` to an exception, which ``fallback_getpass``
    emits as its *first* statement — so the refusal fires before any character is
    read or displayed, covering every fallback route including ones this module
    cannot predict.

    :func:`warnings.catch_warnings` is not thread-safe, which is sound here: this
    is a blocking interactive read on a single-threaded CLI process.
    """
    if not sys.stdin.isatty():
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.custody.errors.non_interactive_secret_required",
        )
    if sys.platform == "win32" and sys.stdin is not sys.__stdin__:
        # win_getpass dispatches to the echoing fallback on exactly this
        # condition; isatty() does not detect it. POSIX is excluded because
        # unix_getpass opens /dev/tty itself and suppresses echo regardless.
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.custody.errors.echo_suppression_unavailable",
        )
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            return getpass.getpass(prompt)
    except getpass.GetPassWarning as exc:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.custody.errors.echo_suppression_unavailable",
        ) from exc
    except EOFError as exc:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.custody.errors.non_interactive_secret_required",
        ) from exc
    except OSError as exc:
        # A console-less terminal layer can fail the underlying msvcrt/tty call;
        # surface this module's own refusal instead of the generic boundary.
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.custody.errors.echo_suppression_unavailable",
        ) from exc


__all__ = [
    "prompt_secret_no_echo",
    "read_secrets_stdin",
    "write_to_controlling_terminal",
]
