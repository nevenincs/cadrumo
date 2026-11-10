"""Count the work-form fields that still need filer action."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Final

from .work_form_field_vocabulary import (
    ModeloFormOrigin,
    ModeloFormStanding,
)
from .work_form_models import (
    ModeloFormCounts,
    ModeloFormField,
)

_TO_DO_TALLIES: Final[tuple[str, ...]] = ("needs_input", "default_to_confirm", "needs_you")

"""The counts of what the filer still has to enter or confirm."""


def count_work_form_fields(fields: Iterable[ModeloFormField], *, filed: bool) -> ModeloFormCounts:
    """Tally fields by origin and by what they ask of the filer; a filed declaration has nothing left to do."""
    tallies = {
        "total": 0,
        "needs_input": 0,
        "entered": 0,
        "imported": 0,
        "calculated": 0,
        "overridden": 0,
        "default_to_confirm": 0,
        "not_applicable": 0,
        "blocked": 0,
        "needs_you": 0,
        "could_not_calculate": 0,
    }
    by_origin = {
        ModeloFormOrigin.NEEDS_INPUT: "needs_input",
        ModeloFormOrigin.ENTERED: "entered",
        ModeloFormOrigin.IMPORTED: "imported",
        ModeloFormOrigin.CALCULATED: "calculated",
        ModeloFormOrigin.OVERRIDES_SOURCE: "overridden",
        ModeloFormOrigin.DEFAULT_TO_CONFIRM: "default_to_confirm",
        ModeloFormOrigin.NOT_APPLICABLE: "not_applicable",
    }
    for field in fields:
        tallies["total"] += 1
        bucket = by_origin.get(field.origin)
        if bucket is not None:
            tallies[bucket] += 1
        if field.blockers:
            tallies["blocked"] += 1
        if field.standing is ModeloFormStanding.NEEDS_YOU:
            tallies["needs_you"] += 1
        if field.origin is ModeloFormOrigin.CALCULATION_FAILED:
            tallies["could_not_calculate"] += 1
    if filed:
        tallies.update(dict.fromkeys(_TO_DO_TALLIES, 0))
    return ModeloFormCounts(**tallies)
