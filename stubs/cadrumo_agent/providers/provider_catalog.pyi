"""Normalized provider catalog records, as the script constructs them.

``ModelCatalogEntry`` and ``NativeControl`` are carried through the script
without being read or built, so they are declared by identity only.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

class HealthState(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"

class AuthenticationState(StrEnum):
    AUTHENTICATED = "authenticated"
    UNAUTHENTICATED = "unauthenticated"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"

class AdmissionState(StrEnum):
    ADMITTED = "admitted"
    UNPROVEN = "unproven"
    NOT_ADMITTED = "not_admitted"
    UNKNOWN = "unknown"

class CatalogStatus(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    STALE = "stale"
    UNKNOWN = "unknown"

class NativeControl: ...
class ModelCatalogEntry: ...

@dataclass(frozen=True, slots=True)
class CatalogState:
    status: CatalogStatus
    checked_at: datetime
    revision: str | None = None
    expires_at: datetime | None = None
    reason: str | None = None

@dataclass(frozen=True, slots=True)
class ProviderHealthAxes:
    configured: HealthState
    transport: HealthState
    authentication: AuthenticationState
    catalog: CatalogStatus
    admission: AdmissionState

class StructuredProviderHealth:
    @classmethod
    def derive(
        cls,
        axes: ProviderHealthAxes,
        *,
        reasons: tuple[str, ...] = (),
        checked_at: datetime,
    ) -> StructuredProviderHealth: ...

@dataclass(frozen=True, slots=True)
class ProviderCatalogKey:
    provider_id: str
    execution_mode: str

@dataclass(frozen=True, slots=True)
class ProviderCatalog:
    key: ProviderCatalogKey
    state: CatalogState
    models: tuple[ModelCatalogEntry, ...]
    native_controls: tuple[NativeControl, ...] = ()
    schema_version: int = ...

@dataclass(frozen=True, slots=True)
class ProviderRecord:
    provider_id: str
    display_name: str
    execution_mode: str
    health: StructuredProviderHealth
    catalog: ProviderCatalog
