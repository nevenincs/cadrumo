"""Registry-owned censo modelo foundation map.

Resolves lifecycle routing for Modelo 036 (active) and Modelo 037 (historical)
censo registration forms. All routing decisions are derived from the
:class:`ValidatedRegistryAuthority` so the registry TOML remains the single
authority for event periods and ownership rules.

Core types:
:class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from ....core.modelo import Modelo
from .authority import PinnedAuthorityOperation, ValidatedRegistryAuthority
from .errors import RegistrySnapshotError, RegistryValidationError
from .schema import ModeloRevision
from .temporal import select_revision

CENSO_MODELO_SERVICE_OWNER = "cadrumo.domain.calculations.registry"
CENSO_MODELO_EVENT_KINDS: tuple[str, ...] = ("alta", "modificacion", "baja")


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


def _require_modelo_string(modelo: object) -> str:
    """Reject a non-string modelo code before any equality or ``strip`` lookup."""
    if not isinstance(modelo, str):
        raise RegistryValidationError(
            f"censo modelo code must be a string, got {type(modelo).__name__}: {modelo!r}",
        )
    return modelo


def censo_ownership_refusing_work_units(
    modelo: str,
    *,
    operation: PinnedAuthorityOperation,
) -> CensoModeloOwnership | None:
    """Return ``modelo``'s ownership when it is a censo modelo that admits no work unit.

    A modelo outside the censo pair, or the active censo modelo, returns
    ``None``. The superseded censo modelo returns its ownership record, which
    names the successor a filing belongs under, so the creation boundary can
    refuse in those terms instead of failing later on a missing revision.
    """
    modelo = _require_modelo_string(modelo)
    if modelo == _ACTIVE_CENSO_MODELO:
        ownership = active_036_ownership_from_registry(operation)
    elif modelo == _HISTORICAL_CENSO_MODELO:
        ownership = _historical_037_ownership_from_registry(operation)
    else:
        return None
    return None if ownership.active_work_unit_allowed else ownership


def active_036_ownership_from_registry(
    authority: PinnedAuthorityOperation | ValidatedRegistryAuthority,
) -> CensoModeloOwnership:
    """Return modelo 036 ownership as the given authority declares it.

    The authority is supplied explicitly so a caller holding a published
    generation and a caller holding a separately validated authority reach the
    same ownership derivation.

    Args:
        authority: A :class:`PinnedAuthorityOperation` leased over a published
            generation, or a :class:`ValidatedRegistryAuthority` compiled for
            this derivation.

    Returns:
        The modelo 036 ownership the supplied authority declares.
    """
    if isinstance(authority, PinnedAuthorityOperation):
        try:
            directory = authority.modelo_directory(_ACTIVE_CENSO_MODELO)
            revisions = tuple(
                authority.revision(_ACTIVE_CENSO_MODELO, str(metadata.id)) for metadata in directory.revisions
            )
            tax_domain = directory.modelo.tax_domain
            cadence = directory.modelo.cadence
        except (RegistrySnapshotError, ValueError) as exc:
            raise RegistryValidationError("active censo modelo 036 registry definition is missing") from exc

        def select_revision_for_event(*, filing_year: int, period: str, on: date) -> ModeloRevision:
            return authority.revision_for_context(
                _ACTIVE_CENSO_MODELO,
                filing_year=filing_year,
                period=period,
                on=on,
            )
    else:
        try:
            modelo_definition = authority.validate_modelo(_ACTIVE_CENSO_MODELO)
            revisions = tuple(modelo_definition.revisions.values())
            tax_domain = modelo_definition.tax_domain
            cadence = modelo_definition.cadence
        except RegistrySnapshotError as exc:
            raise RegistryValidationError("active censo modelo 036 registry definition is missing") from exc

        def select_revision_for_event(*, filing_year: int, period: str, on: date) -> ModeloRevision:
            return select_revision(
                modelo_definition,
                filing_year=filing_year,
                period=period,
                on=on,
                support=authority.catalogues.supported_filing_years,
            )

    _require_active_036_metadata(tax_domain, cadence)
    revision = _latest_active_036_revision(revisions)
    foundation_year = _foundation_year_from_latest_revision(revision)
    event_kinds = tuple(revision.period_selector.declared_periods)
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
        # The typed query is the sanctioned resolver and keeps the teeth: an
        # event kind no revision declares still raises, which is the only thing
        # this loop asserts. It deliberately does not apply the supported-year
        # envelope, because this ownership contract is derived from declared
        # event metadata rather than a filing snapshot. Pinning ``as_of`` to
        # the latest revision's effective date disambiguates a mid-year
        # revision boundary without changing the declared foundation year.
        selected = select_revision_for_event(
            filing_year=foundation_year,
            period=event_kind,
            on=revision.valid_from,
        )
        _require_active_036_foundation_revision(selected, revision)
    return CensoModeloOwnership(
        modelo=_ACTIVE_CENSO_MODELO,
        role=CensoModeloRole.ACTIVE_FOUNDATION,
        service_owner=CENSO_MODELO_SERVICE_OWNER,
        event_kinds=event_kinds,
        active_work_unit_allowed=True,
    )


def _require_active_036_metadata(tax_domain: str, cadence: str) -> None:
    if tax_domain != "censo" or cadence != "ad_hoc":
        raise RegistryValidationError("active censo modelo 036 must be an ad_hoc censo registry definition")


def _latest_active_036_revision(revisions: tuple[ModeloRevision, ...]) -> ModeloRevision:
    try:
        return max(revisions, key=lambda item: (item.valid_from, str(item.id)))
    except ValueError as exc:
        raise RegistryValidationError("active censo modelo 036 has no registry revisions") from exc


def _require_active_036_foundation_revision(selected: ModeloRevision, foundation: ModeloRevision) -> None:
    if selected.id != foundation.id:
        raise RegistryValidationError(
            "active censo modelo 036 foundation revision must resolve from its declared first governed year",
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


def _historical_037_ownership_from_registry(
    authority: PinnedAuthorityOperation | ValidatedRegistryAuthority,
) -> CensoModeloOwnership:
    if isinstance(authority, PinnedAuthorityOperation):
        if _HISTORICAL_CENSO_MODELO in authority.modelo_ids():
            raise RegistryValidationError("historical censo modelo 037 must not have an active registry definition")
        try:
            authority.source_reference(_HISTORICAL_037_SOURCE_REF)
        except (RegistrySnapshotError, ValueError):
            raise RegistryValidationError(
                "historical censo modelo 037 suppression source metadata is missing"
            ) from None
    else:
        if any(str(modelo.id) == _HISTORICAL_CENSO_MODELO for modelo in authority.modelos):
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
    "CENSO_MODELO_EVENT_KINDS",
    "CENSO_MODELO_SERVICE_OWNER",
    "CensoModeloEventKind",
    "CensoModeloOwnership",
    "CensoModeloRole",
    "censo_ownership_refusing_work_units",
]
