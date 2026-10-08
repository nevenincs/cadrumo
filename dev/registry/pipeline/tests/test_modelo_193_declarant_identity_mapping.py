"""An intermediary must not replace the declarant in any Modelo 193 record."""

from pathlib import Path

import pytest

from ..semantic_map import load_semantic_map

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.mark.parametrize("epoch", ["2019", "2023", "2024-early", "2025"])
def test_all_record_types_keep_the_taxpayers_identity(epoch: str) -> None:
    mapping = load_semantic_map(Path(f"dev/registry/mappings/modelo_193/{epoch}"))
    entries = {entry.export_field_id: entry for entry in mapping.entries}
    declarant_fields = {
        "modelo-193-decl-nif",
        "modelo-193-perc-declarante-nif",
        "modelo-193-gasto-declarante-nif",
    }
    assert {
        entry.export_field_id for entry in mapping.entries if entry.producer_key == "taxpayer.tax_id"
    } == declarant_fields
    assert len({entries[field].anchor.record_identity for field in declarant_fields}) == 3
    assert entries["modelo-193-decl-apellidos-razon-social"].producer_key == "taxpayer.full_name"
    assert not any(entry.producer_key == "presenter.tax_id" for entry in mapping.entries)
