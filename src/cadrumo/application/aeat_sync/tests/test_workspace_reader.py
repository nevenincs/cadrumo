"""The pre-pull AEAT Sync reading, and the three local answers it must keep apart.

A local source this session READ and found empty is not the same fact as a local
source it never read, and neither is the same as the AEAT side nobody has pulled.
The row model carries three states for exactly that reason, and this proves the
reader spends all three rather than collapsing the first two.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import NoReturn

import pytest
from pydantic import ValidationError

from ....core.period import Period
from ....domain.modelos.filing_record import ModeloRecord
from ...auth.tests.certificate_secret_fakes import InMemoryCertificateSecretBackendFactory
from ...calculations.ports import FiledDeclaracionObservationProtocol
from ...live.filed_history_operation import (
    build_filed_history_operation_definition,
    build_filed_history_operation_registration,
)
from ...live.notification_ports import NotificationsPorts
from ...live.notifications_read_operation import (
    build_notifications_list_definition,
    build_notifications_list_registration,
)
from ...live.tests.unopened_live_ports import unopened_browser_session_factory, unopened_censal_fetch
from ...operations.registry import OperationPublicContractSetV1
from ...operator_actions.catalogue import OPERATOR_ACTION_CATALOGUE
from ...operator_actions.models import ActionReference
from ...overview.evidence import (
    AeatCalendarEvidenceSources,
    CalendarEvidenceProjection,
    CalendarEvidenceReadOutcome,
    LocalCalendarEvidenceSources,
    build_calendar_evidence_projection,
)
from ...overview.home import HomeAvailability, HomeZoneState
from ...user_profile.censal_operation import (
    build_censal_operation_definition,
    build_censal_operation_registration,
)
from ...user_profile.censo_sync import CENSAL_ADOPTABLE_PATHS
from ..workspace import (
    AeatSyncAeatObservationState,
    AeatSyncCensusCategory,
    AeatSyncCensusStatus,
    AeatSyncDiscrepancyKind,
    AeatSyncJustificanteState,
    AeatSyncLocalFilingState,
    AeatSyncOverviewArea,
    AeatSyncSourceState,
    AeatSyncWorkspaceAvailability,
    AeatSyncWorkspaceCensusRowV1,
    AeatSyncWorkspaceFactV1,
    AeatSyncWorkspaceOverviewRowV1,
    AeatSyncWorkspaceProjectionError,
    AeatSyncWorkspaceSource,
    AeatSyncWorkspaceZone,
    AeatSyncWorkspaceZoneObservationV1,
    project_aeat_sync_workspace,
)
from ..workspace_reader import read_local_aeat_sync_workspace_projection
from ._operator_scope_fakes import build_inward_operator_scope_ports_for_active_route

_OPERATOR_SCOPE_PORTS = build_inward_operator_scope_ports_for_active_route()

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "00000000-0000-4000-8000-000000000001"
_SUBJECT = "00000001R"
_NOW = datetime(2026, 9, 4, 10, 0, tzinfo=UTC)
_CERTIFICATE_SECRET_BACKEND_FACTORY = InMemoryCertificateSecretBackendFactory()


def _unrelated_contracts() -> OperationPublicContractSetV1:
    """A real registered operation that is NOT any AEAT pull.

    The contract set cannot be empty, so the absence being proven -- that no
    pull action is offered without its own operation -- needs a set that is
    populated yet contains nothing this workspace could act on.
    """
    return OperationPublicContractSetV1.build(
        (
            build_censal_operation_registration(
                build_censal_operation_definition(
                    certificate_secret_backend_factory=_CERTIFICATE_SECRET_BACKEND_FACTORY,
                    browser_session_factory=unopened_browser_session_factory,
                    operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                    censal_fetch_port=unopened_censal_fetch,
                    provider_preflight=lambda _profile_id, _operation: None,
                )
            ).contract,
        )
    )


def _contracts_with_notifications_list() -> OperationPublicContractSetV1:
    """Add the canonical registered list contract to an unrelated contract."""

    def unopened_ports() -> NotificationsPorts:
        raise AssertionError("contract discovery does not open notification ports")

    definition = build_notifications_list_definition(unopened_ports)
    notification_contract = build_notifications_list_registration(definition).contract
    return OperationPublicContractSetV1.build((*_unrelated_contracts().definitions, notification_contract))


def _projection(
    *,
    contracts: OperationPublicContractSetV1 | None = None,
    censo_values: dict[str, str] | None = None,
    custody_count: int | None = None,
):
    return read_local_aeat_sync_workspace_projection(
        bucket_id=_BUCKET,
        subject_key=_SUBJECT,
        observed_at=_NOW,
        filings=(),
        operation_contracts=contracts if contracts is not None else _unrelated_contracts(),
        censo_values=censo_values,
        custody_count=custody_count,
    )


def _pre_pull_zone_observations() -> tuple[AeatSyncWorkspaceZoneObservationV1, ...]:
    """The observation set a fresh session actually has: local read, AEAT not.

    Taken from the reader's own projection rather than hand-built, so a gate
    about what may be published pre-pull cannot drift from what pre-pull means.
    """
    projection = _projection(censo_values={})
    return tuple(AeatSyncWorkspaceZoneObservationV1(zone=zone.zone, sources=zone.sources) for zone in projection.zones)


def _overview_row(projection, area: AeatSyncOverviewArea):
    return next(row for row in projection.overview if row.area is area)


def test_a_read_and_empty_local_filing_catalogue_is_absent_not_unobserved() -> None:
    """An observed zero must not be reported as a source nobody read.

    The door loads the filing catalogue on every capture. When it holds
    nothing, that is a fact about the profile, and saying NOT_OBSERVED instead
    would describe the reader rather than the records.
    """
    row = _overview_row(_projection(), AeatSyncOverviewArea.FILED_DECLARATIONS)

    assert row.local_state is AeatSyncSourceState.ABSENT
    assert row.local_observed_at == _NOW


def test_evidence_comparison_reports_its_local_side_as_read_too() -> None:
    """Evidence comparison declares local.filings and must not claim it is unread."""
    row = _overview_row(_projection(), AeatSyncOverviewArea.EVIDENCE_COMPARISON)

    assert row.local_state is AeatSyncSourceState.ABSENT
    assert row.local_observed_at == _NOW


def test_an_area_with_no_local_reader_stays_genuinely_unobserved() -> None:
    """Notifications have no local reader here, so ABSENT would be the lie."""
    row = _overview_row(_projection(), AeatSyncOverviewArea.NOTIFICATIONS)

    assert row.local_state is AeatSyncSourceState.NOT_OBSERVED
    assert row.local_observed_at is None


def test_the_three_local_answers_remain_distinguishable_in_one_projection() -> None:
    """The whole point: read-and-empty, never-read, and the unpulled AEAT side.

    A reader that collapsed any pair would still satisfy each single-area
    assertion above by accident, so this asserts they differ from each other.
    """
    projection = _projection()
    census = _overview_row(projection, AeatSyncOverviewArea.CENSUS)
    filed = _overview_row(projection, AeatSyncOverviewArea.FILED_DECLARATIONS)
    notifications = _overview_row(projection, AeatSyncOverviewArea.NOTIFICATIONS)

    assert census.local_state is AeatSyncSourceState.PRESENT
    assert filed.local_state is AeatSyncSourceState.ABSENT
    assert notifications.local_state is AeatSyncSourceState.NOT_OBSERVED
    assert len({census.local_state, filed.local_state, notifications.local_state}) == 3
    assert {row.aeat_state for row in projection.overview} == {AeatSyncSourceState.NOT_OBSERVED}


def test_the_source_observation_agrees_with_the_row_it_backs() -> None:
    """A row claiming an observed zero needs a source that says it observed one.

    These are published side by side; the defect this catches is the projection
    contradicting itself -- an available source with a zero count beside a row
    reporting that same source as never observed.
    """
    projection = _projection()
    filed_zone = next(zone for zone in projection.zones if zone.zone.value == "filed_declarations")
    local = next(source for source in filed_zone.sources if source.source is AeatSyncWorkspaceSource.LOCAL_FILINGS)

    assert local.availability is AeatSyncWorkspaceAvailability.AVAILABLE
    assert local.item_count == 0
    assert _overview_row(projection, AeatSyncOverviewArea.FILED_DECLARATIONS).local_state is (
        AeatSyncSourceState.ABSENT
    )


def test_no_pull_action_is_offered_without_its_registered_operation() -> None:
    """A pull the session cannot perform must not appear as an offer.

    The contract set here holds one real registered operation -- the censal
    review -- and no AEAT pull. The census row may therefore legitimately offer
    its own operation; what must never appear is a filed-history pull, because
    nothing in this session could carry it out.
    """
    projection = _projection()
    offered = {str(action.action_id) for row in projection.overview for action in row.supported_actions}
    operations = {str(item) for row in projection.overview for item in row.supported_operations}

    assert "operator.live.filed.pull_all" not in offered
    assert "live.filed-history.pull" not in operations
    assert "operator.live.notifications.list" not in offered
    assert "live.notifications.list" not in operations


def test_notifications_list_action_joins_its_exact_tui_contract() -> None:
    """The notifications action appears only when its registered read is composed."""
    projection = _projection(contracts=_contracts_with_notifications_list(), custody_count=0)
    row = _overview_row(projection, AeatSyncOverviewArea.NOTIFICATIONS)

    assert tuple(str(action.action_id) for action in row.supported_actions) == ("operator.live.notifications.list",)
    assert tuple(str(operation) for operation in row.supported_operations) == ("live.notifications.list",)


def test_notification_list_action_without_its_operation_pair_is_rejected() -> None:
    """The projector detects a declared list action with no exact operation join."""
    fact = AeatSyncWorkspaceFactV1(
        bucket_id=_BUCKET,
        subject_key=_SUBJECT,
        row=AeatSyncWorkspaceOverviewRowV1(
            area=AeatSyncOverviewArea.NOTIFICATIONS,
            local_state=AeatSyncSourceState.NOT_OBSERVED,
            aeat_state=AeatSyncSourceState.NOT_OBSERVED,
            discrepancy_kind=AeatSyncDiscrepancyKind.UNOBSERVED,
            supported_actions=(ActionReference(action_id="operator.live.notifications.list"),),
        ),
    )

    with pytest.raises(AeatSyncWorkspaceProjectionError, match="exact public operation join"):
        project_aeat_sync_workspace(
            bucket_id=_BUCKET,
            subject_key=_SUBJECT,
            zone_observations=_pre_pull_zone_observations(),
            action_catalogue=OPERATOR_ACTION_CATALOGUE,
            operation_contracts=_contracts_with_notifications_list(),
            overview=(fact,),
        )


def test_the_census_zone_carries_a_row_for_every_comparable_field() -> None:
    """A read profile produces the whole census, not only its filled-in fields.

    The paths come from `CENSAL_ADOPTABLE_PATHS`, the authority on what an AEAT
    censal read can actually speak to. A field the operator left blank is the
    one a pull is most likely to change, so it earns a row too.
    """
    projection = _projection(censo_values={"contact.postcode": "28013"})

    assert {row.path for row in projection.census} == set(CENSAL_ADOPTABLE_PATHS)


def test_a_blank_censo_field_is_observed_blank_and_never_unobserved() -> None:
    """Read-and-empty and never-read are different answers on the same row.

    `None` on this row means nobody looked, which is false of a record the
    session read to build the row at all. The empty string is what "looked, and
    the profile holds nothing here" is spelled as.
    """
    projection = _projection(censo_values={"contact.postcode": "28013"})
    by_path = {row.path: row for row in projection.census}

    assert by_path["contact.postcode"].local_value == "28013"
    assert by_path["contact.fiscal_address"].local_value == ""
    assert all(row.local_value is not None for row in projection.census)


def test_an_unread_profile_leaves_the_census_zone_empty() -> None:
    """No rows at all is the honest answer when the record was never read.

    This is the state the empty mapping must NOT be confused with: an empty
    mapping still produced a full set of observed blanks above.
    """
    assert _projection(censo_values=None).census == ()


def test_every_pre_pull_census_row_says_it_was_never_compared() -> None:
    """No verdict may be claimed before anyone looks at the AEAT side.

    The four verdicts each assert a comparison ran. Reusing one here would tell
    the operator their address matches, or conflicts, on the strength of an
    observation nobody made.
    """
    projection = _projection(censo_values={})

    assert {row.status for row in projection.census} == {AeatSyncCensusStatus.NOT_COMPARED}
    assert all(row.aeat_value is None for row in projection.census)


def test_a_verdict_cannot_be_published_without_the_aeat_observation() -> None:
    """The zone contract still holds for rows that DO claim a comparison.

    Relaxing the AEAT requirement is what let the uncompared rows exist; this
    proves the relaxation is confined to them, so a producer that starts
    emitting verdicts cannot publish one against a source nobody pulled.
    """
    fact = AeatSyncWorkspaceFactV1(
        bucket_id=_BUCKET,
        subject_key=_SUBJECT,
        row=AeatSyncWorkspaceCensusRowV1(
            path="contact.postcode",
            category=AeatSyncCensusCategory.ADDRESS,
            status=AeatSyncCensusStatus.CONFLICT,
            local_value="28013",
            aeat_value="28014",
        ),
    )
    with pytest.raises(AeatSyncWorkspaceProjectionError, match="AEAT census"):
        project_aeat_sync_workspace(
            bucket_id=_BUCKET,
            subject_key=_SUBJECT,
            zone_observations=_pre_pull_zone_observations(),
            action_catalogue=OPERATOR_ACTION_CATALOGUE,
            operation_contracts=_unrelated_contracts(),
            census=(fact,),
        )


def test_a_never_compared_row_cannot_carry_an_aeat_value() -> None:
    """The contradiction is worth its own gate: the evidence would be right there.

    A row claiming nobody looked while carrying what they found tells the
    operator the field is unchecked with the check sitting beside it.
    """
    with pytest.raises(ValidationError, match="never compared"):
        AeatSyncWorkspaceCensusRowV1(
            path="contact.postcode",
            category=AeatSyncCensusCategory.ADDRESS,
            status=AeatSyncCensusStatus.NOT_COMPARED,
            local_value="28013",
            aeat_value="28014",
        )


def test_an_empty_custody_store_is_an_observed_absence_not_an_unread_one() -> None:
    """Reading custody and finding nothing is a fact the operator can act on.

    This is the pairing S408 names: a local source reporting an observable
    count of zero beside an overview row claiming nobody looked. Both cannot be
    true, and the count is the one backed by an actual read.
    """
    row = _overview_row(_projection(custody_count=0), AeatSyncOverviewArea.NOTIFICATIONS)

    assert row.local_state is AeatSyncSourceState.ABSENT
    assert row.local_observed_at is not None


def test_custody_holding_documents_reports_them_present() -> None:
    """The other side of the same read."""
    row = _overview_row(_projection(custody_count=3), AeatSyncOverviewArea.NOTIFICATIONS)

    assert row.local_state is AeatSyncSourceState.PRESENT


def test_an_uncomposed_custody_reader_leaves_notifications_unobserved() -> None:
    """A door that composed no reader must not be reported as having looked.

    `None` is the third state, and collapsing it into the observed zero above
    would claim a look this session never took.
    """
    row = _overview_row(_projection(custody_count=None), AeatSyncOverviewArea.NOTIFICATIONS)

    assert row.local_state is AeatSyncSourceState.NOT_OBSERVED
    assert row.local_observed_at is None


def test_saved_census_is_available_and_compares_only_observed_facts() -> None:
    """A reopened workspace reads stored evidence without fabricating absent values."""
    from ...user_profile.censal_observation import (
        CensalCell,
        CensalConsultation,
        CensalObservation,
        CensalObservationAddress,
        CensalObservationIdentity,
        CensalRow,
        CensalSection,
    )

    observation = CensalObservation(
        identity=CensalObservationIdentity(nif=_SUBJECT),
        domicilio_fiscal=CensalObservationAddress(codigo_postal="28001"),
        domicilio_notificacion=CensalObservationAddress(),
        captured_at=_NOW,
        source_url="https://sede.agenciatributaria.gob.es/censo",
        consultations=(
            CensalConsultation(
                kind="obligaciones",
                source_url="https://sede.agenciatributaria.gob.es/obligaciones",
                sections=(
                    CensalSection(
                        title="Mis Obligaciones",
                        rows=(
                            CensalRow(
                                cells=(CensalCell(role="value", column="Nueva columna", text="Dato conservado"),),
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )
    projection = read_local_aeat_sync_workspace_projection(
        bucket_id=_BUCKET,
        subject_key=_SUBJECT,
        observed_at=_NOW,
        filings=(),
        operation_contracts=_unrelated_contracts(),
        censo_values={"contact.postcode": "08001"},
        census_observation=observation,
    )
    assert projection.census_observation == observation
    assert type(projection).model_validate_json(projection.model_dump_json()).census_observation == observation
    overview = _overview_row(projection, AeatSyncOverviewArea.CENSUS)
    assert overview.aeat_state is AeatSyncSourceState.PRESENT
    assert overview.aeat_observed_at == _NOW
    rows = {row.path: row for row in projection.census}
    assert rows["contact.postcode"].status is AeatSyncCensusStatus.CONFLICT
    assert rows["contact.postcode"].aeat_value == "28001"
    assert rows["contact.fiscal_address_cadastral_reference"].status is AeatSyncCensusStatus.NOT_COMPARED
    assert rows["contact.fiscal_address_cadastral_reference"].aeat_value is None
    with pytest.raises(AeatSyncWorkspaceProjectionError, match="another profile or taxpayer"):
        read_local_aeat_sync_workspace_projection(
            bucket_id=_BUCKET,
            subject_key="00000002W",
            observed_at=_NOW,
            filings=(),
            operation_contracts=_unrelated_contracts(),
            censo_values={},
            census_observation=observation,
        )


_FILED_SUBJECT = "X1234567L"
_CAPTURED_AT = datetime(2025, 4, 16, 8, 0, tzinfo=UTC)


def _filed_evidence(
    observations: tuple[FiledDeclaracionObservationProtocol, ...] = (),
    *,
    availability: HomeAvailability = HomeAvailability.AVAILABLE,
    verified: bool = False,
) -> CalendarEvidenceProjection:
    """Join stored captures through the calendar's own evidence provider."""
    from ...overview.tests.calendar_test_support import FILED_JUSTIFICANTE_STORAGE_REF

    observable = availability in {HomeAvailability.AVAILABLE, HomeAvailability.STALE}
    state = HomeZoneState(
        availability=availability,
        observed_at=_CAPTURED_AT if observable else None,
        reason_code=None
        if availability is HomeAvailability.AVAILABLE
        else "workbench.calendar.aeat_reader_unavailable",
    )
    return build_calendar_evidence_projection(
        local=CalendarEvidenceReadOutcome(
            state=HomeZoneState(availability=HomeAvailability.AVAILABLE),
            value=LocalCalendarEvidenceSources(),
        ),
        aeat=CalendarEvidenceReadOutcome(
            state=state,
            value=(
                AeatCalendarEvidenceSources(
                    filed_declaration_observations=observations,
                    verified_filed_declaration_artefact_refs=(FILED_JUSTIFICANTE_STORAGE_REF,) if verified else (),
                    verified_filed_declaration_artefact_csvs=(
                        ((FILED_JUSTIFICANTE_STORAGE_REF, "CSVFILED3031T2025"),) if verified else ()
                    ),
                )
                if observable
                else None
            ),
        ),
        expected_tax_id=_FILED_SUBJECT,
    )


