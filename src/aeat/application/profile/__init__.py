"""Application-layer profile validation for the CLI.

``aeat setup profile validate`` consumes the domain-layer
:class:`aeat.domain.profile.ProfileKey` registry rather than carrying
its own hardcoded list of mandatory keys. This module exposes the typed
validation result and factory the CLI calls; the CLI binding stays pure
transport.

``required`` keys block the operator from advancing to declaration
work, ``optional`` keys are surfaced as informational presence or
absence, and any key not in the registry is flagged as ``unknown_keys``
so renderers can warn the operator about typos.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict

from ...domain.profile import (
    PROFILE_KEYS,
    ProfileKey,
    ProfileKeyRequirement,
    optional_profile_keys,
    required_profile_keys,
)

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
    """

    model_config = _STRICT_FROZEN

    valid: bool
    missing_required: tuple[str, ...] = ()
    present_required: tuple[str, ...] = ()
    present_optional: tuple[str, ...] = ()
    unknown_keys: tuple[str, ...] = ()


def _has_value(values: Mapping[str, str], key: str) -> bool:
    """Return whether ``values[key]`` is present and non-blank."""
    raw = values.get(key)
    return raw is not None and raw.strip() != ""


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
    required_keys = tuple(entry.key for entry in required_profile_keys())
    optional_keys = tuple(entry.key for entry in optional_profile_keys())
    known_keys = set(required_keys) | set(optional_keys)

    missing_required: tuple[str, ...] = tuple(key for key in required_keys if not _has_value(values, key))
    present_required: tuple[str, ...] = tuple(key for key in required_keys if _has_value(values, key))
    present_optional: tuple[str, ...] = tuple(key for key in optional_keys if _has_value(values, key))
    unknown_keys: tuple[str, ...] = tuple(sorted(set(values) - known_keys))

    return ProfileValidationResult(
        valid=not missing_required,
        missing_required=missing_required,
        present_required=present_required,
        present_optional=present_optional,
        unknown_keys=unknown_keys,
    )


def list_profile_key_records() -> tuple[ProfileKey, ...]:
    """Return the full :data:`PROFILE_KEYS` tuple in registry order.

    Provided so the CLI's ``aeat setup profile list-keys`` command can
    render the catalogue without importing from the domain underscore
    module directly. The tuple is :data:`PROFILE_KEYS` itself; the
    function exists so the CLI binding has a stable application-layer
    call site.
    """
    return PROFILE_KEYS


__all__ = [
    "ProfileKey",
    "ProfileKeyRequirement",
    "ProfileValidationResult",
    "list_profile_key_records",
    "validate_profile",
]
