"""Modelo 349 calculation display and export parity for operator rows."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.external_constants import OutputLanguage
from ....core.modelo import Modelo
from ....core.modelo_work_progress_state import ModeloWorkProgressState
from ....core.period import Period
from ....domain.calculations.export_field_kind import CasillaFieldKind
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.bindings import resolve_available_bound_inputs_by_casilla_id
from ....domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.schema_form_layouts import FormRepeatingGroupBlock
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....domain.filing.schema import (
    ModeloCasillaProvenance,
    ModeloDraft,
    ModeloValue,
    ModeloValueKind,
    compute_modelo_draft_id,
)
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.row_models import Modelo349OperadorRow
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ....domain.submission.models import ModeloDraftStatus
from ...filing.draft_construction import filing_binding_values
from .._calculation_helpers import build_typed_observations
from .._calculation_modelo_adjustments import drop_row_field_template_outputs
from ..revision_replay_inputs import revision_detail_record_binding_inputs
from ..work_form import build_modelo_work_form
from ..work_form_models import ModeloFormCasillaAddressV1, ModeloFormRepeatingBlock
from ..work_form_records import saved_form_records
from ..work_review import ModeloWorkProgress, ModeloWorkReview, build_modelo_work_review_casillas

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CLOCK = datetime(2026, 6, 29, 12, 0, tzinfo=UTC)
_BUCKET_ID = "9c4acfdc-abb7-4206-8755-1d8c027b6114"  # was 'm349-display-export-parity'
_PROFILE_TAX_ID = "12345678Z"
_DECL_NUMERO_OPERADORES: CasillaId = validated_casilla_id(
    "decl.numero-operadores",
    surface="test_m349_calculation_display_export",
)
_DECL_IMPORTE_OPERACIONES: CasillaId = validated_casilla_id(
    "decl.importe-operaciones",
    surface="test_m349_calculation_display_export",
)
_DECL_NUMERO_RECTIFICACIONES: CasillaId = validated_casilla_id(
    "decl.numero-rectificaciones",
    surface="test_m349_calculation_display_export",
)
_DECL_IMPORTE_RECTIFICACIONES: CasillaId = validated_casilla_id(
    "decl.importe-rectificaciones",
    surface="test_m349_calculation_display_export",
)


def _m349_snapshot(*, period: str) -> RegistrySnapshot:
    return published_snapshot(Modelo("349").value, filing_year=2026, period=period)


def _work_unit(*, period: str, snapshot: RegistrySnapshot) -> WorkUnit:
    filing_period = Period.from_year_and_code(2026, period)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo="349",
            filing_year=2026,
            period=filing_period,
            revision_id=snapshot.revision.id,
        ),
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode("349"),
        filing_year=2026,
        period=filing_period,
        revision_id=snapshot.revision.id,
        name=f"349-2026-{period}",
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )


def _calculated_revision(
    *,
    period: str,
    country: str,
    iva_id: str,
    name: str,
    clave: str,
    amount: Decimal,
) -> tuple[RegistrySnapshot, WorkUnit, CalculationRevision]:
    snapshot = _m349_snapshot(period=period)
    work_unit = _work_unit(period=period, snapshot=snapshot)
    row = Modelo349OperadorRow.model_validate(
        {
            "codigo_pais": country,
            "nif_comunitario": iva_id,
            "razon_social": name,
            "clave_operacion": clave,
            "importe": amount,
        }
    )
    binding_values = {
        "iva-349-declarante-numero-operadores": Decimal("1"),
        "iva-349-declarante-importe-operaciones": amount,
        "iva-349-declarante-numero-rectificaciones": Decimal("0"),
        "iva-349-declarante-importe-rectificaciones": Decimal("0"),
    }
    inputs = resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values)
    engine_result = calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        date_context={"filing_period": work_unit.period.end_date},
        binding_values=binding_values,
    )
    raw_casilla_values = dict(engine_result.values)
    raw_observations = build_typed_observations(engine_result=engine_result, snapshot=snapshot)

    input_values = {casilla_id: str(value) for casilla_id, value in inputs.items()}
    binding_overrides = {binding_id: str(value) for binding_id, value in binding_values.items()}
    detail_rows = (row,)
    casilla_values, observations = drop_row_field_template_outputs(
        revision=snapshot.revision,
        casilla_values=raw_casilla_values,
        observations=raw_observations,
    )
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id=input_values,
        binding_overrides=binding_overrides,
        casilla_values=casilla_values,
        detail_rows=detail_rows,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    return (
        snapshot,
        work_unit,
        CalculationRevision(
            calculation_revision_id=revision_id,
            work_unit_id=work_unit.work_unit_id,
            registry_snapshot_ref=snapshot.snapshot_ref,
            state=CalculationRevisionState.BORRADOR,
            input_values_by_casilla_id=input_values,
            binding_overrides=binding_overrides,
            casilla_values=casilla_values,
            observations=observations,
            detail_rows=detail_rows,
            created_at=_CLOCK,
            updated_at=_CLOCK,
            filing_instance_evidence=None,
            source_provenance=(),
        ),
    )


def _approved_draft(
    *,
    snapshot: RegistrySnapshot,
    work_unit: WorkUnit,
    revision: CalculationRevision,
) -> ModeloDraft:
    values = tuple(
        ModeloValue(
            casilla_id=casilla_id,
            value=value,
            kind=ModeloValueKind.INHERITED,
            source="registry calculation",
        )
        for casilla_id, value in sorted(revision.casilla_values.items())
    )
    replay_inputs = revision_detail_record_binding_inputs(
        revision=revision, modelo=str(work_unit.modelo), binding_record="operador"
    )
    assert replay_inputs is not None
    bindings_by_id = {binding.id: binding for binding in snapshot.revision.bindings}
    binding_values = tuple(filing_binding_values(replay_inputs, bindings_by_id))
    casilla_provenance = tuple(
        ModeloCasillaProvenance(
            casilla_id=casilla.id,
            formula_id=casilla.formula,
            legal_refs=tuple(casilla.legal_refs),
            source_refs=tuple(casilla.source_refs),
        )
        for casilla in sorted(snapshot.revision.casillas, key=lambda item: item.id)
    )
    schema_version = f"registry:{snapshot.modelo.id}:{snapshot.revision.id}"
    snapshot_ref = snapshot.snapshot_ref
    draft_id = compute_modelo_draft_id(
        modelo="349",
        period=work_unit.period,
        profile_tax_id=_PROFILE_TAX_ID,
        snapshot_ref=snapshot_ref,
        values=values,
        binding_values=binding_values,
    )
    return ModeloDraft(
        draft_id=draft_id,
        modelo="349",
        period=work_unit.period,
        profile_tax_id=_PROFILE_TAX_ID,
        subject_tax_id=_PROFILE_TAX_ID,
        snapshot_ref=snapshot_ref,
        status=ModeloDraftStatus.APROBADO,
        values=values,
        binding_values=binding_values,
        casilla_provenance=casilla_provenance,
        created_at=_CLOCK,
        updated_at=_CLOCK,
        schema_version=schema_version,
        approved_at=_CLOCK,
        approved_by="operator",
    )


def _record_calculation() -> tuple[RegistrySnapshot, WorkUnit, CalculationRevision]:
    return _calculated_revision(
        period="1T", country="DE", iva_id="DE123456789", name="EU Trader", clave="E", amount=Decimal("0")
    )


def _operator_block(operation: PinnedAuthorityOperation) -> FormRepeatingGroupBlock:
    layout = operation.form_layout("349", "2020-y-siguientes")
    assert layout is not None
    return next(
        block
        for page in layout.pages
        for section in page.sections
        for block in section.blocks
        if isinstance(block, FormRepeatingGroupBlock) and block.export_record_id == "modelo-349-operador"
    )


def _records(
    snapshot: RegistrySnapshot, revision: CalculationRevision | None, block: FormRepeatingGroupBlock
) -> tuple[bool, tuple[tuple[object, ...], ...]]:
    known, rows = saved_form_records(
        snapshot=snapshot,
        revision=revision,
        block=block,
        column_casillas=tuple(
            None if column.casilla_id is None else str(column.casilla_id) for column in block.columns
        ),
    )
    return known, tuple((row.index, *row.values) for row in rows)


def _record_values(block: FormRepeatingGroupBlock, row: tuple[object, ...]) -> dict[str, object]:
    """Address saved cells by the registry's column identity, preserving row order."""
    return {
        str(column.casilla_id): value
        for column, value in zip(block.columns, row[1:], strict=True)
        if column.casilla_id is not None
    }


