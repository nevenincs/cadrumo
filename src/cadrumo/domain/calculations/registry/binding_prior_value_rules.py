"""The two rules an earlier-filing carry may declare about the figures that stand for its earlier return.

A carry read from an earlier filing is unknown, never zero, while no earlier
return supplies it. Two shortcuts the application takes for an ordinary carry
would turn that unknown into a figure, and some carries must refuse both:

``zero_needs_attestation``
    An operator-typed zero over a carry is ordinarily taken as the filer not
    claiming the carry, so verification asks for no earlier return behind it.
    That holds only where a positive figure would benefit the taxpayer. Where
    a zero is the figure that benefits the taxpayer, as for the net turnover
    of the preceding period that selects a reduced rate (Ley 27/2014 art.
    29.1), a typed zero proves nothing: only an attested zero, or the earlier
    return, verifies clean.

``before_activity_unresolved``
    An earlier period that ended before the taxpayer's activity began
    ordinarily owes no return, so the carry reads zero and verification asks
    for none. Where the law gives such a period another figure, as the
    annualised net turnover of the first period of activity (Ley 27/2014 art.
    101.2), that zero would be a default: the carry stays unresolved and the
    filer states the figure, a genuine zero included.

``held_source_set_aside_when_marked``
    A held earlier return ordinarily supplies the carry. Where the current
    return marks a box under which the law measures the figure otherwise, the
    held return's figure is not the one the current period needs: an entity of
    a grupo mercantil measures the net turnover of the preceding period over the
    whole group (Ley 27/2014 art. 101.3), while its own return shows only its
    own. While any listed box is marked, the held return is set aside: the carry
    stays unresolved, the filer may state it although the return is held, and
    only that statement verifies clean.

Each flag is declared once on the binding row, only as ``true``; the marks are
a list of the current return's boxes. All are declared only on a decimal carry
read from an earlier filing::

    zero_needs_attestation = true
    before_activity_unresolved = true
    held_source_set_aside_when_marked = ["00039"]

The resolver, the edit and the clean-state evaluation read the declaration;
none names a modelo or a box.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Annotated, Final, Literal

from pydantic import AfterValidator, Field

from ....core.aggregation import BindingSourceKind
from ....core.casilla_id import CasillaId
from .ids import BindingId

if TYPE_CHECKING:
    from .schema import ModeloRevision

PriorValueRuleFlag = Literal[True]
"""A declared rule: present only as ``true``, absent otherwise."""

PRIOR_VALUE_RULE_SOURCES: Final = frozenset({BindingSourceKind.PREVIOUS_FILING})
"""The sources whose carries may declare either rule: a direct read of an earlier filing."""


def _distinct_marks(marks: tuple[CasillaId, ...]) -> tuple[CasillaId, ...]:
    if len(set(marks)) != len(marks):
        raise ValueError("held_source_set_aside_when_marked lists a box twice")
    return marks


HeldSourceSetAsideMarks = Annotated[tuple[CasillaId, ...], Field(min_length=1), AfterValidator(_distinct_marks)]
"""The current return's boxes any of which, marked, sets a held earlier return aside."""


def is_marked(value: object) -> bool:
    """Whether a box value marks the box: present and not zero."""
    if value is None:
        return False
    try:
        return Decimal(str(value)) != 0
    except InvalidOperation:
        return bool(str(value).strip())


def set_aside_binding_ids(revision: ModeloRevision, current_values: Mapping[CasillaId, object]) -> frozenset[BindingId]:
    """The carries whose held earlier return the current return's marked boxes set aside."""
    return frozenset(
        binding.id
        for binding in revision.bindings
        if binding.held_source_set_aside_when_marked is not None
        and any(is_marked(current_values.get(mark)) for mark in binding.held_source_set_aside_when_marked)
    )


def set_aside_declaring_binding_ids(revision: ModeloRevision) -> frozenset[BindingId]:
    """The carries that declare boxes under which their held earlier return is set aside."""
    return frozenset(
        binding.id for binding in revision.bindings if binding.held_source_set_aside_when_marked is not None
    )


__all__ = [
    "PRIOR_VALUE_RULE_SOURCES",
    "HeldSourceSetAsideMarks",
    "PriorValueRuleFlag",
    "is_marked",
    "set_aside_binding_ids",
    "set_aside_declaring_binding_ids",
]
