"""Calculation revision actions for modelo work units.

The calculate paths resolve a law-determined :class:`~domain.calculations.registry.schema.RegistrySnapshot` from
each :class:`~WorkUnit`, merge manual inputs with profile,
borrador, IVA-wallet, and bucket aggregation channels, and execute
:func:`~domain.calculations.registry.formula_runtime.calculate_registry_snapshot` against
the asserted :class:`~domain.calculations.registry.schema.ModeloRevision`.

Persistence is centralized through :class:`~CalculationRevision` and the
application-owned :class:`~.calculation_action_ports.CalculationActionPorts`,
so the work-unit pointer and
``modelo.calculation.created`` event advance with the stored draft revision.

:func:`~application.modelo.calculation_actions.calculate_modelo_revision_with_trusted_mesh_sources`
is the lower-level calculation service: it takes manual, binding, enum-binding,
relation, borrador and IVA-wallet inputs together with the backend channels,
source provenance and unresolved-source issues the source mesh resolved.
:func:`~application.modelo.calculation_bucket_actions.calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`
first runs the application source mesh over bucket-local ledgers, invoices,
previous filings, relation prefill, retenciones, withholding, and detail rows,
then feeds the resolved backend channels into that service. It is
the only entry point into that orchestration, and it returns the non-blocking
source diagnostics with the revision rather than beside it, so no caller can
reach the mesh and lose the advisories on the way out.
Source-owned bindings and their bound casillas are guarded before the engine
runs so a persisted revision cannot claim bucket-source grounding while carrying
a caller substitute for the same value.

See Also:
    :mod:`~application.aggregation`:
        Public source-mesh contracts and diagnostics consumed by the bucket
        aggregation path.
    :func:`~application.modelo.calculation_resolution.resolve_calculation_binding_channels`:
        Merges caller, backend, borrador, and date binding channels for the
        registry engine.
    :func:`~application.modelo.calculation_helpers.build_typed_observations`:
        Projects engine output into provenance-bearing casilla observations.
    :func:`~application.modelo.revision_persistence.persist_calculation_revision`:
        Stores the content-addressed ``BORRADOR`` revision and emits the bucket
        event.
    :func:`~application.modelo.verification_actions.verify_modelo_revision_with_preconditions`:
        Lifecycle gate that promotes a calculated revision after verification.

Core types:
:class:`~cadrumo.domain.calculations.registry.bindings.CasillaObservation`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from ...core.casilla_id import CasillaId
from ...core.irnr import M210GrossIncomeSourceMode
from ...core.time.clock import now
from ...domain.calculations.record_row_membership import ClosedRecordRowSet
from ...domain.calculations.registry.casilla_membership import reject_row_field_template_scalar_inputs
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.formula_runtime import (
    RegistryCalculationResult,
    calculate_registry_snapshot,
)
from ...domain.calculations.registry.formula_text_inputs import validated_text_input_casilla_ids
from ...domain.calculations.registry.ids import (
    BindingId,
    RelationId,
)
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.calculations.row_casilla import DirectRowMaterializationProvenance, RowCasillaKey
from ...domain.calculations.row_source_identity import RowBindingKey, RowSourceIdentity
from ...domain.modelos.calculation_revision_m303_handoff import (
    FilingInstanceEvidence,
    M303RegimenSimplificadoAnnualSummaryHandoff,
)
from ...domain.modelos.calculation_revision_operator_layer import CalculationOperatorLayer
from ...domain.modelos.calculation_revision_rendering import CalculationRenderingSnapshot
from ...domain.modelos.calculation_revision_sources import CalculationSourceIssue, CalculationSourceRef
from ...domain.modelos.invoice_fingerprint import InvoiceFingerprintSnapshot
from ...domain.modelos.ledger_filing_snapshot import LedgerFilingSnapshot
from ...domain.modelos.row_models import ModeloDetailRow
from ...domain.modelos.work_unit import WorkUnit
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ..aggregation.invoice_filing_fingerprint import capture_invoice_fingerprint, draft_contributor_identities
from ..aggregation.renta_imputation import declared_imputation_criteria
from ..aggregation.source_mesh import CalculationSourceDiagnostic
from ..calculations.relation_prefill import activity_start_date_for_bucket
from ..invoices.catalogue_reads_ports import InvoiceCatalogueReadPersistenceError
from ..user_profile.projections import record_to_path_values
from .action_errors import (
    ModeloClearedCasillaSourceFedError,
)
from .bucket_unrouted_source_issues import unrouted_source_issues
from .calculation_action_ports import (
    CalculationActionPorts,
)
from .calculation_helpers import (
    build_typed_observations,
)
from .calculation_input_refusal_doors import cleared_casilla_source_fed_verdict, missing_input_listing_verdict
from .calculation_modelo_adjustments import (
    drop_row_field_template_outputs,
    m131_objective_estimation_data_base_inputs,
    raise_if_m390_303_reconciliation_would_save_silent_zero,
    reconciliation_relation_targets,
    require_detail_rows_declared_for_their_owning_modelo,
)
from .calculation_preparation import PreparedCalculation, prepare_calculation
from .calculation_publication import CalculationRevisionPublication
from .calculation_resolution import (
    build_calculation_replay_payloads,
    calculation_row_binding_values,
    precedence_tier_issue,
    resolve_calculation_inputs,
)
from .calculation_screen import calculation_screen_stamp
from .credit_reconciliation import credit_reconciliation_issues, load_credit_cross_check_sources
from .credit_resolution import (
    CreditResolutionLookup,
    credit_resolution_degradation_diagnostics,
    load_credit_resolutions,
    stale_resolution_issues,
)
from .household_row_fact_input import household_row_fact_input_required
from .imputation_filings import imputation_filings_from_repositories
from .m123_count_authority_gate import Modelo123CountAuthorityStage, require_modelo_123_count_authority
from .m303_filing_evidence import validate_m303_filing_instance_evidence_for_revision
from .m303_regimen_simplificado_scope import m303_general_regime_claimed
from .printed_boxes import snapshot_printed_boxes
from .profile_export_binding import profile_text_fact_index, resolve_profile_text_casilla_inputs
from .profile_maternidad_meses import COTIZACIONES_ROW_FACT_LEAF, descendant_rows_lacking_cotizaciones
from .profile_read_recording import calculation_profile_read_fingerprint
from .profile_readiness_gate import load_modelo_work_profile
from .reconciliation_sources import ReconciliationSourceNeed, reconciliation_source_needs, source_period_needs
from .revision_persistence import persist_calculation_revision
from .work_missing_input import (
    ModeloWorkMissingInputError,
    input_required,
    override_admitted,
    prior_carry_absence_unstated,
    prior_period_unfiled,
)
from .work_profile import ModeloWorkProfile

if TYPE_CHECKING:
    from collections.abc import Callable

    from ...core.period import Period
    from ...core.secure_object_write import SecureObjectWrite
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.calculations.registry.bindings import CasillaObservation
    from ...domain.calculations.registry.schema import RegistrySnapshot
    from .calculation_resolution import CalculationReplayPayloads, ResolvedCalculationChannels


from .calculation_source_guards import (
    m210_gross_source_mode,
    require_m303_regimen_simplificado_annual_summary_arrival_values,
    require_m303_regimen_simplificado_annual_summary_handoff,
    validate_m210_agrupacion_renta_detail_rows,
)


def _draft_ledger_anchor(
    *,
    work_unit: WorkUnit,
    source_transaction_ids: tuple[str, ...],
    transaction_repository: TransactionCatalogueRepositoryProtocol,
    captured_at: datetime,
) -> LedgerFilingSnapshot | None:
    """Return the ledger snapshot this calculation consumed, or ``None``.

    Pins the ledger state these casilla values were computed FROM, so verify can
    later detect that the contributing rows moved underneath a draft. Without it
    a draft has no anchor at all: the snapshot is otherwise captured only on a
    granted verify, which is exactly the drafts that need guarding.

    The anchor for the verify-time drift gate. A ledger-derived draft records
    the fingerprints of the rows its casilla values were computed from, so a
    later verify can tell whether those rows still say what they said. The
    fingerprint covers tax facts only — amount, classification, taxable base,
    IVA and IRPF category, lifecycle state — so it moves when a reclassify
    invalidates the computed values and stays put when an evidence attach does
    not. That discrimination is what lets the gate refuse a stale draft without
    refusing the attach-and-re-verify recovery.

    Returns ``None`` for a revision with no contributing rows: nothing can
    drift under it, and storing an empty snapshot would only add noise.
    """
    if not source_transaction_ids:
        return None
    from ..aggregation.ledger_filing_snapshot import compute_ledger_filing_snapshot

    return compute_ledger_filing_snapshot(
        source_transaction_ids=source_transaction_ids,
        catalogue=transaction_repository.load_by_ids(source_transaction_ids),
        captured_at=captured_at,
    )


def _draft_invoice_fingerprint(
    *,
    work_unit: WorkUnit,
    source_transaction_ids: tuple[str, ...],
    source_issues: tuple[CalculationSourceIssue, ...],
    ports: CalculationActionPorts,
    profile: ModeloWorkProfile,
    captured_at: datetime,
) -> InvoiceFingerprintSnapshot | None:
    """Pin the invoices this draft read; an unreadable catalogue leaves it unknown.

    The source mesh already reported that catalogue as degraded, so the draft has
    its own blocking source issue and a capture failure adds nothing to it.
    """
    try:
        return capture_invoice_fingerprint(
            work_unit=work_unit,
            revision=ports.operation.revision(work_unit.modelo, work_unit.revision_id),
            contributors=draft_contributor_identities(source_transaction_ids, source_issues),
            criteria=declared_imputation_criteria(
                profile.record,
                imputation_filings_from_repositories(
                    bucket_id=work_unit.bucket_id,
                    year=work_unit.filing_year,
                    observation_repository=ports.observation_repository,
                    filing_repository=ports.filing_repository,
                    authority=ports.operation,
                ),
            ),
            ports=ports.invoice_catalogue_read_ports,
            captured_at=captured_at,
        )
    except InvoiceCatalogueReadPersistenceError:
        return None


def _draft_anchors(
    *,
    work_unit: WorkUnit,
    source_transaction_ids: tuple[str, ...],
    source_issues: tuple[CalculationSourceIssue, ...],
    ports: CalculationActionPorts,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None,
    profile: ModeloWorkProfile,
    captured_at: datetime,
) -> tuple[LedgerFilingSnapshot | None, InvoiceFingerprintSnapshot | None]:
    """Pin the ledger rows and invoices a draft was computed from, so verify can detect that they moved."""
    ledger_filing_snapshot = _draft_ledger_anchor(
        work_unit=work_unit,
        source_transaction_ids=source_transaction_ids,
        transaction_repository=transaction_repository
        if transaction_repository is not None
        else ports.transaction_repository,
        captured_at=captured_at,
    )
    invoice_fingerprint = _draft_invoice_fingerprint(
        work_unit=work_unit,
        source_transaction_ids=source_transaction_ids,
        source_issues=source_issues,
        ports=ports,
        profile=profile,
        captured_at=captured_at,
    )
    return ledger_filing_snapshot, invoice_fingerprint


def _optional_mapping_as_dict[OptionalMappingKey, OptionalMappingValue](
    value: Mapping[OptionalMappingKey, OptionalMappingValue] | None,
) -> dict[OptionalMappingKey, OptionalMappingValue]:
    """Materialize an optional action payload with its historical defaults."""
    return dict(value or {})


def _trusted_backend_casilla_inputs(
    *,
    prepared: PreparedCalculation,
    work_unit: WorkUnit,
    revision: ModeloRevision,
) -> dict[CasillaId, Decimal]:
    """Combine registry-derived M131 inputs with prepared backend inputs."""
    return {
        **m131_objective_estimation_data_base_inputs(
            work_unit=work_unit,
            revision=revision,
            binding_values=prepared.channels.bindings,
        ),
        **dict(prepared.backend_casilla_inputs or dict[CasillaId, Decimal]()),
    }


@dataclass(frozen=True, slots=True)
class TrustedMeshEvaluation:
    """One engine run over the canonical prepared channels, before anything is published.

    ``casilla_values`` holds every box the run settled; a box the engine left
    unresolved is absent from it, never zero. ``unresolved_binding_ids`` and
    ``unresolved_relation_ids`` are the source gaps the run was told about, so
    a reader can name the boxes they left without a value.
    """

    prepared: PreparedCalculation
    engine_result: RegistryCalculationResult
    replay_payloads: CalculationReplayPayloads
    casilla_values: dict[CasillaId, Decimal]
    typed_observations: tuple[CasillaObservation, ...]
    filing_instance_evidence: FilingInstanceEvidence | None
    resolved_text_inputs: Mapping[CasillaId, str]
    unresolved_binding_ids: tuple[BindingId, ...]
    unresolved_relation_ids: tuple[RelationId, ...]


@dataclass(frozen=True, slots=True)
class TrustedMeshCalculation:
    """A persisted calculation and the precedence divergences its binding overlay found.

    The blocking divergences are already among the revision's source issues;
    ``precedence_diagnostics`` also carries the advisory ones and the note that
    the operator's resolutions could not be read, which are shown and not
    persisted.
    """

    publication: CalculationRevisionPublication
    engine_result: RegistryCalculationResult
    precedence_diagnostics: tuple[CalculationSourceDiagnostic, ...]
    profile_diagnostics: tuple[CalculationSourceDiagnostic, ...] = ()
    """The profile's unanswered bindings; the ones that name a printed box are among the revision's source issues."""


def _profile_diagnostics_for_open_boxes(
    diagnostics: tuple[CalculationSourceDiagnostic, ...], *, settled: AbstractSet[CasillaId]
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Keep the profile's unanswered bindings whose box the run left without a value.

    A comparison the formula never reached leaves its box settled: the joint-filing reduction of
    box 0461 is zero on an individual return whatever the family situation, so naming that fact
    there would ask the filer for something the calculation did not need. A note that names no
    box cannot be judged this way and is kept.
    """
    return tuple(
        diagnostic
        for diagnostic in diagnostics
        if diagnostic.casilla_id is None or diagnostic.casilla_id not in settled
    )


