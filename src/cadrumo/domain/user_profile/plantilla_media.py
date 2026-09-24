"""Average workforce per calendar year, stored as indexed profile instances.

Each instance lives at ``irpf.plantilla_media.{n}`` with three subfields:
``year`` (the calendar year), ``average_workforce`` (LIS art. 102.1 computes it
"con dos decimales", so more places are refused, never rounded) and ``state``
(``observed`` for a closed year, ``committed`` for a year still open). A year
without an instance is undeclared; it never reads as zero.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Final

from .errors import UserProfileValidationError

PLANTILLA_MEDIA_PATH: Final[str] = "irpf.plantilla_media"
"""The declared object field whose instances this module reads."""

YEAR_MINIMUM: Final[int] = 2000
YEAR_MAXIMUM: Final[int] = 2100
_MAXIMUM_DECIMAL_PLACES: Final[int] = 2
_SUBFIELDS: Final[tuple[str, ...]] = ("year", "average_workforce", "state")


class PlantillaMediaState(StrEnum):
    """Whether a year's average workforce is observed or still a commitment."""

    OBSERVED = "observed"
    COMMITTED = "committed"


class PlantillaMediaRefusalKind(StrEnum):
    """Which rule an instance value broke."""

    NUMERIC = "numeric"
    ENUM = "enum"
    INSTANCE = "instance"
    UNKNOWN_PATH = "unknown_path"


@dataclass(frozen=True, slots=True)
class PlantillaMediaRefusal:
    """One refused path and why."""

    path: str
    kind: PlantillaMediaRefusalKind
    message: str


@dataclass(frozen=True, slots=True)
class PlantillaMediaYear:
    """One validated instance."""

    year: int
    average_workforce: Decimal
    state: PlantillaMediaState


def _instance_path(path: str) -> tuple[int, str] | None:
    """Split ``irpf.plantilla_media.{n}.{subfield}``; ``None`` for any other shape."""
    prefix = f"{PLANTILLA_MEDIA_PATH}."
    if not path.startswith(prefix):
        return None
    index, _, subfield = path.removeprefix(prefix).partition(".")
    if not index.isdigit() or not subfield or "." in subfield:
        return None
    return int(index), subfield


def _year_refusal(path: str, value: object) -> PlantillaMediaRefusal | None:
    integral = isinstance(value, int) and not isinstance(value, bool)
    if isinstance(value, Decimal) and value.is_finite() and value == value.to_integral_value():
        integral = value.as_tuple().exponent == 0
    if not integral or not YEAR_MINIMUM <= int(str(value)) <= YEAR_MAXIMUM:
        return PlantillaMediaRefusal(
            path,
            PlantillaMediaRefusalKind.NUMERIC,
            f"{path} must be a whole calendar year from {YEAR_MINIMUM} to {YEAR_MAXIMUM}; got {value!r}",
        )
    return None


def _workforce_refusal(path: str, value: object) -> PlantillaMediaRefusal | None:
    if isinstance(value, bool) or not isinstance(value, (int, Decimal)):
        return PlantillaMediaRefusal(
            path,
            PlantillaMediaRefusalKind.NUMERIC,
            f"{path} must be a number of employees; got {value!r}",
        )
    amount = Decimal(value)
    exponent = amount.as_tuple().exponent
    if not amount.is_finite() or amount < 0 or not isinstance(exponent, int) or exponent < -_MAXIMUM_DECIMAL_PLACES:
        return PlantillaMediaRefusal(
            path,
            PlantillaMediaRefusalKind.NUMERIC,
            f"{path} must be zero or more with at most two decimal places, and is never rounded; got {value!r}",
        )
    return None


def _state_refusal(path: str, value: object) -> PlantillaMediaRefusal | None:
    if value not in {state.value for state in PlantillaMediaState}:
        return PlantillaMediaRefusal(
            path,
            PlantillaMediaRefusalKind.ENUM,
            f"{path} must be one of {', '.join(state.value for state in PlantillaMediaState)}; got {value!r}",
        )
    return None


