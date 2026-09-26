"""AEAT product-software identity carried by filing export envelopes."""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, model_validator

from cadrumo.domain.calculations.registry.tax_id_format import SubjectTaxId

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.hashing import sha256_hex
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.package_version import PACKAGE_VERSION
from .errors import FilingExportValidationError

_PACKAGE_VERSION_AEAT_AUX_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$", re.ASCII)


def aeat_aux_version() -> str:
    """Return the AEAT ``Aux/VERSION`` token for this installed product build.

    AEAT permits at most four characters in the slot.  The product version is
    the software identity it names, so the three decimal package components are
    concatenated without inventing a registry-owned override, padding, hash, or
    truncation.  Non-release package versions fail closed because their suffixes
    do not have an AEAT wire representation under this contract.
    """
    if _PACKAGE_VERSION_AEAT_AUX_PATTERN.fullmatch(PACKAGE_VERSION) is None:
        raise FilingExportValidationError(
            "PACKAGE_VERSION must contain exactly three ASCII decimal components for AEAT Aux/VERSION",
        )
    aux_version = PACKAGE_VERSION.replace(".", "")
    if len(aux_version) > 4:
        raise FilingExportValidationError(
            "PACKAGE_VERSION exceeds AEAT Aux/VERSION's four-character limit after removing dots",
        )
    return aux_version


type AeatProgramIdentifier = Annotated[
    str,
    StringConstraints(min_length=4, max_length=4, pattern=r"^[A-Z0-9]{4}$"),
]
"""Exact four-byte developer-authored software-version identifier for an AEAT header."""


DEVELOPMENT_MOCK_PROGRAM_IDENTIFIER = "0000"
"""All-zero program identifier of Cadrumo's development mock software identity."""

DEVELOPMENT_MOCK_DEVELOPER_TAX_ID = "00000000T"
"""All-zero, checksum-valid developer NIF of Cadrumo's development mock software identity."""

DEVELOPMENT_MOCK_EVIDENCE_REFERENCE = "cadrumo:development-mock-software-identity:not-aeat-certified"
"""Evidence reference naming the mock as uncertified, so no receipt can mistake it for a registration."""


class AeatSoftwareIdentityGrade(StrEnum):
    """Whether an export header's software identity is a reviewed registration or the development mock."""

    REVIEWED = "reviewed"
    """Caller-supplied program identifier and developer NIF backed by reviewed evidence."""

    DEVELOPMENT_MOCK = "development_mock"
    """Cadrumo's all-zero development identity: the rendered file is not presentable at AEAT."""


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

    No module-level instance is supplied. A caller provides both the AEAT
    program identifier and the developer's validated Spanish tax identifier
    with evidence for every generated or emitted envelope: either a reviewed
    registration, or :func:`development_mock_software_identity`, whose
    all-zero values and mock evidence must appear together.
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
        uses_mock_values = (
            self.program_identifier == DEVELOPMENT_MOCK_PROGRAM_IDENTIFIER
            or self.developer_tax_id == DEVELOPMENT_MOCK_DEVELOPER_TAX_ID
        )
        cites_mock_evidence = DEVELOPMENT_MOCK_EVIDENCE_REFERENCE in references
        if uses_mock_values != cites_mock_evidence or (
            uses_mock_values
            and (
                self.program_identifier != DEVELOPMENT_MOCK_PROGRAM_IDENTIFIER
                or self.developer_tax_id != DEVELOPMENT_MOCK_DEVELOPER_TAX_ID
            )
        ):
            raise ValueError(
                "the all-zero development mock values and the mock evidence reference must appear together and whole",
            )
        return self

    @property
    def grade(self) -> AeatSoftwareIdentityGrade:
        """Derive the grade from the values, so a mock can never be relabelled as reviewed."""
        if self.developer_tax_id == DEVELOPMENT_MOCK_DEVELOPER_TAX_ID:
            return AeatSoftwareIdentityGrade.DEVELOPMENT_MOCK
        return AeatSoftwareIdentityGrade.REVIEWED


def development_mock_software_identity() -> AeatProductSoftwareIdentity:
    """Return Cadrumo's development mock identity for envelope-prefixed export headers.

    AEAT reserves the program identifier and developer NIF header fields for a
    software developer it has registered. Cadrumo holds no such registration,
    so exports stamp an all-zero identity that no reader can mistake for one;
    every consumer reports the :attr:`AeatProductSoftwareIdentity.grade` so the
    operator learns the file is not presentable at AEAT. The tax identifier is
    validated like any other, so the caller must hold an authority operation.
    """
    return AeatProductSoftwareIdentity(
        program_identifier=DEVELOPMENT_MOCK_PROGRAM_IDENTIFIER,
        developer_tax_id=DEVELOPMENT_MOCK_DEVELOPER_TAX_ID,
        evidence=(
            AeatProductSoftwareEvidence(
                reference=DEVELOPMENT_MOCK_EVIDENCE_REFERENCE,
                digest=sha256_hex(DEVELOPMENT_MOCK_EVIDENCE_REFERENCE.encode("ascii")),
            ),
        ),
    )


__all__ = [
    "DEVELOPMENT_MOCK_DEVELOPER_TAX_ID",
    "DEVELOPMENT_MOCK_EVIDENCE_REFERENCE",
    "DEVELOPMENT_MOCK_PROGRAM_IDENTIFIER",
    "AeatProductSoftwareEvidence",
    "AeatProductSoftwareIdentity",
    "AeatProgramIdentifier",
    "AeatSoftwareIdentityGrade",
    "aeat_aux_version",
    "development_mock_software_identity",
]