def _trusted_calculation_clock(clock: datetime | None) -> datetime:
    """Resolve the timestamp shared by ledger anchoring and persistence."""
    return clock or now()


def _precedence_issues(diagnostics: Iterable[CalculationSourceDiagnostic]) -> tuple[CalculationSourceIssue, ...]:
    """Persist every blocking divergence the binding overlay found as a source issue."""
    return tuple(issue for diagnostic in diagnostics if (issue := precedence_tier_issue(diagnostic)) is not None)


def calculate_modelo_revision_with_trusted_mesh_sources(
    work_unit_id: str,
    *,
    ports: CalculationActionPorts,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
    actor: str = "system",
    casilla_inputs: Mapping[CasillaId, Decimal],
    text_casilla_inputs: Mapping[CasillaId, str] | None = None,
    cleared_casilla_ids: tuple[CasillaId, ...] = (),
    operator_layer: CalculationOperatorLayer | None = None,
    binding_values: Mapping[BindingId, Decimal] | None = None,
    enum_binding_values: Mapping[BindingId, str] | None = None,
    backend_binding_values: Mapping[BindingId, Decimal] | None = None,
    row_binding_values: Mapping[tuple[BindingId, int], Decimal | str | int | bool] | None = None,
    row_source_identities: Mapping[RowBindingKey, RowSourceIdentity] | None = None,
    payment_year_binding_values: Mapping[BindingId, Decimal] | None = None,
    instalment_basis_binding_values: Mapping[BindingId, Decimal] | None = None,
    closed_record_row_sets: tuple[ClosedRecordRowSet, ...] = (),
    row_casilla_values: Mapping[RowCasillaKey, Decimal] | None = None,
    row_casilla_provenance: Mapping[RowCasillaKey, DirectRowMaterializationProvenance] | None = None,
    backend_casilla_inputs: Mapping[CasillaId, Decimal] | None = None,
    iva_compensation_decision: object | None = None,
    borrador_snapshot_id: str | None = None,
    relation_values: Mapping[RelationId, Decimal] | None = None,
    unresolved_relation_ids: tuple[RelationId, ...] = (),
    unresolved_binding_ids: tuple[BindingId, ...] = (),
    settled_binding_ids: tuple[BindingId, ...] = (),
    source_transaction_ids: tuple[str, ...] = (),
    m210_official_tipo_renta_code: str | None = None,
    m210_gross_income_source_mode: M210GrossIncomeSourceMode | None = None,
    filing_period_date: date | None = None,
    detail_rows: tuple[ModeloDetailRow, ...] = (),
    source_provenance: tuple[CalculationSourceRef, ...],
    source_issues: tuple[CalculationSourceIssue, ...] = (),
    filing_instance_evidence: FilingInstanceEvidence | None = None,
    m303_regimen_simplificado_annual_summary_handoff: M303RegimenSimplificadoAnnualSummaryHandoff | None = None,
    clock: datetime | None = None,
    additional_secure_object_writes_for_revision: (
        Callable[[str, str | None], tuple[SecureObjectWrite, ...]] | None
    ) = None,
    profile: ModeloWorkProfile | None,
) -> TrustedMeshCalculation:
    """Calculate and persist a revision using trusted source evidence.

    Every blocking divergence the binding overlay found is persisted as a
    source issue on the revision beside ``source_issues``.
    """
    ports.relation_override_migration.migrate(ports.calculation_repository, operation=ports.operation)
    now = _trusted_calculation_clock(clock)
    evaluation = evaluate_modelo_revision_with_trusted_mesh_sources(
        work_unit_id,
        ports=ports,
        evaluated_at=now,
        casilla_inputs=casilla_inputs,
        text_casilla_inputs=text_casilla_inputs,
        cleared_casilla_ids=cleared_casilla_ids,
        binding_values=binding_values,
        enum_binding_values=enum_binding_values,
        backend_binding_values=backend_binding_values,
        row_binding_values=row_binding_values,
        closed_record_row_sets=closed_record_row_sets,
        backend_casilla_inputs=backend_casilla_inputs,
        iva_compensation_decision=iva_compensation_decision,
        borrador_snapshot_id=borrador_snapshot_id,
        relation_values=relation_values,
        unresolved_relation_ids=unresolved_relation_ids,
        unresolved_binding_ids=unresolved_binding_ids,
        settled_binding_ids=settled_binding_ids,
        m210_official_tipo_renta_code=m210_official_tipo_renta_code,
        filing_period_date=filing_period_date,
        detail_rows=detail_rows,
        source_provenance=source_provenance,
        filing_instance_evidence=filing_instance_evidence,
        m303_regimen_simplificado_annual_summary_handoff=m303_regimen_simplificado_annual_summary_handoff,
        profile=profile,
    )
    return _persist_trusted_evaluation(
        evaluation,
        work_unit_id=work_unit_id,
        ports=ports,
        transaction_repository=transaction_repository,
        actor=actor,
        now=now,
        source_issues=source_issues,
        payment_year_binding_values=payment_year_binding_values,
        instalment_basis_binding_values=instalment_basis_binding_values,
        source_transaction_ids=source_transaction_ids,
        row_source_identities=row_source_identities,
        closed_record_row_sets=closed_record_row_sets,
        row_casilla_values=row_casilla_values,
        row_casilla_provenance=row_casilla_provenance,
        cleared_casilla_ids=cleared_casilla_ids,
        operator_layer=operator_layer,
        m210_official_tipo_renta_code=m210_official_tipo_renta_code,
        m210_gross_income_source_mode=m210_gross_income_source_mode,
        source_provenance=source_provenance,
        m303_regimen_simplificado_annual_summary_handoff=m303_regimen_simplificado_annual_summary_handoff,
        detail_rows=detail_rows,
        additional_secure_object_writes_for_revision=additional_secure_object_writes_for_revision,
    )


