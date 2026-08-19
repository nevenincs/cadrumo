"""Secure operator secret input for custody commands.

Secrets reach the custody verbs through exactly three channels, never the
command line and never the process environment: interactive no-echo prompts on
the controlling terminal, a single bounded strict-JSON object read from standard
input under ``--secrets-stdin``, or the same object read exactly once from an
inherited file descriptor under ``--secrets-fd``. No secret value is ever
accepted as an ``argv`` option, so passphrases and recovery mnemonics never
appear in the process table, shell history, or logs.

Both machine channels read at most :data:`_MAX_SECRETS_BYTES` and validate the
parsed object against a strict ``extra="forbid"`` pydantic model whose secret
fields are :class:`~pydantic.SecretStr`, so a missing/extra field refuses and the
values never render in a repr. Parsing rejects a repeated object key at any
nesting depth (see :func:`_reject_duplicate_object_keys`) rather than silently
resolving it to its last occurrence, so the strict-parse contract is total: a
collision can never slip past ``extra="forbid"`` by being resolved before
pydantic sees the mapping. This module carries the passphrase channel for the
per-profile custody flows, ``config login`` foremost.

The descriptor channel exists because stdin is a shared, singular resource: a
caller that must also pipe a document, or that runs a verb from a supervisor
already owning stdin, has nowhere to put the passphrase but the environment,
and an environment variable is inherited by every child process, survives for
the whole process lifetime, and is readable from a crash dump or a CI log. A
descriptor is none of those: it is passed to one process, read once, and closed.
:func:`read_secrets_fd` enforces the "once" half by closing the descriptor as
soon as it has been read, including on every refusal path. A second read of a
still-closed number then fails at the operating system and refuses as
unreadable, rather than returning the empty payload that would otherwise be
indistinguishable from a caller supplying an empty secret.

The descriptor must be inherited from the parent. POSIX callers pass one with
``os.pipe()`` plus ``pass_fds``. On Windows arbitrary descriptors are not
inherited by :mod:`subprocess`; a caller there must inherit the underlying
handle and map it with :func:`msvcrt.open_osfhandle` before naming the resulting
number. That is a real portability cost of this channel and is stated rather
than papered over: ``--secrets-stdin`` remains the portable machine channel.
"""

from __future__ import annotations

import getpass
import json
import os
import sys
import warnings
from contextlib import suppress

from pydantic import BaseModel, ValidationError

from ....core.external_constants import UTF_8_ENCODING
from ....core.tty import stdin_is_tty
from .._errors import CliRefusedBoundaryError as _CliRefusedBoundaryError

_MAX_SECRETS_BYTES = 8192
"""Upper bound on a machine-channel secrets payload; a larger read refuses.

A recovery-key + passphrase JSON object is a few hundred bytes; the cap keeps a
malformed or hostile stream from being read unboundedly into memory. Shared by
the stdin and descriptor channels so the two cannot drift into different bounds.
"""

_RESERVED_OUTPUT_DESCRIPTORS = frozenset({1, 2})
"""Descriptors this channel refuses outright: standard output and standard error.

Reading from an output stream is a caller bug rather than a secret channel, and
on a host where those descriptors are attached to a console the read would block
rather than fail. Standard input is deliberately NOT reserved: it is a legitimate
readable descriptor, and refusing it would make ``--secrets-fd 0`` behave
differently from the ``--secrets-stdin`` spelling of the same thing.
"""


