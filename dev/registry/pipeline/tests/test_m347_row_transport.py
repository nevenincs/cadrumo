"""The selected M347 source keeps inmueble rows optional and repeatable."""

from __future__ import annotations

import json
import shutil
import tomllib
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.application.filing.record_renderer import record_render_rows
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.ids import BindingId
from cadrumo.domain.calculations.registry.schema_exports import ExportRecordDefinition
from dev.registry.compiler.authority import compiled_bundled_authority
from dev.registry.pipeline import render_check
from dev.registry.pipeline._export_tree import render_complete_export_tree
from dev.registry.pipeline.render_check import revision_render_inputs
from dev.registry.pipeline.source_defects import source_defects_for

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

AUTHORED_ROOT = Path(__file__).resolve().parents[2]
EPOCHS = (
    ("2011-2024", "2011", "aeat-dr-347-2011", "4cdfb401624e26abe3da3758ddcdcfc85b6b05ffa74e724b2d3f5eeb0c58e809"),
    (
        "2025-y-siguientes",
        "2025",
        "aeat-dr-347-2025",
        "14583ea5ee04441356c4572d30630d46bfe0818366e575ac186370dd3fe38361",
    ),
)
INMUEBLE_ROW_FIELDS = {
    "declarado_tax_id": "inmueble.arrendatario-nif",
    "party_legal_name": "inmueble.arrendatario-nombre",
    "importe_total": "inmueble.importe-operacion",
    "situacion_inmueble": "inmueble.situacion",
    "referencia_catastral": "inmueble.referencia-catastral",
    "premises_address": "inmueble.direccion",
}
LEASE_AMOUNT = "modelo-347-inmueble-row-importe"


@pytest.fixture(scope="module")
def authority():
    """Compile the actual complete source registry once for both design epochs."""
    return compiled_bundled_authority()


def require_two_lease_rows(record: ExportRecordDefinition) -> tuple[int | None, ...]:
    """Refuse a record shape that silently collapses two typed lease rows."""
    values: dict[tuple[BindingId, int | None], object] = {
        (LEASE_AMOUNT, 1): Decimal("12100.00"),
        (LEASE_AMOUNT, 2): Decimal("7260.00"),
    }
    rows = record_render_rows(record, values, {})
    indices = tuple(row.row_index for row in rows)
    if indices != (1, 2):
        raise ValueError(f"M347 inmueble loses source rows: {indices!r}")
    return indices


@pytest.mark.parametrize("revision,epoch,source_ref,source_sha256", EPOCHS)
def test_pinned_map_renders_optional_repeated_inmueble(
    authority,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    revision: str,
    epoch: str,
    source_ref: str,
    source_sha256: str,
) -> None:
    """Source join and production row renderer retain 0-or-many lease cardinality."""
    monkeypatch.setattr(render_check, "_AUTHORED_ROOT", AUTHORED_ROOT)
    inputs = revision_render_inputs(authority, modelo="347", revision=revision)
    assert str(inputs.joined.source.source_ref) == source_ref
    assert inputs.joined.source.source_sha256 == source_sha256
    assert inputs.semantic_map.design_epoch == epoch
    records = {record.export_record_id: record for record in inputs.semantic_map.records}
    declarado = records["m347-declarado"]
    inmueble = records["m347-inmueble"]
    assert declarado.repeat == "binding_rows"
    assert inmueble.required is False
    assert inmueble.repeat == "binding_rows"
    assert dict(inmueble.row_field_casilla_ids) == INMUEBLE_ROW_FIELDS
    declared_rows = dict(declarado.row_field_casilla_ids)
    assert declared_rows["provincia_code"] == "contraparte.provincia-codigo"
    assert declared_rows["business_premises_lease_mark"] == "contraparte.arrendamiento-local-negocio"
    if epoch == "2025":
        assert declared_rows["cash_accounting_mark"] == "contraparte.criterio-caja"
        assert declared_rows["reverse_charge_mark"] == "contraparte.inversion-sujeto-pasivo"

    destination = tmp_path / "export"
    render_complete_export_tree(
        destination,
        revision_id=inputs.revision_id,
        joined=inputs.joined,
        semantic_map=inputs.semantic_map,
        transport_profile=inputs.transport_profile,
        render_profile=inputs.render_profile,
        render_profile_source_evidence=inputs.render_profile_source_evidence,
        source_defects=source_defects_for(source_ref),
    )
    data = tomllib.loads((destination / "0003-record-m347-inmueble.toml").read_text(encoding="utf-8"))
    record = ExportRecordDefinition.model_validate_json(
        json.dumps(data["revisions"][revision]["export_layouts"][0]["records"][0])
    )
    assert record.required is False
    assert record.repeat == "binding_rows"
    assert dict(record.row_field_casilla_ids) == INMUEBLE_ROW_FIELDS
    assert record_render_rows(record, {}, {}) == ()
    assert require_two_lease_rows(record) == (1, 2)

    singleton = record.model_copy(update={"required": True, "repeat": None, "row_field_casilla_ids": {}})
    with pytest.raises(ValueError, match="loses source rows: \\(None,\\)"):
        require_two_lease_rows(singleton)


@pytest.mark.parametrize("revision,epoch,source_ref,source_sha256", EPOCHS)
def test_changed_official_source_pin_refuses_join(
    authority,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    revision: str,
    epoch: str,
    source_ref: str,
    source_sha256: str,
) -> None:
    """A coherent but wrong map digest cannot borrow the official design."""
    authored = tmp_path / "authored"
    shutil.copytree(AUTHORED_ROOT / "mappings/modelo_347" / epoch, authored / "mappings/modelo_347" / epoch)
    shutil.copytree(
        AUTHORED_ROOT / "render_profiles/modelo_347" / epoch, authored / "render_profiles/modelo_347" / epoch
    )
    for fragment in (authored / "mappings/modelo_347" / epoch).glob("*.toml"):
        content = fragment.read_text(encoding="utf-8")
        assert source_sha256 in content
        fragment.write_text(content.replace(source_sha256, "0" * 64), encoding="utf-8")
    monkeypatch.setattr(render_check, "_AUTHORED_ROOT", authored)
    with pytest.raises(RegistryValidationError, match=r"source SHA-256|source.*digest|SHA-256.*source"):
        revision_render_inputs(authority, modelo="347", revision=revision, source_ref=source_ref)
