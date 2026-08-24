"""Frame-grammar parser for the ``cli-sequence`` MyST directive.

Parses a directive body of plain frame lines into a strict
:class:`~dev.docs.sequences._schema.ParsedSequence`. The grammar, line by line:

- ``aeat ...`` -- a visible command frame.
- ``@setup aeat ...`` -- an executed, visually collapsed setup frame.
- ``@result aeat ...`` -- the mandatory terminal verification frame (exactly one,
  last).
- ``@capture <name> <json-path>`` -- binds a value from the preceding frame's
  parsed envelope; later frames interpolate it as ``{name}``.
- ``@expect <json-path> == <literal>`` -- a semantic assertion on the preceding
  frame.
- ``@blocked <code> <detail>`` -- the MANDATORY reason a preceding ``@static``
  frame is not executed: a closed-set :class:`~dev.docs.sequences._schema.StaticBlocker`
  code a gate can cross-check against the frame's own argv, plus the specific
  sentence naming what is unavailable. Refused on an executed frame.
- ``@step <imperative sentence>`` -- a narration caption for the NEXT frame
  (setup, command, or result). Render-side metadata only: never executed,
  never golden-compared, and free prose (no placeholder scan).

Parsing is two-staged. :func:`parse_frame_lines` is the low-level pass that turns
raw text into ordered frame builders plus a list of accumulated problem strings,
with no structural judgement -- it is shared with the seed-recipe loader
(``_seeds.py``). :func:`parse_sequence` is the public entry: it inlines a
``:seed:`` recipe when requested, runs the line pass over the body, then enforces
the sequence-result contract and placeholder resolution, raising a single
accumulating :class:`~dev.docs.sequences._errors.SequenceParseError` naming every
fault. No fault aborts the pass; the author sees the whole worklist at once.
"""

from __future__ import annotations

import json
import re
import shlex
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import get_args

from pydantic import StringConstraints

from ._errors import SequenceParseError
from ._schema import (
    BlockedDetail,
    BlockedReason,
    CaptureBinding,
    ExpectAssertion,
    ExpectLiteral,
    FrameKind,
    Identifier,
    JsonPath,
    ParsedSequence,
    SequenceFrame,
    SequenceId,
    StaticBlocker,
    StepSentence,
    VerifySentence,
)

__all__ = ["parse_frame_lines", "parse_sequence", "result_frame_asserts_result_payload"]

#: The sole human CLI executable; every frame command leads with this token.
_EXECUTABLE: str = "aeat"
#: The ``@expect`` pseudo-path asserting a frame's process exit code; its
#: literal MUST be an integer.
_EXIT_CODE_PATH: str = "exit_code"


def _string_constraints(annotated: object) -> StringConstraints:
    """Return the :class:`StringConstraints` metadata of an annotated str alias.

    The parser validates ids, identifiers, and JSON paths against the SAME
    pattern and length bounds the strict schema enforces, driven off the single
    schema declaration so the two surfaces cannot drift (a raw pydantic
    ``ValidationError`` would otherwise escape the accumulating-error contract).
    """
    for meta in get_args(annotated):
        if isinstance(meta, StringConstraints):
            return meta
    raise TypeError(f"{annotated!r} carries no StringConstraints metadata")


_SEQUENCE_ID_CONSTRAINTS = _string_constraints(SequenceId)
_IDENTIFIER_CONSTRAINTS = _string_constraints(Identifier)
_JSON_PATH_CONSTRAINTS = _string_constraints(JsonPath)
_VERIFY_CONSTRAINTS = _string_constraints(VerifySentence)
_STEP_CONSTRAINTS = _string_constraints(StepSentence)
_BLOCKED_DETAIL_CONSTRAINTS = _string_constraints(BlockedDetail)

