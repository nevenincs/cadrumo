"""Pure assembly of one installed-workbench projection generation.

The installed-session composition root owns secure readers and source
projectors.  It supplies the already-loaded, frontend-neutral inputs declared
here; this module joins those inputs into one immutable generation and derives
the Home and search projections through their existing application composers.

An absent reader result is deliberately not represented by an empty tuple or
an empty projection.  ``LOCKED``, ``NEVER_CAPTURED`` and ``UNAVAILABLE`` are
separate source outcomes and carry an explicit refusal.  The output contract
does not retain the source-input models, so raw source facts cannot cross this
assembly boundary accidentally.

Core types:
:class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`,
:class:`~cadrumo.domain.invoices.models.InvoiceCatalogue`,
:class:`~cadrumo.domain.modelos.filing_record.ModeloRecord`,
:class:`~cadrumo.domain.deadlines.models.TaxpayerProfile`,
:class:`~cadrumo.domain.transactions.models.TransactionCatalogue`,
:class:`~cadrumo.domain.user_profile.values.UserProfileRecord`.
"""

from __future__ import annotations

from typing import Final

from ..core.identifier_grammar import NamespacedId
from ..core.time.utc import UtcInstant
from ..domain.modelos.calculation_revision import (
    CalculationRevisionState,
)
from ..domain.modelos.verification_report import (
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
    VerificationReportCatalogue,
)
from ..domain.modelos.work_unit import WorkUnitCatalogue, WorkUnitState
from .aeat_sync.workspace import AeatSyncWorkspaceProjectionV1
from .ledger.workspace import (
    LedgerWorkspaceArea,
    LedgerWorkspaceProjectionV1,
    LedgerWorkspaceStatus,
)
from .modelo.declarations_calendar import (
    DeclarationsCalendarProjectionV1,
)
from .modelo.declarations_workspace_contracts import DeclarationsWorkspaceProjectionV1
from .modelo.workspace_models import (
    ModeloWorkspaceProjectionV1,
)
from .overview.agenda import OverviewAgenda
from .overview.home import (
    HOME_REASON_BLOCKED_DEPENDENCY,
    HOME_REASON_DECLARATION_NEEDS_REVIEW,
    HOME_REASON_EVIDENCE_MISSING,
    HOME_REASON_LEDGER_CLASSIFICATION_PENDING,
    HomeAccountSession,
    HomeAvailability,
    HomeDeclarationResume,
    HomeDeclarationState,
    HomeLedgerReadiness,
    HomeNextAction,
    HomeProjectionInput,
    HomeZoneState,
)
from .overview.next_actions import declare_next_action
from .search.workbench import WorkbenchDestinationAdmission, WorkbenchDestinationAdmissionState
from .workbench_generation_calendar import _WorkbenchCalendarInputs
from .workbench_generation_contracts import (
    WorkbenchGenerationInputsV1,
    WorkbenchGenerationSourceResultV1,
)


def _secure_profile_home_input(
    *,
    observed_at: UtcInstant,
    account_session: HomeAccountSession,
    agenda: OverviewAgenda | None,
    agenda_evidence_state: HomeZoneState,
    ledger: LedgerWorkspaceProjectionV1 | None,
    declarations: tuple[HomeDeclarationResume, ...] | None,
    blocked_revision_ids: frozenset[str] = frozenset(),
    agenda_refusal: HomeZoneState | None = None,
) -> HomeProjectionInput:
    """Assemble Home from the authorities this session actually read.

    Each zone carries its own state. A zone with no installed reader stays
    UNAVAILABLE and names what is missing, because a Home that renders an
    unread authority as an empty list is indistinguishable from one whose
    operator genuinely has nothing outstanding.
    """

    def unavailable(reason_code: str) -> HomeZoneState:
        return HomeZoneState(availability=HomeAvailability.UNAVAILABLE, reason_code=reason_code)

    def never_captured(reason_code: str) -> HomeZoneState:
        """A zone whose source is readable but has never been captured.

        Distinct from `unavailable`, which says the reader cannot answer. An
        operator reading "unavailable" looks for something broken; one reading
        "never captured" knows the data is simply not here yet and that a pull
        is what produces it. Collapsing the two hides the only action that
        would resolve the zone.
        """
        return HomeZoneState(availability=HomeAvailability.NEVER_CAPTURED, reason_code=reason_code)

    declarations_state = (
        HomeZoneState(availability=HomeAvailability.AVAILABLE, observed_at=observed_at)
        if declarations is not None
        else unavailable("workbench.home.declarations_resume_projector_unavailable")
    )
    addressed = _home_declaration_actions(declarations, blocked_revision_ids)
    cross_cutting = _home_ledger_actions(ledger)
    actions = (
        None
        if cross_cutting is None
        else (
            *addressed,
            *(item.model_copy(update={"rank": len(addressed) + offset}) for offset, item in enumerate(cross_cutting)),
        )
    )
    actions_state = (
        HomeZoneState(availability=HomeAvailability.AVAILABLE, observed_at=observed_at)
        if actions is not None
        else unavailable("workbench.home.actions_projector_unavailable")
    )
    readiness = _home_ledger_readiness(ledger)
    ledger_state = (
        HomeZoneState(availability=HomeAvailability.AVAILABLE, observed_at=observed_at)
        if readiness is not None
        else unavailable("workbench.ledger.snapshot_projector_unavailable")
    )

    return HomeProjectionInput(
        generated_at=observed_at,
        account=account_session,
        actions_state=actions_state,
        actions=actions or (),
        declarations_state=declarations_state,
        declarations=declarations or (),
        ledger_state=ledger_state,
        agenda_state=(
            HomeZoneState(availability=HomeAvailability.AVAILABLE, observed_at=observed_at)
            if agenda is not None
            else agenda_refusal or unavailable("workbench.home.agenda_projector_unavailable")
        ),
        ledger_readiness=readiness,
        overview_agenda=agenda,
        # The AEAT side of the agenda is whatever the evidence read concluded,
        # not a separate refusal: before any pull it is NEVER CAPTURED, and
        # Home must say that rather than call the whole zone unavailable.
        agenda_evidence_state=agenda_evidence_state,
        # AEAT notifications exist only once a pull has persisted a snapshot, so
        # before that the reader is fine and the DATA is absent. The previous
        # code called this reader-unavailable, which named the wrong thing and
        # pointed the operator at a fault that does not exist.
        messages_state=never_captured("workbench.home.messages_never_pulled"),
    )


