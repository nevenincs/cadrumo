"""Typed JSON payloads for the cross-period IVA prorrata register CLI.

Each result model is a strict
:class:`OutputSchema` subclass referenced as a deferred target under a
stable ``command`` key so the ``emit_envelope`` spine and the JSON-schema
conformance gate bind the ``aeat app ledger prorrata`` leaves to a schema.

The register the operator writes here (regime election, differentiated-sector
partition) is the ingress that makes the LIVA art. 106 especial apportionment and
the arts. 9.1.c / 101 per-sector apportionment
(:class:`~domain.prorrata_register.ProrrataRegister`) fire on the live M303
aggregation path; before this surface existed the register was written only by
the settlement auto-seed (general / ninguna).
"""

from __future__ import annotations

from ...core.identity import BucketId
from ...core.json_contract import OutputSchema
from ...core.prorrata_register import ProrrataEspecialTransitionKind


class ProrrataEspecialTransitionPayload(OutputSchema):
    """Typed option or revocation evidence emitted with a register entry."""

    kind: ProrrataEspecialTransitionKind
    evidence_reference: str


class ProrrataEntryPayload(OutputSchema):
    """One ``(ejercicio, sector)`` register entry.

    Mirrors :class:`~domain.prorrata_register.ProrrataRegisterEntry`'s
    ``model_dump(mode='json')`` with the decimal percentages and volumes rendered
    as strings at the emit site.
    """

    ejercicio: int
    regime: str
    especial_transition: ProrrataEspecialTransitionPayload | None
    sector_id: str | None = None
    interrupted: bool
    provisional_percentage: str | None = None
    provisional_provenance: str | None = None
    authorisation_reference: str | None = None
    definitive_percentage: str | None = None
    definitive_volume_con_derecho: str | None = None
    definitive_volume_sin_derecho: str | None = None
    source_observation_ref: str | None = None
    schema_version: str


class SectorDefinitionPayload(OutputSchema):
    """One operator-declared differentiated-sector partition entry."""

    sector_id: str
    letra: str
    member_activity_codes: list[str]


class ProrrataElectResult(OutputSchema):
    """Shared shape referenced by the two regime-election verbs under distinct keys."""

    bucket_id: BucketId
    entry: ProrrataEntryPayload
    count: int


class ProrrataElectEspecialResult(ProrrataElectResult):
    """JSON envelope for ``aeat app ledger prorrata elect-especial``."""


class ProrrataElectGeneralResult(ProrrataElectResult):
    """JSON envelope for ``aeat app ledger prorrata elect-general``."""


class ProrrataRevokeEspecialResult(ProrrataElectResult):
    """JSON envelope for ``aeat app ledger prorrata revoke-especial``."""


class ProrrataDeclareSectorResult(OutputSchema):
    """JSON envelope for ``aeat app ledger prorrata declare-sector``."""

    bucket_id: BucketId
    sector: SectorDefinitionPayload
    count: int


class ProrrataListResult(OutputSchema):
    """JSON envelope for ``aeat app ledger prorrata list``."""

    bucket_id: BucketId
    entries: list[ProrrataEntryPayload]
    sectors: list[SectorDefinitionPayload]
    count: int


__all__ = [
    "ProrrataDeclareSectorResult",
    "ProrrataElectEspecialResult",
    "ProrrataElectGeneralResult",
    "ProrrataElectResult",
    "ProrrataEntryPayload",
    "ProrrataEspecialTransitionPayload",
    "ProrrataListResult",
    "ProrrataRevokeEspecialResult",
    "SectorDefinitionPayload",
]
