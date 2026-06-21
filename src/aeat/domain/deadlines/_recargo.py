"""Loader and resolver for the Ley 58/2003 art-27 recargo bracket table.

The bracket schedule lives at
``registry/aeat/legal/ley-58-2003-recargo-bands.toml`` so the surcharge
percentages stay outside Python source and can be revised when the law
changes without touching engine code. Two functions are exposed:

- :func:`load_recargo_bands` reads and validates the TOML into a tuple
  of :class:`aeat.domain.deadlines.RecargoBand` records.
- :func:`completed_months_late` counts the COMPLETED months between the
  filing deadline and the presentation date (Art. 27.2 LGT counts only
  whole months; a fractional month does not count).
- :func:`resolve_recargo_band` selects the band whose
  ``[min_completed_months, max_completed_months]`` window contains a given
  completed-months value.

The deadline engine calls :func:`build_recovery_for_overdue` to
populate the :class:`Recovery` field on every OVERDUE
:class:`ModeloDeadline`.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from pydantic import ValidationError

from ...core import Period, read_toml
from ...core.decimal import coerce_decimal
from ...core.resources import bundled_path
from ._errors import DeadlineValidationError
from ._models import RecargoBand, Recovery

_DEFAULT_BRACKET_PATH = bundled_path("registry", "aeat", "legal", "ley-58-2003-recargo-bands.toml")


def load_recargo_bands(path: Path | None = None) -> tuple[RecargoBand, ...]:
    """Load and validate the recargo bracket TOML.

    Args:
        path: Override path; defaults to the canonical registry location.

    Returns:
        Tuple of :class:`RecargoBand` records ordered by
        ``min_completed_months`` ascending.

    Raises:
        DeadlineValidationError: When the TOML cannot be read, is
            malformed, is missing rows, or carries an invalid band.
    """
    target = path if path is not None else _DEFAULT_BRACKET_PATH
    resolved = target.resolve()
    try:
        stat = resolved.stat()
    except OSError as exc:
        raise DeadlineValidationError(f"{resolved}: cannot stat recargo bracket registry: {exc}") from exc
    return _load_recargo_bands_cached(str(resolved), stat.st_size, stat.st_mtime_ns)


@lru_cache(maxsize=16)
def _required_decimal(value: object) -> Decimal:
    coerced = coerce_decimal(value)
    if coerced is None:
        raise ValueError(f"could not parse decimal: {value!r}")
    return coerced


def _load_recargo_bands_cached(path: str, byte_count: int, modified_ns: int) -> tuple[RecargoBand, ...]:
    del byte_count, modified_ns
    target = Path(path)
    raw = read_toml(target, error_factory=DeadlineValidationError)
    raw_band = raw.get("band")
    if not raw_band:
        raise DeadlineValidationError(f"recargo bracket TOML at {target} declares no bands")
    assert isinstance(raw_band, list)
    try:
        built: list[RecargoBand] = []
        for raw_row in raw_band:
            assert isinstance(raw_row, dict)
            row: dict[str, object] = {str(k): v for k, v in raw_row.items()}
            row_min = row.get("min_completed_months")
            row_max = row.get("max_completed_months")
            assert isinstance(row_min, int)
            built.append(
                RecargoBand(
                    id=str(row.get("id")),
                    min_completed_months=row_min,
                    max_completed_months=int(row_max) if isinstance(row_max, int) else None,
                    surcharge_pct=_required_decimal(row.get("surcharge_pct")),
                    interest_applies=bool(row.get("interest_applies", False)),
                    legal_ref=str(row.get("legal_ref")),
                ),
            )
        bands = tuple(built)
    except (ArithmeticError, KeyError, TypeError, ValueError, ValidationError) as exc:
        raise DeadlineValidationError(f"{target}: invalid recargo band row: {exc}") from exc
    return tuple(sorted(bands, key=lambda band: band.min_completed_months))


def completed_months_late(closes_on: date, reference_today: date) -> int:
    """Return the number of COMPLETED months between deadline and presentation.

    Art. 27.2 LGT escalates the recargo "por cada mes completo de retraso" —
    by each *completed* month of delay. A month is completed only when the
    presentation date has reached the same day-of-month as the deadline in a
    later month; a fractional (incomplete) month does not count.

    Args:
        closes_on: The filing window's close date (deadline).
        reference_today: The date the self-assessment is presented.

    Returns:
        Completed months of delay, ``>= 0`` (``0`` when filed late but within
        the first incomplete month).
    """
    if reference_today <= closes_on:
        return 0
    months = (reference_today.year - closes_on.year) * 12 + (reference_today.month - closes_on.month)
    if reference_today.day < closes_on.day:
        months -= 1
    return max(0, months)


def resolve_recargo_band(completed_months: int, bands: Sequence[RecargoBand]) -> RecargoBand:
    """Return the band whose window contains ``completed_months``.

    Args:
        completed_months: Completed months past the filing window's close
            date, as returned by :func:`completed_months_late`. Must be
            ``>= 0``.
        bands: Tuple of bands as returned by :func:`load_recargo_bands`.

    Returns:
        The matching :class:`RecargoBand`.

    Raises:
        DeadlineValidationError: When ``completed_months < 0`` or no band's
            window covers the value (which would indicate a TOML gap).
    """
    if completed_months < 0:
        raise DeadlineValidationError(
            f"resolve_recargo_band: completed_months must be >= 0; got {completed_months}",
        )
    for band in bands:
        upper = band.max_completed_months if band.max_completed_months is not None else completed_months
        if band.min_completed_months <= completed_months <= upper:
            return band
    raise DeadlineValidationError(f"resolve_recargo_band: no band covers completed_months={completed_months}")


def build_recovery_for_overdue(
    *,
    closes_on: date,
    reference_today: date,
    modelo: str,
    period: Period,
    bands: Sequence[RecargoBand] | None = None,
) -> Recovery:
    """Resolve the :class:`Recovery` payload for an OVERDUE obligation.

    The recargo percentage is computed precisely per Art. 27.2 LGT from the
    number of COMPLETED months between ``closes_on`` and ``reference_today``
    (1% + 1% per completed month; 15% + intereses de demora once 12 completed
    months have elapsed), not from a day-bracket approximation.

    Args:
        closes_on: The filing window's close date (deadline).
        reference_today: The date the self-assessment is presented.
        modelo: Modelo identifier the operator must still file.
        period: Typed filing period for the overdue obligation.
        bands: Optional pre-loaded band table; when ``None``, the canonical
            TOML is loaded once.

    Returns:
        A :class:`Recovery` carrying the resolved band, the legal
        reference, and a runnable next-action command.
    """
    months = completed_months_late(closes_on, reference_today)
    resolved = resolve_recargo_band(
        months,
        bands if bands is not None else load_recargo_bands(),
    )
    next_command = "aeat app modelo work --help"
    return Recovery(
        still_filable=True,
        recargo_band=resolved,
        legal_ref=resolved.legal_ref,
        next_command=next_command,
    )


__all__ = [
    "build_recovery_for_overdue",
    "completed_months_late",
    "load_recargo_bands",
    "resolve_recargo_band",
]
