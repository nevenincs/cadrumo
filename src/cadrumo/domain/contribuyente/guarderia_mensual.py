"""The one grammar for a descendant's month-level guardería spend.

Art. 81.2 LIRPF draws two month boundaries an annual total cannot express, so
:class:`~domain.contribuyente.GuarderiaMonthSpend` entries are month-granular.
That makes the map a structured value on surfaces that carry only flat strings:
the ``--descendiente`` flag, the ``renta_family.descendiente.{n}.*`` fact index,
and one wizard page. This module is the single grammar all three share.

One grammar rather than three because the alternative was measured on this same
descendant surface and shipped a real defect: a translated key token parsed
without error and was silently dropped, leaving a claiming default in place. A
per-door grammar drifts the same way -- the CLI would accept a shape the wizard
refuses, and the operator would meet different rules depending on which door
they came through.

Accepted form::

    MM:AMOUNT[;MM:AMOUNT...]
    MM-MM:AMOUNT              (an inclusive month range, all at that amount)

``;`` separates entries because the ``--descendiente`` flag already splits its
own keys on ``,``; a comma here would end the flag's value mid-map. ``:`` binds
a month to its amount and cannot occur inside an integer euro figure, so the
split is unambiguous.

The range form is not sugar for its own sake. The dominant real shape is a
constant monthly fee across an enrolment span, so ``9-12:210`` is what a
taxpayer reads off their centre's certificate; spelling four identical entries
is where a transcription slip enters.

Ranges are INPUT only. :func:`serialise_guarderia_mensual` always emits the
expanded, month-sorted ``MM:AMOUNT`` form, so the stored fact has exactly one
representation and a save-then-reload round-trip is byte-stable regardless of
which form the operator typed.

Every malformed input REFUSES rather than dropping the offending entry. Dropping
would under-grant, which is the safe direction on amount, but silently -- and
this map's whole purpose is to carry months a taxpayer can evidence from a
certificate they already hold, so a month that vanished between typing and
storage is precisely what nobody would catch.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from ...core.errors import ProfileAnswerTypeError
from .family_types import GuarderiaMonthSpend

#: Separator between entries. Not ``,``: the ``--descendiente`` flag owns that.
ENTRY_SEPARATOR = ";"

#: Separator binding a month specification to its amount.
_AMOUNT_SEPARATOR = ":"

#: Separator between the two ends of an inclusive month range.
_RANGE_SEPARATOR = "-"

_MIN_MONTH = 1
_MAX_MONTH = 12

#: The accepted form, quoted verbatim in every refusal so the operator is told
#: what to write rather than only what was wrong.
GUARDERIA_MENSUAL_ACCEPTED_FORM = "MM:AMOUNT or MM-MM:AMOUNT, entries separated by ';' (for example 9-12:210;1:180)"


def parse_guarderia_mensual(raw: str, *, field: str) -> tuple[GuarderiaMonthSpend, ...]:
    """Parse the monthly-spend grammar into canonical, month-sorted entries.

    Args:
        raw: The operator-supplied map. A blank string yields an empty tuple,
            which means "no monthly breakdown declared" -- distinct from a
            declared map that happens to sum to zero.
        field: The path or key naming this value in a refusal, so the operator
            is told which descendant and which door the bad value came through.

    Returns:
        The declared months as canonical entries, ascending by month, with every
        range expanded.

    Raises:
        :class:`~cadrumo.core.errors.ProfileAnswerTypeError`: If any entry is
            malformed, names a month outside 1-12, inverts a range, repeats a
            month, or carries an amount that is not a non-negative integer.
    """
    if not raw.strip():
        return ()
    by_month: dict[int, int] = {}
    for chunk in raw.split(ENTRY_SEPARATOR):
        entry = chunk.strip()
        if not entry:
            # An empty entry is a stray or doubled separator. It is refused
            # rather than skipped because the two are indistinguishable from
            # here, and the other reading -- a month whose text was lost -- is
            # the one that silently drops evidence.
            raise ProfileAnswerTypeError(
                f"{field} contains an empty entry; write {GUARDERIA_MENSUAL_ACCEPTED_FORM}.",
            )
        months, amount = _parse_entry(entry, field=field)
        for month in months:
            if month in by_month:
                raise ProfileAnswerTypeError(
                    f"{field} declares month {month} more than once. Give one entry per month "
                    "carrying that month's total; two entries for one month are either a "
                    "duplicate or a partial, and adding them would invent a figure you did "
                    "not state.",
                )
            by_month[month] = amount
    return tuple(GuarderiaMonthSpend(month=month, amount_euros=by_month[month]) for month in sorted(by_month))


def _parse_entry(entry: str, *, field: str) -> tuple[Sequence[int], int]:
    """Split one ``MM:AMOUNT`` or ``MM-MM:AMOUNT`` entry into its months and amount."""
    month_spec, separator, amount_raw = entry.partition(_AMOUNT_SEPARATOR)
    if not separator:
        raise ProfileAnswerTypeError(
            f"{field} entry {entry!r} has no ':' binding a month to an amount; "
            f"write {GUARDERIA_MENSUAL_ACCEPTED_FORM}.",
        )
    return parse_month_spec(month_spec.strip(), entry=entry, field=field), _parse_amount(
        amount_raw.strip(),
        entry=entry,
        field=field,
    )


def parse_month_spec(
    spec: str, *, entry: str, field: str, accepted_form: str = GUARDERIA_MENSUAL_ACCEPTED_FORM
) -> Sequence[int]:
    """Read a bare month or an inclusive range into the months it names.

    Shared with :mod:`._meses_trabajo`, which carries the Art. 81.1 month set
    through the same doors. *accepted_form* is the caller's own grammar, quoted
    in refusals so an operator is told the form of the surface they used rather
    than this module's.
    """
    start_raw, separator, end_raw = spec.partition(_RANGE_SEPARATOR)
    start = _parse_month(start_raw.strip(), entry=entry, field=field, accepted_form=accepted_form)
    if not separator:
        return (start,)
    end = _parse_month(end_raw.strip(), entry=entry, field=field, accepted_form=accepted_form)
    if end < start:
        # Refused rather than reordered. A reversed range is as likely to be a
        # mistyped bound as an inverted one, and silently reading '12-9' as
        # September through December would assert four months the operator may
        # never have paid for -- the one direction this map must not guess in.
        raise ProfileAnswerTypeError(
            f"{field} entry {entry!r} runs from month {start} back to month {end}. "
            "Write the range in ascending order, or give the months separately.",
        )
    return range(start, end + 1)


def is_plain_whole_number(text: str) -> bool:
    """Whether *text* is exactly ASCII digits, so ``int`` cannot fail on it.

    ``str.isdigit`` is NOT that test and the difference is a live defect rather
    than a nicety. It answers True for superscripts and for non-ASCII digit
    scripts, and ``int`` accepts only the second group -- so ``"9:²"``, a shape
    an operator reaches by pasting a footnote marker out of a formatted
    certificate, passed an ``isdigit`` gate and then raised a bare
    :class:`ValueError` from ``int``. That error is untranslated, names neither
    the field nor the accepted form, and escapes the wizard's answer validator
    entirely, because the validator catches only the typed refusal this module
    raises. The operator met a crash where a verdict was due.

    ``isdigit`` also lets ``int``'s own tolerances through unexamined: it would
    be the wrong gate for ``"1_0"``, which ``int`` reads as ten.

    Kept as one named predicate rather than repeated inline, because the same
    mistake was made independently at three sites in this feature and the
    reasoning is what stops it being made a fourth time.
    """
    return text.isascii() and text.isdecimal()


def _parse_month(raw: str, *, entry: str, field: str, accepted_form: str = GUARDERIA_MENSUAL_ACCEPTED_FORM) -> int:
    if not is_plain_whole_number(raw):
        raise ProfileAnswerTypeError(
            f"{field} entry {entry!r} names month {raw!r}, which is not a number; write {accepted_form}.",
        )
    month = int(raw)
    if not (_MIN_MONTH <= month <= _MAX_MONTH):
        raise ProfileAnswerTypeError(
            f"{field} entry {entry!r} names month {month}, outside {_MIN_MONTH}-{_MAX_MONTH}.",
        )
    return month


def _parse_amount(raw: str, *, entry: str, field: str) -> int:
    # A shape test rather than a try/int: it refuses the sign, the decimal point
    # and the exponent in one place. Euros here are whole by the same decision
    # the annual field already made, and a signed or fractional figure is a
    # different shape rather than a rounding question.
    if not is_plain_whole_number(raw):
        raise ProfileAnswerTypeError(
            f"{field} entry {entry!r} carries amount {raw!r}, which is not a whole number of euros "
            f"of zero or more; write {GUARDERIA_MENSUAL_ACCEPTED_FORM}.",
        )
    return int(raw)


def serialise_guarderia_mensual(entries: Iterable[GuarderiaMonthSpend]) -> str:
    """Render entries in the one canonical form, ascending by month.

    Ranges are never emitted. The stored fact therefore has exactly one
    representation for a given map, which is what lets the fact index, the
    wizard's resume projection, and the CLI payload round-trip byte-for-byte
    whichever form the operator originally typed.
    """
    return ENTRY_SEPARATOR.join(
        f"{entry.month:02d}{_AMOUNT_SEPARATOR}{entry.amount_euros}"
        for entry in sorted(entries, key=lambda entry: entry.month)
    )


__all__ = [
    "ENTRY_SEPARATOR",
    "GUARDERIA_MENSUAL_ACCEPTED_FORM",
    "is_plain_whole_number",
    "parse_guarderia_mensual",
    "parse_month_spec",
    "serialise_guarderia_mensual",
]