def _value_refusal(path: str, subfield: str, value: object) -> PlantillaMediaRefusal | None:
    if subfield == "year":
        return _year_refusal(path, value)
    if subfield == "average_workforce":
        return _workforce_refusal(path, value)
    return _state_refusal(path, value)


def plantilla_media_refusals(values: Mapping[str, object]) -> tuple[PlantillaMediaRefusal, ...]:
    """Return every refused plantilla-media path in the effective fact values.

    ``values`` maps each path to its effective value; a cleared (``None``)
    value is absent. Every rule fails closed: a malformed path or subfield,
    an out-of-range or non-integral year, a workforce below zero or with
    more than two decimal places, an unknown state, an instance missing a
    subfield, and a year declared by more than one instance.
    """
    refusals: list[PlantillaMediaRefusal] = []
    instances: dict[int, dict[str, object]] = {}
    for path, value in sorted(values.items()):
        if value is None or not (path == PLANTILLA_MEDIA_PATH or path.startswith(f"{PLANTILLA_MEDIA_PATH}.")):
            continue
        located = _instance_path(path)
        if located is None or located[1] not in _SUBFIELDS:
            refusals.append(
                PlantillaMediaRefusal(
                    path,
                    PlantillaMediaRefusalKind.UNKNOWN_PATH,
                    f"{path} is not an instance subfield; use {PLANTILLA_MEDIA_PATH}.<n>.{{{','.join(_SUBFIELDS)}}}",
                ),
            )
            continue
        index, subfield = located
        instances.setdefault(index, {})[subfield] = value
        if (refusal := _value_refusal(path, subfield, value)) is not None:
            refusals.append(refusal)
    first_index_by_year: dict[object, int] = {}
    for index, fields in sorted(instances.items()):
        missing = [subfield for subfield in _SUBFIELDS if subfield not in fields]
        if missing:
            refusals.append(
                PlantillaMediaRefusal(
                    f"{PLANTILLA_MEDIA_PATH}.{index}",
                    PlantillaMediaRefusalKind.INSTANCE,
                    f"{PLANTILLA_MEDIA_PATH}.{index} is missing {', '.join(missing)}; every instance states "
                    f"{', '.join(_SUBFIELDS)}",
                ),
            )
        year = fields.get("year")
        if year is None:
            continue
        year_key = str(year)
        if year_key in first_index_by_year:
            refusals.append(
                PlantillaMediaRefusal(
                    f"{PLANTILLA_MEDIA_PATH}.{index}.year",
                    PlantillaMediaRefusalKind.INSTANCE,
                    f"{PLANTILLA_MEDIA_PATH}.{index}.year repeats year {year} already declared by "
                    f"{PLANTILLA_MEDIA_PATH}.{first_index_by_year[year_key]}; one instance per year",
                ),
            )
        else:
            first_index_by_year[year_key] = index
    return tuple(refusals)


def plantilla_media_years(values: Mapping[str, object]) -> tuple[PlantillaMediaYear, ...]:
    """Return the validated instances in year order.

    Raises:
        UserProfileValidationError: When any instance is refused; the message
            names each path.
    """
    refusals = plantilla_media_refusals(values)
    if refusals:
        raise UserProfileValidationError("; ".join(refusal.message for refusal in refusals))
    instances: dict[int, dict[str, object]] = {}
    for path, value in values.items():
        located = _instance_path(path)
        if located is not None and value is not None:
            instances.setdefault(located[0], {})[located[1]] = value
    years = [
        PlantillaMediaYear(
            year=int(str(fields["year"])),
            average_workforce=Decimal(str(fields["average_workforce"])),
            state=PlantillaMediaState(str(fields["state"])),
        )
        for fields in instances.values()
    ]
    return tuple(sorted(years, key=lambda item: item.year))


__all__ = [
    "PLANTILLA_MEDIA_PATH",
    "YEAR_MAXIMUM",
    "YEAR_MINIMUM",
    "PlantillaMediaRefusal",
    "PlantillaMediaRefusalKind",
    "PlantillaMediaState",
    "PlantillaMediaYear",
    "plantilla_media_refusals",
    "plantilla_media_years",
]