def _contracts_with_filed_history_pull() -> OperationPublicContractSetV1:
    """Add the canonical whole-history pull contract, as an installed TUI session composes it."""

    def unopened(*_args: object, **_kwargs: object) -> NoReturn:
        raise AssertionError("contract discovery does not open filed-history resources")

    definition = build_filed_history_operation_definition(
        sync_run_repository_factory=unopened,
        composition_factory=unopened,
        browser_resources_factory=unopened,
    )
    pull_contract = build_filed_history_operation_registration(definition).contract
    return OperationPublicContractSetV1.build((*_unrelated_contracts().definitions, pull_contract))


def _filed_projection(
    filed_evidence: CalendarEvidenceProjection | None,
    *,
    filings: tuple[ModeloRecord, ...] = (),
    contracts: OperationPublicContractSetV1 | None = None,
):
    return read_local_aeat_sync_workspace_projection(
        bucket_id=_BUCKET,
        subject_key=_FILED_SUBJECT,
        observed_at=_NOW,
        filings=filings,
        operation_contracts=contracts if contracts is not None else _unrelated_contracts(),
        filed_evidence=filed_evidence,
    )


def _source(projection, zone: AeatSyncWorkspaceZone, source: AeatSyncWorkspaceSource):
    state = next(item for item in projection.zones if item.zone is zone)
    return next(item for item in state.sources if item.source is source)


