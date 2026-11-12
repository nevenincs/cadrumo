"""Modelo IVA wallet refusals and the Saldo de IVA doors they serve.

Every IVA-wallet readiness refusal of the Modelo 303 gate is raised here as a
locale-neutral :class:`ModeloIvaWalletReconciliationBlockedError`, carrying the
opening-balance entry where that is what settles it; :func:`iva_wallet_door`
names the work unit's Saldo de IVA at the boundary that knows it.
"""

from __future__ import annotations

from collections.abc import Generator, Mapping
from contextlib import contextmanager
from decimal import Decimal
from typing import Final, Never, override

from ...core.errors.hierarchy import InternalInvariantError
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import tr
from ...core.identity.hex_ids import WorkUnitId
from ...core.operator_action_enums import ActionEvidenceProvenance
from ...core.period import Period
from ...domain.calculations.registry.form_codes import form_for_role
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.iva_compensation.reconciliation import (
    IvaCompensationDecisionReason,
    IvaCompensationReconciliationDecision,
)
from ...domain.modelos.errors import ModeloError
from ..operations.next_step import (
    OperationNextStepErrorMixin,
    OperationNextStepWording,
    OperationOpenIvaWalletOpeningBalanceStepV1,
    OperationOpenIvaWalletStepV1,
)
from ..operator_actions.invariant_verdicts import internal_invariant_verdict
from .action_errors import ModeloPreconditionErrorMixin
from .iva_wallet_prior_period import prior_compensation_source_period
from .preconditions import (
    IVA_WALLET_OPENING_BALANCE_ACTION_ID,
    IVA_WALLET_OPENING_BALANCE_SCENARIOS,
    IVA_WALLET_OVERRIDE_ACTION_ID,
    IVA_WALLET_OVERRIDE_SCENARIOS,
    ModeloPreconditionFailure,
    build_modelo_precondition_failure,
)
from .work_form_wording import modelo_number, period_words


class ModeloIvaWalletReconciliationBlockedError(OperationNextStepErrorMixin, ModeloPreconditionErrorMixin, ModeloError):
    """Raised when Modelo 303 calculation is blocked by IVA wallet reconciliation.

    A refusal the filer puts right, not a failure: the carried compensation
    needs an authority they supply in the declaration's Saldo de IVA (the AEAT
    wallet captured, the amount declared on the previous return registered, or
    an override). :func:`iva_wallet_door` names that door where the work unit
    is known.
    """

    def __init__(
        self,
        *,
        translated_message: str,
        precondition_failure: ModeloPreconditionFailure,
        context: Mapping[str, object] | None = None,
        next_step: OperationNextStepWording | None = None,
    ) -> None:
        """Carry the reconciliation failure that blocked the modelo 303 calculation.

        ``translated_message`` is the user-facing refusal text, ``precondition_failure``
        identifies the specific IVA wallet mismatch that triggered the block,
        ``context`` carries any additional diagnostic fields for the caller, and
        ``next_step`` is the door the refusal offers for putting it right, where
        it names one.
        """
        super().__init__(
            context=context,
            translated_message=translated_message,
            precondition_failure=precondition_failure,
            next_step=next_step,
        )

    @property
    @override
    def precondition_failure(self) -> ModeloPreconditionFailure:
        """Return the required application-owned IVA-wallet refusal verdict."""
        failure = super().precondition_failure
        if failure is None:
            raise ModeloError(
                "IVA-wallet reconciliation refusal was raised without its precondition verdict",
            )
        return failure


ModeloIvaWalletReconciliationBlocked = ModeloIvaWalletReconciliationBlockedError


class ModeloIvaWalletAuthorityUnavailableError(ModeloIvaWalletReconciliationBlockedError):
    """Raised when the registry the wallet gate reads cannot be read for the work unit.

    Nothing the filer records puts this right, so it stays a failure and serves
    no door, while still being caught wherever a wallet block is.
    """


_OPEN_IVA_WALLET_LOCALE_KEY: Final = "application.modelo.iva_wallet.next_step.open"


def open_iva_wallet_step(work_unit_id: WorkUnitId) -> OperationNextStepWording:
    """Offer opening the Saldo de IVA of ``work_unit_id``, worded in the step's own language."""

    def worded(language: OutputLanguage) -> OperationOpenIvaWalletStepV1:
        return OperationOpenIvaWalletStepV1(
            work_unit_id=work_unit_id,
            words=tr(_OPEN_IVA_WALLET_LOCALE_KEY, locale=language.value),
        )

    return worded


