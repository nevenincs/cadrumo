"""State what earlier years left pending of a let property's interest and repairs, through the guarded edit.

LIRPF art. 23.1.a.1 carries the excess of interest and repairs over a property's rents to the four
following years, and anexo C.1 follows it by the ejercicio it arose in. The Modelo 100 keeps the property's
row and withholds its net yield until the filer states each origin year's carry on its opening column of the
row the calculation emitted. A persona states one total in ``pendiente_intereses_reparacion``: nothing
pending is the statement of no amount on every origin year's opening, made here through the registered form
read, edit check and edit apply the operator uses. An amount cannot be split by origin year, so it is
refused until the persona states it per origin year. A persona that omits the fact states nothing.
"""

from __future__ import annotations

from decimal import Decimal

from ...application.modelo.edit_apply_contracts import ModeloEditApplyPublicResultV1, ModeloEditApplySubmissionV1
from ...application.modelo.edit_contract import ModeloEditMutationFamily
from ...application.modelo.edit_models import (
    ModeloBindingEditIntentV1,
    ModeloEditBindingAddressV1,
    ModeloEditBindingIntentKind,
    ModeloEditRefusedV1,
    ModeloEditSubmissionV1,
)
from ...application.modelo.edit_operator_input import ModeloEditOperatorInputV2
from ...application.modelo.operation_shared import MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID
from ...application.modelo.workbench_operations import (
    MODELO_EDIT_PREFLIGHT_OPERATION_DEFINITION_ID,
    MODELO_WORK_FORM_OPERATION_DEFINITION_ID,
    ModeloEditPreflightProjectionV1,
    ModeloWorkbenchFormRequest,
)
from ...application.modelo.workbench_projection import ModeloWorkbenchFormProjectionV1
from ...application.user_profile.projections import record_to_path_values
from ...core.authority_grade import RegistryAuthorityGrade
from ...core.external_constants import OutputLanguage
from ...domain.calculations.registry.renta_inmueble_bindings import (
    RentaInmuebleOriginPart,
    renta_inmueble_origin_columns,
)
from ...domain.contribuyente.inmueble_facts import inmuebles_from_facts
from ...tests.personas import Persona, RentalProperty
from .persona_materialisation import PersonaMaterialisationError, PersonaWorld, load_profile_record, run_operation

_MODELO = "100"
_PERIOD = "0A"
_LANGUAGE = OutputLanguage.ES


def _row_identity(rental: RentalProperty, world: PersonaWorld) -> str:
    """The source identity of the profile row that holds ``rental``, found by its stated cadastral reference."""
    held = inmuebles_from_facts(record_to_path_values(load_profile_record(world)))
    keys = [item.clave for item in held if item.referencia_catastral == rental.referencia_catastral]
    if len(keys) != 1:
        raise PersonaMaterialisationError(f"{rental.id}: the profile holds {len(keys)} properties of its reference")
    return f"inmueble:{keys[0]}"


def _intents(rental: RentalProperty, world: PersonaWorld, year: int) -> tuple[ModeloBindingEditIntentV1, ...]:
    stated = rental.pendiente_intereses_reparacion
    if stated != Decimal(0):
        raise PersonaMaterialisationError(
            f"{rental.id}: pendiente_intereses_reparacion states {stated} as one total; anexo C.1 needs the "
            "pending amount stated per origin year, which this persona does not state"
        )
    revision = world.operation.snapshot(
        _MODELO, filing_year=year, period=_PERIOD, grade=RegistryAuthorityGrade.CALCULATION
    ).revision
    row = _row_identity(rental, world)
    openings = renta_inmueble_origin_columns(revision)[RentaInmuebleOriginPart.OPENING]
    return tuple(
        ModeloBindingEditIntentV1(
            address=ModeloEditBindingAddressV1(binding_id=binding.id, row_identity=row),
            kind=ModeloEditBindingIntentKind.ATTEST_NO_AMOUNT,
        )
        for _back, binding in sorted(openings.items())
    )


def attest_pending_rental_carries(persona: Persona, world: PersonaWorld, work_unit_id: str, year: int) -> bool:
    """State the persona's pending carry on the calculated Modelo 100 of ``year``; ``True`` when one was stated.

    Raises:
        PersonaMaterialisationError: When the form admits no edit or the check or the apply refuses.
    """
    stated = [rental for rental in persona.rental_properties if rental.pendiente_intereses_reparacion is not None]
    if not stated:
        return False
    form_read = run_operation(
        world,
        MODELO_WORK_FORM_OPERATION_DEFINITION_ID,
        ModeloWorkbenchFormRequest(profile_id=world.profile_id, work_unit_id=work_unit_id, output_language=_LANGUAGE),
        ModeloWorkbenchFormProjectionV1,
        subject=work_unit_id,
    )
    if form_read.admitted_baseline is None:
        raise PersonaMaterialisationError(f"{work_unit_id}: the form admitted no edit: {form_read.admission_refusal}")
    submission = ModeloEditSubmissionV1(
        baseline=form_read.admitted_baseline.to_baseline(),
        mutation_family=ModeloEditMutationFamily.CALCULATE,
        binding_intents=tuple(intent for rental in stated for intent in _intents(rental, world, year)),
    )
    staged = ModeloEditOperatorInputV2(
        submission=ModeloEditApplySubmissionV1.from_submission(submission), output_language=_LANGUAGE
    )
    review = run_operation(
        world,
        MODELO_EDIT_PREFLIGHT_OPERATION_DEFINITION_ID,
        staged,
        ModeloEditPreflightProjectionV1,
        subject=work_unit_id,
    )
    if isinstance(review.outcome, ModeloEditRefusedV1) or any(finding.blocking for finding in review.findings):
        raise PersonaMaterialisationError(f"{work_unit_id}: the check refused the stated rental carry: {review}")
    run_operation(
        world, MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID, staged, ModeloEditApplyPublicResultV1, subject=work_unit_id
    )
    return True


__all__ = ["attest_pending_rental_carries"]
