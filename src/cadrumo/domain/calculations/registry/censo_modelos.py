"""Registry-owned censo modelo foundation map.

Resolves lifecycle routing for Modelo 036 (active) and Modelo 037 (historical)
censo registration forms. All routing decisions are derived from the
:class:`ValidatedRegistryAuthority` so the registry TOML remains the single
authority for event periods and ownership rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache

from pydantic import BaseModel, Field, field_validator

from ....core.logging import get_logger
from ....core.modelo import Modelo
from ....core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .authority import ValidatedRegistryAuthority, bundled_authority
from .errors import RegistrySnapshotError, RegistryValidationError
from .schema import ModeloRevision
from .temporal import select_revision

CENSO_MODELO_SERVICE_OWNER = "cadrumo.domain.calculations.registry"
CENSO_MODELO_EVENT_KINDS: tuple[str, ...] = ("alta", "modificacion", "baja")
CENSO_MODELO_ERROR_CODES: tuple[str, ...] = ("ERROR_CALCULATIONS_REGISTRY_VALIDATION",)

_LOGGER = get_logger(__name__)


class CensoModeloRole(StrEnum):
    """Lifecycle role for censo modelos under the registry foundation."""

    ACTIVE_FOUNDATION = "active_foundation"
    HISTORICAL_METADATA = "historical_metadata"


class CensoModeloEventKind(StrEnum):
    """Accepted event-triggered lifecycle kinds for active Modelo 036."""

    ALTA = "alta"
    MODIFICACION = "modificacion"
    BAJA = "baja"


@dataclass(frozen=True, slots=True)
class CensoModeloOwnership:
    """Non-CLI ownership record for one censo modelo code."""

    modelo: str
    role: CensoModeloRole
    service_owner: str
    event_kinds: tuple[str, ...]
    active_work_unit_allowed: bool
    superseded_by: str | None = None


_ACTIVE_CENSO_MODELO = Modelo("036").value
_HISTORICAL_CENSO_MODELO = Modelo("037").value
_HISTORICAL_037_SOURCE_REF = "boe-modelo-037-historical-suppression"


class CensoModeloFoundationContract(BaseModel):
    """Backend-owned service contract for censo modelo foundation routing."""

    model_config = _STRICT_FROZEN

    schema_version: str = "1"
    service_owner: str = Field(default=CENSO_MODELO_SERVICE_OWNER, pattern=r"^cadrumo\.domain\.calculations\.registry$")
    active_modelo: str = Field(default=Modelo("036").value, min_length=3, max_length=3, pattern=r"^[0-9]{3}$")
    historical_modelos: tuple[str, ...] = (Modelo("037").value,)
    event_kinds: tuple[CensoModeloEventKind, ...]
    error_codes: tuple[str, ...]

    @field_validator("historical_modelos")
    @classmethod
    def _historical_modelos_are_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise RegistryValidationError("historical censo modelos must be unique")
        if Modelo("036").value in value:
            raise RegistryValidationError("active censo modelo 036 must not be historical")
        return value

    @field_validator("event_kinds")
    @classmethod
    def _event_kinds_are_exact(cls, value: tuple[CensoModeloEventKind, ...]) -> tuple[CensoModeloEventKind, ...]:
        expected = tuple(CensoModeloEventKind(kind) for kind in CENSO_MODELO_EVENT_KINDS)
        if value != expected:
            raise RegistryValidationError("censo foundation event kinds must match the registry ownership map")
        return value

    @field_validator("error_codes")
    @classmethod
    def _error_codes_are_exact(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if value != CENSO_MODELO_ERROR_CODES:
            raise RegistryValidationError("censo foundation error codes must match the declared service contract")
        return value


def build_censo_modelo_foundation_contract() -> CensoModeloFoundationContract:
    """Build the immutable backend-owned censo modelo foundation contract.

    Returns:
        The validated :class:`CensoModeloFoundationContract` for the active registry.
    """
    active_ownership = censo_modelo_ownership(_ACTIVE_CENSO_MODELO)
    contract = CensoModeloFoundationContract(
        event_kinds=tuple(CensoModeloEventKind(kind) for kind in active_ownership.event_kinds),
        error_codes=CENSO_MODELO_ERROR_CODES,
    )
    _LOGGER.debug(
        "built censo modelo foundation contract",
        extra={
            "service_name": "censo_modelo_foundation",
            "service_owner": contract.service_owner,
            "active_modelo": contract.active_modelo,
            "historical_modelo_count": len(contract.historical_modelos),
            "event_kind_count": len(contract.event_kinds),
        },
    )
    return contract


@lru_cache(maxsize=1)
def get_censo_modelo_foundation_contract() -> CensoModeloFoundationContract:
    """Return the cached backend-owned :class:`CensoModeloFoundationContract`."""
    return build_censo_modelo_foundation_contract()


def _require_modelo_string(modelo: object) -> str:
    """Reject a non-string modelo code before any equality or ``strip`` lookup."""
    if not isinstance(modelo, str):
        raise RegistryValidationError(
            f"censo modelo code must be a string, got {type(modelo).__name__}: {modelo!r}",
        )
    return modelo


def censo_modelo_ownership(modelo: str) -> CensoModeloOwnership:
    """Return the :class:`CensoModeloOwnership` record for an exact string modelo code."""
    modelo = _require_modelo_string(modelo)
    authority = bundled_authority()
    if modelo == _ACTIVE_CENSO_MODELO:
        return _active_036_ownership_from_registry(authority)
    if modelo == _HISTORICAL_CENSO_MODELO:
        return _historical_037_ownership_from_registry(authority)
    raise RegistryValidationError(f"unknown censo modelo code {modelo!r}; expected '036' or '037'")


def _active_036_ownership_from_registry(authority: ValidatedRegistryAuthority) -> CensoModeloOwnership:
    try:
        definition = authority.validate_modelo(_ACTIVE_CENSO_MODELO)
    except RegistrySnapshotError as exc:
        raise RegistryValidationError("active censo modelo 036 registry definition is missing") from exc
    if definition.tax_domain != "censo" or definition.cadence != "ad_hoc":
        raise RegistryValidationError("active censo modelo 036 must be an ad_hoc censo registry definition")
    try:
        revision = max(definition.revisions.values(), key=lambda item: (item.valid_from, str(item.id)))
    except ValueError as exc:
        raise RegistryValidationError("active censo modelo 036 has no registry revisions") from exc
    foundation_year = _foundation_year_from_latest_revision(revision)
    event_kinds = tuple(revision.period_selector.periods)
    if event_kinds != CENSO_MODELO_EVENT_KINDS:
        raise RegistryValidationError("active censo modelo 036 event periods must come from the registry")
    for event_kind in event_kinds:
        # Revision SELECTION, not a snapshot. The question here is whether each
        # censal event kind resolves to exactly one revision -- an applicability
        # question, feeding the ownership record this function returns, never a
        # filing artefact.
        #
        # `authority.snapshot` takes no grade and always builds at the filing
        # rung, so it demanded a REVIEWED revision and filing capability from
        # modelo 036, whose registry declares `authority_grade = applicability`:
        # a censal alta/modificacion/baja is filed on AEAT's sede, and this
        # application never produces a fichero for it. The call therefore refused
        # for a rung modelo 036 does not claim and is not meant to.
        #
        # `select_revision` is the sanctioned resolver and keeps the teeth: an
        # event kind no revision declares still raises, which is the only thing
        # this loop asserts.
        selected = select_revision(
            definition,
            filing_year=foundation_year,
            period=event_kind,
        )
        if selected.id != revision.id:
            raise RegistryValidationError(
                "active censo modelo 036 foundation revision must resolve from its declared first governed year",
            )
    return CensoModeloOwnership(
        modelo=_ACTIVE_CENSO_MODELO,
        role=CensoModeloRole.ACTIVE_FOUNDATION,
        service_owner=CENSO_MODELO_SERVICE_OWNER,
        event_kinds=event_kinds,
        active_work_unit_allowed=True,
    )


def _foundation_year_from_latest_revision(revision: ModeloRevision) -> int:
    """Derive the active censo foundation year from its latest declared revision."""
    selector = revision.period_selector
    foundation_year = min(selector.years) if selector.years else selector.year_from
    if foundation_year is None:
        raise RegistryValidationError("active censo modelo 036 foundation revision must declare a first governed year")
    if revision.valid_from.year != foundation_year:
        raise RegistryValidationError(
            "active censo modelo 036 foundation revision valid_from year must match its first governed year",
        )
    return foundation_year


def _historical_037_ownership_from_registry(authority: ValidatedRegistryAuthority) -> CensoModeloOwnership:
    try:
        authority.validate_modelo(_HISTORICAL_CENSO_MODELO)
    except RegistrySnapshotError as exc:
        if "is not present in the calculation registry" not in str(exc):
            raise
    else:
        raise RegistryValidationError("historical censo modelo 037 must not have an active registry definition")
    if _HISTORICAL_037_SOURCE_REF not in authority.catalogues.sources:
        raise RegistryValidationError("historical censo modelo 037 suppression source metadata is missing")
    return CensoModeloOwnership(
        modelo=_HISTORICAL_CENSO_MODELO,
        role=CensoModeloRole.HISTORICAL_METADATA,
        service_owner=CENSO_MODELO_SERVICE_OWNER,
        event_kinds=(),
        active_work_unit_allowed=False,
        superseded_by=_ACTIVE_CENSO_MODELO,
    )


__all__ = [
    "CENSO_MODELO_ERROR_CODES",
    "CENSO_MODELO_EVENT_KINDS",
    "CENSO_MODELO_SERVICE_OWNER",
    "CensoModeloEventKind",
    "CensoModeloFoundationContract",
    "CensoModeloOwnership",
    "CensoModeloRole",
    "build_censo_modelo_foundation_contract",
    "censo_modelo_ownership",
    "get_censo_modelo_foundation_contract",
]
