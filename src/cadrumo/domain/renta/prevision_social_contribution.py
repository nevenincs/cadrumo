"""One contribution to a social-welfare system, as the issuer's certificate states it.

A plan manager, mutualidad or insurer certifies to the taxpayer what it declares
on Modelo 345 for one plan and ejercicio: the official clave and subclave and the
amount. A record restates one such line. It is the evidence behind the Modelo 100
boxes of the reduction for contributions to social-welfare systems (LIRPF arts.
51 and 52), and it computes nothing: the casilla it reaches is registry data per
edition (:mod:`.prevision_social_contribution_placement`).

The issuer's and the plan's identifiers live only inside the encrypted payload.
Wherever the record must be named outside it, it is named by keyed digests the
storage adapter computes under a profile-held key, as the payer of a withholding
record is.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Self

from pydantic import BaseModel, Field, model_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.filing_year import FilingYear
from ...core.hex import Hex64Str
from ...core.identity.digest import ContentDigest
from ...core.identity.tax_id import TaxIdIdentityToken
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.prevision_social import (
    PrevisionSocialBeneficiario,
    PrevisionSocialClave,
    PrevisionSocialSubclave,
    is_defined_clave_pair,
)
from ...core.time.utc import UtcInstant
from .errors import RentaValidationError

__all__ = ["PrevisionSocialContribution", "PrevisionSocialContributionIdentity"]

type _Importe = Annotated[Decimal, Field(ge=Decimal("0"), decimal_places=2)]
"""A non-negative euro amount with at most two decimals; a third decimal is refused, never rounded."""

type PrevisionSocialContributionIdentity = tuple[
    int, str, str | None, PrevisionSocialClave, PrevisionSocialSubclave | None
]
"""The ``(ejercicio, issuer_ref, plan_ref, clave, subclave)`` a record is stored under, one row each."""


class PrevisionSocialContribution(BaseModel):
    """One certified contribution of one clave and subclave, to one plan, for one ejercicio.

    Payload schema v1.
    """

    model_config = STRICT_FROZEN_CONFIG

    ejercicio: FilingYear
    """The year the contribution was paid in."""
    issuer_tax_id: Annotated[TaxIdIdentityToken, Field(min_length=1, max_length=32)]
    """The NIF of the plan manager, mutualidad or insurer that certifies the contribution."""
    issuer_legal_name: str | None = Field(default=None, min_length=1, max_length=256)
    issuer_ref: Hex64Str
    """The keyed digest of :attr:`issuer_tax_id`, computed by the storage adapter."""
    plan_tax_id: Annotated[TaxIdIdentityToken, Field(min_length=1, max_length=32)] | None = None
    """The NIF of the plan, where the instrument has one of its own."""
    plan_name: str | None = Field(default=None, min_length=1, max_length=256)
    plan_ref: Hex64Str | None = None
    """The keyed digest of :attr:`plan_tax_id`, computed by the storage adapter; present exactly when it is."""
    clave: PrevisionSocialClave
    subclave: PrevisionSocialSubclave | None = None
    amount: _Importe
    beneficiary: PrevisionSocialBeneficiario
    employer_contributed_to_same_plan: bool | None = None
    """Whether the employer contributed to the same plan, where the certificate or the operator states it.

    Some claves reach a different casilla depending on the answer; the registry
    says which, and a record of such a clave that leaves it unstated is refused.
    """
    evidence_fingerprint: ContentDigest
    """The sha256 of the certificate bytes."""
    replaces_evidence_fingerprint: ContentDigest | None = None
    """The certificate this record's figures correct or replace, when they do.

    Equal to :attr:`evidence_fingerprint` when the figures correct a mistake made
    in reading the same certificate.
    """
    captured_at: UtcInstant

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _pair_is_defined(self) -> Self:
        if not is_defined_clave_pair(self.clave, self.subclave):
            raise RentaValidationError("the Modelo 345 design defines no such subclave for this clave")
        return self

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _plan_ref_follows_plan_tax_id(self) -> Self:
        if (self.plan_tax_id is None) != (self.plan_ref is None):
            raise RentaValidationError("a plan reference is stated exactly when the plan's tax ID is")
        return self

    @property
    def identity(self) -> PrevisionSocialContributionIdentity:
        """Return the identity this record is stored under."""
        return (self.ejercicio, self.issuer_ref, self.plan_ref, self.clave, self.subclave)
