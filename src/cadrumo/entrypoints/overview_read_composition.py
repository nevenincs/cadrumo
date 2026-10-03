"""Compose canonical overview reads inside one authenticated profile worker."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from uuid import UUID

from ..application.overview.applicability_evidence import (
    FilingYearApplicabilityEvidence,
    bind_filing_year_applicability_evidence,
)
from ..application.overview.calendar_models import OverviewCalendar, OverviewCalendarRange
from ..application.overview.read_calendar_projection import (
    OverviewAgendaSnapshot,
    OverviewBacklogSnapshot,
    OverviewCalendarSnapshot,
)
from ..application.overview.read_payload import (
    OverviewAgendaRead,
    OverviewBacklogRead,
    OverviewCalendarRead,
    OverviewExplainRead,
    OverviewPrepareRead,
    OverviewReadPayload,
    OverviewStatusRead,
)
from ..application.overview.read_projection import (
    OverviewCalendarSurveySnapshot,
    OverviewDraftSnapshot,
    OverviewExplainSnapshot,
    OverviewLockedProfileSnapshot,
    OverviewNoticeSnapshot,
    OverviewPeriodStatusSnapshot,
    OverviewPrepareSnapshot,
    OverviewStatusSnapshot,
)
from ..application.overview.read_request import OverviewReadKind, OverviewReadRequest
from ..application.user_profile.access_contracts import AccessDenialCode
from ..application.user_profile.access_errors import ProfileAccessRefusedError
from ..application.user_profile.profile_record_repository import ProfileRecordRepository
from ..application.user_profile.projections import fact_value, projection_for_taxpayer, record_to_values
from ..application.workflow.profile_bucket_models import ProfileBucketPointer
from ..core.bucket_pointer import require_active_bucket_id
from ..core.json_contract import Notice
from ..core.notificacion_estado_servicio import NotificacionEstadoServicio
from ..core.time.clock import today_madrid
from ..domain.calculations.registry.authority import PinnedAuthorityOperation
from ..domain.calculations.registry.facts.resolution import ResolvedScalarFact, ScalarFactQuery
from ..domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ..domain.calculations.registry.profile_grounding import build_profile_grounding_index
from ..domain.calculations.registry.schema_base import DateAxis
from ..domain.contribuyente.entity_type import entity_type_natural_person_token
from ..domain.deadlines.models import TaxpayerProfile
from ..domain.user_profile.values import UserProfileRecord
from .adapter_composition import (
    build_expedientes_ports,
    build_ledger_evidence_ports,
    build_operator_probe_ports,
    build_state_projection_read_ports,
)
from .overview_evidence_composition import (
    live_censo_verified_profile_keys,
    local_calendar_filing_evidence,
    local_live_calendar_events,
    local_modelo_record_calendar_events,
    local_modelo_work_units,
    overview_no_aeat_history_notice,
)


def _deemed_served_legal_ref(calendar: OverviewCalendar, *, operation: PinnedAuthorityOperation) -> str | None:
    """Capture legal provenance under the same pinned authority as calendar facts."""
    events = tuple(
        event
        for event in calendar.events
        if event.notificacion_estado_servicio is NotificacionEstadoServicio.RECHAZO_TACITO
    )
    if not events:
        return None
    resolved = operation.resolve_governed_fact(
        ScalarFactQuery(
            fact_id="dehu-tacit-rejection-natural-days",
            date_axis=DateAxis.SUBMISSION_DATE,
            effective_date=max(event.event_date for event in events),
        )
    )
    if not isinstance(resolved, ResolvedScalarFact) or not resolved.legal_refs:
        raise ValueError("deemed-served notification has no legal provenance")
    return str(resolved.legal_refs[0])


def _refusal_requirements(
    *,
    operation: PinnedAuthorityOperation,
    taxpayer: TaxpayerProfile,
    taxpayer_model_declared: bool,
    warning_codes: tuple[str, ...],
) -> tuple[str, ...]:
    """Render the existing selector guidance with the worker's retained authority."""
    from ..application.user_profile.preflight import format_profile_selector_requirements

    if not taxpayer_model_declared:
        if taxpayer.entity_type is None:
            selectors = ("taxpayer.entity_type",)
        elif taxpayer.entity_type == entity_type_natural_person_token() and not taxpayer.irpf_income_categories:
            selectors = ("taxpayer.irpf_income_categories",)
        else:
            selectors = ()
    else:
        selectors = warning_codes
    if not selectors:
        return ()
    return format_profile_selector_requirements(
        selectors,
        schema=operation.profile_decode_context().schema,
        grounding_index=build_profile_grounding_index(operation),
    )