def _persist_trusted_evaluation(
    evaluation: TrustedMeshEvaluation,
    *,
    work_unit_id: str,
    ports: CalculationActionPorts,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None,
    actor: str,
    now: datetime,
    source_issues: tuple[CalculationSourceIssue, ...],
    payment_year_binding_values: Mapping[BindingId, Decimal] | None,
    instalment_basis_binding_values: Mapping[BindingId, Decimal] | None,
    source_transaction_ids: tuple[str, ...],
    row_source_identities: Mapping[RowBindingKey, RowSourceIdentity] | None,
    closed_record_row_sets: tuple[ClosedRecordRowSet, ...],
    row_casilla_values: Mapping[RowCasillaKey, Decimal] | None,
    row_casilla_provenance: Mapping[RowCasillaKey, DirectRowMaterializationProvenance] | None,
    cleared_casilla_ids: tuple[CasillaId, ...],
    operator_layer: CalculationOperatorLayer | None,
    m210_official_tipo_renta_code: str | None,
    m210_gross_income_source_mode: M210GrossIncomeSourceMode | None,
    source_provenance: tuple[CalculationSourceRef, ...],
    m303_regimen_simplificado_annual_summary_handoff: M303RegimenSimplificadoAnnualSummaryHandoff | None,
    detail_rows: tuple[ModeloDetailRow, ...],
    additional_secure_object_writes_for_revision: (Callable[[str, str | None], tuple[SecureObjectWrite, ...]] | None),
) -> TrustedMeshCalculation:
    """Persist an evaluated calculation as a revision and project its diagnostics."""
    prepared = evaluation.prepared
    work_unit = prepared.work_unit
    snapshot = prepared.snapshot
    channels = prepared.channels
    replay_payloads = evaluation.replay_payloads
    casilla_values = evaluation.casilla_values
    profile_diagnostics, revision_source_issues, resolution_lookup = _revision_source_issues(
        evaluation,
        source_issues,
        payment_year_binding_values=payment_year_binding_values,
        instalment_basis_binding_values=instalment_basis_binding_values,
        ports=ports,
    )
    ledger_filing_snapshot, invoice_fingerprint = _draft_anchors(
        work_unit=work_unit,
        source_transaction_ids=source_transaction_ids,
        source_issues=revision_source_issues,
        ports=ports,
        transaction_repository=transaction_repository,
        profile=prepared.profile,
        captured_at=now,
    )
    publication = persist_calculation_revision(
        operation=ports.operation,
        work_unit_id=work_unit_id,
        registry_snapshot_ref=snapshot.snapshot_ref,
        rendering_snapshot=_capture_calculation_rendering(snapshot, operation=ports.operation),
        screen_stamp=calculation_screen_stamp(snapshot, operation=ports.operation),
        work_unit=work_unit,
        work_units=prepared.work_units,
        work_units_revision_id=prepared.work_units_revision_id,
        ledger_filing_snapshot=ledger_filing_snapshot,
        invoice_fingerprint=invoice_fingerprint,
        profile_read_fingerprint=calculation_profile_read_fingerprint(
            channels.profile_read_fingerprint,
            prepared.profile.record.facts,
        ),
        input_values_by_casilla_id={**replay_payloads.input_values_by_casilla_id, **evaluation.resolved_text_inputs},
        binding_overrides=replay_payloads.binding_overrides,
        row_binding_values=replay_payloads.row_binding_values,
        row_source_identities=_optional_mapping_as_dict(row_source_identities),
        closed_record_row_sets=closed_record_row_sets,
        row_casilla_values=_optional_mapping_as_dict(row_casilla_values),
        row_casilla_provenance=_optional_mapping_as_dict(row_casilla_provenance),
        relation_overrides=replay_payloads.relation_overrides,
        casilla_values=casilla_values,
        source_transaction_ids=source_transaction_ids,
        m210_official_tipo_renta_code=m210_official_tipo_renta_code,
        m210_gross_income_source_mode=m210_gross_source_mode(work_unit, m210_gross_income_source_mode),
        borrador_snapshot_id=channels.borrador_snapshot_id,
        bindings_sourced_from_borrador=channels.bindings_sourced_from_borrador,
        cleared_casilla_ids=cleared_casilla_ids,
        operator_layer=operator_layer,
        observations=evaluation.typed_observations,
        unresolved_outcomes=evaluation.engine_result.unresolved_outcomes,
        source_provenance=(*source_provenance, *channels.profile_source_provenance),
        source_issues=revision_source_issues,
        filing_instance_evidence=evaluation.filing_instance_evidence,
        m303_regimen_simplificado_annual_summary_handoff=m303_regimen_simplificado_annual_summary_handoff,
        detail_rows=detail_rows,
        formula_count=len(evaluation.engine_result.entries),
        actor=actor,
        now=now,
        calculation_repository=ports.calculation_repository,
        work_unit_repository=ports.work_unit_repository,
        bucket_event_repository=ports.bucket_event_repository,
        additional_secure_object_writes_for_revision=additional_secure_object_writes_for_revision,
    )
    return TrustedMeshCalculation(
        publication=publication,
        engine_result=evaluation.engine_result,
        precedence_diagnostics=(
            *channels.precedence_diagnostics,
            *credit_resolution_degradation_diagnostics(resolution_lookup),
        ),
        profile_diagnostics=profile_diagnostics,
    )


