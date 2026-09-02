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
from pydantic import ValidationError

from ....adapters.outbound.aeat.export.registry_record_renderer import RegistryFixedWidthRecordRenderer
from ....core.authority_grade import RegistryAuthorityGrade
from ....core.resources.bundled_data import bundled_path
from ....domain.calculations.registry.export import ResolvedExportLayout, resolve_export_layout
from ....domain.calculations.registry.schema_exports import ExportFieldDefinition
from ....tests.registry_snapshot import build_snapshot
from ....tests.registry_tree import bundled_registry_tree
from ....tests.secure_sql import isolated_runtime_profile
from ..m145_communication_records import (
    M145CommunicationCreateCommand,
    M145CommunicationExportResult,
    create_m145_communication_record,
    export_m145_communication_record,
)

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
    modelos, catalogues = bundled_registry_tree()
    modelo = next(candidate for candidate in modelos if candidate.id == "145")
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2026,
        period="comunicacion",
        grade=RegistryAuthorityGrade.CALCULATION,
    )
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
        result = export_m145_communication_record(
            record.communication_record_id[:12],
            bucket_id=runtime.bucket_id,
            renderer=RegistryFixedWidthRecordRenderer(),
        )

    nif = resolved.fields_by_id["modelo-145-dr-03-perceptor-nif"]
    first_surname = resolved.fields_by_id["modelo-145-dr-04-perceptor-primer-apellido"]
    birth_year = resolved.fields_by_id["modelo-145-dr-07-perceptor-anio-nacimiento"]
    assert isinstance(result, M145CommunicationExportResult)
    assert result.export_layout_id == resolved.layout.id
    assert result.encoding == "iso-8859-1"
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
        result = export_m145_communication_record(
            record.communication_record_id, bucket_id=runtime.bucket_id, renderer=RegistryFixedWidthRecordRenderer()
        )

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
        result = export_m145_communication_record(
            record.communication_record_id, bucket_id=runtime.bucket_id, renderer=RegistryFixedWidthRecordRenderer()
        )

    # The adapter owns the body; this layer owns only the terminator the
    # registry declares per record, so the body is compared against the
    # renderer rather than re-derived here -- the wire format is covered by
    # the renderer's own suite.
    #
    # PREMISE, stated because it bounds what this assertion can catch: this
    # layout declares ``line_ending = "none"``, so the expected terminator is
    # empty. Removing the terminator concatenation from the service is
    # therefore an EQUIVALENT mutation against this data and this test will
    # not flag it -- verified by applying exactly that mutation and watching
    # all nine tests still pass. What it does catch is the mapping drifting,
    # because the expected value below is written out independently of
    # ``_LINE_ENDINGS``. The ``lf``/``crlf`` branches are unreachable from any
    # shipped M145 layout and are left uncovered rather than exercised through
    # a synthetic record that would assert our own constant back at us.
    assert record_definition.line_ending == "none"
    canonical_body = RegistryFixedWidthRecordRenderer().render_record_body(
        record_definition,
        field_values=record.field_values,
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
            export_m145_communication_record(
                record.communication_record_id, bucket_id=runtime.bucket_id, renderer=RegistryFixedWidthRecordRenderer()
            )


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
        with pytest.raises(ValueError):
            export_m145_communication_record(
                record.communication_record_id, bucket_id=runtime.bucket_id, renderer=RegistryFixedWidthRecordRenderer()
            )


def _seeded_export(runtime) -> M145CommunicationExportResult:
    """Produce one genuine export receipt through the production path."""
    record = create_m145_communication_record(
        M145CommunicationCreateCommand(communication_year=2026, field_values=_field_values()),
        bucket_id=runtime.bucket_id,
    )
    return export_m145_communication_record(
        record.communication_record_id, bucket_id=runtime.bucket_id, renderer=RegistryFixedWidthRecordRenderer()
    )


def _tampered(result: M145CommunicationExportResult, **overrides: object):
    return M145CommunicationExportResult.model_validate({**result.model_dump(), **overrides})


def test_export_receipt_refuses_a_byte_length_that_measures_nothing(tmp_path: Path) -> None:
    """A receipt whose byte_length does not measure its payload is refused.

    The producer computes coherent values, so only a direct construction reaches
    this. That is exactly the case the finding names: a public caller anchoring
    downstream communication history on metadata describing no payload.
    """
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        result = _seeded_export(runtime)

    with pytest.raises(ValidationError, match="byte_length"):
        _tampered(result, byte_length=999)


def test_export_receipt_refuses_a_digest_of_other_bytes(tmp_path: Path) -> None:
    """A receipt carrying a digest of something else is refused."""
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        result = _seeded_export(runtime)

    with pytest.raises(ValidationError, match="payload_sha256"):
        _tampered(result, payload_sha256="0" * 64)


def test_export_receipt_refuses_a_payload_swapped_under_a_kept_receipt(tmp_path: Path) -> None:
    """Swapping the payload while keeping the receipt is refused too.

    The mirror of the two cases above: a check that only ever compared the two
    declared fields against each other would accept this, because the lie is in
    the bytes rather than in the metadata.
    """
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        result = _seeded_export(runtime)

    with pytest.raises(ValidationError):
        _tampered(result, payload=result.payload + b"\x00")


def test_export_receipt_round_trips_its_own_producer_output(tmp_path: Path) -> None:
    """Positive control: the produced receipt revalidates unchanged.

    Without it an all-refused result would look like a working guard while
    actually meaning the producer emits an incoherent receipt.
    """
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        result = _seeded_export(runtime)

    revalidated = M145CommunicationExportResult.model_validate(result.model_dump())

    assert revalidated == result
    assert revalidated.byte_length == len(result.payload)
    assert revalidated.payload_sha256 == sha256(result.payload).hexdigest()