def _filing_year_applicability_evidence(
    bucket_id: str,
    record: UserProfileRecord,
    *,
    operation: PinnedAuthorityOperation,
) -> FilingYearApplicabilityEvidence:
    """Bind the per-year profile and ledger evidence to this worker's profile and invoice stores.

    The invoice reader is the one the filing calculation composes for the same
    bucket, so the ledger signal reads exactly the catalogue the declaration
    is built from.
    """
    from ..adapters.persistence.profile.invoice_source_resolver import InvoiceCatalogueSourceResolverAdapter
    from ..adapters.persistence.profile.invoices import InvoiceCatalogueRepository
    from ..application.invoices.source_resolver_ports import InvoiceSourceResolverPorts

    return bind_filing_year_applicability_evidence(
        record=record,
        schema=operation.profile_decode_context().schema,
        bucket_id=bucket_id,
        invoice_source_ports=InvoiceSourceResolverPorts(
            catalogue_reader=InvoiceCatalogueSourceResolverAdapter(
                repository=InvoiceCatalogueRepository(bucket_id=bucket_id),
            ),
        ),
        operation=operation,
        today=today_madrid(),
    )


@dataclass(frozen=True, slots=True)
class _OverviewReadPorts:
    bucket_id: str

    def capture(self, request: OverviewReadRequest, *, operation: PinnedAuthorityOperation) -> OverviewReadPayload:
        """Capture exactly one canonical report while retaining the caller's pin."""
        if self.bucket_id != str(request.profile_id) or require_active_bucket_id() != self.bucket_id:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        with validating_governed_facts(operation):
            repository = ProfileRecordRepository.for_current_session(
                self.bucket_id, profile_decode_context=operation.profile_decode_context()
            )
            record = repository.load(self.bucket_id)
            if str(record.profile_id) != self.bucket_id:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            schema = operation.profile_decode_context().schema
            taxpayer = projection_for_taxpayer(record, schema=schema)
            raw_values = record_to_values(record, schema=schema)
            evidence = _filing_year_applicability_evidence(self.bucket_id, record, operation=operation)
            if request.kind is OverviewReadKind.STATUS:
                return self._status(
                    request, operation=operation, raw_values=raw_values, taxpayer=taxpayer, evidence=evidence
                )
            if request.kind is OverviewReadKind.CALENDAR:
                return self._calendar(
                    request,
                    operation=operation,
                    record=record,
                    taxpayer=taxpayer,
                    raw_values=raw_values,
                    evidence=evidence,
                )
            if request.kind is OverviewReadKind.AGENDA:
                return self._agenda(
                    request, operation=operation, taxpayer=taxpayer, raw_values=raw_values, evidence=evidence
                )
            if request.kind is OverviewReadKind.BACKLOG:
                return self._backlog(
                    request, operation=operation, taxpayer=taxpayer, raw_values=raw_values, evidence=evidence
                )
            if request.kind is OverviewReadKind.EXPLAIN:
                return self._explain(request, operation=operation, record=record, taxpayer=taxpayer, evidence=evidence)
            return self._prepare(request, operation=operation)

    def _status(
        self,
        request: OverviewReadRequest,
        *,
        operation: PinnedAuthorityOperation,
        raw_values: Mapping[str, object],
        taxpayer: TaxpayerProfile,
        evidence: FilingYearApplicabilityEvidence,
    ) -> OverviewStatusRead:
        from ..adapters.persistence.profile.filing_drafts import ModeloDraftRepository
        from ..adapters.persistence.storage.certificate_secret_backend import build_certificate_secret_backend
        from ..adapters.persistence.storage.operator_scope import build_operator_scope_ports
        from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
        from ..application.filing.draft_revision_gate import require_modelo_draft_coordinates_current
        from ..application.overview.calendar import build_overview_calendar
        from ..application.overview.calendar_models import OverviewCalendarRange
        from ..application.overview.status_report import build_overview_status_report
        from ..application.workflow.persistence import workflow_state_repository
        from ..domain.calculations.registry.applicability import derive_tax_route

        if request.period is not None:
            drafts = tuple(
                require_modelo_draft_coordinates_current(draft, operation=operation)
                for draft in ModeloDraftRepository(bucket_id=self.bucket_id).iter_drafts()
            )
            selected = tuple(
                OverviewDraftSnapshot(draft_id=draft.draft_id, modelo=draft.modelo, status=draft.status.value)
                for draft in drafts
                if draft.period.filing_year == request.period.filing_year
                and draft.period.registry_token == request.period.code
            )
            return OverviewStatusRead(
                period_report=OverviewPeriodStatusSnapshot(
                    period=request.period, drafts=selected, verbose=bool(request.verbose)
                )
            )
        state = workflow_state_repository().load()
        if state.active_profile_bucket_id() != self.bucket_id:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        report = build_overview_status_report(
            certificate_secret_backend_factory=build_certificate_secret_backend,
            operator_probe_ports=build_operator_probe_ports(),
            operator_scope_ports=build_operator_scope_ports(),
            state=state,
            raw_values=raw_values,
            read_ports=build_state_projection_read_ports(
                operation=operation,
                objects=secure_object_repository_for_bucket(self.bucket_id),
                bucket_id=self.bucket_id,
            ),
            operation=operation,
        )
        today = today_madrid()
        calendar = build_overview_calendar(
            taxpayer,
            OverviewCalendarRange(from_date=date(today.year, 1, 1), to_date=date(today.year, 12, 31)),
            operation=operation,
            today=today,
            raw_values=raw_values,
            applicability_evidence=evidence,
        )
        history = overview_no_aeat_history_notice(tax_route=derive_tax_route(taxpayer))
        return OverviewStatusRead(
            report=OverviewStatusSnapshot.from_report(report),
            coverage=calendar.coverage,
            coverage_advised_count=len(calendar.coverage.advised),
            notices=(OverviewNoticeSnapshot.from_notice(history),) if history is not None else (),
        )

    def _calendar(
        self,
        request: OverviewReadRequest,
        *,
        operation: PinnedAuthorityOperation,
        record: UserProfileRecord,
        taxpayer: TaxpayerProfile,
        raw_values: Mapping[str, object],
        evidence: FilingYearApplicabilityEvidence,
    ) -> OverviewCalendarRead:
        from ..application.overview.calendar import build_overview_calendar
        from ..application.overview.calendar_models import OverviewCalendarRange
        from ..domain.calculations.registry.applicability import derive_tax_route
        from ..domain.user_profile.values import ProfileSetupState
        from .payer_fact_migration_notices import pending_payer_fact_notices

        if request.from_date is None or request.to_date is None:
            raise ValueError("calendar query requires a date window")
        rng = OverviewCalendarRange(from_date=request.from_date, to_date=request.to_date)
        calendar: OverviewCalendar | None = None
        if request.all_profiles and record.setup_state is not ProfileSetupState.COMPLETE:
            active = None
            legal_ref = None
            notices = ()
        else:
            today = today_madrid()
            expected_tax_id = (fact_value(record, "identity.tax_id") or "").strip()
            live, live_notice = local_live_calendar_events(
                self.bucket_id,
                rng,
                as_of=today,
                expected_tax_id=expected_tax_id,
                expedientes_ports=build_expedientes_ports(bucket_id=self.bucket_id),
            )
            modelo_events, modelo_notice = local_modelo_record_calendar_events(
                self.bucket_id, rng, expected_tax_id=expected_tax_id
            )
            events = (*live, *modelo_events)
            filing_evidence, evidence_notice = local_calendar_filing_evidence(
                self.bucket_id, events, operation=operation, expected_tax_id=expected_tax_id
            )
            units, units_notice = local_modelo_work_units(self.bucket_id)
            history = overview_no_aeat_history_notice(tax_route=derive_tax_route(taxpayer))
            calendar = build_overview_calendar(
                taxpayer,
                rng,
                operation=operation,
                today=today,
                raw_values=raw_values,
                show_suppressed=bool(request.show_suppressed),
                events=events,
                filing_evidence=filing_evidence,
                work_units=units,
                live_censo_verified_profile_keys=live_censo_verified_profile_keys(record),
                applicability_evidence=evidence,
            )
            active = OverviewCalendarSnapshot.from_calendar(calendar)
            legal_ref = _deemed_served_legal_ref(calendar, operation=operation)
            notices = _calendar_notice_snapshots(
                (
                    live_notice,
                    modelo_notice,
                    evidence_notice,
                    units_notice,
                    history,
                    *pending_payer_fact_notices(record, operation=operation),
                )
            )
        if not request.all_profiles:
            if active is None or calendar is None:
                raise ValueError("bound calendar was not captured")
            return OverviewCalendarRead(
                calendar=active,
                notices=notices,
                deemed_served_legal_ref=legal_ref,
                refusal_requirements=_refusal_requirements(
                    operation=operation,
                    taxpayer=taxpayer,
                    taxpayer_model_declared=calendar.taxpayer_model_declared,
                    warning_codes=tuple(warning.code for warning in calendar.warnings),
                ),
            )
        return _calendar_profile_survey(
            self.bucket_id, rng, record, operation, taxpayer, active, calendar, legal_ref, notices
        )

    def _agenda(
        self,
        request: OverviewReadRequest,
        *,
        operation: PinnedAuthorityOperation,
        taxpayer: TaxpayerProfile,
        raw_values: Mapping[str, object],
        evidence: FilingYearApplicabilityEvidence,
    ) -> OverviewAgendaRead:
        from ..application.overview.agenda import build_overview_agenda

        agenda = build_overview_agenda(
            taxpayer,
            as_of=request.as_of or today_madrid(),
            operation=operation,
            horizon_days=request.horizon_days or 14,
            raw_values=raw_values,
            applicability_evidence=evidence,
        )
        return OverviewAgendaRead(
            agenda=OverviewAgendaSnapshot.from_agenda(agenda),
            refusal_requirements=_refusal_requirements(
                operation=operation,
                taxpayer=taxpayer,
                taxpayer_model_declared=agenda.taxpayer_model_declared,
                warning_codes=tuple(warning.code for warning in agenda.warnings),
            ),
        )

    def _backlog(
        self,
        request: OverviewReadRequest,
        *,
        operation: PinnedAuthorityOperation,
        taxpayer: TaxpayerProfile,
        raw_values: Mapping[str, object],
        evidence: FilingYearApplicabilityEvidence,
    ) -> OverviewBacklogRead:
        from ..application.overview.backlog import build_overview_backlog

        units, notice = local_modelo_work_units(self.bucket_id)
        report = build_overview_backlog(
            taxpayer,
            operation=operation,
            from_date=request.from_date,
            to_date=request.to_date,
            raw_values=raw_values,
            work_units=units,
            applicability_evidence=evidence,
        )
        return OverviewBacklogRead(
            backlog=OverviewBacklogSnapshot.from_backlog(report),
            notices=(OverviewNoticeSnapshot.from_notice(notice),) if notice is not None else (),
            refusal_requirements=_refusal_requirements(
                operation=operation,
                taxpayer=taxpayer,
                taxpayer_model_declared=report.taxpayer_model_declared,
                warning_codes=tuple(warning.code for warning in report.warnings),
            ),
        )

    def _explain(
        self,
        request: OverviewReadRequest,
        *,
        operation: PinnedAuthorityOperation,
        record: UserProfileRecord,
        taxpayer: TaxpayerProfile,
        evidence: FilingYearApplicabilityEvidence,
    ) -> OverviewExplainRead:
        from ..application.overview.explain import build_overview_explain
        from ..domain.calculations.registry.applicability import ApplicabilityVerdict
        from .payer_fact_migration_notices import pending_payer_fact_notices

        if request.modelo is None:
            raise ValueError("explanation query requires modelo")
        report = build_overview_explain(
            taxpayer,
            modelo=request.modelo,
            year=request.year,
            operation=operation,
            applicability_evidence=evidence,
        )
        notices = (
            tuple(
                OverviewNoticeSnapshot.from_notice(notice)
                for notice in pending_payer_fact_notices(record, operation=operation, modelo=report.modelo)
            )
            if report.verdict is ApplicabilityVerdict.INCOMPLETE
            else ()
        )
        return OverviewExplainRead(explanation=OverviewExplainSnapshot.from_explain(report), notices=notices)

    def _prepare(self, request: OverviewReadRequest, *, operation: PinnedAuthorityOperation) -> OverviewPrepareRead:
        from ..adapters.persistence.profile.invoices import InvoiceCatalogueRepository
        from ..adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
        from ..adapters.persistence.profile.transactions import TransactionCatalogueRepository
        from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
        from ..application.ledger.evidence import PurchaseInvoiceEvidenceService
        from ..application.ledger.preflight import preflight_ledger_tax_readiness
        from ..application.modelo.registry_discovery import registry_describe_modelo_for_scope
        from ..application.overview.data_prep import build_data_prep_walkthrough

        if request.modelo is None or request.period is None:
            raise ValueError("preparation query requires modelo and period")
        period = request.period.to_period()
        registry_describe_modelo_for_scope(request.modelo, period=period, operation=operation)
        transactions = TransactionCatalogueRepository(bucket_id=self.bucket_id)
        read_ports = build_state_projection_read_ports(
            operation=operation,
            objects=secure_object_repository_for_bucket(self.bucket_id),
            bucket_id=self.bucket_id,
        )
        invoices = InvoiceCatalogueRepository(bucket_id=self.bucket_id).load()
        evidence = PurchaseInvoiceEvidenceService(ports=build_ledger_evidence_ports(bucket_id=self.bucket_id)).list_all(
            bucket_id=self.bucket_id
        )
        preflight = preflight_ledger_tax_readiness(
            bucket_id=self.bucket_id,
            period=period,
            transaction_repository=transactions,
            usage_ratio_profile_loader=read_ports.usage_ratio_profile_loader,
            operation=operation,
        )
        units = WorkUnitCatalogueRepository(bucket_id=self.bucket_id).load()
        walkthrough = build_data_prep_walkthrough(
            bucket_id=self.bucket_id,
            modelo=request.modelo,
            period=period,
            transaction_repository=transactions,
            invoice_catalogue=invoices,
            evidence_records=evidence,
            preflight_report=preflight,
            work_unit_catalogue=units,
        )
        return OverviewPrepareRead(preparation=OverviewPrepareSnapshot.from_walkthrough(walkthrough))