@contextmanager
def iva_wallet_door(work_unit_id: WorkUnitId) -> Generator[None]:
    """Serve the Saldo de IVA of ``work_unit_id`` as the door of a wallet refusal raised inside.

    The gate's helpers refuse without knowing the work unit; the boundary that
    holds it names the door once, here. An unreadable registry is no refusal of
    the filer's and passes through unchanged.
    """
    try:
        yield
    except ModeloIvaWalletAuthorityUnavailableError:
        raise
    except ModeloIvaWalletReconciliationBlockedError as refused:
        message = refused.translated_message
        if message is None or refused.operation_next_step(OutputLanguage.ES) is not None:
            raise
        raise ModeloIvaWalletReconciliationBlockedError(
            translated_message=message,
            precondition_failure=refused.precondition_failure,
            context=refused.context,
            next_step=open_iva_wallet_step(work_unit_id),
        ) from refused


def blocked_iva_wallet_refusal(decision: IvaCompensationReconciliationDecision) -> tuple[str, str]:
    """Name WHY a wallet decision blocks, and the message that says it.

    Returns the code AND its translated-message key together, because the two
    cannot be chosen independently: every neighbouring refusal in this module
    states a specific code and selects the message written for that case, and a
    site that picked a specific code while keeping the generic template would
    put a machine token in the ``%{reason}`` slot of a sentence meant for a
    person. That is what the blocked refusal did -- an operator read the same
    sentence for a stale wallet as for evidence that existed and could not be
    interpreted.

    The persisted reason is a closed locale-neutral identity. Every blocking
    identity selects its own translated message, so calculate and export expose
    the same specific cause as the history surface without domain-authored prose.
    """
    if decision.reason_identity is IvaCompensationDecisionReason.LOCAL_EVIDENCE_UNREADABLE:
        return "local_evidence_unreadable", "application.iva_wallet.decision_reason.local_evidence_unreadable"
    if decision.reason_identity is IvaCompensationDecisionReason.NO_USABLE_AUTHORITY:
        return "no_usable_authority", "application.iva_wallet.decision_reason.no_usable_authority"
    if decision.reason_identity is IvaCompensationDecisionReason.FILED_HISTORY_REQUIRES_OVERRIDE:
        return (
            "filed_history_requires_override",
            "application.iva_wallet.decision_reason.filed_history_requires_override",
        )
    if decision.reason_identity is IvaCompensationDecisionReason.LOCAL_RECURRENCE_REQUIRES_OVERRIDE:
        return (
            "local_recurrence_requires_override",
            "application.iva_wallet.decision_reason.local_recurrence_requires_override",
        )
    if decision.reason_identity is IvaCompensationDecisionReason.STALE_WALLET_NO_LOCAL_RECURRENCE:
        return (
            "stale_wallet_no_local_recurrence",
            "application.iva_wallet.decision_reason.stale_wallet_no_local_recurrence",
        )
    if decision.reason_identity is IvaCompensationDecisionReason.STALE_WALLET_LOCAL_RECURRENCE_REQUIRES_OVERRIDE:
        return (
            "stale_wallet_local_recurrence_requires_override",
            "application.iva_wallet.decision_reason.stale_wallet_local_recurrence_requires_override",
        )
    if decision.reason_identity is IvaCompensationDecisionReason.WALLET_LOCAL_RECURRENCE_DIVERGENCE:
        return (
            "wallet_local_recurrence_divergence",
            "application.iva_wallet.decision_reason.wallet_local_recurrence_divergence",
        )
    if decision.reason_identity is IvaCompensationDecisionReason.LOCAL_CALCULATION_REFUND_UNDECIDED:
        return (
            "local_calculation_refund_undecided",
            "application.iva_wallet.decision_reason.local_calculation_refund_undecided",
        )
    if decision.reason_identity is IvaCompensationDecisionReason.LOCAL_CALCULATION_REDEME_UNSTATED:
        return (
            "local_calculation_redeme_unstated",
            "application.iva_wallet.decision_reason.local_calculation_redeme_unstated",
        )
    raise ValueError(
        f"blocked IVA wallet decision has non-blocking reason {decision.reason_identity.value!r}",
    )


_OPEN_OPENING_BALANCE_LOCALE_KEY: Final[str] = "application.modelo.iva_wallet.next_step.open_opening_balance"


def open_iva_wallet_opening_balance_step(*, modelo: str, period: Period) -> OperationNextStepWording:
    """Offer recording the opening IVA balance declared for ``period``, which the period after it carries."""

    def worded(language: OutputLanguage) -> OperationOpenIvaWalletOpeningBalanceStepV1:
        return OperationOpenIvaWalletOpeningBalanceStepV1(
            modelo=modelo,
            filing_year=period.filing_year,
            period_code=str(period.code),
            words=tr(
                _OPEN_OPENING_BALANCE_LOCALE_KEY,
                modelo=modelo_number(modelo, language),
                period=period_words(period, language),
                locale=language.value,
            ),
        )

    return worded


