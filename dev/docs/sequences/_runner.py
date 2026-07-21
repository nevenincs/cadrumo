"""Per-sequence hermetic sandbox runner for ``cli-sequence`` frames.

Each :class:`~dev.docs.sequences._schema.ParsedSequence` executes in FULL
isolation: a fresh real-crypto storage root (:func:`isolated_profile_storage_root`
— genuine ``bucket-dek-v1`` provisioning under the ephemeral dev-test master-key
backend), the project-wide frozen instant :data:`SANDBOX_INSTANT`
(:func:`cadrumo.core.time.frozen_clock`), a deterministic injected profile
identity :data:`SANDBOX_PROFILE_ID` registered through the canonical atomic
create (:func:`~cadrumo.application.user_profile.register_active_profile` inside
:func:`~cadrumo.application.user_profile.profile_create_storage_span` — never a
parallel write path), English output pinned via the central settings surface,
and the live-AEAT gate off. Frames are invoked in-process through the cached
Click tree (:func:`~cadrumo.tests.cli_runner.invoke_cached_cli`). Sequences never
share state — not across pages and not within a page.

Capture threading: after a frame executes, each of its
:class:`~dev.docs.sequences._schema.CaptureBinding` json-paths is read from the
frame's parsed JSON envelope and bound; later frames interpolate the bound value
into their ``{name}`` placeholder tokens before execution. A capture against
non-JSON output, a json-path missing from the envelope, a non-scalar or null
capture, and an undeclared non-zero exit code are all fail-fast
:class:`~dev.docs.sequences._errors.SequenceExecutionError` refusals — every
later frame would otherwise run against a corrupted premise.

Safety: a frame that would contact live
AEAT is refused BEFORE any execution. Detection is fail-closed over the argv
tokens: any non-option token equal to ``live`` or ``pull``, or starting with
``pull-``, marks the frame unenrollable (the ``pull`` verb family and the
``app live`` group are, by the CLI naming standard, exactly the live-AEAT read
surface). The sandbox additionally refuses to open while the live-test opt-in
is set, and never sets it.

Layering note: this docs-tooling engine deliberately consumes the shared
in-package test substrate — :mod:`cadrumo.tests.cli_runner` and
:mod:`cadrumo.tests.secure_sql` — rather than duplicating a second engine on
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
import os
import re
import shutil
import time
from collections.abc import Iterator, Mapping, Sequence
from contextlib import chdir, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal

from click.testing import Result
from pydantic import BaseModel, Field, JsonValue

from cadrumo.adapters.persistence.storage import dispose_engine
from cadrumo.core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from cadrumo.core.config import load_settings, override_settings, suppress_operator_dotenv
from cadrumo.core.time import frozen_clock
from cadrumo.domain.user_profile import UserProfileFact
from cadrumo.tests.cli_runner import invoke_cached_cli, semantic_cli_text
from cadrumo.tests.secure_sql import isolated_profile_storage_root

from ._errors import SequenceExecutionError
from ._schema import (
    FrameKind,
    Identifier,
    JsonPath,
    ParsedSequence,
    SequenceFrame,
    SequenceId,
)

__all__ = [
    "SANDBOX_INSTANT",
    "SANDBOX_PROFILE_ID",
    "SANDBOX_PROFILE_LABEL",
    "CapturedValue",
    "EnvelopeSource",
    "FrameExecution",
    "SequenceSandbox",
    "SequenceTranscript",
    "default_fixtures_root",
    "execute_page_sequences",
    "execute_sequence",
    "sequence_sandbox",
]

#: The one project-wide frozen instant every sequence executes under.
SANDBOX_INSTANT: datetime = datetime(2026, 4, 1, 9, 0, 0, tzinfo=UTC)

#: The deterministic injected profile identity (a fixed valid UUIDv4 shape,
#: distinct from the shared test-fixture bucket ids). With the clock frozen and
#: this identity injected, only the substrate's declared surrogate keys should
#: still flap across runs (``GOLDEN_MASK_FIELDS``).
SANDBOX_PROFILE_ID: str = "99999999-9999-4999-8999-999999999999"

#: The sandbox profile's display label (a decoupled label, no role in any key).
SANDBOX_PROFILE_LABEL: str = "docs-sequence-sandbox"

#: Synthetic profile facts for the injected sandbox identity, mirroring the
#: fact paths the workspace-initialization service persists. All values are
#: synthetic; richer fixture state is built by ``@setup`` frames.
_SANDBOX_PROFILE_FACTS: tuple[UserProfileFact, ...] = (
    UserProfileFact(path="identity.tax_id", value="12345678Z"),
    UserProfileFact(path="identity.name", value="Docs"),
    UserProfileFact(path="identity.surnames", value="Sandbox"),
    UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
    UserProfileFact(path="activities.description", value="documentation examples"),
    UserProfileFact(path="iva.regime", value="GENERAL"),
)

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
class SequenceSandbox:
    """The open hermetic sandbox a sequence executes inside."""

    storage_root: Path
    workdir: Path
    profile_id: str
    frozen_instant: datetime


def default_fixtures_root() -> Path:
    """Return the committed ``docs/_sequences/fixtures/`` synthetic-input tree.

    Resolved relative to this module so the engine finds fixtures regardless of
    the process working directory (the same anchoring as the seed recipes).
    """
    repo_root = Path(__file__).resolve().parents[3]
    return repo_root / "docs" / "_sequences" / "fixtures"


def _frame_at(frame: SequenceFrame) -> str:
    """Render a frame's source/line locator prefix for a failure message."""
    if frame.source == "body":
        return f"line {frame.line_number}"
    return f"{frame.source} line {frame.line_number}"


