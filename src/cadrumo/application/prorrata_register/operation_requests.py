"""Canonical request schemas for the registered prorrata operations."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ..operations.public_scalar import PublicDecimal

PRORRATA_LIST_OPERATION_DEFINITION_ID = "ledger.prorrata.list"
PRORRATA_DECLARE_SECTOR_OPERATION_DEFINITION_ID = "ledger.prorrata.declare_sector"
PRORRATA_ELECT_ESPECIAL_OPERATION_DEFINITION_ID = "ledger.prorrata.elect_especial"
PRORRATA_ELECT_GENERAL_OPERATION_DEFINITION_ID = "ledger.prorrata.elect_general"
PRORRATA_REVOKE_ESPECIAL_OPERATION_DEFINITION_ID = "ledger.prorrata.revoke_especial"
PRORRATA_SEED_OPERATION_DEFINITION_ID = "ledger.prorrata.seed"
PRORRATA_SEED_SECTOR_OPERATION_DEFINITION_ID = "ledger.prorrata.seed_sector"
PRORRATA_SETTLE_SECTOR_OPERATION_DEFINITION_ID = "ledger.prorrata.settle_sector"
PRORRATA_DECLARE_GROSS_OPERATION_DEFINITION_ID = "ledger.prorrata.declare_gross"
PRORRATA_REMOVE_GROSS_OPERATION_DEFINITION_ID = "ledger.prorrata.remove_gross"

type ProrrataOperationId = Literal[
    "list",
    "declare_sector",
    "elect_especial",
    "elect_general",
    "revoke_especial",
    "seed",
    "seed_sector",
    "settle_sector",
    "declare_gross",
    "remove_gross",
]


class ProrrataProfileRequest(BaseModel):
    """Common hidden exact-profile binding for prorrata register operations."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID


class ProrrataListRequest(ProrrataProfileRequest):
    """Read the complete prorrata singleton for the selected profile."""


class ProrrataDeclareSectorRequest(ProrrataProfileRequest):
    """Declare the taxpayer-authored differentiated-sector partition row."""

    sector_id: str
    letra: str
    member_activity_codes: tuple[str, ...] = ()


class ProrrataElectionRequest(ProrrataProfileRequest):
    """Operator-authored provisional percentage and evidence reference."""

    ejercicio: int
    percentage: PublicDecimal
    provenance: str | None = None
    reference: str | None = None
    sector_id: str | None = None


class ProrrataElectEspecialRequest(ProrrataElectionRequest):
    """Elect especial prorrata for one exercise."""

    evidence_reference: str | None = None


class ProrrataElectGeneralRequest(ProrrataElectionRequest):
    """Elect general prorrata for one exercise."""


class ProrrataRevokeEspecialRequest(ProrrataElectionRequest):
    """Record the evidence-backed revocation of especial prorrata."""

    evidence_reference: str


class ProrrataSeedRequest(ProrrataProfileRequest):
    """Carry the whole-entity prior definitive from the held prior 390 or final-period 303.

    ``percentage`` is the taxpayer's statement of that prior definitive; it is
    carried only when neither return is held, and refused when a held return
    states another figure.
    """

    ejercicio: int
    percentage: PublicDecimal | None = None


class ProrrataSeedSectorRequest(ProrrataProfileRequest):
    """Carry one differentiated sector from its latest prior register definitive."""

    ejercicio: int
    sector_id: str


class ProrrataSettleSectorRequest(ProrrataProfileRequest):
    """Compute and record one sector's year-end definitive prorrata."""

    ejercicio: int
    sector_id: str
    con_derecho_volume: PublicDecimal
    sin_derecho_volume: PublicDecimal


class ProrrataDeclareGrossRequest(ProrrataProfileRequest):
    """Declare one earlier liquidation period's gross deducible cuota before prorrata."""

    ejercicio: int
    period: str
    sector_id: str | None = None
    gross_cuota: PublicDecimal
    evidence_reference: str
    replace: bool = False


class ProrrataRemoveGrossRequest(ProrrataProfileRequest):
    """Remove one earlier liquidation period's operator gross declaration."""

    ejercicio: int
    period: str
    sector_id: str | None = None


__all__ = [
    "PRORRATA_DECLARE_GROSS_OPERATION_DEFINITION_ID",
    "PRORRATA_DECLARE_SECTOR_OPERATION_DEFINITION_ID",
    "PRORRATA_ELECT_ESPECIAL_OPERATION_DEFINITION_ID",
    "PRORRATA_ELECT_GENERAL_OPERATION_DEFINITION_ID",
    "PRORRATA_LIST_OPERATION_DEFINITION_ID",
    "PRORRATA_REMOVE_GROSS_OPERATION_DEFINITION_ID",
    "PRORRATA_REVOKE_ESPECIAL_OPERATION_DEFINITION_ID",
    "PRORRATA_SEED_OPERATION_DEFINITION_ID",
    "PRORRATA_SEED_SECTOR_OPERATION_DEFINITION_ID",
    "PRORRATA_SETTLE_SECTOR_OPERATION_DEFINITION_ID",
    "ProrrataDeclareGrossRequest",
    "ProrrataDeclareSectorRequest",
    "ProrrataElectEspecialRequest",
    "ProrrataElectGeneralRequest",
    "ProrrataElectionRequest",
    "ProrrataListRequest",
    "ProrrataOperationId",
    "ProrrataProfileRequest",
    "ProrrataRemoveGrossRequest",
    "ProrrataRevokeEspecialRequest",
    "ProrrataSeedRequest",
    "ProrrataSeedSectorRequest",
    "ProrrataSettleSectorRequest",
]