def test_saved_detail_rows_populate_the_real_form_and_make_the_optional_page_applicable(
    operation: PinnedAuthorityOperation,
) -> None:
    snapshot, unit, revision = _record_calculation()
    review = ModeloWorkReview(
        bucket_id=unit.bucket_id,
        modelo=unit.modelo,
        filing_year=unit.filing_year,
        period=unit.period,
        registry_revision_id=unit.revision_id,
        work_unit_id=unit.work_unit_id,
        calculation_revision_id=revision.calculation_revision_id,
        lifecycle_state=revision.state,
        verification_outcome=None,
        progress=ModeloWorkProgress(state=ModeloWorkProgressState.UNDEFINED),
        casillas=build_modelo_work_review_casillas(snapshot=snapshot, revision=revision, operation=operation),
        findings=(),
        blockers=(),
    )
    form = build_modelo_work_form(
        review=review,
        snapshot=snapshot,
        revision=revision,
        layout=operation.form_layout("349", "2020-y-siguientes"),
        permitted_surface=None,
        entered_casilla_ids=None,
        overridden_binding_ids=None,
        language=OutputLanguage.EN,
    )
    page = next(
        page
        for page in form.pages
        if any(
            isinstance(block, ModeloFormRepeatingBlock) and block.id == "modelo-349-operador"
            for section in page.sections
            for block in section.blocks
        )
    )
    block = next(
        block for section in page.sections for block in section.blocks if isinstance(block, ModeloFormRepeatingBlock)
    )
    assert page.applies is True
    assert block.rows_known and len(block.rows) == 1
    assert block.column_casilla_ids == tuple(
        None if column.casilla_id is None else str(column.casilla_id) for column in _operator_block(operation).columns
    )
    assert dict(zip(block.column_casilla_ids, block.rows[0].values, strict=True)) == {
        "sustituto.nif": None,
        "sustituto.apellidos-razon-social": None,
        "op.codigo-pais": "DE",
        "op.nif-comunitario": "123456789",
        "op.apellidos-razon-social": "EU Trader",
        "op.clave-operacion": "E",
        "op.base-imponible": Decimal("0"),
    }
    assert not any(
        isinstance(field.address, ModeloFormCasillaAddressV1)
        and str(field.address.casilla_id) in {"op.codigo-pais", "op.base-imponible"}
        for field in form.fields()
    )


