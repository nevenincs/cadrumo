"""M280's source-listed negative imputation depends on extinction key 2."""

from __future__ import annotations

import pytest

from cadrumo.application.filing.m280_context_validation import require_m280_negative_imputation_context
from cadrumo.application.filing.producer_snapshot import FilingProducerSnapshot
from cadrumo.application.filing.record_field_renderer import render_record
from cadrumo.application.filing.record_types import RecordRenderRow
from cadrumo.core.modelo import Modelo
from cadrumo.core.period import Period
from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.fixed_width_codec import (
    ExportJustification,
    ExportPadding,
    render_fixed_width_export_field,
    render_fixed_width_export_record_body,
)
from cadrumo.domain.calculations.registry.schema_exports import ExportFieldDefinition, ExportRecordDefinition
from cadrumo.domain.calculations.registry.tests.published_authority import published_revision
from cadrumo.domain.filing.errors import FilingExportValidationError
from cadrumo.domain.filing.schema import ModeloDraft

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]
_SOURCE_DIGESTS = {"aeat-dr-280-2022": "45cab8f0880dfc4094d6cc8905ae37efba0c10a568d49e8648e1c9a20b2a5701"}


_GUARDED_IDS = (
    "modelo-280-t2-rendimientos-negativos-imputables-sign",
    "modelo-280-t2-rendimientos-negativos-imputables-component-177",
    "modelo-280-t2-rendimientos-negativos-imputables-component-185",
    "modelo-280-t2-extincion-plan",
)


def _record() -> ExportRecordDefinition:
    """The published declarado record exactly as the hydrated layout declares it."""
    layout = published_revision("280", "2025").export_layouts[0]
    return next(record for record in layout.records if record.id == "modelo-280-declarado")


def _wire(*, key: str, sign: str, magnitude: str) -> str:
    wire = list(" " * 500)
    wire[136], wire[175], wire[176:186] = key, sign, list(magnitude)
    return "".join(wire)


def _renderable_record() -> ExportRecordDefinition:
    """Keep the exact guarded source fields while supplying their wire shapes."""
    source = _record()
    sign, integer, fraction, key = (next(field for field in source.fields if field.id == i) for i in _GUARDED_IDS)
    components = (
        sign.model_copy(
            update={
                "data_type": "text",
                "required": False,
                "padding": ExportPadding.NONE,
                "justification": ExportJustification.NONE,
                "signed": False,
            }
        ),
        *(
            field.model_copy(
                update={
                    "data_type": "integer",
                    "required": False,
                    "padding": ExportPadding.LEFT_ZERO,
                    "justification": ExportJustification.RIGHT,
                    "signed": False,
                }
            )
            for field in (integer, fraction)
        ),
        key,
        ExportFieldDefinition.model_construct(id="record-tail", offset=187, length=314, kind=CasillaFieldKind.FILLER),
    )
    return source.model_copy(update={"fields": components, "encoding": "ascii"})


def _render_application_record(
    record: ExportRecordDefinition,
    *,
    key: str,
    amount: object,
    source_digests: dict[str, str] = _SOURCE_DIGESTS,
) -> str:
    return render_record(
        record,
        draft=ModeloDraft.model_construct(modelo=Modelo("280"), period=Period.from_year_and_code(2022, "0A")),
        producer_values={},
        producer_snapshot=FilingProducerSnapshot.model_construct(),
        casilla_values={"extincion-plan": key, "rendimientos-negativos-imputables": amount},
        binding_values={},
        row=RecordRenderRow(row_index=None, active_binding_ids=frozenset()),
        render_context=None,
        projection_values={},
        source_digests=source_digests,
    )


def test_application_renderer_preserves_present_zero_and_missing_key_two_distinction() -> None:
    record = _renderable_record()
    for key, amount, expected in (
        ("1", None, "00000000000"),
        ("1", "0.00", "00000000000"),
        ("2", "-1.23", "N0000000123"),
        ("2", "0.00", "N0000000000"),
    ):
        wire = _render_application_record(record, key=key, amount=amount)
        assert len(wire) == 500
        assert wire[175:186] == expected
        require_m280_negative_imputation_context(record, wire, source_digests=_SOURCE_DIGESTS)

    with pytest.raises(FilingExportValidationError, match="requires key 2"):
        _render_application_record(record, key="2", amount=None)


def test_application_renderer_treats_empty_optional_amount_as_absent() -> None:
    record = _renderable_record()
    ordinary_wire = _render_application_record(record, key="1", amount="")
    assert ordinary_wire[175:186] == "00000000000"
    require_m280_negative_imputation_context(record, ordinary_wire, source_digests=_SOURCE_DIGESTS)

    with pytest.raises(FilingExportValidationError, match="requires key 2"):
        _render_application_record(record, key="2", amount="")