def _live_aeat_tokens(frame: SequenceFrame) -> tuple[str, ...]:
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


def _refuse_live_frames(sequence: ParsedSequence) -> None:
    """Refuse the whole sequence when any EXECUTED frame would contact live AEAT.

    A ``@static`` frame is the sanctioned way to DISPLAY a live-AEAT command
    (it is never executed), so static frames are exempt; an executed frame
    (command / setup / result) that reads live AEAT is still refused.
    """
    violations = [
        f"{_frame_at(frame)}: {frame.command_line!r} is a live-AEAT invocation "
        f"(tokens {', '.join(_live_aeat_tokens(frame))}); pull verbs and the "
        "'app live' group cannot be executed. Run build/verify/export frames, "
        "or show the live command as a @static frame instead"
        for frame in sequence.executed_frames
        if _live_aeat_tokens(frame)
    ]
    if violations:
        raise SequenceExecutionError(sequence.sequence_id, "; ".join(violations))


def _refuse_live_opt_in(sequence_id: str) -> None:
    """Refuse to open a sandbox while the live-test opt-in is set."""
    if load_settings().live_tests_enabled:
        raise SequenceExecutionError(
            sequence_id,
            "the live-test opt-in (CADRUMO_LIVE_TESTS_ENABLED) is set; the docs "
            "sequence sandbox never runs against live AEAT — unset it and re-run",
        )


def _provision_sandbox_profile() -> None:
    """Register the deterministic sandbox profile through the canonical create.

    Mirrors the workspace-initialization composition exactly — the
    cross-store atomic create is owned by
    :func:`~cadrumo.application.user_profile.register_active_profile` inside a
    :func:`~cadrumo.application.user_profile.profile_create_storage_span` — so
    the sandbox introduces no parallel write path. The injected fixed
    ``profile_id`` is what makes every profile-derived identifier in a frame's
    output deterministic across runs.
    The application-layer imports are deferred: importing
    ``cadrumo.application.*`` transitively resolves product settings at module
    import time, which must only happen after the sandbox has pinned an
    isolated storage root (the docs-build ``ensure_isolated_storage_root``
    pattern). Both targets are public top-level facades.
    """
    from cadrumo.application.user_profile import (
        profile_create_storage_span,
        register_active_profile,
    )
    from cadrumo.application.workflow import workflow_state_repository

    with profile_create_storage_span(SANDBOX_PROFILE_ID) as routing_profile_id:
        workflow_state_repository().update(
            lambda state: register_active_profile(
                state,
                profile_id=SANDBOX_PROFILE_ID,
                display_name=SANDBOX_PROFILE_LABEL,
                facts=_SANDBOX_PROFILE_FACTS,
                routing_profile_id=routing_profile_id,
            ),
        )


