"""Application-level export serialization helpers.

Serializes tabular application data into the operator-chosen output format
for the export verbs, separate from the registry-driven fichero-BOE modelo
export. Pure value logic with no I/O.

Major declarations:

* :func:`serialize_tabular_rows` — render rows into a
  :class:`TabularExportResult`.
* :class:`ExportSerializationFormat` — the closed set of supported output
  formats.
"""

from __future__ import annotations

from ._tabular import ExportSerializationFormat, TabularExportResult, serialize_tabular_rows

__all__ = [
    "ExportSerializationFormat",
    "TabularExportResult",
    "serialize_tabular_rows",
]