def _opening_balance_period(
    reason_code: str, carry_period: Period | None, carry_revision: ModeloRevision | None
) -> Period:
    """The period whose declared balance ``carry_period``'s carry reads, for a refusal the opening balance settles.

    A declared opening balance is the closing balance of the period it names,
    which the period after it carries, so the door names the period the carry
    reads rather than the refused one; the revision's own requirement says which.
    """
    if carry_period is None or carry_revision is None:
        raise InternalInvariantError(
            f"iva wallet refusal {reason_code} is settled by the opening balance of a period it did not name",
            precondition_verdict=internal_invariant_verdict("iva_wallet_refusal.opening_balance_period_named"),
        )
    source_period = prior_compensation_source_period(carry_revision, carry_period)
    if source_period is None:
        raise InternalInvariantError(
            f"iva wallet refusal {reason_code} names a carry whose revision reads no single earlier period",
            precondition_verdict=internal_invariant_verdict("iva_wallet_refusal.carry_reads_single_period"),
        )
    return source_period


def _wallet_action(
    reason_code: str,
    *,
    carry_period: Period | None,
    carry_revision: ModeloRevision | None,
    local_amount: Decimal | None,
) -> tuple[
    str | None,
    Mapping[str, str | int | bool | Decimal] | None,
    tuple[str, ...],
    OperationNextStepWording | None,
]:
    """The catalogue action settling ``reason_code``, its known arguments, those the taxpayer supplies, and its step."""
    if reason_code in IVA_WALLET_OPENING_BALANCE_SCENARIOS:
        balance_period = _opening_balance_period(reason_code, carry_period, carry_revision)
        # The amount is the filer's own figure, so the action names it as still to supply.
        return (
            IVA_WALLET_OPENING_BALANCE_ACTION_ID,
            {"filing_year": balance_period.filing_year, "period": balance_period.registry_token},
            ("amount",),
            open_iva_wallet_opening_balance_step(modelo=form_for_role("iva.periodic"), period=balance_period),
        )
    if reason_code in IVA_WALLET_OVERRIDE_SCENARIOS:
        if carry_period is None:
            raise InternalInvariantError(
                f"iva wallet refusal {reason_code} is settled by an override of a period it did not name",
                precondition_verdict=internal_invariant_verdict("iva_wallet_refusal.override_period_named"),
            )
        known: dict[str, str | int | bool | Decimal] = {
            "filing_year": carry_period.filing_year,
            "period": carry_period.registry_token,
        }
        # A decision that records no amount from the taxpayer's records leaves it to them too.
        if local_amount is None:
            return IVA_WALLET_OVERRIDE_ACTION_ID, known, ("amount", "evidence_locator", "reason"), None
        return IVA_WALLET_OVERRIDE_ACTION_ID, {**known, "amount": local_amount}, ("evidence_locator", "reason"), None
    return None, None, (), None


def raise_iva_wallet_precondition(
    *,
    subject_leaf_key: str,
    reason_code: str,
    translated_message: str,
    evidence_values: Mapping[str, str | int | bool | Decimal],
    context: Mapping[str, object] | None = None,
    cause: BaseException | None = None,
    error_type: type[ModeloIvaWalletReconciliationBlockedError] = ModeloIvaWalletReconciliationBlockedError,
    carry_period: Period | None = None,
    carry_revision: ModeloRevision | None = None,
    local_amount: Decimal | None = None,
) -> Never:
    """Raise one locale-neutral IVA-wallet readiness refusal, or ``error_type`` where it is no refusal.

    ``carry_period`` is the Modelo 303 period whose carry the gate was settling,
    and ``carry_revision`` the edition calculating it. Where the reason is one
    the wallet's opening balance settles, the refusal carries the step that
    opens that entry and names the catalogue action that declares it, both for
    the earlier period whose balance the carry reads, so every frontend is
    offered the same remedy and following it settles the refusal. Where the reason
    is one an explicit override settles, the action names the period and
    ``local_amount``, the carry the taxpayer's own records give, and leaves the
    reason and the evidence to the taxpayer, and the amount too where the decision
    records none. A refusal for either kind of reason that does not name the
    period is an invariant breach. Nothing is written either way.
    """
    action_id, action_argument_values, missing_action_arguments, next_step = _wallet_action(
        reason_code, carry_period=carry_period, carry_revision=carry_revision, local_amount=local_amount
    )
    error = error_type(
        translated_message=translated_message,
        context=context,
        precondition_failure=build_modelo_precondition_failure(
            subject_leaf_key=subject_leaf_key,
            condition_id=f"{subject_leaf_key}.iva_wallet.ready",
            scenario_id=f"{subject_leaf_key}.iva_wallet.{reason_code}",
            evidence_id=f"{subject_leaf_key}.iva_wallet",
            evidence_values=evidence_values,
            provenance=ActionEvidenceProvenance.APPLICATION_STATE,
            action_id=action_id,
            action_argument_values=action_argument_values,
            missing_action_arguments=missing_action_arguments,
        ),
        next_step=next_step,
    )
    if cause is not None:
        raise error from cause
    raise error
