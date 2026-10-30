"""Per-sequence hermetic sandbox runner for ``cli-sequence`` frames.

Each :class:`~dev.docs.sequences.schema.ParsedSequence` executes in FULL
isolation: a fresh real-crypto storage root (:func:`isolated_profile_storage_root`
with genuine password custody over an ephemeral deterministic test DEK),
the project-wide frozen instant :data:`SANDBOX_INSTANT`
(:func:`cadrumo.core.time.frozen_clock`), a deterministic injected profile
identity :data:`SANDBOX_PROFILE_ID` published through the canonical capsule
writer (:class:`~cadrumo.application.user_profile.lifecycle.ProfileCapsuleLifecycle`,
with facts merged by
:func:`~cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime.upsert_test_profile_facts` inside
:func:`~cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime.open_test_profile_session` — never a
parallel write path), English output pinned via the central settings surface,
and the live-AEAT gate off. Frames are invoked in-process through the cached
Click tree (:func:`~cadrumo.entrypoints.cli.tests.cli_runner.invoke_cached_cli`). Sequences never
share state — not across pages and not within a page.

Capture threading: after a frame executes, each of its
:class:`~dev.docs.sequences.schema.CaptureBinding` json-paths is read from the
frame's parsed JSON envelope and bound; later frames interpolate the bound value
into their ``{name}`` placeholder tokens before execution. A capture against
non-JSON output, a json-path missing from the envelope, a non-scalar or null
capture, and an undeclared non-zero exit code are all fail-fast
:class:`~dev.docs.sequences.errors.SequenceExecutionError` refusals — every
later frame would otherwise run against a corrupted premise.

Safety: a frame that would contact live
AEAT is refused BEFORE any execution. Detection is fail-closed over the argv
tokens: any non-option token equal to ``live`` or ``pull``, or starting with
``pull-``, marks the frame unenrollable (the ``pull`` verb family and the
``app live`` group are, by the CLI naming standard, exactly the live-AEAT read
surface). The sandbox additionally refuses to open while the live-test opt-in
is set, and never sets it.

Layering note: this docs-tooling engine deliberately consumes the shared
in-package test substrate — :mod:`cadrumo.entrypoints.cli.tests.cli_runner` and
:mod:`cadrumo.adapters.persistence.storage.tests.secure_sql` — rather than duplicating a second engine on
top of it. Both are public, non-underscore modules of the shipped
``cadrumo.tests`` package and are the canonical hermetic in-process
CLI/storage providers; duplicating them here would create the parallel write
path the composition rules forbid.

The typed :class:`SequenceTranscript` this module returns is the input contract
for the golden store and comparison layers: per frame it carries the argv as
executed, the exit code, the verbatim output, the parsed envelope document
(pre-mask) where the output is JSON, and the values captured from that frame.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import time
import warnings
from collections.abc import Callable, Generator, Mapping, Sequence
from contextlib import AbstractContextManager, contextmanager, nullcontext
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal, Unpack, cast

from click.testing import CliRunner, Result
from pydantic import BaseModel, Field, JsonValue

from cadrumo.adapters.persistence.storage.master_key.active_session import (
    active_session,
    current_active_bucket_session,
)
from cadrumo.adapters.persistence.storage.sql.engine import dispose_engine
from cadrumo.core.atomic_write import atomic_write_best_effort_text
from cadrumo.core.config import load_settings, override_settings
from cadrumo.core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from cadrumo.entrypoints.cli.command_schema import command_registration_for_node
from cadrumo.entrypoints.cli.command_specs import COMMAND_GRAPH
from cadrumo.entrypoints.cli.tests.cli_runner import semantic_cli_text
from cadrumo.tests.cli_fixture_ports import ClickInvokeKwargs
from cadrumo_client.contracts.command_ports import ProfileAuthenticationPosture
from cadrumo_runtime.host.tests.frontend.cli.cli_runner import cadrumo_click_command
from dev.temporary_output import prepare_temp_root

from .errors import SequenceExecutionError
from .sandbox import SequenceSandbox, _publish_replacement_sandbox_profile, sequence_sandbox
from .schema import (
    CommandProgram,
    FrameKind,
    Identifier,
    JsonPath,
    ParsedSequence,
    SequenceFrame,
    SequenceId,
)

_FRAME_OBSERVER: ContextVar[Callable[[int], AbstractContextManager[None]] | None] = ContextVar(
    "sequence_frame_observer", default=None
)


@contextmanager
def observe_sequence_frames(observer: Callable[[int], AbstractContextManager[None]]) -> Generator[None]:
    """Observe invocation durations without exposing arguments or captured outputs."""
    token = _FRAME_OBSERVER.set(observer)
    try:
        yield
    finally:
        _FRAME_OBSERVER.reset(token)


#: The ``@expect`` pseudo-path asserting a frame's process exit code.
_EXIT_CODE_PATH: str = "exit_code"

#: Argv tokens that mark a frame as live-AEAT and therefore unenrollable: the
#: ``app live`` group and the ``pull`` verb family are, per the CLI pull/file
#: naming standard, exactly the fetch-from-AEAT surface. The scan is
#: fail-closed: it inspects every non-option token, accepting that an option
#: VALUE spelled ``live``/``pull`` (which no current surface takes) would also
#: refuse — a false refusal is safe, a false pass is not.
_LIVE_TOKENS: frozenset[str] = frozenset({"live", "pull"})
_PULL_VERB_PREFIX: str = "pull-"

#: One json-path segment: a dotted key (an identifier or an all-digit object
#: key such as a casilla number), a ``[index]`` list address, or a bracketed
#: double-quoted ``["<key>"]`` literal object key (any char except a
#: double-quote). Group 1 = dotted key, group 2 = list index, group 3 = quoted
#: object key. The three forms are mutually exclusive per match.
_PATH_SEGMENT_RE = re.compile(r'([A-Za-z_][A-Za-z0-9_]*|[0-9]+)|\[([0-9]+)\]|\["([^"]*)"\]')

#: Transient registry-race markers: concurrent modification of the registry
#: TOML tree during local development produces these transient failures; the
#: frame invocation retries bounded on exactly these markers so a real
#: refusal is never masked.
_TRANSIENT_REGISTRY_RACE_MARKERS: tuple[str, ...] = (
    "registry directory changed during cache fingerprinting",
    "required-role gate",
    "duplicate catalogue ids",
    "references unknown source id",
)
_TRANSIENT_RETRY_ATTEMPTS: int = 8

#: An optional child-process handoff path.  The parent check supervisor owns
#: its lifetime; the runner only records the last frame that actually started.
#: It deliberately does not use a ``CADRUMO_*`` name because sandbox execution
#: correctly scrubs that operator-facing namespace.
_PROGRESS_JOURNAL_ENV: str = "CLI_SEQUENCE_PROGRESS_JOURNAL"
_SEQUENCE_PROGRESS_PAGE: ContextVar[str | None] = ContextVar("sequence_progress_page", default=None)

#: A captured value must be a non-null JSON scalar: it interpolates into a
#: later frame's argv, where an object, array, or null has no faithful text.
CapturedScalar = str | int | float | bool


class CapturedValue(BaseModel):
    """One value captured from a frame's parsed JSON envelope.

    ``value`` is the scalar read from ``json_path``; it is what later frames'
    ``{name}`` placeholders interpolate to.
    """

    model_config = _STRICT_FROZEN

    name: Identifier
    json_path: JsonPath
    value: CapturedScalar


#: Which stream carried a frame's parsed JSON envelope: the success envelope
#: rides stdout; the refusal error document (which shares the envelope spine,
#: per the CLI notices standard) rides stderr.
EnvelopeSource = Literal["stdout", "stderr"]


class FrameExecution(BaseModel):
    """The executed record of one sequence frame.

    ``command_line`` is the authored line (placeholders intact); ``argv`` is the
    command as actually executed, after ``{name}`` interpolation, leading with
    the ``aeat`` executable token. ``output`` is the verbatim stdout and
    ``stderr`` the verbatim stderr — recorded separately so a refusal's
    error document is a first-class, golden-able artifact. ``envelope`` is the
    parsed JSON document (the pre-mask captured
    :class:`~cadrumo.core.json_contract.SchemaEnvelope`), resolved
    stdout-first-then-stderr: a success envelope is emitted on stdout, a
    refusal's error document on stderr, and both share the envelope spine.
    ``envelope_source`` names the carrying stream (``None`` for a pure text
    frame).
    """

    model_config = _STRICT_FROZEN

    kind: FrameKind
    command_line: str
    argv: tuple[str, ...] = Field(min_length=1)
    exit_code: int
    output: str
    stderr: str = ""
    envelope: dict[str, JsonValue] | None = None
    envelope_source: EnvelopeSource | None = None
    captured: tuple[CapturedValue, ...] = Field(default=())


class SequenceTranscript(BaseModel):
    """The full execution transcript of one sequence in its sandbox.

    This is the typed input the golden store serializes and the comparison
    layer diffs. ``storage_root`` and ``workdir`` are per-run sandbox paths —
    they exist so text-frame normalisation can replace them with stable
    tokens; they are never golden content themselves.
    """

    model_config = _STRICT_FROZEN

    sequence_id: SequenceId
    profile_id: str
    frozen_instant: datetime
    storage_root: str
    workdir: str
    frames: tuple[FrameExecution, ...] = Field(min_length=1)

    @property
    def result_frame(self) -> FrameExecution:
        """The executed terminal ``@result`` frame (always the last frame)."""
        return self.frames[-1]

    @property
    def captures(self) -> dict[str, CapturedScalar]:
        """Every capture bound across the run, in frame order."""
        return {item.name: item.value for frame in self.frames for item in frame.captured}


@dataclass(frozen=True)
class _PageSeedState:
    """Immutable result of executing one named seed in a page sandbox."""

    frames: tuple[SequenceFrame, ...]
    executions: tuple[FrameExecution, ...]
    captures: tuple[CapturedValue, ...]


def _seed_execution_signature(frames: tuple[SequenceFrame, ...]) -> tuple[str, ...]:
    """Return the narration-independent executable identity of one seed."""
    return tuple(
        json.dumps(
            frame.model_dump(exclude={"source", "line_number", "step_description"}, mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        )
        for frame in frames
    )


def _frame_at(frame: SequenceFrame) -> str:
    """Render a frame's source/line locator prefix for a failure message."""
    if frame.source == "body":
        return f"line {frame.line_number}"
    return f"{frame.source} line {frame.line_number}"