#: Environment prefixes scrubbed from the process environment for the whole
#: sandbox scope: the operator's ambient ``CADRUMO_*`` / ``AEAT_*`` machine
#: state (auth credentials, Cl@ve identifiers, live opt-ins, machine-local
#: paths) must never be observable by a docs sequence execution — both a
#: privacy boundary (``sensitive-financial-data``) and a determinism one.
_SCRUBBED_ENV_PREFIXES: tuple[str, ...] = ("CADRUMO_", "AEAT_")

#: Deliberate pins that survive the scrub. ``CADRUMO_LOCAL_STORAGE_ROOT`` is
#: the process-level isolation seam itself (``ensure_isolated_storage_root``);
#: removing it would UNPIN the guard that keeps import-time settings resolution
#: off the operator's real product state. The English output pin rides
#: ``override_settings``, not the environment, so it needs no entry here.
_ENV_SCRUB_ALLOWLIST: frozenset[str] = frozenset({"CADRUMO_LOCAL_STORAGE_ROOT"})


@contextmanager
def _neutralized_ambient_env() -> Iterator[None]:
    """Remove ambient ``CADRUMO_*`` / ``AEAT_*`` env vars for the scope.

    Settings resolution inside the sandbox re-reads the process environment on
    every :class:`Settings` instantiation, so any operator-exported variable
    would otherwise flow straight into sandboxed frame executions. Everything
    removed is restored verbatim on exit. BOTH operator-state channels are now
    closed for the sandbox scope: this scrub covers the ambient environment,
    and the settings-level :func:`~cadrumo.core.config.suppress_operator_dotenv`
    seam (engaged alongside it in :func:`sequence_sandbox`) drops the
    project-root ``env/.env`` dotenv source, which pydantic-settings loads via
    an ABSOLUTE path regardless of the working directory.
    """
    removed: dict[str, str] = {}
    for key in list(os.environ):
        upper = key.upper()
        if upper.startswith(_SCRUBBED_ENV_PREFIXES) and upper not in _ENV_SCRUB_ALLOWLIST:
            removed[key] = os.environ.pop(key)
    try:
        yield
    finally:
        os.environ.update(removed)


@contextmanager
def _isolated_external_tool_env(sandbox_root: Path) -> Iterator[None]:
    """Pin external-tool discovery to empty sandbox-owned directories.

    ``PATH`` and the Playwright browser cache are workstation state just as
    surely as ``CADRUMO_*`` settings are. Sequence execution must not discover
    a contributor's provider CLIs or browser installation, so real probes see
    stable absence with their real remediation while the process environment
    is restored verbatim afterwards.
    """
    # Keep these beneath the sequence workdir so the existing golden path
    # normaliser rewrites their per-run root to ``<sandbox-workdir>``.
    empty_bin = sandbox_root / "workdir" / ".external-tools"
    empty_browsers = sandbox_root / "workdir" / ".playwright-browsers"
    empty_bin.mkdir(parents=True, exist_ok=True)
    empty_browsers.mkdir(parents=True, exist_ok=True)
    pins = {
        "PATH": str(empty_bin),
        "PLAYWRIGHT_BROWSERS_PATH": str(empty_browsers),
    }
    previous = {key: os.environ.get(key) for key in pins}
    os.environ.update(pins)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@contextmanager
