"""Typed exception hierarchy for the calculations application layer.

These exceptions are raised by previous-filing, binding-prefill, IVA
compensation, and encrypted observation-repository services at the application
boundary. Every class inherits from :class:`~core.errors.CoreError`;
validation failures use :class:`~core.errors.CoreValidationError` so CLI
and API callers receive registry-backed envelopes instead of generic
``ValueError`` or ``TypeError`` failures.

Every refusal raised across this package carries a registered locale key plus
machine facts; no raise site authors an operator-facing sentence, so
``str(exc)`` renders the key and the prose is resolved once, per locale, at the
presentation boundary.

A narrow subset is additionally a *safety* disposition: the calculation
observed evidence whose contradiction cannot be resolved by choosing one side,
because either choice silently changes a declared amount. Those raise sites
attach a :class:`~application.operator_actions.PreconditionVerdict` whose
``no_recovery_outcome`` is :attr:`~core.NoRecoveryOutcome.SAFETY`, so the CLI
boundary projects an explicit "there is deliberately no recovery here" instead
of manufacturing a retry that would re-derive the same contradiction.

See Also:
    :mod:`application.calculations._binding_prefill`:
        Previous-filing binding readers that raise
        :exc:`BindingPrefillTypeError`.
    :mod:`application.calculations.iva_compensation_history`:
        Modelo 303 IVA compensation carry-forward readers that raise
        :exc:`IvaCompensationModeloError`.
    :mod:`application.calculations.observations_repository`:
        Encrypted observation storage that raises :exc:`ObservationKeyError`
        and :exc:`ObservationCasillaReferenceError`.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import TYPE_CHECKING

from ...core import ActionEvidenceProvenance, NoRecoveryOutcome
from ...core.errors.hierarchy import CoreError, CoreValidationError, TerminalPreconditionErrorMixin

if TYPE_CHECKING:
    from ..operator_actions import PreconditionVerdict

    _CalculationPreconditionErrorMixin = TerminalPreconditionErrorMixin[PreconditionVerdict]
else:
    _CalculationPreconditionErrorMixin = TerminalPreconditionErrorMixin


class CalculationRefusalPrecondition(StrEnum):
    """Closed failed-condition identities for calculation safety dispositions.

    Membership is deliberately narrow. A condition earns a place here only when
    the refusal reports two sources of the same declared amount that disagree,
    so no automatic remedy exists: resolving it means deciding which figure the
    taxpayer actually declared, which is an operator judgement made against
    AEAT's own record. An evidence-incomplete refusal an operator fixes by
    supplying better evidence is not a safety disposition and stays a plain
    typed refusal.
    """

    OFFICIAL_EVIDENCE_PRESERVED = "calculations.observations.official_evidence_preserved"
    M303_CARRY_DISPOSITION_CONSISTENT = "calculations.m303_carry.disposition_consistent"
    M303_CARRY_DERIVATION_CONSISTENT = "calculations.m303_carry.derivation_consistent"
    M303_CARRY_MATCHES_REGISTRY_FORMULA = "calculations.m303_carry.matches_registry_formula"


def calculation_no_recovery_verdict(
    condition: CalculationRefusalPrecondition,
    *,
    facts: Mapping[str, str | int | bool],
    outcome: NoRecoveryOutcome = NoRecoveryOutcome.SAFETY,
) -> PreconditionVerdict:
    """Return one explicitly non-actionable outcome for a calculation refusal.

    The facts name exactly what the two disagreeing sources reported; the closed
    outcome is what stops a downstream boundary from manufacturing a recovery
    command that would simply re-derive the same contradiction. No action is
    bound because none of these conditions has a safe automatic remedy.

    Args:
        condition: The calculation condition that failed.
        facts: Stable machine facts, never prose, describing the observation.
        outcome: The closed no-recovery reason. Defaults to
            :attr:`~core.NoRecoveryOutcome.SAFETY`.

    Returns:
        The :class:`~application.operator_actions.PreconditionVerdict` carrying
        the failed condition and its explicit no-recovery outcome.
    """
    from ..operator_actions import no_action_precondition_verdict

    return no_action_precondition_verdict(
        condition_id=condition.value,
        facts=facts,
        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        outcome=outcome,
    )


class IvaCompensationModeloError(CoreError):
    """Raised when a non-Modelo 303 observation is passed to IVA compensation history.

    The IVA compensation carry-forward pipeline is exclusively sourced from
    Modelo 303 filed observations. Passing any other modelo to
    :func:`~application.calculations.iva_compensation_history.iva_compensation_state_from_observation_envelope`,
    or
    :func:`~application.calculations.iva_compensation_history.iva_compensation_annual_summary_from_filed_observation`
    violates the calculation boundary contract.
    """


class BindingPrefillTypeError(CoreValidationError):
    """Raised when a binding selector field carries an unexpected runtime type.

    Binding selectors flow through pydantic with a union value type, so static
    analysis loses the per-key shape. This error is raised by the selector
    narrowing helpers in :mod:`application.calculations._binding_prefill`.
    It protects
    :func:`~application.calculations._binding_prefill.resolve_bindings_from_local_store`
    from selector values that do not match the expected ``int | str`` or
    ``str | tuple[str, ...]`` shape.
    """


class ObservationKeyError(CoreValidationError):
    """Raised when an observation key component fails its repository contract.

    The repository key for a ``(modelo, filing_year, period)`` triple must
    satisfy
    :func:`~adapters.persistence.storage.safe_repository_id` for string
    components and fall within the supported year range ``[2000, 2099]`` for
    the integer year component. The key builders in
    :mod:`application.calculations.observations_repository` raise this
    error instead of a bare :class:`ValueError` so failures propagate through
    the typed error registry and produce structured envelopes.
    """


class ObservationEvidenceDisplacementError(_CalculationPreconditionErrorMixin, CoreValidationError):
    """Raised when a non-official write would displace official AEAT evidence.

    A ``(modelo, filing_year, period)`` slot holding evidence observed from AEAT
    -- a captured justificante, a live Sede capture, a CSV register row -- is the
    only record of what the authority holds. Writing a locally-sourced
    observation into that slot replaces it, and the displaced evidence cannot be
    recovered through any path this repository exposes.

    Both non-official provenances are refused, for different reasons that the
    refusal message distinguishes. An operator-manual figure displacing captured
    evidence is a downgrade with no compensating gain. A local filing
    recalculation displacing it is the same downgrade wearing a plausible
    justification: if the recalculation is correct the operator must re-file with
    AEAT and re-pull, so the local figure is not the authority either way.

    The operator verb can override deliberately; the local filing flow cannot,
    because there is no situation in which it should silently win.
    """


class ObservationCasillaReferenceError(CoreValidationError):
    """Raised when a persisted filing observation names undeclared casillas.

    :class:`~application.calculations.CalculationObservationRepository`
    is the encrypted calculation-history substrate for cross-period and
    cross-modelo reads. It must not persist a
    :class:`~domain.calculations.registry.RegistryModeloObservation` whose
    casilla keys are only syntactically valid ``CasillaId`` strings; every key
    must be declared by the resolved
    :class:`~domain.calculations.registry.RegistrySnapshot` for that
    modelo, year, and period via
    :func:`~domain.calculations.registry.undeclared_casilla_ids`.
    """