@contextmanager
def _sequence_progress_scope(page: str) -> Generator[None]:
    """Bind the owning docs page while its sequences execute.

    The binding is invocation-scoped, so a child interpreter that checks more
    than one page cannot report a stale page after a prior sequence returns.
    """
    token = _SEQUENCE_PROGRESS_PAGE.set(page)
    try:
        yield
    finally:
        _SEQUENCE_PROGRESS_PAGE.reset(token)


def _record_frame_progress(
    sequence: ParsedSequence,
    frame: SequenceFrame,
    *,
    frame_index: int,
    argv: tuple[str, ...],
) -> None:
    """Persist the dynamically-derived last-started frame for a supervising child.

    Diagnostics stay outside :class:`SequenceTranscript`: the journal is a
    parent/child supervision aid, never sequence or golden data.  A single
    child executes frames serially, so replacing the sole record is sufficient
    and avoids accumulating an unbounded diagnostic log.
    """
    journal = os.environ.get(_PROGRESS_JOURNAL_ENV)
    page = _SEQUENCE_PROGRESS_PAGE.get()
    if journal is None or page is None:
        return
    payload = {
        "page": page,
        "sequence_id": sequence.sequence_id,
        "frame_index": frame_index,
        "frame_source": frame.source,
        "frame_line": frame.line_number,
        "argv": list(argv),
    }
    atomic_write_best_effort_text(
        Path(journal),
        json.dumps(payload, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def live_aeat_tokens(frame: SequenceFrame) -> tuple[str, ...]:
    """Return the argv tokens that mark ``frame`` as a live-AEAT invocation.

    A token immediately following an option token is treated as that option's
    value and skipped (so ``--file pull-history.csv`` never false-refuses); an
    ``=``-joined value rides its option token and is skipped with it. A bare
    positional value spelled ``live``/``pull`` would still refuse — the scan is
    deliberately fail-closed, and the refusal names the offending token so a
    false refusal is instantly diagnosable.
    """
    flagged: list[str] = []
    previous_was_option = False
    for token in frame.argv[1:]:
        if token.startswith("-"):
            previous_was_option = "=" not in token
            continue
        if previous_was_option or "{" in token:
            previous_was_option = False
            continue
        if token in _LIVE_TOKENS or token.startswith(_PULL_VERB_PREFIX):
            flagged.append(token)
    return tuple(flagged)


def refuse_live_frames(sequence: ParsedSequence) -> None:
    """Refuse the whole sequence when any EXECUTED frame would contact live AEAT.

    A ``@static`` frame is the sanctioned way to DISPLAY a live-AEAT command
    (it is never executed), so static frames are exempt; an executed frame
    (command / setup / result) that reads live AEAT is still refused.
    """
    violations = [
        f"{_frame_at(frame)}: {frame.command_line!r} is a live-AEAT invocation "
        f"(tokens {', '.join(live_aeat_tokens(frame))}); pull verbs and the "
        "'app live' group cannot be executed. Run build/verify/export frames, "
        "or show the live command as a @static frame instead"
        for frame in sequence.executed_frames
        if live_aeat_tokens(frame)
    ]
    if violations:
        raise SequenceExecutionError(sequence.sequence_id, "; ".join(violations))


def _interpolation_text(value: CapturedScalar) -> str:
    """Render a captured scalar as the text a placeholder interpolates to."""
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _resolved_argv(
    frame: SequenceFrame,
    captures: Mapping[str, CapturedScalar],
) -> tuple[str, ...]:
    """Interpolate the frame's ``{name}`` placeholders from bound captures.

    The parser has already proven every placeholder resolves to a strictly
    earlier frame's capture, so a missing binding here means the producing
    frame's capture failed — which the runner raises on at capture time.
    """
    resolved: list[str] = []
    for token in frame.argv:
        text = token
        for name in frame.placeholder_names:
            text = text.replace("{" + name + "}", _interpolation_text(captures[name]))
        resolved.append(text)
    return tuple(resolved)


def _expected_exit_code(frame: SequenceFrame, sequence_id: str) -> int:
    """Return the frame's declared exit-code expectation (default 0)."""
    declared = {assertion.expected for assertion in frame.expects if assertion.json_path == _EXIT_CODE_PATH}
    if not declared:
        return 0
    if len(declared) > 1:
        raise SequenceExecutionError(
            sequence_id,
            f"{_frame_at(frame)}: contradictory @expect {_EXIT_CODE_PATH} "
            f"assertions ({sorted(str(item) for item in declared)}); declare one",
        )
    only = declared.pop()
    # The parser enforces an integer literal on the exit_code pseudo-path; this
    # backstop keeps the runner honest against hand-built frames.
    if not isinstance(only, int) or isinstance(only, bool):
        raise SequenceExecutionError(
            sequence_id,
            f"{_frame_at(frame)}: @expect {_EXIT_CODE_PATH} value {only!r} must be an integer",
        )
    return only


def _parse_envelope(output: str) -> dict[str, JsonValue] | None:
    """Parse a frame's output as a JSON envelope document, or ``None`` for text."""
    try:
        document = json.loads(output)
    except json.JSONDecodeError:
        return None
    if not isinstance(document, dict):
        return None
    # ``json.loads`` types the mapping loosely; re-keying with ``str`` yields an
    # honestly-typed document (JSON object keys are always strings).
    return {str(key): value for key, value in document.items()}


def resolve_json_path(document: Mapping[str, object], path: str) -> tuple[bool, object]:
    """Walk a dotted/bracketed json-path; return ``(found, value)``.

    Segment-form resolution rules:

    * A dotted key: an all-digit segment (``.03``) is a string OBJECT KEY first
      — casilla numbers are JSON object keys — and is a list index only when the
      current node is a list; an identifier segment is an object key.
    * The bracketed integer form ``[n]`` is always and only a LIST INDEX.
    * The bracketed double-quoted form ``["<key>"]`` is always and only a
      literal OBJECT KEY (never a list index); on a non-Mapping node it misses
      cleanly, returning ``(False, None)``.
    """
    current: object = document
    for match in _PATH_SEGMENT_RE.finditer(path):
        key, index, quoted_key = match.group(1), match.group(2), match.group(3)
        if quoted_key is not None:
            found, current = _resolve_object_key(current, quoted_key)
            if not found:
                return False, None
            continue
        if key is not None:
            found, current = _resolve_dotted_segment(current, key)
            if not found:
                return False, None
            continue
        if not isinstance(current, list) or int(index) >= len(current):
            return False, None
        current = current[int(index)]
    return True, current


def _capture_values(
    frame: SequenceFrame,
    envelope: dict[str, JsonValue] | None,
    *,
    sequence_id: str,
    argv: tuple[str, ...],
    output: str,
) -> tuple[CapturedValue, ...]:
    """Resolve the frame's ``@capture`` bindings against its parsed envelope."""
    if not frame.captures:
        return ()
    if envelope is None:
        raise SequenceExecutionError(
            sequence_id,
            f"{_frame_at(frame)}: frame declares @capture but its output is not a "
            f"JSON document — invoke the command with '--format json' "
            f"(argv: {' '.join(argv)}; output starts: {output[:120]!r})",
        )
    captured: list[CapturedValue] = []
    for binding in frame.captures:
        found, value = resolve_json_path(envelope, binding.json_path)
        if not found:
            top_level = ", ".join(sorted(envelope))
            raise SequenceExecutionError(
                sequence_id,
                f"{_frame_at(frame)}: @capture {binding.name!r} path "
                f"{binding.json_path!r} is missing from the frame's envelope "
                f"(top-level keys: {top_level})",
            )
        if value is None or not isinstance(value, CapturedScalar):
            raise SequenceExecutionError(
                sequence_id,
                f"{_frame_at(frame)}: @capture {binding.name!r} path "
                f"{binding.json_path!r} resolved to {type(value).__name__}; a "
                "capture must be a non-null JSON scalar to interpolate into a "
                "later frame's command line",
            )
        captured.append(CapturedValue(name=binding.name, json_path=binding.json_path, value=value))
    return tuple(captured)


def _drop_handlers_bound_to_a_dead_stream() -> None:
    """Detach root handlers whose stream has been closed under them.

    Sibling eviction to the ``close_active_bucket_session()`` calls above, for
    the same reason and against the same hazard: this engine invokes the CLI
    IN-PROCESS, so state a real operator would discard with the process instead
    survives into the next frame.

    The mechanism, confirmed rather than assumed.
    :func:`cadrumo.core.logging.configure_logging` installs its stderr handler
    with ``"stream": "ext://sys.stderr"``, which ``dictConfig`` resolves to the
    stream object live AT THAT MOMENT, and the function is idempotent behind a
    module-global. The FIRST CLI invocation in the process therefore fixes the
    handler to whatever ``sys.stderr`` then was -- and every frame here runs
    under Click's ``CliRunner``, which has replaced it with a per-invocation
    capture buffer. That buffer dies with the frame; the handler does not. Every
    later log record is then written to a closed stream, and the stdlib prints
    its ``--- Logging error ---`` block to the real stderr, where it lands in the
    NEXT frame's captured output and diverges that frame's golden.

    This eviction is NOT what kept the goldens non-deterministic, and the
    paragraph above is not the whole account of that fault. The observed
    ``--- Logging error ---`` blocks came, every one of them, from the ROTATING
    FILE handler: it was bound at import time to the workstation's shared
    ``cadrumo.log``, and its rollover ``os.rename`` failed with WinError 32
    whenever a peer process held that file open. Widening this eviction to drop
    any handler not on the live ``sys.stderr`` therefore could not help — it
    detached the file handler, then the reconfigure immediately rebound it to
    the same contended path. That fault is fixed at its source, by giving each
    sequence its own storage root and so its own log file.

    Detaching here stays narrow on purpose, as a genuine dead-stream guard only:
    handlers whose own stream reports itself CLOSED are removed, so a handler on
    the real stderr, or on a live capture, is untouched. Eviction alone would
    leave the configure-once latch set and the root logger bare, so a rebind
    follows it.
    """
    from cadrumo.core.logging import configure_logging

    from ..logging_rebind import allow_logging_reconfiguration

    evicted = False
    for handler in list(logging.getLogger().handlers):
        stream = getattr(handler, "stream", None)
        if stream is not None and getattr(stream, "closed", False):
            logging.getLogger().removeHandler(handler)
            evicted = True

    if evicted:
        allow_logging_reconfiguration()
        configure_logging()


@contextmanager
def _next_process_session_view() -> Generator[None]:
    """Show a frame the session state a fresh ``aeat`` process would see.

    Every documented command is its own process, but the sandbox runs them in
    one: the capsule session opened for the whole span is what lets each frame
    reach the bucket. Logout seals that session in place, and a real next
    process would then find no session at all -- so once it is sealed, the
    following frames run with the session masked as absent rather than
    observing a sealed object no separate process could ever hold.
    """
    live = current_active_bucket_session()
    if live is None or not live.sealed:
        yield
        return
    with active_session.override(None):
        yield


def _invoke_frame(args: tuple[str, ...], *, program: CommandProgram) -> Result:
    """Invoke the cached CLI, retrying only on the transient registry-write race.

    The race exists only during local development, where concurrent
    modification of the registry TOML tree mid-load produces these transient
    failures; under CI the tree is static, so any marker match there is a
    genuine failure and the retry loop is skipped entirely rather than
    burning bounded-retry latency in front of it.
    """
    _drop_handlers_bound_to_a_dead_stream()
    # The synthetic capsule stays readable across a sequence through a
    # test-only active-profile override. Profile deletion is deliberately
    # sessionless, however, and must observe the durable selection retained
    # after logout rather than that provisioning override. Narrowly mask the harness
    # field for this exact leaf; every sibling retains the normal sandbox span.
    is_profile_delete = any(args[index : index + 3] == ("config", "profile", "delete") for index in range(len(args)))
    settings_context = override_settings(cadrumo_active_profile=None) if is_profile_delete else nullcontext()
    with settings_context, _next_process_session_view():
        result = _invoke_authenticated_frame(args, program=program)
    if bool(os.environ.get("CI")):
        return result
    tries = 1
    while (
        tries < _TRANSIENT_RETRY_ATTEMPTS
        and result.exit_code != 0
        and any(marker in result.output for marker in _TRANSIENT_REGISTRY_RACE_MARKERS)
    ):
        time.sleep(2)
        dispose_engine()
        result = _invoke_authenticated_frame(args, program=program)
        tries += 1
    return result


def invoke_cached_cli(args: Sequence[str], **kwargs: Unpack[ClickInvokeKwargs]) -> Result:
    """Invoke the runtime frontend against the sequence-owned native server."""
    return CliRunner().invoke(cadrumo_click_command(), list(args), **kwargs)


def _invoke_authenticated_frame(args: tuple[str, ...], *, program: CommandProgram) -> Result:
    """Supply a fresh bounded password proof without replacing authored channels."""
    if program is CommandProgram.AUTHENTICATION:
        from cadrumo_runtime.commands.command_specs import RUNTIME_COMMAND_GRAPH
        from cadrumo_runtime.commands.tests.config.runtime_cli import invoke_runtime_cli

        graph = RUNTIME_COMMAND_GRAPH
        invoke = invoke_runtime_cli
    else:
        graph = COMMAND_GRAPH
        invoke = invoke_cached_cli
    if _has_explicit_authentication(args):
        return invoke(list(args))
    spec = graph.resolve_invocation(args)
    registration = None if spec is None else command_registration_for_node(graph.node(spec.key))
    if spec is not None and spec.key == "config_login":
        password = load_settings().cadrumo_dev_test_database_password.get_secret_value()
        return invoke([*args, "--secrets-stdin"], input=json.dumps({"passphrase": password}))
    posture = (
        spec.profile_authentication
        if program is CommandProgram.AUTHENTICATION and spec is not None
        else None
        if registration is None
        else registration.profile_authentication
    )
    if posture is not ProfileAuthenticationPosture.RESUME_FALLBACK:
        return invoke(list(args))
    password = load_settings().cadrumo_dev_test_database_password.get_secret_value()
    return invoke(["--profile-secrets-stdin", *args], input=json.dumps({"profile_passphrase": password}))


def _has_explicit_authentication(args: tuple[str, ...]) -> bool:
    explicit = {
        "--profile-secrets-stdin",
        "--profile-secrets-fd",
        "--profile-credential-ref",
        "--profile-auth-method",
        "--secrets-stdin",
        "--secrets-fd",
    }
    return any(argument.split("=", 1)[0] in explicit for argument in args)


def _execute_frame(
    sequence: ParsedSequence,
    frame: SequenceFrame,
    captures: dict[str, CapturedScalar],
    *,
    frame_index: int,
) -> FrameExecution:
    """Execute one frame, enforce its exit code, and thread its captures."""
    argv = _resolved_argv(frame, captures)
    _record_frame_progress(sequence, frame, frame_index=frame_index, argv=argv)
    observer = _FRAME_OBSERVER.get()
    with observer(frame_index) if observer is not None else nullcontext():
        result = _invoke_frame(argv[1:], program=frame.program)
    # The runner records the two streams separately: ``Result.output`` under
    # this Click version is the COMBINED capture, so read the split
    # ``stdout``/``stderr`` properties — a refusal's error document (which
    # rides stderr) must be a first-class, golden-able artifact.
    output = semantic_cli_text(result.stdout)
    stderr = semantic_cli_text(result.stderr)

    expected_exit = _expected_exit_code(frame, sequence.sequence_id)
    if result.exit_code != expected_exit:
        cause = f" (uncaught: {result.exception!r})" if result.exception is not None else ""
        raise SequenceExecutionError(
            sequence.sequence_id,
            f"{_frame_at(frame)}: frame exited {result.exit_code}, expected "
            f"{expected_exit} (declare a non-zero expectation with "
            f"'@expect {_EXIT_CODE_PATH} == <n>'){cause}\n"
            f"  argv: {' '.join(argv)}\n"
            f"  stdout tail: {output[-1500:]!r}\n"
            f"  stderr tail: {stderr[-1500:]!r}",
        )

    # Envelope resolution is stdout-first-then-stderr: the success envelope is
    # emitted on stdout; the refusal error document — which shares the envelope
    # spine per the CLI notices standard — on stderr.
    envelope = _parse_envelope(output)
    envelope_source: EnvelopeSource | None = "stdout" if envelope is not None else None
    if envelope is None:
        envelope = _parse_envelope(stderr)
        envelope_source = "stderr" if envelope is not None else None

    captured = _capture_values(
        frame,
        envelope,
        sequence_id=sequence.sequence_id,
        argv=argv,
        output=output,
    )
    captures.update({item.name: item.value for item in captured})

    return FrameExecution(
        kind=frame.kind,
        command_line=frame.command_line,
        argv=argv,
        exit_code=result.exit_code,
        output=output,
        stderr=stderr,
        envelope=envelope,
        envelope_source=envelope_source,
        captured=captured,
    )


def execute_sequence(
    sequence: ParsedSequence,
    *,
    sandbox_root: Path | None = None,
    fixtures_root: Path | None = None,
) -> SequenceTranscript:
    """Execute a parsed sequence in a fresh hermetic sandbox.

    Frames execute in order through the cached in-process Click tree, each
    frame's captures binding before the next frame's placeholders interpolate.
    The sandbox is torn down before returning; the transcript is the only
    surviving artifact.

    Args:
        sequence: The structurally valid parsed sequence to run.
        sandbox_root: An empty directory to sandbox under (tests pass a
            ``tmp_path`` child); when ``None`` a temporary directory is created
            and removed after the run.
        fixtures_root: Optional override of the committed synthetic-fixtures
            tree copied into the sandbox workdir.

    Returns:
        The typed :class:`SequenceTranscript` of the run.

    Raises:
        SequenceExecutionError: When the sequence has no executed frames (it is
            all ``@static``, so there is nothing to run and no golden to build),
            any executed frame is a live-AEAT invocation, exits with an undeclared
            code, declares a capture its output cannot satisfy, or the live-test
            opt-in is set.
    """
    _refuse_unexecutable(sequence)
    if sandbox_root is not None:
        return _execute_in_root(sequence, sandbox_root, fixtures_root)
    # Engine handles on Windows can outlive the run despite the teardown's
    # dispose; ignore_cleanup_errors keeps a stale handle from failing the run.
    with TemporaryDirectory(prefix="seq-", ignore_cleanup_errors=True, dir=prepare_temp_root()) as tmp:
        return _execute_in_root(sequence, Path(tmp), fixtures_root)


def _refuse_unexecutable(sequence: ParsedSequence) -> None:
    """Refuse a sequence with nothing to run, or one that would reach live AEAT."""
    if not sequence.executed_frames:
        raise SequenceExecutionError(
            sequence.sequence_id,
            "an all-@static sequence has no executed frames to run and no golden to build; "
            "the check/refresh path skips it (it is display-only)",
        )
    refuse_live_frames(sequence)


def _execute_in_root(
    sequence: ParsedSequence,
    sandbox_root: Path,
    fixtures_root: Path | None,
) -> SequenceTranscript:
    """Open the sandbox under ``sandbox_root`` and run every frame in order."""
    with executed_sequence_sandbox(sequence, sandbox_root=sandbox_root, fixtures_root=fixtures_root) as (_, transcript):
        return transcript


@contextmanager
def executed_sequence_sandbox(
    sequence: ParsedSequence,
    *,
    sandbox_root: Path,
    fixtures_root: Path | None = None,
) -> Generator[tuple[SequenceSandbox, SequenceTranscript]]:
    """Run a sequence and hold its sandbox open over the state it built.

    The golden tier needs only the transcript, so it leaves the scope at once.
    A consumer that renders what the sequence produced -- the TUI visual
    review, which shows the calculated declaration a sequence leaves behind --
    needs the storage, the frozen clock and the open profile session still in
    place, and reads them inside this scope. It is the same execution as
    :func:`execute_sequence`, with the same refusals; there is no second way
    to run a frame.

    Args:
        sequence: The structurally valid parsed sequence to run.
        sandbox_root: An empty directory the sandbox owns.
        fixtures_root: Optional override of the committed synthetic-fixtures
            tree copied into the sandbox workdir.

    Yields:
        The open sandbox and the transcript of every executed frame.

    Raises:
        SequenceExecutionError: Under the conditions :func:`execute_sequence`
            names.
    """
    _refuse_unexecutable(sequence)
    with (
        _logs_retained_on_failure(sandbox_root, _retained_logs_root(), sequence.sequence_id),
        sequence_sandbox(
            sequence_id=sequence.sequence_id,
            sandbox_root=sandbox_root,
            fixtures_root=fixtures_root,
        ) as sandbox,
    ):
        captures: dict[str, CapturedScalar] = {}
        # @static frames are display-only: they never run, so they never enter
        # the transcript (and therefore never the golden).
        frames = tuple(
            _execute_frame(sequence, frame, captures, frame_index=frame_index)
            for frame_index, frame in enumerate(sequence.executed_frames)
        )
        yield (
            sandbox,
            SequenceTranscript(
                sequence_id=sequence.sequence_id,
                profile_id=sandbox.profile_id,
                frozen_instant=sandbox.frozen_instant,
                storage_root=str(sandbox.storage_root),
                workdir=str(sandbox.workdir),
                frames=frames,
            ),
        )


def execute_page_sequences(
    sequences: Sequence[ParsedSequence],
    *,
    label: str = "page",
    sandbox_root: Path | None = None,
    fixtures_root: Path | None = None,
) -> tuple[SequenceTranscript, ...]:
    """Execute a page's sequences cumulatively in ONE hermetic sandbox.

    The page-coherence tier: a reader following an enrolled page top to bottom
    works in one clean environment, so this mode opens a single sandbox (same
    substrate as :func:`execute_sequence` — isolated real-crypto storage,
    frozen clock, injected deterministic profile) and runs every sequence IN
    PAGE ORDER inside it, state accumulating across sequences by design. This
    is deliberately NOT the golden contract: goldens stay the per-sequence
    isolated expectation, and cumulative transcripts must never be compared
    against them.

    Captures stay sequence-scoped (the parser proves placeholder resolution per
    sequence); persistent state — the ledger, work units, profile facts — is
    what carries across. Frame execution keeps its fail-fast guarantees
    (exit-code enforcement, capture resolution, live-AEAT refusal for every
    sequence up front), so a mid-page failure aborts the page rather than
    cascading a corrupted premise into later sequences.

    Args:
        sequences: The page's structurally valid sequences, in page order.
        label: A locator label for sandbox-level failure messages (the page
            docname).
        sandbox_root: An empty directory to sandbox under; a temporary
            directory when ``None``.
        fixtures_root: Optional override of the committed fixtures tree.

    Returns:
        One :class:`SequenceTranscript` per EXECUTABLE sequence, in page order;
        an all-``@static`` sequence runs nothing and yields no transcript, so the
        caller aligns transcripts with the executable sequences.
    """
    for sequence in sequences:
        refuse_live_frames(sequence)
    if not sequences:
        return ()
    if sandbox_root is not None:
        return _execute_page_in_root(sequences, label, sandbox_root, fixtures_root)
    with TemporaryDirectory(prefix="page-", ignore_cleanup_errors=True, dir=prepare_temp_root()) as tmp:
        return _execute_page_in_root(sequences, label, Path(tmp), fixtures_root)


def _execute_page_in_root(
    sequences: Sequence[ParsedSequence],
    label: str,
    sandbox_root: Path,
    fixtures_root: Path | None,
) -> tuple[SequenceTranscript, ...]:
    """Open one sandbox under ``sandbox_root`` and run every EXECUTABLE sequence in order.

    An all-``@static`` sequence runs nothing, so it produces no transcript (the
    same skip :func:`execute_sequence` applies at the golden tier); the returned
    tuple therefore carries one transcript per executable sequence, in page order.
    """
    transcripts: list[SequenceTranscript] = []
    page_seeds: dict[str, _PageSeedState] = {}
    page_seed_signatures: dict[tuple[str, ...], tuple[str, _PageSeedState]] = {}
    with (
        _logs_retained_on_failure(sandbox_root, _retained_logs_root(), label),
        sequence_sandbox(
            sequence_id=label,
            sandbox_root=sandbox_root,
            fixtures_root=fixtures_root,
            enrolled_sequence_ids=tuple(sequence.sequence_id for sequence in sequences if sequence.executed_frames),
        ) as sandbox,
    ):
        for sequence in sequences:
            transcript = _execute_page_sequence(sequence, label, sandbox, page_seeds, page_seed_signatures)
            if transcript is not None:
                transcripts.append(transcript)
    return tuple(transcripts)


def _retained_logs_root() -> Path:
    """Keep disposable failure diagnostics in the owning worktree's temporary root."""
    return Path(prepare_temp_root()) / "failed-sandboxes"


@contextmanager
def _logs_retained_on_failure(sandbox_root: Path, retained_root: Path, label: str) -> Generator[None]:
    """Copy a failed sandbox's product logs out before its directory is removed.

    Each sandbox binds the runtime's, the profile worker's and this process's
    diagnostic log under its own storage root, which goes with the sandbox. A
    worker that dies mid-sequence, or a runtime that fails its own teardown,
    would otherwise leave no record anywhere. Every ``logs`` directory under
    the sandbox root is kept, by its path relative to that root.
    """
    try:
        yield
    except BaseException as error:
        destination = retained_root / f"{re.sub(r'[^A-Za-z0-9._-]+', '_', label)}-{os.getpid()}-{time.time_ns()}"
        try:
            for logs in sandbox_root.rglob("logs"):
                if logs.is_dir():
                    shutil.copytree(logs, destination / logs.relative_to(sandbox_root), dirs_exist_ok=True)
        except OSError as copy_error:
            error.add_note(f"sandbox logs could not be retained: {type(copy_error).__name__}")
        else:
            error.add_note(f"sandbox logs retained at {destination}")
        raise


def _execute_page_sequence(
    sequence: ParsedSequence,
    label: str,
    sandbox: SequenceSandbox,
    page_seeds: dict[str, _PageSeedState],
    page_seed_signatures: dict[tuple[str, ...], tuple[str, _PageSeedState]],
) -> SequenceTranscript | None:
    if not sequence.executed_frames:
        return None  # all-@static: nothing runs, so no transcript
    if sequence.sequence_id == "profile-setup-delete":
        _publish_replacement_sandbox_profile()
    captures: dict[str, CapturedScalar] = {}
    seed_source = f"seed:{sequence.seed}" if sequence.seed is not None else None
    seed_frames = (
        tuple(frame for frame in sequence.executed_frames if frame.source == seed_source)
        if seed_source is not None
        else ()
    )
    body_frames = tuple(frame for frame in sequence.executed_frames if frame.source != seed_source)
    reused_seed_executions: tuple[FrameExecution, ...] = ()
    seed_signature = _seed_execution_signature(seed_frames)

    _require_page_seed_frames(sequence, label, seed_frames)

    reused_seed_executions = _page_seed_executions(
        sequence, label, seed_frames, seed_signature, captures, page_seeds, page_seed_signatures
    )

    body_start = len(seed_frames)
    body_executions = tuple(
        _execute_frame(sequence, frame, captures, frame_index=body_start + frame_index)
        for frame_index, frame in enumerate(body_frames)
    )
    frames = reused_seed_executions + body_executions
    return SequenceTranscript(
        sequence_id=sequence.sequence_id,
        profile_id=sandbox.profile_id,
        frozen_instant=sandbox.frozen_instant,
        storage_root=str(sandbox.storage_root),
        workdir=str(sandbox.workdir),
        frames=frames,
    )


def _page_seed_executions(
    sequence: ParsedSequence,
    label: str,
    seed_frames: tuple[SequenceFrame, ...],
    seed_signature: tuple[str, ...],
    captures: dict[str, CapturedScalar],
    page_seeds: dict[str, _PageSeedState],
    page_seed_signatures: dict[tuple[str, ...], tuple[str, _PageSeedState]],
) -> tuple[FrameExecution, ...]:
    if sequence.seed is not None and sequence.seed not in page_seeds and seed_signature in page_seed_signatures:
        return _reuse_equivalent_page_seed(
            sequence, label, seed_frames, seed_signature, captures, page_seeds, page_seed_signatures
        )
    if sequence.seed is not None and sequence.seed in page_seeds:
        return _reuse_named_page_seed(sequence, label, seed_frames, captures, page_seeds)
    if sequence.seed is not None:
        return _execute_new_page_seed(sequence, seed_frames, seed_signature, captures, page_seeds, page_seed_signatures)
    return ()


def _reuse_equivalent_page_seed(
    sequence: ParsedSequence,
    label: str,
    seed_frames: tuple[SequenceFrame, ...],
    seed_signature: tuple[str, ...],
    captures: dict[str, CapturedScalar],
    page_seeds: dict[str, _PageSeedState],
    page_seed_signatures: dict[tuple[str, ...], tuple[str, _PageSeedState]],
) -> tuple[FrameExecution, ...]:
    prior_identity, prior = page_seed_signatures[seed_signature]
    warnings.warn(
        f"page {label!r} sequence {sequence.sequence_id!r} seed {sequence.seed!r} "
        f"is execution-equivalent to already-run seed {prior_identity!r}; reused its "
        "once-per-page state and immutable captures instead of replaying side effects",
        UserWarning,
        stacklevel=5,
    )
    page_seeds[cast(str, sequence.seed)] = _PageSeedState(
        frames=seed_frames,
        executions=prior.executions,
        captures=prior.captures,
    )
    captures.update({item.name: item.value for item in prior.captures})
    return prior.executions


def _reuse_named_page_seed(
    sequence: ParsedSequence,
    label: str,
    seed_frames: tuple[SequenceFrame, ...],
    captures: dict[str, CapturedScalar],
    page_seeds: dict[str, _PageSeedState],
) -> tuple[FrameExecution, ...]:
    prior = page_seeds[cast(str, sequence.seed)]
    if prior.frames != seed_frames:
        detail = (
            f"page {label!r} sequence {sequence.sequence_id!r} reuses seed identity "
            f"{sequence.seed!r} with a divergent definition; give the changed recipe "
            "a new seed identity or make every use structurally equivalent"
        )
        warnings.warn(detail, UserWarning, stacklevel=5)
        raise SequenceExecutionError(sequence.sequence_id, detail)
    available = {item.name: item.value for item in prior.captures}
    required = {binding.name for frame in seed_frames for binding in frame.captures}
    missing = sorted(required - available.keys())
    if missing:
        detail = (
            f"page {label!r} sequence {sequence.sequence_id!r} cannot reuse seed "
            f"{sequence.seed!r}; page seed state lacks captures {missing}. Re-run from "
            "a clean page root and ensure every declared seed capture resolves"
        )
        warnings.warn(detail, UserWarning, stacklevel=5)
        raise SequenceExecutionError(sequence.sequence_id, detail)
    warnings.warn(
        f"page {label!r} sequence {sequence.sequence_id!r} would replay seed "
        f"{sequence.seed!r}; reused its once-per-page state and immutable captures instead",
        UserWarning,
        stacklevel=5,
    )
    captures.update(available)
    return prior.executions


def _execute_new_page_seed(
    sequence: ParsedSequence,
    seed_frames: tuple[SequenceFrame, ...],
    seed_signature: tuple[str, ...],
    captures: dict[str, CapturedScalar],
    page_seeds: dict[str, _PageSeedState],
    page_seed_signatures: dict[tuple[str, ...], tuple[str, _PageSeedState]],
) -> tuple[FrameExecution, ...]:
    seed_executions = tuple(
        _execute_frame(sequence, frame, captures, frame_index=frame_index)
        for frame_index, frame in enumerate(seed_frames)
    )
    seed_captures = tuple(item for execution in seed_executions for item in execution.captured)
    state = _PageSeedState(
        frames=seed_frames,
        executions=seed_executions,
        captures=seed_captures,
    )
    page_seeds[cast(str, sequence.seed)] = state
    page_seed_signatures[seed_signature] = (cast(str, sequence.seed), state)
    return seed_executions


def _require_page_seed_frames(sequence: ParsedSequence, label: str, seed_frames: tuple[SequenceFrame, ...]) -> None:
    if sequence.seed is not None and not seed_frames:
        detail = (
            f"page {label!r} sequence {sequence.sequence_id!r} requests seed "
            f"{sequence.seed!r}, but no inlined seed frames are available; reparse the "
            "sequence from its contract before running page coherence"
        )
        warnings.warn(detail, UserWarning, stacklevel=4)
        raise SequenceExecutionError(sequence.sequence_id, detail)


def _resolve_object_key(current: object, key: str) -> tuple[bool, object]:
    if not isinstance(current, Mapping):
        return False, None
    # JSON keys are strings; preserve the defensive str-keyed view.
    step: Mapping[str, object] = {str(item): entry for item, entry in current.items()}
    if key not in step:
        return False, None
    return True, step[key]


def _resolve_dotted_segment(current: object, key: str) -> tuple[bool, object]:
    if isinstance(current, Mapping):
        return _resolve_object_key(current, key)
    if isinstance(current, list) and key.isdigit():
        position = int(key)
        if position >= len(current):
            return False, None
        return True, current[position]
    return False, None
