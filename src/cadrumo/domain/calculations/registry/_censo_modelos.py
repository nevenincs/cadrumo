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
from typing import Literal, Self

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator

from ....core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ....core import Modelo
from ....core.logging import get_logger
from ....core.resources import resources
from ._authority import ValidatedRegistryAuthority
from .errors import RegistrySnapshotError, RegistryValidationError
from ._temporal import select_revision

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


class CensoModeloFoundationLogFields(BaseModel):
    """Stable, non-secret log fields emitted by the censo foundation service."""

    model_config = _STRICT_FROZEN

    service_name: str = "censo_modelo_foundation"
    service_owner: str = Field(pattern=r"^cadrumo\.domain\.calculations\.registry$")
    modelo: str = Field(min_length=3, max_length=3, pattern=r"^[0-9]{3}$")
    role: CensoModeloRole
    decision: Literal["active_work_unit_allowed", "historical_metadata_only"]
    event_kind: CensoModeloEventKind | None = None
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
class CensoModeloOwnership:
    """Non-CLI ownership record for one censo modelo code."""

    modelo: str
    role: CensoModeloRole
    service_owner: str
    event_kinds: tuple[str, ...]
    active_work_unit_allowed: bool
    superseded_by: str | None = None


_ACTIVE_CENSO_MODELO = Modelo.M036.value
_HISTORICAL_CENSO_MODELO = Modelo.M037.value
_HISTORICAL_037_SOURCE_REF = "boe-modelo-037-historical-suppression"
_CENSO_FOUNDATION_YEAR = 2025


class CensoModeloFoundationContract(BaseModel):
    """Backend-owned service contract for censo modelo foundation routing."""

    model_config = _STRICT_FROZEN

    schema_version: str = "1"
    service_owner: str = Field(default=CENSO_MODELO_SERVICE_OWNER, pattern=r"^cadrumo\.domain\.calculations\.registry$")
    active_modelo: str = Field(default=Modelo.M036.value, min_length=3, max_length=3, pattern=r"^[0-9]{3}$")
    historical_modelos: tuple[str, ...] = (Modelo.M037.value,)
    event_kinds: tuple[CensoModeloEventKind, ...]
    error_codes: tuple[str, ...]

    @field_validator("historical_modelos")
    @classmethod
    def _historical_modelos_are_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise RegistryValidationError("historical censo modelos must be unique")
        if Modelo.M036.value in value:
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


class CensoModeloFoundationCommand(BaseModel):
    """Command contract for resolving one censo modelo foundation request."""

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=3, max_length=3, pattern=r"^[0-9]{3}$")
    event_kind: CensoModeloEventKind | None = None

    @model_validator(mode="after")
    def _validate_censo_command(self) -> Self:
        ownership = censo_modelo_ownership(self.modelo)
        if ownership.active_work_unit_allowed and self.event_kind is None:
            raise RegistryValidationError("active censo modelo 036 requires event_kind")
        if not ownership.active_work_unit_allowed and self.event_kind is not None:
            raise RegistryValidationError("historical censo modelo 037 must not declare event_kind")
        return self