def test_captured_filings_reach_filed_declarations_with_receipt_and_submission_apart() -> None:
    """Stored captures fill the AEAT side, including declarations with no local filing.

    The 1T capture carries a verified justificante and joins the local filing;
    the 2T capture has no local filing and no verified receipt. Both must show
    the submission AEAT registered, and only the first may claim a receipt.
    """
    from ...overview.tests.calendar_test_support import (
        filed_declaration_artefact,
        filed_declaration_observation,
        modelo_record,
    )

    first = filed_declaration_observation(artefacts=(filed_declaration_artefact(),))
    second = replace(
        filed_declaration_observation(artefacts=(), expediente_id="22222222222222222222"),
        _period=Period.from_year_and_code(2025, "2T"),
    )
    projection = _filed_projection(_filed_evidence((first, second), verified=True), filings=(modelo_record(),))

    rows = {row.period.registry_token: row for row in projection.filed_declarations}
    assert set(rows) == {"1T", "2T"}
    joined, aeat_only = rows["1T"], rows["2T"]
    assert joined.local_filing_state is AeatSyncLocalFilingState.FILED
    assert joined.aeat_observation_state is AeatSyncAeatObservationState.SUBMITTED
    assert joined.aeat_observed_at == _CAPTURED_AT
    assert joined.justificante_state is AeatSyncJustificanteState.VERIFIED
    assert aeat_only.local_filing_state is AeatSyncLocalFilingState.NOT_OBSERVED
    assert aeat_only.local_filed_at is None
    assert aeat_only.aeat_observation_state is AeatSyncAeatObservationState.SUBMITTED
    assert aeat_only.justificante_state is AeatSyncJustificanteState.NOT_OBSERVED
    assert aeat_only.justificante_observed_at is None

    source = _source(
        projection, AeatSyncWorkspaceZone.FILED_DECLARATIONS, AeatSyncWorkspaceSource.AEAT_FILED_DECLARATIONS
    )
    assert source.availability is AeatSyncWorkspaceAvailability.AVAILABLE
    assert (source.observed_at, source.item_count) == (_CAPTURED_AT, 2)
    overview = _overview_row(projection, AeatSyncOverviewArea.FILED_DECLARATIONS)
    assert (overview.local_state, overview.aeat_state) == (AeatSyncSourceState.PRESENT, AeatSyncSourceState.PRESENT)
    assert overview.aeat_observed_at == _CAPTURED_AT
    assert overview.discrepancy_kind is AeatSyncDiscrepancyKind.NONE


