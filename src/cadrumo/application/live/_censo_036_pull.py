"""Pull the taxpayer's filed Modelo 036 and derive their censal enrolment.

Modelo 036 IS the censo: it is the declaración censal de alta, modificación
y baja in the Censo de Empresarios, Profesionales y Retenedores, and it is
what a person or entity actually files to enrol in the Spanish tax system.
So the honest way to learn a taxpayer's censal situation is to read the 036
they filed — not to ask them to retype it.

This module reads that filing from the declarations register, the same
authenticated read surface the justificante and expediente pulls already
use. It never touches the "Censos WEB" modification tool. That distinction
is the whole safety argument: ADR ``2026-07-11-censo-operator-manual-enrolment``
retired reading *current census state*, because the only path to it was
operating a write tool, and a read one accidental submit away from mutating
AEAT census state is a live-write path with extra steps. Reading the
taxpayer's own filed declaration out of their own expediente history is a
pure read of filed evidence — the same class as every justificante pull
that already ships, and subject to the same read gate.

Scope, stated honestly: the register row carries the filing's identity and
lifecycle (which 036 was filed, when, its expediente, and whether it was an
alta, a modificación or a baja). That is what this module derives. The
richer censal detail *inside* the declaration — epígrafes IAE, domicilio,
obligaciones, regímenes — lives in the declaration PDF, and extracting it
needs the ``modelo-036-declaracion-pdf`` extraction profile to declare those
target casillas; today it declares exactly one. Deriving what the register
genuinely carries, and not pretending to the rest, is the point.

See Also:
    :mod:`cadrumo.application.modelo._m036_lifecycle`
        The operator-manual recording surface this automates the input of.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, ConfigDict

from ...core import Modelo
from ...domain.calculations.registry import CensoModeloEventKind

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ...adapters.outbound.aeat.sede import Declaracion
    from ...domain.user_profile import UserProfileFact


CENSO_STATUS_FACT_PATH: Final[str] = "censo.status"
"""Profile path carrying the taxpayer's current censal lifecycle state.

The same path the registry's ``modelo-036-profile-censo-status`` binding
reads, so a pulled value feeds the calculation engine through the existing
binding rather than a second channel.
"""

CENSO_FILED_ON_FACT_PATH: Final[str] = "censo.filed_on"
"""Profile path carrying the date of the censal filing the state came from."""

_ALTA_TOKENS: Final[tuple[str, ...]] = ("alta",)
_BAJA_TOKENS: Final[tuple[str, ...]] = ("baja",)
_MODIFICACION_TOKENS: Final[tuple[str, ...]] = ("modificacion", "modificación")


class Filed036Declaration(BaseModel):
    """One filed Modelo 036 as the declarations register reports it."""

    model_config = ConfigDict(frozen=True)

    ejercicio: int
    expediente_id: str
    event_kind: CensoModeloEventKind
    presented_at: datetime


def classify_censal_event(*, tipo_solicitud: str | None, observaciones: str | None) -> CensoModeloEventKind:
    """Classify a filed 036 as an alta, a modificación, or a baja.

    AEAT labels the causa de presentación on the register row rather than
    exposing it as a code, so the classification reads that prose. The
    default is :attr:`CensoModeloEventKind.MODIFICACION`, deliberately: an
    unrecognised label most likely describes a change to an existing
    enrolment, and guessing ALTA would assert a first enrolment that may
    never have happened, while guessing BAJA would assert a deregistration
    that would suppress obligations the taxpayer still has. Modificación is
    the reading that asserts least.

    Baja is tested before alta because a baja row's prose routinely names
    the alta it reverses ("baja ... alta anterior"), so an alta-first check
    would classify a deregistration as an enrolment.
    """
    haystack = " ".join(part for part in (tipo_solicitud, observaciones) if part).casefold()
    if any(token in haystack for token in _BAJA_TOKENS):
        return CensoModeloEventKind.BAJA
    if any(token in haystack for token in _ALTA_TOKENS):
        return CensoModeloEventKind.ALTA
    if any(token in haystack for token in _MODIFICACION_TOKENS):
        return CensoModeloEventKind.MODIFICACION
    return CensoModeloEventKind.MODIFICACION


def filed_036_declarations(rows: Sequence[Declaracion]) -> tuple[Filed036Declaration, ...]:
    """Project register rows onto typed 036 filings, oldest first.

    Non-036 rows are dropped rather than refused: the caller may hand over
    a mixed register capture, and the censal question only concerns 036.
    """
    filings = [
        Filed036Declaration(
            ejercicio=row.ejercicio,
            expediente_id=row.expediente_id,
            event_kind=classify_censal_event(
                tipo_solicitud=row.tipo_solicitud,
                observaciones=row.observaciones,
            ),
            presented_at=row.presented_at,
        )
        for row in rows
        if row.modelo == Modelo.M036.value
    ]
    return tuple(sorted(filings, key=lambda filing: filing.presented_at))


def current_censal_state(filings: Sequence[Filed036Declaration]) -> Filed036Declaration | None:
    """Return the filing that determines the taxpayer's censal state today.

    The most recent filing wins, because that is what censal lifecycle
    means: a modificación supersedes the alta it amends, and a baja
    supersedes everything before it. ``None`` when nothing was filed.
    """
    if not filings:
        return None
    return max(filings, key=lambda filing: filing.presented_at)


def censo_facts_from_filed_036(filings: Sequence[Filed036Declaration]) -> tuple[UserProfileFact, ...]:
    """Project the censal state onto profile facts ready to persist.

    Returns an empty tuple when nothing was filed, so a taxpayer with no
    036 on record has no facts asserted about them — silence is correct
    there, and stamping a default would invent an enrolment.

    The facts are operator-tier evidence, not AEAT-verified: they are read
    from the register, which reports what was filed rather than certifying
    the current census. The calendar's ``censo.enrolment_unverified``
    posture is unaffected, exactly as the operator-manual path leaves it.
    """
    from ...domain.user_profile import UserProfileFact

    current = current_censal_state(filings)
    if current is None:
        return ()
    return (
        UserProfileFact(path=CENSO_STATUS_FACT_PATH, value=current.event_kind.value),
        UserProfileFact(path=CENSO_FILED_ON_FACT_PATH, value=current.presented_at.date().isoformat()),
    )


async def pull_filed_036(*, bucket_id: str, year_from: int, year_to: int) -> tuple[Filed036Declaration, ...]:
    """Live-read the declarations register for filed 036s across a year span.

    Composes the shipped expediente capture, so the read gate, the
    authenticated session, and the persisted snapshot all behave exactly as
    they do for a justificante pull. A year with no 036 contributes nothing
    rather than failing the span — a taxpayer files a censal declaration
    only when something changes, so most years are legitimately empty.
    """
    from . import capture_expedientes

    collected: list[Filed036Declaration] = []
    for year in range(year_from, year_to + 1):
        snapshot = await capture_expedientes(bucket_id=bucket_id, modelo=Modelo.M036.value, year=year)
        collected.extend(filed_036_declarations(snapshot.declarations))
    return tuple(sorted(collected, key=lambda filing: filing.presented_at))


__all__ = [
    "CENSO_FILED_ON_FACT_PATH",
    "CENSO_STATUS_FACT_PATH",
    "Filed036Declaration",
    "censo_facts_from_filed_036",
    "classify_censal_event",
    "current_censal_state",
    "filed_036_declarations",
    "pull_filed_036",
]
