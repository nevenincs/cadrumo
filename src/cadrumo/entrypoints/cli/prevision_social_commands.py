"""CLI presentation handlers for the pension contribution certificate operations."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import typer
from pydantic import ValidationError

from ...application.operations.public_scalar import PublicDecimal
from ...application.prevision_social_contribution.requests import (
    PrevisionSocialListRequest,
    PrevisionSocialRecordRequest,
    PrevisionSocialRemoveRequest,
)
from ...core.i18n.render import tr
from ...core.prevision_social import PrevisionSocialBeneficiario, PrevisionSocialClave, PrevisionSocialSubclave
from .common import active_bucket_id_or_refuse, bad, emit_envelope
from .decimal_parsing import parse_decimal_amount
from .operation_ledger_prevision_social import (
    list_prevision_social,
    record_prevision_social,
    remove_prevision_social,
)
from .prevision_social_options import PrevisionSocialSamePlanAnswer
from .prevision_social_results import PrevisionSocialRowPayload


def _profile_id() -> UUID:
    return UUID(active_bucket_id_or_refuse())


def _stated(value: object | None) -> str:
    return "" if value is None else str(value)


def _row_line(row: PrevisionSocialRowPayload) -> str:
    return (
        f"{row.clave}{_stated(row.subclave)}\t{row.issuer_ref}\t{_stated(row.plan_ref)}\t{row.issuer_name or ''}\t"
        f"amount={row.amount}\tbeneficiary={row.beneficiary}\tsame_plan={_stated(row.employer_same_plan)}\t"
        f"casilla={_stated(row.casilla_id)}\trevision={row.revision_id}"
    )


def _invalid() -> typer.BadParameter:
    return bad(tr("cli.app.ledger.prevision_social.invalid_input"))


def prevision_social_record(
    ctx: typer.Context,
    issuer_tax_id: str,
    ejercicio: int,
    clave: PrevisionSocialClave,
    amount: str,
    subclave: PrevisionSocialSubclave | None = None,
    beneficiary: PrevisionSocialBeneficiario = PrevisionSocialBeneficiario.TAXPAYER,
    employer_same_plan: PrevisionSocialSamePlanAnswer | None = None,
    issuer_name: str | None = None,
    plan_nif: str | None = None,
    plan_name: str | None = None,
    certificate_file: Path | None = None,
    evidence_sha256: str | None = None,
    expected_revision: str | None = None,
) -> None:
    """Record or correct the contribution one certificate states and present the stored row."""
    contribution = PublicDecimal(decimal=str(parse_decimal_amount(amount, label="--amount", signed=False)))
    try:
        request = PrevisionSocialRecordRequest(
            profile_id=_profile_id(),
            ejercicio=ejercicio,
            issuer_tax_id=issuer_tax_id,
            issuer_legal_name=issuer_name,
            plan_tax_id=plan_nif,
            plan_name=plan_name,
            clave=clave,
            subclave=subclave,
            amount=contribution,
            beneficiary=beneficiary,
            employer_contributed_to_same_plan=None if employer_same_plan is None else employer_same_plan.stated,
            evidence_fingerprint=evidence_sha256,
            source_path=None if certificate_file is None else str(certificate_file),
            source_directory=None if certificate_file is None else str(Path.cwd()),
            expected_revision_id=expected_revision,
        )
    except ValidationError:
        raise _invalid() from None
    result = record_prevision_social(ctx, request)
    emit_envelope(
        ctx,
        command="ledger.prevision_social.record",
        result=result,
        lines=(f"bucket\t{result.bucket_id}", _row_line(result.row), f"count\t{result.count}"),
    )


def prevision_social_list(ctx: typer.Context, ejercicio: int) -> None:
    """Read the stored contribution records of one ejercicio and present them without tax identifiers."""
    try:
        request = PrevisionSocialListRequest(profile_id=_profile_id(), ejercicio=ejercicio)
    except ValidationError:
        raise _invalid() from None
    result = list_prevision_social(ctx, request)
    emit_envelope(
        ctx,
        command="ledger.prevision_social.list",
        result=result,
        lines=(f"bucket\t{result.bucket_id}", f"count\t{result.count}", *(_row_line(row) for row in result.rows)),
    )


def prevision_social_remove(
    ctx: typer.Context,
    issuer_ref: str,
    ejercicio: int,
    clave: PrevisionSocialClave,
    expected_revision: str,
    subclave: PrevisionSocialSubclave | None = None,
    plan_ref: str | None = None,
) -> None:
    """Remove one contribution record against the revision a list showed."""
    try:
        request = PrevisionSocialRemoveRequest(
            profile_id=_profile_id(),
            ejercicio=ejercicio,
            issuer_ref=issuer_ref,
            plan_ref=plan_ref,
            clave=clave,
            subclave=subclave,
            expected_revision_id=expected_revision,
        )
    except ValidationError:
        raise _invalid() from None
    result = remove_prevision_social(ctx, request)
    emit_envelope(
        ctx,
        command="ledger.prevision_social.remove",
        result=result,
        lines=(
            f"bucket\t{result.bucket_id}",
            f"removed\t{result.clave}{_stated(result.subclave)}\t{result.issuer_ref}\t{_stated(result.plan_ref)}",
            f"count\t{result.count}",
        ),
    )