def test_record_projection_uses_filing_replay_precedence_and_normalization(operation: PinnedAuthorityOperation) -> None:
    snapshot, unit, revision = _record_calculation()
    revision = revision.model_copy(
        update={
            "row_binding_values": {
                "iva-349-operador-row-nif": {"7": "DIFFERENT"},
                "iva-349-operador-row-base": {"7": "999"},
            },
            "row_casilla_values": {("op.base-imponible", 7): Decimal("999")},
        }
    )
    block = _operator_block(operation)
    known, rows = _records(snapshot, revision, block)
    assert known and tuple(row[0] for row in rows) == (1,)
    assert _record_values(block, rows[0]) == {
        "sustituto.nif": None,
        "sustituto.apellidos-razon-social": None,
        "op.codigo-pais": "DE",
        "op.nif-comunitario": "123456789",
        "op.apellidos-razon-social": "EU Trader",
        "op.clave-operacion": "E",
        "op.base-imponible": Decimal("0"),
    }
    replay = revision_detail_record_binding_inputs(
        revision=revision, modelo=str(unit.modelo), binding_record="operador"
    )
    assert replay is not None and replay["iva-349-operador-row-nif"] == {"1": "123456789"}


def test_a_supported_explicit_empty_family_is_known_but_an_omitted_legacy_family_is_unknown(
    operation: PinnedAuthorityOperation,
) -> None:
    snapshot, _, revision = _record_calculation()
    block = _operator_block(operation)
    empty = revision.model_copy(update={"detail_rows": ()})
    assert _records(snapshot, empty, block) == (True, ())
    legacy = CalculationRevision.model_construct(
        _fields_set=empty.model_fields_set - {"detail_rows"}, **empty.model_dump()
    )
    assert _records(snapshot, legacy, block) == (False, ())
    assert _records(snapshot, None, block) == (False, ())
    assert _records(snapshot, empty, block.model_copy(update={"export_record_id": "unknown-record"})) == (False, ())


