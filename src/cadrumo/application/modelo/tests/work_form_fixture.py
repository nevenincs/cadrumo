"""Forms built by the real builder over the published registry and its layout, for application tests.

A form's ``held`` boxes carry the calculation's values; everything else is what
the registry declares for the revision the period selects.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from ....core.casilla_id import validated_casilla_id
from ....core.external_constants import OutputLanguage
from ....core.modelo_work_progress_state import ModeloWorkProgressState
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.filing.schema import ModeloValueKind
from ....domain.modelos.calculation_revision import CalculationRevision, CalculationRevisionState
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.verification_report import ModeloVerificationFinding
from ..work_form import build_modelo_work_form
from ..work_form_models import ModeloFormCasillaAddressV1, ModeloFormField, ModeloWorkForm
from ..work_form_service import modelo_form_snapshot
from ..work_review import ModeloWorkProgress, ModeloWorkReview, build_modelo_work_review_casillas


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
) -> ModeloWorkForm:
    """Build a form whose ``held`` boxes carry the calculation's values; ``entered`` ``None`` is an unknown record.

    ``revision`` is the calculation the form shows, whose notes the form carries; ``None`` before any.
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
        calculation_revision_id=None if revision is None else revision.calculation_revision_id,
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
        permitted_surface=None,
        entered_casilla_ids=None if entered is None else frozenset(validated_casilla_id(item) for item in entered),
        overridden_binding_ids=None if entered is None else frozenset(),
        language=language,
    )


def form_casilla(form: ModeloWorkForm, casilla_id: str) -> ModeloFormField:
    return next(
        field
        for field in form.fields()
        if isinstance(field.address, ModeloFormCasillaAddressV1) and str(field.address.casilla_id) == casilla_id
    )


__all__ = ["built_form", "form_casilla", "form_snapshot"]
