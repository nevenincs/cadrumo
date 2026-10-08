"""AEAT product-software identity carried by filing export envelopes."""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, model_validator

from cadrumo.domain.calculations.registry.export_literal_fact import ExportLiteralFact, resolve_export_literal_fact
from cadrumo.domain.calculations.registry.governed_fact_scope import GovernedFactSource, require_governed_fact_authority
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


DEVELOPMENT_MOCK_SOFTWARE_IDENTITY_FACT_ID = "aeat-eedd:development-mock-software-identity"
"""Governed mapping fact holding the development mock's program identifier and developer NIE.

The registry fact is the one home of those values: the fixed-record envelopes
bind their EEDD slots to it through ``literal_fact``, and
:func:`development_mock_software_identity` reads the same entries.
"""

DEVELOPMENT_MOCK_PROGRAM_IDENTIFIER_FACT = ExportLiteralFact(
    fact_id=DEVELOPMENT_MOCK_SOFTWARE_IDENTITY_FACT_ID,
    key="program_identifier",
)
DEVELOPMENT_MOCK_DEVELOPER_TAX_ID_FACT = ExportLiteralFact(
    fact_id=DEVELOPMENT_MOCK_SOFTWARE_IDENTITY_FACT_ID,
    key="developer_tax_id",
)

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
        zero_program = _is_all_zero(self.program_identifier)
        zero_developer = _is_all_zero(self.developer_tax_id)
        cites_mock_evidence = DEVELOPMENT_MOCK_EVIDENCE_REFERENCE in references
        if zero_program != zero_developer or zero_program != cites_mock_evidence:
            raise ValueError(
                "the all-zero development mock values and the mock evidence reference must appear together and whole",
            )
        return self

    @property
    def grade(self) -> AeatSoftwareIdentityGrade:
        """Derive the grade from the values, so a mock can never be relabelled as reviewed."""
        if _is_all_zero(self.developer_tax_id):
            return AeatSoftwareIdentityGrade.DEVELOPMENT_MOCK
        return AeatSoftwareIdentityGrade.REVIEWED


def _is_all_zero(identifier: str) -> bool:
    """Whether every digit of an identifier is zero: the mark of the development mock.

    A program identifier is all digits; a Spanish tax identifier carries one or
    two control letters around its number, so only its digits are read. No AEAT
    registration is numbered zero, which is what makes the all-zero shape a
    placeholder no reader can mistake for one.
    """
    digits = [character for character in identifier if character.isdigit()]
    return bool(digits) and all(character == "0" for character in digits)


def development_mock_software_identity(authority: GovernedFactSource | None = None) -> AeatProductSoftwareIdentity:
    """Return Cadrumo's development mock identity for envelope-prefixed export headers.

    AEAT reserves the program identifier and developer NIF header fields for a
    software developer it has registered. Cadrumo holds no such registration,
    so exports stamp the all-zero identity the governed fact
    :data:`DEVELOPMENT_MOCK_SOFTWARE_IDENTITY_FACT_ID` declares; every consumer
    reports the :attr:`AeatProductSoftwareIdentity.grade` so the operator learns
    the file is not presentable at AEAT. Both the fact and the tax identifier's
    validation need governed facts, so the caller must hold an authority
    operation or pass ``authority``.
    """
    selected = require_governed_fact_authority(authority, subject="development mock software identity")
    return AeatProductSoftwareIdentity(
        program_identifier=resolve_export_literal_fact(DEVELOPMENT_MOCK_PROGRAM_IDENTIFIER_FACT, authority=selected),
        developer_tax_id=resolve_export_literal_fact(DEVELOPMENT_MOCK_DEVELOPER_TAX_ID_FACT, authority=selected),
        evidence=(
            AeatProductSoftwareEvidence(
                reference=DEVELOPMENT_MOCK_EVIDENCE_REFERENCE,
                digest=sha256_hex(DEVELOPMENT_MOCK_EVIDENCE_REFERENCE.encode("ascii")),
            ),
        ),
    )


__all__ = [
    "DEVELOPMENT_MOCK_DEVELOPER_TAX_ID_FACT",
    "DEVELOPMENT_MOCK_EVIDENCE_REFERENCE",
    "DEVELOPMENT_MOCK_PROGRAM_IDENTIFIER_FACT",
    "DEVELOPMENT_MOCK_SOFTWARE_IDENTITY_FACT_ID",
    "AeatProductSoftwareEvidence",
    "AeatProductSoftwareIdentity",
    "AeatProgramIdentifier",
    "AeatSoftwareIdentityGrade",
    "aeat_aux_version",
    "development_mock_software_identity",
]
