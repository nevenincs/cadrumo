"""Typed identity primitives for the operator profile and its storage slice.

A `ProfileName` is the operator-typed label for one identity (one NIF,
one activity, one IVA regime, one language preference). A `BucketId`
is the storage-layer identifier for the encrypted slice that holds
one profile's persisted records. The profile-bucket lifecycle ADR
mandates 1:1 cardinality between profile and bucket, so the two
aliases are interchangeable at the boundary but carry different
intent in code: `ProfileName` lives on operator-facing surfaces (CLI
arguments, prompts, status emit), `BucketId` lives on storage-layer
surfaces (manifest fields, secure-object indices, audit-event
records).

Both aliases preserve the historical secure-object index constraint
(strip whitespace, minimum length one, maximum length 128). Tighter
validation (kebab-case, locale-safety, reserved-name refusal) is a
deliberate future tightening; introducing it here would invalidate
historical bucket-id values stored in encrypted indices and is out
of scope for the introduction commit.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import StringConstraints

ProfileName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]
"""Operator-typed identifier for one profile."""

BucketId = ProfileName
"""Storage-layer identifier for the encrypted slice behind one profile."""


__all__ = ["BucketId", "ProfileName"]