class CensoModeloFoundationResult(BaseModel):
    """Result contract describing the registry-owned censo foundation decision."""

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=3, max_length=3, pattern=r"^[0-9]{3}$")
    role: CensoModeloRole
    service_owner: str = Field(pattern=r"^cadrumo\.domain\.calculations\.registry$")
    event_kind: CensoModeloEventKind | None = None
    event_kinds: tuple[CensoModeloEventKind, ...] = ()
    active_work_unit_allowed: bool
    superseded_by: str | None = Field(default=None, min_length=3, max_length=3, pattern=r"^[0-9]{3}$")

    @computed_field
    @property
    def log_fields(self) -> CensoModeloFoundationLogFields:
        """Return stable logging fields for this foundation decision.

        Returns:
            A :class:`CensoModeloFoundationLogFields` record with all structured log fields.
        """
        decision: Literal["active_work_unit_allowed", "historical_metadata_only"]
        decision = "active_work_unit_allowed" if self.active_work_unit_allowed else "historical_metadata_only"
        return CensoModeloFoundationLogFields(
            service_owner=self.service_owner,
            modelo=self.modelo,
            role=self.role,
            decision=decision,
            event_kind=self.event_kind,
            active_work_unit_allowed=self.active_work_unit_allowed,
            superseded_by=self.superseded_by,
        )

    @model_validator(mode="after")
    def _validate_censo_result(self) -> Self:
        if self.modelo == Modelo.M036:
            self._validate_active_036_shape()
            return self
        if self.modelo == Modelo.M037:
            self._validate_historical_037_shape()
            return self
        raise RegistryValidationError(f"unknown censo modelo code {self.modelo!r}; expected '036' or '037'")

    def _validate_active_036_shape(self) -> None:
        """Reject any 036 result that disagrees with the active-foundation contract."""
        if self.role is not CensoModeloRole.ACTIVE_FOUNDATION:
            raise RegistryValidationError("modelo 036 result must use active_foundation role")
        if self.service_owner != CENSO_MODELO_SERVICE_OWNER:
            raise RegistryValidationError("modelo 036 result must be owned by the registry domain")
        if self.event_kind is None:
            raise RegistryValidationError("modelo 036 result requires event_kind")
        if self.event_kinds != tuple(CensoModeloEventKind(kind) for kind in CENSO_MODELO_EVENT_KINDS):
            raise RegistryValidationError("modelo 036 result must expose the accepted event kinds")
        if not self.active_work_unit_allowed or self.superseded_by is not None:
            raise RegistryValidationError("modelo 036 result must allow active work units and not be superseded")

    def _validate_historical_037_shape(self) -> None:
        """Reject any 037 result that disagrees with the historical-metadata contract."""
        if self.role is not CensoModeloRole.HISTORICAL_METADATA:
            raise RegistryValidationError("modelo 037 result must use historical_metadata role")
        if self.event_kind is not None or self.event_kinds:
            raise RegistryValidationError("modelo 037 result must not expose active event kinds")
        if self.active_work_unit_allowed or self.superseded_by != Modelo.M036:
            raise RegistryValidationError("modelo 037 result must be inactive and superseded by 036")


def censo_modelo_ownership_map() -> tuple[CensoModeloOwnership, ...]:
    """Return the registry-owned censo modelo ownership map.

    Returns:
        Tuple of :class:`CensoModeloOwnership` records, one per censo modelo.
    """
    return (censo_modelo_ownership(_ACTIVE_CENSO_MODELO), censo_modelo_ownership(_HISTORICAL_CENSO_MODELO))


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
    authority = resources().modelos.authority
    if modelo == _ACTIVE_CENSO_MODELO:
        return _active_036_ownership_from_registry(authority)
    if modelo == _HISTORICAL_CENSO_MODELO:
        return _historical_037_ownership_from_registry(authority)
    raise RegistryValidationError(f"unknown censo modelo code {modelo!r}; expected '036' or '037'")


def _find_censo_modelo_ownership(modelo: str) -> CensoModeloOwnership | None:
    if modelo not in {_ACTIVE_CENSO_MODELO, _HISTORICAL_CENSO_MODELO}:
        stripped_modelo = modelo.strip()
        if stripped_modelo in {_ACTIVE_CENSO_MODELO, _HISTORICAL_CENSO_MODELO, "36", "37"}:
            raise RegistryValidationError(f"unknown censo modelo code {modelo!r}; expected '036' or '037'")
        return None
    return censo_modelo_ownership(modelo)


