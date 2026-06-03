"""Typed contracts for the Modelo 036 declarative-recording verbs.

Per the 2026-05-16 amendment to
``cli-workflow-redesign-modelo-036-037-foundation-adr`` the local
app never files a 036. AEAT is the authority; the operator files
at sede. The verbs surfaced by ``aeat app modelo m036
{alta,modificacion,baja}`` are declarative recording — they
record that the operator filed at sede so downstream profile
state and stale-cascade logic can react.

This module defines the Pydantic command + result contracts the
verb handlers and downstream service implementations consume.
The service implementation lands in a follow-up commit per the
3-commit landing plan in
``2026-06-03-m036-lifecycle-verbs-research``.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from ...core.identity import ProfileId
from ...domain.calculations.registry import CensoModeloEventKind


class M036DeclarationCommand(BaseModel):
    """Operator request to record an M036 declaration filed at sede.

    The operator files the 036 with AEAT through the sede portal
    (or in person at an oficina). This command records that the
    declaration happened locally so the downstream stale-cascade
    + audit-trail logic can react. The command MUST NOT trigger
    any local filing action.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    profile_id: ProfileId
    event_kind: CensoModeloEventKind
    declared_on: date
    sede_justificante: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        description="Optional AEAT acuse de recibo identifier emitted by sede for the filing.",
    )
    note: str | None = Field(default=None, max_length=512)


class M036DeclarationResult(BaseModel):
    """Outcome of a successful declaration-recording call.

    Carries the content-addressed declaration id (SHA-256 over the
    derived tuple), the canonical event-kind, the declared date,
    and the timestamp at which the local record was written.
    Downstream consumers (stale-cascade engine, profile-state
    re-derivation) read these fields to decide what to recompute.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    declaration_id: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
        description=(
            "SHA-256 hex content-address derived from "
            "(profile_id, event_kind, declared_on, sede_justificante)."
        ),
    )
    profile_id: ProfileId
    event_kind: CensoModeloEventKind
    declared_on: date
    sede_justificante: str | None = None
    recorded_at: datetime


__all__ = [
    "M036DeclarationCommand",
    "M036DeclarationResult",
]