def test_generic_saved_binding_rows_preserve_sparse_indices_zero_and_text(operation: PinnedAuthorityOperation) -> None:
    snapshot, _, revision = _record_calculation()
    layouts = tuple(
        layout.model_copy(
            update={
                "records": tuple(
                    record.model_copy(update={"binding_record": "other-owner"})
                    if record.id == "modelo-349-operador"
                    else record
                    for record in layout.records
                )
            }
        )
        for layout in snapshot.revision.export_layouts
    )
    snapshot = snapshot.model_copy(
        update={"revision": snapshot.revision.model_copy(update={"export_layouts": layouts})}
    )
    revision = revision.model_copy(
        update={
            "detail_rows": (),
            "row_binding_values": {
                "iva-349-operador-row-apellidos": {"3": "First", "9": "Second"},
                "iva-349-operador-row-base": {"3": "0", "9": "42.50"},
            },
        }
    )
    block = _operator_block(operation)
    known, rows = _records(snapshot, revision, block)
    assert known and tuple(row[0] for row in rows) == (3, 9)
    empty = {
        "sustituto.nif": None,
        "sustituto.apellidos-razon-social": None,
        "op.codigo-pais": None,
        "op.nif-comunitario": None,
        "op.clave-operacion": None,
    }
    assert tuple(_record_values(block, row) for row in rows) == (
        {**empty, "op.apellidos-razon-social": "First", "op.base-imponible": Decimal("0")},
        {**empty, "op.apellidos-razon-social": "Second", "op.base-imponible": Decimal("42.50")},
    )
    assert _records(snapshot, revision.model_copy(update={"row_binding_values": {}}), _operator_block(operation)) == (
        False,
        (),
    )


def test_a_detail_owner_does_not_claim_an_unrelated_record_or_modelo(operation: PinnedAuthorityOperation) -> None:
    _, _, revision = _record_calculation()
    assert revision_detail_record_binding_inputs(revision=revision, modelo="130", binding_record="operador") is None
    assert revision_detail_record_binding_inputs(revision=revision, modelo="349", binding_record="unknown") is None
    assert revision_detail_record_binding_inputs(revision=revision, modelo="349", binding_record="rectificacion") == {}


def test_record_wide_text_does_not_inherit_a_numeric_placeholder(operation: PinnedAuthorityOperation) -> None:
    snapshot, _, revision = _record_calculation()
    revision = revision.model_copy(
        update={"casilla_values": {**revision.casilla_values, "sustituto.nif": Decimal("0")}}
    )
    block = _operator_block(operation)
    _, rows = _records(snapshot, revision, block)
    assert _record_values(block, rows[0])["sustituto.nif"] is None
    revision = revision.model_copy(update={"input_values_by_casilla_id": {"sustituto.nif": "0"}})
    _, rows = _records(snapshot, revision, block)
    assert _record_values(block, rows[0])["sustituto.nif"] == "0"


