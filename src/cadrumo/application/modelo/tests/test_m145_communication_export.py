"""Real-runtime export tests for Modelo 145 local communication records.

See Also:
    :mod:`~application.modelo._m145_communication_records`
        Backend service that validates and renders the local record.
    :func:`~application.modelo.export_m145_communication_record`
        Public facade export function exercised by these tests.
    :class:`~application.modelo.M145CommunicationExportResult`
        Export result DTO carrying payload bytes and source refs.
    :class:`~domain.calculations.registry.ResolvedExportLayout`
        Registry-resolved fixed-width layout used to assert byte slices.
    :class:`~domain.calculations.registry.ExportFieldDefinition`
        Field metadata that anchors offsets, lengths, and padding behavior.
"""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest

from ....adapters.outbound.aeat.export._formats._serialise import render_record_body
from ....core.resources import resources
from ....domain.calculations.registry import ExportFieldDefinition, ResolvedExportLayout, resolve_export_layout
from ....tests.secure_sql import isolated_runtime_profile
from .. import (
    M145CommunicationCreateCommand,
    M145CommunicationExportResult,
    create_m145_communication_record,
    export_m145_communication_record,
)
from .._m145_communication_records import _m145_export_inputs

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _field_values(**overrides: str) -> dict[str, str]:
    values = {
        "perceptor.nif": "12345678Z",
        "perceptor.primer-apellido": "Garcia",
        "perceptor.segundo-apellido": "Lopez",
        "perceptor.nombre": "Ana",
        "perceptor.anio-nacimiento": "1981",
    }
    values.update(overrides)
    return values


def _resolved_layout() -> ResolvedExportLayout:
    snapshot = resources().modelos.authority.snapshot("145", filing_year=2026, period="comunicacion")
    return resolve_export_layout(snapshot)


def _payload_slice(payload: bytes, field: ExportFieldDefinition) -> bytes:
    assert field.offset is not None
    assert field.length is not None
    start = field.offset - 1
    return payload[start : start + field.length]


def _content_length(resolved: ResolvedExportLayout) -> int:
    return max((field.offset or 0) + (field.length or 0) - 1 for field in resolved.ordered_fields)


def test_export_m145_communication_record_renders_registry_fixed_width_payload(tmp_path: Path) -> None:
    resolved = _resolved_layout()

    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        record = create_m145_communication_record(
            M145CommunicationCreateCommand(communication_year=2026, field_values=_field_values()),
            bucket_id=runtime.bucket_id,
        )
        result = export_m145_communication_record(record.communication_record_id[:12], bucket_id=runtime.bucket_id)

    nif = resolved.fields_by_id["modelo-145-dr-03-perceptor-nif"]
    first_surname = resolved.fields_by_id["modelo-145-dr-04-perceptor-primer-apellido"]
    birth_year = resolved.fields_by_id["modelo-145-dr-07-perceptor-anio-nacimiento"]
    assert isinstance(result, M145CommunicationExportResult)
    assert result.export_layout_id == resolved.layout.id
    assert result.encoding == "latin-1"
    assert result.record_count == 1
    assert result.byte_length == _content_length(resolved)
    assert result.payload_sha256 == sha256(result.payload).hexdigest()
    assert result.source_refs == tuple(sorted(str(ref) for ref in resolved.layout.source_refs))
    assert result.payload.startswith(b"<T145010>")
    assert result.payload.endswith(b"</T145010>")
    assert _payload_slice(result.payload, nif) == b"12345678Z"
    assert first_surname.length is not None
    assert _payload_slice(result.payload, first_surname) == b"Garcia" + (b" " * (first_surname.length - 6))
    assert _payload_slice(result.payload, birth_year) == b"1981"


def test_export_m145_communication_record_applies_registry_numeric_and_money_padding(tmp_path: Path) -> None:
    resolved = _resolved_layout()
    descendant_year = resolved.fields_by_id["modelo-145-dr-16-descendiente-1-anio-nacimiento"]
    compensation = resolved.fields_by_id["modelo-145-dr-44-pension-compensatoria-importe-anual"]
    absent_ascendant_year = resolved.fields_by_id["modelo-145-dr-36-ascendiente-1-anio-nacimiento"]

    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        record = create_m145_communication_record(
            M145CommunicationCreateCommand(
                communication_year=2026,
                field_values=_field_values(
                    **{
                        "descendiente-1.anio-nacimiento": "2010",
                        "pension-compensatoria.importe-anual": "1234.56",
                    },
                ),
            ),
            bucket_id=runtime.bucket_id,
        )
        result = export_m145_communication_record(record.communication_record_id, bucket_id=runtime.bucket_id)

    assert _payload_slice(result.payload, descendant_year) == b"2010"
    assert _payload_slice(result.payload, compensation) == f"{123456:017d}".encode()
    assert _payload_slice(result.payload, absent_ascendant_year) == b"0000"


def test_export_m145_communication_record_matches_canonical_encoder_for_money_and_text(tmp_path: Path) -> None:
    """The registry layout's text and monetary fields share the generic byte encoder."""
    resolved = _resolved_layout()
    record_definition = resolved.layout.records[0]
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        record = create_m145_communication_record(
            M145CommunicationCreateCommand(
                communication_year=2026,
                field_values=_field_values(
                    **{
                        "perceptor.primer-apellido": "García",
                        "pension-compensatoria.importe-anual": "1234.56",
                    },
                ),
            ),
            bucket_id=runtime.bucket_id,
        )
        result = export_m145_communication_record(record.communication_record_id, bucket_id=runtime.bucket_id)

    specs, headers, casilla_values, total_length = _m145_export_inputs(record_definition, record)
    canonical_body = render_record_body(
        casilla_values=casilla_values,
        headers=headers,
        specs=specs,
        encoding="iso-8859-1",
        total_length=total_length,
    )
    assert result.payload == canonical_body


def test_export_m145_communication_record_refuses_invalid_record(tmp_path: Path) -> None:
    values = _field_values()
    values.pop("perceptor.nif")

    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        record = create_m145_communication_record(
            M145CommunicationCreateCommand(communication_year=2026, field_values=values),
            bucket_id=runtime.bucket_id,
        )
        with pytest.raises(ValueError, match="validation passes"):
            export_m145_communication_record(record.communication_record_id, bucket_id=runtime.bucket_id)


def test_export_m145_communication_record_refuses_layout_field_overflow(tmp_path: Path) -> None:
    first_surname = _resolved_layout().fields_by_id["modelo-145-dr-04-perceptor-primer-apellido"]
    assert first_surname.length is not None

    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        record = create_m145_communication_record(
            M145CommunicationCreateCommand(
                communication_year=2026,
                field_values=_field_values(**{"perceptor.primer-apellido": "A" * (first_surname.length + 1)}),
            ),
            bucket_id=runtime.bucket_id,
        )
        with pytest.raises(ValueError, match="overflows length"):
            export_m145_communication_record(record.communication_record_id, bucket_id=runtime.bucket_id)