_HOME_LEDGER_AREAS: Final = (
    (LedgerWorkspaceArea.ENTRIES, "entries"),
    (LedgerWorkspaceArea.REVIEW, "requiring_review"),
    (LedgerWorkspaceArea.CLASSIFICATION, "unclassified"),
    (LedgerWorkspaceArea.EVIDENCE, "missing_evidence"),
)


def _home_ledger_readiness(ledger: LedgerWorkspaceProjectionV1 | None) -> HomeLedgerReadiness | None:
    """Home's four Ledger counts, or nothing when any of them was not measured.

    `item_count` is always an integer, so a zero alone cannot be trusted: an
    area whose status is UNMEASURED reports zero for "nobody looked", the same
    value a genuinely empty area reports for "I looked and there was nothing".
    Home renders these as bare numbers with no room to qualify them, so an
    unmeasured area makes the whole readiness block refuse and name itself
    rather than publish a zero the operator would read as a finding.
    """
    if ledger is None:
        return None
    by_area = {state.area: state for state in ledger.areas}
    counts: dict[str, int] = {}
    for area, field in _HOME_LEDGER_AREAS:
        state = by_area.get(area)
        if state is None or state.status is LedgerWorkspaceStatus.UNMEASURED:
            return None
        counts[field] = state.item_count
    return HomeLedgerReadiness(**counts)


_HOME_DECLARATION_STATES: Final[dict[CalculationRevisionState, HomeDeclarationState]] = {
    # Read from the domain's own vocabulary, not invented for Home.
    # `VERIFICADO_COMPLETO` says verified and complete, which is the only thing
    # READY can honestly mean; `BORRADOR` is a calculation that exists and has
    # not been verified, which is exactly NEEDS_REVIEW; both PRESENTADO forms
    # are filed, superseded or not.
    CalculationRevisionState.BORRADOR: HomeDeclarationState.NEEDS_REVIEW,
    CalculationRevisionState.VERIFICADO_COMPLETO: HomeDeclarationState.READY,
    CalculationRevisionState.PRESENTADO: HomeDeclarationState.FILED,
    CalculationRevisionState.PRESENTADO_SUPERSEDIDO: HomeDeclarationState.FILED,
    CalculationRevisionState.DESCARTADO: HomeDeclarationState.DISCARDED,
}


"""How a calculation's state reads on Home.

The mapping ERRS SAFE in the one direction that matters: nothing becomes READY
except the state that literally says verified and complete. Telling an operator
a declaration is ready to file when nobody verified it is a filing-grade harm,
so every other state resolves to something that keeps work in front of them.
"""


