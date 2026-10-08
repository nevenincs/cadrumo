"""Source-identified envelope prefixes and fixed records keep separate byte authority."""

from __future__ import annotations

from functools import cache

import pytest
from pydantic import ValidationError

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_exports import ExportLayoutDefinition

from .. import export_layout_record_join as record_join
from ..loader import load_modelo_directory, load_shared_catalogues
from ..record_design_schema import RecordDesignSheet
from ..validate_export_layout_coverage import (
    _joined_variable_header_coverage_inputs,
    _layout_failure,
    _missing_report,
    validate_export_layout_record_coverage,
)
from ..validate_exports import validate_embedded_envelope_source_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@cache
def _catalogue():
    return load_shared_catalogues(bundled_path("registry", "aeat")).sources


@cache
def _revision(modelo: str, revision: str) -> ModeloRevision:
    return load_modelo_directory(bundled_path("registry", "aeat", "modelos", modelo)).revisions[revision]


def _layout(modelo: str, revision: str) -> ExportLayoutDefinition:
    return _revision(modelo, revision).export_layouts[0]


def _sheet(source_ref: str, sheet_name: str) -> RecordDesignSheet:
    source = _catalogue()[source_ref]
    sheets = record_join._read_design_sheets(source)
    assert not isinstance(sheets, str)
    return next(sheet for sheet in sheets if sheet.name == sheet_name)


@pytest.mark.parametrize(
    ("modelo", "revision"),
    (
        ("232", "2016-2017"),
        ("232", "2018-y-siguientes"),
        ("390", "2022"),
        ("390", "2023"),
        ("390", "2024"),
        ("390", "2025"),
    ),
)
def test_real_variable_prefix_and_fixed_body_have_complete_separate_coverage(modelo: str, revision: str) -> None:
    selected = _revision(modelo, revision)
    assert (
        validate_export_layout_record_coverage(
            prefix=f"modelo {modelo} revision {revision}", revision=selected, source_refs=_catalogue()
        )
        == []
    )


@pytest.mark.parametrize(
    ("modelo", "revision"),
    (
        ("122", "2017-y-siguientes"),
        ("123", "2019-2023"),
        ("123", "2024-y-siguientes"),
        ("126", "2019-y-siguientes"),
        ("128", "2019-y-siguientes"),
        ("490", "2022-2t-4t"),
        ("369", "esquema-exterior"),
        ("604", "2024-y-siguientes"),
        ("714", "2025"),
    ),
)
def test_real_source_joined_fixed_header_covers_variable_prefix(modelo: str, revision: str) -> None:
    selected = _revision(modelo, revision)
    assert (
        validate_export_layout_record_coverage(
            prefix=f"modelo {modelo} revision {revision}", revision=selected, source_refs=_catalogue()
        )
        == []
    )


@pytest.mark.parametrize("change", ("geometry", "literal", "filler"))
def test_source_joined_header_refuses_changed_prefix_claim(change: str) -> None:
    sheet = _sheet("aeat-dr-122-2016", "Pag. 0")
    layout = _layout("122", "2017-y-siguientes")
    source = _catalogue()["aeat-dr-122-2016"]
    joined = record_join._join_record(sheet, layout.records, source=source)
    assert joined is not None
    target = {"geometry": 23, "literal": 323, "filler": 23}[change]

    def changed(field):
        if field.offset != target:
            return field
        assert field.length is not None
        return field.model_copy(
            update={
                "length": field.length - 1 if change == "geometry" else field.length,
                "literal": "</BAD>" if change == "literal" else field.literal,
                "kind": CasillaFieldKind.HEADER if change == "filler" else field.kind,
            }
        )

    fields = tuple(changed(field) for field in joined.fields)
    with pytest.raises(RegistryValidationError, match="contradict the source"):
        _joined_variable_header_coverage_inputs(sheet, joined.model_copy(update={"fields": fields}))


@pytest.mark.parametrize("change", ("absent", "source", "hash", "identity", "extent", "equal_length_roles"))
def test_m232_variable_prefix_refuses_missing_or_changed_envelope_claim(change: str) -> None:
    layout = _layout("232", "2016-2017")
    envelope = layout.filing_envelope
    assert envelope is not None
    if change == "absent":
        replacement = None
    elif change == "equal_length_roles":
        prefix_fields = list(envelope.prefix_fields)
        first, second = 3, 8  # Filing year and program identifier are both four bytes.
        prefix_fields[first] = prefix_fields[first].model_copy(update={"role": envelope.prefix_fields[second].role})
        prefix_fields[second] = prefix_fields[second].model_copy(update={"role": envelope.prefix_fields[first].role})
        replacement = envelope.model_copy(update={"prefix_fields": tuple(prefix_fields)})
    else:
        updates = {
            "source": {"source_ref": "aeat-dr-390-2022"},
            "hash": {"source_sha256": "0" * 64},
            "identity": {"record_identity": "wrong-record"},
            "extent": {"prefix_extent": 327},
        }
        replacement = envelope.model_copy(update=updates[change])
    if change in {"extent", "equal_length_roles"}:
        assert replacement is not None
        with pytest.raises(ValidationError, match=r"prefix extent|canonical source order"):
            type(envelope).model_validate(replacement.model_dump(mode="python"))
    elif change in {"source", "hash"}:
        changed = layout.model_copy(update={"filing_envelope": replacement})
        failures: list[str] = []
        validate_embedded_envelope_source_authority(
            failures,
            prefix="modelo 232",
            layout=changed,
            source_refs=_catalogue(),
            source_root=bundled_path(),
        )
        assert any("does not match canonical catalogue digest" in failure for failure in failures)
    else:
        changed = layout.model_copy(update={"filing_envelope": replacement})
        failure = _layout_failure(prefix="modelo 232", layout=changed, source_refs=_catalogue())
        assert failure is not None
        assert "DR23200" in failure


