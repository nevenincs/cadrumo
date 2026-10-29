"""Render and edit revision governance fields in TOML manifests."""

from __future__ import annotations

import re
from datetime import date
from typing import Final

from cadrumo.domain.calculations.registry.schema import REVISION_GOVERNANCE_FIELDS

#: Emit order for the governance scalars, chosen so a manifest reads
#: authorship first and the review claim after it.
_EMIT_ORDER: Final[tuple[str, ...]] = (
    "engineered_by",
    "review_status",
    "reviewed_by",
    "reviewed_at",
    "reviewed_against",
)

GOVERNANCE_KEYS: Final[tuple[str, ...]] = (
    *(key for key in _EMIT_ORDER if key in REVISION_GOVERNANCE_FIELDS),
    *sorted(REVISION_GOVERNANCE_FIELDS - set(_EMIT_ORDER)),
)
"""The governance scalars this writer owns, in the order it emits them.

The SET is the shipped :data:`REVISION_GOVERNANCE_FIELDS`, never a second copy:
that set is derived from the field declarations themselves and is the sole input
to the loader's fragment refusal, so a fifth governance scalar added to the model
must reach this writer without anybody remembering to update it. Only the ORDER
is chosen here, and a field the emit order does not name is appended rather than
dropped — an unordered field is a cosmetic gap, an unwritable one is a
capability hole.
"""


class StampError(RuntimeError):
    """A governance stamp was refused, or could not be written safely."""


def render_toml_value(value: object) -> str:
    """Render one governance scalar in canonical TOML form.

    Dates are emitted bare, matching ``valid_from`` in every shipped manifest;
    strings are emitted with the escaping TOML requires so a reviewer name
    carrying a quote cannot break the table.
    """
    if isinstance(value, date):
        return value.isoformat()
    text = str(value)
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


_QUOTE = '"'
_TRIPLE_QUOTE = '"""'
_LINE_CONTINUATION = "\\\n"

#: Physical width the wrapped form aims for. Deliberately well under BOTH
#: reviewability caps in the tree (520 and 600) rather than tracking either: this
#: module lives in ``dev/`` and the gates in ``src/``, so importing one constant
#: is the wrong direction, and a value comfortably below every cap needs no
#: coordination.
_WRAPPED_NOTE_WIDTH = 90

#: Above this, a rendered assignment is wrapped. Short notes stay single-line, so
#: the common manifest is untouched and diffs stay small.
_WRAP_ASSIGNMENT_ABOVE = 200


def _render_governance_assignment(key: str, rendered_value: str) -> str:
    """Render one ``key = value`` line, wrapping a long note across lines.

    Reviewer notes are prose and routinely run past 2,000 characters. Emitted on
    one line they break the registry reviewability gates, and the sweep to wrap
    them by hand has had to be repeated after each stamping round -- the churn
    starts here, so it is stopped here.

    The wrapped form is a TOML multi-line basic string whose newlines are all
    eaten by line-ending backslashes, so the VALUE is byte-identical to the
    single-line form. Only a plain quoted string is wrapped, and only when it has
    spaces to break at; anything else is returned unchanged rather than risking a
    value the writer cannot reproduce.

    :func:`_without_governance_assignments` already walks an assignment's full
    span, so a multi-line value written here stays replaceable by a later stamp --
    the defect that once made two revisions permanently unstampable.
    """
    single = f"{key} = {rendered_value}"
    if len(single) <= _WRAP_ASSIGNMENT_ABOVE:
        return single
    if not (rendered_value.startswith(_QUOTE) and rendered_value.endswith(_QUOTE)):
        return single
    if rendered_value.startswith(_TRIPLE_QUOTE) or " " not in rendered_value:
        return single
    inner = rendered_value[1:-1]
    words = inner.split(" ")
    line = ""
    out: list[str] = []
    for word in words:
        if line and len(line) + 1 + len(word) > _WRAPPED_NOTE_WIDTH:
            out.append(line + " ")
            line = word
        else:
            line = f"{line} {word}" if line else word
    out.append(line)
    body = _LINE_CONTINUATION.join(out)
    return f"{key} = {_TRIPLE_QUOTE}{_LINE_CONTINUATION}{body}{_TRIPLE_QUOTE}"


def apply_governance(text: str, revision: str, rendered: dict[str, str]) -> str:
    """Rewrite the manifest's governance keys inside its single revision table.

    Line-oriented on purpose: a full TOML round-trip would reformat every
    hand-authored multi-line array in the file and bury the one-line stamp in an
    unreviewable diff. Only whole ``key = value`` lines for the four governance
    keys are touched; every other line is passed through byte for byte.

    "Byte for byte" includes the LINE TERMINATOR, which is why the joiner is
    read off the input rather than assumed. ``splitlines`` discards the
    terminator it split on, so re-joining with a fixed LF would silently rewrite
    every line of a CRLF manifest — the same whole-file rewrite, arriving from
    the other direction, that writing through ``write_text`` produced on an LF
    one.
    """
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines()
    header = f'[revisions."{revision}"]'
    start = _revision_table_start(lines, header)

    end = _revision_table_end(lines, start)
    body = _without_governance_assignments(lines[start + 1 : end])
    while body and not body[-1].strip():
        body.pop()
    body.extend(_render_governance_assignment(key, rendered[key]) for key in GOVERNANCE_KEYS if key in rendered)

    rebuilt = [*lines[:start], lines[start], *body, "", *lines[end:]]
    while rebuilt and not rebuilt[-1].strip():
        rebuilt.pop()
    return newline.join(rebuilt) + newline