def _home_declarations(
    declarations: DeclarationsWorkspaceProjectionV1 | None,
    work_units: WorkUnitCatalogue,
) -> tuple[HomeDeclarationResume, ...] | None:
    """Home's resumable declarations, or nothing when the workspace is refused."""
    if declarations is None:
        return None
    current_by_unit = {
        revision.work_unit_id: revision for revision in declarations.calculation_revisions if revision.is_current
    }
    resumes: list[HomeDeclarationResume] = []
    for ref in declarations.declarations:
        unit = work_units.work_units.get(ref.work_unit_id)
        if unit is None:
            # The declaration names a work unit this session did not load. Its
            # display name lives on the unit, so the row cannot be rendered
            # honestly and the zone refuses rather than inventing a label.
            return None
        revision = current_by_unit.get(ref.work_unit_id)
        if ref.state is WorkUnitState.DESCARTADO:
            state = HomeDeclarationState.DISCARDED
        elif ref.has_current_filing:
            state = HomeDeclarationState.FILED
        elif revision is None:
            # No calculation exists yet, so there is nothing to review or file.
            state = HomeDeclarationState.DRAFT
        else:
            state = _HOME_DECLARATION_STATES[revision.state]
        resumes.append(
            HomeDeclarationResume(
                work_unit_id=ref.work_unit_id,
                modelo=ref.modelo,
                filing_year=ref.filing_year,
                period=ref.period,
                name=unit.name,
                state=state,
                revision_id=revision.calculation_revision_id if revision is not None else None,
            )
        )
    return tuple(resumes)


_HOME_LEDGER_ACTIONS: Final = (
    (LedgerWorkspaceArea.CLASSIFICATION, "operator.ledger.classify", HOME_REASON_LEDGER_CLASSIFICATION_PENDING),
    (LedgerWorkspaceArea.EVIDENCE, "operator.ledger.evidence.review.list", HOME_REASON_EVIDENCE_MISSING),
)


"""Cross-cutting Ledger work Home can offer, in the order it is offered."""


def _dependency_blocked_revisions(
    verification: VerificationReportCatalogue | None,
) -> frozenset[str]:
    """Calculation revisions blocked by an unclean cross-period dependency.

    ONE finding kind is read, deliberately. `CROSS_PERIOD_DEPENDENCY_UNCLEAN`
    is `blocked_dependency` by its own name, so the reason Home renders is the
    domain's own word for the condition. The other two blocked reason codes
    Home declares are left unproduced: nothing in
    `ModeloVerificationFindingKind` names evidence, and routing
    `blocked_review` to BLOCKING_RULE or MISSING_REQUIRED_CASILLA would be a
    guess dressed as a finding.

    Only BLOCKING severity counts, and only on a report whose completeness is
    BLOCKED. An advisory finding of the same kind is information, not a
    blocker, and offering it as one would put work in front of an operator that
    nothing is actually waiting on.
    """
    if verification is None:
        return frozenset[str]()
    return frozenset(
        report.calculation_revision_id
        for report in verification.reports.values()
        if report.completeness_status is VerificationCompletenessStatus.BLOCKED
        and any(
            finding.kind is ModeloVerificationFindingKind.CROSS_PERIOD_DEPENDENCY_UNCLEAN
            and finding.severity is ModeloVerificationFindingSeverity.BLOCKING
            for finding in report.findings
        )
    )


def _home_declaration_actions(
    resumes: tuple[HomeDeclarationResume, ...] | None,
    blocked_revision_ids: frozenset[str] = frozenset(),
) -> tuple[HomeNextAction, ...]:
    """One action per declaration whose calculation is not yet verified.

    `operator.modelo.work.revisions` takes the work unit id the resume already
    carries, and listing a work unit's calculation revisions is precisely what
    `declaration_needs_review` asks the operator to do -- so the action is the
    catalogue's, the reason is Home's, and the address is the declaration's.
    Nothing here is minted for the zone.

    Ranked ahead of the cross-cutting Ledger offers because these name a single
    declaration the operator can finish, while "classify the ledger" is work
    spread across every record.
    """
    if resumes is None:
        return ()
    offered: list[HomeNextAction] = []
    for resume in resumes:
        blocked = resume.revision_id is not None and resume.revision_id in blocked_revision_ids
        if not blocked and resume.state is not HomeDeclarationState.NEEDS_REVIEW:
            continue
        offered.append(
            HomeNextAction(
                rank=len(offered),
                # A blocked declaration is named by its blocker rather than by
                # the generic review prompt: "a dependency is blocked" tells
                # the operator why the work will not close, where "needs
                # review" invites them to try and find out.
                reason_code=(HOME_REASON_BLOCKED_DEPENDENCY if blocked else HOME_REASON_DECLARATION_NEEDS_REVIEW),
                action=declare_next_action("operator.modelo.work.revisions", work_unit_id=resume.work_unit_id),
                modelo=resume.modelo,
                filing_year=resume.filing_year,
                period=resume.period,
            )
        )
    return tuple(offered)


