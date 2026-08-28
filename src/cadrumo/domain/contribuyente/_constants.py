"""Typed identity primitive for the operator profile and its storage slice.

A `ProfileName` is the operator-typed label for one identity (one NIF,
one activity, one IVA regime, one language preference). The same
typed alias is reused on storage-layer surfaces (manifest fields,
secure-object indices, audit-event records) because a profile and its
bucket carry 1:1 cardinality:
operator-facing CLI arguments / prompts / status emit and storage-
layer index entries name the same identifier, so introducing a
second alias only added documentation surface without changing the
constraint or the value.

The alias preserves the historical secure-object index constraint
(strip whitespace, minimum length one, maximum length 128). Tighter
validation (kebab-case, locale-safety, reserved-name refusal) is a
deliberate future tightening; introducing it here would invalidate
historical values stored in encrypted indices and is out of scope.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator, StringConstraints

from .errors import ProfileValidationError

ProfileName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]
"""Typed identifier for one profile. Used on operator-facing surfaces
(CLI arguments, prompts, status emit) AND storage-layer surfaces
(manifest fields, secure-object indices, audit-event records)."""


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


__all__ = ["SUPPORTED_PROFILE_SCHEMA_VERSION", "ProfileName", "ProfileSchemaVersion"]
