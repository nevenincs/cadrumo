"""A two-field record-design intermediate payload shared by the semantic-map tests."""

from __future__ import annotations

from ..pipeline.record_design_intermediate import RecordDesignWorkbookFormat


def intermediate_payload(
    *,
    source_sha256: str = "0" * 64,
    source_ref: str = "aeat-dr-200-2025",
    design_epoch: str = "2025",
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
