"""Service-error and logging tests for Modelo 145 local communication records.

See Also:
    :mod:`~application.modelo._m145_communication_records`
        Backend service whose error and log vocabulary is constrained here.
    :class:`~application.modelo.M145CommunicationServiceError`
        Base service error registered in the central error catalogue.
    :class:`~application.modelo.M145CommunicationRecordValidationError`
        Typed validation refusal raised for invalid local communication records.
    :class:`~application.modelo.M145CommunicationRecordTransitionError`
        Typed transition refusal raised for invalid lifecycle moves.
    :func:`~core.errors.get_registered_error_code`
        Central error-code lookup asserted for the M145 error hierarchy.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from ....core.errors import get_registered_error_code
from ....tests.secure_sql import isolated_runtime_profile
from .._m145_communication_records import (
    M145CommunicationCreateCommand,
    M145CommunicationRecordAmbiguousError,
    M145CommunicationRecordExportError,
    M145CommunicationRecordNotFoundError,
    M145CommunicationRecordTransitionError,
    M145CommunicationRecordValidationError,
    M145CommunicationServiceError,
    create_m145_communication_record,
    mark_m145_communication_record_delivered_to_payer,
    mark_m145_communication_record_locally_completed,
    read_m145_communication_record,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LOGGER_NAME = "cadrumo.application.modelo._m145_communication_records"
_FORBIDDEN_LOG_TERMS = (
    "file",
    "filing",
    "filed",
    "deadline",
    "live_read",
    "portal",
    "submit",
    "receipt",
    "tramite",
    "tr\u00e1mite",
)


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


def _command(*, field_values: dict[str, str] | None = None) -> M145CommunicationCreateCommand:
    return M145CommunicationCreateCommand(
        communication_year=2026,
        field_values=field_values if field_values is not None else _field_values(),
    )


def _captured_service_messages(caplog: pytest.LogCaptureFixture) -> tuple[str, ...]:
    return tuple(record.getMessage() for record in caplog.records if record.name == _LOGGER_NAME)


def _assert_messages_use_communication_vocabulary(messages: tuple[str, ...]) -> None:
    assert messages
    for message in messages:
        lowered = message.lower()
        assert "m145 communication" in lowered
        for term in _FORBIDDEN_LOG_TERMS:
            assert term not in lowered


def test_m145_communication_service_errors_are_registered_and_typed() -> None:
    error_codes = {
        M145CommunicationServiceError: "ERROR_M145_COMMUNICATION_SERVICE",
        M145CommunicationRecordNotFoundError: "ERROR_M145_COMMUNICATION_RECORD_NOT_FOUND",
        M145CommunicationRecordAmbiguousError: "REFUSED_M145_COMMUNICATION_RECORD_AMBIGUOUS",
        M145CommunicationRecordValidationError: "REFUSED_M145_COMMUNICATION_RECORD_VALIDATION",
        M145CommunicationRecordExportError: "REFUSED_M145_COMMUNICATION_RECORD_EXPORT",
        M145CommunicationRecordTransitionError: "REFUSED_M145_COMMUNICATION_RECORD_TRANSITION",
    }

    assert issubclass(M145CommunicationRecordNotFoundError, KeyError)
    assert issubclass(M145CommunicationRecordAmbiguousError, KeyError)
    assert issubclass(M145CommunicationRecordValidationError, ValueError)
    assert issubclass(M145CommunicationRecordExportError, ValueError)
    assert issubclass(M145CommunicationRecordTransitionError, ValueError)
    for error_type, code in error_codes.items():
        assert get_registered_error_code(error_type).code == code


def test_m145_communication_create_delivery_completion_logs_use_communication_vocabulary(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger=_LOGGER_NAME)

    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        created = create_m145_communication_record(_command(), bucket_id=runtime.bucket_id)
        mark_m145_communication_record_delivered_to_payer(
            created.communication_record_id,
            bucket_id=runtime.bucket_id,
        )
        mark_m145_communication_record_locally_completed(
            created.communication_record_id,
            bucket_id=runtime.bucket_id,
        )

    messages = _captured_service_messages(caplog)
    assert any("created" in message for message in messages)
    assert any("delivered_to_payer" in message for message in messages)
    assert any("locally_completed" in message for message in messages)
    _assert_messages_use_communication_vocabulary(messages)


def test_m145_communication_invalid_delivery_raises_typed_error_and_logs_refusal(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger=_LOGGER_NAME)
    field_values = _field_values()
    field_values.pop("perceptor.nif")

    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        record = create_m145_communication_record(_command(field_values=field_values), bucket_id=runtime.bucket_id)
        with pytest.raises(M145CommunicationRecordValidationError) as raised:
            mark_m145_communication_record_delivered_to_payer(
                record.communication_record_id,
                bucket_id=runtime.bucket_id,
            )

    assert isinstance(raised.value, ValueError)
    assert raised.value.context is not None
    assert raised.value.context["communication_record_id"] == record.communication_record_id
    assert raised.value.context["issue_count"] == 1
    messages = _captured_service_messages(caplog)
    assert any("delivery refused" in message for message in messages)
    _assert_messages_use_communication_vocabulary(messages)


def test_m145_communication_completion_before_delivery_raises_typed_error_and_logs_refusal(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger=_LOGGER_NAME)

    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        record = create_m145_communication_record(_command(), bucket_id=runtime.bucket_id)
        with pytest.raises(M145CommunicationRecordTransitionError) as raised:
            mark_m145_communication_record_locally_completed(
                record.communication_record_id,
                bucket_id=runtime.bucket_id,
            )

    assert isinstance(raised.value, ValueError)
    assert raised.value.context == {"communication_record_id": record.communication_record_id, "state": "created"}
    messages = _captured_service_messages(caplog)
    assert any("completion refused" in message for message in messages)
    _assert_messages_use_communication_vocabulary(messages)


def test_m145_communication_missing_record_raises_typed_key_error_and_logs_lookup(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger=_LOGGER_NAME)
    missing_id = "0" * 64

    with (
        isolated_runtime_profile(tmp_path=tmp_path) as runtime,
        pytest.raises(M145CommunicationRecordNotFoundError) as raised,
    ):
        read_m145_communication_record(missing_id, bucket_id=runtime.bucket_id)

    assert isinstance(raised.value, KeyError)
    assert raised.value.context == {"communication_record_id": missing_id}
    messages = _captured_service_messages(caplog)
    assert any("lookup missing" in message for message in messages)
    _assert_messages_use_communication_vocabulary(messages)
