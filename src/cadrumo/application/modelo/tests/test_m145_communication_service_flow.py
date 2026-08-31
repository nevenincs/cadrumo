"""Real service-flow tests for Modelo 145 local communication records.

See Also:
    :mod:`~application.modelo._m145_communication_records`
        Backend service implementing the local record lifecycle exercised here.
    :class:`~application.modelo.M145CommunicationCreateCommand`
        Create-command DTO used to start the service flow.
    :class:`~application.modelo.M145CommunicationRecordState`
        State vocabulary asserted across delivery and completion transitions.
    :func:`~application.modelo.create_m145_communication_record`
        Public facade entry point for creating the local communication record.
    :func:`~application.modelo.export_m145_communication_record`
        Registry-backed export step in the end-to-end local flow.
"""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest

from ....adapters.outbound.aeat.export.registry_record_renderer import RegistryFixedWidthRecordRenderer
from ....tests.secure_sql import isolated_runtime_profile
from ..m145_communication_records import (
    M145CommunicationCreateCommand,
    M145CommunicationRecordState,
    create_m145_communication_record,
    export_m145_communication_record,
    mark_m145_communication_record_delivered_to_payer,
    mark_m145_communication_record_locally_completed,
    read_m145_communication_record,
    validate_m145_communication_record,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _field_values() -> dict[str, str]:
    return {
        "perceptor.nif": "12345678Z",
        "perceptor.primer-apellido": "Garcia",
        "perceptor.segundo-apellido": "Lopez",
        "perceptor.nombre": "Ana",
        "perceptor.anio-nacimiento": "1981",
    }


def test_m145_communication_service_flow_creates_validates_exports_delivers_and_completes(
    tmp_path: Path,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        created = create_m145_communication_record(
            M145CommunicationCreateCommand(
                communication_year=2026,
                field_values=_field_values(),
                note="Initial payer communication",
            ),
            bucket_id=runtime.bucket_id,
            actor="service-flow-test",
        )
        validation = validate_m145_communication_record(
            created.communication_record_id[:12],
            bucket_id=runtime.bucket_id,
        )
        exported = export_m145_communication_record(
            created.communication_record_id[:12],
            bucket_id=runtime.bucket_id,
            renderer=RegistryFixedWidthRecordRenderer(),
            actor="service-flow-test",
        )
        delivered = mark_m145_communication_record_delivered_to_payer(
            created.communication_record_id[:12],
            bucket_id=runtime.bucket_id,
            actor="service-flow-test",
        )
        completed = mark_m145_communication_record_locally_completed(
            created.communication_record_id[:12],
            bucket_id=runtime.bucket_id,
            actor="service-flow-test",
        )
        read_back = read_m145_communication_record(
            created.communication_record_id[:12],
            bucket_id=runtime.bucket_id,
        )

    assert created.state is M145CommunicationRecordState.CREATED
    assert validation.communication_record_id == created.communication_record_id
    assert validation.valid is True
    assert validation.issue_count == 0
    assert validation.issues == ()
    assert exported.communication_record_id == created.communication_record_id
    assert exported.payload_sha256 == sha256(exported.payload).hexdigest()
    assert exported.payload.startswith(b"<T145010>")
    assert exported.payload.endswith(b"</T145010>")
    assert delivered.state is M145CommunicationRecordState.DELIVERED_TO_PAYER
    assert delivered.delivered_to_payer_at is not None
    assert delivered.locally_completed_at is None
    assert completed.state is M145CommunicationRecordState.LOCALLY_COMPLETED
    assert completed.delivered_to_payer_at == delivered.delivered_to_payer_at
    assert completed.locally_completed_at is not None
    assert completed.delivered_to_payer_at is not None
    assert completed.locally_completed_at >= completed.delivered_to_payer_at
    assert read_back == completed
