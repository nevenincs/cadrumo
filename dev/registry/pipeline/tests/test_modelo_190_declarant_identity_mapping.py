"""The declarant remains the taxpayer when an intermediary presents the return."""

from pathlib import Path

import pytest

from ..semantic_map import load_semantic_map

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.mark.parametrize("epoch", ["2020", "2023", "2024", "2025"])
def test_both_record_types_bind_declarant_identity_to_the_taxpayer(epoch: str) -> None:
    mapping = load_semantic_map(Path(f"dev/registry/mappings/modelo_190/{epoch}"))
    entries = {entry.export_field_id: entry for entry in mapping.entries}
    declarant = entries["modelo-190-decl-nif"]
    assert declarant.producer_key == "taxpayer.tax_id"
    repeated = [
        entry
        for entry in mapping.entries
        if entry.export_field_id != declarant.export_field_id and entry.producer_key == "taxpayer.tax_id"
    ]
    assert len(repeated) == 1
    assert repeated[0].anchor.record_identity == "Tipo 2 - Registro De Perceptor"
    assert entries["modelo-190-decl-apellidos-razon-social"].producer_key == "taxpayer.full_name"
    assert not any(entry.producer_key == "presenter.tax_id" for entry in mapping.entries)
