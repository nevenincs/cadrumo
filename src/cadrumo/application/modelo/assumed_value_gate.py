"""Detection, finding and refusal for a declaration that still holds an assumed value.

A box the calculation holds but nobody is recorded as entering is an assumed
value, and the work form withholds the file on it until the filer confirms it:
padding cannot supply a required fact, and a zero or default the filer never
saw must not become a declared figure. One detection, the work form's own
(:func:`~cadrumo.application.modelo.work_form_assumed.assumed_fields`), serves
every stage, so the form and the backend cannot disagree about which boxes
wait.

Verification reports each unconfirmed box as one blocking finding that names
the box and keeps the return from verificado completo. Local filing and export
refuse with one typed reason whose door is the action that states the box
again. Neither the finding nor the refusal carries a value: the filer reads
the figure on the form, and a refusal travels further than the form does.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Final

from ...core.external_constants import OutputLanguage
from ...core.operator_action_enums import ActionEvidenceProvenance
from ...domain.modelos.errors import ModeloError
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from .action_errors import ModeloPreconditionErrorMixin
from .preconditions import ModeloPreconditionFailure, build_modelo_precondition_failure_for_scenario
from .work_form_assumed import assumed_fields
from .work_form_field_vocabulary import ModeloFormBindingAddressV1, ModeloFormCasillaAddressV1
from .work_form_service import load_modelo_work_form

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.modelos.calculation_revision import CalculationRevisionCatalogue
    from ...domain.modelos.protocols import (
        CalculationRevisionCatalogueRepositoryProtocol,
        VerificationReportCatalogueRepositoryProtocol,
    )
    from ...domain.modelos.work_unit import WorkUnit
    from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
    from .credit_resolution_repository import CreditResolutionReader
    from .work_form_models import ModeloFormField

#: The declaration the filer makes is theirs to state (LGT art. 119).
_ASSUMED_VALUE_LEGAL_REFS: Final[tuple[str, ...]] = ("ley-58-2003:art-119",)


class ModeloAssumedValueStage(StrEnum):
    """Operator leaf whose action an unconfirmed assumed value refuses."""

    VERIFY = "modelo.work.verify"
    FILE = "modelo.work.file"
    EXPORT = "modelo.export"


class ModeloAssumedValueUnconfirmedError(ModeloPreconditionErrorMixin, ModeloError):
    """Raised when a declaration still holds values nobody entered or confirmed."""


def unconfirmed_assumed_fields(
    work_unit: WorkUnit,
    *,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
    verification_repository: VerificationReportCatalogueRepositoryProtocol,
    credit_resolutions: CreditResolutionReader | None,
    operation: PinnedAuthorityOperation,
    calculation_catalogue: CalculationRevisionCatalogue | None = None,
) -> tuple[ModeloFormField, ...]:
    """The boxes of the work unit's current calculation that hold an assumed value, as its work form reads them.

    Verification passes the catalogue it read with its revision guard, so the gate judges that snapshot.
    """
    loaded = load_modelo_work_form(
        work_unit.bucket_id,
        work_unit.modelo,
        work_unit.filing_year,
        work_unit.period,
        operation=operation,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
        verification_repository=verification_repository,
        admission=None,
        # Only the boxes' origins are read; no words are rendered from this form.
        language=OutputLanguage.EN,
        credit_resolutions=credit_resolutions,
        calculation_catalogue=calculation_catalogue,
    )
    return assumed_fields(loaded.form)


def _box(field: ModeloFormField) -> str:
    address = field.address
    if isinstance(address, ModeloFormCasillaAddressV1):
        return str(address.casilla_id)
    return str(address.binding_id)


def _door_arguments(work_unit: WorkUnit, field: ModeloFormField) -> dict[str, str]:
    """What the door already knows: the declaration and the box, so the filer supplies only the value."""
    name = "binding_id" if isinstance(field.address, ModeloFormBindingAddressV1) else "casilla_id"
    return {"work_unit_id": work_unit.work_unit_id, name: _box(field)}


def _confirm_scenario(field: ModeloFormField) -> str:
    """The door that states this box again: its casilla's own value, or the override of the source it reads."""
    return "unconfirmed_source" if isinstance(field.address, ModeloFormBindingAddressV1) else "unconfirmed"


def assumed_value_unconfirmed_failure(
    work_unit: WorkUnit, field: ModeloFormField, *, count: int, stage: ModeloAssumedValueStage
) -> ModeloPreconditionFailure:
    """Build the declared verdict that sends the filer to state or confirm the box at ``stage``."""
    leaf = stage.value
    return build_modelo_precondition_failure_for_scenario(
        subject_leaf_key=leaf,
        scenario_id=f"{leaf}.assumed_value.{_confirm_scenario(field)}",
        evidence_id=f"{leaf}.assumed_value",
        evidence_values={
            "work_unit_id": work_unit.work_unit_id,
            "modelo": str(work_unit.modelo),
            "year": work_unit.filing_year,
            "box": _box(field),
            "unconfirmed_assumed_values": count,
            "confirmed": False,
        },
        provenance=ActionEvidenceProvenance.PERSISTED_STATE,
        action_argument_values=_door_arguments(work_unit, field),
        missing_action_arguments=("value",),
    )


def require_assumed_values_confirmed(
    work_unit: WorkUnit,
    assumed: tuple[ModeloFormField, ...],
    *,
    stage: ModeloAssumedValueStage,
) -> None:
    """Refuse to file or export a declaration that holds values the filer has not confirmed."""
    if not assumed:
        return
    # A box the filer types leads: stating it again is the confirmation.
    lead = next((field for field in assumed if _confirm_scenario(field) == "unconfirmed"), assumed[0])
    raise ModeloAssumedValueUnconfirmedError(
        translated_message="errors.refused.refused_modelo_assumed_value_unconfirmed",
        context={
            "modelo": str(work_unit.modelo),
            "filing_year": str(work_unit.filing_year),
            "unconfirmed_assumed_values": str(len(assumed)),
            "boxes": ", ".join(_box(field) for field in assumed),
            "stage": stage.value,
        },
        precondition_failure=assumed_value_unconfirmed_failure(work_unit, lead, count=len(assumed), stage=stage),
    )


def assumed_value_verification_findings(
    work_unit: WorkUnit, assumed: tuple[ModeloFormField, ...]
) -> tuple[tuple[ModeloVerificationFinding, ModeloPreconditionFailure], ...]:
    """One blocking finding per unconfirmed box, each with its verify verdict."""
    return tuple(
        (
            ModeloVerificationFinding(
                kind=ModeloVerificationFindingKind.BLOCKING_RULE,
                severity=ModeloVerificationFindingSeverity.BLOCKING,
                casilla_id=field.address.casilla_id if isinstance(field.address, ModeloFormCasillaAddressV1) else None,
                message_locale_key="application.modelo.findings.assumed_value_unconfirmed",
                message_facts={"box": _box(field)},
                legal_refs=_ASSUMED_VALUE_LEGAL_REFS,
            ),
            assumed_value_unconfirmed_failure(
                work_unit, field, count=len(assumed), stage=ModeloAssumedValueStage.VERIFY
            ),
        )
        for field in assumed
    )


__all__ = [
    "ModeloAssumedValueStage",
    "ModeloAssumedValueUnconfirmedError",
    "assumed_value_unconfirmed_failure",
    "assumed_value_verification_findings",
    "require_assumed_values_confirmed",
    "unconfirmed_assumed_fields",
]
