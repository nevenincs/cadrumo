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
    :class:`~domain.calculations.registry.ModeloRevision`
        Registry revision whose application links, legal refs, source refs, and
        export layouts ground the returned contract.
    :class:`~domain.calculations.registry.ValidatedRegistryAuthority`
        Bundled authority loader that supplies the Modelo 145 snapshot.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field

from ...core.modelo import Modelo
from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...domain.calculations.registry.ids import RevisionId

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
    *, filing_year: int | None = None, operation: PinnedAuthorityOperation | None = None
) -> M145CommunicationServiceContract:
    """Return the registry-backed Modelo 145 local communication contract.

    Reads the law-selected Modelo 145 revision for the communication period
    and refuses if the registry exposes filing, deadline, live-read, portal, or
    other non-local surfaces. The returned record is read-only ownership data;
    it does not create, persist, export, or transition any communication, so
    the revision is read structurally (:func:`select_revision`) rather than
    through a filing-grade snapshot.
    """
    selected_filing_year = date.today().year if filing_year is None else filing_year
    if operation is None:
        with bundled_indexed_authority().operation() as indexed_operation:
            return build_m145_communication_service_contract(
                filing_year=filing_year,
                operation=indexed_operation,
            )
    directory = operation.modelo_directory(Modelo("145").value)
    year_revision = max(
        (
            operation.revision(Modelo("145").value, str(candidate.id))
            for candidate in directory.revisions
            if candidate.period_selector.periods_for_year(selected_filing_year)
        ),
        key=lambda revision: (revision.valid_from, str(revision.id)),
    )
    period_tokens = tuple(
        str(period) for period in year_revision.period_selector.periods_for_year(selected_filing_year)
    )
    if len(period_tokens) != 1:
        raise ValueError("Modelo 145 communication contract requires one registry period token")
    period_token = period_tokens[0]
    revision = operation.revision_for_context(
        Modelo("145").value,
        filing_year=selected_filing_year,
        period=period_token,
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
        period_token=period_token,
        surfaces=_EXPECTED_SURFACES,
        export_layout_ids=tuple(sorted(layout.id for layout in revision.export_layouts)),
        legal_refs=tuple(sorted(str(ref) for ref in revision.legal_refs)),
        source_refs=tuple(sorted(str(ref) for ref in revision.source_refs)),
    )


__all__ = [
    "M145_COMMUNICATION_SERVICE_OWNER",
    "M145CommunicationAction",
    "M145CommunicationServiceContract",
    "build_m145_communication_service_contract",
]
