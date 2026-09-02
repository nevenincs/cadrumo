"""Typed contracts shared by application diagnostic report producers.

The reports in this module remain independent from the diagnostic probes that
populate them.  Their forward references are rebuilt only when a repair probe
needs the heavy storage and wizard-status types, preserving the import-light
version surface.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field, model_validator

from ..core.models import STRICT_FROZEN_CONFIG
from ..core.operator_action_enums import (
    ActionArgumentSource,
    ActionArgumentStatus,
    ActionConditionality,
    ActionEvidenceProvenance,
    NoRecoveryOutcome,
)
from .errors import DiagnosticModelError
from .operator_actions.models import ActionArgumentBinding, ActionReference, ConditionEvidence, PreconditionVerdict

if TYPE_CHECKING:
    from ..adapters.persistence.storage.sql.secure_objects import SecureObjectNamespaceIntegrity
    from .wizard.status import WizardStatusReport


DiagnosticStatus = Literal["ok", "warn", "fail"]


class RegistryVersionSummary(BaseModel):
    """Stable registry summary suitable for version and repair surfaces.

    Built from
    :class:`~domain.calculations.registry.ValidatedRegistryAuthority` when
    registry detail is requested, then embedded in both :class:`CliVersionReport`
    and :class:`ConfigRepairReport`.

    Every count is an inventory tally -- a ``len()`` over a loaded collection --
    so it is non-negative by construction and declares that bound. The
    unavailable-registry branch reports zeroes rather than omitting the summary,
    which is why the counts default to ``0``.
    """

    model_config = STRICT_FROZEN_CONFIG

    available: bool
    registry_root: str
    modelo_count: int = Field(default=0, ge=0)
    revision_count: int = Field(default=0, ge=0)
    casilla_count: int = Field(default=0, ge=0)
    formula_count: int = Field(default=0, ge=0)
    revision_ids: tuple[str, ...] = ()
    error: str | None = None


class CliVersionReport(BaseModel):
    """Version payload rendered by root CLI version surfaces."""

    model_config = STRICT_FROZEN_CONFIG

    package_name: str
    package_version: str
    registry: RegistryVersionSummary


DiagnosticAudience = Literal["operator", "internal"]
"""Who can act on a check."""


class DiagnosticFinding(BaseModel):
    """One concrete, named sub-finding inside a :class:`DiagnosticCheck`."""

    model_config = STRICT_FROZEN_CONFIG

    summary: str
    detail: str | None = None
    requirement: Literal["required", "optional"] | None = None


class DiagnosticCheck(BaseModel):
    """One concrete config repair check with an unambiguous recovery outcome."""

    model_config = STRICT_FROZEN_CONFIG

    name: str
    status: DiagnosticStatus
    summary: str
    detail: str | None = None
    precondition_verdict: PreconditionVerdict | None = None
    audience: DiagnosticAudience = "operator"
    findings: tuple[DiagnosticFinding, ...] = ()

    @model_validator(mode="after")
    def _enforce_actionable_contract(self) -> DiagnosticCheck:
        if self.status in {"fail", "warn"}:
            if self.precondition_verdict is None:
                raise DiagnosticModelError(
                    f"DiagnosticCheck(status={self.status!r}) must populate `precondition_verdict`; "
                    "silent failing rows are forbidden",
                )
        elif self.precondition_verdict is not None:
            raise DiagnosticModelError("DiagnosticCheck(status='ok') must not carry a recovery outcome")
        return self


def diagnostic_action_verdict(
    *,
    condition_id: str,
    evidence_id: str,
    values: dict[str, str | bool | int],
    action_id: str,
    argument_bindings: tuple[ActionArgumentBinding, ...] = (),
    missing_argument_names: tuple[str, ...] = (),
) -> PreconditionVerdict:
    """Build one diagnostics-owned actionable failed-condition verdict."""
    return PreconditionVerdict(
        failed_condition_id=condition_id,
        evidence=(
            ConditionEvidence(
                condition_id=condition_id,
                evidence_id=evidence_id,
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                values=values,
            ),
        ),
        action=ActionReference(action_id=action_id),
        argument_bindings=argument_bindings,
        missing_argument_names=missing_argument_names,
        conditionality=(
            ActionConditionality.REQUIRES_ARGUMENTS if missing_argument_names else ActionConditionality.IMMEDIATE
        ),
    )


def diagnostic_no_recovery_verdict(
    *,
    condition_id: str,
    evidence_id: str,
    values: dict[str, str | bool | int],
    outcome: NoRecoveryOutcome,
) -> PreconditionVerdict:
    """Build one explicit diagnostics-owned closed recovery outcome."""
    from .operator_actions.preconditions import no_action_precondition_verdict

    return no_action_precondition_verdict(
        condition_id=condition_id,
        evidence_id=evidence_id,
        facts=values,
        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        outcome=outcome,
    )


def resolved_verdict_binding(argument_name: str, value: str | bool) -> ActionArgumentBinding:
    """Bind a concrete diagnostics fact to one catalogue argument."""
    return ActionArgumentBinding(
        argument_name=argument_name,
        status=ActionArgumentStatus.RESOLVED,
        value=value,
        source=ActionArgumentSource.VERDICT_CONTEXT,
        source_key=argument_name,
    )


def missing_verdict_binding(argument_name: str) -> ActionArgumentBinding:
    """Declare one catalogue argument diagnostics cannot honestly supply."""
    return ActionArgumentBinding(
        argument_name=argument_name,
        status=ActionArgumentStatus.MISSING,
    )


class SecureObjectIntegrityReport(BaseModel):
    """Aggregated decryptability counts across every populated namespace."""

    model_config = STRICT_FROZEN_CONFIG

    namespaces: tuple[SecureObjectNamespaceIntegrity, ...] = ()
    readable_total: int = 0
    unreadable_total: int = 0


class ConfigRepairReport(BaseModel):
    """Composite report rendered by the bare ``aeat config repair`` command."""

    model_config = STRICT_FROZEN_CONFIG

    overall: DiagnosticStatus
    package_name: str
    package_version: str
    python_version: str
    log_file: str
    registry: RegistryVersionSummary
    setup: WizardStatusReport | None
    secure_objects: SecureObjectIntegrityReport
    checks: tuple[DiagnosticCheck, ...]


_models_rebuilt = False


def ensure_models_rebuilt() -> None:
    """Resolve deferred heavy-type forward references on repair report models."""
    global _models_rebuilt
    if _models_rebuilt:
        return
    from ..adapters.persistence.storage.sql.secure_objects import SecureObjectNamespaceIntegrity
    from .wizard.status import WizardStatusReport

    _model_rebuild_types = (SecureObjectNamespaceIntegrity, WizardStatusReport)
    SecureObjectIntegrityReport.model_rebuild(_types_namespace=locals())
    ConfigRepairReport.model_rebuild(_types_namespace={**globals(), **locals()})
    _models_rebuilt = True


class RegistryIntegrityReport(BaseModel):
    """Result of the opt-in full registry-validation probe."""

    model_config = STRICT_FROZEN_CONFIG

    registry: RegistryVersionSummary
    check: DiagnosticCheck
