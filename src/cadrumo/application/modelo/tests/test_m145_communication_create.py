"""Real-runtime create tests for Modelo 145 local communication records.

See Also:
    :mod:`~application.modelo._m145_communication_records`
        Backend service implementing create, list, read, and object-key flows.
    :class:`~application.modelo.M145CommunicationCreateCommand`
        Strict command DTO accepted by the create service.
    :class:`~application.modelo.M145CommunicationRecord`
        Persisted bucket-local record asserted by this module.
    :func:`~application.modelo.derive_m145_communication_record_id`
        Deterministic record-id helper checked against persisted output.
    :data:`~adapters.persistence.storage.M145_COMMUNICATION_RECORD_NAMESPACE`
        Secure-object namespace that stores local communication records.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ....adapters.persistence.storage.secure_object_namespaces import M145_COMMUNICATION_RECORD_NAMESPACE
from ....domain.calculations.registry.casilla_membership import undeclared_casilla_ids
from ....tests.registry_tree import bundled_registry_tree
from ....tests.secure_sql import isolated_runtime_profile
from ..m145_communication_period import M145CommunicationPeriod
from ..m145_communication_records import (
    M145CommunicationCreateCommand,
    M145CommunicationRecord,
    create_m145_communication_record,
    derive_m145_communication_record_id,
    list_m145_communication_records,
    m145_communication_record_object_key,
    read_m145_communication_record,
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


def _command(
    *,
    period_token: M145CommunicationPeriod = M145CommunicationPeriod.COMMUNICATION,
    note: str | None = "Initial local communication",
) -> M145CommunicationCreateCommand:
    return M145CommunicationCreateCommand(
        communication_year=2026,
        period_token=period_token,
        field_values=_field_values(),
        note=note,
    )


def test_create_m145_communication_record_persists_bucket_scoped_registry_record(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        record = create_m145_communication_record(_command(), bucket_id=runtime.bucket_id)
        listed = list_m145_communication_records(bucket_id=runtime.bucket_id)
        read_back = read_m145_communication_record(record.communication_record_id[:12], bucket_id=runtime.bucket_id)

    assert isinstance(record, M145CommunicationRecord)
    assert record.bucket_id == runtime.bucket_id
    assert record.modelo == "145"
    assert record.service_owner == "cadrumo.application.modelo"
    assert record.communication_year == 2026
    assert record.period_token is M145CommunicationPeriod.COMMUNICATION
    assert record.revision_id == "2012-01-31-y-siguientes"
    assert record.state.value == "created"
    assert record.field_values == _field_values()
    assert record.communication_record_id == derive_m145_communication_record_id(
        bucket_id=runtime.bucket_id,
        communication_year=2026,
        period_token=M145CommunicationPeriod.COMMUNICATION,
        revision_id="2012-01-31-y-siguientes",
        field_values=_field_values(),
    )
    assert "rd-439-2007:art-88" in record.legal_refs
    assert "aeat-modelo-145-form" in record.source_refs
    assert listed == (record,)
    assert read_back == record


def test_create_m145_communication_record_persists_to_secure_namespace(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        record = create_m145_communication_record(_command(), bucket_id=runtime.bucket_id)

        envelope = runtime.repository.load(
            M145_COMMUNICATION_RECORD_NAMESPACE.namespace,
            m145_communication_record_object_key(runtime.bucket_id, record.communication_record_id),
            expected_class=M145_COMMUNICATION_RECORD_NAMESPACE.sensitivity,
            max_supported_version=M145_COMMUNICATION_RECORD_NAMESPACE.schema_version,
        )

    assert envelope is not None
    assert envelope.classification is M145_COMMUNICATION_RECORD_NAMESPACE.sensitivity


def test_create_m145_communication_record_is_idempotent_for_identical_content(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        first = create_m145_communication_record(_command(), bucket_id=runtime.bucket_id)
        second = create_m145_communication_record(_command(note="Ignored replay note"), bucket_id=runtime.bucket_id)
        listed = list_m145_communication_records(bucket_id=runtime.bucket_id)

    assert second == first
    assert second.communication_record_id == first.communication_record_id
    assert second.created_at == first.created_at
    assert listed == (first,)


def test_create_m145_communication_record_distinguishes_variation_period(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        communication = create_m145_communication_record(_command(), bucket_id=runtime.bucket_id)
        variation = create_m145_communication_record(
            _command(period_token=M145CommunicationPeriod.VARIATION),
            bucket_id=runtime.bucket_id,
        )
        listed = list_m145_communication_records(bucket_id=runtime.bucket_id)

    assert variation.period_token is M145CommunicationPeriod.VARIATION
    assert variation.communication_record_id != communication.communication_record_id
    assert {record.communication_record_id for record in listed} == {
        communication.communication_record_id,
        variation.communication_record_id,
    }


def test_create_m145_communication_record_refuses_undeclared_casilla_id(tmp_path: Path) -> None:
    command = M145CommunicationCreateCommand(
        communication_year=2026,
        field_values={"perceptor.no-declarado": "x"},
    )
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime, pytest.raises(ValueError, match="undeclared casilla"):
        create_m145_communication_record(command, bucket_id=runtime.bucket_id)


def test_create_m145_communication_record_uses_real_registry_membership() -> None:
    from ....domain.calculations.registry.temporal import select_revision

    modelos, _catalogues = bundled_registry_tree()
    modelo = next(m for m in modelos if m.id == "145")
    revision = select_revision(modelo, filing_year=2026, period="comunicacion")

    assert undeclared_casilla_ids(revision, _field_values()) == ()
    assert undeclared_casilla_ids(revision, {"perceptor.no-declarado": "x"}) == ("perceptor.no-declarado",)
