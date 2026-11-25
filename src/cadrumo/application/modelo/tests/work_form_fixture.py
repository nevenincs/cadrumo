"""Forms built by the real builder over the published registry and its layout, for application tests.

A form's ``held`` boxes carry the calculation's values; everything else is what
the registry declares for the revision the period selects.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from ....core.casilla_id import validated_casilla_id
from ....core.external_constants import OutputLanguage
from ....core.modelo_work_progress_state import ModeloWorkProgressState
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.tax_id_format import runtime_tax_id_format
from ....domain.filing.schema import ModeloValueKind
from ....domain.modelos.calculation_revision import CalculationRevision, CalculationRevisionState
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.verification_report import ModeloVerificationFinding
from ..calculation_note_gate import (
    NO_SOURCE_DISAGREEMENT_RESOLUTIONS,
    SourceDisagreementResolutions,
    calculation_screen_outdated,
)
from ..edit_admission import RESPONSIBLE_OWNER
from ..edit_models import (
    ModeloEditDomainRefusalV1,
    ModeloEditPermittedSurfaceEntryV1,
    ModeloEditRefusalCode,
    ModeloEditRefusedV1,
)
from ..work_form import build_modelo_work_form
from ..work_form_field_vocabulary import ModeloFormCasillaAddressV1
from ..work_form_models import (
    ModeloFormField,
    ModeloWorkForm,
)
from ..work_form_service import modelo_form_snapshot, modelo_work_form_load
from ..work_review import ModeloWorkProgress, ModeloWorkReview, build_modelo_work_review_casillas
from ..workbench_read import ModeloWorkbenchFormReadV1


def form_snapshot(operation: PinnedAuthorityOperation, modelo: str, year: int, code: str) -> RegistrySnapshot:
    period = Period.from_year_and_code(year, code)
    revision_id = str(operation.revision_for_context(modelo, filing_year=year, period=code).id)
    return modelo_form_snapshot(operation, ModeloCode(modelo), year, period, revision_id)


def built_form(
    operation: PinnedAuthorityOperation,
    modelo: str,
    year: int,
    code: str,
    *,
    held: Mapping[str, Decimal | str] | None = None,
    entered: frozenset[str] | None = None,
    lifecycle: CalculationRevisionState | None = None,
    findings: tuple[ModeloVerificationFinding, ...] = (),
    language: OutputLanguage = OutputLanguage.EN,
    revision: CalculationRevision | None = None,
    known_truths: Mapping[str, bool] | None = None,
    permitted_surface: tuple[ModeloEditPermittedSurfaceEntryV1, ...] | None = None,
    calculated: bool = False,
    resolutions: SourceDisagreementResolutions = NO_SOURCE_DISAGREEMENT_RESOLUTIONS,
) -> ModeloWorkForm:
    """Build a form whose ``held`` boxes carry the calculation's values; ``entered`` ``None`` is an unknown record.

    ``revision`` is the calculation the form shows, whose notes the form carries; ``None`` before any.
    Whether its screen is outdated is the calculation-note gate's own answer, as the form service asks it.
    ``known_truths`` are the filer's yes-or-no profile facts by boolean binding; ``None`` states none.
    ``permitted_surface`` is the edit admission's surface; ``None`` offers nothing for editing.
    ``calculated`` says the work unit has a calculation although no revision is shown: a computed box
    that holds nothing is then one the calculation could not work out.
    ``resolutions`` are the source disagreements the operator accepted; none by default.
    """
    snapshot = form_snapshot(operation, modelo, year, code)
    values = held or {}
    rows = build_modelo_work_review_casillas(snapshot=snapshot, revision=None, operation=operation)
    review = ModeloWorkReview(
        bucket_id="13000000-0000-4000-8000-000000000455",
        modelo=modelo,
        filing_year=year,
        period=Period.from_year_and_code(year, code),
        registry_revision_id=snapshot.revision.id,
        work_unit_id="e" * 64,
        calculation_revision_id=(
            "f" * 64
            if calculated and revision is None
            else None
            if revision is None
            else revision.calculation_revision_id
        ),
        lifecycle_state=lifecycle,
        verification_outcome=None,
        progress=ModeloWorkProgress(state=ModeloWorkProgressState.UNDEFINED),
        casillas=tuple(
            row.model_copy(update={"value": values[str(row.casilla_id)], "realised_kind": ModeloValueKind.LITERAL})
            if str(row.casilla_id) in values
            else row
            for row in rows
        ),
        findings=findings,
        blockers=(),
    )
    return build_modelo_work_form(
        review=review,
        snapshot=snapshot,
        layout=operation.form_layout(modelo, snapshot.revision.id),
        revision=revision,
        permitted_surface=permitted_surface,
        entered_casilla_ids=None if entered is None else frozenset(validated_casilla_id(item) for item in entered),
        overridden_binding_ids=None if entered is None else frozenset(),
        language=language,
        known_truths=known_truths,
        resolutions=resolutions,
        calculation_screen_outdated=revision is not None
        and calculation_screen_outdated(
            revision, modelo=modelo, filing_year=year, period=Period.from_year_and_code(year, code), operation=operation
        ),
    )


def uncalculated_review(
    snapshot: RegistrySnapshot, operation: PinnedAuthorityOperation, *, modelo: str, filing_year: int, period: Period
) -> ModeloWorkReview:
    """The review of a work unit that has no calculation yet: every box as the registry declares it."""
    return ModeloWorkReview(
        bucket_id="13000000-0000-4000-8000-000000000455",
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        registry_revision_id=snapshot.revision.id,
        work_unit_id="e" * 64,
        calculation_revision_id=None,
        lifecycle_state=None,
        verification_outcome=None,
        progress=ModeloWorkProgress(state=ModeloWorkProgressState.UNDEFINED),
        casillas=build_modelo_work_review_casillas(snapshot=snapshot, revision=None, operation=operation),
        findings=(),
        blockers=(),
    )


def form_casilla(form: ModeloWorkForm, casilla_id: str) -> ModeloFormField:
    return next(
        field
        for field in form.fields()
        if isinstance(field.address, ModeloFormCasillaAddressV1) and str(field.address.casilla_id) == casilla_id
    )


__all__ = ["built_form", "form_casilla", "form_snapshot", "uncalculated_review"]


def read_before_calculation(
    form: ModeloWorkForm,
    operation: PinnedAuthorityOperation,
    *,
    verified: bool = False,
    filed: bool = False,
    **offer_fields: Any,
) -> ModeloWorkbenchFormReadV1:
    """The public form read of a declaration whose edit door is refused until it is calculated."""
    return ModeloWorkbenchFormReadV1(
        load=modelo_work_form_load(form, verified=verified, filed=filed),
        admission=ModeloEditRefusedV1(
            refusal=ModeloEditDomainRefusalV1(
                code=ModeloEditRefusalCode.ADMISSION_DENIED,
                facts=("current_calculation_revision_id",),
                responsible_owner=RESPONSIBLE_OWNER,
                reconsideration_condition="calculate the declaration before editing it",
            )
        ),
        calculation_revision_id=None,
        verification_report_id=None,
        asks_m303_evidence=False,
        asks_modelo_390=False,
        registry_revision_id=form.registry_revision_id,
        tax_id_format=runtime_tax_id_format(authority=operation),
        **offer_fields,
    )
