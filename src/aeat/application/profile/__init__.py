"""Application-layer profile validation for the CLI.

``aeat config profile status`` consumes the domain-layer
:class:`aeat.domain.profile.ProfileKey` registry rather than carrying
its own hardcoded list of mandatory keys. This module exposes the typed
validation result and factory the CLI calls; the CLI binding stays pure
transport.

``required`` keys and active conditional requirements block the
operator from advancing to declaration work, ``optional`` keys are
surfaced as informational presence or absence, and any key not in the
registry is flagged as ``unknown_keys`` so renderers can warn the
operator about typos.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict

from ...domain.profile import (
    PROFILE_KEYS,
    ProfileKey,
    ProfileKeyRequirement,
    optional_profile_keys,
)
from ._actions import (
    clear_profile_values,
    set_active_profile,
    set_profile_values,
)
from ._models import ProfileRecord
from ._repository import ProfileBucket, ProfileBucketRepository, profile_bucket_repository

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")
"""Shared :class:`pydantic.ConfigDict` for profile validation records."""


class ProfileValidationResult(BaseModel):
    """Typed result of :func:`validate_profile`.

    Attributes:
        valid: ``True`` when every required profile key has a
            non-empty value. The CLI's exit code is derived from this
            field — a thin transport, not a re-implementation.
        missing_required: Tuple of required key paths whose value is
            absent or blank. Empty when ``valid`` is ``True``.
        present_required: Tuple of required key paths whose value is
            present and non-blank.
        present_optional: Tuple of optional key paths whose value is
            present and non-blank.
        unknown_keys: Tuple of keys supplied by the operator but not
            in :data:`aeat.domain.profile.PROFILE_KEYS`. These do not
            block validation but the CLI surfaces them as warnings so
            the operator notices typos.
        present_keys: Count of schema-declared keys with non-blank values.
        total_keys: Count of schema-declared profile keys.
    """

    model_config = _STRICT_FROZEN

    valid: bool
    missing_required: tuple[str, ...] = ()
    present_required: tuple[str, ...] = ()
    present_optional: tuple[str, ...] = ()
    unknown_keys: tuple[str, ...] = ()
    present_keys: int
    total_keys: int


class ProfileValueRow(BaseModel):
    """One schema-backed profile value row for CLI/API display."""

    model_config = _STRICT_FROZEN

    key: str
    value: str | None
    is_set: bool
    requirement: ProfileKeyRequirement
    description: str


def _has_value(values: Mapping[str, str], key: str) -> bool:
    """Return whether ``values[key]`` is present and non-blank."""
    raw = values.get(key)
    return raw is not None and raw.strip() != ""


def _conditional_requirement_applies(values: Mapping[str, str], entry: ProfileKey) -> bool:
    """Return whether an optional key is required by another profile value."""
    if entry.required_when_key is None or entry.required_when_value is None:
        return False
    raw = values.get(entry.required_when_key)
    return raw is not None and raw.strip() == entry.required_when_value


def validate_profile(values: Mapping[str, str]) -> ProfileValidationResult:
    """Validate ``values`` against the domain :data:`PROFILE_KEYS` registry.

    The function is a pure projection of the registry over the
    operator's stored profile values. It does not mutate ``values``,
    does not touch the storage layer, and does not depend on any
    CLI state.

    Args:
        values: Mapping from profile key path (e.g. ``"tax.id"``) to
            the string value the operator stored. Empty / whitespace
            values are treated as absent.

    Returns:
        A :class:`ProfileValidationResult` with deterministic field
        ordering: each field's tuple is ordered by the registry's
        canonical key order so renders are reproducible across runs.
    """
    entries = PROFILE_KEYS
    required_keys = tuple(
        entry.key
        for entry in entries
        if entry.requirement is ProfileKeyRequirement.REQUIRED or _conditional_requirement_applies(values, entry)
    )
    optional_keys = tuple(entry.key for entry in optional_profile_keys())
    known_keys = set(required_keys) | set(optional_keys)

    missing_required: tuple[str, ...] = tuple(key for key in required_keys if not _has_value(values, key))
    present_required: tuple[str, ...] = tuple(key for key in required_keys if _has_value(values, key))
    present_optional: tuple[str, ...] = tuple(key for key in optional_keys if _has_value(values, key))
    unknown_keys: tuple[str, ...] = tuple(sorted(set(values) - known_keys))
    present_keys = sum(1 for entry in entries if _has_value(values, entry.key))

    return ProfileValidationResult(
        valid=not missing_required,
        missing_required=missing_required,
        present_required=present_required,
        present_optional=present_optional,
        unknown_keys=unknown_keys,
        present_keys=present_keys,
        total_keys=len(entries),
    )


def list_profile_key_records() -> tuple[ProfileKey, ...]:
    """Return the full :data:`PROFILE_KEYS` tuple in registry order.

    Provided so the CLI's ``aeat config profile list`` command can
    render the catalogue without importing from the domain underscore
    module directly. The tuple is :data:`PROFILE_KEYS` itself; the
    function exists so the CLI binding has a stable application-layer
    call site.
    """
    return PROFILE_KEYS


def list_profile_value_rows(
    values: Mapping[str, str],
    *,
    include_unset: bool = False,
) -> tuple[ProfileValueRow, ...]:
    """Return schema-backed profile rows for display surfaces.

    Args:
        values: Stored profile key/value mapping.
        include_unset: When ``True``, include every key declared in the
            profile schema registry with :data:`None` for missing or blank
            values. When ``False``, include only keys that are actually set.

    Returns:
        Rows ordered by the domain profile-key registry.
    """

    rows: list[ProfileValueRow] = []
    for entry in PROFILE_KEYS:
        value = values.get(entry.key)
        is_set = value is not None and value.strip() != ""
        if not is_set and not include_unset:
            continue
        rows.append(
            ProfileValueRow(
                key=entry.key,
                value=value.strip() if is_set and value is not None else None,
                is_set=is_set,
                requirement=entry.requirement,
                description=str(entry.description),
            )
        )
    return tuple(rows)


__all__ = [
    "ProfileBucket",
    "ProfileBucketRepository",
    "ProfileKey",
    "ProfileKeyRequirement",
    "ProfileRecord",
    "ProfileValidationResult",
    "ProfileValueRow",
    "clear_profile_values",
    "list_profile_key_records",
    "list_profile_value_rows",
    "profile_bucket_repository",
    "set_active_profile",
    "set_profile_values",
    "validate_profile",
]
