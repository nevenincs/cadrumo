"""Loader and resolver for the Ley 58/2003 art-27 recargo bracket table.

The bracket schedule lives at
``registry/aeat/legal/ley-58-2003-recargo-bands.toml`` so the surcharge
percentages stay outside Python source and can be revised when the law
changes without touching engine code. Two functions are exposed:

- :func:`load_recargo_bands` reads and validates the TOML into a tuple
  of :class:`aeat.domain.deadlines.RecargoBand` records.
- :func:`resolve_recargo_band` selects the band whose
  ``[min_days_late, max_days_late]`` window contains a given
  ``days_late`` value.

The deadline engine calls :func:`build_recovery_for_overdue` to
populate the :class:`Recovery` field on every OVERDUE
:class:`ModeloDeadline`.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from pydantic import ValidationError

from ...core._toml import read_toml
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
        ``min_days_late`` ascending.

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
            row_min = row.get("min_days_late")
            row_max = row.get("max_days_late")
            assert isinstance(row_min, int)
            built.append(
                RecargoBand(
                    id=str(row.get("id")),
                    min_days_late=row_min,
                    max_days_late=int(row_max) if isinstance(row_max, int) else None,
                    surcharge_pct=_required_decimal(row.get("surcharge_pct")),
                    interest_applies=bool(row.get("interest_applies", False)),
                    legal_ref=str(row.get("legal_ref")),
                )
            )
        bands = tuple(built)
    except (ArithmeticError, KeyError, TypeError, ValueError, ValidationError) as exc:
        raise DeadlineValidationError(f"{target}: invalid recargo bracket row: {exc}") from exc
    return tuple(sorted(bands, key=lambda band: band.min_days_late))


def resolve_recargo_band(days_late: int, bands: Sequence[RecargoBand]) -> RecargoBand:
    """Return the band whose window contains ``days_late``.

    Args:
        days_late: Days past the filing window's close date. Must be
            ``>= 1``; the caller filters non-overdue obligations out
            before invoking this resolver.
        bands: Tuple of bands as returned by :func:`load_recargo_bands`.

    Returns:
        The matching :class:`RecargoBand`.

    Raises:
        DeadlineValidationError: When ``days_late < 1`` or no band's window
            covers the value (which would indicate a TOML gap).
    """
    if days_late < 1:
        raise DeadlineValidationError(f"resolve_recargo_band: days_late must be >= 1; got {days_late}")
    for band in bands:
        upper = band.max_days_late if band.max_days_late is not None else days_late
        if band.min_days_late <= days_late <= upper:
            return band
    raise DeadlineValidationError(f"resolve_recargo_band: no band covers days_late={days_late}")


def build_recovery_for_overdue(
    *,
    days_late: int,
    modelo: str,
    period: str,
    bands: Sequence[RecargoBand] | None = None,
) -> Recovery:
    """Resolve the :class:`Recovery` payload for an OVERDUE obligation.

    Args:
        days_late: Days past the filing window's close date.
        modelo: Modelo identifier the operator must still file.
        period: Canonical period string (e.g. ``"2026Q1"``).
        bands: Optional pre-loaded bracket table; when ``None``, the
            canonical TOML is loaded once.

    Returns:
        A :class:`Recovery` carrying the resolved band, the legal
        reference, and a runnable next-action command.
    """
    resolved = resolve_recargo_band(
        days_late,
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
    "load_recargo_bands",
    "resolve_recargo_band",
]
