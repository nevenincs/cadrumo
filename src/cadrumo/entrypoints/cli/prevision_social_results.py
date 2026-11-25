"""Typed JSON payloads for the pension contribution certificate CLI.

No payload carries a tax identifier: a record is named by its keyed
``issuer_ref`` and ``plan_ref``, the issuer's legal name and the plan's name;
:class:`OutputSchema`, the declared output contract.
"""

from __future__ import annotations

from ...core.identity.bucket import BucketId
from ...core.json_contract import OutputSchema


class PrevisionSocialRowPayload(OutputSchema):
    """One stored contribution record without any tax identifier."""

    ejercicio: int
    issuer_ref: str
    issuer_name: str | None = None
    plan_ref: str | None = None
    plan_name: str | None = None
    clave: str
    subclave: str | None = None
    amount: str
    beneficiary: str
    employer_same_plan: bool | None = None
    casilla_id: str | None = None
    evidence_sha256: str
    replaces_evidence_sha256: str | None = None
    revision_id: str


class PrevisionSocialRecordResult(OutputSchema):
    """JSON envelope for ``aeat app ledger prevision-social record``."""

    bucket_id: BucketId
    row: PrevisionSocialRowPayload
    count: int


class PrevisionSocialListResult(OutputSchema):
    """JSON envelope for ``aeat app ledger prevision-social list``."""

    bucket_id: BucketId
    ejercicio: int
    rows: list[PrevisionSocialRowPayload]
    count: int


class PrevisionSocialRemoveResult(OutputSchema):
    """JSON envelope for ``aeat app ledger prevision-social remove``."""

    bucket_id: BucketId
    ejercicio: int
    issuer_ref: str
    plan_ref: str | None = None
    clave: str
    subclave: str | None = None
    count: int


__all__ = [
    "PrevisionSocialListResult",
    "PrevisionSocialRecordResult",
    "PrevisionSocialRemoveResult",
    "PrevisionSocialRowPayload",
]