def sequence_sandbox(
    *,
    sequence_id: str,
    sandbox_root: Path,
    fixtures_root: Path | None = None,
) -> Iterator[SequenceSandbox]:
    """Open one hermetic per-sequence sandbox under ``sandbox_root``.

    Inside the scope: an isolated real-crypto storage root, the frozen
    :data:`SANDBOX_INSTANT`, the deterministic :data:`SANDBOX_PROFILE_ID`
    registered and active, ``cadrumo_output_language`` pinned to English, the
    operator's ambient ``CADRUMO_*`` / ``AEAT_*`` environment scrubbed for the
    whole scope (restored on exit; the storage-root isolation pin survives),
    and the process working directory moved to a scratch ``workdir`` seeded
    with a copy of the committed synthetic fixtures — so a frame's relative
    ``fixtures/...`` input reads the committed artifact's copy and a frame's
    relative ``--output`` lands inside the sandbox, never in the repository.

    Args:
        sequence_id: The owning sequence id, for failure messages.
        sandbox_root: An empty per-sequence directory the sandbox owns.
        fixtures_root: The committed fixtures tree to copy into the workdir;
            defaults to :func:`default_fixtures_root` (skipped when absent).

    Yields:
        The open :class:`SequenceSandbox`.
    """
    # Importing the application resolves the product storage root; a machine
    # carrying retired product state must never red (or leak into) a docs
    # sequence run, so pin the process-level scratch root first — exactly the
    # docs-build isolation seam. Deferred import: ``dev.docs.build`` is a CLI
    # tool module, not an engine dependency.
    from ..build import ensure_isolated_storage_root

    ensure_isolated_storage_root()
    _refuse_live_opt_in(sequence_id)
    workdir = sandbox_root / "workdir"
    workdir.mkdir(parents=True, exist_ok=True)
    fixtures = fixtures_root if fixtures_root is not None else default_fixtures_root()
    if fixtures.is_dir():
        shutil.copytree(fixtures, workdir / "fixtures", dirs_exist_ok=True)

    dispose_engine()
    with (
        _neutralized_ambient_env(),
        _isolated_external_tool_env(sandbox_root),
        suppress_operator_dotenv(),
        # The docs sandbox runs genuinely zero-auth: per the operator ruling,
        # auth-provider readiness binds only live/AEAT-touching purposes, never
        # the local build/calculate/verify/file/export flow the sequences drive.
        # A taxpayer with no auth provider configured completes the whole local
        # artefact flow, and the docs gates prove that ruled behaviour in CI.
        override_settings(
            cadrumo_llm_ollama_chat_url="http://127.0.0.1:1/api/chat",
            cadrumo_output_language="en",
        ),
        isolated_profile_storage_root(tmp_path=sandbox_root),
        frozen_clock(SANDBOX_INSTANT),
        chdir(workdir),
    ):
        _provision_sandbox_profile()
        effective_settings = load_settings()
        yield SequenceSandbox(
            storage_root=Path(effective_settings.cadrumo_local_storage_root),
            workdir=workdir.resolve(),
            profile_id=SANDBOX_PROFILE_ID,
            frozen_instant=SANDBOX_INSTANT,
        )


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


def _resolve_json_path(document: Mapping[str, object], path: str) -> tuple[bool, object]:
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
            if isinstance(current, Mapping):
                step_q: Mapping[str, object] = {str(item): entry for item, entry in current.items()}
                if quoted_key not in step_q:
                    return False, None
                current = step_q[quoted_key]
                continue
            return False, None
        if key is not None:
            if isinstance(current, Mapping):
                # Re-key defensively: JSON object keys are always strings, and
                # the str-keyed view gives the checker a concrete key type.
                step: Mapping[str, object] = {str(item): entry for item, entry in current.items()}
                if key not in step:
                    return False, None
                current = step[key]
                continue
            if isinstance(current, list) and key.isdigit():
                position = int(key)
                if position >= len(current):
                    return False, None
                current = current[position]
                continue
            return False, None
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
        found, value = _resolve_json_path(envelope, binding.json_path)
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