def _active_036_ownership_from_registry(authority: ValidatedRegistryAuthority) -> CensoModeloOwnership:
    try:
        definition = authority.validate_modelo(_ACTIVE_CENSO_MODELO)
    except RegistrySnapshotError as exc:
        raise RegistryValidationError("active censo modelo 036 registry definition is missing") from exc
    if definition.tax_domain != "censo" or definition.cadence != "ad_hoc":
        raise RegistryValidationError("active censo modelo 036 must be an ad_hoc censo registry definition")
    revisions = tuple(
        revision
        for revision in definition.revisions.values()
        if revision.period_selector.includes_year(_CENSO_FOUNDATION_YEAR)
    )
    if not revisions:
        raise RegistryValidationError("active censo modelo 036 has no registry revision for the foundation year")
    revision = max(revisions, key=lambda item: (item.valid_from, str(item.id)))
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
        select_revision(
            definition,
            filing_year=_CENSO_FOUNDATION_YEAR,
            period=event_kind,
        )
    return CensoModeloOwnership(
        modelo=_ACTIVE_CENSO_MODELO,
        role=CensoModeloRole.ACTIVE_FOUNDATION,
        service_owner=CENSO_MODELO_SERVICE_OWNER,
        event_kinds=event_kinds,
        active_work_unit_allowed=True,
    )


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


def is_active_censo_modelo(modelo: str) -> bool:
    """Return whether a censo modelo may create active work units."""
    return censo_modelo_ownership(modelo).active_work_unit_allowed


def resolve_censo_modelo_foundation(command: CensoModeloFoundationCommand) -> CensoModeloFoundationResult:
    """Resolve one censo modelo foundation command and return a :class:`CensoModeloFoundationResult`."""
    ownership = censo_modelo_ownership(command.modelo)
    event_kinds = tuple(CensoModeloEventKind(kind) for kind in ownership.event_kinds)
    result = CensoModeloFoundationResult(
        modelo=ownership.modelo,
        role=ownership.role,
        service_owner=ownership.service_owner,
        event_kind=command.event_kind,
        event_kinds=event_kinds,
        active_work_unit_allowed=ownership.active_work_unit_allowed,
        superseded_by=ownership.superseded_by,
    )
    _LOGGER.debug("resolved censo modelo foundation", extra=result.log_fields.as_extra())
    return result


def resolve_censo_modelo_work_unit_foundation(
    *,
    modelo: str,
    period: str,
) -> CensoModeloFoundationResult | None:
    """Resolve a work-unit period through the censo foundation when it applies.

    Returns:
        A :class:`CensoModeloFoundationResult` when the modelo is a censo modelo,
        or ``None`` when the modelo is not registered as a censo modelo.
    """
    modelo = _require_modelo_string(modelo)
    ownership = _find_censo_modelo_ownership(modelo)
    if ownership is None:
        return None
    if not ownership.active_work_unit_allowed:
        raise RegistryValidationError(
            f"censo modelo {ownership.modelo} is historical censo metadata only and cannot create active work units",
        )
    payload: dict[str, object] = {"modelo": ownership.modelo}
    try:
        payload["event_kind"] = CensoModeloEventKind(period)
    except ValueError as exc:
        raise RegistryValidationError(
            "active censo modelo 036 work units require one of the censo event periods: alta, modificacion, baja",
        ) from exc
    return resolve_censo_modelo_foundation(CensoModeloFoundationCommand.model_validate(payload))


__all__ = [
    "CENSO_MODELO_ERROR_CODES",
    "CENSO_MODELO_EVENT_KINDS",
    "CENSO_MODELO_SERVICE_OWNER",
    "CensoModeloEventKind",
    "CensoModeloFoundationCommand",
    "CensoModeloFoundationContract",
    "CensoModeloFoundationLogFields",
    "CensoModeloFoundationResult",
    "CensoModeloOwnership",
    "CensoModeloRole",
    "build_censo_modelo_foundation_contract",
    "censo_modelo_ownership",
    "censo_modelo_ownership_map",
    "get_censo_modelo_foundation_contract",
    "is_active_censo_modelo",
    "resolve_censo_modelo_foundation",
    "resolve_censo_modelo_work_unit_foundation",
]