_SEQUENCE_ID_RE = re.compile(_SEQUENCE_ID_CONSTRAINTS.pattern or "")
_IDENTIFIER_RE = re.compile(_IDENTIFIER_CONSTRAINTS.pattern or "")
_JSON_PATH_RE = re.compile(_JSON_PATH_CONSTRAINTS.pattern or "")
#: Matches every ``{...}`` interpolation token; the inner text is validated
#: separately so a malformed placeholder is an instructive error, not a miss.
_PLACEHOLDER_RE = re.compile(r"\{([^{}]*)\}")
#: Any residual brace after valid ``{...}`` tokens are stripped is an unbalanced
#: placeholder (e.g. ``{work_unit_id`` with no closer).
_STRAY_BRACE_RE = re.compile(r"[{}]")

#: The frame-introducing sigils, mapped to the frame kind they declare.
_FRAME_SIGILS: dict[str, FrameKind] = {
    "@setup": FrameKind.SETUP,
    "@result": FrameKind.RESULT,
    "@static": FrameKind.STATIC,
}


@dataclass
class _FrameBuilder:
    """Mutable accumulator for one frame while a line pass is in progress."""

    kind: FrameKind
    command_line: str
    argv: tuple[str, ...]
    placeholder_names: tuple[str, ...]
    source: str
    line_number: int
    captures: list[CaptureBinding] = field(default_factory=list)
    expects: list[ExpectAssertion] = field(default_factory=list)
    #: The source line of each entry in :attr:`captures`, positionally aligned,
    #: so a duplicate-name diagnostic points at the offending ``@capture`` line
    #: rather than the frame's command line.
    capture_lines: list[int] = field(default_factory=list)
    #: The ``@step`` narration sentence authored above this frame, if any.
    step_description: str | None = None
    #: The ``@blocked`` reason authored beneath this ``@static`` frame, if any.
    blocked: BlockedReason | None = None

    def build(self) -> SequenceFrame:
        return SequenceFrame(
            kind=self.kind,
            command_line=self.command_line,
            argv=self.argv,
            captures=tuple(self.captures),
            expects=tuple(self.expects),
            placeholder_names=self.placeholder_names,
            step_description=self.step_description,
            blocked=self.blocked,
            source=self.source,
            line_number=self.line_number,
        )


def _at(source: str, line_number: int) -> str:
    """Render a source/line locator prefix for a problem message."""
    if source == "body":
        return f"line {line_number}"
    return f"{source} line {line_number}"


def _validate_kebab_id(value: str, label: str, problems: list[str]) -> None:
    """Validate a kebab-case id against the shared :data:`SequenceId` constraints.

    Checks the pattern AND the length bounds the strict schema enforces, so an
    over-long id is an accumulated problem here rather than a raw pydantic
    ``ValidationError`` escaping the single-error contract downstream.
    """
    minimum = _SEQUENCE_ID_CONSTRAINTS.min_length or 0
    maximum = _SEQUENCE_ID_CONSTRAINTS.max_length
    if not _SEQUENCE_ID_RE.match(value) or (maximum is not None and not (minimum <= len(value) <= maximum)):
        bound = f"{minimum} to {maximum}" if maximum is not None else f"at least {minimum}"
        problems.append(f"{label} {value!r} must be a kebab-case identifier of {bound} characters")


def _placeholder_names(command_line: str, source: str, line_number: int, problems: list[str]) -> tuple[str, ...]:
    """Extract and validate every ``{name}`` placeholder in a command line."""
    names: list[str] = []
    for match in _PLACEHOLDER_RE.finditer(command_line):
        inner = match.group(1).strip()
        if not _IDENTIFIER_RE.match(inner):
            problems.append(
                f"{_at(source, line_number)}: invalid placeholder {match.group(0)!r}; "
                "a placeholder is '{name}' where name is a prior @capture identifier",
            )
            continue
        names.append(inner)
    # A lone '{' or '}' surviving after every balanced ``{...}`` token is removed
    # is an unterminated placeholder, which would otherwise pass through as a
    # literal argv token and misfire at runtime.
    if _STRAY_BRACE_RE.search(_PLACEHOLDER_RE.sub("", command_line)):
        problems.append(
            f"{_at(source, line_number)}: unbalanced placeholder brace in {command_line!r}; "
            "a placeholder is '{name}' with a matching brace",
        )
    return tuple(names)


