"""Stage a statement that nothing is pending, or that there is none, as one edit of the declaration.

The work form serves a statement for every family of figures that holds no value and that the
filer can state holds nothing (:mod:`.work_form_carry_attestation`): an amount carried from an
earlier ejercicio, or the work-income boxes no payer certificate fills. A frontend that makes the
statement without drawing the form stages exactly what the form names, one ``attest_no_amount``
intent per binding, against the baseline its form read admitted, so the statement is checked and
applied by the edit contract like any change the window stages. A declaration with nothing left to
state is refused before anything is staged, in the words of the family asked about.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Final

from ...domain.calculations.registry.binding_absence_attestation import AbsenceAttestationFamily
from ...domain.modelos.errors import ModeloError
from .edit_contract import ModeloEditMutationFamily
from .edit_models import (
    ModeloBindingEditIntentV1,
    ModeloEditBaselineV1,
    ModeloEditBindingAddressV1,
    ModeloEditBindingIntentKind,
    ModeloEditSubmissionV1,
)
from .work_form_models import ModeloFormCarryAttestation

_WORDED_FAMILIES: Final[frozenset[AbsenceAttestationFamily]] = frozenset(
    {
        AbsenceAttestationFamily.RENTA_NEGATIVE_GENERAL_BASES_PENDING,
        AbsenceAttestationFamily.RENTA_TRABAJO_INCOME_NOT_STATED,
    }
)
if frozenset(AbsenceAttestationFamily) != _WORDED_FAMILIES:
    raise ValueError("every statement family needs the words of its nothing-open refusal")


class ModeloAbsenceStatementNothingOpenError(ModeloError):
    """The declaration holds no figure of the asked family that the statement could answer.

    Every figure already holds a value, from a stored earlier return, an entry or an earlier
    statement, or the declaration reads none. Nothing was staged.
    """

    def __init__(self, *, modelo: str, filing_year: int, family: AbsenceAttestationFamily) -> None:
        """Name the declaration the filer asked about, in the words of the family."""
        super().__init__(
            translated_message=(
                "application.modelo.errors.trabajo_income_nothing_open"
                if family is AbsenceAttestationFamily.RENTA_TRABAJO_INCOME_NOT_STATED
                else "application.modelo.errors.prior_carries_nothing_open"
            ),
            context={"modelo": modelo, "filing_year": filing_year},
        )


def absence_statement_submission(
    baseline: ModeloEditBaselineV1,
    attestations: Iterable[ModeloFormCarryAttestation],
    *,
    family: AbsenceAttestationFamily,
) -> ModeloEditSubmissionV1:
    """One ``attest_no_amount`` intent for each binding the form's statements of ``family`` name, against ``baseline``.

    Statements of another family are left out, so one family's wording never states another's figures.
    Raises :class:`ModeloAbsenceStatementNothingOpenError` when the form serves no statement of the
    family, so no empty edit is ever submitted.
    """
    binding_ids = sorted(
        {
            binding_id
            for attestation in attestations
            if attestation.family is family
            for binding_id in attestation.binding_ids
        }
    )
    if not binding_ids:
        raise ModeloAbsenceStatementNothingOpenError(
            modelo=str(baseline.modelo), filing_year=baseline.filing_year, family=family
        )
    return ModeloEditSubmissionV1(
        baseline=baseline,
        mutation_family=ModeloEditMutationFamily.CALCULATE,
        binding_intents=tuple(
            ModeloBindingEditIntentV1(
                address=ModeloEditBindingAddressV1(binding_id=binding_id),
                kind=ModeloEditBindingIntentKind.ATTEST_NO_AMOUNT,
            )
            for binding_id in binding_ids
        ),
    )


__all__ = ["ModeloAbsenceStatementNothingOpenError", "absence_statement_submission"]
