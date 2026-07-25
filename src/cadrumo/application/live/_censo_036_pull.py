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

Classification has two tiers, and the module never blurs them. When the
ticked causa-de-presentación boxes are known, the lifecycle is read from
AEAT's own numbering: the 036 revision declares all 29 causas from PÁGINA 1
with their published numbers, and the TIPO column rides on each casilla's
section path, so classification is registry lookup rather than
interpretation. The declarations register does not report those boxes — it
lists that a filing happened, not what the form said — so a row read from
the register falls back to classifying its causa prose.

Scope, stated honestly: this derives the filing's identity and lifecycle.
The richer censal detail *inside* the declaration — epígrafes IAE,
domicilio, obligaciones, regímenes — lives on later pages of the PDF, and
lifting it needs the ``modelo-036-declaracion-pdf`` extraction profile to
declare those target casillas against the bundled diseño de registro.
Deriving what is genuinely available, and not pretending to the rest, is
the point.

See Also:
    :mod:`cadrumo.application.modelo._m036_lifecycle`
        The operator-manual recording surface this automates the input of.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, ConfigDict

from ...core import Modelo
from ...core.external_constants import PROVENANCE_SOURCE_CENSO_FILED_036
from ...domain.calculations.registry import CensoModeloEventKind, bundled_authority
from ...domain.user_profile import UserProfileFact
from . import capture_expedientes

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ...adapters.outbound.aeat.sede import Declaracion


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


_CENSAL_PERIOD_CODE: Final[str] = "0A"
"""Period code a censal declaration files under.

036 is not a periodic return — it is filed when something changes — so it
carries the annual code, which is the shape the justificante fixtures for
this modelo already use.
"""

_CAUSA_CASILLA_PREFIX: Final[str] = "decl.causa-"

#: Lifecycle precedence when a declaration ticks causas of several tipos.
#: A baja ends the enrolment whatever else the same form changes, and an
#: alta establishes it; modificación only ever amends an enrolment that
#: already exists, so it yields to both.
_EVENT_KIND_PRECEDENCE: Final[tuple[CensoModeloEventKind, ...]] = (
    CensoModeloEventKind.BAJA,
    CensoModeloEventKind.ALTA,
    CensoModeloEventKind.MODIFICACION,
)

_EVENT_KIND_BY_VALUE: Final[dict[str, CensoModeloEventKind]] = {kind.value: kind for kind in CensoModeloEventKind}
"""Lookup from a registry section leaf to its lifecycle member."""


def causa_casilla_event_kinds() -> dict[str, CensoModeloEventKind]:
    """Map each causa-de-presentación casilla number onto its lifecycle tipo.

    Derived from the registry rather than restated here. The 036 revision
    declares every causa casilla with AEAT's own number and carries the
    TIPO column as the leaf of its ``section`` path, so the mapping is
    registry data; hardcoding a second copy would be a regulatory value
    inlined at a call site, and would drift the moment AEAT adds a causa.
    """
    definition = bundled_authority().validate_modelo(Modelo.M036.value)
    mapping: dict[str, CensoModeloEventKind] = {}
    for revision in definition.revisions.values():
        for casilla in revision.casillas:
            if not casilla.id.startswith(_CAUSA_CASILLA_PREFIX):
                continue
            # The section leaf IS the enum value: registry section parts are
            # snake_case ASCII (a schema-hygiene gate enforces it), which is
            # exactly the spelling CensoModeloEventKind uses. So this is an
            # equality lookup, not prefix guessing.
            tipo = casilla.section[-1]
            if tipo in _EVENT_KIND_BY_VALUE:
                mapping[casilla.number] = _EVENT_KIND_BY_VALUE[tipo]
    return mapping


def classify_from_causa_casillas(ticked: Sequence[str]) -> CensoModeloEventKind | None:
    """Classify a filing from the causa casillas its declaration ticks.

    This is the grounded classification: AEAT numbers each causa on
    PÁGINA 1 and the registry records which lifecycle tipo each number
    belongs to, so a declaration that reports its ticked boxes needs no
    prose reading at all.

    Returns ``None`` when nothing recognisable was ticked, so the caller
    can fall back rather than receive a guess dressed as evidence.
    """
    mapping = causa_casilla_event_kinds()
    kinds = {mapping[number] for number in ticked if number in mapping}
    if not kinds:
        return None
    return next(kind for kind in _EVENT_KIND_PRECEDENCE if kind in kinds)