def _revision_source_issues(
    evaluation: TrustedMeshEvaluation,
    source_issues: tuple[CalculationSourceIssue, ...],
    *,
    payment_year_binding_values: Mapping[BindingId, Decimal] | None,
    instalment_basis_binding_values: Mapping[BindingId, Decimal] | None,
    ports: CalculationActionPorts,
) -> tuple[
    tuple[CalculationSourceDiagnostic, ...],
    tuple[CalculationSourceIssue, ...],
    CreditResolutionLookup,
]:
    """Assemble every source issue the evaluated revision persists, with the profile notes and credit resolutions.

    The caller's issues come first, then the blocking precedence divergences, the profile's unanswered
    bindings that name a printed box the run left open, and finally the credit reconciliation issues.
    """
    prepared = evaluation.prepared
    snapshot = prepared.snapshot
    channels = prepared.channels
    profile_diagnostics = _profile_diagnostics_for_open_boxes(
        channels.profile_diagnostics,
        settled=evaluation.casilla_values.keys() | evaluation.resolved_text_inputs.keys(),
    )
    revision_source_issues, resolution_lookup = _with_credit_source_issues(
        (
            *source_issues,
            *_precedence_issues(channels.precedence_diagnostics),
            *unrouted_source_issues(profile_diagnostics, snapshot_printed_boxes(ports.operation, snapshot)),
        ),
        snapshot,
        prepared.work_unit,
        casilla_values=evaluation.casilla_values,
        channels=channels,
        payment_year_binding_values=payment_year_binding_values,
        instalment_basis_binding_values=instalment_basis_binding_values,
        ports=ports,
    )
    return profile_diagnostics, revision_source_issues, resolution_lookup


