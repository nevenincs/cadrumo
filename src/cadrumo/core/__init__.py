"""Public facade for Cadrumo's canonical product identity.

The core package currently exposes the immutable product tuple and the closed
referent vocabulary that distinguishes Cadrumo from the external AEAT authority.
Broader core primitives move to this package in the later root-relocation wave;
this facade deliberately exports no former-product aliases or compatibility
fallbacks.
"""

from __future__ import annotations

from .product_identity import (
    AEAT_AUTHORITY_SHORT_NAME,
    PRODUCT_IDENTITY,
    IdentityReferent,
    ProductIdentity,
)

__all__: list[str] = [
    "AEAT_AUTHORITY_SHORT_NAME",
    "PRODUCT_IDENTITY",
    "IdentityReferent",
    "ProductIdentity",
]