def _decompose_argv(command_line: str, source: str, line_number: int, problems: list[str]) -> tuple[str, ...] | None:
    """Shell-decompose a command line into argv, leading with ``aeat``.

    Returns ``None`` (and records a problem) when the line does not tokenise or
    does not invoke the ``aeat`` executable.
    """
    try:
        tokens = shlex.split(command_line, posix=True)
    except ValueError as exc:
        problems.append(f"{_at(source, line_number)}: cannot parse command line ({exc}): {command_line!r}")
        return None
    if not tokens:
        problems.append(f"{_at(source, line_number)}: empty command line")
        return None
    if tokens[0] != _EXECUTABLE:
        problems.append(
            f"{_at(source, line_number)}: a command frame must invoke {_EXECUTABLE!r}, "
            f"got {tokens[0]!r}: {command_line!r}",
        )
        return None
    return tuple(tokens)


def _parse_capture(rest: str, source: str, line_number: int, problems: list[str]) -> CaptureBinding | None:
    """Parse an ``@capture <name> <json-path>`` annotation body."""
    parts = rest.split()
    if len(parts) != 2:
        problems.append(
            f"{_at(source, line_number)}: @capture must be '@capture <name> <json-path>', got {rest!r}",
        )
        return None
    name, json_path = parts
    ok = True
    if not _IDENTIFIER_RE.match(name):
        problems.append(f"{_at(source, line_number)}: @capture name {name!r} is not a valid identifier")
        ok = False
    if not _JSON_PATH_RE.match(json_path):
        problems.append(f"{_at(source, line_number)}: @capture json-path {json_path!r} is not a valid dotted path")
        ok = False
    if not ok:
        return None
    return CaptureBinding(name=name, json_path=json_path)


def _parse_expect_literal(
    literal: str,
    source: str,
    line_number: int,
    problems: list[str],
) -> tuple[ExpectLiteral, bool]:
    """Parse the right-hand JSON literal of an ``@expect`` assertion."""
    try:
        value = json.loads(literal)
    except json.JSONDecodeError:
        problems.append(
            f"{_at(source, line_number)}: @expect value {literal!r} must be a JSON literal "
            '(quote strings, e.g. "verified_complete"; numbers, true/false, null are bare)',
        )
        return None, False
    if not isinstance(value, (str, int, float, bool)) and value is not None:
        problems.append(
            f"{_at(source, line_number)}: @expect value {literal!r} must be a scalar JSON literal, "
            "not an array or object",
        )
        return None, False
    return value, True


def _parse_expect(rest: str, source: str, line_number: int, problems: list[str]) -> ExpectAssertion | None:
    """Parse an ``@expect <json-path> == <literal>`` annotation body."""
    path_part, separator, literal_part = rest.partition("==")
    if not separator:
        problems.append(
            f"{_at(source, line_number)}: @expect must be '@expect <json-path> == <literal>', got {rest!r}",
        )
        return None
    json_path = path_part.strip()
    literal = literal_part.strip()
    ok = True
    if not _JSON_PATH_RE.match(json_path):
        problems.append(f"{_at(source, line_number)}: @expect json-path {json_path!r} is not a valid dotted path")
        ok = False
    if not literal:
        problems.append(f"{_at(source, line_number)}: @expect is missing a value after '=='")
        ok = False
    value: ExpectLiteral = None
    if literal:
        value, literal_ok = _parse_expect_literal(literal, source, line_number, problems)
        ok = ok and literal_ok
    # exit_code is an integer exit status; a bool is not an exit code even
    # though ``bool`` is an ``int`` subclass in Python.
    if ok and json_path == _EXIT_CODE_PATH and not (isinstance(value, int) and not isinstance(value, bool)):
        problems.append(
            f"{_at(source, line_number)}: @expect {_EXIT_CODE_PATH} value {literal!r} must be an integer literal",
        )
        ok = False
    if not ok:
        return None
    return ExpectAssertion(json_path=json_path, expected=value)


