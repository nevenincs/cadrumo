"""Modelo 347 schema manifest for exercise 2024."""

from __future__ import annotations

from decimal import Decimal

from ._records import ClaveOperacion, Modelo347RecordLine, Modelo347SchemaManifest

_RECORD_FIELDS = tuple(Modelo347RecordLine.model_fields)

MANIFEST_2024 = Modelo347SchemaManifest(
    ejercicio=2024,
    threshold_amount=Decimal("3005.06"),
    operation_keys=tuple(ClaveOperacion),
    record_fields=_RECORD_FIELDS,
    source="Orden EHA/3012/2008 consolidated Modelo 347 type-2 declared-person record",
)

__all__ = ["MANIFEST_2024"]
