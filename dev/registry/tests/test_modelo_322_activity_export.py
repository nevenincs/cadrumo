"""A zero-result election must not manufacture Modelo 322's activity declaration."""

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.application.filing.record_field_renderer import render_record
from cadrumo.application.filing.record_types import RecordRenderRow
from cadrumo.core.casilla_id import CasillaId
from cadrumo.core.period import Period
from cadrumo.core.result_disposition import ResultDisposition
from cadrumo.domain.calculations.registry.governed_fact_scope import validating_governed_facts
from cadrumo.domain.calculations.registry.schema_references import RegistrySnapshotRef
from cadrumo.domain.filing.schema import ModeloDraft, compute_modelo_draft_id, registry_schema_version
from cadrumo.domain.submission.models import ModeloDraftStatus

from ..compiler.authority import compiled_bundled_authority
from ..compiler.loader import load_modelo_directory
from ..workbook_demo import DEMO_CASES, demonstration_producer

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]


@pytest.fixture(scope="module", autouse=True)
def governed_facts():
    with validating_governed_facts(compiled_bundled_authority()):
        yield


@pytest.mark.parametrize(
    "revision_id,year,record_id,field_id,offset",
    [
        ("2008-2022", 2022, "m322-page-02", "m322-2022.page-02.f020", 270),
        ("2023", 2023, "m322-page-02", "m322-2023.page-02.f019", 253),
        ("2024-2025", 2025, "m322-page-02", "m322-2024.pagina02.f019", 253),
        ("2026-y-siguientes", 2026, "modelo-322-page-02", "modelo-322-page-02-338", 338),
    ],
)
@pytest.mark.parametrize("marker,expected", [(None, " "), ("", " "), ("X", "X")])
@pytest.mark.parametrize("disposition", [ResultDisposition.NEGATIVA, ResultDisposition.INGRESO])
def test_activity_byte_reads_only_the_explicit_fact(
    marker, expected, disposition, revision_id, year, record_id, field_id, offset
):
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/322")).revisions[revision_id]
    record = next(r for layout in revision.export_layouts for r in layout.records if r.id == record_id)
    field = next(f for f in record.fields if f.id == field_id)
    assert field.kind == "casilla" and field.casilla_id == "decl.sin-actividad"
    assert field.computed_key is None
    producer = demonstration_producer(next(c for c in DEMO_CASES if c.modelo == "322"))
    assert producer is not None
    producer = producer.model_copy(
        update={"elections": producer.elections.model_copy(update={"result_disposition": disposition})}
    )
    period = Period.from_year_and_code(year, "12")
    ref = RegistrySnapshotRef(modelo="322", revision_id=str(revision.id), modelo_year=year, period="12")
    draft = ModeloDraft(
        draft_id=compute_modelo_draft_id(
            modelo="322", period=period, profile_tax_id="B12345674", snapshot_ref=ref, values=()
        ),
        modelo="322",
        period=period,
        profile_tax_id="B12345674",
        subject_tax_id="B12345674",
        snapshot_ref=ref,
        status=ModeloDraftStatus.BORRADOR,
        values=(),
        created_at=datetime(year, 12, 31, tzinfo=UTC),
        updated_at=datetime(year, 12, 31, tzinfo=UTC),
        schema_version=registry_schema_version(modelo="322", revision_id=str(revision.id)),
    )
    # Equal output and deductible VAT is still activity, irrespective of the
    # zero settlement or the result-disposition election. Isolate the exact
    # enrolled field: this is a wire-byte regression, not a full filing test.
    values: dict[CasillaId, object] = {
        "38": Decimal("210"),
        "62": Decimal("210"),
        "70": Decimal("0"),
    }
    if marker is not None:
        values["decl.sin-actividad"] = marker
    payload = render_record(
        record.model_copy(update={"fields": (field,)}),
        draft=draft,
        producer_values={},
        producer_snapshot=producer,
        casilla_values=values,
        binding_values={},
        row=RecordRenderRow(None, frozenset()),
        render_context=None,
        projection_values={},
    )
    assert len(payload) == offset
    assert payload[offset - 1] == expected
