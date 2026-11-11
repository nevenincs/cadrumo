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
from ....domain.calculations.registry.schema_base import CasillaDataType
from ....domain.calculations.registry.schema_exports import (
    ExportFieldDefinition,
    ExportLayoutDefinition,
    ExportRecordDefinition,
)
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope, revision_serving_period
from ....domain.filing.errors import FilingExportValidationError
from ....domain.filing.schema import ModeloDraft, ModeloValue, ModeloValueKind, registry_schema_version
from ....domain.submission.models import ModeloDraftStatus
from ..export_verification import mismatched_casilla_ids
from ..record_field_renderer import format_field, projection_field_value
from ..runtime import RegistrySchemaAccessor, build_runtime_schema_provider

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

# The layouts below are synthetic: they exist to exercise the value-policy
# renderer and the verifier's record-and-field identity lookup, both of which
# are modelo-agnostic. The registry snapshot is needed only for its source
# resolution (`source_root`/`sources`), so it must simply be a coordinate the
# authority still admits at filing grade. Modelo 303 at the newest supported year is used
# because it files, and its refs are quoted here so the synthetic declaration
# stays grounded in the modelo it names rather than in an unrelated one.
_MODELO = "303"
_FILING_YEAR = filing_year_envelope().horizon
_PERIOD_CODE = "4T"
_REVISION = revision_serving_period(_MODELO, _FILING_YEAR, _PERIOD_CODE)
_REVISION_ID = str(_REVISION.id)
_LEGAL_REFS = ("orden-eha-3786-2008:art-1",)
_SOURCE_REFS = (f"aeat-dr-303-{_REVISION.valid_from.year}",)

#: The policy prints the last two digits of the year. A year ending in 00 is the boundary
#: where a naive ``year - 2000`` or unpadded rendering would print nothing or one digit.
_YEAR_ENDING_IN_00 = next(year for year in range(_FILING_YEAR, _FILING_YEAR + 100) if year % 100 == 0)


def _short(year: int) -> str:
    return f"{year % 100:02d}"


def _filing_schema_provider() -> RegistrySchemaAccessor:
    """A real filing-grade provider, for source resolution only."""
    return build_runtime_schema_provider(
        filing_year=_FILING_YEAR,
        period=Period.from_year_and_code(_FILING_YEAR, _PERIOD_CODE),
        modelos=(_MODELO,),
    )


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
        data_type=CasillaDataType.INTEGER,
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
    period = Period.from_year_and_code(_FILING_YEAR, _PERIOD_CODE)
    stamped = datetime(1980, 8, 10, tzinfo=UTC)
    return ModeloDraft(
        draft_id="policy-proof",
        modelo=_MODELO,
        period=period,
        profile_tax_id="12345678Z",
        subject_tax_id="12345678Z",
        snapshot_ref=RegistrySnapshotRef(
            modelo=_MODELO,
            revision_id=_REVISION_ID,
            modelo_year=_FILING_YEAR,
            period=_PERIOD_CODE,
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
        schema_version=registry_schema_version(modelo=_MODELO, revision_id=_REVISION_ID),
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
    return format_field(field, value)


@pytest.mark.parametrize(
    ("checkbox", "year", "expected"),
    [
        (False, _FILING_YEAR, f"0{_short(_FILING_YEAR)}".encode()),
        (True, str(_FILING_YEAR), f"1{_short(_FILING_YEAR)}".encode()),
        (None, _YEAR_ENDING_IN_00, f"0{_short(_YEAR_ENDING_IN_00)}".encode()),
    ],
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


@pytest.mark.parametrize(
    "invalid",
    [
        _FILING_YEAR % 100,
        _short(_FILING_YEAR),
        float(_FILING_YEAR),
        Decimal(_FILING_YEAR),
        f" {_FILING_YEAR}",
    ],
)
def test_filing_writer_refuses_invalid_short_year_inputs(invalid: object) -> None:
    with pytest.raises(FilingExportValidationError):
        _render_one(_two_record_layout().records[1], invalid)


def test_verifier_projects_expected_values_by_record_and_field_identity() -> None:
    layout = _two_record_layout()
    mismatched, checked = mismatched_casilla_ids(
        layout,
        draft=_draft(checkbox=True, year=_FILING_YEAR),
        payload=f"1{_short(_FILING_YEAR)}".encode(),
        schema_provider=_filing_schema_provider(),
    )

    assert mismatched == ()
    assert checked == ("01", "02")


@pytest.mark.parametrize(
    ("payload", "expected_mismatch"),
    [
        (f"0{_short(_FILING_YEAR)}".encode(), "01"),
        (f"1{_short(_FILING_YEAR + 1)}".encode(), "02"),
    ],
)
def test_verifier_detects_transformed_value_drift(payload: bytes, expected_mismatch: str) -> None:
    mismatched, _ = mismatched_casilla_ids(
        _two_record_layout(),
        draft=_draft(checkbox=True, year=_FILING_YEAR),
        payload=payload,
        schema_provider=_filing_schema_provider(),
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
        data_type=CasillaDataType.TEXT,
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
        projection_field_value(_projection_field(), None, {})


def test_projection_field_without_a_reference_refuses_before_the_context_check() -> None:
    """A projection field missing its ``projection_ref`` refuses on its own terms."""
    field = _projection_field().model_copy(update={"projection_ref": None})

    with pytest.raises(FilingExportValidationError, match="must declare projection_ref"):
        projection_field_value(field, None, {})