#: The accepted ``@blocked`` codes, rendered for a diagnostic's accepted-value set.
_BLOCKER_CODES: tuple[str, ...] = tuple(member.value for member in StaticBlocker)


def _parse_blocked(rest: str, source: str, line_number: int, problems: list[str]) -> BlockedReason | None:
    """Parse a ``@blocked <code> <detail>`` annotation body.

    The code is validated against the closed :class:`StaticBlocker` set and the
    refusal enumerates every accepted value, so a mistyped code names its own
    fix rather than failing as a bare "value invalid".
    """
    code_text, _, detail_text = rest.partition(" ")
    code_text = code_text.strip()
    detail = detail_text.strip()
    if not code_text:
        problems.append(
            f"{_at(source, line_number)}: @blocked must be '@blocked <code> <detail>' where code is "
            f"one of {', '.join(_BLOCKER_CODES)}",
        )
        return None
    try:
        code = StaticBlocker(code_text)
    except ValueError:
        problems.append(
            f"{_at(source, line_number)}: @blocked code {code_text!r} is not a known blocker; "
            f"accepted values are {', '.join(_BLOCKER_CODES)}",
        )
        return None
    minimum = _BLOCKED_DETAIL_CONSTRAINTS.min_length or 0
    maximum = _BLOCKED_DETAIL_CONSTRAINTS.max_length
    if len(detail) < minimum:
        problems.append(
            f"{_at(source, line_number)}: @blocked {code_text} needs a specific reason of at least "
            f"{minimum} characters naming what is unavailable (e.g. 'Reads the AEAT sede over the "
            "operator's live session.'); the code alone is not a reason",
        )
        return None
    if maximum is not None and len(detail) > maximum:
        problems.append(f"{_at(source, line_number)}: the @blocked detail must be at most {maximum} characters")
        return None
    return BlockedReason(code=code, detail=detail)


def _parse_step_sentence(rest: str, source: str, line_number: int, problems: list[str]) -> tuple[str, bool]:
    """Parse an ``@step <imperative sentence>`` annotation body.

    The sentence is narration prose, not a command: it is never argv-decomposed
    and the ``{name}`` placeholder scan does NOT apply. Only emptiness and the
    schema's length bound are enforced, parser-side, so a fault accumulates
    instead of escaping as a raw pydantic ``ValidationError``.
    """
    sentence = rest.strip()
    if not sentence:
        problems.append(
            f"{_at(source, line_number)}: @step requires one imperative sentence "
            "describing the frame below it (e.g. '@step Create the work unit.')",
        )
        return "", False
    maximum = _STEP_CONSTRAINTS.max_length
    if maximum is not None and len(sentence) > maximum:
        problems.append(f"{_at(source, line_number)}: the @step sentence must be at most {maximum} characters")
        return "", False
    return sentence, True


