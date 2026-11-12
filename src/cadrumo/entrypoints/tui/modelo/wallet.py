"""The profile's IVA compensation balance, and the door that reads it and records what the filer states about it.

A declaration whose registry revision declares the carried-forward compensation
offers the balance. The balance is read by the registered balance operation for
a reference year; the filer can state an opening balance, correct one or
replace the carry by hand through the three registered recording operations.
Every figure, the receipt of every recording and every refusal sentence are the
application's own: this module holds the TUI's side of that journey, the door a
host binds to the runtime, and the shapes the screen draws. It adds up nothing,
carries nothing forward and words no tax statement.

A recording that is refused changed nothing and is shown as the application
refused it. A recording that fails after it was sent has an unknown outcome and
is never settled here as a refusal or a success.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from ....application.modelo.iva_wallet_balance_operation import ModeloIvaWalletBalanceProjection
from ....application.modelo.iva_wallet_correction_operation import ModeloIvaWalletCorrectionProjection
from ....application.modelo.iva_wallet_override_operation import ModeloIvaWalletOverrideProjection
from ....application.modelo.iva_wallet_refusal_profiles import IVA_WALLET_OVERRIDE_ACTION_ID
from ....application.modelo.iva_wallet_seed_operation import ModeloIvaWalletSeedProjection
from ....application.modelo.work_form_models import ModeloWorkForm
from ....application.operations.next_step import (
    OperationOpenIvaWalletOpeningBalanceStepV1,
    OperationOpenIvaWalletStepV1,
)
from ....application.operations.public_scalar import PublicDecimal
from ....core.operator_action_enums import ActionArgumentStatus
from ..refusal.served import ServedRefusalV1, refusal_ways

type IvaWalletReceiptV1 = (
    ModeloIvaWalletSeedProjection | ModeloIvaWalletCorrectionProjection | ModeloIvaWalletOverrideProjection
)
"""What a recording came back with, as the application released it."""


class IvaWalletActionKind(StrEnum):
    """The three recordings the application registers, in the order the screen offers them."""

    SEED = "seed"
    CORRECT = "correct"
    OVERRIDE = "override"


class IvaWalletEntryV1(BaseModel, frozen=True):
    """What the filer typed for one recording, before the application's own request validates it.

    ``reason`` is used by a correction and an override, ``evidence_locator`` by
    an override only; the door sends exactly what the kind takes.
    """

    kind: IvaWalletActionKind
    filing_year: int
    period_code: str
    amount: str
    reason: str = ""
    evidence_locator: str = ""


class IvaWalletOpeningV1(BaseModel, frozen=True):
    """Where a refusal's door opens the balance dialog, and the words that offer it.

    Everything is the refusal's: the recording it names, the period it names
    and, for an override, the amount the taxpayer's own records give. ``None``
    leaves the dialog's own default, the declaration's period. Nothing here is
    sent; the filer still states, checks and sends the recording.
    """

    words: str
    kind: IvaWalletActionKind = IvaWalletActionKind.SEED
    filing_year: int | None = None
    period_code: str | None = None
    amount: str = ""


class IvaWalletNotSentError(Exception):
    """The request failed the application's own validation, so nothing was sent and nothing changed."""


class IvaWalletRefusedError(Exception):
    """The application refused the read or the recording; a refused recording changed nothing.

    ``refusal`` is the refusal as served, ``None`` when it served nothing to show.
    """

    def __init__(self, refusal: ServedRefusalV1 | None) -> None:
        """Carry the refusal exactly as it was served."""
        super().__init__("iva_wallet_refused")
        self.refusal = refusal


@runtime_checkable
class ModeloIvaWalletDoorV1(Protocol):
    """What a host binds to the profile so the TUI can read the balance and record about it.

    Each method runs a registered operation to its settlement and blocks, so the
    screen calls it off the event loop. A refusal raises :class:`IvaWalletRefusedError`,
    a request the application's validation rejects raises :class:`IvaWalletNotSentError`,
    and any other failure of a recording means it may have been stored.
    """

    def read_balance(self, as_of_year: int) -> ModeloIvaWalletBalanceProjection:
        """Read the balance facts the application releases for the profile as of one year."""
        ...

    def record(self, entry: IvaWalletEntryV1) -> IvaWalletReceiptV1:
        """Send one recording and return the receipt the application released for it."""
        ...


def offers_iva_wallet(form: ModeloWorkForm | None) -> bool:
    """Whether the form served says the declaration offers the profile's IVA balance.

    The flag says nothing about the balance or whether a recording would be
    admitted: the operations answer those.
    """
    return form is not None and form.offers_iva_wallet


def wallet_opening(refusal: ServedRefusalV1 | None, form: ModeloWorkForm | None) -> IvaWalletOpeningV1 | None:
    """The door a refusal serves into this declaration's balance, or ``None`` when it serves none for it.

    The step is the refusal's own, as in the window: the opening-balance door
    is offered where the declaration shown keeps the balance of the modelo the
    step names, at the period the step names; the balance door only for the
    declaration it names. A refusal whose primary way out is the override
    opens the override, at the period and amount that way was served with.
    """
    if refusal is None or form is None or not form.offers_iva_wallet:
        return None
    step = refusal.next_step
    if isinstance(step, OperationOpenIvaWalletOpeningBalanceStepV1):
        if step.modelo != str(form.modelo):
            return None
        return IvaWalletOpeningV1(
            words=step.words, kind=IvaWalletActionKind.SEED, filing_year=step.filing_year, period_code=step.period_code
        )
    if isinstance(step, OperationOpenIvaWalletStepV1):
        if str(step.work_unit_id) != form.work_unit_id:
            return None
        return _override_opening(refusal, step.words)
    return None


def _override_opening(refusal: ServedRefusalV1, words: str) -> IvaWalletOpeningV1:
    """The balance door, opened on the override when the refusal's primary way out is the override."""
    primary = next((way for way in refusal_ways(refusal) if way.role == "primary"), None)
    if primary is None or str(primary.action_id) != IVA_WALLET_OVERRIDE_ACTION_ID:
        return IvaWalletOpeningV1(words=words)
    served = {
        binding.argument_name: binding.value
        for binding in primary.argument_bindings
        if binding.status is ActionArgumentStatus.RESOLVED and binding.value is not None
    }
    year, code, amount = served.get("filing_year"), served.get("period"), served.get("amount")
    return IvaWalletOpeningV1(
        words=words,
        kind=IvaWalletActionKind.OVERRIDE,
        filing_year=year if isinstance(year, int) and not isinstance(year, bool) else None,
        period_code=code if isinstance(code, str) else None,
        amount=amount.decimal if isinstance(amount, PublicDecimal) else amount if isinstance(amount, str) else "",
    )


__all__ = [
    "IvaWalletActionKind",
    "IvaWalletEntryV1",
    "IvaWalletNotSentError",
    "IvaWalletOpeningV1",
    "IvaWalletReceiptV1",
    "IvaWalletRefusedError",
    "ModeloIvaWalletDoorV1",
    "offers_iva_wallet",
    "wallet_opening",
]