def _with_credit_source_issues(
    revision_source_issues: tuple[CalculationSourceIssue, ...],
    snapshot: RegistrySnapshot,
    work_unit: WorkUnit,
    *,
    casilla_values: Mapping[CasillaId, Decimal],
    channels: ResolvedCalculationChannels,
    payment_year_binding_values: Mapping[BindingId, Decimal] | None,
    instalment_basis_binding_values: Mapping[BindingId, Decimal] | None,
    ports: CalculationActionPorts,
) -> tuple[tuple[CalculationSourceIssue, ...], CreditResolutionLookup]:
    """Add the credit reconciliation issues and the stale-resolution issues to the revision's source issues."""
    reconciled = (
        *revision_source_issues,
        *credit_reconciliation_issues(
            snapshot,
            work_unit,
            casilla_values=casilla_values,
            binding_values=channels.bindings,
            sources=load_credit_cross_check_sources(
                snapshot,
                work_unit,
                ports=ports,
                borrador_snapshot_id=channels.borrador_snapshot_id,
                payment_year_binding_values=payment_year_binding_values or {},
                instalment_basis_binding_values=instalment_basis_binding_values or {},
            ),
        ),
    )
    resolution_lookup = load_credit_resolutions(
        ports.credit_resolution_reader,
        modelo=str(work_unit.modelo),
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
    )
    return (*reconciled, *stale_resolution_issues(reconciled, resolution_lookup)), resolution_lookup


