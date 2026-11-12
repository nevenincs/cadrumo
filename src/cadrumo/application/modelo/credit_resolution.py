"""Find, accept, revoke and apply the operator's resolutions of disputed Modelo figures.

A calculation persists each source disagreement it finds with the finding key of
its :class:`~cadrumo.domain.modelos.source_disagreement.SourceDisagreementFact`.
The operator answers one by its finding id, the leading characters of that key
that the refusal and the form show. This module matches the id against the
findings the work unit's current calculation persisted, so an id that names no
current finding is refused rather than stored: a resolution that matches nothing
would leave the operator believing a figure was accepted that was not.

A resolution covers exactly the finding it answers. A recalculation that
reproduces the same sources and amounts finds the same key and keeps it. A
changed amount, an added or removed source, another registry revision or a
changed declaration is another key, so the stored resolution no longer applies
and the calculation says so with ``credit_resolution_stale``.

A store that cannot be read is neither empty nor permissive. The lookup says it
is unreadable, no resolution is honoured, and the figure stays withheld;
:class:`CalculationRevision`, the saved calculation revision.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final

from ...core.filing_year import FilingYear
from ...core.i18n.render import tr
from ...core.time.utc import UtcInstant
from ...domain.modelos.calculation_revision_sources import (
    CALCULATION_SOURCE_ISSUE_MESSAGE_LIMIT,
    DISAGREEMENT_REASONS,
    CalculationNoteFact,
    CalculationNoteSentence,
    CalculationSourceIssue,
    RecordedCalculationNote,
)
from ...domain.modelos.credit_resolution import CreditResolutionRecord
from ...domain.modelos.source_disagreement import SourceDisagreementFact
from ..aggregation.source_mesh import CalculationSourceDiagnostic
from ..aggregation.source_resolution_operations import storage_degradation_resolution
from .calculation_note_gate import SOURCE_DISAGREEMENT_FINDING_ID_LENGTH, SourceDisagreementResolutions
from .calculation_notes import note_fact_text, what_locale_key
from .credit_resolution_repository import (
    CreditResolutionPersistenceError,
    CreditResolutionReader,
    CreditResolutionRefusedError,
    CreditResolutionRevokeRefusalReason,
    credit_resolution_refusal,
    revoke_refusal_reason,
)
from .declaration_refusal_profiles import DeclarationRefusalCause
from .disagreement_words import sources_facts, value_facts

if TYPE_CHECKING:
    from ...domain.modelos.calculation_revision import CalculationRevision
    from ...domain.modelos.work_unit import WorkUnit

__all__ = [
    "CREDIT_RESOLUTION_APPLIED_REASON",
    "CREDIT_RESOLUTION_STALE_REASON",
    "CreditResolutionLookup",
    "applied_credit_resolutions",
    "applied_resolution_notes",
    "credit_resolution_degradation_diagnostics",
    "credit_resolution_for_finding",
    "credit_resolutions_for_work",
    "find_finding",
    "load_credit_resolutions",
    "revoke_refusal_for",
    "stale_resolution_issues",
    "stored_resolution_for",
]

CREDIT_RESOLUTION_STALE_REASON: Final = "credit_resolution_stale"
"""The persisted reason of a figure whose accepted disagreement has since changed."""

CREDIT_RESOLUTION_APPLIED_REASON: Final = "credit_resolution_applied"
"""The reason of the note that restates an acceptance covering a disagreement of the calculation."""

_HEX_DIGITS: Final = frozenset("0123456789abcdef")


@dataclass(frozen=True, slots=True)
class CreditResolutionLookup:
    """Every resolution one declaration holds, or the failure that kept them from being read."""

    records: tuple[CreditResolutionRecord, ...] = field(default=())
    failure: CreditResolutionPersistenceError | None = None

    @property
    def unreadable(self) -> bool:
        """Whether the store could not be read, which is neither an empty store nor a permissive one."""
        return self.failure is not None

    @property
    def active(self) -> tuple[CreditResolutionRecord, ...]:
        """The resolutions that currently lift a hold; none when the store was unreadable."""
        return () if self.unreadable else tuple(record for record in self.records if record.active)

    @property
    def resolutions(self) -> SourceDisagreementResolutions:
        """The view the gate decides with."""
        return SourceDisagreementResolutions(
            finding_keys=frozenset(record.finding_key for record in self.active), unreadable=self.unreadable
        )


def load_credit_resolutions(
    reader: CreditResolutionReader, *, modelo: str, filing_year: FilingYear, period: str
) -> CreditResolutionLookup:
    """Read the resolutions of one declaration; a storage failure is an unreadable lookup, never an empty one."""
    try:
        return CreditResolutionLookup(
            records=reader.load_for_work(modelo=modelo, filing_year=filing_year, period=period)
        )
    except CreditResolutionPersistenceError as failure:
        return CreditResolutionLookup(failure=failure)


_RESOLVER_ID: Final = "credit_resolution"
_SOURCE_KIND: Final = "credit_resolution"


def credit_resolution_degradation_diagnostics(
    lookup: CreditResolutionLookup,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """The notes saying the resolutions could not be read, so none was honoured; none when they were read."""
    if lookup.failure is None:
        return ()
    return storage_degradation_resolution(
        resolver_id=_RESOLVER_ID, owned_sources=(), source_kinds=(_SOURCE_KIND,), error=lookup.failure
    ).diagnostics


def credit_resolutions_for_work(reader: CreditResolutionReader, work_unit: WorkUnit) -> SourceDisagreementResolutions:
    """The view of resolutions the gate decides ``work_unit`` with."""
    return load_credit_resolutions(
        reader,
        modelo=str(work_unit.modelo),
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
    ).resolutions


def find_finding(revision: CalculationRevision, finding_id: str) -> CalculationSourceIssue:
    """Return the disagreement ``revision`` persisted whose finding key begins with ``finding_id``.

    Raises:
        CreditResolutionRefusedError: The id is not a finding id, names no
            disagreement of this revision, or names more than one.

    ``revision`` is the :class:`CalculationRevision`, the saved calculation revision.
    """
    token = finding_id.strip().lower()
    if len(token) != SOURCE_DISAGREEMENT_FINDING_ID_LENGTH or not set(token) <= _HEX_DIGITS:
        raise credit_resolution_refusal("unknown_finding", DeclarationRefusalCause.CREDIT_FINDING_NAMED)
    matches = {
        issue.disagreement.finding_key: issue
        for issue in revision.source_issues
        if issue.disagreement is not None and issue.disagreement.finding_key.startswith(token)
    }
    if len(matches) != 1:
        raise credit_resolution_refusal("unknown_finding", DeclarationRefusalCause.CREDIT_FINDING_NAMED)
    return next(iter(matches.values()))


def stored_resolution_for(records: Iterable[CreditResolutionRecord], finding_id: str) -> CreditResolutionRecord:
    """Return the one stored resolution whose finding key begins with ``finding_id``.

    Raises:
        CreditResolutionRefusedError: The id names no stored resolution, or more than one.
    """
    matches = [record for record in records if record.finding_key.startswith(finding_id)]
    if len(matches) != 1:
        raise credit_resolution_refusal("unknown_finding", DeclarationRefusalCause.CREDIT_FINDING_NAMED)
    return matches[0]


def revoke_refusal_for(
    records: Iterable[CreditResolutionRecord], finding_id: str
) -> CreditResolutionRevokeRefusalReason | None:
    """Why the revocation would refuse the acceptance ``finding_id`` names, or ``None`` when it would take it back.

    It runs the checks the revocation runs, in its order: the id must name exactly one stored
    resolution, and that resolution must be active.
    """
    try:
        record = stored_resolution_for(records, finding_id)
    except CreditResolutionRefusedError as refused:
        return "unknown_finding" if refused.reason == "unknown_finding" else "not_resolved"
    return revoke_refusal_reason(record)


def credit_resolution_for_finding(
    issue: CalculationSourceIssue, *, reason: str, at: UtcInstant, by_session: str
) -> CreditResolutionRecord:
    """Build the active resolution that accepts the value the calculation used for ``issue``'s disagreement."""
    fact = issue.disagreement
    if fact is None:
        raise credit_resolution_refusal("unknown_finding", DeclarationRefusalCause.CREDIT_FINDING_READABLE)
    return CreditResolutionRecord(
        disagreement=fact,
        accepted_role=fact.selected_role,
        reason=reason,
        resolved_at=at,
        resolved_by_session=by_session,
    )


