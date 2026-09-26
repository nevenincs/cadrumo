"""Declare, list and withdraw the average workforce of one calendar year.

``irpf.plantilla_media`` stores one indexed instance per calendar year.  The
year is the instance's identity: setting a declared year overwrites that
instance, setting a new year takes the next free index, and removing a year
clears its three leaves.  A cleared index stays occupied, so a later year never
inherits an index a reader may still associate with a withdrawn one, and no
other instance is renumbered.  Each operation reads the record once and writes
once through the shared profile-fact writer with that record as the
compare-and-swap expectation, so a concurrent write refuses instead of being
overwritten.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from ...domain.calculations.registry.authority_artifact import ProfileDecodeContext
from ...domain.user_profile.errors import UserProfileValidationError
from ...domain.user_profile.plantilla_media import (
    PLANTILLA_MEDIA_PATH,
    PlantillaMediaState,
    PlantillaMediaYear,
    plantilla_media_years,
)
from ...domain.user_profile.values import UserProfileFact, UserProfileRecord
from .fact_write import ProfileFactWriteDoor, apply_profile_fact_changes
from .profile_record_repository import ProfileRecordRepository
from .projections import in_window_order

_SUBFIELDS = ("year", "average_workforce", "state")


class PlantillaMediaWriteSurface(StrEnum):
    """Which operator surface asks for the write, recorded as its write door."""

    CLI = "cli"
    MANAGER = "manager"


def _effective_values(record: UserProfileRecord) -> dict[str, object]:
    """Return each plantilla-media path's effective typed value; a clear is ``None``."""
    effective: dict[str, object] = {}
    for fact in in_window_order(record.facts):
        if fact.path.startswith(f"{PLANTILLA_MEDIA_PATH}."):
            effective[fact.path] = fact.value
    return effective


def _instance_index(path: str) -> int | None:
    index, _, _ = path.removeprefix(f"{PLANTILLA_MEDIA_PATH}.").partition(".")
    return int(index) if index.isdigit() else None


def _index_of_year(effective: dict[str, object], year: int) -> int | None:
    for path, value in effective.items():
        if path.endswith(".year") and value is not None and str(value) == str(year):
            return _instance_index(path)
    return None


def _next_index(effective: dict[str, object]) -> int:
    """One above every index ever used, cleared ones included."""
    used = [index for path in effective if (index := _instance_index(path)) is not None]
    return max(used) + 1 if used else 0


def _load(profile_id: str, profile_decode_context: ProfileDecodeContext) -> UserProfileRecord:
    return ProfileRecordRepository.for_current_session(
        profile_id,
        profile_decode_context=profile_decode_context,
    ).load(profile_id)


def _publish(
    *,
    profile_id: str,
    changes: tuple[UserProfileFact, ...],
    record: UserProfileRecord,
    surface: PlantillaMediaWriteSurface,
    profile_decode_context: ProfileDecodeContext,
) -> UserProfileRecord:
    if surface is PlantillaMediaWriteSurface.CLI:
        return apply_profile_fact_changes(
            profile_id=profile_id,
            changes=changes,
            door=ProfileFactWriteDoor.CLI_PLANTILLA_MEDIA,
            expected_record=record,
            profile_decode_context=profile_decode_context,
        )
    return apply_profile_fact_changes(
        profile_id=profile_id,
        changes=changes,
        door=ProfileFactWriteDoor.MANAGER_PLANTILLA_MEDIA,
        expected_record=record,
        profile_decode_context=profile_decode_context,
    )


def plantilla_media_years_of(record: UserProfileRecord) -> tuple[PlantillaMediaYear, ...]:
    """Return a record's declared years through the canonical reader.

    Core types:
    :class:`~cadrumo.domain.user_profile.values.UserProfileRecord`.
    """
    return plantilla_media_years(
        {path: value for path, value in _effective_values(record).items() if value is not None},
    )


def list_plantilla_media_years(
    *,
    profile_id: str,
    profile_decode_context: ProfileDecodeContext,
) -> tuple[PlantillaMediaYear, ...]:
    """Return the active profile's declared average workforce, in year order."""
    return plantilla_media_years_of(_load(profile_id, profile_decode_context))


def set_plantilla_media_year(
    *,
    profile_id: str,
    year: int,
    average_workforce: Decimal,
    state: PlantillaMediaState,
    surface: PlantillaMediaWriteSurface,
    profile_decode_context: ProfileDecodeContext,
) -> tuple[PlantillaMediaYear, ...]:
    """Declare or replace one year's average workforce and return every declared year."""
    record = _load(profile_id, profile_decode_context)
    effective = _effective_values(record)
    index = _index_of_year(effective, year)
    if index is None:
        index = _next_index(effective)
    prefix = f"{PLANTILLA_MEDIA_PATH}.{index}"
    changes = (
        UserProfileFact(path=f"{prefix}.year", value=year),
        UserProfileFact(path=f"{prefix}.average_workforce", value=average_workforce),
        UserProfileFact(path=f"{prefix}.state", value=state.value),
    )
    published = _publish(
        profile_id=profile_id,
        changes=changes,
        record=record,
        surface=surface,
        profile_decode_context=profile_decode_context,
    )
    return plantilla_media_years_of(published)


def remove_plantilla_media_year(
    *,
    profile_id: str,
    year: int,
    surface: PlantillaMediaWriteSurface,
    profile_decode_context: ProfileDecodeContext,
) -> tuple[PlantillaMediaYear, ...]:
    """Withdraw one declared year and return the years that remain.

    Raises:
        UserProfileValidationError: When the year is not declared.
    """
    record = _load(profile_id, profile_decode_context)
    index = _index_of_year(_effective_values(record), year)
    if index is None:
        raise UserProfileValidationError(f"the average workforce of {year} is not declared")
    changes = tuple(
        UserProfileFact(path=f"{PLANTILLA_MEDIA_PATH}.{index}.{subfield}", value=None) for subfield in _SUBFIELDS
    )
    published = _publish(
        profile_id=profile_id,
        changes=changes,
        record=record,
        surface=surface,
        profile_decode_context=profile_decode_context,
    )
    return plantilla_media_years_of(published)


__all__ = [
    "PlantillaMediaWriteSurface",
    "list_plantilla_media_years",
    "plantilla_media_years_of",
    "remove_plantilla_media_year",
    "set_plantilla_media_year",
]
