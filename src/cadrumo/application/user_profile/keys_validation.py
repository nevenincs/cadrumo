"""Profile-key-catalogue validation projection used by the CLI status surface.

The wizard catalogue (``application/wizard/catalogue.py``) declares each
``WizardQuestion.profile_key`` as a canonical schema-TOML path (for example,
``identity.tax_id`` and ``preferences.output_language``). The application
profile-key catalogue compiles those declarations into :class:`ProfileKey`
records. The helpers in this module project a flat operator-supplied
``Mapping[str, str]`` over that catalogue and report which required keys are
missing or set so the CLI status surface can render a deterministic readiness
summary.

These helpers are intentionally projection-only: they do not read or write
secure storage, do not touch :class:`WorkflowState`, and do not depend on any
CLI state. The flat-dict input is produced by
:func:`application.user_profile.projections.record_to_values` or by the wizard runner's
canonical projection.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING

from pydantic import BaseModel

from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.requirement import Requirement
from .completeness import (
    IVA_REGIME_PATH,
    conditional_profile_required_paths,
    iva_regime_required,
    profile_value_is_present,
)
from .profile_key import ProfileKey
from .profile_keys import optional_profile_keys, profile_keys

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation


class ProfileValidationResult(BaseModel):
    """Typed result of :func:`validate_profile_values`."""

    model_config = _STRICT_FROZEN

    valid: bool
    missing_required: tuple[str, ...] = ()
    present_required: tuple[str, ...] = ()
    present_optional: tuple[str, ...] = ()
    unknown_keys: tuple[str, ...] = ()
    present_keys: int
    total_keys: int


def _has_value(values: Mapping[str, str], key: str) -> bool:
    return profile_value_is_present(values.get(key))


def _conditional_requirement_applies(values: Mapping[str, str], entry: ProfileKey) -> bool:
    if entry.required_when_key is None or entry.required_when_value is None:
        return False
    raw = values.get(entry.required_when_key)
    return raw is not None and raw.strip() == entry.required_when_value


def validate_profile_values(
    values: Mapping[str, str],
    *,
    operation: PinnedAuthorityOperation,
) -> ProfileValidationResult:
    """Validate ``values`` against the application profile-key catalogue.

    ``values`` is keyed by canonical schema path (``identity.tax_id``,
    ``preferences.output_language`` etc.).

    Returns:
        A typed validation result carrying missing, present, and unknown paths.
    """
    entries = profile_keys(operation)
    required_keys = _required_profile_keys(values, entries)
    optional_keys = tuple(entry.key for entry in optional_profile_keys(operation))
    known_keys = set(required_keys) | set(optional_keys)

    missing_required = tuple(key for key in required_keys if not _has_value(values, key))
    present_required = _present_profile_keys(values, required_keys)
    present_optional = _present_profile_keys(values, optional_keys)
    unknown_keys = _unknown_profile_keys(values, known_keys)
    present_keys = _count_present_profile_keys(values, entries)

    return ProfileValidationResult(
        valid=not missing_required,
        missing_required=missing_required,
        present_required=present_required,
        present_optional=present_optional,
        unknown_keys=unknown_keys,
        present_keys=present_keys,
        total_keys=len(entries),
    )


def _required_profile_keys(
    values: Mapping[str, str],
    entries: tuple[ProfileKey, ...],
) -> tuple[str, ...]:
    """Return static and conditional required paths in declaration order."""
    static_required_keys = tuple(entry.key for entry in entries if _profile_entry_is_required(values, entry))
    return tuple(dict.fromkeys((*static_required_keys, *conditional_profile_required_paths(values))))


def _profile_entry_is_required(values: Mapping[str, str], entry: ProfileKey) -> bool:
    """Apply the catalogue requirement and IVA-regime conditional policy."""
    return (entry.requirement is Requirement.REQUIRED or _conditional_requirement_applies(values, entry)) and (
        entry.key != IVA_REGIME_PATH or iva_regime_required(values)
    )


def _present_profile_keys(values: Mapping[str, str], keys: Iterable[str]) -> tuple[str, ...]:
    """Return supplied keys whose values satisfy the canonical presence rule."""
    return tuple(key for key in keys if _has_value(values, key))


def _unknown_profile_keys(values: Mapping[str, str], known_keys: set[str]) -> tuple[str, ...]:
    """Return input paths absent from both required and optional catalogues."""
    return tuple(sorted(set(values) - known_keys))


def _count_present_profile_keys(values: Mapping[str, str], entries: Iterable[ProfileKey]) -> int:
    """Count catalogue paths carrying a value."""
    return sum(1 for entry in entries if _has_value(values, entry.key))


__all__ = [
    "ProfileValidationResult",
    "validate_profile_values",
]
