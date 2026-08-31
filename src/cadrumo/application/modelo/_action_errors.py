"""Typed exception vocabulary for modelo application actions.

The classes in this module are the stable application-layer errors raised by
modelo work-unit lifecycle, calculation, verification, filing, amendment,
external-import, and workflow-gate services. They all inherit from
:class:`cadrumo.domain.modelos.errors.ModeloError` so CLI and API error
boundaries can route them through the central error-code registry without
depending on the implementation module that raised them.

Most classes are deliberately thin taxonomy markers whose operator-facing code
and message key live in :mod:`cadrumo.core.errors.registry`. The richer
contracts are kept here when the exception must preserve domain context without
leaking it into rendered error payloads, as with
:class:`ModeloWorkflowGateError` and its private
:class:`~cadrumo.application.workflow.WorkflowResult`.

See Also:
    :mod:`cadrumo.application.modelo`:
        Public package facade for these action errors.
    :mod:`cadrumo.core.errors.registry`:
        Maps these exception classes to stable error codes and message keys.
    :mod:`cadrumo.application.modelo._workflow_gate`:
        Raises :class:`ModeloWorkflowGateError` after persisting an aborted
        workflow run.
    :mod:`cadrumo.application.modelo._profile_readiness_gate`:
        Raises :class:`ModeloProfileReadinessError` for filing-grade profile
        preflight failures.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import cast

from ...core.operator_action_enums import ActionEvidenceProvenance
from ...core.errors.not_found import CoreNotFoundError
from ...domain.modelos.errors import ModeloError
from ..operator_actions import PreconditionVerdict
from ..workflow.run_models import WorkflowResult
from ._preconditions import ModeloPreconditionFailure, build_modelo_precondition_failure_for_scenario

WORKFLOW_GATE_LEGAL_REFS: tuple[str, ...] = (
    "ley-58-2003:art-119",
    "ley-58-2003:art-120",
    "ley-58-2003:art-122",
)
"""Legal anchors attached to workflow-gate refusal observations.

