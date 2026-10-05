"""``app modelo m360``: declare, list and remove Modelo 360 solicitudes.

A solicitud's facts name people, addresses and tax identifiers, and a
representante account carries an IBAN, so a declaration never travels as
command arguments: it arrives as one JSON document in the ``solicitud`` field of
the bounded strict-JSON machine-secret channel (``--secrets-stdin`` or
``--secrets-fd``). Every output shows a solicitud by its year, destination,
holder and masked account only.
"""

from __future__ import annotations

from uuid import UUID

import pydantic
import typer
from pydantic import BaseModel, SecretStr

from ...application.filing.producer_snapshot_m360 import Modelo360ProfileFacts
from ...application.modelo.m360_solicitud_operation import (
    MODELO_360_SOLICITUD_OPERATION_DEFINITION_ID,
    Modelo360RepresentanteAccountInput,
    Modelo360SolicitudProjection,
    Modelo360SolicitudRequest,
    Modelo360SolicitudResult,
)
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...core.bucket_pointer import require_active_bucket_id
from ...core.i18n.render import tr
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.transactions.own_accounts import OwnAccountId
from ._modelo_m360_payloads import (
    Modelo360SolicitudChangeResult,
    Modelo360SolicitudListResult,
    Modelo360SolicitudPayload,
)
from .common import active_bucket_id_or_refuse, bad, emit_envelope
from .config.secure_input import MachineSecretPayload, read_machine_secret_payload, select_machine_secret_channel
from .registered_operation_contracts import RegisteredOperationCompletion
from .registered_operation_errors import invalid_completion_error
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import run_registered_operation


class Modelo360SolicitudSecrets(MachineSecretPayload):
    """Machine-channel input for ``app modelo m360 declare``: the solicitud document as JSON text."""

    solicitud: SecretStr


class _SolicitudDocument(BaseModel):
    """The declared solicitud: its facts and exactly one account, as the operator wrote them."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    facts: Modelo360ProfileFacts
    own_account_id: OwnAccountId | None = None
    representante_account: Modelo360RepresentanteAccountInput | None = None


def _run(ctx: typer.Context, request: Modelo360SolicitudRequest) -> Modelo360SolicitudResult:
    """Run one exact-profile request and correlate its receipt with what was asked."""
    client = require_profile_client(ctx, expected_profile_id=UUID(require_active_bucket_id()))
    if request.profile_id != client.profile_id:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    completed: RegisteredOperationCompletion[Modelo360SolicitudResult] = run_registered_operation(
        client,
        request,
        definition_id=MODELO_360_SOLICITUD_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=Modelo360SolicitudResult,
        request_version=1,
        result_version=1,
        timeout=120,
    )
    result = completed.projection
    expected_effect = OperationEffect.UPDATED if result.changed else OperationEffect.NONE
    if (
        result.profile_id != client.profile_id
        or result.action != request.action
        or result.filing_year != request.filing_year
        or completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not expected_effect
        or (request.action == "list" and result.changed)
    ):
        raise invalid_completion_error(completed)
    return result


def _profile_id() -> UUID:
    return UUID(active_bucket_id_or_refuse())


def _line(solicitud: Modelo360SolicitudProjection) -> str:
    account = solicitud.own_account_id or solicitud.masked_iban or "-"
    return (
        f"{solicitud.filing_year}\t{solicitud.pais_destino}\t{solicitud.causa_presentacion.value}"
        f"\t{solicitud.titular_en_calidad_de.value}\t{account}"
    )


def _payloads(result: Modelo360SolicitudResult) -> tuple[Modelo360SolicitudPayload, ...]:
    return tuple(Modelo360SolicitudPayload.from_projection(item) for item in result.solicitudes)


def _emit_change(ctx: typer.Context, command: str, filing_year: int, result: Modelo360SolicitudResult) -> None:
    lines = [_line(item) for item in result.solicitudes]
    if not result.changed:
        lines.append(tr("cli.modelo.m360.unchanged"))
    emit_envelope(
        ctx,
        command=command,
        result=Modelo360SolicitudChangeResult(
            filing_year=filing_year, changed=result.changed, solicitudes=_payloads(result)
        ),
        lines=lines,
    )


def m360_declare(
    ctx: typer.Context,
    filing_year: int,
    secrets_stdin: bool = False,
    secrets_fd: int | None = None,
) -> None:
    """Declare the solicitud for a filing year; its document arrives only through the secret channel."""
    profile_id = _profile_id()
    selection = select_machine_secret_channel(secrets_stdin=secrets_stdin, secrets_fd=secrets_fd)
    if selection is None:
        raise bad(tr("cli.modelo.m360.errors.secret_channel_required"))
    secrets = read_machine_secret_payload(Modelo360SolicitudSecrets, selection=selection)
    try:
        document = _SolicitudDocument.model_validate_json(secrets.solicitud.get_secret_value())
        request = Modelo360SolicitudRequest(
            profile_id=profile_id,
            action="declare",
            filing_year=filing_year,
            facts=document.facts,
            own_account_id=document.own_account_id,
            representante_account=document.representante_account,
        )
    except pydantic.ValidationError as error:
        # Input is hidden from these messages, so they never carry the declared facts.
        reasons = "; ".join(f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}" for item in error.errors())
        raise bad(tr("cli.modelo.m360.errors.invalid_document", reasons=reasons)) from None
    _emit_change(ctx, "modelo.m360.declare", filing_year, _run(ctx, request))


def m360_list(ctx: typer.Context) -> None:
    """List every declared solicitud by year, destination, holder and masked account."""
    result = _run(ctx, Modelo360SolicitudRequest(profile_id=_profile_id(), action="list"))
    lines = [_line(item) for item in result.solicitudes]
    if not result.solicitudes:
        lines.append(tr("cli.modelo.m360.none"))
    emit_envelope(
        ctx,
        command="modelo.m360.list",
        result=Modelo360SolicitudListResult(solicitudes=_payloads(result)),
        lines=lines,
    )


def m360_remove(ctx: typer.Context, filing_year: int) -> None:
    """Remove the solicitud declared for a filing year."""
    result = _run(
        ctx,
        Modelo360SolicitudRequest(profile_id=_profile_id(), action="remove", filing_year=filing_year),
    )
    _emit_change(ctx, "modelo.m360.remove", filing_year, result)


__all__ = ["Modelo360SolicitudSecrets", "m360_declare", "m360_list", "m360_remove"]