def _reject_duplicate_object_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Build a JSON object from ``pairs``, refusing a repeated key.

    Installed as :func:`json.loads`'s ``object_pairs_hook`` so it runs for
    every object the decoder builds, including nested ones. Plain
    :func:`json.loads` silently keeps the LAST occurrence of a duplicate key,
    which resolves the collision before the strict ``extra="forbid"`` model can
    ever observe it — a payload assembled from concatenated fragments or a
    templating bug could then silently rewrap the secret store under a value
    the caller never intended. The raised message names only the offending
    KEY (a static field name, e.g. ``"recovery_code"``), never a payload
    value, so no secret can reach it.
    """
    seen: set[str] = set()
    for key, _value in pairs:
        if key in seen:
            raise ValueError(f"duplicate key in secrets-stdin payload: {key!r}")
        seen.add(key)
    return dict(pairs)


def _validate_secrets_payload[SecretsModelT: BaseModel](
    raw: bytes,
    model: type[SecretsModelT],
    *,
    invalid_json_key: str,
    missing_fields_key: str,
) -> SecretsModelT:
    """Decode and strictly validate one machine-channel secrets payload.

    Shared by both machine channels so the bound, the duplicate-key refusal and
    the strict-model contract cannot drift apart between them; only the refusal
    keys differ, because a message naming the wrong flag sends the operator to a
    channel they did not use.
    """
    # The accepted key set travels with every refusal on this channel. It is
    # the CLI-boundary contract -- a refusal names what it would accept rather
    # than only what it rejected -- and it matters most here: this is the
    # channel a caller with no terminal MUST use, so "not a valid JSON object"
    # left the one operator who cannot be prompted with nothing to correct
    # towards. The names are the model's own declared fields, so they cannot
    # drift from what validation actually accepts. No value is ever included.
    expected_fields = ", ".join(model.model_fields)
    try:
        decoded = raw.decode(UTF_8_ENCODING)
        payload = json.loads(decoded, object_pairs_hook=_reject_duplicate_object_keys)
    except (ValueError, UnicodeDecodeError) as exc:
        raise _CliRefusedBoundaryError(
            translated_message=invalid_json_key,
            context={"expected_fields": expected_fields},
        ) from exc
    if not isinstance(payload, dict):
        raise _CliRefusedBoundaryError(
            translated_message=invalid_json_key,
            context={"expected_fields": expected_fields},
        )
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        raise _CliRefusedBoundaryError(
            translated_message=missing_fields_key,
            context={"expected_fields": expected_fields},
        ) from exc


def read_secrets_stdin[SecretsModelT: BaseModel](model: type[SecretsModelT]) -> SecretsModelT:
    """Read one bounded strict-JSON object from stdin and validate it against ``model``.

    The payload must be a single JSON object carrying exactly the fields ``model``
    declares (``extra="forbid"``). A payload larger than
    :data:`_MAX_SECRETS_BYTES`, invalid UTF-8, non-object JSON, malformed
    JSON, a repeated object key at any nesting depth (see
    :func:`_reject_duplicate_object_keys`), or a missing/unexpected field
    refuses with a localised :class:`CliRefusedBoundaryError`; the raw bytes
    are never echoed or logged.
    """
    raw = sys.stdin.buffer.read(_MAX_SECRETS_BYTES + 1)
    if len(raw) > _MAX_SECRETS_BYTES:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.custody.errors.secrets_stdin_too_large",
        )
    return _validate_secrets_payload(
        raw,
        model,
        invalid_json_key="cli.config.custody.errors.secrets_stdin_invalid_json",
        missing_fields_key="cli.config.custody.errors.secrets_stdin_missing_fields",
    )


def _read_descriptor_to_bound(descriptor: int, *, maximum_bytes: int) -> bytes:
    """Drain ``descriptor`` up to ``maximum_bytes`` + 1, then close it.

    Reads through :func:`os.read` rather than wrapping the descriptor in a
    buffered file object: a wrapper that is garbage-collected without an
    explicit close emits a ``ResourceWarning`` and, on some hosts, closes the
    descriptor a second time. The close happens here, unconditionally, so a
    refusal on a malformed payload still leaves no descriptor open onto the
    secret.

    A short read is not end of stream on a pipe, so the loop continues until
    :func:`os.read` returns empty or the bound is exceeded.
    """
    chunks: list[bytes] = []
    total = 0
    try:
        while total <= maximum_bytes:
            chunk = os.read(descriptor, maximum_bytes + 1 - total)
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
    finally:
        # An already-closed descriptor is not a failure to report: the read
        # result stands and there is nothing left to release.
        with suppress(OSError):
            os.close(descriptor)
    return b"".join(chunks)


def read_secrets_fd[SecretsModelT: BaseModel](model: type[SecretsModelT], *, descriptor: int) -> SecretsModelT:
    """Read one bounded strict-JSON secrets object from ``descriptor``, exactly once.

    The one-shot contract is the reason this exists as its own channel rather
    than a stdin variant: the descriptor is closed as soon as it has been read,
    on the success path and on every refusal path alike, so the secret is not
    left behind a descriptor the process still holds open.

    The close IS the enforcement, and deliberately no process-local register of
    consumed descriptor numbers stands beside it. Such a register looks like a
    stronger guarantee and is in fact a false one: the operating system reissues
    a freed descriptor number immediately, so the number a caller staged a
    SECOND, genuinely different secret behind is very often the number the first
    read just released. A number-keyed guard refuses that legitimate second
    channel and blames the caller for a collision the platform created — which
    is exactly what a verb collecting two secrets, a bundle passphrase and a new
    profile passphrase, would hit on its first run. The case the register was
    meant to catch is already covered more precisely: reading a closed
    descriptor fails at the operating system and surfaces as
    ``secrets_fd_unreadable``, never as an empty payload.

    ``descriptor`` itself is a small integer on ``argv``; the secret is not.
    Standard output and standard error are refused (:data:`_RESERVED_OUTPUT_DESCRIPTORS`)
    because reading an output stream is a caller bug that would block rather
    than fail on a console-attached host. A descriptor that is not open, not
    readable, or not inherited refuses with its own message rather than the
    payload-shaped ones, so an inheritance mistake is not reported as a JSON
    fault.
    """
    if descriptor < 0 or descriptor in _RESERVED_OUTPUT_DESCRIPTORS:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.custody.errors.secrets_fd_reserved_stream",
            context={"descriptor": str(descriptor)},
        )
    try:
        raw = _read_descriptor_to_bound(descriptor, maximum_bytes=_MAX_SECRETS_BYTES)
    except OSError as exc:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.custody.errors.secrets_fd_unreadable",
            context={"descriptor": str(descriptor)},
        ) from exc
    if len(raw) > _MAX_SECRETS_BYTES:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.custody.errors.secrets_fd_too_large",
        )
    return _validate_secrets_payload(
        raw,
        model,
        invalid_json_key="cli.config.custody.errors.secrets_fd_invalid_json",
        missing_fields_key="cli.config.custody.errors.secrets_fd_missing_fields",
    )


def resolve_secrets_channel(*, secrets_stdin: bool, secrets_fd: int | None) -> None:
    """Refuse an invocation naming both machine secret channels at once.

    Two channels supplying one passphrase is not a precedence question with a
    safe answer: whichever loses is a secret the caller staged and this process
    never consumed, left resident in a pipe the caller believes was drained.
    The refusal names both flags so the caller knows which one to drop.
    """
    if secrets_stdin and secrets_fd is not None:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.custody.errors.secrets_channel_conflict",
        )


def _stdin_is_a_real_console() -> bool:
    """Return whether stdin is a genuine console, not merely a character device.

    ``isatty()`` is necessary but NOT sufficient on Windows. Both the ``NUL``
    device and a console-less host (a ``DETACHED_PROCESS`` spawn) report
    ``isatty() == True`` and ``GetFileType() == FILE_TYPE_CHAR`` while no
    console input queue exists behind them — so ``msvcrt.getwch()``, which
    :func:`getpass.getpass` calls on win32, BLOCKS FOREVER rather than
    returning or raising. A prompt that hangs is worse than one that refuses,
    and the operator has no way to tell the two apart.

    ``GetConsoleMode`` succeeds only for a real console handle and fails with
    ``ERROR_INVALID_HANDLE`` for both non-console cases, which discriminates
    them exactly. This is verified by probe rather than assumed: on this
    platform a real console returns mode ``0x1f7``, while ``NUL`` and a
    detached host both fail.

    Fails CLOSED. When the check cannot be completed the answer is "not a
    console", because the whole point is to never reach a promptable-looking
    channel that cannot actually be typed into. On non-win32, ``isatty()`` is
    trusted: :func:`getpass.unix_getpass` opens the terminal device itself and
    surfaces a real failure instead of blocking.
    """
    if sys.platform != "win32":
        return True
    try:
        import ctypes
        import msvcrt
        from ctypes import wintypes

        # TYPE-IGNORE-RATIONALE-PLATFORM-WINDOWS-CTYPES:
        # get_osfhandle and WinDLL are Windows-only, absent from cross-platform stubs.
        handle = msvcrt.get_osfhandle(sys.stdin.fileno())  # type: ignore[attr-defined]  # reason: TYPE-IGNORE-RATIONALE-PLATFORM-WINDOWS-CTYPES: get_osfhandle and WinDLL are Windows-only, absent from cross-platform stubs
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]  # reason: TYPE-IGNORE-RATIONALE-PLATFORM-WINDOWS-CTYPES, same Windows-only gate as the get_osfhandle call above
        kernel32.GetConsoleMode.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel32.GetConsoleMode.restype = wintypes.BOOL
        mode = wintypes.DWORD()
        return bool(kernel32.GetConsoleMode(wintypes.HANDLE(handle), ctypes.byref(mode)))
    except (OSError, ValueError, AttributeError, ImportError):
        return False


def terminal_can_prompt_for_secrets() -> bool:
    """Whether a hardened no-echo secret prompt can actually be shown here.

    The precondition :func:`prompt_secret_no_echo` enforces, exposed so a
    caller can decide WHETHER to route through that prompt without having
    to re-derive when it would refuse. A second derivation would drift
    from the refusal it is supposed to predict, which is the whole reason
    this is one predicate rather than a repeated pair of checks.

    A caller that simply wants to prompt should call
    :func:`prompt_secret_no_echo` directly and let it refuse; this exists
    for the caller choosing between the hardened prompt and a different
    channel entirely.
    """
    return stdin_is_tty() and _stdin_is_a_real_console()


def write_to_controlling_terminal(text: str) -> None:
    """Display ``text`` on the controlling terminal, bypassing ``stdout``.

    The counterpart to :func:`prompt_secret_no_echo`: that reads a secret the
    operator holds, this shows one the application minted. A recovery mnemonic
    is the case it exists for, and it is the reason this cannot go through the
    ordinary render path. Everything the CLI prints normally is capturable --
    ``> file`` redirects it, ``--format json`` folds it into an envelope a
    caller will persist, a supervisor tees it into a log. A 24-word mnemonic is
    a BEARER credential over the taxpayer's whole encrypted store, so writing
    it anywhere durable is the exact defect the channel exists to prevent.

    Opening the terminal DEVICE directly (``CONOUT$`` on Windows, ``/dev/tty``
    elsewhere) resolves to the operator's screen no matter what the standard
    streams were rebound to, so the words reach a human and nothing else.

    This refuses rather than degrading. If there is no controlling terminal --
    a pipe, a CI job, a supervised child -- there is nowhere safe to show the
    secret, and falling back to ``stdout`` would write the bearer credential
    into precisely the captured stream this bypasses. A caller that cannot
    display a mnemonic must refuse the operation that mints one, not proceed
    with the operator none the wiser.

    The precondition is :func:`terminal_can_prompt_for_secrets`, NOT whether
    the device happens to open. Opening is not evidence a human is watching:
    Windows hands a detached process a freshly allocated console, so ``CONOUT$``
    opens and the write "succeeds" onto a surface nobody can see. That failure
    is worse than a refusal rather than milder -- the operator is told their
    profile is enrolled for recovery while the only copy of the words went to a
    phantom console -- so this reuses the same predicate that decides whether a
    secret may be PROMPTED for, instead of growing a second notion of what
    counts as an attached terminal.

    Raises:
        CliRefusedBoundaryError: When no interactive terminal is attached, or
            the device cannot be opened.
    """
    if not terminal_can_prompt_for_secrets():
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.custody.errors.no_controlling_terminal_for_secret",
        )
    device = "CONOUT$" if sys.platform == "win32" else "/dev/tty"
    try:
        # newline="" keeps the device's own line discipline: the console is a
        # DEVICE, not a tracked artefact, and forcing LF degrades Windows
        # console rendering.
        with open(device, "w", encoding="utf-8", newline="") as terminal:
            terminal.write(text)
            terminal.write("\n")
            terminal.flush()
    except OSError as exc:
        raise _CliRefusedBoundaryError(
            translated_message="cli.config.custody.errors.no_controlling_terminal_for_secret",
        ) from exc


def prompt_secret_no_echo(prompt: str) -> str:
    """Read one secret from the controlling terminal with echo suppressed.

    ``prompt`` is the already-localised prompt text (callers pass ``tr(...)`` so
    the catalogue key stays statically discoverable). The typed value is never
    echoed: when echo suppression cannot be guaranteed this refuses
    (``REFUSED``, exit 2) rather than degrading to a visible read, and when the
    channel is not a real console it refuses rather than reaching a prompt that
    would block forever (see :func:`_stdin_is_a_real_console`).

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
    if not terminal_can_prompt_for_secrets():
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
    "read_secrets_fd",
    "read_secrets_stdin",
    "resolve_secrets_channel",
    "terminal_can_prompt_for_secrets",
    "write_to_controlling_terminal",
]
