"""PROFILE_KEYS-driven validation projection used by the CLI status surface.

The wizard catalogue (``application/wizard/_catalogue.py``) declares
each ``WizardQuestion.profile_key`` as a canonical schema-TOML path
(e.g. ``identity.tax_id``, ``preferences.output_language``).
``compile_profile_keys`` produces :data:`PROFILE_KEYS` as a tuple of
:class:`ProfileKey` records keyed by those canonical paths. The
helpers in this module project a flat operator-supplied
``Mapping[str, str]`` over that registry and report which required
keys are missing or set so the CLI status surface can render a
deterministic readiness summary.

These helpers are intentionally projection-only: they do not read or
write secure storage, do not touch :class:`WorkflowState`, and do
not depend on any CLI state. The flat-dict input is produced by
:func:`application.user_profile.record_to_values` or by the wizard
runner's canonical projection.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...domain.contribuyente import (
    ProfileKey,
    ProfileKeyRequirement,
    optional_profile_keys,
)
from ...domain.contribuyente._keys import _profile_keys as _get_profile_keys


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


class ProfileValueRow(BaseModel):
    """One schema-backed profile value row for CLI/API display."""

    model_config = _STRICT_FROZEN

    key: str
    value: str | None
    is_set: bool
    requirement: ProfileKeyRequirement
    description: str


def _has_value(values: Mapping[str, str], key: str) -> bool:
    raw = values.get(key)
    return raw is not None and raw.strip() != ""


def _conditional_requirement_applies(values: Mapping[str, str], entry: ProfileKey) -> bool:
    if entry.required_when_key is None or entry.required_when_value is None:
        return False
    raw = values.get(entry.required_when_key)
    return raw is not None and raw.strip() == entry.required_when_value


def validate_profile_values(values: Mapping[str, str]) -> ProfileValidationResult:
    """Validate ``values`` against :data:`PROFILE_KEYS`.

    ``values`` is keyed by canonical schema path
    (``identity.tax_id``, ``preferences.output_language`` etc.).

    Returns a :class:`ProfileValidationResult`.
    """
    entries = _get_profile_keys()
    required_keys = tuple(
        entry.key
        for entry in entries
        if entry.requirement is ProfileKeyRequirement.REQUIRED or _conditional_requirement_applies(values, entry)
    )
    optional_keys = tuple(entry.key for entry in optional_profile_keys())
    known_keys = set(required_keys) | set(optional_keys)

    missing_required = tuple(key for key in required_keys if not _has_value(values, key))
    present_required = tuple(key for key in required_keys if _has_value(values, key))
    present_optional = tuple(key for key in optional_keys if _has_value(values, key))
    unknown_keys = tuple(sorted(set(values) - known_keys))
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

    Each element is a :class:`ProfileKey` describing one profile field.
    """
    return _get_profile_keys()


def list_profile_value_rows(
    values: Mapping[str, str],
    *,
    include_unset: bool = False,
) -> tuple[ProfileValueRow, ...]:
    """Return schema-backed :class:`ProfileValueRow` entries for display surfaces."""
    rows: list[ProfileValueRow] = []
    for entry in _get_profile_keys():
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
            ),
        )
    return tuple(rows)


__all__ = [
    "ProfileValidationResult",
    "ProfileValueRow",
    "list_profile_key_records",
    "list_profile_value_rows",
    "validate_profile_values",
]
