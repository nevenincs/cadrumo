"""Modelo identity codes and informational-declaration row models.

The public surface exposes ``ModeloCode`` (the closed set of AEAT modelo
identifiers) together with the typed per-row records for the informational
declarations: ``Modelo184MemberRow``, ``Modelo232VinculadaRow``,
``Modelo347ContraparteRow``, ``Modelo349OperadorRow``, and ``ModeloDetailRow``
(plus ``validate_m349_nif_format``). The Modelo 347 declarability threshold is a
regulatory constant owned by ``core.external_constants`` (``M347_THRESHOLD_EUR``),
consumed directly from there.

The package also hosts, as submodules imported by their consumers directly, the
domain-layer modelo persistence and identity core: the calculation, filing, and
verification repositories, calculation revisions, filing records, verification
reports, and work units.
"""

from __future__ import annotations

from ._codes import ModeloCode
from ._row_models import (
    Modelo184MemberRow,
    Modelo232VinculadaRow,
    Modelo347ContraparteRow,
    Modelo349OperadorRow,
    ModeloDetailRow,
    validate_m349_nif_format,
)

__all__ = (
    "Modelo184MemberRow",
    "Modelo232VinculadaRow",
    "Modelo347ContraparteRow",
    "Modelo349OperadorRow",
    "ModeloCode",
    "ModeloDetailRow",
    "validate_m349_nif_format",
)
