"""Reviewed-censal field intents for every adoptable path, with per-path overrides."""

from __future__ import annotations

from collections.abc import Mapping

from ..censal_operation import CensalFieldIntent, CensalReviewedFieldIntent
from ..censo_sync import CENSAL_ADOPTABLE_PATHS


def censal_field_intents(
    overrides: Mapping[str, CensalFieldIntent] | None = None,
    *,
    default: CensalFieldIntent = CensalFieldIntent.PRESERVE,
    paths: tuple[str, ...] = CENSAL_ADOPTABLE_PATHS,
) -> tuple[CensalReviewedFieldIntent, ...]:
    """Build one intent per path, in the given order, deciding `default` unless overridden.

    Raises:
        KeyError: An override names a path outside `paths`, so a typo cannot pass silently.
    """
    chosen = dict(overrides or {})
    unknown = set(chosen) - set(paths)
    if unknown:
        raise KeyError(sorted(unknown))
    return tuple(CensalReviewedFieldIntent(path=path, intent=chosen.get(path, default)) for path in paths)
