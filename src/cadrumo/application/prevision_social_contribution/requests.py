"""Exact-profile request schemas for the pension contribution certificate operations."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.filing_year import FilingYear
from ...core.hex import Hex64Str
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.prevision_social import PrevisionSocialBeneficiario, PrevisionSocialClave, PrevisionSocialSubclave
from ..operations.public_scalar import PublicDecimal

type _Revision = Annotated[str, Field(min_length=1, max_length=128)]
type _Path = Annotated[str, Field(min_length=1, max_length=4_096)]
type _TaxId = Annotated[str, Field(min_length=1, max_length=32)]
type _Name = Annotated[str, Field(min_length=1, max_length=256)]


class PrevisionSocialProfileRequest(BaseModel):
    """Common private exact-profile binding for the contribution operations."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID


class PrevisionSocialListRequest(PrevisionSocialProfileRequest):
    """Read every stored contribution record of one ejercicio."""

    ejercicio: FilingYear


class PrevisionSocialRecordRequest(PrevisionSocialProfileRequest):
    """Add one certified contribution, or correct the stored one of the same issuer, plan, clave and subclave.

    ``issuer_tax_id`` and ``plan_tax_id`` are sensitive inputs: the model never
    echoes them in a validation error. ``expected_revision_id`` is absent for a
    first record and the revision a prior list showed for a correction, which
    replaces the stored certificate's figures and records the certificate it
    replaces.

    The certificate is named by ``source_path`` (resolved against
    ``source_directory``, the submitting frontend's directory), which the worker
    reads and keeps in encrypted attachment custody, or by ``evidence_fingerprint``
    alone for bytes custody already holds. Given with a file, the fingerprint is
    only an integrity cross-check against the bytes read.

    ``employer_contributed_to_same_plan`` is the answer some claves need to reach
    a box; the operation refuses such a clave when it is left unstated.
    """

    ejercicio: FilingYear
    issuer_tax_id: _TaxId
    issuer_legal_name: _Name | None = None
    plan_tax_id: _TaxId | None = None
    plan_name: _Name | None = None
    clave: PrevisionSocialClave
    subclave: PrevisionSocialSubclave | None = None
    amount: PublicDecimal
    beneficiary: PrevisionSocialBeneficiario = PrevisionSocialBeneficiario.TAXPAYER
    employer_contributed_to_same_plan: bool | None = None
    evidence_fingerprint: ContentDigest | None = None
    source_path: _Path | None = None
    source_directory: _Path | None = None
    expected_revision_id: _Revision | None = None

    @model_validator(mode="after")
    def _file_is_resolved_against_a_directory(self) -> PrevisionSocialRecordRequest:
        if (self.source_path is None) != (self.source_directory is None):
            raise ValueError("a certificate file is named by a path and the directory it is resolved against")
        return self


class PrevisionSocialRemoveRequest(PrevisionSocialProfileRequest):
    """Remove the record stored under ``(ejercicio, issuer_ref, plan_ref, clave, subclave)``."""

    ejercicio: FilingYear
    issuer_ref: Hex64Str
    plan_ref: Hex64Str | None = None
    clave: PrevisionSocialClave
    subclave: PrevisionSocialSubclave | None = None
    expected_revision_id: _Revision


__all__ = [
    "PrevisionSocialListRequest",
    "PrevisionSocialProfileRequest",
    "PrevisionSocialRecordRequest",
    "PrevisionSocialRemoveRequest",
]
