"""Modelo 145 local payer-communication service ownership contract.

Modelo 145 is not an AEAT filing surface. The application layer owns only a
local communication workflow: create the communication, validate it, export the
official record, mark payer delivery, and mark local completion. This module is
the P04 ownership contract for that backend service; later steps add the
mutating behavior behind the same vocabulary.

See Also:
    :mod:`~cadrumo.application.modelo.m145_communication_records`
        Persisted record service that consumes this ownership contract.
    :class:`M145CommunicationServiceContract`
        Immutable, registry-backed ownership record returned by this module.
    :class:`M145CommunicationAction`
        Closed backend action vocabulary for the local communication workflow.
    :func:`build_m145_communication_service_contract`
        Builder that reads the registry snapshot and refuses filing-like drift.
    :class:`~domain.calculations.registry.schema.ModeloRevision`
        Registry revision whose application links, legal refs, source refs, and
        export layouts ground the returned contract.
    :class:`~domain.calculations.registry.authority.ValidatedRegistryAuthority`
        Bundled authority loader that supplies the Modelo 145 snapshot.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from ...core.modelo import Modelo
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.time.clock import today_madrid
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.ids import RevisionId
from .m145_communication_period import M145CommunicationPeriod

M145_COMMUNICATION_SERVICE_OWNER = "cadrumo.application.modelo"


class M145CommunicationAction(StrEnum):
    """Closed backend action vocabulary for Modelo 145 local communication."""

    CREATE = "create"
    VALIDATE = "validate"
    EXPORT = "export"
    MARK_DELIVERED_TO_PAYER = "mark_delivered_to_payer"
    MARK_LOCALLY_COMPLETED = "mark_locally_completed"


_EXPECTED_SURFACES: tuple[str, ...] = ("communication", "payer_delivery", "export")
_EXPECTED_ACTIONS: tuple[M145CommunicationAction, ...] = (
    M145CommunicationAction.CREATE,
    M145CommunicationAction.VALIDATE,
    M145CommunicationAction.EXPORT,
    M145CommunicationAction.MARK_DELIVERED_TO_PAYER,
    M145CommunicationAction.MARK_LOCALLY_COMPLETED,
)
_FORBIDDEN_SURFACES: frozenset[str] = frozenset(
    {"filing", "deadline", "live_read", "portal", "submit", "receipt", "amendment"}
)


class M145CommunicationServiceContract(BaseModel):
    """Immutable ownership contract for the Modelo 145 backend service.

    The contract is built from the registry snapshot so later behavior cannot
    drift into a filing lifecycle without tripping the ownership tests first.
    """

    model_config = STRICT_FROZEN_CONFIG

    schema_version: str = "1"
    service_owner: str = Field(
        default=M145_COMMUNICATION_SERVICE_OWNER,
        pattern=r"^cadrumo\.application\.modelo$",
    )
    modelo: str = Field(default=Modelo("145").value, pattern=r"^145$")
    period_token: str = Field(min_length=1)
    revision_id: RevisionId = Field(min_length=1)
    actions: tuple[M145CommunicationAction, ...] = _EXPECTED_ACTIONS
    surfaces: tuple[str, ...]
    export_layout_ids: tuple[str, ...]
    legal_refs: tuple[str, ...]
    source_refs: tuple[str, ...]


def build_m145_communication_service_contract(
    *,
    period_token: M145CommunicationPeriod,
    filing_year: int | None = None,
    operation: PinnedAuthorityOperation,
) -> M145CommunicationServiceContract:
    """Return the registry-backed Modelo 145 local communication contract.

    Reads the law-selected Modelo 145 revision for the requested communication
    period and refuses if that revision does not declare the period or exposes
    filing, deadline, live-read, portal, or other non-local surfaces. The
    returned record is read-only ownership data; it does not create, persist,
    export, or transition any communication, so the revision is read
    structurally rather than through a filing-grade snapshot.
    """
    selected_filing_year = today_madrid().year if filing_year is None else filing_year
    requested_token = M145CommunicationPeriod(period_token).value
    revision = operation.revision_for_context(
        Modelo("145").value,
        filing_year=selected_filing_year,
        period=requested_token,
    )
    declared_tokens = tuple(
        str(period).lower() for period in revision.period_selector.periods_for_year(selected_filing_year)
    )
    if requested_token not in declared_tokens:
        raise ValueError(
            f"Modelo 145 revision {revision.id!r} does not declare communication period {requested_token!r} "
            f"for {selected_filing_year}; declared {declared_tokens!r}"
        )
    declared_surfaces = frozenset(str(link.surface) for link in revision.application_links)
    forbidden = tuple(sorted(declared_surfaces & _FORBIDDEN_SURFACES))
    if forbidden:
        raise ValueError(f"Modelo 145 communication service cannot own filing-like surfaces: {forbidden!r}")
    if declared_surfaces != frozenset(_EXPECTED_SURFACES):
        got = tuple(sorted(declared_surfaces))
        raise ValueError(f"Modelo 145 communication service expected surfaces {_EXPECTED_SURFACES!r}; got {got!r}")

    return M145CommunicationServiceContract(
        revision_id=revision.id,
        period_token=requested_token,
        surfaces=_EXPECTED_SURFACES,
        export_layout_ids=tuple(
            sorted(
                layout.id
                for layout in operation.revision_with_export_layouts(
                    Modelo("145").value, str(revision.id)
                ).export_layouts
            )
        ),
        legal_refs=tuple(sorted(str(ref) for ref in revision.legal_refs)),
        source_refs=tuple(sorted(str(ref) for ref in revision.source_refs)),
    )


__all__ = [
    "M145_COMMUNICATION_SERVICE_OWNER",
    "M145CommunicationAction",
    "M145CommunicationServiceContract",
    "build_m145_communication_service_contract",
]