def _invoke_frame(args: tuple[str, ...]) -> Result:
    """Invoke the cached CLI, retrying only on the transient registry-write race.

    The race exists only during local development, where concurrent
    modification of the registry TOML tree mid-load produces these transient
    failures; under CI the tree is static, so any marker match there is a
    genuine failure and the retry loop is skipped entirely rather than
    burning bounded-retry latency in front of it.
    """
    result = invoke_cached_cli(list(args))
    if os.environ.get("CI"):
        return result
    tries = 1
    while (
        tries < _TRANSIENT_RETRY_ATTEMPTS
        and result.exit_code != 0
        and any(marker in result.output for marker in _TRANSIENT_REGISTRY_RACE_MARKERS)
    ):
        time.sleep(2)
        dispose_engine()
        result = invoke_cached_cli(list(args))
        tries += 1
    return result


def _execute_frame(
    sequence: ParsedSequence,
    frame: SequenceFrame,
    captures: dict[str, CapturedScalar],
) -> FrameExecution:
    """Execute one frame, enforce its exit code, and thread its captures."""
    argv = _resolved_argv(frame, captures)
    result = _invoke_frame(argv[1:])
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
    if not sequence.executed_frames:
        raise SequenceExecutionError(
            sequence.sequence_id,
            "an all-@static sequence has no executed frames to run and no golden to build; "
            "the check/refresh path skips it (it is display-only)",
        )
    _refuse_live_frames(sequence)
    if sandbox_root is not None:
        return _execute_in_root(sequence, sandbox_root, fixtures_root)
    # Engine handles on Windows can outlive the run despite the teardown's
    # dispose; ignore_cleanup_errors keeps a stale handle from failing the run.
    with TemporaryDirectory(prefix="cli-sequence-", ignore_cleanup_errors=True) as tmp:
        return _execute_in_root(sequence, Path(tmp), fixtures_root)


def _execute_in_root(
    sequence: ParsedSequence,
    sandbox_root: Path,
    fixtures_root: Path | None,
) -> SequenceTranscript:
    """Open the sandbox under ``sandbox_root`` and run every frame in order."""
    with sequence_sandbox(
        sequence_id=sequence.sequence_id,
        sandbox_root=sandbox_root,
        fixtures_root=fixtures_root,
    ) as sandbox:
        captures: dict[str, CapturedScalar] = {}
        # @static frames are display-only: they never run, so they never enter
        # the transcript (and therefore never the golden).
        frames = tuple(_execute_frame(sequence, frame, captures) for frame in sequence.executed_frames)
    return SequenceTranscript(
        sequence_id=sequence.sequence_id,
        profile_id=sandbox.profile_id,
        frozen_instant=sandbox.frozen_instant,
        storage_root=str(sandbox.storage_root),
        workdir=str(sandbox.workdir),
        frames=frames,
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
        _refuse_live_frames(sequence)
    if not sequences:
        return ()
    if sandbox_root is not None:
        return _execute_page_in_root(sequences, label, sandbox_root, fixtures_root)
    with TemporaryDirectory(prefix="cli-sequence-page-", ignore_cleanup_errors=True) as tmp:
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
    with sequence_sandbox(
        sequence_id=label,
        sandbox_root=sandbox_root,
        fixtures_root=fixtures_root,
    ) as sandbox:
        for sequence in sequences:
            if not sequence.executed_frames:
                continue  # all-@static: nothing runs, so no transcript
            captures: dict[str, CapturedScalar] = {}
            frames = tuple(_execute_frame(sequence, frame, captures) for frame in sequence.executed_frames)
            transcripts.append(
                SequenceTranscript(
                    sequence_id=sequence.sequence_id,
                    profile_id=sandbox.profile_id,
                    frozen_instant=sandbox.frozen_instant,
                    storage_root=str(sandbox.storage_root),
                    workdir=str(sandbox.workdir),
                    frames=frames,
                ),
            )
    return tuple(transcripts)
