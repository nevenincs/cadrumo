"""Load one declaration's editor form, and say what a recalculation changed on it.

The form is a function of four reads: the canonical work review, the revision's
declared form layout, the operator layer recorded on the current calculation
head and the current edit admission. This module reads the first three from the
caller's pinned authority and repositories, takes the admission the caller
already holds, and hands everything to the form builder. It decides nothing the
builder does not.

Whether a value was entered by the filer is only ever claimed from the recorded
operator layer. A head calculated before operator layers existed, or a head the
calculation catalogue no longer resolves, gives an unknown layer -- never an
empty one -- so the form can say it cannot tell rather than guess.

The change query compares two forms of the same declaration, typically the one
shown before an apply and the one read after it, and lists every field whose
value or origin moved, so the filer sees what their change did to the rest of
the declaration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from pydantic import BaseModel

from ...core.external_constants import OutputLanguage
from ...core.identity.bucket import BucketId
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period
from ...domain.modelos.calculation_revision import CalculationRevision, CalculationRevisionState
from ...domain.modelos.codes import ModeloCode
from ...domain.modelos.protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    VerificationReportCatalogueRepositoryProtocol,
)
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from .caller_context import caller_context_of
from .edit_models import ModeloEditAdmissionResultV1, ModeloEditAdmittedV1
from .work_form import build_modelo_work_form
from .work_form_models import (
    ModeloFormAddressV1,
    ModeloFormOrigin,
    ModeloFormScalar,
    ModeloFormText,
    ModeloWorkForm,
    address_key,
)
from .work_review import build_modelo_work_review

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.calculations.registry.schema import RegistrySnapshot

_VERIFIED_STATES: Final[frozenset[CalculationRevisionState]] = frozenset(
    {
        CalculationRevisionState.VERIFICADO_COMPLETO,
        CalculationRevisionState.PRESENTADO,
        CalculationRevisionState.PRESENTADO_SUPERSEDIDO,
    }
)
_FILED_STATES: Final[frozenset[CalculationRevisionState]] = frozenset(
    {CalculationRevisionState.PRESENTADO, CalculationRevisionState.PRESENTADO_SUPERSEDIDO}
)


class ModeloWorkFormLoadV1(BaseModel):
    """One declaration's form with how far its filing has got."""

    model_config = STRICT_FROZEN_CONFIG

    form: ModeloWorkForm
    verified: bool
    filed: bool


class ModeloFormValueChangeV1(BaseModel):
    """One field whose value or origin differs between two reads of a form."""

    model_config = STRICT_FROZEN_CONFIG

    address: ModeloFormAddressV1
    box: str | None
    label: ModeloFormText
    before: ModeloFormScalar
    after: ModeloFormScalar
    before_origin: ModeloFormOrigin | None
    after_origin: ModeloFormOrigin | None


def _head(
    calculation_revision_id: str | None, calculation_repository: CalculationRevisionCatalogueRepositoryProtocol
) -> tuple[bool, CalculationRevision | None]:
    """Return whether the head resolved, and the head; no calculation resolves to ``None``."""
    if calculation_revision_id is None:
        return True, None
    head = calculation_repository.load().get(calculation_revision_id)
    return head is not None, head


def modelo_form_snapshot(
    operation: PinnedAuthorityOperation, modelo: ModeloCode, filing_year: int, period: Period, revision_id: str
) -> RegistrySnapshot:
    """The snapshot a form reads its revision through, at the grade that revision declares.

    Asking every revision for filing grade would refuse an applicability-only
    one the filer can still open and inspect, so the form asks for what the
    revision actually claims, as the work review does.
    """
    grade = operation.revision(str(modelo), revision_id).effective_authority_grade
    return operation.snapshot(
        str(modelo), filing_year=filing_year, period=period.registry_token, revision_id=revision_id, grade=grade
    )


def load_modelo_work_form(
    bucket_id: BucketId,
    modelo: ModeloCode,
    filing_year: int,
    period: Period,
    *,
    operation: PinnedAuthorityOperation,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
    verification_repository: VerificationReportCatalogueRepositoryProtocol,
    admission: ModeloEditAdmissionResultV1 | None,
    language: OutputLanguage,
) -> ModeloWorkFormLoadV1:
    """Read one declaration's review, layout and operator layer and build its form.

    ``admission`` is the edit admission the caller holds for this declaration,
    or ``None`` when none was sought; a refused admission, or one for another
    work unit, offers nothing for editing.
    """
    review = build_modelo_work_review(
        bucket_id,
        modelo,
        filing_year,
        period,
        operation=operation,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
        verification_repository=verification_repository,
    )
    snapshot = modelo_form_snapshot(operation, modelo, filing_year, period, review.registry_revision_id)
    layout = operation.form_layout(str(modelo), review.registry_revision_id)
    resolved, head = _head(review.calculation_revision_id, calculation_repository)
    layer = caller_context_of(head).operator_layer if resolved else None
    surface = (
        admission.baseline.permitted_surface
        if isinstance(admission, ModeloEditAdmittedV1)
        and str(admission.baseline.work_unit_id) == str(review.work_unit_id)
        else None
    )
    form = build_modelo_work_form(
        review=review,
        snapshot=snapshot,
        layout=layout,
        revision=head,
        permitted_surface=surface,
        entered_casilla_ids=None if layer is None else frozenset(layer.casilla_ids()),
        overridden_binding_ids=None if layer is None else frozenset(layer.binding_overrides),
        language=language,
    )
    state = review.lifecycle_state
    return ModeloWorkFormLoadV1(form=form, verified=state in _VERIFIED_STATES, filed=state in _FILED_STATES)


def modelo_work_form_changes(before: ModeloWorkForm, after: ModeloWorkForm) -> tuple[ModeloFormValueChangeV1, ...]:
    """List every field whose value or origin differs between two forms of one declaration.

    Fields come in the later form's reading order, then any the later form no
    longer shows.
    """
    earlier = {address_key(field.address): field for field in before.fields()}
    later = {address_key(field.address): field for field in after.fields()}
    changes: list[ModeloFormValueChangeV1] = []
    for key, field in later.items():
        previous = earlier.get(key)
        if previous is not None and previous.value == field.value and previous.origin is field.origin:
            continue
        changes.append(
            ModeloFormValueChangeV1(
                address=field.address,
                box=field.box,
                label=field.label,
                before=None if previous is None else previous.value,
                after=field.value,
                before_origin=None if previous is None else previous.origin,
                after_origin=field.origin,
            )
        )
    changes.extend(
        ModeloFormValueChangeV1(
            address=field.address,
            box=field.box,
            label=field.label,
            before=field.value,
            after=None,
            before_origin=field.origin,
            after_origin=None,
        )
        for key, field in earlier.items()
        if key not in later
    )
    return tuple(changes)


__all__ = [
    "ModeloFormValueChangeV1",
    "ModeloWorkFormLoadV1",
    "load_modelo_work_form",
    "modelo_form_snapshot",
    "modelo_work_form_changes",
]
