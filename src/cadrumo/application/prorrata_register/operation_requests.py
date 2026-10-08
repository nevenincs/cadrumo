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

type ProrrataOperationId = Literal[
    "list",
    "declare_sector",
    "elect_especial",
    "elect_general",
    "revoke_especial",
    "seed",
    "seed_sector",
    "settle_sector",
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
    """Carry whole-entity prior definitive from the pinned 303 observation."""

    ejercicio: int


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


__all__ = [
    "PRORRATA_DECLARE_SECTOR_OPERATION_DEFINITION_ID",
    "PRORRATA_ELECT_ESPECIAL_OPERATION_DEFINITION_ID",
    "PRORRATA_ELECT_GENERAL_OPERATION_DEFINITION_ID",
    "PRORRATA_LIST_OPERATION_DEFINITION_ID",
    "PRORRATA_REVOKE_ESPECIAL_OPERATION_DEFINITION_ID",
    "PRORRATA_SEED_OPERATION_DEFINITION_ID",
    "PRORRATA_SEED_SECTOR_OPERATION_DEFINITION_ID",
    "PRORRATA_SETTLE_SECTOR_OPERATION_DEFINITION_ID",
    "ProrrataDeclareSectorRequest",
    "ProrrataElectEspecialRequest",
    "ProrrataElectGeneralRequest",
    "ProrrataElectionRequest",
    "ProrrataListRequest",
    "ProrrataOperationId",
    "ProrrataProfileRequest",
    "ProrrataRevokeEspecialRequest",
    "ProrrataSeedRequest",
    "ProrrataSeedSectorRequest",
    "ProrrataSettleSectorRequest",
]
