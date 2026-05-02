"""Authoritative AEAT modelo catalogue and metadata.

This subpackage exposes the closed, strict, pydantic v2 registry of
every AEAT modelo the project tracks (twenty-one codes: 036, 037, 100,
111, 115, 123, 130, 131, 180, 190, 193, 200, 202, 232, 303, 347, 349,
369, 390, 720, 840). The registry is built at import time from the
per-modelo entries under the private ``_entries`` package and is
frozen as a :class:`types.MappingProxyType`.

Consumers outside :mod:`aeat.domain.modelos` MUST import from this
module only; the underscore-prefixed submodules are internal and
unstable. The public surface is the :data:`__all__` tuple below.

Deadlines are resolved at query time through the :func:`year_plan`
helper, which delegates to :mod:`aeat.domain.deadlines` — the
catalogue itself is import-time free of any deadline dependency.
"""

from __future__ import annotations

from ._applicability import ModeloApplicability
from ._categories import (
    LegalCitationSource,
    ModeloCadence,
    ModeloCategory,
    TaxpayerProfile,
)
from ._citations import LegalCitation
from ._codes import ModeloCode
from ._errors import (
    ModeloRegistryError,
    RegistryIntegrityError,
    UnknownModeloError,
)
from ._metadata import ModeloMetadata
from ._registry import (
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
