"""Canonical Google registration contracts."""

from __future__ import annotations

from pathlib import Path

import typer
from pydantic import ValidationError

from ....adapters.outbound.google.errors import GoogleAuthValidationError
from ....application.runtime.contracts import RuntimeRefusalCode
from ....application.user_profile.google_configuration_operation_contracts import (
    GOOGLE_REGISTER_OPERATION_DEFINITION_ID,
    GoogleRegisterProjection,
    GoogleRegisterRequest,
)
from ....core.hashing import sha256_hex
from ..errors import CliRefusedBoundaryError
from ..registered_operation_errors import submitted_operation_error
from ..runtime_profile_binding import bound_profile_client
from .google_errors import google_refusal
from .runtime_google_configuration import run_google_configuration

GOOGLE_CLIENT_SECRET_MAX_BYTES = 65_536


def run_google_register(ctx: typer.Context, source_path: Path) -> GoogleRegisterProjection:
    """Submit client JSON as one protected secret, with only path and digest public."""
    client = bound_profile_client(ctx)
    source = source_path.absolute()
    secret = bytearray(GOOGLE_CLIENT_SECRET_MAX_BYTES + 1)
    try:
        with source.open("rb") as stream:
            byte_count = stream.readinto(secret)
    except OSError as error:
        wipe_google_secret(secret)
        raise google_refusal(
            GoogleAuthValidationError(
                translated_message="cli.config.google.detail.client_json_unreadable",
                context={"path": str(source), "error_type": type(error).__name__},
            ),
        ) from None
    if byte_count > GOOGLE_CLIENT_SECRET_MAX_BYTES:
        wipe_google_secret(secret)
        raise google_refusal(
            GoogleAuthValidationError(
                translated_message="cli.config.google.detail.client_json_schema_invalid",
                context={"path": str(source), "error_type": "ValidationError"},
            ),
        ) from None
    del secret[byte_count:]
    if not secret:
        wipe_google_secret(secret)
        raise google_refusal(
            GoogleAuthValidationError(
                translated_message="cli.config.google.detail.client_json_invalid",
                context={"path": str(source), "error_type": "JSONDecodeError"},
            ),
        ) from None
    try:
        request = GoogleRegisterRequest(
            profile_id=client.profile_id,
            client_json_path=str(source),
            client_json_sha256=sha256_hex(bytes(secret)),
        )
    except ValidationError:
        wipe_google_secret(secret)
        raise submitted_operation_error(
            GOOGLE_REGISTER_OPERATION_DEFINITION_ID,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=None,
            effect=None,
        ) from None
    try:
        projection = run_google_configuration(ctx, request, result_type=GoogleRegisterProjection, secret=secret)
    finally:
        wipe_google_secret(secret)
    if type(projection) is not GoogleRegisterProjection:
        raise CliRefusedBoundaryError(RuntimeRefusalCode.INVALID_FRAME.value)
    return projection


def wipe_google_secret(secret: bytearray) -> None:
    """Erase the owned mutable secret after registration or refusal."""
    secret[:] = bytes(len(secret))
