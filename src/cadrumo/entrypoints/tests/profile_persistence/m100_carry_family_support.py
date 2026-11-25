"""Shared fixtures for the Modelo 100 prior-carry family-selection tests: the seeded facts, the open families and the production helpers that stage them."""

from __future__ import annotations

from ....adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from ....application.modelo.carry_family_selection import (
    select_prior_carry_attestations,
)
from ....application.modelo.edit_apply_contracts import ModeloEditApplySubmissionV1
from ....application.modelo.edit_models import (
    ModeloEditSubmissionV1,
)
from ....application.modelo.edit_operator_input import ModeloEditOperatorInputV2
from ....application.modelo.operation_shared import MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID
from ....application.modelo.work_form_models import ModeloFormCarryAttestation, ModeloWorkForm
from ....application.modelo.work_form_service import load_modelo_work_form
from ....application.operations.models import OperationRequest
from ....core.absence_attestation_family import PRIOR_CARRY_FAMILIES, AbsenceAttestationFamily
from ....core.authority_grade import RegistryAuthorityGrade
from ....core.errors.hierarchy import CadrumoError
from ....core.external_constants import OutputLanguage
from ....domain.calculations.registry.errors import FilingYearOutsideSupportEnvelopeError
from ....domain.calculations.registry.tests.published_authority import published_supported_filing_years
from ....domain.user_profile.tests.general_regime_facts import RENTA_UNMARRIED_TAXPAYER_FACTS
from ....domain.user_profile.values import UserProfileFact
from ..modelo_operator_work_storage import SeededOperatorWork

FACTS = (UserProfileFact(path="tax_residence.ccaa", value="madrid"), *RENTA_UNMARRIED_TAXPAYER_FACTS)
FAMILIES = tuple(family for family in AbsenceAttestationFamily if family in PRIOR_CARRY_FAMILIES)
GENERAL, CAPITAL, GAINS = (
    AbsenceAttestationFamily.RENTA_NEGATIVE_GENERAL_BASES_PENDING,
    AbsenceAttestationFamily.RENTA_NEGATIVE_SAVINGS_CAPITAL_INCOME_PENDING,
    AbsenceAttestationFamily.RENTA_NEGATIVE_SAVINGS_GAINS_LOSSES_PENDING,
)


def renta_years() -> tuple[int, ...]:
    """The Modelo 100 years the registry support envelope admits at calculation grade."""
    support = published_supported_filing_years()
    assert support is not None
    admitted: list[int] = []
    for year in sorted(support.years):
        try:
            published_authority_operation().snapshot(
                "100", filing_year=year, period="0A", grade=RegistryAuthorityGrade.CALCULATION
            )
        except FilingYearOutsideSupportEnvelopeError:
            continue
        admitted.append(year)
    return tuple(admitted)


def carry_form(work: SeededOperatorWork) -> ModeloWorkForm:
    unit = work.work_unit
    return load_modelo_work_form(
        unit.bucket_id,
        unit.modelo,
        unit.filing_year,
        unit.period,
        operation=work.operation,
        work_unit_repository=work.ports.work_unit_repository,
        calculation_repository=work.ports.calculation_repository,
        verification_repository=work.ports.verification_repository,
        admission=work.admit(),
        language=OutputLanguage.EN,
    ).form


def open_carry_families(work: SeededOperatorWork) -> set[AbsenceAttestationFamily]:
    return {item.family for item in carry_form(work).carry_attestations if item.family in PRIOR_CARRY_FAMILIES}


def choose_carries(
    work: SeededOperatorWork,
    *,
    families: tuple[AbsenceAttestationFamily, ...] = (),
    offered: tuple[ModeloFormCarryAttestation, ...] | None = None,
) -> tuple[ModeloFormCarryAttestation, ...]:
    return select_prior_carry_attestations(
        work.baseline(),
        carry_form(work).carry_attestations if offered is None else offered,
        families=families,
    )


def apply_statement(work: SeededOperatorWork, submission: ModeloEditSubmissionV1) -> CadrumoError | None:
    """Apply the staged statement as the command line submits it; the apply refusal."""
    return work.execute(
        OperationRequest(
            definition_id=MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID,
            subject_ref=work.work_unit_id,
            payload=ModeloEditOperatorInputV2(
                submission=ModeloEditApplySubmissionV1.from_submission(submission), output_language=OutputLanguage.EN
            ),
        )
    )


def first_carry_box(work: SeededOperatorWork, binding_id: str) -> str:
    boxes = [
        field.box
        for field in carry_form(work).fields()
        if field.box is not None and field.bindings and field.bindings[0].binding_id == binding_id
    ]
    assert boxes
    return boxes[0]