def parse_frame_lines(text: str, *, source: str) -> tuple[list[_FrameBuilder], list[str]]:
    """Parse raw directive/seed text into ordered frame builders and problems.

    The low-level pass: it classifies every non-blank line, decomposes command
    frames into argv, attaches ``@capture`` / ``@expect`` annotations to the frame
    above them, and accumulates an instructive problem string (naming the source
    and line) for every grammar violation. It makes NO structural judgement about
    result frames, verification, or placeholder resolution -- that is
    :func:`parse_sequence`'s job -- so the seed-recipe loader can reuse it.

    Args:
        text: The raw body text (newline-separated frame lines).
        source: A locator label for diagnostics (``"body"`` or ``"seed:<name>"``).

    Returns:
        A ``(builders, problems)`` pair. ``builders`` are in document order;
        ``problems`` is empty when every line parsed cleanly.
    """
    builders: list[_FrameBuilder] = []
    problems: list[str] = []
    current: _FrameBuilder | None = None
    #: A parsed ``@step`` sentence (with its line, for diagnostics) waiting for
    #: the NEXT frame line to attach to.
    pending_step: tuple[str, int] | None = None

    for offset, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("```") or line.startswith("~~~"):
            problems.append(f"{_at(source, offset)}: nested code fences are not allowed inside a cli-sequence")
            continue

        head, _, remainder = line.partition(" ")
        remainder = remainder.strip()

        if head == _EXECUTABLE or head in _FRAME_SIGILS:
            kind = _FRAME_SIGILS.get(head, FrameKind.COMMAND)
            command_line = line if head == _EXECUTABLE else remainder
            if not command_line:
                problems.append(f"{_at(source, offset)}: {head} requires an '{_EXECUTABLE} ...' command")
                current = None
                continue
            argv = _decompose_argv(command_line, source, offset, problems)
            if argv is None:
                current = None
                continue
            placeholders = _placeholder_names(command_line, source, offset, problems)
            current = _FrameBuilder(
                kind=kind,
                command_line=command_line,
                argv=argv,
                placeholder_names=placeholders,
                source=source,
                line_number=offset,
            )
            if pending_step is not None:
                current.step_description = pending_step[0]
                pending_step = None
            builders.append(current)
            continue

        if head == "@step":
            # Narration prose for the NEXT frame — never a command, so no
            # argv decomposition and no placeholder/brace scan applies.
            sentence, sentence_ok = _parse_step_sentence(remainder, source, offset, problems)
            if pending_step is not None:
                problems.append(
                    f"{_at(source, offset)}: a frame takes one @step description; this line "
                    f"follows an unattached @step at {_at(source, pending_step[1])}",
                )
                continue
            if sentence_ok:
                pending_step = (sentence, offset)
            continue

        if head == "@capture":
            if current is None:
                problems.append(f"{_at(source, offset)}: @capture must follow a command frame")
                continue
            if current.kind is FrameKind.STATIC:
                problems.append(
                    f"{_at(source, offset)}: @capture cannot annotate a @static frame; a @static "
                    "frame is not executed, so it produces no output to capture",
                )
                continue
            binding = _parse_capture(remainder, source, offset, problems)
            if binding is not None:
                current.captures.append(binding)
                current.capture_lines.append(offset)
            continue

        if head == "@expect":
            if current is None:
                problems.append(f"{_at(source, offset)}: @expect must follow a command frame")
                continue
            if current.kind is FrameKind.STATIC:
                problems.append(
                    f"{_at(source, offset)}: @expect cannot annotate a @static frame; a @static "
                    "frame is not executed, so there is nothing to assert",
                )
                continue
            assertion = _parse_expect(remainder, source, offset, problems)
            if assertion is not None:
                current.expects.append(assertion)
            continue

        if head == "@blocked":
            if current is None:
                problems.append(f"{_at(source, offset)}: @blocked must follow a @static frame")
                continue
            if current.kind is not FrameKind.STATIC:
                problems.append(
                    f"{_at(source, offset)}: @blocked cannot annotate a {current.kind.value} frame; "
                    "an executed frame runs, so it has no blocker to record",
                )
                continue
            if current.blocked is not None:
                problems.append(
                    f"{_at(source, offset)}: a @static frame takes one @blocked reason; "
                    f"the frame at {_at(current.source, current.line_number)} already carries one",
                )
                continue
            current.blocked = _parse_blocked(remainder, source, offset, problems)
            continue

        if head.startswith("@"):
            problems.append(
                f"{_at(source, offset)}: unknown sigil {head!r}; expected "
                "@setup, @result, @static, @capture, @expect, @blocked, or @step",
            )
            current = None
            continue

        problems.append(
            f"{_at(source, offset)}: unrecognised line {line!r}; expected an "
            f"'{_EXECUTABLE} ...' command, @setup, @result, @static, @capture, @expect, @blocked, or @step",
        )
        current = None

    if pending_step is not None:
        problems.append(
            f"{_at(source, pending_step[1])}: @step must be followed by the frame it "
            "describes; this trailing @step attaches to nothing",
        )

    return builders, problems


