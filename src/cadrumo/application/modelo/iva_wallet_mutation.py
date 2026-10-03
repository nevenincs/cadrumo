"""Contract shared by the operator-local IVA-wallet seed, override and correction operations."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from pydantic import Field

from ...core.decimal.grammar import try_parse_canonical_decimal
from ...core.operations import OperationEffect, profile_operation_subject
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ..operations.models import (
    OperationTerminalReceipt,
    require_succeeded_terminal_receipt,
)
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .iva_wallet_seed_ports import ModeloIvaWalletSeedPorts, ModeloIvaWalletSeedPortsFactory

IVA_WALLET_MUTATION_RESULT_MAX_BYTES = 16 * 1024
"""Encoded size ceiling of one wallet mutation's report and public projection."""

IvaWalletCanonicalAmount = Annotated[
    str,
    Field(
        min_length=1,
        max_length=128,
        pattern=r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]{1,2})?$",
    ),
]
"""Monetary text in the CLI's canonical two-decimal grammar."""

IvaWalletTaxpayerNif = Annotated[str, Field(min_length=1, max_length=32)]
"""The persisted wallet state's taxpayer NIF, as projected."""


def validate_iva_wallet_amount(value: str) -> str:
    """Keep monetary inputs and projections within the CLI's canonical grammar."""
    if try_parse_canonical_decimal(value, max_fraction_digits=2) is None:
        raise ValueError("wallet amounts must be canonical decimal text")
    return value


def bind_iva_wallet_profile_ports(
    factory: ModeloIvaWalletSeedPortsFactory,
    *,
    profile_id: str,
    operation: PinnedAuthorityOperation,
) -> ModeloIvaWalletSeedPorts:
    """Build the wallet repository bundle for one profile and reject a foreign factory result."""
    ports = factory(bucket_id=profile_id, operation=operation)
    if ports.work_unit_repository.bucket_id != profile_id or ports.calculation_repository.bucket_id != profile_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return ports


def require_iva_wallet_write_receipt(
    receipt: OperationTerminalReceipt,
    *,
    definition_id: str,
    profile_id: UUID,
    message: str,
) -> None:
    """Raise ``ValueError(message)`` unless ``receipt`` settled this profile's wallet write.

    The write must have succeeded with an updating effect, name its result and
    carry no refusal or failure facts.
    """
    require_succeeded_terminal_receipt(
        receipt,
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(profile_id)),
        effect=OperationEffect.UPDATED,
        message=message,
    )


__all__ = [
    "IVA_WALLET_MUTATION_RESULT_MAX_BYTES",
    "IvaWalletCanonicalAmount",
    "IvaWalletTaxpayerNif",
    "bind_iva_wallet_profile_ports",
    "require_iva_wallet_write_receipt",
    "validate_iva_wallet_amount",
]
