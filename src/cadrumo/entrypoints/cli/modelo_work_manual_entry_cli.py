"""Behavior for the commands that enter one value of a declaration by hand.

``set-value`` types a value into a box the filer fills, ``override`` states the
value of an input over what its source supplies (or in place of a source that
supplied nothing, such as an earlier return that is not stored), and
``attest-no-amount`` states that a carry from an earlier filing holds no
amount, and ``attest-prior-value`` states the figure of a carry whose earlier
return the profile holds nowhere, so the statement stands in for that return.
Each reads the declaration's form, which admits the edit baseline,
reads the typed value through the address's own grammar, checks the staged
change, and applies it through the guarded edit only when the filer confirms
with ``--yes``. Applying one entry keeps every other value the filer entered.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

import typer
from pydantic import ValidationError

from cadrumo_client.commands.output import activate_subcommand_output_language
from cadrumo_client.commands.profile_binding import require_profile_client
from cadrumo_client.transport.frontend_client import FrontendClient

from ...application.modelo.action_errors import ModeloEditRefusedError, modelo_edit_refusal_error
from ...application.modelo.edit_apply_contracts import ModeloEditApplyPublicResultV1
from ...application.modelo.edit_contract import ModeloEditMutationFamily
from ...application.modelo.edit_models import (
    ModeloBindingEditIntentV1,
    ModeloEditBaselineV1,
    ModeloEditBindingAddressV1,
    ModeloEditBindingIntentKind,
    ModeloEditParsedValueV1,
    ModeloEditParseReason,
    ModeloEditParseRefusalV1,
    ModeloEditParseRequestV1,
    ModeloEditRefusedV1,
    ModeloEditScalarAddressV1,
    ModeloEditScalarIntentKind,
    ModeloEditSubmissionV1,
    ModeloEditValueAddressV1,
    ModeloEditWritableBindingOverrideSurfaceEntryV1,
    ModeloScalarEditIntentV1,
)
from ...application.modelo.edit_parsing import modelo_edit_address_grammar, parse_modelo_edit_lexeme
from ...application.modelo.edit_review_wording import edit_refusal_words, entry_read_back, grammar_data_type
from ...application.modelo.workbench_operations import ModeloEditPreflightProjectionV1
from ...application.modelo.workbench_projection import restore_modelo_workbench_form
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import output_language as active_output_language
from ...core.i18n.render import tr
from ...core.identity.documents import SpanishTaxIdFormat
from .common import emit_envelope
from .modelo_cli_support import resolve_explicit_or_active_bucket_id
from .modelo_work_manual_entry_payloads import WorkManualEntryResult
from .operation_modelo_carry_attestation import (
    apply_modelo_edit_for_cli,
    preflight_modelo_edit_for_cli,
    read_modelo_work_form_for_cli,
)

type ManualEntryIntent = Literal["set_typed_value", "set_override_value", "attest_no_amount", "attest_prior_value"]

_SET_VALUE_COMMAND = "modelo.work.set_value"
_OVERRIDE_COMMAND = "modelo.work.override"
_ATTEST_NO_AMOUNT_COMMAND = "modelo.work.attest_no_amount"
_ATTEST_PRIOR_VALUE_COMMAND = "modelo.work.attest_prior_value"


def _not_writable(address: ModeloEditValueAddressV1, language: OutputLanguage) -> typer.BadParameter:
    refusal = ModeloEditParseRefusalV1(address=address, reason=ModeloEditParseReason.ADDRESS_NOT_WRITABLE)
    return typer.BadParameter(edit_refusal_words(refusal, language))


def _scalar_address(casilla_id: str) -> ModeloEditScalarAddressV1:
    try:
        return ModeloEditScalarAddressV1.model_validate({"casilla_id": casilla_id.strip()})
    except ValidationError:
        raise typer.BadParameter(tr("cli.app.modelo.work.entry_casilla_unknown", casilla=casilla_id)) from None


def _binding_address(binding_id: str, row_identity: str | None = None) -> ModeloEditBindingAddressV1:
    try:
        return ModeloEditBindingAddressV1(
            binding_id=binding_id.strip(), row_identity=None if row_identity is None else row_identity.strip()
        )
    except ValidationError:
        raise typer.BadParameter(tr("cli.app.modelo.work.entry_binding_unknown", binding=binding_id)) from None


def _admitted_baseline(
    client: FrontendClient, work_unit_id: str, language: OutputLanguage
) -> tuple[ModeloEditBaselineV1, SpanishTaxIdFormat]:
    """The edit baseline the form read admitted, with the governed tax-identifier format it was read under."""
    projection = read_modelo_work_form_for_cli(client, work_unit_id=work_unit_id.strip(), language=language)
    if projection.admission_refusal is not None:
        raise modelo_edit_refusal_error(projection.admission_refusal.refusal)
    if projection.admitted_baseline is None:
        raise ModeloEditRefusedError()
    return projection.admitted_baseline.to_baseline(), restore_modelo_workbench_form(projection).tax_id_format


def _typed_value(
    baseline: ModeloEditBaselineV1,
    address: ModeloEditValueAddressV1,
    lexeme: str,
    *,
    tax_id_format: SpanishTaxIdFormat,
    language: OutputLanguage,
) -> tuple[ModeloEditParsedValueV1, str]:
    """Read ``lexeme`` through the grammar the baseline admitted for ``address``, and say it as the box shows it."""
    outcome = parse_modelo_edit_lexeme(
        ModeloEditParseRequestV1(address=address, entry_locale=language, lexeme=lexeme),
        baseline=baseline,
        tax_id_format=tax_id_format,
    )
    if isinstance(outcome, ModeloEditRefusedV1):
        raise typer.BadParameter(edit_refusal_words(outcome.refusal, language))
    grammar = modelo_edit_address_grammar(baseline, address)
    if grammar is None:
        raise _not_writable(address, language)
    return outcome, entry_read_back(outcome.value, data_type=grammar_data_type(grammar, address), language=language)


def _checked(review: ModeloEditPreflightProjectionV1) -> list[str]:
    """The check's findings in words, refusing the staged change the check refused."""
    if isinstance(review.outcome, ModeloEditRefusedV1):
        raise modelo_edit_refusal_error(review.outcome.refusal)
    return [finding.words for finding in review.findings]


