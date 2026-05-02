"""Inbound adapter surface for Spanish tax-identifier validation.

Re-exports :func:`aeat.core.identity.validate_spanish_tax_id` so adapter-layer
callers can validate NIF / NIE values without reaching across the layer
boundary into :mod:`aeat.core.identity` directly. The validator implements
the Spanish DNI / NIE checksum algorithm (mod-23 lookup) and is the
canonical entry point for any inbound identifier coming off a PDF, XLSX,
or external service.
"""

from __future__ import annotations

from ....core.identity import validate_spanish_tax_id

__all__ = ["validate_spanish_tax_id"]
