"""Count the work-form fields that still need filer action."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Final

from .work_form_models import ModeloFormCounts, ModeloFormField, ModeloFormOrigin

_TO_DO_TALLIES: Final[tuple[str, ...]] = ("needs_input", "default_to_confirm")

"""The counts of what the filer still has to enter or confirm."""


def count_work_form_fields(fields: Iterable[ModeloFormField], *, filed: bool) -> ModeloFormCounts:
    """Tally fields by origin; a declaration recorded as filed has nothing left to enter or confirm."""
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
    if filed:
        tallies.update(dict.fromkeys(_TO_DO_TALLIES, 0))
    return ModeloFormCounts(**tallies)