def _result(
    baseline: ModeloEditBaselineV1,
    *,
    intent: ManualEntryIntent,
    address: ModeloEditValueAddressV1,
    value_text: str | None,
    findings: list[str],
    applied: ModeloEditApplyPublicResultV1 | None,
) -> WorkManualEntryResult:
    return WorkManualEntryResult(
        bucket_id=baseline.bucket_id,
        work_unit_id=baseline.work_unit_id,
        modelo=str(baseline.modelo),
        filing_year=baseline.filing_year,
        intent=intent,
        casilla_id=address.casilla_id if isinstance(address, ModeloEditScalarAddressV1) else None,
        binding_id=address.binding_id if isinstance(address, ModeloEditBindingAddressV1) else None,
        value_text=value_text,
        applied=applied is not None,
        findings=findings,
        receipt_id=None if applied is None else applied.receipt_id,
        calculation_revision_id=None if applied is None else applied.calculation_revision_id,
    )


def _lines(result: WorkManualEntryResult, *, command: str, command_words: str) -> list[str]:
    entry = result.casilla_id or result.binding_id
    lines = [
        f"operation	{command}",
        f"work_unit_id	{result.work_unit_id}",
        f"applied	{str(result.applied).lower()}",
        f"entry	{entry}	{result.value_text or '-'}",
        *(f"finding	{words}" for words in result.findings),
    ]
    if result.applied:
        lines.extend(
            (f"receipt_id	{result.receipt_id}", f"calculation_revision_id	{result.calculation_revision_id}")
        )
    else:
        lines.append(tr("cli.app.modelo.work.entry_confirm", command=command_words))
    return lines


def _settle(
    ctx: typer.Context,
    client: FrontendClient,
    submission: ModeloEditSubmissionV1,
    *,
    command: str,
    intent: ManualEntryIntent,
    address: ModeloEditValueAddressV1,
    command_words: str,
    value_text: str | None,
    confirmed: bool,
    language: OutputLanguage,
) -> None:
    """Check the staged change, apply it when confirmed, and emit what happened."""
    review = preflight_modelo_edit_for_cli(client, submission, language=language)
    findings = _checked(review)
    applied: ModeloEditApplyPublicResultV1 | None = None
    if confirmed:
        if any(finding.blocking for finding in review.findings):
            raise ModeloEditRefusedError()
        applied = apply_modelo_edit_for_cli(client, submission, language=language).projection
    result = _result(
        submission.baseline, intent=intent, address=address, value_text=value_text, findings=findings, applied=applied
    )
    lines = _lines(result, command=command, command_words=command_words)
    emit_envelope(ctx, command=command, result=result, lines=lines)


def _session(ctx: typer.Context, output_language: OutputLanguage | None) -> tuple[FrontendClient, OutputLanguage]:
    activate_subcommand_output_language(ctx, output_language)
    client = require_profile_client(ctx, expected_profile_id=UUID(resolve_explicit_or_active_bucket_id(None)))
    return client, OutputLanguage(active_output_language())


def work_set_value(
    ctx: typer.Context,
    work_unit_id: str,
    casilla_id: str,
    value: str,
    confirmed: bool = False,
    output_language: OutputLanguage | None = None,
) -> None:
    """Type a value into a box the filer fills, as the declaration's form takes it."""
    client, language = _session(ctx, output_language)
    baseline, tax_id_format = _admitted_baseline(client, work_unit_id, language)
    address = _scalar_address(casilla_id)
    parsed, value_text = _typed_value(baseline, address, value, tax_id_format=tax_id_format, language=language)
    submission = ModeloEditSubmissionV1(
        baseline=baseline,
        mutation_family=ModeloEditMutationFamily.CALCULATE,
        scalar_intents=(
            ModeloScalarEditIntentV1(
                address=address, kind=ModeloEditScalarIntentKind.SET_TYPED_VALUE, value=parsed.value
            ),
        ),
    )
    _settle(
        ctx,
        client,
        submission,
        command=_SET_VALUE_COMMAND,
        intent="set_typed_value",
        address=address,
        command_words=f"aeat app modelo work set-value {baseline.work_unit_id} {address.casilla_id} <value> --yes",
        value_text=value_text,
        confirmed=confirmed,
        language=language,
    )


