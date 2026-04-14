"""Authoritative AEAT modelo catalogue and metadata.

This subpackage exposes the closed, strict, pydantic v2 registry of
every AEAT modelo the project tracks in v1 (twenty codes: 036, 037,
100, 111, 115, 123, 130, 131, 180, 190, 200, 202, 232, 303, 347, 349,
369, 390, 720, 840). The registry is built at import time from the
per-modelo entries under the private ``_entries`` package and is
frozen as a :class:`types.MappingProxyType`.

Consumers outside :mod:`aeat.models` MUST import from this module
only; the underscore-prefixed submodules are internal and unstable.
The public surface is the :data:`__all__` tuple below.

Architectural context: see the 2026-04-13 modelo-inventory ADR and
the accompanying research document for the provenance of each
modelo's data. Deadlines are resolved at query time through the
:func:`year_plan` helper, which delegates to
:mod:`aeat.deadlines` — the catalogue itself is import-time free
of any deadline dependency.
"""

from __future__ import annotations

from aeat.models._applicability import ModeloApplicability
from aeat.models._categories import (
    LegalCitationSource,
    ModeloCadence,
    ModeloCategory,
    TaxpayerProfile,
)
from aeat.models._citations import LegalCitation
from aeat.models._codes import ModeloCode
from aeat.models._errors import (
    ModeloRegistryError,
    RegistryIntegrityError,
    UnknownModeloError,
)
from aeat.models._metadata import ModeloMetadata
from aeat.models._registry import (
    MODELO_REGISTRY,
    get_modelo,
    modelos_for_profile,
    year_plan,
)

__all__ = (
    "MODELO_REGISTRY",
    "LegalCitation",
    "LegalCitationSource",
    "ModeloApplicability",
    "ModeloCadence",
    "ModeloCategory",
    "ModeloCode",
    "ModeloMetadata",
    "ModeloRegistryError",
    "RegistryIntegrityError",
    "TaxpayerProfile",
    "UnknownModeloError",
    "get_modelo",
    "modelos_for_profile",
    "year_plan",
)
