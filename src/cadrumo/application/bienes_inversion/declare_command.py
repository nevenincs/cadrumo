"""Declaring a capital good from operator intent, rather than from a finished record.

``BienesInversionRegisterService.declare`` takes a
:class:`BienInversionIvaRecord` that is already valid. Someone has to build it,
and building it is not clerical: the operator supplies a disposal year and a
disposal regime as two separate answers, and neither is meaningful without the
other. That pairing rule lived in the CLI, which meant the register could only
be added to from one surface — and a second surface adding to it would have had
to restate the rule and hope it matched.

The refusal is typed rather than an interface error, because a half-declared
disposal is a fact about the declaration, not about how it was typed in. The
adapter maps it to its own message; a different frontend maps it differently.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, NonNegativeInt

from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.bienes_inversion.register import (
    BienesInversionIvaRegister,
    BienInversionDisposal,
    BienInversionDisposalRegime,
    BienInversionIvaRecord,
    BienInversionKind,
)
from .service import BienesInversionRegisterService


class BienInversionDisposalIncompleteError(ValueError):
    """Raised when exactly one half of a disposal was supplied.

    A disposal is a year AND a regime: the year alone does not say how the
    remaining window is imputed, and the regime alone does not say when. The
    error names which half is missing so a surface can point at the right
    input.
    """

    def __init__(self, *, missing: str) -> None:
        """Record which half of the disposal pair was omitted."""
        super().__init__(f"a bien de inversión disposal requires both a year and a regime; {missing} is missing")
        self.missing = missing


class BienInversionDeclarationCommand(BaseModel):
    """One operator's intent to track a capital good in the register."""

    model_config = STRICT_FROZEN_CONFIG

    identifier: str
    description: str
    acquisition_year: NonNegativeInt
    acquisition_ledger_id: str
    cuota_soportada: Decimal
    prorrata_inicial_pct: Decimal
    kind: BienInversionKind
    art108_elegible: bool = True
    asset_record_ref: str | None = None
    prorrata_sector_id: str | None = None
    disposal_year: NonNegativeInt | None = None
    disposal_regime: BienInversionDisposalRegime | None = None


class BienInversionDeclarationResultV1(BaseModel):
    """The persisted record and the register it now belongs to."""

    model_config = STRICT_FROZEN_CONFIG

    record: BienInversionIvaRecord
    updated_register: BienesInversionIvaRegister


def resolve_bien_inversion_disposal(
    *,
    disposal_year: int | None,
    disposal_regime: BienInversionDisposalRegime | None,
) -> BienInversionDisposal | None:
    """Pair a disposal year with its regime, or refuse a half-supplied one.

    Args:
        disposal_year: The year the good was transmitted, when it was.
        disposal_regime: How the remaining window is imputed, when disposed.

    Returns:
        The disposal, or ``None`` when neither half was supplied.

    Raises:
        BienInversionDisposalIncompleteError: When exactly one half is present.
    """
    if disposal_year is None and disposal_regime is None:
        return None
    if disposal_year is None:
        raise BienInversionDisposalIncompleteError(missing="year")
    if disposal_regime is None:
        raise BienInversionDisposalIncompleteError(missing="regime")
    return BienInversionDisposal(year=disposal_year, regime=disposal_regime)


def declare_bien_inversion(
    command: BienInversionDeclarationCommand,
    *,
    service: BienesInversionRegisterService | None = None,
) -> BienInversionDeclarationResultV1:
    """Build one register record from operator intent and persist it.

    Args:
        command: The operator's declaration.
        service: Injected register service; the active-profile one by default.

    Returns:
        The record as persisted, with the updated register.

    Raises:
        BienInversionDisposalIncompleteError: When only one half of a disposal
            was supplied.
    """
    record = BienInversionIvaRecord(
        identifier=command.identifier,
        description=command.description,
        acquisition_year=command.acquisition_year,
        cuota_soportada=command.cuota_soportada,
        prorrata_inicial_pct=command.prorrata_inicial_pct,
        kind=command.kind,
        art108_elegible=command.art108_elegible,
        asset_record_ref=command.asset_record_ref,
        acquisition_ledger_id=command.acquisition_ledger_id,
        prorrata_sector_id=command.prorrata_sector_id,
        disposal=resolve_bien_inversion_disposal(
            disposal_year=command.disposal_year,
            disposal_regime=command.disposal_regime,
        ),
    )
    register = (service if service is not None else BienesInversionRegisterService()).declare(record)
    return BienInversionDeclarationResultV1(record=record, updated_register=register)


__all__ = [
    "BienInversionDeclarationCommand",
    "BienInversionDeclarationResultV1",
    "BienInversionDisposalIncompleteError",
    "declare_bien_inversion",
    "resolve_bien_inversion_disposal",
]
