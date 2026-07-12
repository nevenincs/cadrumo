"""Typed identity primitive for the operator profile and its storage slice.

A `ProfileName` is the operator-typed label for one identity (one NIF,
one activity, one IVA regime, one language preference). The same
typed alias is reused on storage-layer surfaces (manifest fields,
secure-object indices, audit-event records) because the profile-bucket
lifecycle ADR mandates 1:1 cardinality between profile and bucket:
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

from pydantic import StringConstraints

ProfileName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]
"""Typed identifier for one profile. Used on operator-facing surfaces
(CLI arguments, prompts, status emit) AND storage-layer surfaces
(manifest fields, secure-object indices, audit-event records)."""


__all__ = ["ProfileName"]
