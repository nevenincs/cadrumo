"""Official M190 signed amounts retain their reintegro and key conditions."""

from __future__ import annotations

import pytest

from cadrumo.application.filing.m190_context_validation import require_m190_signed_reintegro_context
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.schema_exports import ExportFieldDefinition, ExportRecordDefinition
from cadrumo.domain.calculations.registry.tests.published_authority import published_revision
from cadrumo.domain.filing.errors import FilingExportValidationError
from cadrumo.domain.modelos.perceptor_clave_scope import resolve_perceptor_clave_scope

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.usefixtures("operation")]

_REVISIONS = ("2022", "2023", "2024", "2025-y-siguientes")
_SOURCE_DIGESTS = {
    "aeat-dr-190-2020": "4cefd924a7dda3ac5159582f728a72f6f162d3344b8e87f2d17900e6fdcf3b32",
    "aeat-dr-190-2023": "430daf439ed645155ffc6096b65c4da5b26dd2e6c16b8e4781f9be145b3792cb",
    "aeat-dr-190-2024": "20bc8086525ce850063b9ae8644b8514483e5c34f90c8e47cfadc6c52cf7390e",
    "aeat-dr-190-2025": "a7d1092f78620431812354e560a5146a3ae244e0aed69d9d58c353370ba0134d",
}


def _check(record: ExportRecordDefinition, wire: str, *, source_digests: dict[str, str]) -> None:
    require_m190_signed_reintegro_context(
        record,
        wire,
        clave_scope=resolve_perceptor_clave_scope(period=Period.from_year_and_code(2025, "0A")),
        source_digests=source_digests,
    )


def _record(revision: str) -> ExportRecordDefinition:
    layout = published_revision("190", revision).export_layouts[0]
    return next(record for record in layout.records if record.id == "modelo-190-perceptor")


def _field(record: ExportRecordDefinition, field_id: str) -> ExportFieldDefinition:
    return next(field for field in record.fields if field.id == field_id)


@pytest.fixture(params=_REVISIONS)
def record(request: pytest.FixtureRequest) -> ExportRecordDefinition:
    return _record(request.param)


def _wire(*, key: str = "A", subkey: str = "01", devengo: str = "2024", filing: str = "2025") -> list[str]:
    wire = list(" " * 500)
    wire[4:8], wire[77], wire[78:80], wire[147:151] = list(filing), key, list(subkey), list(devengo)
    for offset in (82, 109, 256, 283, 95, 122, 269, 296):
        wire[offset - 1 : offset + 12] = list("0" * 13)
    return wire


def test_negative_reintegro_requires_prior_devengo_and_zero_withholding(record: ExportRecordDefinition) -> None:
    wire = _wire()
    wire[80], wire[81:94] = "N", list("0" * 12 + "1")
    _check(record, "".join(wire), source_digests=_SOURCE_DIGESTS)
    for changed in (_wire(devengo="2025"), _wire(devengo="0000"), _wire(devengo="2024")):
        changed[80], changed[81:94] = "N", list("0" * 12 + "1")
        if changed[147:151] == list("2024"):
            changed[94:107] = list("0" * 12 + "1")
        with pytest.raises(FilingExportValidationError, match="earlier devengo year and zero"):
            _check(record, "".join(changed), source_digests=_SOURCE_DIGESTS)


def test_incapacity_key_conditions_apply_to_positive_and_negative_amounts(record: ExportRecordDefinition) -> None:
    monetary = _wire(key="B", subkey="01")
    monetary[254], monetary[255:268] = "N", list("0" * 12 + "1")
    _check(record, "".join(monetary), source_digests=_SOURCE_DIGESTS)
    for key, subkey in (("B", "02"), ("C", "01")):
        bad = _wire(key=key, subkey=subkey)
        bad[255:268] = list("0" * 12 + "1")
        with pytest.raises(FilingExportValidationError, match="incapacidad-dineraria-percepcion"):
            _check(record, "".join(bad), source_digests=_SOURCE_DIGESTS)
    in_kind = _wire(key="B", subkey="01")
    in_kind[282:295] = list("0" * 12 + "1")
    with pytest.raises(FilingExportValidationError, match="incapacidad-especie-valoracion"):
        _check(record, "".join(in_kind), source_digests=_SOURCE_DIGESTS)


def _with_field(record: ExportRecordDefinition, field_id: str, **update: object) -> ExportRecordDefinition:
    fields = tuple(field.model_copy(update=update) if field.id == field_id else field for field in record.fields)
    return record.model_copy(update={"fields": fields})


def test_signed_context_refuses_stale_source_and_inconsistent_pair(record: ExportRecordDefinition) -> None:
    wire = "".join(_wire())
    sign = _field(record, "modelo-190-perc-signo-percepcion-dineraria")
    ref = str(sign.source_refs[0])
    with pytest.raises(FilingExportValidationError, match="reviewed source digest"):
        _check(record, wire, source_digests={ref: "0" * 64})
    changed = _with_field(record, sign.id, binding="other")
    with pytest.raises(FilingExportValidationError, match="declaration is incomplete or changed"):
        _check(changed, wire, source_digests=_SOURCE_DIGESTS)
    negative_zero = _wire()
    negative_zero[80] = "N"
    with pytest.raises(FilingExportValidationError, match="nonzero magnitude"):
        _check(record, "".join(negative_zero), source_digests=_SOURCE_DIGESTS)


def test_signed_context_refuses_a_wire_that_is_not_the_declared_record_width(record: ExportRecordDefinition) -> None:
    with pytest.raises(FilingExportValidationError, match="record is incomplete"):
        _check(record, "".join(_wire())[:-1], source_digests=_SOURCE_DIGESTS)


def test_signed_context_refuses_a_component_pair_that_is_no_longer_adjacent(record: ExportRecordDefinition) -> None:
    moved = _with_field(record, "modelo-190-perc-percepcion-dineraria", offset=83)
    with pytest.raises(FilingExportValidationError, match="declaration is incomplete or changed"):
        _check(moved, "".join(_wire()), source_digests=_SOURCE_DIGESTS)


def test_signed_context_reads_the_withholding_where_the_layout_declares_it(record: ExportRecordDefinition) -> None:
    relocated = _with_field(record, "modelo-190-perc-retenciones-practicadas", offset=400)
    wire = _wire()
    wire[80], wire[81:94] = "N", list("0" * 12 + "1")
    wire[94:107] = list("0" * 12 + "1")
    wire[399:412] = list("0" * 13)
    _check(relocated, "".join(wire), source_digests=_SOURCE_DIGESTS)
    wire[399:412] = list("0" * 12 + "1")
    with pytest.raises(FilingExportValidationError, match="earlier devengo year and zero"):
        _check(relocated, "".join(wire), source_digests=_SOURCE_DIGESTS)