def evaluate_modelo_revision_with_trusted_mesh_sources(
    work_unit_id: str,
    *,
    ports: CalculationActionPorts,
    evaluated_at: datetime,
    casilla_inputs: Mapping[CasillaId, Decimal],
    text_casilla_inputs: Mapping[CasillaId, str] | None = None,
    cleared_casilla_ids: tuple[CasillaId, ...] = (),
    binding_values: Mapping[BindingId, Decimal] | None = None,
    enum_binding_values: Mapping[BindingId, str] | None = None,
    backend_binding_values: Mapping[BindingId, Decimal] | None = None,
    row_binding_values: Mapping[tuple[BindingId, int], Decimal | str | int | bool] | None = None,
    closed_record_row_sets: tuple[ClosedRecordRowSet, ...] = (),
    backend_casilla_inputs: Mapping[CasillaId, Decimal] | None = None,
    iva_compensation_decision: object | None = None,
    borrador_snapshot_id: str | None = None,
    relation_values: Mapping[RelationId, Decimal] | None = None,
    unresolved_relation_ids: tuple[RelationId, ...] = (),
    unresolved_binding_ids: tuple[BindingId, ...] = (),
    settled_binding_ids: tuple[BindingId, ...] = (),
    m210_official_tipo_renta_code: str | None = None,
    filing_period_date: date | None = None,
    detail_rows: tuple[ModeloDetailRow, ...] = (),
    source_provenance: tuple[CalculationSourceRef, ...],
    filing_instance_evidence: FilingInstanceEvidence | None = None,
    m303_regimen_simplificado_annual_summary_handoff: M303RegimenSimplificadoAnnualSummaryHandoff | None = None,
    profile: ModeloWorkProfile | None,
) -> TrustedMeshEvaluation:
    """Run the preparation gates and the engine over trusted source evidence, publishing nothing.

    This is the evaluation the persisting calculation publishes, so a reader
    that only needs the engine's answer gets exactly what a calculation would
    have saved. Preparation may still persist a refreshed Modelo 303 IVA-wallet
    decision, as it does for every calculation of that modelo.
    """
    prepared = prepare_calculation(
        evaluated_at=evaluated_at,
        work_unit_id=work_unit_id,
        work_unit_repository=ports.work_unit_repository,
        calculation_repository=ports.calculation_repository,
        casilla_inputs=casilla_inputs,
        backend_casilla_inputs=backend_casilla_inputs,
        ledger_preflight_transaction_repository=ports.transaction_repository,
        operation=ports.operation,
        iva_compensation_decision=iva_compensation_decision,
        observation_repository=ports.observation_repository,
        iva_compensation_decision_repository=ports.iva_compensation_decision_repository,
        iva_compensation_history_repository=ports.iva_compensation_history_repository,
        binding_values=binding_values,
        enum_binding_values=enum_binding_values,
        backend_binding_values=backend_binding_values,
        filing_period_date=filing_period_date,
        borrador_snapshot_id=borrador_snapshot_id,
        borrador_snapshot_repository=ports.borrador_snapshot_repository,
        unresolved_relation_ids=unresolved_relation_ids,
        unresolved_binding_ids=unresolved_binding_ids,
        profile=profile,
        backend_source_provenance=source_provenance,
    )
    (
        engine_result,
        replay_payloads,
        casilla_values,
        typed_observations,
        validated_filing_instance_evidence,
        resolved_text_inputs,
    ) = _evaluate_prepared_calculation(
        prepared,
        ports,
        detail_rows,
        m210_official_tipo_renta_code,
        relation_values,
        text_casilla_inputs,
        cleared_casilla_ids,
        unresolved_relation_ids,
        unresolved_binding_ids,
        settled_binding_ids,
        closed_record_row_sets,
        row_binding_values,
        filing_instance_evidence,
        m303_regimen_simplificado_annual_summary_handoff,
    )
    return TrustedMeshEvaluation(
        prepared=prepared,
        engine_result=engine_result,
        replay_payloads=replay_payloads,
        casilla_values=casilla_values,
        typed_observations=typed_observations,
        filing_instance_evidence=validated_filing_instance_evidence,
        resolved_text_inputs=resolved_text_inputs,
        unresolved_binding_ids=unresolved_binding_ids,
        unresolved_relation_ids=unresolved_relation_ids,
    )


def _reject_clears_of_source_fed_casillas(
    cleared_casilla_ids: tuple[CasillaId, ...],
    *,
    resolved_casilla_ids: tuple[CasillaId, ...],
) -> None:
    """Refuse an explicit clear that a source would immediately refill.

    A caller never supplies a value for a casilla it clears, so a cleared
    casilla that still reaches the resolved inputs was fed by a source tier.
    Persisting the clear would record "cleared" beside the source's value for
    the same casilla -- two contradictory facts about one box.
    """
    fed = sorted(set(cleared_casilla_ids).intersection(resolved_casilla_ids))
    if fed:
        raise ModeloClearedCasillaSourceFedError(
            translated_message="errors.error.error_modelo_cleared_casilla_source_fed",
            context={"casilla_ids": ",".join(fed)},
            precondition_verdict=cleared_casilla_source_fed_verdict(",".join(fed)),
        )


def _capture_calculation_rendering(
    snapshot: RegistrySnapshot, *, operation: PinnedAuthorityOperation
) -> CalculationRenderingSnapshot:
    """Join the separately published form under the actual calculation's leased pin."""
    layout = operation.form_layout(snapshot.modelo.id, snapshot.revision.id)
    if layout is not None:
        snapshot = snapshot.model_copy(
            update={"revision": snapshot.revision.model_copy(update={"form_layouts": (layout,)})}
        )
    return CalculationRenderingSnapshot.capture(snapshot, authority_generation=operation.pin().logical_generation)


def _calculate_prepared_registry_snapshot(
    snapshot: RegistrySnapshot,
    *,
    resolved_inputs: Mapping[CasillaId, Decimal],
    resolved_text_inputs: Mapping[CasillaId, str],
    period_date: date,
    binding_values: Mapping[BindingId, Decimal],
    enum_binding_values: Mapping[BindingId, str],
    relation_values: Mapping[RelationId, Decimal],
    unresolved_relation_ids: tuple[RelationId, ...],
    unresolved_binding_ids: tuple[BindingId, ...],
    date_binding_values: Mapping[BindingId, date],
    boolean_binding_values: Mapping[BindingId, bool],
    closed_record_row_sets: tuple[ClosedRecordRowSet, ...] = (),
    settled_binding_ids: tuple[BindingId, ...] = (),
) -> RegistryCalculationResult:
    """Evaluate the registry after application channels have been resolved."""
    return calculate_registry_snapshot(
        snapshot,
        inputs=resolved_inputs,
        text_inputs=resolved_text_inputs or None,
        date_context={"filing_period": period_date},
        binding_values=binding_values,
        enum_binding_values=enum_binding_values,
        relation_values=relation_values,
        unresolved_relation_ids=unresolved_relation_ids,
        unresolved_binding_ids=unresolved_binding_ids,
        settled_binding_ids=settled_binding_ids,
        date_binding_values=date_binding_values or None,
        boolean_binding_values=boolean_binding_values or None,
        closed_record_row_sets=closed_record_row_sets,
    )


def calculation_source_period_needs(
    work_unit: WorkUnit,
    periods: Iterable[tuple[str, Period]],
    *,
    ports: CalculationActionPorts,
) -> tuple[ReconciliationSourceNeed, ...]:
    """Where each earlier (modelo, period) a calculation reads stands, read from the calculation's ports.

    A period that ended before the activity started owes no return, so it is
    never named as one the calculation waits on.
    """
    activity_start = activity_start_date_for_bucket(
        work_unit.bucket_id, profile_path_values_reader=ports.profile_read_ports.path_values
    )
    owed = tuple(
        (modelo, period)
        for modelo, period in periods
        if activity_start is None or not period.has_date_span() or period.end_date >= activity_start
    )
    if not owed:
        return ()
    return source_period_needs(
        owed,
        bucket_id=work_unit.bucket_id,
        work_catalogue=ports.work_unit_repository.load(),
        calculation_catalogue=ports.calculation_repository.load(operation=ports.operation),
        observations=ports.observation_repository,
        operation=ports.operation,
    )


