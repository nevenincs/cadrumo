"""Stage the statement that no earlier-ejercicio carry is pending as one edit of the declaration.

The work form serves the statement for every carry of a declared family that
holds no value (:mod:`.work_form_carry_attestation`). A frontend that makes the
statement without drawing the form stages exactly what the form names, one
``attest_no_amount`` intent per carry, against the baseline its form read
admitted, so the statement is checked and applied by the edit contract like any
change the window stages. A declaration with nothing left to state is refused
before anything is staged.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Final

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

_NOTHING_OPEN_MESSAGE_KEY: Final[str] = "application.modelo.errors.prior_carries_nothing_open"


class ModeloPriorCarryNothingOpenError(ModeloError):
    """The declaration holds no carry from an earlier ejercicio that the statement could answer.

    Every carry already holds a value, from a stored earlier return, an entry or
    an earlier statement, or the declaration reads none. Nothing was staged.
    """

    def __init__(self, *, modelo: str, filing_year: int) -> None:
        """Name the declaration the filer asked about."""
        super().__init__(
            translated_message=_NOTHING_OPEN_MESSAGE_KEY,
            context={"modelo": modelo, "filing_year": filing_year},
        )


def prior_carry_attestation_submission(
    baseline: ModeloEditBaselineV1, attestations: Iterable[ModeloFormCarryAttestation]
) -> ModeloEditSubmissionV1:
    """One ``attest_no_amount`` intent for each carry the form's statements name, against ``baseline``.

    Raises :class:`ModeloPriorCarryNothingOpenError` when the form serves no
    statement, so no empty edit is ever submitted.
    """
    binding_ids = sorted({binding_id for attestation in attestations for binding_id in attestation.binding_ids})
    if not binding_ids:
        raise ModeloPriorCarryNothingOpenError(modelo=str(baseline.modelo), filing_year=baseline.filing_year)
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


__all__ = ["ModeloPriorCarryNothingOpenError", "prior_carry_attestation_submission"]
