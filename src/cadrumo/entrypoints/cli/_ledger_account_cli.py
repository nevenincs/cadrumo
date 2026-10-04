"""``app ledger account``: set up the taxpayer's own bank accounts.

Account numbers never travel as command arguments. The IBAN, and for an account
outside the SEPA zone its SWIFT-BIC and foreign-bank block, arrive through one
bounded strict-JSON machine-secret channel (``--secrets-stdin`` or
``--secrets-fd``) or through no-echo prompts on a real console. Every output
shows an account by its mask and its ``own_account_id`` only.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

import typer
from pydantic import SecretStr

from ...application.ledger.own_account_operation import (
    LEDGER_OWN_ACCOUNT_OPERATION_DEFINITION_ID,
    LedgerOwnAccountRequest,
    LedgerOwnAccountResult,
    OwnAccountProjection,
)
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...core.bucket_pointer import require_active_bucket_id
from ...core.i18n.render import tr
from ...core.iban import normalise_iban
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.iva.sepa_marca import SepaMarca, derive_sepa_marca
from ...domain.transactions.own_accounts import OwnAccountHolding, OwnAccountRole
from ._ledger_account_payloads import (
    OwnAccountChangeResult,
    OwnAccountDesignationPayload,
    OwnAccountListResult,
    OwnAccountPayload,
    OwnAccountShowResult,
)
from .common import active_bucket_id_or_refuse, bad, emit_envelope
from .config.secure_input import (
    MachineSecretPayload,
    prompt_secret_no_echo,
    read_machine_secret_payload,
    select_machine_secret_channel,
)
from .registered_operation_contracts import RegisteredOperationCompletion
from .registered_operation_errors import invalid_completion_error
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import run_registered_operation


class OwnAccountAddSecrets(MachineSecretPayload):
    """Machine-channel account material for ``app ledger account add``.

    ``iban`` is required; the SWIFT-BIC and the foreign-bank block are needed only
    for an account outside the SEPA zone and are blank otherwise.
    """

    iban: SecretStr
    swift_bic: str = ""
    bank_name: str = ""
    bank_address: str = ""
    bank_city: str = ""
    bank_country_code: str = ""


class OwnAccountUpdateSecrets(MachineSecretPayload):
    """Machine-channel account material for ``app ledger account update``; absent fields stay as stored."""

    iban: SecretStr | None = None
    swift_bic: str | None = None
    bank_name: str | None = None
    bank_address: str | None = None
    bank_city: str | None = None
    bank_country_code: str | None = None


def _run(ctx: typer.Context, request: LedgerOwnAccountRequest) -> LedgerOwnAccountResult:
    """Run one exact-profile request and correlate its receipt with what was asked."""
    client = require_profile_client(ctx, expected_profile_id=UUID(require_active_bucket_id()))
    if request.profile_id != client.profile_id:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    completed: RegisteredOperationCompletion[LedgerOwnAccountResult] = run_registered_operation(
        client,
        request,
        definition_id=LEDGER_OWN_ACCOUNT_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=LedgerOwnAccountResult,
        request_version=1,
        result_version=1,
        timeout=120,
    )
    result = completed.projection
    expected_effect = OperationEffect.UPDATED if result.changed else OperationEffect.NONE
    names_account = request.own_account_id is not None or request.action == "add"
    if (
        result.profile_id != client.profile_id
        or result.action != request.action
        or completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not expected_effect
        or (request.own_account_id is not None and result.own_account_id != request.own_account_id)
        or (names_account and result.own_account_id is None)
        or (request.action in {"list", "show"} and result.changed)
    ):
        raise invalid_completion_error(completed)
    return result


def _profile_id() -> UUID:
    return UUID(active_bucket_id_or_refuse())


def _date_option(value: str | None, *, option: str) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise bad(tr("cli.ledger.account.errors.invalid_date", option=option)) from None


def _accounts(result: LedgerOwnAccountResult) -> tuple[OwnAccountPayload, ...]:
    return tuple(OwnAccountPayload.from_projection(account) for account in result.accounts)


def _designations(result: LedgerOwnAccountResult) -> tuple[OwnAccountDesignationPayload, ...]:
    return tuple(OwnAccountDesignationPayload.from_projection(item) for item in result.designations)


def _account_line(account: OwnAccountProjection) -> str:
    closed = "" if account.closed_on is None else f"\tclosed {account.closed_on.isoformat()}"
    return f"{account.own_account_id}\t{account.masked_iban}\t{account.currency}\t{account.label}{closed}"


def _designation_lines(result: LedgerOwnAccountResult) -> list[str]:
    return [f"{item.role.value}\t{item.modelo or 'all'}\t{item.own_account_id}" for item in result.designations]


def _emit_change(ctx: typer.Context, command: str, result: LedgerOwnAccountResult) -> None:
    lines = [_account_line(account) for account in result.accounts]
    lines.extend(_designation_lines(result))
    if not result.changed:
        lines.append(tr("cli.ledger.account.unchanged"))
    emit_envelope(
        ctx,
        command=command,
        result=OwnAccountChangeResult(
            own_account_id=result.own_account_id,
            changed=result.changed,
            accounts=_accounts(result),
            designations=_designations(result),
        ),
        lines=lines,
    )


def _prompted_add_secrets() -> OwnAccountAddSecrets:
    """Ask for the account material on a real console, without echo."""
    iban = prompt_secret_no_echo(tr("cli.ledger.account.prompts.iban"))
    if derive_sepa_marca(iban=normalise_iban(iban)) is not SepaMarca.RESTO_PAISES:
        return OwnAccountAddSecrets(iban=SecretStr(iban))
    return OwnAccountAddSecrets(
        iban=SecretStr(iban),
        swift_bic=prompt_secret_no_echo(tr("cli.ledger.account.prompts.swift_bic")),
        bank_name=prompt_secret_no_echo(tr("cli.ledger.account.prompts.bank_name")),
        bank_address=prompt_secret_no_echo(tr("cli.ledger.account.prompts.bank_address")),
        bank_city=prompt_secret_no_echo(tr("cli.ledger.account.prompts.bank_city")),
        bank_country_code=normalise_iban(iban)[:2],
    )


def account_add(
    ctx: typer.Context,
    label: str,
    holding: str,
    currency: str | None = None,
    opened_on: str | None = None,
    secrets_stdin: bool = False,
    secrets_fd: int | None = None,
) -> None:
    """Add one own account; its number arrives through the secret channel or a no-echo prompt."""
    profile_id = _profile_id()
    opened = _date_option(opened_on, option="--opened-on")
    selection = select_machine_secret_channel(secrets_stdin=secrets_stdin, secrets_fd=secrets_fd)
    secrets = (
        read_machine_secret_payload(OwnAccountAddSecrets, selection=selection)
        if selection is not None
        else _prompted_add_secrets()
    )
    result = _run(
        ctx,
        LedgerOwnAccountRequest(
            profile_id=profile_id,
            action="add",
            label=label,
            holding=OwnAccountHolding(holding),
            iban=secrets.iban.get_secret_value(),
            swift_bic=secrets.swift_bic,
            bank_name=secrets.bank_name,
            bank_address=secrets.bank_address,
            bank_city=secrets.bank_city,
            bank_country_code=secrets.bank_country_code,
            currency=currency,
            opened_on=opened,
        ),
    )
    _emit_change(ctx, "ledger.account.add", result)


def account_list(ctx: typer.Context) -> None:
    """List every own account by its mask, with the role designations."""
    result = _run(ctx, LedgerOwnAccountRequest(profile_id=_profile_id(), action="list"))
    lines = [_account_line(account) for account in result.accounts]
    lines.extend(_designation_lines(result))
    if not result.accounts:
        lines.append(tr("cli.ledger.account.none"))
    emit_envelope(
        ctx,
        command="ledger.account.list",
        result=OwnAccountListResult(accounts=_accounts(result), designations=_designations(result)),
        lines=lines,
    )


def account_show(ctx: typer.Context, own_account_id: str) -> None:
    """Show one own account by its mask, with the designations that name it."""
    result = _run(
        ctx,
        LedgerOwnAccountRequest(profile_id=_profile_id(), action="show", own_account_id=own_account_id),
    )
    (account,) = result.accounts
    emit_envelope(
        ctx,
        command="ledger.account.show",
        result=OwnAccountShowResult(
            account=OwnAccountPayload.from_projection(account),
            designations=_designations(result),
        ),
        lines=[_account_line(account), *_designation_lines(result)],
    )


def account_update(
    ctx: typer.Context,
    own_account_id: str,
    label: str | None = None,
    holding: str | None = None,
    currency: str | None = None,
    opened_on: str | None = None,
    secrets_stdin: bool = False,
    secrets_fd: int | None = None,
) -> None:
    """Replace the named details of one own account; account material comes only through the secret channel."""
    profile_id = _profile_id()
    opened = _date_option(opened_on, option="--opened-on")
    selection = select_machine_secret_channel(secrets_stdin=secrets_stdin, secrets_fd=secrets_fd)
    secrets = (
        read_machine_secret_payload(OwnAccountUpdateSecrets, selection=selection)
        if selection is not None
        else OwnAccountUpdateSecrets()
    )
    request_fields = {
        "label": label,
        "holding": None if holding is None else OwnAccountHolding(holding),
        "currency": currency,
        "opened_on": opened,
        "iban": None if secrets.iban is None else secrets.iban.get_secret_value(),
        "swift_bic": secrets.swift_bic,
        "bank_name": secrets.bank_name,
        "bank_address": secrets.bank_address,
        "bank_city": secrets.bank_city,
        "bank_country_code": secrets.bank_country_code,
    }
    if all(value is None for value in request_fields.values()):
        raise bad(tr("cli.ledger.account.errors.nothing_to_update", account=own_account_id))
    result = _run(
        ctx,
        LedgerOwnAccountRequest.model_validate(
            {"profile_id": profile_id, "action": "update", "own_account_id": own_account_id, **request_fields},
        ),
    )
    _emit_change(ctx, "ledger.account.update", result)


def account_close(ctx: typer.Context, own_account_id: str, closed_on: str) -> None:
    """Close one own account on a date; a closed account is kept, not deleted."""
    closed = _date_option(closed_on, option="--on")
    result = _run(
        ctx,
        LedgerOwnAccountRequest(
            profile_id=_profile_id(),
            action="close",
            own_account_id=own_account_id,
            closed_on=closed,
        ),
    )
    _emit_change(ctx, "ledger.account.close", result)


def account_remove(ctx: typer.Context, own_account_id: str) -> None:
    """Remove an own account no transaction references and no role designates."""
    result = _run(
        ctx,
        LedgerOwnAccountRequest(profile_id=_profile_id(), action="remove", own_account_id=own_account_id),
    )
    _emit_change(ctx, "ledger.account.remove", result)


def account_designate(ctx: typer.Context, own_account_id: str, role: str, modelo: str | None = None) -> None:
    """Designate one own account for the charge or refund role, for one modelo or for all."""
    result = _run(
        ctx,
        LedgerOwnAccountRequest(
            profile_id=_profile_id(),
            action="designate",
            own_account_id=own_account_id,
            role=OwnAccountRole(role),
            modelo=modelo,
        ),
    )
    _emit_change(ctx, "ledger.account.designate", result)


def account_undesignate(ctx: typer.Context, role: str, modelo: str | None = None) -> None:
    """Remove the designation of a role, for one modelo or for all."""
    result = _run(
        ctx,
        LedgerOwnAccountRequest(
            profile_id=_profile_id(),
            action="undesignate",
            role=OwnAccountRole(role),
            modelo=modelo,
        ),
    )
    _emit_change(ctx, "ledger.account.undesignate", result)


__all__ = [
    "OwnAccountAddSecrets",
    "OwnAccountUpdateSecrets",
    "account_add",
    "account_close",
    "account_designate",
    "account_list",
    "account_remove",
    "account_show",
    "account_undesignate",
    "account_update",
]