def applied_credit_resolutions(
    revision: CalculationRevision, lookup: CreditResolutionLookup
) -> tuple[CreditResolutionRecord, ...]:
    """The active resolutions that cover a disagreement ``revision`` persisted, in the order of its issues.

    ``revision`` is the :class:`CalculationRevision`, the saved calculation revision.
    """
    keys = {record.finding_key: record for record in lookup.active}
    applied: dict[str, CreditResolutionRecord] = {}
    for issue in revision.source_issues:
        if issue.disagreement is not None and issue.disagreement.finding_key in keys:
            applied.setdefault(issue.disagreement.finding_key, keys[issue.disagreement.finding_key])
    return tuple(applied.values())


def stale_resolution_issues(
    issues: Iterable[CalculationSourceIssue], lookup: CreditResolutionLookup
) -> tuple[CalculationSourceIssue, ...]:
    """Notes saying a figure was accepted, but is now disputed in another way than the one accepted.

    A disagreement is stale-resolved when an active resolution exists for the same
    figure of the same declaration and none covers this exact finding. The note
    withholds nothing by itself: the disagreement it restates still does.
    """
    active = lookup.active
    stale: list[CalculationSourceIssue] = []
    seen: set[str] = set()
    for issue in issues:
        fact = issue.disagreement
        if fact is None or issue.reason not in DISAGREEMENT_REASONS or fact.finding_key in seen:
            continue
        if _accepted_only_elsewhere(active, fact):
            seen.add(fact.finding_key)
            stale.append(_stale_issue(issue))
    return tuple(stale)