def _enforce_result_contract(builders: list[_FrameBuilder], problems: list[str]) -> None:
    """Enforce the @result contract, relaxed for ``@static`` frames.

    An all-``@static`` sequence runs nothing, so it must carry NO @result. A
    sequence with at least one executed frame must carry exactly one @result,
    which must be the LAST EXECUTED frame (``@static`` frames may follow it) and
    carry at least one @expect.
    """
    executed = [index for index, builder in enumerate(builders) if builder.kind is not FrameKind.STATIC]
    result_indices = [index for index, builder in enumerate(builders) if builder.kind is FrameKind.RESULT]

    if not executed:
        # An all-@static sequence runs nothing, so it needs no @result (and a
        # @result is itself an executed frame, so ``executed`` would be non-empty).
        return

    if not result_indices:
        problems.append(
            "a sequence with executed frames must end its executed run in exactly one @result frame; found none",
        )
        return
    if len(result_indices) > 1:
        located = ", ".join(_at(builders[index].source, builders[index].line_number) for index in result_indices)
        problems.append(f"a sequence must have exactly one @result frame; found {len(result_indices)} ({located})")
        return
    only = result_indices[0]
    if only != executed[-1]:
        result = builders[only]
        problems.append(
            f"the @result frame ({_at(result.source, result.line_number)}) must be the last EXECUTED "
            "frame in the sequence; only @static frames may follow it",
        )
        return
    result = builders[only]
    if not result.expects:
        problems.append(
            f"the @result frame ({_at(result.source, result.line_number)}) must carry at least one "
            "@expect assertion (e.g. '@expect result.status == \"verified_complete\"')",
        )


#: A json-path addressing the result PAYLOAD (the ``result`` object of the
#: envelope), as opposed to the ``exit_code`` process status or the ``status``
#: envelope-spine field.
_SEMANTIC_PAYLOAD_PREFIXES: tuple[str, ...] = ("result.", "result[", "error.", "error[")


def result_frame_asserts_result_payload(sequence: ParsedSequence) -> bool:
    """Whether the sequence's ``@result`` frame asserts the result PAYLOAD.

    The tightened @result contract requires at least one ``@expect`` on
    the structured success or refusal payload — a ``result.*`` or ``error.*``
    json-path — so a sequence verifies the MEANING of its final output, not merely that the process
    exited (``exit_code``) or that the envelope status equals a value (``status``,
    a spine field). A frame asserting only ``exit_code`` (and/or ``status``) proves
    the command ran without proving it produced the right answer, the weak pattern
    this contract eliminates. An all-``@static`` sequence has no ``@result`` frame
    and is vacuously compliant.
    """
    frame = sequence.result_frame
    if frame is None:
        return True
    if frame.command_line.rstrip().endswith("--help"):
        # Click help is deliberately human-readable text, not a JSON envelope.
        # Its exact process-success assertion is the only available structured
        # contract; text rendering itself is covered by the CLI help snapshots.
        return any(assertion.json_path == "exit_code" and assertion.expected == 0 for assertion in frame.expects)
    return any(
        assertion.json_path in {"result", "error"}
        or assertion.json_path.startswith(_SEMANTIC_PAYLOAD_PREFIXES)
        for assertion in frame.expects
    )


def _enforce_static_frames_state_a_reason(builders: list[_FrameBuilder], problems: list[str]) -> None:
    """Every ``@static`` frame must carry a ``@blocked`` reason.

    A bare ``@static`` marker is indistinguishable from a frame nobody got round
    to converting, and that ambiguity is exactly how a documented dead end hides:
    the quickstart export frame sat static and unexercised until its narrative was
    found to have no working path. Requiring the reason at parse time means the
    ambiguity cannot be re-authored.
    """
    for builder in builders:
        if builder.kind is FrameKind.STATIC and builder.blocked is None:
            problems.append(
                f"{_at(builder.source, builder.line_number)}: the @static frame {builder.command_line!r} "
                "must state why it is not executed on the line beneath it: "
                f"'@blocked <code> <detail>' where code is one of {', '.join(_BLOCKER_CODES)}. "
                f"Use '{StaticBlocker.UNCONVERTED.value}' only when nothing actually blocks execution",
            )


