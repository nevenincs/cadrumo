"""Real byte and verification proofs for registry-declared export value policies."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....core import (
    M303Exonerado390ActivityField,
    M303Exonerado390ActivityProjectionRef,
    Period,
)
from ....domain.calculations.registry import (
    ExportFieldDefinition,
    ExportLayoutDefinition,
    ExportRecordDefinition,
    ExportValuePolicy,
    RegistrySnapshotRef,
)
from ....domain.filing import (
    FilingExportValidationError,
    ModeloDraft,
    ModeloValue,
    ModeloValueKind,
    registry_schema_version,
)
from ....domain.submission import ModeloDraftStatus
from .._export import _mismatched_casilla_ids, _RecordRenderRow, _render_record, render_layout
from ..runtime import RegistrySchemaAccessor
from ._export_support import _typed_producer_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LEGAL_REFS = ("ley-27-2014:art-40",)
_SOURCE_REFS = ("aeat-dr-200-2025",)


def _field(
    *,
    field_id: str,
    casilla_id: str,
    offset: int,
    policy: ExportValuePolicy,
) -> ExportFieldDefinition:
    return ExportFieldDefinition(
        id=field_id,
        offset=offset,
        length=1 if policy is ExportValuePolicy.SELECTED_1_UNSELECTED_0 else 2,
        kind="casilla",
        casilla_id=casilla_id,
        data_type="integer",
        required=False,
        padding="left_zero",
        justification="right",
        signed=False,
        value_policy=policy,
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
    )


def _record(record_id: str, field: ExportFieldDefinition, *, order: int) -> ExportRecordDefinition:
    return ExportRecordDefinition(
        id=record_id,
        record_type=str(order),
        order=order,
        encoding="ascii",
        line_ending="none",
        fields=(field,),
    )


def _draft(*, checkbox: bool | None, year: int | str):
    period = Period.from_year_and_code(2026, "1T")
    stamped = datetime(2026, 8, 10, tzinfo=UTC)
    return ModeloDraft(
        draft_id="policy-proof",
        modelo="200",
        period=period,
        profile_tax_id="12345678Z",
        subject_tax_id="12345678Z",
        snapshot_ref=RegistrySnapshotRef(
            modelo="200",
            revision_id="2025",
            modelo_year=2026,
            period="1T",
        ),
        status=ModeloDraftStatus.APROBADO,
        values=(
            *(
                (ModeloValue(casilla_id="01", value=checkbox, kind=ModeloValueKind.LITERAL, source="policy proof"),)
                if checkbox is not None
                else ()
            ),
            ModeloValue(casilla_id="02", value=year, kind=ModeloValueKind.LITERAL, source="policy proof"),
        ),
        created_at=stamped,
        updated_at=stamped,
        schema_version=registry_schema_version(modelo="200", revision_id="2025"),
    )


def _two_record_layout() -> ExportLayoutDefinition:
    # Repeating the field id is deliberate: field identity is record-scoped.
    return ExportLayoutDefinition(
        id="policy-layout",
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
        records=(
            _record(
                "checkbox-record",
                _field(
                    field_id="shared-value",
                    casilla_id="01",
                    offset=1,
                    policy=ExportValuePolicy.SELECTED_1_UNSELECTED_0,
                ),
                order=0,
            ),
            _record(
                "year-record",
                _field(
                    field_id="shared-value",
                    casilla_id="02",
                    offset=1,
                    policy=ExportValuePolicy.FOUR_DIGIT_YEAR_FINAL_TWO_DIGITS,
                ),
                order=1,
            ),
        ),
    )


def _render_one(record: ExportRecordDefinition, value: object) -> str:
    field = record.fields[0]
    assert field.casilla_id is not None
    return _render_record(
        record,
        draft=_draft(checkbox=False, year=2026),
        producer_values={},
        producer_snapshot=_typed_producer_snapshot(),
        projection_values={},
        casilla_values={field.casilla_id: value},
        binding_values={},
        row=_RecordRenderRow(row_index=None, active_binding_ids=frozenset()),
    )


@pytest.mark.parametrize(
    ("checkbox", "year", "expected"),
    [(False, 2026, b"026"), (True, "2026", b"126"), (None, 2000, b"000")],
)
def test_filing_writer_emits_exact_policy_bytes(
    checkbox: bool | None,
    year: int | str,
    expected: bytes,
) -> None:
    assert (
        render_layout(
            _two_record_layout(),
            draft=_draft(checkbox=checkbox, year=year),
            producer_snapshot=_typed_producer_snapshot(),
        )
        == expected
    )


def test_filing_writer_dispatches_only_the_exact_typed_projection_reference() -> None:
    ref = M303Exonerado390ActivityProjectionRef(
        slot=1,
        field=M303Exonerado390ActivityField.ACTIVITY_CODE,
    )
    field = ExportFieldDefinition(
        id="typed-projection",
        offset=1,
        length=3,
        kind="projection",
        projection_ref=ref,
        data_type="text",
        required=True,
        padding="right_space",
        justification="left",
        signed=False,
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
    )
    layout = ExportLayoutDefinition(
        id="typed-projection-layout",
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
        records=(_record("typed-projection-record", field, order=0),),
    )

    assert (
        render_layout(
            layout,
            draft=_draft(checkbox=False, year=2026),
            producer_snapshot=_typed_producer_snapshot(),
            projection_values={(ref.model_dump_json(), None): "A01"},
        )
        == b"A01"
    )

    with pytest.raises(FilingExportValidationError, match="no exact typed projection value"):
        render_layout(
            layout,
            draft=_draft(checkbox=False, year=2026),
            producer_snapshot=_typed_producer_snapshot(),
        )


def test_projection_row_occurrences_are_selected_only_by_resolved_typed_values() -> None:
    ref = M303Exonerado390ActivityProjectionRef(
        slot=1,
        field=M303Exonerado390ActivityField.ACTIVITY_CODE,
    )
    field = ExportFieldDefinition(
        id="typed-row-projection",
        offset=1,
        length=3,
        kind="projection",
        projection_ref=ref,
        data_type="text",
        required=True,
        padding="right_space",
        justification="left",
        signed=False,
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
    )
    record = ExportRecordDefinition(
        id="typed-projection-rows",
        record_type="2",
        order=0,
        encoding="ascii",
        line_ending="none",
        repeat="projection_rows",
        fields=(field,),
    )
    layout = ExportLayoutDefinition(
        id="typed-projection-row-layout",
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
        records=(record,),
    )

    assert (
        render_layout(
            layout,
            draft=_draft(checkbox=False, year=2026),
            producer_snapshot=_typed_producer_snapshot(),
            projection_values={
                (ref.model_dump_json(), 0): "A01",
                (ref.model_dump_json(), 1): "A02",
            },
        )
        == b"A01A02"
    )
    with pytest.raises(FilingExportValidationError, match="has no projected occurrences"):
        render_layout(
            layout,
            draft=_draft(checkbox=False, year=2026),
            producer_snapshot=_typed_producer_snapshot(),
            projection_values={},
        )
    optional_layout = layout.model_copy(
        update={"records": (record.model_copy(update={"required": False}),)},
    )
    assert (
        render_layout(
            optional_layout,
            draft=_draft(checkbox=False, year=2026),
            producer_snapshot=_typed_producer_snapshot(),
            projection_values={},
        )
        == b""
    )


@pytest.mark.parametrize("invalid", ["yes", 2, " "])
def test_filing_writer_refuses_invalid_checkbox_inputs(invalid: object) -> None:
    with pytest.raises(FilingExportValidationError):
        _render_one(_two_record_layout().records[0], invalid)


@pytest.mark.parametrize("invalid", [26, "26", 2026.0, Decimal("2026"), " 2026"])
def test_filing_writer_refuses_invalid_short_year_inputs(invalid: object) -> None:
    with pytest.raises(FilingExportValidationError):
        _render_one(_two_record_layout().records[1], invalid)


def test_verifier_projects_expected_values_by_record_and_field_identity() -> None:
    layout = _two_record_layout()
    mismatched, checked = _mismatched_casilla_ids(
        layout,
        draft=_draft(checkbox=True, year=2026),
        payload=b"126",
        schema_provider=RegistrySchemaAccessor(collections={}, subviews={}),
    )

    assert mismatched == ()
    assert checked == ("01", "02")


@pytest.mark.parametrize(("payload", "expected_mismatch"), [(b"026", "01"), (b"125", "02")])
def test_verifier_detects_transformed_value_drift(payload: bytes, expected_mismatch: str) -> None:
    mismatched, _ = _mismatched_casilla_ids(
        _two_record_layout(),
        draft=_draft(checkbox=True, year=2026),
        payload=payload,
        schema_provider=RegistrySchemaAccessor(collections={}, subviews={}),
    )

    assert mismatched == (expected_mismatch,)
