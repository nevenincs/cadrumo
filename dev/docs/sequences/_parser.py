"""Frame-grammar parser for the ``cli-sequence`` MyST directive (ADR D1, D4).

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

Parsing is two-staged. :func:`parse_frame_lines` is the low-level pass that turns
raw text into ordered frame builders plus a list of accumulated problem strings,
with no structural judgement -- it is shared with the seed-recipe loader
(``_seeds.py``). :func:`parse_sequence` is the public entry: it inlines a
``:seed:`` recipe when requested, runs the line pass over the body, then enforces
the sequence-result contract (ADR D4) and placeholder resolution, raising a single
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

from ._errors import SequenceParseError
from ._schema import (
    CaptureBinding,
    ExpectAssertion,
    ExpectLiteral,
    FrameKind,
    ParsedSequence,
    SequenceFrame,
)

__all__ = ["parse_frame_lines", "parse_sequence"]

#: The sole human CLI executable; every frame command leads with this token.
_EXECUTABLE: str = "aeat"

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_JSON_PATH_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*|\[[0-9]+\])*$")
#: Matches every ``{...}`` interpolation token; the inner text is validated
#: separately so a malformed placeholder is an instructive error, not a miss.
_PLACEHOLDER_RE = re.compile(r"\{([^{}]*)\}")

#: The frame-introducing sigils, mapped to the frame kind they declare.
_FRAME_SIGILS: dict[str, FrameKind] = {
    "@setup": FrameKind.SETUP,
    "@result": FrameKind.RESULT,
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

    def build(self) -> SequenceFrame:
        return SequenceFrame(
            kind=self.kind,
            command_line=self.command_line,
            argv=self.argv,
            captures=tuple(self.captures),
            expects=tuple(self.expects),
            placeholder_names=self.placeholder_names,
            source=self.source,
            line_number=self.line_number,
        )


def _at(source: str, line_number: int) -> str:
    """Render a source/line locator prefix for a problem message."""
    if source == "body":
        return f"line {line_number}"
    return f"{source} line {line_number}"


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
    if not ok:
        return None
    return ExpectAssertion(json_path=json_path, expected=value)


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
            builders.append(current)
            continue

        if head == "@capture":
            if current is None:
                problems.append(f"{_at(source, offset)}: @capture must follow a command frame")
                continue
            binding = _parse_capture(remainder, source, offset, problems)
            if binding is not None:
                current.captures.append(binding)
            continue

        if head == "@expect":
            if current is None:
                problems.append(f"{_at(source, offset)}: @expect must follow a command frame")
                continue
            assertion = _parse_expect(remainder, source, offset, problems)
            if assertion is not None:
                current.expects.append(assertion)
            continue

        if head.startswith("@"):
            problems.append(
                f"{_at(source, offset)}: unknown sigil {head!r}; expected @setup, @result, @capture, or @expect",
            )
            current = None
            continue

        problems.append(
            f"{_at(source, offset)}: unrecognised line {line!r}; "
            f"expected an '{_EXECUTABLE} ...' command, @setup, @result, @capture, or @expect",
        )
        current = None

    return builders, problems


def _enforce_result_contract(builders: list[_FrameBuilder], problems: list[str]) -> None:
    """Enforce the exactly-one-terminal-@result contract (ADR D4)."""
    result_indices = [index for index, builder in enumerate(builders) if builder.kind is FrameKind.RESULT]
    if not result_indices:
        problems.append("a sequence must end in exactly one @result frame; found none")
        return
    if len(result_indices) > 1:
        located = ", ".join(_at(builders[index].source, builders[index].line_number) for index in result_indices)
        problems.append(f"a sequence must have exactly one @result frame; found {len(result_indices)} ({located})")
        return
    only = result_indices[0]
    if only != len(builders) - 1:
        result = builders[only]
        problems.append(
            f"the @result frame ({_at(result.source, result.line_number)}) must be the last frame in the sequence",
        )
        return
    result = builders[only]
    if not result.expects:
        problems.append(
            f"the @result frame ({_at(result.source, result.line_number)}) must carry at least one "
            "@expect assertion (e.g. '@expect result.status == \"verified_complete\"')",
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
        for binding in builder.captures:
            if binding.name in seen_names:
                problems.append(
                    f"{_at(builder.source, builder.line_number)}: duplicate @capture name {binding.name!r}",
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
    the directive body, then enforces the sequence-result contract (ADR D4),
    unique capture names, and prior-capture placeholder resolution. Every grammar
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

    if not _SEQUENCE_ID_RE.match(sequence_id.strip()):
        problems.append(f"sequence id {sequence_id!r} must be a kebab-case identifier")

    verify_raw = options.get("verify")
    verify = (verify_raw or "").strip()
    if not verify:
        problems.append(
            "the :verify: option is required: one singular imperative verification sentence "
            '(e.g. "Verify the calculation before exporting.")',
        )

    builders: list[_FrameBuilder] = []
    seed_raw = options.get("seed")
    seed = (seed_raw or "").strip() or None
    if seed is not None:
        if not _SEQUENCE_ID_RE.match(seed):
            problems.append(f":seed: recipe name {seed!r} must be a kebab-case identifier")
        else:
            seed_builders, seed_problems = load_seed_frames(seed, seeds_root=seeds_root)
            problems.extend(seed_problems)
            builders.extend(seed_builders)

    body_builders, body_problems = parse_frame_lines(body, source="body")
    problems.extend(body_problems)
    builders.extend(body_builders)

    _enforce_result_contract(builders, problems)
    _enforce_captures_and_placeholders(builders, problems)

    if problems:
        raise SequenceParseError(sequence_id, problems)

    return ParsedSequence(
        sequence_id=sequence_id.strip(),
        verify=verify,
        seed=seed,
        frames=tuple(builder.build() for builder in builders),
    )


_SEQUENCE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")
