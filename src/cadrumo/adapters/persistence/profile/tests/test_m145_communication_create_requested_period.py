"""Modelo 145 record creation honours the requested registry communication period."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation

from ..m145_communication_records import build_m145_communication_records_ports
from ...storage.tests.secure_sql import isolated_runtime_profile
from .....application.modelo.m145_communication_period import M145CommunicationPeriod
from .....application.modelo.m145_communication_records import (
    M145CommunicationCreateCommand,
    M145CommunicationRecordState,
    create_m145_communication_record,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def _field_values() -> dict[str, str]:
    return {
        "perceptor.nif": "12345678Z",
        "perceptor.primer-apellido": "Garcia",
        "perceptor.segundo-apellido": "Lopez",
        "perceptor.nombre": "Ana",
        "perceptor.anio-nacimiento": "1981",
    }


@pytest.mark.parametrize("period_token", tuple(M145CommunicationPeriod))
def test_create_records_the_requested_declared_communication_period(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    period_token: M145CommunicationPeriod,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        created = create_m145_communication_record(
            M145CommunicationCreateCommand(
                communication_year=2026,
                period_token=period_token,
                field_values=_field_values(),
            ),
            bucket_id=runtime.bucket_id,
            actor="requested-period-test",
            ports=build_m145_communication_records_ports(bucket_id=runtime.bucket_id),
            operation=operation,
        )

    assert created.state is M145CommunicationRecordState.CREATED
    assert created.period_token is period_token


def test_create_command_refuses_a_period_token_modelo_145_does_not_declare() -> None:
    declared = M145CommunicationCreateCommand.model_validate_json(
        '{"communication_year": 2026, "period_token": "variacion", "field_values": {"perceptor.nif": "12345678Z"}}'
    )
    assert declared.period_token is M145CommunicationPeriod.VARIATION

    with pytest.raises(ValidationError, match="period_token"):
        M145CommunicationCreateCommand.model_validate_json(
            '{"communication_year": 2026, "period_token": "alta", "field_values": {"perceptor.nif": "12345678Z"}}'
        )
