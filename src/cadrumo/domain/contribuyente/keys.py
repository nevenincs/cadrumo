"""Schema-backed registry of editable taxpayer-profile keys.

The registry is a tuple of strict :class:`ProfileKey` records compiled
from the wizard descriptor catalogue
(``cadrumo.application.wizard.catalogue.WIZARD_FLOWS``) and pushed into this
domain registry via :func:`register_profile_keys` when the wizard package is
imported (its ``__init__`` eagerly runs the compiler's registration). The
domain never pulls upward into the application layer: reading the
registry before the push raises :class:`ProfileKeysRegistrationError`. Each
entry carries the canonical key path (dot-separated), a requirement flag
(required vs optional for declaration export), and a short multilingual
description rendered in operator-facing surfaces.

Adding a new key means appending a :class:`WizardQuestion` to the relevant
flow in the wizard catalogue. The :class:`ProfileKey` class itself remains the
canonical schema record consumed by ``validate_profile`` and every profile
editor surface.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core.i18n import Translatable as tr
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.requirement import Requirement
from .errors import ProfileKeysRegistrationError, ProfileValidationError
from .normalise import normalise_key

if TYPE_CHECKING:
    PROFILE_KEYS: tuple[ProfileKey, ...]


class ProfileKey(BaseModel):
    """Strict frozen record describing one editable profile key."""

    model_config = STRICT_FROZEN_CONFIG

    key: str = Field(min_length=1, max_length=128)
    requirement: Requirement
    description: tr
    required_when_key: str | None = None
    required_when_value: str | None = None

    @field_validator("key")
    @classmethod
    def _validate_key_shape(cls, value: str) -> str:
        """Reject blank or whitespace-padded keys; keep dot-separated paths intact."""
        if not value.strip():
            raise ProfileValidationError("key must not be empty or whitespace-only")
        if value.strip() != value:
            raise ProfileValidationError("key must not be padded with whitespace")
        return value

    @field_validator("description")
    @classmethod
    def _validate_description_key(cls, value: tr) -> tr:
        """Require profile-owned translation keys for authoritative descriptions."""
        if not value.strip():
            raise ProfileValidationError("description must not be empty")
        if not str(value).startswith("profile.keys."):
            raise ProfileValidationError("description must use a profile translation key")
        return value

    @field_validator("required_when_key", "required_when_value")
    @classmethod
    def _validate_conditional_requirement(cls, value: str | None) -> str | None:
        if value and value.strip() != value:
            raise ProfileValidationError("conditional requirement fields must not be padded")
        if value == "":
            raise ProfileValidationError("conditional requirement fields must not be empty")
        return value

    @model_validator(mode="after")
    def _validate_conditional_requirement_pair(self) -> ProfileKey:
        if bool(self.required_when_key) != bool(self.required_when_value):
            raise ProfileValidationError("required_when_key and required_when_value must be set together")
        return self

    @classmethod
    def from_key(cls, raw: str) -> ProfileKey:
        """Return the :class:`ProfileKey` for ``raw`` after canonical normalisation.

        Normalisation strips surrounding whitespace, lowercases, and
        folds dashes into dots so ``"TAX.ID"`` and ``"tax.id"`` resolve
        to the same registry entry.

        Args:
            raw: Raw profile key string, possibly with non-canonical
                casing or separator characters.

        Returns:
            The matching :class:`ProfileKey` from the registry.

        Raises:
            KeyError: When the normalised form is not in the registry.
        """
        canonical = normalise_key(raw)
        try:
            return _by_key()[canonical]
        except KeyError as exc:
            raise KeyError(f"unknown profile key: {raw!r}") from exc


_PROFILE_KEYS_CACHE: list[tuple[ProfileKey, ...]] = []
_BY_KEY_CACHE: list[dict[str, ProfileKey]] = []


def register_profile_keys(keys: tuple[ProfileKey, ...]) -> None:
    """Seed the domain profile-key registry from outside the domain layer.

    The domain does not compile the tuple itself: reading the registry
    before it is seeded raises :class:`ProfileKeysRegistrationError`. Outer
    layers (the wizard compiler) call this function at their own import time
    to seed the cache, which is what makes the registry readable. Calling this
    function twice with different tuples raises a :class:`RuntimeError`
    so the registration stays single-writer.
    """
    if _PROFILE_KEYS_CACHE:
        if _PROFILE_KEYS_CACHE[0] == keys:
            return
        raise ProfileKeysRegistrationError()
    _PROFILE_KEYS_CACHE.append(keys)
    _BY_KEY_CACHE.append({entry.key: entry for entry in keys})


def _profile_keys() -> tuple[ProfileKey, ...]:
    if not _PROFILE_KEYS_CACHE:
        raise ProfileKeysRegistrationError(
            "profile keys are not registered; import the wizard catalogue "
            "(cadrumo.application.wizard) so the compiled keys are pushed via "
            "register_profile_keys before the profile-key registry is read",
        )
    return _PROFILE_KEYS_CACHE[0]


def profile_keys() -> tuple[ProfileKey, ...]:
    """Return the full registered :class:`ProfileKey` tuple, resolved at call time.

    Unlike the :data:`PROFILE_KEYS` module attribute (resolved once, at
    whatever moment a caller's ``from ... import PROFILE_KEYS`` statement
    executes), this function always defers resolution to the moment it is
    called. Callers that read the registry from inside a function body
    (rather than at their own module-import time) should prefer this
    function so they cannot race the wizard catalogue's registration.
    """
    return _profile_keys()


def _by_key() -> dict[str, ProfileKey]:
    _profile_keys()
    return _BY_KEY_CACHE[0]


def __getattr__(name: str) -> tuple[ProfileKey, ...]:
    """Lazily resolve ``PROFILE_KEYS`` at first attribute access."""
    if name == "PROFILE_KEYS":
        return _profile_keys()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def get_profile_key(key: str) -> ProfileKey:
    """Return the :class:`ProfileKey` for ``key``.

    Performs canonical normalisation (strip / lowercase / dash-to-dot)
    before the registry lookup so case-insensitive callers resolve to
    the same entry as the canonical form.

    Args:
        key: Raw profile key string to look up.

    Returns:
        The matching :class:`ProfileKey` from the registry.
    """
    return ProfileKey.from_key(key)


def required_profile_keys() -> tuple[ProfileKey, ...]:
    """Return only the keys whose ``requirement`` is ``REQUIRED``.

    Returns:
        Tuple of :class:`ProfileKey` entries that are required.
    """
    return tuple(entry for entry in _profile_keys() if entry.requirement is Requirement.REQUIRED)


def optional_profile_keys() -> tuple[ProfileKey, ...]:
    """Return only the :class:`ProfileKey` entries whose ``requirement`` is ``OPTIONAL``."""
    return tuple(entry for entry in _profile_keys() if entry.requirement is Requirement.OPTIONAL)


__all__ = [
    "PROFILE_KEYS",
    "ProfileKey",
    "get_profile_key",
    "optional_profile_keys",
    "profile_keys",
    "register_profile_keys",
    "required_profile_keys",
]
