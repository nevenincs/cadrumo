"""Current profile-record schema version contract."""

from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator

from .errors import ProfileValidationError

SUPPORTED_PROFILE_SCHEMA_VERSION = "1"
"""The only profile-record schema version this code reads or writes."""


def _require_supported_profile_schema_version(value: str) -> str:
    if value != SUPPORTED_PROFILE_SCHEMA_VERSION:
        raise ProfileValidationError(
            f"schema_version must be {SUPPORTED_PROFILE_SCHEMA_VERSION!r}",
        )
    return value


ProfileSchemaVersion = Annotated[str, AfterValidator(_require_supported_profile_schema_version)]
"""The profile-record schema version, refused unless it is the supported one.

Every profile record carries this, and the refusal is deliberately a hard
:class:`~cadrumo.domain.contribuyente.errors.ProfileValidationError` rather than
a pattern constraint, so the message names the version rather than reciting a
regular expression.

One alias rather than a validator per model: the two profile records declaring
this field each carried a byte-identical copy, so bumping the version in one
would have left the other refusing the value the first had just started
writing -- a divergence no test would catch, because each model's own
roundtrip would still pass."""


__all__ = ["SUPPORTED_PROFILE_SCHEMA_VERSION", "ProfileSchemaVersion"]