def test_modelo_390_page_seven_joins_only_with_its_exact_source_adjudication() -> None:
    source = _catalogue()["aeat-dr-390-2022"]
    assert source.sha256 == "7c6554f3182df51daaec37284dd891eb925e1f92df7e69bc01b8ccfb8e4f26fe"
    sheet = _sheet("aeat-dr-390-2022", "Pág. 7")
    assert record_join._join_record(sheet, _layout("390", "2022").records) is None
    joined = record_join._join_record(sheet, _layout("390", "2022").records, source=source)
    assert joined is not None
    assert joined.record_type == "page_07"


def test_source_adjudication_refuses_a_parser_that_drops_its_pinned_sheet() -> None:
    source = _catalogue()["aeat-dr-390-2022"]
    other_sheet = _sheet("aeat-dr-390-2022", "Pág. 1")
    with pytest.raises(RegistryValidationError, match=r"names missing sheet 'Pág. 7'"):
        record_join._require_adjudicated_source_sheets(source, (other_sheet,))


@pytest.mark.parametrize("change", ("hash", "content", "width"))
def test_modelo_390_adjudication_refuses_stale_source_or_changed_cell(change: str) -> None:
    source = _catalogue()["aeat-dr-390-2022"]
    sheet = _sheet("aeat-dr-390-2022", "Pág. 7")
    if change == "hash":
        source = source.model_copy(update={"sha256": "0" * 64})
    else:
        fields = tuple(
            field.model_copy(
                update={
                    "content": 'Constante "</T39007000>"' if change == "content" else field.content,
                    "length": 11 if change == "width" else field.length,
                }
            )
            if field.row == 53
            else field
            for field in sheet.fields
        )
        sheet = sheet.model_copy(update={"fields": fields})
    with pytest.raises(RegistryValidationError, match="source-defect declaration"):
        record_join._join_record(sheet, _layout("390", "2022").records, source=source)


def test_ambiguous_multi_record_sheet_cannot_pass_from_layout_wide_bytes() -> None:
    source = _catalogue()["aeat-dr-390-2022"]
    sheet = _sheet("aeat-dr-390-2022", "Pág. 1")
    fields = tuple(
        field.model_copy(update={"content": None}) if field.offset in {6, 1176} else field for field in sheet.fields
    )
    ambiguous = sheet.model_copy(update={"fields": fields})
    layout = _layout("390", "2022")
    assert record_join._join_record(ambiguous, layout.records, source=source) is None
    _required, _missing, unresolved, lines = _missing_report(((ambiguous, source),), layout.records)
    assert unresolved == 1
    assert any("layout-wide byte coverage cannot verify this record" in line for line in lines)


def test_matched_fixed_record_still_refuses_real_reserved_byte_intrusion() -> None:
    source = _catalogue()["aeat-dr-232-2016"]
    sheet = _sheet("aeat-dr-232-2016", "DR23201")
    layout = _layout("232", "2016-2017")
    matched = record_join._join_record(sheet, layout.records, source=source)
    assert matched is not None
    assert record_join._reserved_write_failures(sheet, matched.fields, source=source) == []
    intruding_fields = tuple(
        field.model_copy(update={"kind": CasillaFieldKind.HEADER})
        if field.offset == 220 and field.length == 20
        else field
        for field in matched.fields
    )
    intruding = matched.model_copy(update={"fields": intruding_fields})
    amended_records = tuple(intruding if record is matched else record for record in layout.records)
    assert record_join._join_record(sheet, amended_records, source=source) is intruding
    failures = record_join._reserved_write_failures(sheet, intruding.fields, source=source)
    assert len(failures) == 1
    assert "@220..239" in failures[0]


def test_unjoined_single_record_checks_its_own_reserved_bytes() -> None:
    source = _catalogue()["aeat-dr-232-2016"]
    sheet = _sheet("aeat-dr-232-2016", "DR23201")
    layout = _layout("232", "2016-2017")
    matched = record_join._join_record(sheet, layout.records, source=source)
    assert matched is not None
    without_identity = sheet.model_copy(
        update={"fields": tuple(field.model_copy(update={"content": None}) for field in sheet.fields)}
    )
    assert record_join._join_record(without_identity, (matched,), source=source) is None
    intruding_fields = tuple(
        field.model_copy(update={"kind": CasillaFieldKind.HEADER})
        if field.offset == 220 and field.length == 20
        else field
        for field in matched.fields
    )
    intruding = matched.model_copy(update={"fields": intruding_fields})
    _required, missing, unresolved, lines = _missing_report(((without_identity, source),), (intruding,))
    assert missing >= 1
    assert unresolved == 0
    assert any("@220..239" in line for line in lines)