def classify_censal_event(*, tipo_solicitud: str | None, observaciones: str | None) -> CensoModeloEventKind:
    """Classify a filed 036 from the register row's prose.

    The fallback path. Prefer :func:`classify_from_causa_casillas` whenever
    the ticked causa boxes are available: those are AEAT's own numbering
    and need no interpretation. The declarations register does not carry
    them — it reports a filing, not the form's contents — so a row read
    from the register is classified from the causa prose it does carry. The
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
    current = current_censal_state(filings)
    if current is None:
        return ()
    return (
        UserProfileFact(
            path=CENSO_STATUS_FACT_PATH,
            value=current.event_kind.value,
            source=PROVENANCE_SOURCE_CENSO_FILED_036,
        ),
        UserProfileFact(
            path=CENSO_FILED_ON_FACT_PATH,
            value=current.presented_at.date().isoformat(),
            source=PROVENANCE_SOURCE_CENSO_FILED_036,
        ),
    )


async def pull_censal_declaration(*, bucket_id: str, year_from: int, year_to: int):
    """Live-pull the taxpayer's current filed 036 and read the form itself.

    The full censal pull, and the one the operator actually wants: find
    which 036 is current, fetch that declaration's signed PDF over the
    same authenticated Playwright session every justificante pull uses,
    and read the form. Reading the register alone tells you a filing
    happened and roughly what it was called; reading the declaration tells
    you what it said.

    Returns ``(filing, observation)`` for the current declaration, or
    ``None`` when the taxpayer has filed no 036 in the span — silence, not
    a default, because stamping one would invent an enrolment.

    The PDF is parsed from memory and never written to disk: it is the
    taxpayer's own filed declaration, and
    ``sensitive-financial-data-secure-storage-only`` allows decrypted
    evidence to exist only transiently in process memory.
    """
    from ...adapters.inbound.declaracion import parse_declaracion_bytes
    from ...core import Period
    from . import capture_justificante_snapshot

    filings = await pull_filed_036(bucket_id=bucket_id, year_from=year_from, year_to=year_to)
    current = current_censal_state(filings)
    if current is None:
        return None
    snapshot = await capture_justificante_snapshot(
        bucket_id=bucket_id,
        modelo=Modelo.M036.value,
        year=current.ejercicio,
        period=Period.from_year_and_code(current.ejercicio, _CENSAL_PERIOD_CODE),
    )
    observation = parse_declaracion_bytes(
        snapshot.decoded_pdf_bytes(),
        source_label=f"filed 036 {current.ejercicio} expediente {current.expediente_id}",
        modelo_override=Modelo.M036.value,
        año_override=current.ejercicio,
        period_override=_CENSAL_PERIOD_CODE,
    )
    return current, observation


async def pull_filed_036(*, bucket_id: str, year_from: int, year_to: int) -> tuple[Filed036Declaration, ...]:
    """Live-read the declarations register for filed 036s across a year span.

    Composes the shipped expediente capture, so the read gate, the
    authenticated session, and the persisted snapshot all behave exactly as
    they do for a justificante pull. A year with no 036 contributes nothing
    rather than failing the span — a taxpayer files a censal declaration
    only when something changes, so most years are legitimately empty.
    """
    collected: list[Filed036Declaration] = []
    for year in range(year_from, year_to + 1):
        snapshot = await capture_expedientes(bucket_id=bucket_id, modelo=Modelo.M036.value, year=year)
        collected.extend(filed_036_declarations(snapshot.declarations))
    return tuple(sorted(collected, key=lambda filing: filing.presented_at))


__all__ = [
    "CENSO_FILED_ON_FACT_PATH",
    "CENSO_STATUS_FACT_PATH",
    "Filed036Declaration",
    "causa_casilla_event_kinds",
    "censo_facts_from_filed_036",
    "classify_censal_event",
    "classify_from_causa_casillas",
    "current_censal_state",
    "filed_036_declarations",
    "pull_censal_declaration",
    "pull_filed_036",
]