def _revision_table_start(lines: list[str], header: str) -> int:
    """Find the exact manifest header line, refusing equivalent TOML spellings."""
    try:
        return next(index for index, line in enumerate(lines) if line.strip() == header)
    except StopIteration as exc:
        # REACHABLE, and it used to carry a pragma claiming otherwise on the
        # ground that ``_declared_governance`` proves the table exists. That
        # proves the table exists in PARSED TOML, never that any line matches
        # this one exact spelling. Measured: both ``[revisions.'<id>']`` and
        # ``[ revisions."<id>" ]`` parse to the same key, load through the real
        # registry loader, and miss here. The line editor needs a literal line to
        # edit, so the narrow match stays and the message names the requirement
        # instead of leaving the caller with a manifest the loader accepts and
        # this writer cannot address.
        raise StampError(
            f"{header} is not present as a whole line in the revision manifest. This writer edits the "
            f"manifest line by line so a hand-authored file stays reviewable, so it needs the table "
            f"header written in exactly that form; an equivalent TOML spelling such as a single-quoted "
            f"or space-padded header parses to the same table and loads cleanly, but cannot be located "
            f"here. Rewrite the header line in the canonical form and stamp again.",
        ) from exc


def _revision_table_end(lines: list[str], start: int) -> int:
    """Index of the first line after the revision table that ``start`` opens.

    A table ends at the next line that OPENS a new TOML table, but the scan
    cannot simply look for a leading ``[``: a governance value written as a
    multi-line basic string carries arbitrary prose, and a wrapped continuation
    line may legitimately BEGIN with a bracket. Modelo 840 is the worked case --
    its reviewed_by cites AEAT box numbers, and the wrap put ``[13]. VERIFIED
    -- ...`` at the start of a line, which the naive scan read as a table header
    and used to truncate the table thirty lines early. The rebuild then emitted
    the remaining prose outside any table and the manifest stopped parsing, so
    the revision was unstampable through this writer while its neighbours were
    fine.

    Skipping each governance assignment's full span keeps the scan on real
    structure. This is the same span walk :func:`_without_governance_assignments`
    performs; both must agree, or the body slice and the removal disagree about
    where the table ends.
    """
    index = start + 1
    while index < len(lines):
        if _is_governance_line(lines[index]):
            index += _governance_assignment_length(lines, index)
            continue
        if lines[index].startswith("["):
            return index
        index += 1
    return len(lines)


def _without_governance_assignments(body: list[str]) -> list[str]:
    """Return ``body`` with every governance assignment removed, bodies included.

    A governance value is a scalar, but a scalar written as a TOML multi-line
    basic string still occupies several PHYSICAL lines. Dropping only the line
    that carries the key orphans the remaining prose and the closing delimiter
    as bare TOML, and a reviewer note conventionally opening ``agent: ...`` then
    parses as a key with a colon where an equals belongs. That is not
    hypothetical: it refused every attempt to restamp a revision whose
    ``reviewed_by`` had been written in the triple-quoted form, while the
    single-line form beside it stamped cleanly.

    The refusal was the good outcome -- the caller restores the previous bytes
    rather than leaving a broken manifest -- but it made those revisions
    permanently unstampable through this writer.
    """
    kept: list[str] = []
    index = 0
    while index < len(body):
        if _is_governance_line(body[index]):
            index += _governance_assignment_length(body, index)
            continue
        kept.append(body[index])
        index += 1
    return kept


def _governance_assignment_length(body: list[str], index: int) -> int:
    """How many physical lines the governance assignment at ``index`` occupies.

    One, unless its value opens a multi-line basic string that the same line
    does not also close. An unterminated opener runs to the end of the table
    rather than past it, so a malformed manifest cannot make this consume the
    caller's unrelated lines.
    """
    _, _, after = body[index].partition("=")
    if after.count('"""') % 2 == 0:
        return 1
    for offset in range(index + 1, len(body)):
        if '"""' in body[offset]:
            return offset - index + 1
    return len(body) - index


def _is_governance_line(line: str) -> bool:
    """Whether a manifest line OPENS an assignment of one of the four governance scalars.

    Anchored at the start of the line so a governance key name appearing inside
    a continued array element is never mistaken for an assignment. The line is
    the START of the assignment; :func:`_governance_assignment_length` decides
    how far it runs.
    """
    stripped = line.lstrip()
    return any(re.match(rf"{key}\s*=", stripped) for key in GOVERNANCE_KEYS)
