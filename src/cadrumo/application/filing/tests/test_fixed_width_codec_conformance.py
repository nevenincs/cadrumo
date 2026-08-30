"""Real parity proofs for the single registry fixed-width field codec."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....adapters.outbound.aeat.export import RegistryFixedWidthRecordRenderer
from ....core import CasillaId, FilingProducerKey, Period
from ....core.directory_scan import scan_directory
from ....domain.calculations.export_field_kind import CasillaFieldKind
from ....domain.calculations.registry.errors import RegistryValidationError
from ....domain.calculations.registry.export_parse import parse_export_payload
from ....domain.calculations.registry.export_value_policy import ExportValuePolicy
from ....domain.calculations.registry.schema_exports import ExportFieldDefinition, ExportRecordDefinition
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.filing.errors import FilingExportValidationError
from ....domain.filing.schema import ModeloDraft, registry_schema_version
from ....domain.modelos.errors import ModeloExportError
from ....domain.submission import ModeloDraftStatus
from .._export import _RecordRenderRow, _render_record
from ._export_support import _typed_producer_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _draft() -> ModeloDraft:
    stamped = datetime(2026, 8, 10, tzinfo=UTC)
    return ModeloDraft(
        draft_id="canonical-codec-proof",
        modelo="200",
        period=Period.from_year_and_code(2026, "1T"),
        profile_tax_id="12345678Z",
        subject_tax_id="12345678Z",
        snapshot_ref=RegistrySnapshotRef(
            modelo="200",
            revision_id="2025",
            modelo_year=2026,
            period="1T",
        ),
        status=ModeloDraftStatus.APROBADO,
        values=(),
        created_at=stamped,
        updated_at=stamped,
        schema_version=registry_schema_version(modelo="200", revision_id="2025"),
    )


def _field(
    field_id: str,
    *,
    offset: int,
    length: int,
    data_type: str = "text",
    casilla_id: str | None = None,
    literal: str | None = None,
    padding: str = "right_space",
    justification: str = "left",
    decimals: int | None = None,
    signed: bool = False,
    required: bool = False,
    value_policy: ExportValuePolicy | None = None,
) -> ExportFieldDefinition:
    kind = CasillaFieldKind.LITERAL if literal is not None else CasillaFieldKind.CASILLA
    return ExportFieldDefinition.model_validate(
        {
            "id": field_id,
            "offset": offset,
            "length": length,
            "kind": kind,
            "casilla_id": casilla_id,
            "literal": literal,
            "data_type": data_type,
            "required": required,
            "padding": padding,
            "justification": justification,
            "decimals": decimals,
            "signed": signed,
            "value_policy": value_policy,
            "legal_refs": ("ley-27-2014:art-40",),
            "source_refs": ("aeat-dr-200-2025",),
        },
    )


def _record(*fields: ExportFieldDefinition) -> ExportRecordDefinition:
    return ExportRecordDefinition(
        id="canonical-codec-record",
        record_type="1",
        order=0,
        encoding="iso-8859-1",
        line_ending="none",
        fields=fields,
    )


def _canonical_record(*, signed_money: bool = True, required_integer: bool = False) -> ExportRecordDefinition:
    return _record(
        _field("literal", offset=1, length=1, literal="A", padding="none", justification="none"),
        _field(
            "integer",
            offset=2,
            length=4,
            data_type="integer",
            casilla_id="01",
            padding="left_zero",
            justification="right",
            required=required_integer,
        ),
        _field(
            "money",
            offset=6,
            length=6,
            data_type="money",
            casilla_id="02",
            padding="left_zero",
            justification="right",
            signed=signed_money,
        ),
        _field(
            "decimal",
            offset=12,
            length=5,
            data_type="decimal",
            casilla_id="03",
            padding="left_zero",
            justification="right",
            decimals=2,
        ),
        _field("boolean", offset=17, length=1, data_type="boolean", casilla_id="04"),
        _field(
            "checkbox",
            offset=18,
            length=1,
            data_type="integer",
            casilla_id="05",
            padding="left_zero",
            justification="right",
            value_policy=ExportValuePolicy.SELECTED_1_UNSELECTED_0,
        ),
        _field(
            "year",
            offset=19,
            length=2,
            data_type="integer",
            casilla_id="06",
            padding="left_zero",
            justification="right",
            value_policy=ExportValuePolicy.FOUR_DIGIT_YEAR_FINAL_TWO_DIGITS,
        ),
    )


def _application_bytes(record: ExportRecordDefinition, values: Mapping[CasillaId, object]) -> bytes:
    rendered = _render_record(
        record,
        draft=_draft(),
        producer_values={},
        producer_snapshot=_typed_producer_snapshot(),
        casilla_values=dict(values),
        binding_values={},
        row=_RecordRenderRow(row_index=None, active_binding_ids=frozenset()),
        render_context=None,
        projection_values={},
    )
    return rendered.encode(record.encoding)


def _adapter_bytes(record: ExportRecordDefinition, values: Mapping[CasillaId, str]) -> bytes:
    return RegistryFixedWidthRecordRenderer().render_record_body(record, field_values=values)


@pytest.mark.parametrize(
    ("values", "expected"),
    (
        ({"01": "7", "02": "2.005", "03": "1.25", "04": "true", "05": "", "06": "2026"}, b"A0007 0020100125X026"),
        ({"01": "0", "02": "-12.34", "03": "0", "04": "false", "05": "1", "06": "2000"}, b"A0000N0123400000 100"),
        ({"01": "0", "02": "0", "03": "0", "04": "", "05": "0", "06": "1999"}, b"A0000 0000000000 099"),
    ),
)
def test_application_and_adapter_emit_identical_exact_bytes(
    values: Mapping[CasillaId, str],
    expected: bytes,
) -> None:
    record = _canonical_record()

    assert _application_bytes(record, values) == expected
    assert _adapter_bytes(record, values) == expected


@pytest.mark.parametrize(("internal_value", "expected_wire"), (("true", b"X"), ("false", b" ")))
def test_real_amendment_header_internal_boolean_spelling_emits_exact_wire_byte(
    internal_value: str,
    expected_wire: bytes,
) -> None:
    """The modelo exporter composes exact ``true``/``false`` header values."""
    field = ExportFieldDefinition.model_validate(
        {
            "id": "modelo-111-complementaria-indicator",
            "offset": 538,
            "length": 1,
            "kind": "header",
            "producer_key": FilingProducerKey.AMENDMENT_IS_COMPLEMENTARIA,
            "data_type": "boolean",
            "required": False,
            "padding": "right_space",
            "justification": "left",
            "signed": False,
            "legal_refs": ("ley-35-2006:art-99",),
            "source_refs": ("aeat-dr-111-2019-v18",),
        },
    )
    record = ExportRecordDefinition(
        id="modelo-111-page-01",
        record_type="1",
        order=0,
        encoding="iso-8859-1",
        line_ending="none",
        fields=(field,),
    )

    rendered = _render_record(
        record,
        draft=_draft(),
        producer_values={FilingProducerKey.AMENDMENT_IS_COMPLEMENTARIA: internal_value},
        producer_snapshot=_typed_producer_snapshot(complementaria=internal_value == "true"),
        casilla_values={},
        binding_values={},
        row=_RecordRenderRow(row_index=None, active_binding_ids=frozenset()),
        render_context=None,
        projection_values={},
    ).encode(record.encoding)

    assert len(rendered) == 538
    assert rendered[537:538] == expected_wire


@pytest.mark.parametrize(
    ("field_id", "invalid"),
    (
        ("01", "7.5"),
        ("02", "bad"),
        ("02", "NaN"),
        ("02", "Infinity"),
        ("03", "1e2"),
        ("04", "yes"),
        ("01", "10000"),
    ),
)
def test_application_and_adapter_refuse_the_same_invalid_values(field_id: CasillaId, invalid: str) -> None:
    record = _canonical_record()
    values: dict[CasillaId, str] = {
        "01": "7",
        "02": "2.00",
        "03": "1.25",
        "04": "true",
        "05": "1",
        "06": "2026",
    }
    values[field_id] = invalid

    with pytest.raises(FilingExportValidationError):
        _application_bytes(record, values)
    with pytest.raises(ModeloExportError):
        _adapter_bytes(record, values)


def test_unsigned_negative_is_refused_by_both_active_renderers() -> None:
    record = _canonical_record(signed_money=False)
    values: dict[CasillaId, str] = {
        "01": "7",
        "02": "-1",
        "03": "1.25",
        "04": "true",
        "05": "1",
        "06": "2026",
    }

    with pytest.raises(FilingExportValidationError):
        _application_bytes(record, values)
    with pytest.raises(ModeloExportError):
        _adapter_bytes(record, values)


@pytest.mark.parametrize("omitted", ({}, {"01": ""}))
def test_absent_optional_numeric_renders_alike_in_both_active_renderers(omitted: dict[CasillaId, str]) -> None:
    """An optional numeric slot left empty renders its declared zero fill in both.

    A fixed-width field occupies its byte slot unconditionally, and AEAT's record
    designs fill an empty numeric field with zeros, so a taxpayer who simply has
    no such figure still produces a complete record rather than a refusal. Both
    active renderers reach the same codec, so the two must agree byte for byte.
    """
    record = _canonical_record()
    values: dict[CasillaId, str] = {
        "01": "7",
        "02": "2.00",
        "03": "1.25",
        "04": "true",
        "05": "1",
        "06": "2026",
    }
    del values["01"]
    values.update(omitted)

    application = _application_bytes(record, values)

    assert application[1:5] == b"0000"
    assert _adapter_bytes(record, values) == application


def test_absent_required_numeric_is_refused_by_both_active_renderers() -> None:
    """The same empty slot on a required field refuses in both renderers.

    This is the half that must never soften: rendering an omitted mandatory
    figure as zeros would under-declare behind a structurally valid record.
    """
    record = _canonical_record(required_integer=True)
    values: dict[CasillaId, str] = {
        "02": "2.00",
        "03": "1.25",
        "04": "true",
        "05": "1",
        "06": "2026",
    }

    with pytest.raises(FilingExportValidationError):
        _application_bytes(record, values)
    with pytest.raises(ModeloExportError):
        _adapter_bytes(record, values)


def test_empty_declared_literal_fills_its_required_slot_but_absent_required_input_refuses() -> None:
    """A registry-owned blank literal is content; a missing required casilla is not.

    The first field carries an explicit ``literal = \"\"`` payload, so both
    active consumers must write its two width-correct blank bytes.  The second
    field has no producer value at all; accepting it would turn a missing
    mandatory taxpayer value into a plausible record.
    """
    declared_blank = _record(
        _field(
            "declared-blank",
            offset=1,
            length=2,
            literal="",
            required=True,
        ),
    )
    absent_required = _record(
        _field(
            "absent-required",
            offset=1,
            length=2,
            casilla_id="01",
            required=True,
        ),
    )

    assert _application_bytes(declared_blank, {}) == b"  "
    assert _adapter_bytes(declared_blank, {}) == b"  "
    with pytest.raises(FilingExportValidationError):
        _application_bytes(absent_required, {})
    with pytest.raises(ModeloExportError):
        _adapter_bytes(absent_required, {})


@pytest.mark.parametrize(
    "mutation",
    (
        b"A0007+0020100125X026",
        b"A0007X0020100125X026",
        b"A0007 0020100125S026",
        b"A0007 0020100125X226",
    ),
)
def test_parser_refuses_noncanonical_sign_boolean_and_policy_mutations(mutation: bytes) -> None:
    layout = {
        "id": "canonical-codec-layout",
        "format": "fixed_width",
        "records": (_canonical_record(),),
        "legal_refs": ("ley-27-2014:art-40",),
        "source_refs": ("aeat-dr-200-2025",),
    }
    from ....domain.calculations.registry.schema_exports import ExportLayoutDefinition

    with pytest.raises(RegistryValidationError):
        parse_export_payload(ExportLayoutDefinition.model_validate(layout), mutation)


def test_codec_has_one_owner_and_active_consumers_import_the_public_facade() -> None:
    root = Path("src/cadrumo")
    owner = root / "domain/calculations/registry/fixed_width_codec.py"
    consumers = (
        root / "application/filing/_export.py",
        root / "domain/calculations/registry/export_parse.py",
        root / "adapters/outbound/aeat/export/_registry_record_renderer.py",
    )

    assert owner.is_file()
    assert not scan_directory(root / "adapters/outbound/aeat/export/_formats", pattern="*.py", recursive=True)
    for consumer in consumers:
        source = consumer.read_text(encoding="utf-8")
        assert "fixed_width" in source
        assert ".zfill(" not in source
        assert ".rjust(" not in source
        assert ".ljust(" not in source
        assert "def _format_money(" not in source
        assert "def _format_integer(" not in source
        assert "def _parse_money(" not in source
        assert "def _parse_integer(" not in source
        if "domain/calculations/registry" not in consumer.as_posix():
            assert "._fixed_width_codec" not in source
            assert "render_fixed_width_export_field" in source

    registry_export = (root / "domain/calculations/registry/export.py").read_text(encoding="utf-8")
    assert "_ExportPadding" not in registry_export
    assert "_ExportJustification" not in registry_export
