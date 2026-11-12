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
from ....application.modelo.iva_wallet_seed_operation import ModeloIvaWalletSeedProjection
from ....application.modelo.work_form_models import ModeloWorkForm
from ..refusal.served import ServedRefusalV1

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


__all__ = [
    "IvaWalletActionKind",
    "IvaWalletEntryV1",
    "IvaWalletNotSentError",
    "IvaWalletReceiptV1",
    "IvaWalletRefusedError",
    "ModeloIvaWalletDoorV1",
    "offers_iva_wallet",
]