def _accepted_only_elsewhere(active: Iterable[CreditResolutionRecord], fact: SourceDisagreementFact) -> bool:
    accepted_here = [
        record
        for record in active
        if record.disagreement.key == fact.key and record.disagreement.value_channel == fact.value_channel
    ]
    return bool(accepted_here) and all(record.finding_key != fact.finding_key for record in accepted_here)


def _stale_issue(disagreement: CalculationSourceIssue) -> CalculationSourceIssue:
    fact = disagreement.disagreement
    figure = "" if fact is None else fact.key
    return CalculationSourceIssue(
        reason=CREDIT_RESOLUTION_STALE_REASON,
        binding_source=disagreement.binding_source,
        casilla_id=disagreement.casilla_id,
        message=(
            f"a resolution accepted an earlier disagreement of {figure!r}, "
            "which no longer applies to the figures now compared"
        )[:CALCULATION_SOURCE_ISSUE_MESSAGE_LIMIT],
        fact=CalculationNoteFact.of(
            CalculationNoteSentence.CREDIT_RESOLUTION_STALE, box=disagreement.casilla_id or figure
        ),
    )


def applied_resolution_notes(
    revision: CalculationRevision, lookup: CreditResolutionLookup
) -> tuple[RecordedCalculationNote, ...]:
    """One note, in words, for each acceptance that covers a disagreement ``revision`` persisted.

    Each note states the box, the value accepted, what every source stated, the
    finding id and the operator's reason, so a check, an export or a report that
    restates the calculation's notes says what the operator answered. The notes
    are derived from the stored resolutions and are never persisted with the
    calculation.

    ``revision`` is the :class:`CalculationRevision`, the saved calculation revision.
    """
    notes: list[RecordedCalculationNote] = []
    for record in applied_credit_resolutions(revision, lookup):
        fact = record.disagreement
        accepted = next(source for source in fact.sources if source.role is record.accepted_role)
        note_fact = CalculationNoteFact.of(
            CalculationNoteSentence.CREDIT_RESOLUTION_APPLIED,
            box=fact.reached_casillas[0] if fact.reached_casillas else fact.key,
            accepted=value_facts(accepted.value),
            sources=sources_facts(fact.sources),
            reason=record.reason,
        )
        notes.append(
            RecordedCalculationNote(
                reason=CREDIT_RESOLUTION_APPLIED_REASON,
                fact=note_fact,
                message=note_fact_text(note_fact),
                detail=tr(what_locale_key(CREDIT_RESOLUTION_APPLIED_REASON)),
            )
        )
    return tuple(notes)
