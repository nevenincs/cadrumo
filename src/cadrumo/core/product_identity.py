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
from typing import Final, NamedTuple


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
    mcp_server: str
    mcp_executable: str
    mcp_tool_prefix: str
    mcp_resource_scheme: str
    plugin_identifier: str
    environment_prefix: str
    companion_distributions: tuple[str, str]
    companion_namespace: str


PRODUCT_IDENTITY: Final[ProductIdentity] = ProductIdentity(
    display_name="CADRUMO",
    prose_name="Cadrumo",
    python_package="cadrumo",
    distribution="cadrumo",
    cli_executable="aeat",
    repository="nevenincs/cadrumo",
    mcp_server="cadrumo",
    mcp_executable="cadrumo-mcp",
    mcp_tool_prefix="cadrumo",
    mcp_resource_scheme="cadrumo",
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
    "IdentityReferent",
    "ProductIdentity",
    "normalise_product_identity_references",
]
