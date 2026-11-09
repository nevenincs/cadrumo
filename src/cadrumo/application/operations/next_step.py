"""The step a refused operation serves for putting the refusal right.

A refusal can name one thing the filer does next: creating a declaration that
does not exist yet, calculating one that has no calculation, opening one whose
own form says what it still lacks, filling in one profile detail the refusal
named, declaring the profile setup complete, opening the ledger movement
that stops a calculation, or recording the opening IVA balance a period's
carry reads. The step says which kind, what
it concerns and the words that offer it, so a frontend does what it already
knows for that kind and keeps no table of operator action identifiers. The kind
is closed; an address that cannot be run is refused when the step is built.

A profile step addresses the schema path the profile's own facts live at -
``activities.description`` - never a private wizard question id, because the
path is what a profile surface already addresses its own rows by.

The words are in the language the refusal's own sentence is in
(``refusal_words_language`` of the error detail that carries the step): the
detail words both when it is built.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Annotated, Final, Literal

from pydantic import BaseModel, Field, StringConstraints

from ...core.external_constants import OutputLanguage
from ...core.filing_year import FourDigitYear
from ...core.identity.hex_ids import WorkUnitId
from ...core.identity.transaction_ids import TransactionId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG

_Token = Annotated[str, StringConstraints(min_length=1, max_length=16, pattern=r"^[A-Za-z0-9]+$")]
_Words = Annotated[str, StringConstraints(min_length=1, max_length=512)]
#: A profile fact's own schema address: a section, a field, and the row index a
#: repeatable section's fact carries. Never a wizard question id. Public so a
#: producer choosing a step can ask whether a selector it holds is one, rather
#: than restating the shape or discovering it as a validation error.
PROFILE_FIELD_PATH_PATTERN: Final[str] = r"^[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+$"
MAX_PROFILE_FIELD_PATH_LENGTH: Final[int] = 128

_ProfilePath = Annotated[
    str,
    StringConstraints(min_length=3, max_length=MAX_PROFILE_FIELD_PATH_LENGTH, pattern=PROFILE_FIELD_PATH_PATTERN),
]


def is_profile_field_path(candidate: str) -> bool:
    """Whether ``candidate`` is a profile fact's own schema address."""
    return (
        len(candidate) <= MAX_PROFILE_FIELD_PATH_LENGTH
        and re.fullmatch(PROFILE_FIELD_PATH_PATTERN, candidate) is not None
    )


class OperationCreateWorkStepV1(BaseModel):
    """Create the declaration of one modelo, filing year and period."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["create_work"] = "create_work"
    modelo: _Token
    filing_year: FourDigitYear
    period_code: _Token
    words: _Words


class OperationCalculateWorkStepV1(BaseModel):
    """Calculate the declaration one work unit holds."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["calculate_work"] = "calculate_work"
    work_unit_id: WorkUnitId
    words: _Words


class OperationOpenWorkStepV1(BaseModel):
    """Open the declaration one work unit holds, where its own form says what it still lacks."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["open_work"] = "open_work"
    work_unit_id: WorkUnitId
    words: _Words


class OperationOpenProfileFieldStepV1(BaseModel):
    """Fill in one profile detail the refusal named, at the schema path it lives at."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["open_profile_field"] = "open_profile_field"
    path: _ProfilePath
    words: _Words


class OperationCompleteProfileSetupStepV1(BaseModel):
    """Declare the profile setup complete, which every filing-grade verb re-checks."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["complete_profile_setup"] = "complete_profile_setup"
    words: _Words


class OperationOpenMovementStepV1(BaseModel):
    """Open one ledger movement in the Libro, where the fact the refusal names is recorded."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["open_movement"] = "open_movement"
    transaction_id: TransactionId
    words: _Words


class OperationOpenIvaWalletOpeningBalanceStepV1(BaseModel):
    """Record the opening IVA balance the period's carry reads, in the IVA balance of that declaration.

    The balance is the wallet's own, addressed by the modelo, filing year and
    period whose carry the refusal could not settle; the window opens that
    declaration's IVA balance at its opening-balance entry.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["open_iva_wallet_opening_balance"] = "open_iva_wallet_opening_balance"
    modelo: _Token
    filing_year: FourDigitYear
    period_code: _Token
    words: _Words


type OperationNextStepV1 = Annotated[
    OperationCreateWorkStepV1
    | OperationCalculateWorkStepV1
    | OperationOpenWorkStepV1
    | OperationOpenProfileFieldStepV1
    | OperationCompleteProfileSetupStepV1
    | OperationOpenMovementStepV1
    | OperationOpenIvaWalletOpeningBalanceStepV1,
    Field(discriminator="kind"),
]
"""The step a refusal serves: a closed kind, what it concerns, and the words that offer it."""


type OperationNextStepWording = Callable[[OutputLanguage], OperationNextStepV1]
"""A step still to be worded: given the language of the refusal's own sentence, the step in that language."""


class OperationNextStepErrorMixin:
    """Carry the step a refusal serves, beside whatever else the error carries.

    It is mixed in ahead of the error's other mixins, so the error keeps its own
    registered code and typed verdict; the step is the one the producer chose
    where it raised, never derived from the verdict afterwards. It is held
    unworded and worded when the refusal's detail is built, in the language of
    that detail's own sentence.
    """

    def __init__(self, *args: object, next_step: OperationNextStepWording | None = None, **kwargs: object) -> None:
        """Initialize the parent error and retain the step's wording."""
        parent_init: Callable[..., None] = super().__init__
        parent_init(*args, **kwargs)
        self._operation_next_step = next_step

    def operation_next_step(self, language: OutputLanguage) -> OperationNextStepV1 | None:
        """The step the refusal serves worded in ``language``, or ``None`` when it names none."""
        return None if self._operation_next_step is None else self._operation_next_step(language)


def error_next_step(error: BaseException, language: OutputLanguage) -> OperationNextStepV1 | None:
    """The step ``error`` serves worded in ``language``, or ``None`` for an error that carries none."""
    if isinstance(error, OperationNextStepErrorMixin):
        return error.operation_next_step(language)
    return None


__all__ = [
    "MAX_PROFILE_FIELD_PATH_LENGTH",
    "PROFILE_FIELD_PATH_PATTERN",
    "OperationCalculateWorkStepV1",
    "OperationCompleteProfileSetupStepV1",
    "OperationCreateWorkStepV1",
    "OperationNextStepErrorMixin",
    "OperationNextStepV1",
    "OperationNextStepWording",
    "OperationOpenIvaWalletOpeningBalanceStepV1",
    "OperationOpenMovementStepV1",
    "OperationOpenProfileFieldStepV1",
    "OperationOpenWorkStepV1",
    "error_next_step",
    "is_profile_field_path",
]