def _enforce_captures_and_placeholders(builders: list[_FrameBuilder], problems: list[str]) -> None:
    """Enforce unique capture names and prior-capture placeholder resolution."""
    available: set[str] = set()
    seen_names: set[str] = set()
    for builder in builders:
        for name in builder.placeholder_names:
            if name not in available:
                problems.append(
                    f"{_at(builder.source, builder.line_number)}: placeholder '{{{name}}}' does not resolve "
                    "to an earlier @capture",
                )
        for binding, capture_line in zip(builder.captures, builder.capture_lines, strict=True):
            if binding.name in seen_names:
                problems.append(
                    f"{_at(builder.source, capture_line)}: duplicate @capture name {binding.name!r}",
                )
            seen_names.add(binding.name)
        # A capture is produced by its own frame's output, so it only becomes
        # available to frames that run strictly later.
        available.update(binding.name for binding in builder.captures)


def parse_sequence(
    *,
    sequence_id: str,
    options: Mapping[str, str | None],
    body: str,
    seeds_root: Path | None = None,
) -> ParsedSequence:
    """Parse a ``cli-sequence`` directive into a strict :class:`ParsedSequence`.

    Inlines the ``:seed:`` recipe (when present) as leading setup frames, parses
    the directive body, then enforces the sequence-result contract, unique
    capture names, and prior-capture placeholder resolution. Every grammar
    and structural fault is accumulated and raised together.

    Args:
        sequence_id: The directive argument (the unique sequence id).
        options: The directive options mapping; ``seed`` and ``verify`` are read.
            ``verify`` is required.
        body: The directive body (the frame lines).
        seeds_root: The directory holding ``<name>.seq`` recipes; defaults to the
            committed ``docs/_sequences/seeds/`` tree when ``None``.

    Returns:
        The validated :class:`ParsedSequence`.

    Raises:
        SequenceParseError: When the id, options, or body violate the grammar or
            the structural contract. The error enumerates every fault.
    """
    from ._seeds import load_seed_frames  # deferred: _seeds imports this module's line parser

    problems: list[str] = []

    _validate_kebab_id(sequence_id.strip(), "sequence id", problems)

    builders: list[_FrameBuilder] = []
    seed_raw = options.get("seed")
    seed = (seed_raw or "").strip() or None
    if seed is not None:
        before = len(problems)
        _validate_kebab_id(seed, ":seed: recipe name", problems)
        if len(problems) == before:
            seed_builders, seed_problems = load_seed_frames(seed, seeds_root=seeds_root)
            problems.extend(seed_problems)
            builders.extend(seed_builders)

    body_builders, body_problems = parse_frame_lines(body, source="body")
    problems.extend(body_problems)
    builders.extend(body_builders)

    if not builders:
        problems.append("a cli-sequence must contain at least one frame")

    _enforce_result_contract(builders, problems)
    _enforce_static_frames_state_a_reason(builders, problems)
    _enforce_captures_and_placeholders(builders, problems)

    # The :verify: contract depends on whether the sequence runs anything: it is
    # mandatory when at least one frame executes and refused for an all-@static
    # sequence (nothing runs, so a "Confirm ..." sentence would overclaim).
    verify_text = (options.get("verify") or "").strip()
    verify_max = _VERIFY_CONSTRAINTS.max_length
    all_static = bool(builders) and all(builder.kind is FrameKind.STATIC for builder in builders)
    if all_static:
        if verify_text:
            problems.append(
                "an all-@static sequence runs nothing, so the :verify: option is refused "
                "(a verification sentence would overclaim); remove :verify:",
            )
        verify: str | None = None
    else:
        if not verify_text:
            problems.append(
                "the :verify: option is required: one singular imperative verification sentence "
                '(e.g. "Verify the calculation before exporting.")',
            )
        elif verify_max is not None and len(verify_text) > verify_max:
            problems.append(f"the :verify: sentence must be at most {verify_max} characters")
        verify = verify_text or None

    if problems:
        raise SequenceParseError(sequence_id, problems)

    return ParsedSequence(
        sequence_id=sequence_id.strip(),
        verify=verify,
        seed=seed,
        frames=tuple(builder.build() for builder in builders),
    )