@pytest.mark.parametrize("raw", ("not-a-number", "NaN", "Infinity"))
def test_a_malformed_numeric_row_preserves_its_index_and_unknown_cell(
    operation: PinnedAuthorityOperation,
    raw: str,
) -> None:
    snapshot, _, revision = _record_calculation()
    layouts = tuple(
        layout.model_copy(
            update={
                "records": tuple(
                    record.model_copy(update={"binding_record": "other-owner"})
                    if record.id == "modelo-349-operador"
                    else record
                    for record in layout.records
                )
            }
        )
        for layout in snapshot.revision.export_layouts
    )
    snapshot = snapshot.model_copy(
        update={"revision": snapshot.revision.model_copy(update={"export_layouts": layouts})}
    )
    revision = revision.model_copy(
        update={
            "detail_rows": (),
            "row_binding_values": {
                "iva-349-operador-row-base": {"8": raw},
            },
        }
    )
    known, rows = _records(snapshot, revision, _operator_block(operation))
    assert known and rows == ((8, None, None, None, None, None, None, None),)


def test_saved_per_row_casillas_are_not_overwritten_by_a_record_wide_scalar(
    operation: PinnedAuthorityOperation,
) -> None:
    snapshot, _, revision = _record_calculation()
    layout = snapshot.revision.export_layouts[0]
    record = next(record for record in layout.records if record.id == "modelo-349-operador")
    amount = next(field for field in record.fields if field.binding == "iva-349-operador-row-base")
    record = record.model_copy(
        update={
            "binding_record": None,
            "repeat": None,
            "row_field_casilla_ids": {},
            "fields": (
                amount.model_copy(
                    update={"kind": CasillaFieldKind.CASILLA, "binding": None, "casilla_id": "op.base-imponible"}
                ),
            ),
        }
    )
    layout = layout.model_copy(update={"records": (record,)})
    snapshot = snapshot.model_copy(
        update={"revision": snapshot.revision.model_copy(update={"export_layouts": (layout,)})}
    )
    revision = revision.model_copy(
        update={
            "row_casilla_values": {("op.base-imponible", 2): Decimal("0"), ("op.base-imponible", 5): Decimal("19.25")},
            "casilla_values": {"op.base-imponible": Decimal("999")},
            "detail_rows": (),
        }
    )
    block = _operator_block(operation)
    known, rows = _records(snapshot, revision, block)
    assert known and [(row[0], _record_values(block, row)["op.base-imponible"]) for row in rows] == [
        (2, Decimal("0")),
        (5, Decimal("19.25")),
    ]


def test_saved_projection_casillas_remain_visible_even_when_the_projection_owner_is_unknown(
    operation: PinnedAuthorityOperation,
) -> None:
    _, _, revision = _record_calculation()
    snapshot = operation.snapshot("303", filing_year=2026, period="1T")
    record = next(
        record
        for layout in snapshot.revision.export_layouts
        for record in layout.records
        if record.repeat == "projection_rows" and any(field.endpoint_casilla_id for field in record.fields)
    )
    target = next(field.endpoint_casilla_id for field in record.fields if field.endpoint_casilla_id is not None)
    block = _operator_block(operation).model_copy(update={"export_record_id": record.id})
    revision = revision.model_copy(update={"row_casilla_values": {(target, 4): Decimal("17.50")}, "detail_rows": ()})
    known, rows = saved_form_records(snapshot=snapshot, revision=revision, block=block, column_casillas=(str(target),))
    assert known and [(row.index, row.values) for row in rows] == [(4, (Decimal("17.50"),))]
    assert saved_form_records(
        snapshot=snapshot,
        revision=revision.model_copy(update={"row_casilla_values": {}}),
        block=block,
        column_casillas=(str(target),),
    ) == (False, ())