def calculation_reconciliation_source_needs(
    work_unit: WorkUnit,
    snapshot: RegistrySnapshot,
    *,
    ports: CalculationActionPorts,
    relation_ids: Iterable[RelationId] | None = None,
) -> tuple[ReconciliationSourceNeed, ...]:
    """Where each source declaration of the snapshot's reconciliation stands, read from the calculation's ports.

    A revision that declares no reconciliation relation needs nothing, so no store is read for it.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`.
    """
    if not reconciliation_relation_targets(snapshot):
        return ()
    return reconciliation_source_needs(
        snapshot,
        bucket_id=work_unit.bucket_id,
        work_catalogue=ports.work_unit_repository.load(),
        calculation_catalogue=ports.calculation_repository.load(operation=ports.operation),
        observations=ports.observation_repository,
        activity_start_date=activity_start_date_for_bucket(
            work_unit.bucket_id, profile_path_values_reader=ports.profile_read_ports.path_values
        ),
        operation=ports.operation,
        relation_ids=relation_ids,
    )


def _refused_missing_input(
    missing: ModeloWorkMissingInputError,
    *,
    work_unit: WorkUnit,
    snapshot: RegistrySnapshot,
    ports: CalculationActionPorts,
    unresolved_binding_ids: frozenset[BindingId],
) -> ModeloWorkMissingInputError:
    """The refusal a binding without a value is served as, with the door to the input it needs.

    A carry the filer can state holds nothing is refused as that open statement,
    naming every carry of its family the sources left open. A carry from an
    earlier period of this ejercicio waits on that period's filed return, which
    the refusal opens or offers to create. Any other missing input is the
    operator's to supply, so the refusal names it and serves the door to it.
    """
    boxes = snapshot_printed_boxes(ports.operation, snapshot)
    unstated = prior_carry_absence_unstated(
        missing,
        work_unit=work_unit,
        snapshot=snapshot,
        boxes=boxes,
        unresolved_binding_ids=unresolved_binding_ids,
    )
    if unstated is not None:
        return unstated
    unfiled = prior_period_unfiled(
        missing,
        work_unit=work_unit,
        snapshot=snapshot,
        source_needs=lambda periods: calculation_source_period_needs(work_unit, periods, ports=ports),
    )
    if unfiled is not None:
        return unfiled
    unstated_row_fact = _household_row_fact_refusal(missing, work_unit=work_unit, snapshot=snapshot, ports=ports)
    if unstated_row_fact is not None:
        return unstated_row_fact
    return input_required(
        missing,
        work_unit=work_unit,
        snapshot=snapshot,
        boxes=boxes,
        overridable=_override_admitted(missing, work_unit=work_unit, snapshot=snapshot, ports=ports),
    )


def _household_row_fact_refusal(
    missing: ModeloWorkMissingInputError,
    *,
    work_unit: WorkUnit,
    snapshot: RegistrySnapshot,
    ports: CalculationActionPorts,
) -> ModeloWorkMissingInputError | None:
    """The refusal naming the descendant rows whose cotizaciones the filer never stated, if ``missing`` waits on them.

    The household row fact gate words it and serves the profile door for the descendant
    rows; ``None`` when the binding does not wait on a household row fact.
    """
    profile = load_modelo_work_profile(
        bucket_id=work_unit.bucket_id, profile_decode_context=ports.operation.profile_decode_context()
    )
    if profile is None:
        return None
    rows = descendant_rows_lacking_cotizaciones(profile.record, snapshot, missing.binding_id, operation=ports.operation)
    return household_row_fact_input_required(
        missing,
        work_unit=work_unit,
        group="renta_family.descendiente",
        fact_leaf=COTIZACIONES_ROW_FACT_LEAF,
        rows=rows,
    )


def _override_admitted(
    missing: ModeloWorkMissingInputError,
    *,
    work_unit: WorkUnit,
    snapshot: RegistrySnapshot,
    ports: CalculationActionPorts,
) -> bool:
    """Whether the edit admission lets the operator state the value ``missing`` names on this work unit."""
    return override_admitted(
        snapshot,
        missing.binding_id,
        period=work_unit.period.registry_token,
        layout=ports.operation.form_layout(str(work_unit.modelo), snapshot.revision.id),
    )


def _resolve_prepared_casilla_inputs(
    prepared: PreparedCalculation,
    ports: CalculationActionPorts,
    *,
    text_casilla_inputs: Mapping[CasillaId, str] | None,
) -> tuple[dict[CasillaId, Decimal], dict[CasillaId, str]]:
    """Resolve the numeric and text casilla inputs the engine runs over from every prepared channel."""
    work_unit = prepared.work_unit
    revision = prepared.snapshot.revision
    channel_inputs = resolve_calculation_inputs(
        revision=revision,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        backend_casilla_inputs=_trusted_backend_casilla_inputs(
            prepared=prepared, work_unit=work_unit, revision=revision
        ),
        resolved_bindings=prepared.channels.bindings,
        casilla_inputs=prepared.casilla_inputs,
        text_casilla_inputs=text_casilla_inputs,
        resolved_text_bindings=prepared.channels.enum_bindings,
        profile_text_casilla_inputs=resolve_profile_text_casilla_inputs(
            revision,
            profile_text_fact_index(
                prepared.profile.record,
                prepared.profile.profile_decode_context.schema,
                operation=ports.operation,
            ),
        ).values,
    )
    return channel_inputs.casilla_inputs, validated_text_input_casilla_ids(channel_inputs.text_casilla_inputs)