def test_application_zero_projection_refuses_changed_source_and_geometry() -> None:
    record = _renderable_record()
    with pytest.raises(FilingExportValidationError, match="reviewed source"):
        _render_application_record(record, key="2", amount="0", source_digests={"aeat-dr-280-2022": "0" * 64})
    changed = record.model_copy(
        update={"fields": (record.fields[0].model_copy(update={"offset": 175}), *record.fields[1:])}
    )
    with pytest.raises(FilingExportValidationError, match="reviewed source"):
        _render_application_record(changed, key="2", amount="0")


def test_renderer_and_guard_accept_absent_ordinary_row_and_negative_key_two() -> None:
    record = _renderable_record()
    for key, amount, expected in (
        ("1", None, "00000000000"),
        ("2", "-1.23", "N0000000123"),
    ):
        wire = render_fixed_width_export_record_body(
            record,
            field_values={"extincion-plan": key, "rendimientos-negativos-imputables": amount},
        ).decode("ascii")
        assert len(wire) == 500
        assert wire[136] == key
        assert wire[175:186] == expected
        require_m280_negative_imputation_context(record, wire, source_digests=_SOURCE_DIGESTS)

    missing_key_two = render_fixed_width_export_record_body(
        record,
        field_values={"extincion-plan": "2", "rendimientos-negativos-imputables": None},
    ).decode("ascii")
    with pytest.raises(FilingExportValidationError, match="requires key 2"):
        require_m280_negative_imputation_context(record, missing_key_two, source_digests=_SOURCE_DIGESTS)
    with pytest.raises(RegistryValidationError, match="required export field"):
        render_fixed_width_export_field(record.fields[0].model_copy(update={"required": True}), None)


def test_exact_key_two_negative_imputation_and_other_key_zero_fill() -> None:
    record = _record()
    require_m280_negative_imputation_context(
        record, _wire(key="2", sign="N", magnitude="0000000001"), source_digests=_SOURCE_DIGESTS
    )
    require_m280_negative_imputation_context(
        record, _wire(key="1", sign="0", magnitude="0000000000"), source_digests=_SOURCE_DIGESTS
    )
    require_m280_negative_imputation_context(
        record, _wire(key="2", sign="N", magnitude="0000000000"), source_digests=_SOURCE_DIGESTS
    )
    for wire in (
        _wire(key="1", sign="N", magnitude="0000000001"),
        _wire(key="2", sign="0", magnitude="0000000000"),
        _wire(key="2", sign="N", magnitude="00000000A0"),
    ):
        with pytest.raises(FilingExportValidationError, match="requires key 2"):
            require_m280_negative_imputation_context(record, wire, source_digests=_SOURCE_DIGESTS)


def test_negative_imputation_refuses_changed_source_and_component() -> None:
    record = _record()
    wire = _wire(key="2", sign="N", magnitude="0000000001")
    with pytest.raises(FilingExportValidationError, match="reviewed source"):
        require_m280_negative_imputation_context(record, wire, source_digests={"aeat-dr-280-2022": "0" * 64})
    changed = record.model_copy(
        update={
            "fields": tuple(
                field.model_copy(update={"source_refs": ("wrong",)}) if field.id == _GUARDED_IDS[1] else field
                for field in record.fields
            )
        }
    )
    with pytest.raises(FilingExportValidationError, match="reviewed source"):
        require_m280_negative_imputation_context(changed, wire, source_digests=_SOURCE_DIGESTS)


def test_guard_reads_the_key_and_amount_where_the_layout_declares_them() -> None:
    record = _renderable_record()
    key_field = next(field for field in record.fields if field.id == "modelo-280-t2-extincion-plan")
    moved = record.model_copy(
        update={
            "fields": tuple(
                field.model_copy(update={"offset": 300}) if field is key_field else field for field in record.fields
            )
        }
    )
    wire = list(_wire(key="1", sign="0", magnitude="0" * 10))
    wire[299] = "2"
    with pytest.raises(FilingExportValidationError, match="requires key 2"):
        require_m280_negative_imputation_context(moved, "".join(wire), source_digests=_SOURCE_DIGESTS)
    wire[175] = "N"
    require_m280_negative_imputation_context(moved, "".join(wire), source_digests=_SOURCE_DIGESTS)


def test_guard_refuses_a_wire_that_is_not_the_declared_record_width() -> None:
    record = _renderable_record()
    with pytest.raises(FilingExportValidationError, match="record is incomplete"):
        require_m280_negative_imputation_context(
            record, _wire(key="1", sign="0", magnitude="0" * 10)[:-1], source_digests=_SOURCE_DIGESTS
        )