def test_captured_filings_project_when_the_session_composes_the_whole_history_pull() -> None:
    """The whole-history pull is offered on the area's overview row, never on one declaration.

    An installed session composes that pull. A filed row that inherited it
    would break the per-row action rule, and the first capture to produce a
    row would take the whole AEAT Sync area down.
    """
    from ...overview.tests.calendar_test_support import filed_declaration_artefact, filed_declaration_observation

    capture = filed_declaration_observation(artefacts=(filed_declaration_artefact(),))
    projection = _filed_projection(
        _filed_evidence((capture,), verified=True), contracts=_contracts_with_filed_history_pull()
    )

    overview = _overview_row(projection, AeatSyncOverviewArea.FILED_DECLARATIONS)
    assert "operator.live.filed.pull_all" in {str(action.action_id) for action in overview.supported_actions}
    (row,) = projection.filed_declarations
    assert row.aeat_observation_state is AeatSyncAeatObservationState.SUBMITTED
    assert "operator.live.filed.pull_all" not in {str(action.action_id) for action in row.supported_actions}


def test_a_first_run_capture_is_aeat_only_and_comparison_stays_unread() -> None:
    """No local filing yet: the area is AEAT-only, and figures were never compared.

    Captures name submissions, not casilla values, so the comparison zone must
    not turn its unread AEAT side into an observed zero discrepancies.
    """
    from ...overview.tests.calendar_test_support import filed_declaration_observation

    projection = _filed_projection(_filed_evidence((filed_declaration_observation(artefacts=()),)))

    overview = _overview_row(projection, AeatSyncOverviewArea.FILED_DECLARATIONS)
    assert (overview.local_state, overview.aeat_state) == (AeatSyncSourceState.ABSENT, AeatSyncSourceState.PRESENT)
    assert overview.discrepancy_kind is AeatSyncDiscrepancyKind.AEAT_ONLY
    comparison_row = _overview_row(projection, AeatSyncOverviewArea.EVIDENCE_COMPARISON)
    assert comparison_row.aeat_state is AeatSyncSourceState.NOT_OBSERVED
    comparison = _source(
        projection, AeatSyncWorkspaceZone.EVIDENCE_COMPARISON, AeatSyncWorkspaceSource.AEAT_FILED_DECLARATIONS
    )
    assert comparison.availability is AeatSyncWorkspaceAvailability.UNAVAILABLE
    assert comparison.refusal == "workbench.aeat_sync.aeat_figures_not_read"
    zone = next(item for item in projection.zones if item.zone is AeatSyncWorkspaceZone.EVIDENCE_COMPARISON)
    assert zone.item_count is None