def build_overview_read_ports(*, bucket_id: str, operation: PinnedAuthorityOperation) -> _OverviewReadPorts:
    """Bind only the active authenticated profile's overview readers."""
    profile_id = str(UUID(bucket_id))
    if require_active_bucket_id() != profile_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    operation.profile_decode_context()
    return _OverviewReadPorts(bucket_id=profile_id)


__all__ = ["build_overview_read_ports"]


def _calendar_other_profiles(
    bucket_id: str, pointers: Mapping[str, ProfileBucketPointer]
) -> tuple[OverviewLockedProfileSnapshot, ...]:
    """List every other public profile pointer in the established label order."""
    other = tuple(
        OverviewLockedProfileSnapshot(profile_id=pointer.bucket_id, label=pointer.label)
        for bucket_id, pointer in sorted(pointers.items(), key=lambda pair: pair[1].label)
        if bucket_id != bucket_id
    )
    return other


def _calendar_profile_survey(
    bucket_id: str,
    rng: OverviewCalendarRange,
    record: UserProfileRecord,
    operation: PinnedAuthorityOperation,
    taxpayer: TaxpayerProfile,
    active: OverviewCalendarSnapshot | None,
    calendar: OverviewCalendar | None,
    legal_ref: str | None,
    notices: tuple[OverviewNoticeSnapshot, ...],
) -> OverviewCalendarRead:
    """Project locked, incomplete, and active profiles without reading their private records."""
    from ..application.workflow.profile_bucket_scan import list_profile_buckets
    from ..domain.user_profile.values import ProfileSetupState

    pointers = list_profile_buckets()
    own_pointer = pointers.get(bucket_id)
    other = _calendar_other_profiles(bucket_id, pointers)
    incomplete = record.setup_state is not ProfileSetupState.COMPLETE
    return OverviewCalendarRead(
        survey=OverviewCalendarSurveySnapshot(
            from_date=rng.from_date,
            to_date=rng.to_date,
            active_profile_id=bucket_id if active is not None else None,
            active_label=own_pointer.label if own_pointer is not None and active is not None else None,
            active_calendar=active,
            locked=other,
            setup_incomplete=(
                (OverviewLockedProfileSnapshot(profile_id=own_pointer.bucket_id, label=own_pointer.label),)
                if incomplete and own_pointer is not None
                else ()
            ),
        ),
        notices=notices,
        deemed_served_legal_ref=legal_ref,
        refusal_requirements=(
            _refusal_requirements(
                operation=operation,
                taxpayer=taxpayer,
                taxpayer_model_declared=calendar.taxpayer_model_declared,
                warning_codes=tuple(warning.code for warning in calendar.warnings),
            )
            if active is not None and calendar is not None
            else ()
        ),
    )


def _calendar_notice_snapshots(notices: tuple[Notice | None, ...]) -> tuple[OverviewNoticeSnapshot, ...]:
    """Keep every available calendar notice in source order without changing its facts."""
    return tuple(OverviewNoticeSnapshot.from_notice(notice) for notice in notices if notice is not None)
