"""Give an amount for some carries of a statement that states the rest as nothing pending.

One statement of earlier-ejercicio carries may state absence for a family and an
amount for a carry of another, or for one carry of the same family. The filer
names an amount by the box the carry feeds, ``<box>=<amount>``, and the box is
resolved through the declaration's own form to the open carry binding that feeds
it, so a mistyped box can never state the wrong carry as nothing pending. Every
refusal comes before anything is staged.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from decimal import Decimal, InvalidOperation
from typing import Final

from ...domain.calculations.registry.ids import BindingId
from ...domain.modelos.errors import ModeloError
from ..operations.next_step import OperationNextStepErrorMixin, OperationNextStepWording
from .carry_attestation_submission import prior_carry_attestation_submission
from .carry_family_selection import open_declaration_step
from .edit_models import (
    ModeloBindingEditIntentV1,
    ModeloEditBaselineV1,
    ModeloEditBindingAddressV1,
    ModeloEditBindingIntentKind,
    ModeloEditSubmissionV1,
)
from .work_form_models import ModeloFormCarryAttestation, ModeloWorkForm
from .workbench_projection import PublicModeloWorkForm

_AMOUNT_INVALID_MESSAGE_KEY: Final[str] = "application.modelo.errors.prior_carries_amount_invalid"
_AMOUNT_NOT_A_CARRY_MESSAGE_KEY: Final[str] = "application.modelo.errors.prior_carries_amount_not_a_carry"
_AMOUNT_DUPLICATE_MESSAGE_KEY: Final[str] = "application.modelo.errors.prior_carries_amount_duplicate"
_CANONICAL_AMOUNT: Final[re.Pattern[str]] = re.compile(r"(?:0|[1-9][0-9]*)(?:\.[0-9]{1,2})?")
_BOX: Final[re.Pattern[str]] = re.compile(r"[0-9A-Za-z]{1,8}")


class ModeloPriorCarryAmountInvalidError(OperationNextStepErrorMixin, ModeloError):
    """An ``--amount`` is not ``<box>=<amount>`` with a positive amount written like ``1234.56``. Nothing was staged."""

    def __init__(self, *, baseline: ModeloEditBaselineV1, next_step: OperationNextStepWording) -> None:
        """Name the declaration the amount was given for."""
        super().__init__(
            translated_message=_AMOUNT_INVALID_MESSAGE_KEY,
            context={"modelo": str(baseline.modelo), "filing_year": baseline.filing_year},
            next_step=next_step,
        )


class ModeloPriorCarryAmountNotACarryError(OperationNextStepErrorMixin, ModeloError):
    """The box of an ``--amount`` is not an open carry of a family the statement names. Nothing was staged."""

    def __init__(self, *, baseline: ModeloEditBaselineV1, box: str, next_step: OperationNextStepWording) -> None:
        """Name the declaration and the box that feeds none of the named families' open carries."""
        super().__init__(
            translated_message=_AMOUNT_NOT_A_CARRY_MESSAGE_KEY,
            context={"modelo": str(baseline.modelo), "filing_year": baseline.filing_year, "box": box},
            next_step=next_step,
        )


class ModeloPriorCarryAmountDuplicateError(OperationNextStepErrorMixin, ModeloError):
    """One carry was given two amounts, whether by the same box twice or by two boxes it feeds. Nothing was staged."""

    def __init__(self, *, baseline: ModeloEditBaselineV1, box: str, next_step: OperationNextStepWording) -> None:
        """Name the declaration and the box whose carry already had an amount."""
        super().__init__(
            translated_message=_AMOUNT_DUPLICATE_MESSAGE_KEY,
            context={"modelo": str(baseline.modelo), "filing_year": baseline.filing_year, "box": box},
            next_step=next_step,
        )


def _parse_amount(
    option: str, *, baseline: ModeloEditBaselineV1, next_step: OperationNextStepWording
) -> tuple[str, Decimal]:
    box, separator, text = option.strip().partition("=")
    box, text = box.strip(), text.strip()
    if not separator or _BOX.fullmatch(box) is None or _CANONICAL_AMOUNT.fullmatch(text) is None:
        raise ModeloPriorCarryAmountInvalidError(baseline=baseline, next_step=next_step)
    try:
        amount = Decimal(text)
    except InvalidOperation:
        raise ModeloPriorCarryAmountInvalidError(baseline=baseline, next_step=next_step) from None
    if amount <= 0:
        raise ModeloPriorCarryAmountInvalidError(baseline=baseline, next_step=next_step)
    return box, amount


def resolve_prior_carry_amounts(
    baseline: ModeloEditBaselineV1,
    form: ModeloWorkForm | PublicModeloWorkForm,
    statements: Iterable[ModeloFormCarryAttestation],
    options: Iterable[str],
) -> Mapping[BindingId, Decimal]:
    """The amount given for each carry, by the open carry binding the box feeds on ``form``.

    Only the open carries of the families ``statements`` states can take an amount;
    any other box, a malformed or non-positive amount, and a second amount for one
    carry are refused.
    """
    next_step = open_declaration_step(baseline)
    open_carries = {binding_id for statement in statements for binding_id in statement.binding_ids}
    carry_of_box = {
        field.box: field.bindings[0].binding_id
        for field in form.fields()
        if field.box is not None and field.bindings and field.bindings[0].binding_id in open_carries
    }
    amounts: dict[BindingId, Decimal] = {}
    for option in options:
        box, amount = _parse_amount(option, baseline=baseline, next_step=next_step)
        binding_id = carry_of_box.get(box)
        if binding_id is None:
            raise ModeloPriorCarryAmountNotACarryError(baseline=baseline, box=box, next_step=next_step)
        if binding_id in amounts:
            raise ModeloPriorCarryAmountDuplicateError(baseline=baseline, box=box, next_step=next_step)
        amounts[binding_id] = amount
    return amounts


def prior_carry_statement_submission(
    baseline: ModeloEditBaselineV1,
    statements: tuple[ModeloFormCarryAttestation, ...],
    amounts: Mapping[BindingId, Decimal],
) -> ModeloEditSubmissionV1:
    """One edit that states each carry as nothing pending, or as its amount where one was given."""
    absence = prior_carry_attestation_submission(baseline, statements)
    intents = tuple(
        ModeloBindingEditIntentV1(
            address=ModeloEditBindingAddressV1(binding_id=intent.address.binding_id),
            kind=ModeloEditBindingIntentKind.SET_OVERRIDE_VALUE,
            value=amounts[intent.address.binding_id],
        )
        if intent.address.binding_id in amounts
        else intent
        for intent in absence.binding_intents
    )
    return absence.model_copy(update={"binding_intents": intents})


__all__ = [
    "ModeloPriorCarryAmountDuplicateError",
    "ModeloPriorCarryAmountInvalidError",
    "ModeloPriorCarryAmountNotACarryError",
    "prior_carry_statement_submission",
    "resolve_prior_carry_amounts",
]
