"""Contract tests for the pure installed-workbench generation assembler."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from ...core.errors.hierarchy import InternalInvariantError
from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.modelos.calculation_revision import CalculationRevisionCatalogue, CalculationRevisionState
from ...domain.modelos.filing_record import ModeloRecordCatalogue
from ...domain.modelos.work_unit import WorkUnitCatalogue
from ...domain.user_profile.values import (
    UserProfileFact,
)
from .. import workbench_generation_calendar as calendar_module
from ..ledger.workspace import (
    LedgerWorkspaceArea,
    LedgerWorkspaceAreaStateV1,
    LedgerWorkspaceProjectionV1,
    LedgerWorkspaceSource,
    LedgerWorkspaceStatus,
)
from ..overview.calendar_models import OverviewCalendar, OverviewCalendarRange
from ..overview.home import (
    HomeAccountSession,
    HomeAvailability,
    HomeDeclarationState,
    HomeSessionPosture,
)
from ..overview.tests.calendar_test_support import modelo_record
from ..workbench_generation import (
    InstalledWorkbenchGenerationProviderV1,
    assemble_workbench_generation,
    assemble_workbench_generation_from,
)
from ..workbench_generation_contracts import (
    WorkbenchGenerationAvailability,
    WorkbenchGenerationInputsV1,
    WorkbenchGenerationSourceResultV1,
)
from .workbench_generation_support import (
    NOW,
    ChangingLedgerStore,
    Repository,
    StableStore,
    admission,
    inputs,
    ledger_ports,
    plain_generation_door,
    profile_record,
    stub_empty_calendar,
    synthetic_transaction,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_secure_profile_provider_refuses_a_ledger_written_during_capture(
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A ledger write between the two reads refuses the whole generation.

    The guard was total when it was written; it stopped being so when Ledger
    arrived, because the door began reading two stores it never re-checked. A
    generation could then carry a Ledger snapshot from a different instant
    than its Declarations with nothing to detect it.
    """
    from ...domain.invoices.catalogue import InvoiceCatalogue
    from ...domain.transactions.models import TransactionCatalogue

    profile = Repository(profile_record(authority_operation))
    work_units = Repository(WorkUnitCatalogue())
    revisions = Repository(CalculationRevisionCatalogue())
    filings = Repository(ModeloRecordCatalogue())

    stub_empty_calendar(monkeypatch)
    written = TransactionCatalogue.model_validate([synthetic_transaction()])
    door = plain_generation_door(
        authority_operation,
        profile=profile,
        work_units=work_units,
        revisions=revisions,
        filings=filings,
        ledger_action_ports=ledger_ports(
            authority_operation,
            transactions=ChangingLedgerStore(TransactionCatalogue(), written),
            invoices=StableStore(InvoiceCatalogue()),
        ),
    )

    with pytest.raises(InternalInvariantError, match="changed during capture"):
        door.read_workbench_generation_inputs()


