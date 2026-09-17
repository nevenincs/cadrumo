"""AEAT product-software identity carried by filing export envelopes."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, model_validator

from cadrumo.domain.calculations.registry.tax_id_format import SubjectTaxId

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_CONFIG

type AeatProgramIdentifier = Annotated[
    str,
    StringConstraints(min_length=4, max_length=4, pattern=r"^[A-Z0-9]{4}$"),
]
"""Exact four-byte AEAT-assigned program identifier for one export header."""


class AeatProductSoftwareEvidence(BaseModel):
    """One immutable evidence item authorising an AEAT software identity.

    This is deliberately distinct from legal, taxpayer, presenter and filing
    producer evidence. A product developer must be explicitly authorised to
    emit its program and tax identifiers; neither identifier may be guessed
    from a filing participant.
    """

    model_config = STRICT_FROZEN_CONFIG

    reference: str = Field(min_length=1, max_length=512)
    digest: ContentDigest


class AeatProductSoftwareIdentity(BaseModel):
    """Explicit product/software authority for an AEAT export header.

    No module-level instance is supplied. A caller must provide both the AEAT
    program identifier and the developer's validated Spanish tax identifier
    with reviewed evidence for every generated or emitted envelope.
    """

    model_config = STRICT_FROZEN_CONFIG

    program_identifier: AeatProgramIdentifier
    developer_tax_id: SubjectTaxId
    evidence: tuple[AeatProductSoftwareEvidence, ...] = Field(min_length=1)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _require_exact_wire_widths(self) -> AeatProductSoftwareIdentity:
        if len(self.program_identifier.encode("ascii")) != 4:
            raise ValueError("AEAT program identifier must encode to exactly four ASCII bytes")
        if len(self.developer_tax_id.encode("ascii")) != 9:
            raise ValueError("AEAT developer tax identifier must encode to exactly nine ASCII bytes")
        references = tuple(item.reference for item in self.evidence)
        if len(set(references)) != len(references):
            raise ValueError("AEAT product software evidence must not repeat a reference")
        return self


__all__ = [
    "AeatProductSoftwareEvidence",
    "AeatProductSoftwareIdentity",
    "AeatProgramIdentifier",
]
