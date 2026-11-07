"""A two-field record-design intermediate payload shared by the semantic-map tests."""

from __future__ import annotations

from cadrumo.domain.calculations.registry.tests.authored_editions import newest_authored_edition

from ..pipeline.record_design_intermediate import RecordDesignWorkbookFormat

DEFAULT_DESIGN_EPOCH = str(newest_authored_edition("200"))
"""The design epoch of the default Modelo 200 source: the newest edition that modelo authors."""


def intermediate_payload(
    *,
    source_sha256: str = "0" * 64,
    source_ref: str = "aeat-dr-200-2025",
    design_epoch: str = DEFAULT_DESIGN_EPOCH,
) -> dict[str, object]:
    return {
        "source": {
            "source_ref": source_ref,
            "source_sha256": source_sha256,
            "workbook_format": RecordDesignWorkbookFormat.XLSX,
            "design_epoch": design_epoch,
        },
        "sheets": (
            {
                "sheet": "Registro tipo 1",
                "record_identity": "registro-tipo-1",
                "declared_total": 2,
                "fields": (
                    {
                        "sheet": "Registro tipo 1",
                        "record_identity": "registro-tipo-1",
                        "source_row": 14,
                        "source_cell": "A14",
                        "ordinal": "1",
                        "offset": 1,
                        "length": 1,
                        "aeat_type": "AN",
                        "normalized_description": "Campo uno",
                    },
                    {
                        "sheet": "Registro tipo 1",
                        "record_identity": "registro-tipo-1",
                        "source_row": 15,
                        "source_cell": "A15",
                        "ordinal": "2",
                        "offset": 2,
                        "length": 1,
                        "aeat_type": "AN",
                        "normalized_description": "Campo dos",
                    },
                ),
            },
        ),
    }
