"""Canonical Cadrumo product identity and AEAT authority vocabulary.

This module is the single runtime authority for names that identify the
application.  :data:`PRODUCT_IDENTITY` projects the accepted CADRUMO tuple into
an immutable, import-light value.  :class:`IdentityReferent` supplies the closed
vocabulary used to distinguish that product identity from references to the
external Spanish tax authority.

``AEAT`` remains correct when it denotes the Agencia Estatal de Administracion
Tributaria, its portals, protocols, credentials, official artefacts, legal
provenance, or registry classifications.  It is not a former-product alias.
Conversely, every product surface uses the CADRUMO values below; this module
provides no legacy spelling, compatibility lookup, or fallback.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Annotated, Final, NamedTuple

from pydantic import BaseModel, Field, StringConstraints, model_validator

from .models import STRICT_FROZEN_CONFIG
from .identity import ContentDigest, SubjectTaxId


class IdentityReferent(StrEnum):
    """Closed vocabulary for deciding which entity an identity names."""

    CADRUMO_PRODUCT = "cadrumo_product"
    AEAT_AUTHORITY = "aeat_authority"


class ProductIdentity(NamedTuple):
    """Immutable names that jointly identify the Cadrumo product.

    ``repository`` is the owner-qualified source repository slug.
    """

    display_name: str
    prose_name: str
    python_package: str
    distribution: str
    cli_executable: str
    repository: str
    plugin_identifier: str
    environment_prefix: str
    companion_distributions: tuple[str, str]
    companion_namespace: str


type AeatProgramIdentifier = Annotated[
    str,
    StringConstraints(min_length=4, max_length=4, pattern=r"^[A-Z0-9]{4}$"),
]
"""Exact four-byte AEAT-assigned program identifier for one export header."""


class AeatProductSoftwareEvidence(BaseModel):
    """One immutable evidence item authorising an AEAT software identity.

    This is deliberately distinct from legal, taxpayer, presenter and filing
    producer evidence.  A product developer must be explicitly authorised to
    emit its program and tax identifiers; neither identifier may be guessed
    from a filing participant.
    """

    model_config = STRICT_FROZEN_CONFIG

    reference: str = Field(min_length=1, max_length=512)
    digest: ContentDigest


class AeatProductSoftwareIdentity(BaseModel):
    """The one explicit product/software authority for an AEAT export header.

    No module-level instance is supplied.  A caller must provide both the AEAT
    program identifier and the developer's validated Spanish tax identifier
    with reviewed evidence for every generated or emitted envelope.
    """

    model_config = STRICT_FROZEN_CONFIG

    program_identifier: AeatProgramIdentifier
    developer_tax_id: SubjectTaxId
    evidence: tuple[AeatProductSoftwareEvidence, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _require_exact_wire_widths(self) -> AeatProductSoftwareIdentity:
        if len(self.program_identifier.encode("ascii")) != 4:
            raise ValueError("AEAT program identifier must encode to exactly four ASCII bytes")
        if len(self.developer_tax_id.encode("ascii")) != 9:
            raise ValueError("AEAT developer tax identifier must encode to exactly nine ASCII bytes")
        references = tuple(item.reference for item in self.evidence)
        if len(set(references)) != len(references):
            raise ValueError("AEAT product software evidence must not repeat a reference")
        return self


PRODUCT_IDENTITY: Final[ProductIdentity] = ProductIdentity(
    display_name="CADRUMO",
    prose_name="Cadrumo",
    python_package="cadrumo",
    distribution="cadrumo",
    cli_executable="aeat",
    repository="nevenincs/cadrumo",
    plugin_identifier="cadrumo",
    environment_prefix="CADRUMO_",
    companion_distributions=("cadrumo-data-manuals", "cadrumo-data-official"),
    companion_namespace="cadrumo_data",
)

#: Short legal name retained only for the external tax authority referent.
AEAT_AUTHORITY_SHORT_NAME: Final[str] = "AEAT"

_STALE_CLI_EXECUTABLE_RE = re.compile(r"\bcadrumo(?=[ \t\r\n]+(?:app|config|manual|--|<))")


def normalise_product_identity_references(value: str) -> str:
    """Replace only stale human command prefixes with the canonical executable."""
    return _STALE_CLI_EXECUTABLE_RE.sub(PRODUCT_IDENTITY.cli_executable, value)


__all__ = [
    "AEAT_AUTHORITY_SHORT_NAME",
    "PRODUCT_IDENTITY",
    "AeatProductSoftwareEvidence",
    "AeatProductSoftwareIdentity",
    "AeatProgramIdentifier",
    "IdentityReferent",
    "ProductIdentity",
    "normalise_product_identity_references",
]
