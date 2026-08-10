"""Typed-id aliases for modelo records.

Each modelo record (work unit, calculation revision, filing record)
carries a content-addressed SHA-256 identity. The aliases here pin the
hex-64 shape at the pydantic boundary so a malformed identifier is
rejected on construction rather than leaking into persisted records.

These identities share the same string-level shape but carry distinct
semantic roles (a work-unit id is not assignable to a filing-record id
field). Keeping them as separate aliases preserves that distinction for
downstream call sites; collapsing them to a single hex-64 alias would
lose the role separation.

An identity consumed ACROSS package boundaries does not belong here, and
several have already moved out for that reason: the per-profile storage
bucket, the ledger transaction, the content-addressed invoice and the
verification report all live in :mod:`cadrumo.core.identity`, each
aliased from the one canonical hex-64 primitive. The rule that decides
placement is ownership rather than subject matter -- a modelo record's
own identity stays here, and an identity a sibling package must name in
its own signatures goes to the shared home. The remaining aliases are
migrating to that home as their consumer sweeps land.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import StringConstraints

_HEX_64_PATTERN = r"^[0-9a-f]{64}$"

WorkUnitId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=64, max_length=64, pattern=_HEX_64_PATTERN),
]
"""Hex-64 identity of a modelo work unit. Minted via ``new_work_unit_id()``."""

__all__ = ("WorkUnitId",)