def _evaluate_prepared_calculation(
    prepared: PreparedCalculation,
    ports: CalculationActionPorts,
    detail_rows: tuple[ModeloDetailRow, ...],
    m210_official_tipo_renta_code: str | None,
    relation_values: Mapping[RelationId, Decimal] | None,
    text_casilla_inputs: Mapping[CasillaId, str] | None,
    cleared_casilla_ids: tuple[CasillaId, ...],
    unresolved_relation_ids: tuple[RelationId, ...],
    unresolved_binding_ids: tuple[BindingId, ...],
    settled_binding_ids: tuple[BindingId, ...],
    closed_record_row_sets: tuple[ClosedRecordRowSet, ...],
    row_binding_values: Mapping[tuple[BindingId, int], Decimal | str | int | bool] | None,
    filing_instance_evidence: FilingInstanceEvidence | None,
    m303_regimen_simplificado_annual_summary_handoff: M303RegimenSimplificadoAnnualSummaryHandoff | None,
) -> tuple[
    RegistryCalculationResult,
    CalculationReplayPayloads,
    dict[CasillaId, Decimal],
    tuple[CasillaObservation, ...],
    FilingInstanceEvidence | None,
    Mapping[CasillaId, str],
]:
    """Evaluate the pinned snapshot and validate its publication evidence."""
    work_unit = prepared.work_unit
    snapshot = prepared.snapshot
    require_modelo_123_count_authority(
        work_unit,
        retencion_ports=ports.retencion_observation_ports,
        stage=Modelo123CountAuthorityStage.CALCULATE,
    )
    require_m303_regimen_simplificado_annual_summary_handoff(
        revision=snapshot.revision,
        profile=prepared.profile,
        handoff=m303_regimen_simplificado_annual_summary_handoff,
    )
    require_detail_rows_declared_for_their_owning_modelo(work_unit=work_unit, detail_rows=detail_rows)
    validate_m210_agrupacion_renta_detail_rows(work_unit, detail_rows, m210_official_tipo_renta_code)
    resolved_relations = _optional_mapping_as_dict(relation_values)
    resolved_inputs, resolved_text_inputs = _resolve_prepared_casilla_inputs(
        prepared, ports, text_casilla_inputs=text_casilla_inputs
    )
    _reject_clears_of_source_fed_casillas(
        cleared_casilla_ids,
        resolved_casilla_ids=(*resolved_inputs, *resolved_text_inputs),
    )
    # The row-field template outputs are dropped after the engine runs, so a
    # scalar input for one would be persisted with no observation to ground it.
    reject_row_field_template_scalar_inputs(snapshot.revision, (*resolved_inputs, *resolved_text_inputs))

    try:
        engine_result = _calculate_prepared_registry_snapshot(
            snapshot,
            resolved_inputs=resolved_inputs,
            resolved_text_inputs=resolved_text_inputs,
            period_date=prepared.period_date,
            binding_values=prepared.channels.bindings,
            enum_binding_values=prepared.channels.enum_bindings,
            relation_values=resolved_relations,
            unresolved_relation_ids=unresolved_relation_ids,
            unresolved_binding_ids=unresolved_binding_ids,
            settled_binding_ids=settled_binding_ids,
            date_binding_values=prepared.channels.date_bindings,
            boolean_binding_values=prepared.channels.boolean_bindings,
            closed_record_row_sets=closed_record_row_sets,
        )
    except RegistryValidationError as error:
        missing = ModeloWorkMissingInputError.from_registry_error(
            error, precondition_verdict=missing_input_listing_verdict(work_unit)
        )
        if missing is None:
            raise
        # This boundary precedes revision publication. Earlier migrations may
        # already have written state; later advisory failures never enter it.
        raise _refused_missing_input(
            missing,
            work_unit=work_unit,
            snapshot=snapshot,
            ports=ports,
            unresolved_binding_ids=frozenset(unresolved_binding_ids).difference(prepared.channels.bindings),
        ) from error

    replay_payloads = build_calculation_replay_payloads(
        resolved_inputs=resolved_inputs,
        resolved_bindings=prepared.channels.bindings,
        resolved_enum_bindings=prepared.channels.enum_bindings,
        resolved_date_bindings=prepared.channels.date_bindings,
        resolved_relations=resolved_relations,
        resolved_row_bindings=calculation_row_binding_values(row_binding_values, prepared.channels),
        resolved_boolean_bindings=prepared.channels.boolean_bindings,
    )
    casilla_values = dict(engine_result.values)
    require_m303_regimen_simplificado_annual_summary_arrival_values(
        casilla_values=casilla_values,
        handoff=m303_regimen_simplificado_annual_summary_handoff,
    )
    raise_if_m390_303_reconciliation_would_save_silent_zero(
        work_unit=work_unit,
        snapshot=snapshot,
        casilla_values=casilla_values,
        resolved_binding_values=prepared.channels.bindings,
        general_regime_claimed=m303_general_regime_claimed(
            record_to_path_values(prepared.profile.record).get("iva.m303_regime_composition")
        ),
        observations=engine_result.observations,
        supplied_casilla_ids=frozenset(resolved_inputs),
        answered_binding_ids=frozenset(
            (*prepared.channels.bindings, *prepared.channels.boolean_bindings, *settled_binding_ids)
        ),
        source_needs=lambda relation_ids: calculation_reconciliation_source_needs(
            work_unit, snapshot, ports=ports, relation_ids=relation_ids
        ),
    )
    typed_observations = build_typed_observations(engine_result=engine_result, snapshot=snapshot)
    casilla_values, typed_observations = drop_row_field_template_outputs(
        revision=snapshot.revision,
        casilla_values=casilla_values,
        observations=typed_observations,
    )
    validated_filing_instance_evidence = validate_m303_filing_instance_evidence_for_revision(
        work_unit=work_unit,
        registry_snapshot=snapshot,
        evidence=filing_instance_evidence,
        casilla_values=casilla_values,
        observations=typed_observations,
        operation=ports.operation,
        profile=prepared.profile,
    )

    return (
        engine_result,
        replay_payloads,
        casilla_values,
        typed_observations,
        validated_filing_instance_evidence,
        resolved_text_inputs,
    )
