"""Strict Pydantic records for a parsed ``cli-sequence`` directive.

A :class:`ParsedSequence` is the typed contract the rest of the engine builds
on: the sandbox runner (``_runner.py``) executes each :class:`SequenceFrame`'s
``argv`` in order, threads :class:`CaptureBinding` values into later frames'
``{name}`` placeholders, evaluates each :class:`ExpectAssertion` against the
live output, and the golden store / comparison layers persist and diff the
result. The parser (``_parser.py``) is the sole producer of these records; every
model is strict, frozen, and forbids extra fields
(:data:`~cadrumo.core.STRICT_FROZEN_CONFIG`).

The grammar these records model is a body of plain frame lines where a bare
``aeat ...`` line is a visible command frame, ``@setup aeat ...`` an
executed-but-collapsed setup frame, ``@result aeat ...`` the single terminal
verification frame, ``@capture <name> <json-path>`` binds a value from the
preceding frame's parsed envelope, ``@expect <json-path> == <literal>``
attaches a semantic assertion to the preceding frame, ``@blocked <code>
<detail>`` records WHY the preceding ``@static`` frame is not executed, and
``@step <sentence>`` attaches a narration caption to the NEXT frame
(render-side metadata only, never executed).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from cadrumo.core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN

__all__ = [
    "BlockedReason",
    "CaptureBinding",
    "ExpectAssertion",
    "FrameKind",
    "ParsedSequence",
    "SequenceFrame",
    "StaticBlocker",
]

#: A ``cli-sequence`` id (the directive argument) and a ``:seed:`` recipe name:
#: kebab-case, the shape a filesystem-safe reusable identifier takes.
SequenceId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=2, max_length=96, pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$"),
]
#: A capture / placeholder name and a JSON-path leaf segment: a Python-style
#: identifier so ``{name}`` interpolation and env-var-free threading are trivial.
Identifier = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=64, pattern=r"^[A-Za-z_][A-Za-z0-9_]*$"),
]
#: A dotted JSON path into a frame's parsed envelope, e.g. ``result.work_unit_id``,
#: ``result.items[0].id``, ``result.casilla_values.03``, or
#: ``result.casilla_values["decl.importe-operaciones"]``. A dotted segment is
#: an identifier OR an all-digit OBJECT KEY (casilla numbers like ``01``/``03``
#: are JSON object keys, not list indexes); the bracketed ``[n]`` form is the
#: explicit list-index segment; the bracketed double-quoted form
#: ``["<key>"]`` is a literal OBJECT KEY that may carry any character except a
#: double-quote (dots and hyphens included — e.g. M349's declarante casillas
#: keyed ``decl.importe-operaciones`` / ``decl.numero-operadores``, which the
#: dotted grammar would wrongly split on the dot). No embedded-quote escaping:
#: a double-quote inside the key is refused. The pseudo-path ``exit_code`` (a
#: bare identifier) is accepted so ``@expect exit_code == <n>`` declares a
#: non-zero expectation.
JsonPath = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=256,
        pattern=r'^[A-Za-z_][A-Za-z0-9_]*(\.(?:[A-Za-z_][A-Za-z0-9_]*|[0-9]+)|\[[0-9]+\]|\["[^"]*"\])*$',
    ),
]
#: One singular imperative verification sentence carried by the ``:verify:``
#: directive option, rendered as the result frame's caption.
VerifySentence = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=240),
]
#: One singular imperative step-description sentence carried by an ``@step``
#: annotation, rendered as its frame's narration caption. Same shape as the
#: ``:verify:`` sentence: free prose, never a command, never executed.
StepSentence = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=240),
]
#: The specific sentence carried by a ``@blocked`` annotation, naming what
#: exactly is unavailable. A floor of 12 characters refuses a token-length
#: restatement of the code ("live", "n/a") — the code already classifies, so the
#: detail exists to be checkable prose.
BlockedDetail = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=12, max_length=240),
]

#: A JSON literal on the right-hand side of an ``@expect`` assertion — a quoted
#: string, a number, a boolean, or null, parsed from the authored literal.
ExpectLiteral = str | int | float | bool | None


class FrameKind(StrEnum):
    """Closed set of frame kinds in a ``cli-sequence`` body."""

    #: A visible ``aeat ...`` command frame, rendered in document order.
    COMMAND = "command"
    #: An executed ``@setup aeat ...`` frame, rendered collapsed under a
    #: "Preparation" disclosure — executed truth, never invisible magic.
    SETUP = "setup"
    #: The mandatory terminal ``@result aeat ...`` verification frame; exactly
    #: one per sequence with executed frames, and it must be the last EXECUTED
    #: frame (``@static`` frames may follow it).
    RESULT = "result"
    #: A non-executed ``@static aeat ...`` display frame: rendered as the unified
    #: step card (header plus tokenised command) but never run, so it carries no
    #: output and no golden. Admissible only where hermetic execution is
    #: impossible (live AEAT, Google OAuth, interactive wizards, or an
    #: operator-machine-specific path); output is never fabricated for it.
    #: Every static frame MUST carry a :class:`BlockedReason` naming why it does
    #: not execute — a bare marker is indistinguishable from one nobody
    #: converted, and that ambiguity is how a documented dead end hides.
    STATIC = "static"


class StaticBlocker(StrEnum):
    """Closed set of reasons a ``@static`` frame is not executed.

    Every member except :attr:`UNCONVERTED` asserts a VERIFIED impossibility:
    the frame cannot run hermetically, so displaying it is the honest choice.
    :attr:`UNCONVERTED` asserts the opposite — no blocker is known and the frame
    is merely awaiting conversion — so it is the one member a ratchet gate
    drives to zero. Keeping the two apart is the whole point: a real blocker and
    an unconverted frame must never wear the same marker.
    """

    #: Reads a live AEAT surface. That is the whole criterion, and it is a fact
    #: about the HANDLER, never about the verb's name: the CLI naming standard
    #: is one-directional (an AEAT fetch MUST be named ``pull``), so a ``pull``
    #: name does NOT imply an AEAT fetch. ``ledger evidence pull-all`` is the worked
    #: counter-example — it reads Google Drive end to end and belongs under
    #: :attr:`EXTERNAL_SERVICE`. Note that the runner's live-token scan is
    #: deliberately fail-closed over argv, so it refuses such a frame anyway;
    #: that refusal is a reason the frame cannot execute, not evidence about
    #: which surface it reads.
    LIVE_AEAT = "live-aeat"
    #: Needs an interactive terminal: a wizard prompt, a passphrase read, or a
    #: confirmation the hermetic in-process runner cannot answer.
    INTERACTIVE_TTY = "interactive-tty"
    #: Needs the OS credential store (keyring / certificate custody), which is
    #: unavailable to the headless sandbox.
    CREDENTIAL_STORE = "credential-store"
    #: Needs a third-party network service — Google OAuth / Sheets, or an LLM
    #: provider API — that the hermetic sandbox neither has nor should contact.
    EXTERNAL_SERVICE = "external-service"
    #: Needs an operator-supplied artefact (a real AEAT justificante, an
    #: exported profile bundle) that is not, and should not be fabricated as, a
    #: committed fixture.
    OPERATOR_ARTIFACT = "operator-artifact"
    #: Executes cleanly and still cannot be converted, because its output is not
    #: reproducible: a golden built from it diverges on the next run. Exit status
    #: is therefore NOT evidence of convertibility — a stable golden is, and only
    #: a second execution can show the difference. ``ledger export
    #: --export-format xlsx`` is the worked case: the envelope's export id is a
    #: SHA-256 over the written bytes, and openpyxl stamps the workbook with a
    #: per-run timestamp, so the id changes every time. The remedy is a masking
    #: decision (widening ``GOLDEN_MASK_FIELDS``) with its own owner and gates,
    #: not a re-run.
    NONDETERMINISTIC_OUTPUT = "nondeterministic-output"
    #: Blocked by the posture of the PAGE's sandbox rather than by anything about
    #: the verb: the same command converts on one page and refuses on another, so
    #: no per-verb classifier can ever decide it. The worked evidence is the
    #: identical transaction-repository lookup that SUCCEEDS on the
    #: ``ledger-evidence`` page, whose sandbox holds an unlocked bucket session,
    #: and FAILS on ``troubleshooting``, whose sandbox deliberately holds none —
    #: measured exit 4, "No active bucket session is open." Deciding this member
    #: requires running the frame in ITS OWN page's sandbox.
    SANDBOX_POSTURE = "sandbox-posture"
    #: Refused because the filing obligation's window is not open in the frozen
    #: sandbox instant. Stating the condition beats stretching
    #: :attr:`OPERATOR_ARTIFACT`: nothing is missing, the calendar simply does not
    #: permit the action yet. Declare it only from the refusal text, never from
    #: the verb, since the same verb converts inside its window.
    OBLIGATION_WINDOW = "obligation-window"
    #: No verified blocker: the frame COULD execute and is awaiting conversion.
    #: Never a justification — a visible, counted debt the ratchet retires. The
    #: bar is a REPRODUCIBLE run, not a zero exit; see
    #: :attr:`NONDETERMINISTIC_OUTPUT` for the trap, and run any candidate twice
    #: before declaring this.
    #:
    #: Read the two hazards below as examples, never as an exhaustive checklist:
    #: a reason this member is wrong is any property a single invocation cannot
    #: show, and the list of those is open.
    #:
    #: A frame carrying a ``<placeholder>`` metavariable has not been run AT
    #: ALL, so this member states only that its FORM is not yet rewritten; it is
    #: never a verdict that the frame is convertible. Converting one means
    #: authoring the ``@capture`` chain that produces the real id and then
    #: running THAT twice, like any other candidate — the capture chain is the
    #: thing under test, not the id. ``aeat app ledger participation
    #: <transaction-id>`` is the worked refutation: it was recorded as needing
    #: only a captured id, and supplying a real one still refused with exit 4
    #: under :attr:`SANDBOX_POSTURE`.
    UNCONVERTED = "unconverted"


class BlockedReason(BaseModel):
    """The ``@blocked <code> <detail>`` annotation on a ``@static`` frame.

    ``code`` is the closed-set classification a gate can cross-check against the
    frame's own argv; ``detail`` is the specific, human-checkable sentence that
    makes the refusal auditable rather than a generic label.
    """

    model_config = _STRICT_FROZEN

    code: StaticBlocker
    detail: BlockedDetail


class CaptureBinding(BaseModel):
    """A ``@capture <name> <json-path>`` binding attached to a frame.

    After the owning frame executes, ``json_path`` is read from its parsed JSON
    envelope and bound to ``name``; later frames interpolate it as ``{name}``.
    """

    model_config = _STRICT_FROZEN

    name: Identifier
    json_path: JsonPath


class ExpectAssertion(BaseModel):
    """An ``@expect <json-path> == <literal>`` assertion attached to a frame.

    ``expected`` is the JSON literal parsed from the authored right-hand side.
    The parser records it verbatim; the runner evaluates ``json_path == expected``
    against the frame's live output. The pseudo-path ``exit_code`` asserts the
    frame's process exit code.
    """

    model_config = _STRICT_FROZEN

    json_path: JsonPath
    expected: ExpectLiteral


class SequenceFrame(BaseModel):
    """One executed frame of a ``cli-sequence``.

    ``argv`` is the shell-decomposed command (always leading with ``aeat``),
    preserving any ``{name}`` placeholder tokens for the runner to interpolate.
    ``captures`` and ``expects`` are the annotations authored directly beneath
    the frame. ``placeholder_names`` lists every ``{name}`` referenced in
    ``argv``, which the parser has already proven resolves to a prior capture.
    ``step_description`` is the optional ``@step`` narration sentence authored
    directly ABOVE the frame — render-side metadata only, never executed truth:
    the runner, golden store, and comparison ignore it entirely, so authoring or
    editing an ``@step`` line can never invalidate a committed golden.
    ``blocked`` is the mandatory ``@blocked`` reason on a
    :attr:`FrameKind.STATIC` frame and is ``None`` on every executed kind — the
    parser enforces both directions, so a static frame can never ship without a
    stated reason and an executed frame can never carry a stale one.
    ``source`` and ``line_number`` locate the frame for diagnostics
    (``"body"`` or ``"seed:<name>"``).
    """

    model_config = _STRICT_FROZEN

    kind: FrameKind
    command_line: Annotated[str, StringConstraints(min_length=1)]
    argv: tuple[Annotated[str, StringConstraints(min_length=1)], ...] = Field(min_length=1)
    captures: tuple[CaptureBinding, ...] = Field(default=())
    expects: tuple[ExpectAssertion, ...] = Field(default=())
    placeholder_names: tuple[Identifier, ...] = Field(default=())
    step_description: StepSentence | None = None
    blocked: BlockedReason | None = None
    source: Annotated[str, StringConstraints(min_length=1)]
    line_number: int = Field(ge=1)


class ParsedSequence(BaseModel):
    """A fully parsed, structurally valid ``cli-sequence``.

    ``frames`` are in document order: any inlined ``:seed:`` setup frames first,
    then the directive body's own frames. A sequence with at least one executed
    frame ends its executed run in exactly one :attr:`FrameKind.RESULT` frame
    carrying at least one :class:`ExpectAssertion`; a sequence of only
    :attr:`FrameKind.STATIC` frames runs nothing and carries no result. ``verify``
    is the singular imperative sentence from the ``:verify:`` option, mandatory
    for a sequence with executed frames and ``None`` for an all-static sequence
    (nothing runs to verify). ``seed`` names the inlined recipe when one was
    requested.
    """

    model_config = _STRICT_FROZEN

    sequence_id: SequenceId
    verify: VerifySentence | None = None
    seed: SequenceId | None = None
    frames: tuple[SequenceFrame, ...] = Field(min_length=1)

    @property
    def executed_frames(self) -> tuple[SequenceFrame, ...]:
        """The frames that actually run (every kind except :attr:`FrameKind.STATIC`)."""
        return tuple(frame for frame in self.frames if frame.kind is not FrameKind.STATIC)

    @property
    def result_frame(self) -> SequenceFrame | None:
        """The terminal :attr:`FrameKind.RESULT` frame, or ``None`` for an all-static sequence."""
        return next((frame for frame in self.frames if frame.kind is FrameKind.RESULT), None)

    @property
    def capture_names(self) -> tuple[str, ...]:
        """Every capture name bound across the sequence, in frame order."""
        return tuple(binding.name for frame in self.frames for binding in frame.captures)
