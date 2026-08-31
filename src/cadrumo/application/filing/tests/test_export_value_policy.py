"""Real byte and verification proofs for registry-declared export value policies."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....core.filing_projection_ref import (
    M303Exonerado390ActivityField,
    M303Exonerado390ActivityProjectionRef,
)
from ....core.period import Period
from ....domain.calculations.registry.export_value_policy import ExportValuePolicy
from ....domain.calculations.registry.schema_exports import (
    ExportFieldDefinition,
    ExportLayoutDefinition,
    ExportRecordDefinition,
)
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.filing.errors import FilingExportValidationError
from ....domain.filing.schema import ModeloDraft, ModeloValue, ModeloValueKind, registry_schema_version
from ....domain.submission._protocols import ModeloDraftStatus
from .._export import _format_field, _projection_field_value
from ..export_verification import _mismatched_casilla_ids
from ..runtime import build_runtime_schema_provider

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


def _draft(*, checkbox: bool | None, year: int | str) -> ModeloDraft:
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
    return _format_field(field, value)


@pytest.mark.parametrize(
    ("checkbox", "year", "expected"),
    [(False, 2026, b"026"), (True, "2026", b"126"), (None, 2000, b"000")],
)
def test_filing_writer_emits_exact_policy_bytes(checkbox: object, year: object, expected: bytes) -> None:
    layout = _two_record_layout()
    assert (
        "".join((_render_one(layout.records[0], checkbox), _render_one(layout.records[1], year))).encode() == expected
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
        schema_provider=build_runtime_schema_provider(
            filing_year=2025,
            period=Period.from_year_and_code(2025, "0A"),
            modelos=("200",),
        ),
    )

    assert mismatched == ()
    assert checked == ("01", "02")


@pytest.mark.parametrize(("payload", "expected_mismatch"), [(b"026", "01"), (b"125", "02")])
def test_verifier_detects_transformed_value_drift(payload: bytes, expected_mismatch: str) -> None:
    mismatched, _ = _mismatched_casilla_ids(
        _two_record_layout(),
        draft=_draft(checkbox=True, year=2026),
        payload=payload,
        schema_provider=build_runtime_schema_provider(
            filing_year=2025,
            period=Period.from_year_and_code(2025, "0A"),
            modelos=("200",),
        ),
    )

    assert mismatched == (expected_mismatch,)


def _projection_field() -> ExportFieldDefinition:
    """A real projection field, exactly as the M303 layout declares one."""
    return ExportFieldDefinition(
        id="exonerado-activity-code",
        offset=1,
        length=3,
        kind="projection",
        projection_ref=M303Exonerado390ActivityProjectionRef(
            projection_kind="m303_exonerado_390_activity",
            slot=1,
            field=M303Exonerado390ActivityField.ACTIVITY_CODE,
        ),
        data_type="text",
        required=True,
        padding="right_space",
        justification="left",
        signed=False,
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
    )


def test_projection_field_refuses_a_context_free_render_instead_of_blanking() -> None:
    """A projection slot without its snapshot-owned context must refuse, never render blank.

    ``_render_record`` accepts ``render_context=None`` so that a non-projection
    record can be rendered from a synthetic layout, which cannot carry a
    snapshot-owned :class:`FilingRecordRenderContext` (its validator checks
    layout and record ownership by identity, deliberately, so no synthetic
    context can be forged). That nullable must not become a way for a
    projection field to reach disk as a blank slot behind a valid digest.
    """
    with pytest.raises(FilingExportValidationError, match="requires a snapshot-owned render context"):
        _projection_field_value(_projection_field(), None, {})


def test_projection_field_without_a_reference_refuses_before_the_context_check() -> None:
    """A projection field missing its ``projection_ref`` refuses on its own terms."""
    field = _projection_field().model_copy(update={"projection_ref": None})

    with pytest.raises(FilingExportValidationError, match="must declare projection_ref"):
        _projection_field_value(field, None, {})