def work_override(
    ctx: typer.Context,
    work_unit_id: str,
    binding_id: str,
    value: str,
    confirmed: bool = False,
    output_language: OutputLanguage | None = None,
) -> None:
    """State the value of an input over, or in place of, what its source supplies."""
    client, language = _session(ctx, output_language)
    baseline, tax_id_format = _admitted_baseline(client, work_unit_id, language)
    address = _binding_address(binding_id)
    parsed, value_text = _typed_value(baseline, address, value, tax_id_format=tax_id_format, language=language)
    submission = ModeloEditSubmissionV1(
        baseline=baseline,
        mutation_family=ModeloEditMutationFamily.CALCULATE,
        binding_intents=(
            ModeloBindingEditIntentV1(
                address=address, kind=ModeloEditBindingIntentKind.SET_OVERRIDE_VALUE, value=parsed.value
            ),
        ),
    )
    _settle(
        ctx,
        client,
        submission,
        command=_OVERRIDE_COMMAND,
        intent="set_override_value",
        address=address,
        command_words=f"aeat app modelo work override {baseline.work_unit_id} {address.binding_id} <value> --yes",
        value_text=value_text,
        confirmed=confirmed,
        language=language,
    )


def _row_words(address: ModeloEditBindingAddressV1) -> str:
    return "" if address.row_identity is None else f" --row {address.row_identity}"


def work_attest_no_amount(
    ctx: typer.Context,
    work_unit_id: str,
    binding_id: str,
    row_identity: str | None = None,
    confirmed: bool = False,
    output_language: OutputLanguage | None = None,
) -> None:
    """State that one carry from an earlier filing holds no amount, on one row where ``--row`` names it."""
    client, language = _session(ctx, output_language)
    baseline, _ = _admitted_baseline(client, work_unit_id, language)
    address = _binding_address(binding_id, row_identity)
    if not any(
        isinstance(entry, ModeloEditWritableBindingOverrideSurfaceEntryV1)
        and entry.binding_id == address.binding_id
        and ModeloEditBindingIntentKind.ATTEST_NO_AMOUNT in entry.allowed_intents
        for entry in baseline.permitted_surface
    ):
        raise _not_writable(address, language)
    submission = ModeloEditSubmissionV1(
        baseline=baseline,
        mutation_family=ModeloEditMutationFamily.CALCULATE,
        binding_intents=(
            ModeloBindingEditIntentV1(address=address, kind=ModeloEditBindingIntentKind.ATTEST_NO_AMOUNT),
        ),
    )
    _settle(
        ctx,
        client,
        submission,
        command=_ATTEST_NO_AMOUNT_COMMAND,
        intent="attest_no_amount",
        address=address,
        command_words=(
            f"aeat app modelo work attest-no-amount {baseline.work_unit_id} {address.binding_id}"
            f"{_row_words(address)} --yes"
        ),
        value_text=None,
        confirmed=confirmed,
        language=language,
    )


def work_attest_prior_value(
    ctx: typer.Context,
    work_unit_id: str,
    binding_id: str,
    value: str,
    row_identity: str | None = None,
    confirmed: bool = False,
    output_language: OutputLanguage | None = None,
) -> None:
    """State the figure of a carry whose earlier return the profile does not hold, on one row where ``--row`` names it.

    The check refuses the statement where that return is held, because the
    declaration then follows the return rather than the statement.
    """
    client, language = _session(ctx, output_language)
    baseline, tax_id_format = _admitted_baseline(client, work_unit_id, language)
    address = _binding_address(binding_id, row_identity)
    parsed, value_text = _typed_value(baseline, address, value, tax_id_format=tax_id_format, language=language)
    submission = ModeloEditSubmissionV1(
        baseline=baseline,
        mutation_family=ModeloEditMutationFamily.CALCULATE,
        binding_intents=(
            ModeloBindingEditIntentV1(
                address=address, kind=ModeloEditBindingIntentKind.ATTEST_PRIOR_VALUE, value=parsed.value
            ),
        ),
    )
    _settle(
        ctx,
        client,
        submission,
        command=_ATTEST_PRIOR_VALUE_COMMAND,
        intent="attest_prior_value",
        address=address,
        command_words=(
            f"aeat app modelo work attest-prior-value {baseline.work_unit_id} {address.binding_id} <value>"
            f"{_row_words(address)} --yes"
        ),
        value_text=value_text,
        confirmed=confirmed,
        language=language,
    )


__all__ = ["work_attest_no_amount", "work_attest_prior_value", "work_override", "work_set_value"]