def test_another_taxpayers_capture_is_an_observed_zero_not_a_filing() -> None:
    """Exact-subject scoping comes from the shared join, and the read still happened."""
    from ...overview.tests.calendar_test_support import filed_declaration_observation

    foreign = replace(filed_declaration_observation(artefacts=()), _authenticated_identity="00000001R")
    projection = _filed_projection(_filed_evidence((foreign,)))

    assert projection.filed_declarations == ()
    source = _source(
        projection, AeatSyncWorkspaceZone.FILED_DECLARATIONS, AeatSyncWorkspaceSource.AEAT_FILED_DECLARATIONS
    )
    assert (source.availability, source.item_count) == (AeatSyncWorkspaceAvailability.AVAILABLE, 0)
    assert _overview_row(projection, AeatSyncOverviewArea.FILED_DECLARATIONS).aeat_state is AeatSyncSourceState.ABSENT


@pytest.mark.parametrize(
    ("filed_evidence", "availability", "refusal"),
    (
        (None, AeatSyncWorkspaceAvailability.NEVER_CAPTURED, "workbench.aeat_sync.never_pulled"),
        (
            "never_captured",
            AeatSyncWorkspaceAvailability.NEVER_CAPTURED,
            "workbench.aeat_sync.never_pulled",
        ),
        (
            "unavailable",
            AeatSyncWorkspaceAvailability.UNAVAILABLE,
            "workbench.calendar.aeat_reader_unavailable",
        ),
    ),
)
def test_an_unreadable_capture_store_stays_distinct_from_one_never_pulled(
    filed_evidence: str | None,
    availability: AeatSyncWorkspaceAvailability,
    refusal: str,
) -> None:
    """Never captured, unreadable and observed-empty are three different answers."""
    evidence = None if filed_evidence is None else _filed_evidence(availability=HomeAvailability(filed_evidence))
    projection = _filed_projection(evidence)

    source = _source(
        projection, AeatSyncWorkspaceZone.FILED_DECLARATIONS, AeatSyncWorkspaceSource.AEAT_FILED_DECLARATIONS
    )
    assert (source.availability, source.refusal, source.item_count) == (availability, refusal, None)
    assert projection.filed_declarations == ()
    overview = _overview_row(projection, AeatSyncOverviewArea.FILED_DECLARATIONS)
    assert overview.aeat_state is AeatSyncSourceState.NOT_OBSERVED