def test_a_quiet_ledger_publishes_its_generation(
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The guard must not refuse a capture nothing wrote during."""
    from ...domain.invoices.catalogue import InvoiceCatalogue
    from ...domain.transactions.models import TransactionCatalogue

    profile = Repository(profile_record(authority_operation))
    work_units = Repository(WorkUnitCatalogue())
    revisions = Repository(CalculationRevisionCatalogue())
    filings = Repository(ModeloRecordCatalogue())

    stub_empty_calendar(monkeypatch)
    door = plain_generation_door(
        authority_operation,
        profile=profile,
        work_units=work_units,
        revisions=revisions,
        filings=filings,
        ledger_action_ports=ledger_ports(
            authority_operation,
            transactions=StableStore(TransactionCatalogue()),
            invoices=StableStore(InvoiceCatalogue()),
        ),
    )

    inputs = door.read_workbench_generation_inputs()

    assert inputs.ledger.value is not None


def test_calendar_evidence_scope_preserves_available_empty_for_historical_filing() -> None:
    """A prior-year filing is outside the query, not orphaned or never captured."""
    historical = modelo_record()
    schedule = OverviewCalendar(
        range=OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 12, 31)),
        entries=(),
        generated_at=NOW,
        evaluated_on=NOW.date(),
    )

    scoped = calendar_module.scope_filing_records((historical,), schedule)

    assert scoped == ()


def test_generation_projects_home_and_never_turns_missing_areas_into_empty() -> None:
    """Missing production loaders remain explicit refusals in every output area."""
    generation = assemble_workbench_generation(inputs())

    assert generation.home.projection is not None
    assert generation.home.availability is WorkbenchGenerationAvailability.AVAILABLE
    assert generation.ledger.projection is None
    assert generation.declarations.projection is None
    assert generation.declarations_calendar.projection is None
    assert generation.aeat_sync.projection is None
    assert generation.modelo.projection is None
    assert generation.search.projection is None
    assert generation.search.availability is WorkbenchGenerationAvailability.NEVER_CAPTURED
    assert generation.search.refusal == "source.ledger"


def test_generation_search_refusal_preserves_mixed_source_unavailability() -> None:
    """A single unavailable source prevents a falsely empty search snapshot."""
    generation = assemble_workbench_generation(
        inputs(aeat_sync=WorkbenchGenerationSourceResultV1.unavailable(refusal="source.aeat_down"))
    )

    assert generation.search.projection is None
    assert generation.search.availability is WorkbenchGenerationAvailability.UNAVAILABLE
    assert generation.search.refusal == "source.ledger"


def test_generation_accepts_stale_value_without_collapsing_it_to_available() -> None:
    """A stale preloaded value remains available to the caller as stale evidence."""
    stale = WorkbenchGenerationSourceResultV1[tuple[int, ...]].stale(
        (1, 2),
        observed_at=NOW,
        refusal="source.stale",
    )

    assert stale.value == (1, 2)
    assert stale.availability is WorkbenchGenerationAvailability.STALE
    assert stale.refusal == "source.stale"


def test_input_admissions_must_name_the_installed_search_destinations() -> None:
    """Search cannot be assembled against a different destination authority."""
    values = inputs().model_dump()
    values["declarations_admission"] = admission("workbench.ledger")
    with pytest.raises(ValidationError, match=r"workbench\.declarations"):
        WorkbenchGenerationInputsV1.model_validate(values)


def test_output_has_no_source_value_field_or_input_wrapper() -> None:
    """Output serialization contains only projection results, never source inputs."""
    generation = assemble_workbench_generation(inputs())
    payload = generation.model_dump_json()

    assert "value" not in WorkbenchGenerationInputsV1.model_fields
    assert "value" not in type(generation).model_fields
    assert all(
        "value" not in type(getattr(generation, name)).model_fields
        for name in (
            "home",
            "ledger",
            "declarations",
            "declarations_calendar",
            "aeat_sync",
            "modelo",
            "search",
        )
    )
    assert '"value"' not in payload
    assert "WorkbenchGenerationSourceResultV1" not in repr(generation)


def test_source_and_projection_result_models_are_frozen_and_closed() -> None:
    """Both sides reject mutation and undeclared fields at their boundary."""
    source = WorkbenchGenerationSourceResultV1[tuple[int, ...]].never_captured(refusal="source.never")
    with pytest.raises(ValidationError):
        WorkbenchGenerationSourceResultV1[tuple[int, ...]](
            availability=WorkbenchGenerationAvailability.NEVER_CAPTURED,
            refusal="source.never",
            unexpected=True,
        )
    with pytest.raises(ValidationError):
        source.availability = WorkbenchGenerationAvailability.UNAVAILABLE  # type: ignore[misc]


@dataclass(frozen=True)
class _Door:
    """Structural read-door implementation for the protocol contract."""

    inputs: WorkbenchGenerationInputsV1

    def read_workbench_generation_inputs(self) -> WorkbenchGenerationInputsV1:
        return self.inputs


def test_structural_read_door_is_accepted() -> None:
    """Composition accepts a typed protocol implementation without a frontend."""
    generation = assemble_workbench_generation_from(_Door(inputs()))
    assert generation.home.projection is not None


def _ledger_projection_with_statuses(
    status: LedgerWorkspaceStatus,
    *,
    unmeasured: LedgerWorkspaceArea | None = None,
) -> LedgerWorkspaceProjectionV1:
    """A Ledger projection whose areas carry a chosen status, one optionally unmeasured."""
    return LedgerWorkspaceProjectionV1(
        bucket_id="bucket",
        areas=tuple(
            LedgerWorkspaceAreaStateV1(
                area=area,
                sources=(LedgerWorkspaceSource.LOCAL_LEDGER,),
                status=LedgerWorkspaceStatus.UNMEASURED if area is unmeasured else status,
                item_count=2,
            )
            for area in LedgerWorkspaceArea
        ),
        entries=(),
        review_transaction_ids=(),
        invoice_reconciliations=(),
        link_inconsistencies=(),
        affected_declarations=(),
    )


def test_home_refuses_its_ledger_zone_rather_than_publishing_an_unmeasured_zero() -> None:
    """An unmeasured Ledger area must not reach Home as the number nought.

    `LedgerWorkspaceAreaStateV1.item_count` is a plain integer, so an area that
    nobody measured reports 0 -- the same value a genuinely empty area reports.
    The Ledger workspace keeps them apart through `status`, rendering
    UNMEASURED as "Sin medir" rather than a digit. Home has no such room: its
    readiness block is four bare numbers, and a zero there reads as a finding.

    So the whole block refuses when ANY of its four areas is unmeasured, rather
    than publishing three real counts beside one fabricated one. Partial truth
    in a summary is indistinguishable from whole truth once rendered.
    """
    from ..overview.home import HomeLedgerReadiness
    from ..workbench_generation_home import home_ledger_readiness

    measured = _ledger_projection_with_statuses(LedgerWorkspaceStatus.READY)
    readiness = home_ledger_readiness(measured)
    assert isinstance(readiness, HomeLedgerReadiness)
    assert (readiness.entries, readiness.requiring_review) == (2, 2)

    for area in (
        LedgerWorkspaceArea.ENTRIES,
        LedgerWorkspaceArea.REVIEW,
        LedgerWorkspaceArea.CLASSIFICATION,
        LedgerWorkspaceArea.EVIDENCE,
    ):
        partial = _ledger_projection_with_statuses(LedgerWorkspaceStatus.READY, unmeasured=area)
        assert home_ledger_readiness(partial) is None, (
            f"an unmeasured {area.value} area still produced a readiness block, so Home renders a zero nobody measured"
        )

    assert home_ledger_readiness(None) is None


def test_a_zone_awaiting_a_pull_is_never_captured_not_unavailable() -> None:
    """Home must not report absent remote data as a broken reader.

    AEAT notifications exist only once a pull has persisted a snapshot. Before
    that the reader is perfectly able to answer and the DATA is what is
    missing, which is exactly the distinction `no-silent-under-declaration`
    keeps: UNAVAILABLE says something is wrong, NEVER_CAPTURED says nothing has
    been fetched yet. Only the second tells the operator that a pull is the
    action that resolves the zone; the first sends them looking for a fault
    that does not exist.

    Asserted on the reason code as well as the availability, because a zone
    that carries the right state under a reason code naming a "reader
    unavailable" still tells the operator the wrong story wherever that code is
    rendered or logged.
    """
    from datetime import UTC, datetime

    from ..overview.home import HomeAvailability, HomeZoneState
    from ..workbench_generation_home import secure_profile_home_input

    observed_at = datetime(2026, 9, 4, tzinfo=UTC)
    home = secure_profile_home_input(
        observed_at=observed_at,
        account_session=HomeAccountSession(posture=HomeSessionPosture.NO_PROFILE),
        agenda=None,
        agenda_evidence_state=HomeZoneState(
            availability=HomeAvailability.NEVER_CAPTURED,
            reason_code="workbench.home.agenda_evidence_never_pulled",
        ),
        ledger=None,
        declarations=None,
    )

    assert home.messages_state.availability is HomeAvailability.NEVER_CAPTURED, (
        "Home reports never-pulled AEAT notifications as an unavailable reader, "
        "which points the operator at a fault instead of at the pull"
    )
    assert home.messages_state.reason_code is not None
    assert "reader_unavailable" not in home.messages_state.reason_code, (
        f"the reason code {home.messages_state.reason_code!r} still blames the reader"
    )


def test_only_a_verified_calculation_reads_as_ready_on_home() -> None:
    """READY is the one Home state that must never be reached by inference.

    Telling an operator a declaration is ready to file when nobody verified it
    is a filing-grade harm, so the mapping errs in exactly one direction: the
    only calculation state that becomes READY is the one whose name says
    verified and complete. Every other state resolves to something that keeps
    work in front of them.

    The mapping is read from the domain's own vocabulary rather than invented
    for Home, and this asserts the whole table so a new calculation state
    cannot be added and silently default to anything.
    """
    from ..workbench_generation_home import HOME_DECLARATION_STATES

    assert set(HOME_DECLARATION_STATES) == set(CalculationRevisionState), (
        "a calculation state has no declared Home reading, so it would raise or "
        "default rather than being mapped deliberately"
    )

    ready = {state for state, home in HOME_DECLARATION_STATES.items() if home is HomeDeclarationState.READY}
    assert ready == {CalculationRevisionState.VERIFICADO_COMPLETO}, (
        f"only a verified-complete calculation may read as READY on Home; found {sorted(ready)}"
    )

    assert HOME_DECLARATION_STATES[CalculationRevisionState.BORRADOR] is (HomeDeclarationState.NEEDS_REVIEW), (
        "an unverified calculation must keep review in front of the operator"
    )


def test_home_offers_ledger_work_only_when_there_is_some_and_never_for_an_unmeasured_area() -> None:
    """An offered action must correspond to work that exists and can be named.

    Two failure modes, both worse than an empty zone. Offering "classify"
    when the classification area holds zero entries sends the operator to an
    empty screen. Offering it when the area is UNMEASURED is the same mistake
    dressed as a fact: `item_count` is a plain integer, so an area nobody
    measured reports the same zero a finished one does.

    Also asserts the reason codes are Home's OWN declared vocabulary. A code
    with no `tui.home.reason.*` entry renders the degraded generic line, so an
    action invented to fill the zone would arrive unreadable.
    """
    from ..workbench_generation_home import home_ledger_actions

    populated = _ledger_projection_with_statuses(LedgerWorkspaceStatus.NEEDS_ATTENTION)
    offered = home_ledger_actions(populated)
    assert offered is not None
    assert {item.reason_code for item in offered} == {
        "ledger_classification_pending",
        "evidence_missing",
    }
    assert [item.rank for item in offered] == list(range(len(offered)))

    catalogue = _home_reason_keys_for_test()
    for item in offered:
        assert f"tui.home.reason.{item.reason_code}" in catalogue, (
            f"offered action reason {item.reason_code!r} has no copy, so Home degrades to its generic line"
        )

    for area in (LedgerWorkspaceArea.CLASSIFICATION, LedgerWorkspaceArea.EVIDENCE):
        unmeasured = _ledger_projection_with_statuses(LedgerWorkspaceStatus.NEEDS_ATTENTION, unmeasured=area)
        assert home_ledger_actions(unmeasured) is None, (
            f"an unmeasured {area.value} area still produced an offer, so Home invites the "
            f"operator to work nobody measured"
        )

    assert home_ledger_actions(None) is None


def _home_reason_keys_for_test() -> frozenset[str]:
    """Every `tui.home.reason.*` key the Spanish catalogue declares."""
    import yaml

    root = Path(__file__).resolve().parents[2] / "locales" / "es" / "common.yml"
    raw = yaml.safe_load(root.read_text(encoding="utf-8"))
    reasons = raw["tui"]["home"]["reason"]
    return frozenset(f"tui.home.reason.{name}" for name in reasons)


def test_a_declaration_needing_review_is_offered_with_its_own_address() -> None:
    """A declaration-addressed action carries the declaration it is about.

    `declaration_needs_review` without an address is advice; with modelo,
    filing year and period it is a task the operator can act on, and Home
    renders that address beside the row. The action is the catalogue's
    `operator.modelo.work.revisions`, which takes the work unit id the resume
    already carries, so nothing is minted to fill the zone.

    Only NEEDS_REVIEW is offered. A verified, filed, draft or discarded
    declaration is not work the operator has been asked to do, and offering it
    would make the zone a list of everything rather than a list of what is
    outstanding.
    """
    from ..overview.home import HomeDeclarationResume
    from ..workbench_generation_home import home_declaration_actions

    def _resume(state: HomeDeclarationState, unit: str) -> HomeDeclarationResume:
        return HomeDeclarationResume(
            work_unit_id=unit * 64,
            modelo="303",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "3T"),
            name=f"{unit}-declaration",
            state=state,
        )

    resumes = tuple(
        _resume(state, letter)
        for state, letter in (
            (HomeDeclarationState.NEEDS_REVIEW, "a"),
            (HomeDeclarationState.READY, "b"),
            (HomeDeclarationState.FILED, "c"),
            (HomeDeclarationState.DRAFT, "d"),
            (HomeDeclarationState.DISCARDED, "e"),
        )
    )
    offered = home_declaration_actions(resumes)

    assert len(offered) == 1, (
        f"only a declaration needing review is outstanding work; got {[item.reason_code for item in offered]}"
    )
    only = offered[0]
    assert only.reason_code == "declaration_needs_review"
    assert (only.modelo, only.filing_year) == ("303", 2026)
    assert only.period is not None, "an addressed action without its period cannot be acted on"
    assert only.action.action.action_id == "operator.modelo.work.revisions"

    assert home_declaration_actions(None) == ()


def test_only_a_blocking_dependency_finding_reads_as_a_blocked_declaration() -> None:
    """`blocked_dependency` is produced from the domain's own word, or not at all.

    `CROSS_PERIOD_DEPENDENCY_UNCLEAN` names the condition Home's
    `blocked_dependency` describes, so that one code is grounded. The other two
    Home declares are deliberately unproduced: nothing in
    `ModeloVerificationFindingKind` names evidence, and routing
    `blocked_review` to BLOCKING_RULE or MISSING_REQUIRED_CASILLA would be a
    guess wearing a finding's clothes.

    Severity and completeness both gate it. An ADVISORY finding of the same
    kind is information rather than a blocker, and a report that is not BLOCKED
    has nothing outstanding -- offering either as blocked work would send the
    operator at something nothing is waiting on.
    """
    from ...domain.calculations.registry.tests.published_authority import published_snapshot
    from ...domain.modelos.verification_report import (
        ModeloVerificationFinding,
        ModeloVerificationFindingKind,
        ModeloVerificationFindingSeverity,
        VerificationCompletenessStatus,
        VerificationReport,
        VerificationReportCatalogue,
        derive_verification_report_id,
    )
    from ..workbench_generation_home import dependency_blocked_revisions

    def _catalogue(
        kind: ModeloVerificationFindingKind,
        severity: ModeloVerificationFindingSeverity,
        status: VerificationCompletenessStatus,
    ) -> VerificationReportCatalogue:
        findings = (
            ModeloVerificationFinding(
                kind=kind,
                severity=severity,
                message_locale_key="application.modelo.findings.cross_period_dependency",
                legal_refs=("ley-37-1992:art-99",),
            ),
        )
        report = VerificationReport(
            # Content-addressed: the id is DERIVED from the report's own facts,
            # so it is computed here rather than invented, which also means a
            # fixture cannot drift from the identity the domain would assign.
            verification_report_id=derive_verification_report_id(
                calculation_revision_id="b" * 64,
                completeness_status=status,
                findings=findings,
                verified_by="operator",
            ),
            calculation_revision_id="b" * 64,
            registry_snapshot_ref=published_snapshot("303", filing_year=2026, period="1T").snapshot_ref,
            completeness_status=status,
            findings=findings,
            run_at=datetime(2026, 9, 4, tzinfo=UTC),
            verified_by="operator",
            granted_verificado_completo=False,
        )
        return VerificationReportCatalogue(reports={report.verification_report_id: report})

    blocked = _catalogue(
        ModeloVerificationFindingKind.CROSS_PERIOD_DEPENDENCY_UNCLEAN,
        ModeloVerificationFindingSeverity.BLOCKING,
        VerificationCompletenessStatus.BLOCKED,
    )
    assert dependency_blocked_revisions(blocked) == frozenset({"b" * 64})

    warning = _catalogue(
        ModeloVerificationFindingKind.CROSS_PERIOD_DEPENDENCY_UNCLEAN,
        ModeloVerificationFindingSeverity.WARNING,
        VerificationCompletenessStatus.BLOCKED,
    )
    assert dependency_blocked_revisions(warning) == frozenset(), (
        "a WARNING dependency finding is information, not a blocker"
    )

    other_kind = _catalogue(
        ModeloVerificationFindingKind.BLOCKING_RULE,
        ModeloVerificationFindingSeverity.BLOCKING,
        VerificationCompletenessStatus.BLOCKED,
    )
    assert dependency_blocked_revisions(other_kind) == frozenset(), (
        "only the dependency finding kind may read as blocked_dependency; another kind "
        "reaching it would be a guess about what the operator is blocked on"
    )

    assert dependency_blocked_revisions(None) == frozenset()


def test_an_incomplete_profile_publishes_reasoned_zones_instead_of_failing(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A profile the taxpayer projection refuses must not stop the workbench.

    Declaring one IVA fact claims the whole IVA block, and the projection then
    refuses until the rest of that block is answered. The operator reached this
    state by editing one field, so the generation serves every zone it can and
    names the missing paths on the zones that need the projection.
    """
    record = profile_record(
        authority_operation,
        facts=(UserProfileFact(path="iva.regime", value="GENERAL"),),
    )

    generation = InstalledWorkbenchGenerationProviderV1(
        plain_generation_door(authority_operation, profile=Repository(record))
    )()

    assert generation.home.availability is WorkbenchGenerationAvailability.AVAILABLE
    home = generation.home.projection
    assert home is not None
    assert home.agenda_state.availability is HomeAvailability.UNAVAILABLE
    assert home.agenda_state.reason_code == "workbench.home.taxpayer_profile_incomplete"
    # A declared general regime settles the Modelo 303 composition, so only the
    # block's other unanswered facts remain owed.
    assert "iva.m303_regime_composition" not in home.agenda_state.missing_profile_paths
    assert "iva.redeme_enrolled" in home.agenda_state.missing_profile_paths
    calendar = generation.declarations_calendar.projection
    assert calendar is not None
    assert calendar.entries == ()
    assert {source.reason_code for source in calendar.sources} == {"workbench.home.taxpayer_profile_incomplete"}
    assert generation.declarations.projection is not None


def test_an_undeclared_taxpayer_model_leaves_the_agenda_unavailable(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """No taxpayer model means no schedule, which is not the same as no dates."""
    generation = InstalledWorkbenchGenerationProviderV1(
        plain_generation_door(authority_operation, profile=Repository(profile_record(authority_operation)))
    )()

    home = generation.home.projection
    assert home is not None
    assert home.agenda_state.availability is HomeAvailability.UNAVAILABLE
    assert home.agenda_state.reason_code == "workbench.calendar.taxpayer_model_undeclared"
    assert home.agenda == ()