def _home_ledger_actions(ledger: LedgerWorkspaceProjectionV1 | None) -> tuple[HomeNextAction, ...] | None:
    """Offer the Ledger work that is outstanding, or nothing when unmeasured.

    An UNMEASURED area yields no action rather than an action for zero items:
    `item_count` is a plain integer, so an unmeasured area reports the same
    zero a finished one does, and offering "classify 0 entries" is worse than
    offering nothing. The zone refuses as a whole under the same rule the
    readiness block uses.
    """
    if ledger is None:
        return None
    by_area = {state.area: state for state in ledger.areas}
    actions: list[HomeNextAction] = []
    for area, action_id, reason_code in _HOME_LEDGER_ACTIONS:
        state = by_area.get(area)
        if state is None or state.status is LedgerWorkspaceStatus.UNMEASURED:
            return None
        if state.item_count:
            actions.append(
                HomeNextAction(
                    rank=len(actions),
                    action=declare_next_action(action_id),
                    reason_code=reason_code,
                )
            )
    return tuple(actions)


def _generation_admission(
    destination: str,
    state: WorkbenchDestinationAdmissionState,
    *,
    reason_code: str | None = None,
) -> WorkbenchDestinationAdmission:
    return WorkbenchDestinationAdmission(destination=destination, state=state, reason_code=reason_code)


def _source_result[SourceT](
    value: SourceT | None,
    *,
    observed_at: UtcInstant,
    refusal: NamespacedId,
) -> WorkbenchGenerationSourceResultV1[SourceT]:
    if value is None:
        return WorkbenchGenerationSourceResultV1[SourceT].unavailable(refusal=refusal)
    return WorkbenchGenerationSourceResultV1[SourceT].available(value, observed_at=observed_at)


def _source_admission(
    destination: str,
    value: object | None,
    *,
    unavailable_reason: str,
) -> WorkbenchDestinationAdmission:
    if value is None:
        return _generation_admission(
            destination,
            WorkbenchDestinationAdmissionState.UNAVAILABLE,
            reason_code=unavailable_reason,
        )
    return _generation_admission(destination, WorkbenchDestinationAdmissionState.AVAILABLE)


def _build_workbench_generation_inputs(
    *,
    observed_at: UtcInstant,
    account_session: HomeAccountSession,
    calendar_inputs: _WorkbenchCalendarInputs,
    ledger: LedgerWorkspaceProjectionV1 | None,
    declarations: DeclarationsWorkspaceProjectionV1 | None,
    aeat_sync: AeatSyncWorkspaceProjectionV1 | None,
    aeat_sync_refusal: NamespacedId,
    modelo: tuple[ModeloWorkspaceProjectionV1, ...] | None,
    work_units: WorkUnitCatalogue,
    verification: VerificationReportCatalogue | None,
) -> WorkbenchGenerationInputsV1:
    return WorkbenchGenerationInputsV1(
        assembled_at=observed_at,
        home=WorkbenchGenerationSourceResultV1[HomeProjectionInput].available(
            _secure_profile_home_input(
                observed_at=observed_at,
                account_session=account_session,
                agenda=calendar_inputs.agenda,
                agenda_evidence_state=calendar_inputs.agenda_evidence_state,
                ledger=ledger,
                declarations=_home_declarations(declarations, work_units),
                blocked_revision_ids=_dependency_blocked_revisions(verification),
                agenda_refusal=calendar_inputs.agenda_refusal,
            ),
            observed_at=observed_at,
        ),
        ledger=_source_result(
            ledger,
            observed_at=observed_at,
            refusal="workbench.ledger.snapshot_projector_unavailable",
        ),
        declarations=_source_result(
            declarations,
            observed_at=observed_at,
            refusal="workbench.declarations.snapshot_projector_unavailable",
        ),
        declarations_calendar=WorkbenchGenerationSourceResultV1[DeclarationsCalendarProjectionV1].available(
            calendar_inputs.declarations_calendar,
            observed_at=observed_at,
        ),
        aeat_sync=_source_result(aeat_sync, observed_at=observed_at, refusal=aeat_sync_refusal),
        modelo=_source_result(
            modelo,
            observed_at=observed_at,
            refusal="workbench.modelo.bulk_reader_unavailable",
        ),
        ledger_admission=_source_admission(
            "workbench.ledger",
            ledger,
            unavailable_reason="workbench.ledger.snapshot_projector_unavailable",
        ),
        declarations_admission=_source_admission(
            "workbench.declarations",
            declarations,
            unavailable_reason="workbench.declarations.snapshot_projector_unavailable",
        ),
        aeat_sync_admission=_source_admission(
            "workbench.aeat_sync",
            aeat_sync,
            unavailable_reason=aeat_sync_refusal,
        ),
    )
