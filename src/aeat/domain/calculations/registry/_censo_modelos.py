"""Registry-owned census modelo foundation map."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

from ....core.logging import get_logger
from ....core.resources import resources
from ._authority import ValidatedRegistryAuthority
from ._errors import RegistrySnapshotError, RegistryValidationError

CENSUS_MODELO_SERVICE_OWNER = "aeat.domain.calculations.registry"
CENSUS_MODELO_EVENT_KINDS: tuple[str, ...] = ("alta", "modificacion", "baja")
CENSUS_MODELO_ERROR_CODES: tuple[str, ...] = ("ERROR_CALCULATIONS_REGISTRY_VALIDATION",)
_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")
_LOGGER = get_logger(__name__)


class CensusModeloRole(StrEnum):
    """Lifecycle role for census modelos under the registry foundation."""

    ACTIVE_FOUNDATION = "active_foundation"
    HISTORICAL_METADATA = "historical_metadata"


class CensusModeloEventKind(StrEnum):
    """Accepted event-triggered lifecycle kinds for active Modelo 036."""

    ALTA = "alta"
    MODIFICACION = "modificacion"
    BAJA = "baja"


class CensusModeloFoundationLogFields(BaseModel):
    """Stable, non-secret log fields emitted by the census foundation service."""

    model_config = _STRICT_FROZEN

    service_name: str = "census_modelo_foundation"
    service_owner: str = Field(pattern=r"^aeat\.domain\.calculations\.registry$")
    modelo: str = Field(min_length=3, max_length=3, pattern=r"^[0-9]{3}$")
    role: CensusModeloRole
    decision: Literal["active_work_unit_allowed", "historical_metadata_only"]
    event_kind: CensusModeloEventKind | None = None
    active_work_unit_allowed: bool
    superseded_by: str | None = Field(default=None, min_length=3, max_length=3, pattern=r"^[0-9]{3}$")

    def as_extra(self) -> dict[str, object]:
        """Return a logging ``extra`` payload with stable field names."""

        return {
            "service_name": self.service_name,
            "service_owner": self.service_owner,
            "modelo": self.modelo,
            "role": self.role.value,
            "decision": self.decision,
            "event_kind": self.event_kind.value if self.event_kind is not None else "",
            "active_work_unit_allowed": self.active_work_unit_allowed,
            "superseded_by": self.superseded_by or "",
        }


@dataclass(frozen=True, slots=True)
class CensusModeloOwnership:
    """Non-CLI ownership record for one census modelo code."""

    modelo: str
    role: CensusModeloRole
    service_owner: str
    event_kinds: tuple[str, ...]
    active_work_unit_allowed: bool
    superseded_by: str | None = None


_ACTIVE_CENSUS_MODELO = "036"
_HISTORICAL_CENSUS_MODELO = "037"
_HISTORICAL_037_SOURCE_REF = "boe-modelo-037-historical-suppression"
_CENSUS_FOUNDATION_YEAR = 2025


class CensusModeloFoundationContract(BaseModel):
    """Backend-owned service contract for census modelo foundation routing."""

    model_config = _STRICT_FROZEN

    schema_version: str = "1"
    service_owner: str = Field(default=CENSUS_MODELO_SERVICE_OWNER, pattern=r"^aeat\.domain\.calculations\.registry$")
    active_modelo: str = Field(default="036", min_length=3, max_length=3, pattern=r"^[0-9]{3}$")
    historical_modelos: tuple[str, ...] = ("037",)
    event_kinds: tuple[CensusModeloEventKind, ...]
    error_codes: tuple[str, ...]

    @field_validator("historical_modelos")
    @classmethod
    def _historical_modelos_are_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise RegistryValidationError("historical census modelos must be unique")
        if "036" in value:
            raise RegistryValidationError("active census modelo 036 must not be historical")
        return value

    @field_validator("event_kinds")
    @classmethod
    def _event_kinds_are_exact(cls, value: tuple[CensusModeloEventKind, ...]) -> tuple[CensusModeloEventKind, ...]:
        expected = tuple(CensusModeloEventKind(kind) for kind in CENSUS_MODELO_EVENT_KINDS)
        if value != expected:
            raise RegistryValidationError("census foundation event kinds must match the registry ownership map")
        return value

    @field_validator("error_codes")
    @classmethod
    def _error_codes_are_exact(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if value != CENSUS_MODELO_ERROR_CODES:
            raise RegistryValidationError("census foundation error codes must match the declared service contract")
        return value


class CensusModeloFoundationCommand(BaseModel):
    """Command contract for resolving one census modelo foundation request."""

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=3, max_length=3, pattern=r"^[0-9]{3}$")
    event_kind: CensusModeloEventKind | None = None

    @model_validator(mode="after")
    def _validate_census_command(self) -> Self:
        ownership = census_modelo_ownership(self.modelo)
        if ownership.active_work_unit_allowed and self.event_kind is None:
            raise RegistryValidationError("active census modelo 036 requires event_kind")
        if not ownership.active_work_unit_allowed and self.event_kind is not None:
            raise RegistryValidationError("historical census modelo 037 must not declare event_kind")
        return self


class CensusModeloFoundationResult(BaseModel):
    """Result contract describing the registry-owned census foundation decision."""

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=3, max_length=3, pattern=r"^[0-9]{3}$")
    role: CensusModeloRole
    service_owner: str = Field(pattern=r"^aeat\.domain\.calculations\.registry$")
    event_kind: CensusModeloEventKind | None = None
    event_kinds: tuple[CensusModeloEventKind, ...] = ()
    active_work_unit_allowed: bool
    superseded_by: str | None = Field(default=None, min_length=3, max_length=3, pattern=r"^[0-9]{3}$")

    @computed_field
    @property
    def log_fields(self) -> CensusModeloFoundationLogFields:
        """Return stable logging fields for this foundation decision."""

        decision: Literal["active_work_unit_allowed", "historical_metadata_only"]
        decision = "active_work_unit_allowed" if self.active_work_unit_allowed else "historical_metadata_only"
        return CensusModeloFoundationLogFields(
            service_owner=self.service_owner,
            modelo=self.modelo,
            role=self.role,
            decision=decision,
            event_kind=self.event_kind,
            active_work_unit_allowed=self.active_work_unit_allowed,
            superseded_by=self.superseded_by,
        )

    @model_validator(mode="after")
    def _validate_census_result(self) -> Self:
        if self.modelo == "036":
            self._validate_active_036_shape()
            return self
        if self.modelo == "037":
            self._validate_historical_037_shape()
            return self
        raise RegistryValidationError(f"unknown census modelo code {self.modelo!r}; expected '036' or '037'")

    def _validate_active_036_shape(self) -> None:
        """Reject any 036 result that disagrees with the active-foundation contract."""
        if self.role is not CensusModeloRole.ACTIVE_FOUNDATION:
            raise RegistryValidationError("modelo 036 result must use active_foundation role")
        if self.service_owner != CENSUS_MODELO_SERVICE_OWNER:
            raise RegistryValidationError("modelo 036 result must be owned by the registry domain")
        if self.event_kind is None:
            raise RegistryValidationError("modelo 036 result requires event_kind")
        if self.event_kinds != tuple(CensusModeloEventKind(kind) for kind in CENSUS_MODELO_EVENT_KINDS):
            raise RegistryValidationError("modelo 036 result must expose the accepted event kinds")
        if not self.active_work_unit_allowed or self.superseded_by is not None:
            raise RegistryValidationError("modelo 036 result must allow active work units and not be superseded")

    def _validate_historical_037_shape(self) -> None:
        """Reject any 037 result that disagrees with the historical-metadata contract."""
        if self.role is not CensusModeloRole.HISTORICAL_METADATA:
            raise RegistryValidationError("modelo 037 result must use historical_metadata role")
        if self.event_kind is not None or self.event_kinds:
            raise RegistryValidationError("modelo 037 result must not expose active event kinds")
        if self.active_work_unit_allowed or self.superseded_by != "036":
            raise RegistryValidationError("modelo 037 result must be inactive and superseded by 036")


def census_modelo_ownership_map() -> tuple[CensusModeloOwnership, ...]:
    """Return the registry-owned census modelo ownership map."""

    return (census_modelo_ownership(_ACTIVE_CENSUS_MODELO), census_modelo_ownership(_HISTORICAL_CENSUS_MODELO))


def build_census_modelo_foundation_contract() -> CensusModeloFoundationContract:
    """Build the immutable backend-owned census modelo foundation contract."""

    active_ownership = census_modelo_ownership(_ACTIVE_CENSUS_MODELO)
    contract = CensusModeloFoundationContract(
        event_kinds=tuple(CensusModeloEventKind(kind) for kind in active_ownership.event_kinds),
        error_codes=CENSUS_MODELO_ERROR_CODES,
    )
    _LOGGER.debug(
        "built census modelo foundation contract",
        extra={
            "service_name": "census_modelo_foundation",
            "service_owner": contract.service_owner,
            "active_modelo": contract.active_modelo,
            "historical_modelo_count": len(contract.historical_modelos),
            "event_kind_count": len(contract.event_kinds),
        },
    )
    return contract


@lru_cache(maxsize=1)
def get_census_modelo_foundation_contract() -> CensusModeloFoundationContract:
    """Return the cached backend-owned census modelo foundation contract."""

    return build_census_modelo_foundation_contract()


def census_modelo_ownership(modelo: str) -> CensusModeloOwnership:
    """Return the census ownership record for an exact string modelo code."""

    if not isinstance(modelo, str):
        raise RegistryValidationError("census modelo code must be a string")
    authority = resources().modelos.authority
    if modelo == _ACTIVE_CENSUS_MODELO:
        return _active_036_ownership_from_registry(authority)
    if modelo == _HISTORICAL_CENSUS_MODELO:
        return _historical_037_ownership_from_registry(authority)
    raise RegistryValidationError(f"unknown census modelo code {modelo!r}; expected '036' or '037'")


def _find_census_modelo_ownership(modelo: str) -> CensusModeloOwnership | None:
    if not isinstance(modelo, str):
        raise RegistryValidationError("census modelo code must be a string")
    if modelo not in {_ACTIVE_CENSUS_MODELO, _HISTORICAL_CENSUS_MODELO}:
        stripped_modelo = modelo.strip()
        if stripped_modelo in {_ACTIVE_CENSUS_MODELO, _HISTORICAL_CENSUS_MODELO, "36", "37"}:
            raise RegistryValidationError(f"unknown census modelo code {modelo!r}; expected '036' or '037'")
        return None
    return census_modelo_ownership(modelo)


def _active_036_ownership_from_registry(authority: ValidatedRegistryAuthority) -> CensusModeloOwnership:
    try:
        definition = authority.validate_modelo(_ACTIVE_CENSUS_MODELO)
    except RegistrySnapshotError as exc:
        raise RegistryValidationError("active census modelo 036 registry definition is missing") from exc
    if definition.tax_domain != "census" or definition.cadence != "ad_hoc":
        raise RegistryValidationError("active census modelo 036 must be an ad_hoc census registry definition")
    revisions = tuple(
        revision
        for revision in definition.revisions.values()
        if revision.period_selector.includes_year(_CENSUS_FOUNDATION_YEAR)
    )
    if not revisions:
        raise RegistryValidationError("active census modelo 036 has no registry revision for the foundation year")
    revision = max(revisions, key=lambda item: (item.valid_from, str(item.id)))
    event_kinds = tuple(revision.period_selector.periods)
    if event_kinds != CENSUS_MODELO_EVENT_KINDS:
        raise RegistryValidationError("active census modelo 036 event periods must come from the registry")
    for event_kind in event_kinds:
        authority.snapshot(
            _ACTIVE_CENSUS_MODELO,
            filing_year=_CENSUS_FOUNDATION_YEAR,
            period=event_kind,
        )
    return CensusModeloOwnership(
        modelo=_ACTIVE_CENSUS_MODELO,
        role=CensusModeloRole.ACTIVE_FOUNDATION,
        service_owner=CENSUS_MODELO_SERVICE_OWNER,
        event_kinds=event_kinds,
        active_work_unit_allowed=True,
    )


def _historical_037_ownership_from_registry(authority: ValidatedRegistryAuthority) -> CensusModeloOwnership:
    try:
        authority.validate_modelo(_HISTORICAL_CENSUS_MODELO)
    except RegistrySnapshotError:
        pass
    else:
        raise RegistryValidationError("historical census modelo 037 must not have an active registry definition")
    if _HISTORICAL_037_SOURCE_REF not in authority.catalogues.sources:
        raise RegistryValidationError("historical census modelo 037 suppression source metadata is missing")
    return CensusModeloOwnership(
        modelo=_HISTORICAL_CENSUS_MODELO,
        role=CensusModeloRole.HISTORICAL_METADATA,
        service_owner=CENSUS_MODELO_SERVICE_OWNER,
        event_kinds=(),
        active_work_unit_allowed=False,
        superseded_by=_ACTIVE_CENSUS_MODELO,
    )


def is_active_census_modelo(modelo: str) -> bool:
    """Return whether a census modelo may create active work units."""

    return census_modelo_ownership(modelo).active_work_unit_allowed


def resolve_census_modelo_foundation(command: CensusModeloFoundationCommand) -> CensusModeloFoundationResult:
    """Resolve one census modelo foundation command through the registry owner."""

    ownership = census_modelo_ownership(command.modelo)
    event_kinds = tuple(CensusModeloEventKind(kind) for kind in ownership.event_kinds)
    result = CensusModeloFoundationResult(
        modelo=ownership.modelo,
        role=ownership.role,
        service_owner=ownership.service_owner,
        event_kind=command.event_kind,
        event_kinds=event_kinds,
        active_work_unit_allowed=ownership.active_work_unit_allowed,
        superseded_by=ownership.superseded_by,
    )
    _LOGGER.debug("resolved census modelo foundation", extra=result.log_fields.as_extra())
    return result


def resolve_census_modelo_work_unit_foundation(
    *,
    modelo: str,
    period: str,
) -> CensusModeloFoundationResult | None:
    """Resolve a work-unit period through the census foundation when it applies."""

    ownership = _find_census_modelo_ownership(modelo)
    if ownership is None:
        return None
    if not ownership.active_work_unit_allowed:
        raise RegistryValidationError(
            f"census modelo {ownership.modelo} is historical census metadata only and cannot create active work units"
        )
    payload: dict[str, object] = {"modelo": ownership.modelo}
    try:
        payload["event_kind"] = CensusModeloEventKind(period)
    except ValueError as exc:
        raise RegistryValidationError(
            "active census modelo 036 work units require one of the census event periods: alta, modificacion, baja"
        ) from exc
    return resolve_census_modelo_foundation(CensusModeloFoundationCommand.model_validate(payload))


__all__ = [
    "CENSUS_MODELO_ERROR_CODES",
    "CENSUS_MODELO_EVENT_KINDS",
    "CENSUS_MODELO_SERVICE_OWNER",
    "CensusModeloEventKind",
    "CensusModeloFoundationCommand",
    "CensusModeloFoundationContract",
    "CensusModeloFoundationLogFields",
    "CensusModeloFoundationResult",
    "CensusModeloOwnership",
    "CensusModeloRole",
    "build_census_modelo_foundation_contract",
    "census_modelo_ownership",
    "census_modelo_ownership_map",
    "get_census_modelo_foundation_contract",
    "is_active_census_modelo",
    "resolve_census_modelo_foundation",
    "resolve_census_modelo_work_unit_foundation",
]
