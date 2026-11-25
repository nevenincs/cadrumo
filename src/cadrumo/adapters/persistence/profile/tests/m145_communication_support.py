"""Valid payer-communication field values and create command shared by the M145 tests."""

from __future__ import annotations

from .....application.modelo.m145_communication_records import M145CommunicationCreateCommand

__all__ = ["communication_command", "valid_field_values"]


def valid_field_values(**overrides: str) -> dict[str, str]:
    values = {
        "perceptor.nif": "12345678Z",
        "perceptor.primer-apellido": "Garcia",
        "perceptor.segundo-apellido": "Lopez",
        "perceptor.nombre": "Ana",
        "perceptor.anio-nacimiento": "1981",
    }
    values.update(overrides)
    return values


def communication_command(*, field_values: dict[str, str] | None = None) -> M145CommunicationCreateCommand:
    return M145CommunicationCreateCommand(
        communication_year=2026,
        field_values=field_values if field_values is not None else valid_field_values(),
    )
