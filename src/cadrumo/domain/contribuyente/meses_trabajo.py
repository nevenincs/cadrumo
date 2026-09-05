"""The one grammar for the months a mother met the Art. 81.1 requirements.

Art. 81.2 prorates its guardería increment by "el número de meses en que se
cumplan de forma simultánea los requisitos exigidos en el artículo 81.1 y 2",
which is an intersection of two month SETS. A count cannot express it: a mother
entitled May to August against nursery paid January to June overlaps in two
months, and the manual works exactly that case to ``1.000 ÷ 12 × 2 = 166,67``
while a count-based ``min(4, 6)`` yields four and 333,33 — an over-grant of the
deducción, which under-declares tax.

This module is why the months are now carried rather than counted. It shares the
month-specification grammar with :mod:`.guarderia_mensual` rather than
restating it, so the two descendant month surfaces cannot drift into accepting
different forms through different doors.

Accepted form::

    MM[;MM...]
    MM-MM              (an inclusive month range)

Ranges are INPUT only. :func:`serialise_meses_trabajo` always emits the
expanded, month-sorted ``MM`` form, so the stored fact has exactly one
representation and a save-then-reload round-trip is byte-stable regardless of
which form the operator typed.

Every malformed input REFUSES rather than dropping the offending month. A month
that vanished between typing and storage would silently change the proration
basis, and this set exists precisely to stop the basis being guessed.
"""

from __future__ import annotations

from collections.abc import Iterable

from ...core.errors.hierarchy import ProfileAnswerTypeError
from .guarderia_mensual import ENTRY_SEPARATOR, parse_month_spec

#: The accepted form, quoted verbatim in every refusal so the operator is told
#: what to write rather than only what was wrong.
MESES_TRABAJO_ACCEPTED_FORM = "MM or MM-MM, entries separated by ';' (for example 5-8 or 1;2;11;12)"


def parse_meses_trabajo(raw: str, *, field: str) -> tuple[int, ...]:
    """Parse the worked-months grammar into canonical, ascending months.

    Args:
        raw: The operator-supplied months. A blank string yields an empty tuple,
            which means "no qualifying months declared".
        field: The path or key naming this value in a refusal, so the operator
            is told which descendant and which door the bad value came through.

    Returns:
        The declared months, ascending, with every range expanded and no
        repeats.

    Raises:
        :class:`~cadrumo.core.errors.ProfileAnswerTypeError`: If any entry is
            malformed, names a month outside 1-12, inverts a range, or repeats
            a month.
    """
    if not raw.strip():
        return ()
    months: set[int] = set()
    for chunk in raw.split(ENTRY_SEPARATOR):
        entry = chunk.strip()
        if not entry:
            # An empty entry is a stray or doubled separator, refused rather
            # than skipped for the same reason the spend grammar refuses one:
            # the other reading is a month whose text was lost.
            raise ProfileAnswerTypeError(
                f"{field} contains an empty entry; write {MESES_TRABAJO_ACCEPTED_FORM}.",
            )
        for month in parse_month_spec(entry, entry=entry, field=field, accepted_form=MESES_TRABAJO_ACCEPTED_FORM):
            if month in months:
                raise ProfileAnswerTypeError(
                    f"{field} declares month {month} more than once. A month either qualified "
                    "or it did not, so a repeat is a transcription slip rather than a figure "
                    "to combine.",
                )
            months.add(month)
    return tuple(sorted(months))


def serialise_meses_trabajo(months: Iterable[int]) -> str:
    """Render months in the one canonical form, ascending.

    Ranges are never emitted, so the stored fact has exactly one representation
    for a given set and the fact index, the wizard's resume projection and the
    CLI payload round-trip byte-for-byte whichever form was typed.
    """
    return ENTRY_SEPARATOR.join(f"{month:02d}" for month in sorted(months))


__all__ = [
    "MESES_TRABAJO_ACCEPTED_FORM",
    "parse_meses_trabajo",
    "serialise_meses_trabajo",
]