The cross-period clean-state finding tests assert these ids remain present in
the workflow-gate provenance payload. They correspond to the Ley 58/2003
articles that frame declaration, self-assessment, and complementary declaration
flows.
"""


class WorkUnitNotFoundError(ModeloError, KeyError):
    """Raised when a work-unit lookup or mutation targets a missing id."""


class ModeloPreconditionErrorMixin:
    """Attach one locale-neutral application decision to a registered error."""

    def __init__(
        self,
        message: str | None = None,
        *,
        context: Mapping[str, object] | None = None,
        translated_message: str | None = None,
        precondition_failure: ModeloPreconditionFailure | None = None,
    ) -> None:
        parent_init = cast(Callable[..., None], super().__init__)
        parent_init(
            message,
            context=context,
            translated_message=translated_message,
        )
        self._precondition_failure = precondition_failure

    @property
    def precondition_failure(self) -> ModeloPreconditionFailure | None:
        """Return the failed-precondition carrier for a later transport."""
        return self._precondition_failure

    @property
    def terminal_precondition_verdict(self) -> PreconditionVerdict | None:
        """Expose the one application-owned verdict to the generic CLI boundary."""
        failure = self.precondition_failure
        return None if failure is None else failure.verdict


class WorkUnitAlreadyDiscardedError(ModeloPreconditionErrorMixin, ModeloError):
    """Raised when discard is invoked on a work unit already discarded."""


class WorkUnitMutationRefusedError(ModeloPreconditionErrorMixin, ModeloError):
    """Raised when a lifecycle mutation targets a rejected work-unit state."""


class CalculationRevisionNotFoundError(ModeloPreconditionErrorMixin, ModeloError, CoreNotFoundError):
    """Raised when a calculation revision lookup fails."""


class CalculationRevisionStateError(ModeloPreconditionErrorMixin, ModeloError):
    """Raised when a state transition is requested from an incompatible source state."""


class ModeloRecordNotFoundError(ModeloError, KeyError):
    """Raised when a filing record lookup fails."""


class VerificationReportNotFoundError(ModeloError, KeyError):
    """Raised when a verification report lookup fails."""


class AmendmentEvidenceMissingError(ModeloPreconditionErrorMixin, ModeloError):
    """Raised when the modelo-amend path lacks imported official evidence."""


def amendment_evidence_missing_precondition(
    *,
    work_unit_id: str,
    filing_record_id: str,
) -> ModeloPreconditionFailure:
    """Return the declared no-action refusal for an unattested amendment baseline."""
    return build_modelo_precondition_failure_for_scenario(
        subject_leaf_key="modelo.work.amend_wizard",
        scenario_id="modelo.work.amend_wizard.external_evidence.missing",
        evidence_id="modelo.work.amend_wizard.external_evidence",
        evidence_values={
            "work_unit_id": work_unit_id,
            "filing_record_id": filing_record_id,
            "external_evidence_present": False,
        },
        provenance=ActionEvidenceProvenance.PERSISTED_STATE,
    )


def modelo_work_wizard_retry_exhausted_precondition(
    *,
    work_unit_id: str,
    retry_limit: int,
) -> ModeloPreconditionFailure:
    """Return the declared no-action outcome after the wizard exhausts its retries."""
    return build_modelo_precondition_failure_for_scenario(
        subject_leaf_key="modelo.work.wizard",
        scenario_id="modelo.work.wizard.inputs.retry_exhausted",
        evidence_id="modelo.work.wizard.retry_limit",
        evidence_values={"work_unit_id": work_unit_id, "retry_limit": retry_limit},
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
    )


class AmendmentM303RectificativaMotiveError(ModeloError):
    """Raised when the closed M303 rectificativa motive is missing or inapplicable."""


class AmendmentTargetStateError(ModeloError):
    """Raised when the modelo-amend path targets a non-current filing record."""


class AmendmentKindNotPermittedError(ModeloError):
    """Raised when the requested amendment kind is not legally available for the period.

    AEAT's amendment mechanism changed over time: the unified autoliquidación
    rectificativa (LGT art. 120.4, RD 117/2024) replaced the dual
    complementaria/solicitud-de-rectificación regime (LGT art. 122.2 /
    art. 120.3) only from the period each modelo's own orden establishes (see
    :mod:`cadrumo.core.amendment_kind_regime`). Requesting ``rectificativa`` for
    a pre-adoption period, or ``complementaria`` for a modelo/period where
    rectificativa has replaced it as the ordinary correction mechanism, is
    refused rather than silently accepted or silently downgraded — the accepted
    kind set for the resolved period is always named in the refusal.
    """


class AmendmentComplementariaLiabilityDecreaseError(ModeloError):
    """Raised when a pre-rectificativa complementaria would decrease liability.

    Before the autoliquidación rectificativa unification (LGT art. 120.4), a
    self-filed ``complementaria`` (LGT art. 122.2) can only ever RAISE the
    taxpayer's own declared tax due (or lower a requested devolución): "los
    obligados tributarios podrán presentar autoliquidaciones complementarias"
    when the new autoliquidación yields "un importe a ingresar superior... o
    una cantidad a devolver inferior". A correction that LOWERS the declared
    liability is not a complementaria in law; it requires the separate
    ``solicitud de rectificación`` procedure (LGT art. 120.3, developed by RGAT
    art. 126-128). Filing a liability-decreasing correction as a
    complementaria would silently misrepresent which legal procedure the
    taxpayer used, so it is refused with guidance toward the correct
    procedure rather than silently accepted.
    """


class StoredCalculationDriftError(ModeloError):
    """Raised when a persisted calculation revision has drifted from its content-addressed id."""


class ExternalModeloImportError(ModeloError):
    """Raised when the external-filing import path cannot persist an imported baseline."""


class ModeloLocalObservationError(ModeloError):
    """Raised when an operator-supplied local observation cannot be persisted."""


class ModeloCrossPeriodCleanStateError(ModeloPreconditionErrorMixin, ModeloError):
    """Raised when a filing-grade workflow lacks clean prior-filing proof."""


class ModeloWorkflowGateError(ModeloError):
    """Raised when the workflow gate refuses an internal file transition.

    The constructor stores the live :class:`~cadrumo.application.workflow.WorkflowResult`
    on a private attribute and exposes it through :attr:`result`. The rendered
    error context contains only primitive machine codes (``abort_code`` and
    ``stage``), which keeps CLI JSON/text payloads stable while allowing
    telemetry and tests to inspect the full workflow run.

    See Also:
        :func:`cadrumo.application.modelo._workflow_gate.run_revision_workflow_gate`:
            Persists the workflow run and raises this error for aborted results.
        :func:`cadrumo.core.errors.render_error_text`:
            Renders the primitive context without serialising the live result.
    """

    def __init__(self, result: WorkflowResult) -> None:
        self._result = result
        reason = result.aborted_reason.value if result.aborted_reason is not None else "unknown"
        super().__init__(
            translated_message=str(result.summary_locale_key),
            context={
                "abort_code": reason,
                "stage": result.final_stage.value,
            },
        )

    @property
    def result(self) -> WorkflowResult:
        """Return the live :class:`~cadrumo.application.workflow.WorkflowResult` that triggered the abort."""
        return self._result

    @property
    def terminal_precondition_verdict(self) -> PreconditionVerdict:
        """Return the persisted terminal verdict without exposing the live run.

        The workflow-result model requires every aborted run to end in a failed
        step carrying this verdict.  Keeping the result private avoids a raw
        persistence-object leak through generic error context, while the CLI
        boundary can schema-resolve this exact application-owned decision.
        """
        verdict = self._result.steps[-1].precondition_verdict
        if verdict is None:  # defensive: WorkflowResult normally rejects this shape
            raise ValueError("aborted workflow gate result has no terminal precondition verdict")
        return verdict


class AmendmentOverrideCasillaError(ModeloError):
    """Raised when an amendment override targets an undeclared casilla id."""


class AmendmentVerificationRefusedError(ModeloError):
    """Raised when the corrected casilla map fails verification."""


class CalculationRegistryUnavailableError(ModeloError):
    """Raised when the registry snapshot for a work unit cannot be resolved."""


class ModeloAggregationBindingError(ModeloPreconditionErrorMixin, ModeloError):
    """Raised when bucket-derived aggregation bindings conflict with caller input."""


class ModeloRequiredBindingsMissingError(ModeloPreconditionErrorMixin, ModeloError):
    """Raised when Modelo 202 lifecycle work lacks required calculation bindings."""


class ModeloProfileReadinessError(ModeloPreconditionErrorMixin, ModeloError):
    """Raised when filing-grade modelo work starts with missing active-profile facts.

    Carries the declared precondition failure so the operator surface resolves
    the recovery from the scenario identity and its machine facts rather than
    from a rendered explanation.
    """


class M303FilingEvidenceError(ModeloPreconditionErrorMixin, ModeloError):
    """Raised when Modelo 303 filing-instance evidence fails its revision-time validation.

    Carries the declared precondition failure rather than a rendered
    explanation, so the operator surface resolves the recovery from the
    scenario identity and its machine facts.
    """


class CasillaProvenanceMissingError(ModeloError):
    """Raised when an engine-result casilla has no registry definition."""


class ModeloApplicabilityFilterError(ModeloError):
    """Raised when an unknown applicability filter name is encountered."""


class ModeloRefundElectionNotEligibleError(ModeloError):
    """Raised when an operator elects a Modelo 303 refund for an ineligible period.

    A non-REDEME taxpayer may request a negative Modelo 303 result back as a refund
    (devolución, Tipo de declaración ``D``) only in the last filing period of the
    year (the annual liquidación, Ley 37/1992 art. 116). Electing ``devolver`` for
    any earlier period is refused rather than silently downgraded to compensación —
    a silent downgrade would hide that the operator's refund request was discarded,
    and a silent upgrade would file a refund the law does not permit for the period.
    The fix is operator-driven: carry the credit forward (``compensar``), or make
    the election in the year's last period.
    """


class ModeloPaymentElectionIncompatibleError(ModeloError):
    """Raised when a non-default payment election contradicts the result sign."""


class ModeloPaymentElectionCapabilityRefusedError(ModeloError):
    """Raised when a canonical payment election lacks a grounded capability.

    ``CUENTA_CORRIENTE`` remains typed so its future capability does not fork
    the contract, but is refused until officially grounded. It never infers or
    reuses a charge account.
    """


class ModeloPriorDomiciliationElectionRefusedError(ModeloError):
    """Raised when a prior-direct-debit election lacks legal, registry, or U-proof authority."""


class ModeloRefundAccountMissingError(ModeloError):
    """Raised when a refund-disposition export has no refund account on file.

    When the determined disposition is a refund (devolución, ``D`` / ``V`` /
    ``X``) the fichero must carry the cuenta-devolución block AEAT pays into —
    the IBAN, or the SWIFT-BIC plus foreign-bank block for a non-SEPA account.
    If the operator's profile carries no refund account (no ``iban``), the
    export REFUSES rather than emitting an empty or partial DID block: an empty
    refund block produces a devolución fichero AEAT cannot pay — a silent,
    defective filing. The fix is operator-driven: configure a refund account on
    the profile, or carry the credit forward (``compensar``) instead of
    requesting a refund. This is the no-silent-under-declaration sibling of the
    election's eligibility refusal.
    """


class ModeloChargeAccountMissingError(ModeloError):
    """Raised when a domiciliación export has no charge account on file.

    A ``U`` declaration instructs AEAT to debit the taxpayer's account. The
    DID page therefore needs the separately recorded charge-account IBAN; a
    refund account is a destination for payments from AEAT and cannot satisfy
    a debit instruction. The export refuses rather than falling back to that
    separate account or writing an empty account page.
    """


class WorkUnitRevisionDivergenceError(ModeloError):
    """Raised when the registry's law-determined revision diverges from the work unit's pinned revision.

    This can only happen when the registry's law-mapping was corrected after the
    work unit was created (the creation gate now enforces resolver-equality), or
    for work units persisted before the strengthened creation gate landed.  The
    resolution is to re-create the work unit so its identity reflects the
    corrected law-determined revision.
    """


__all__ = [
    "WORKFLOW_GATE_LEGAL_REFS",
    "AmendmentComplementariaLiabilityDecreaseError",
    "AmendmentEvidenceMissingError",
    "AmendmentKindNotPermittedError",
    "AmendmentOverrideCasillaError",
    "AmendmentTargetStateError",
    "AmendmentVerificationRefusedError",
    "CalculationRegistryUnavailableError",
    "CalculationRevisionNotFoundError",
    "CalculationRevisionStateError",
    "CasillaProvenanceMissingError",
    "ExternalModeloImportError",
    "ModeloAggregationBindingError",
    "ModeloApplicabilityFilterError",
    "ModeloChargeAccountMissingError",
    "ModeloCrossPeriodCleanStateError",
    "ModeloLocalObservationError",
    "ModeloPaymentElectionCapabilityRefusedError",
    "ModeloPaymentElectionIncompatibleError",
    "ModeloProfileReadinessError",
    "ModeloRecordNotFoundError",
    "ModeloRefundAccountMissingError",
    "ModeloRefundElectionNotEligibleError",
    "ModeloRequiredBindingsMissingError",
    "ModeloWorkflowGateError",
    "StoredCalculationDriftError",
    "VerificationReportNotFoundError",
    "WorkUnitAlreadyDiscardedError",
    "WorkUnitMutationRefusedError",
    "WorkUnitNotFoundError",
    "WorkUnitRevisionDivergenceError",
    "amendment_evidence_missing_precondition",
    "modelo_work_wizard_retry_exhausted_precondition",
]
