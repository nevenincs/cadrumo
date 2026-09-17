"""External filing import actions for modelo baselines.

:func:`~cadrumo.application.modelo.external_import_actions.import_external_filing_evidence` turns
AEAT-attested external evidence into a presented
:class:`CalculationRevision` plus current
:class:`ModeloRecord`. Evidence-bearing imports validate the
referenced :class:`Justificante`, stamp an
:class:`ExternalEvidence` payload on the filing record,
supersede any prior current filing for the same target, and emit
``modelo.filing.imported`` through
:class:`~cadrumo.domain.buckets.protocols.BucketEventHistoryRepositoryProtocol`.

The imported record is the production baseline consumed by the amendment path.
It is intentionally distinct from a locally calculated and filed return:
``external_evidence`` marks that the values came from official AEAT evidence,
while
:func:`~cadrumo.application.modelo._calculation_helpers.external_filing_observations`
keeps the imported casilla values on the same registry-grounded
:class:`CasillaObservation` contract as local
calculation revisions.

See Also:
    :func:`~cadrumo.entrypoints.cli._modelo_records_cli.filing_record_import`:
        CLI surface that parses ``filing-record import`` options and calls this
        service.
    :func:`~cadrumo.application.modelo.amendment_actions.amend_modelo_revision`:
        Consumes the imported current :class:`ModeloRecord`
        as an amendment baseline.
    :mod:`~cadrumo.domain.justificante`:
        Receipt metadata store required by justificante-PDF and live-capture evidence
        kinds. CSV/XLSX register imports bind the source reference directly to
        the target work-unit coordinates instead of masquerading as a receipt.
    :func:`~cadrumo.application.modelo._registry_helpers.reject_unknown_import_casillas`:
        Resolves the registry snapshot and refuses noncanonical or undeclared
        imported casilla ids.
    :class:`ExternalEvidence`:
        Filing-record metadata that records the official evidence source.

Core types:
:class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

from ...core.casilla_id import CasillaId, validated_casilla_id
from ...core.decimal.coercion import normalize_decimal_separators
from ...core.identity.hex_ids import CalculationRevisionId
from ...core.modelo import Modelo
from ...core.observed_header_fact import ObservedHeaderFact
from ...core.period import Period
from ...core.time.clock import now as _utc_now
from ...domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from ...domain.calculations.registry.authority import bundled_indexed_authority
from ...domain.calculations.registry.bindings import CasillaObservation, RegistryModeloObservation
from ...domain.calculations.registry.ids import (
    BindingId,
    RelationId,
)
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.calculations.registry.schema_references import RegistrySnapshotRef
from ...domain.justificante.protocols import JustificanteRepositoryProtocol
from ...domain.justificante.schema import Justificante
from ...domain.modelos.calculation_repository import upsert_calculation_revision
from ...domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ...domain.modelos.calculation_revision_m303_handoff import FilingInstanceEvidence
from ...domain.modelos.codes import ModeloCode
from ...domain.modelos.filing_record import (
    AeatConfirmationState,
    AeatRegisterRef,
    ExternalEvidence,
    ExternalEvidenceKind,
    FilingDeclarationKind,
    FilingOrigin,
    ModeloRecord,
    ModeloRecordStatus,
    is_receipt_bound_external_evidence,
)
from ...domain.modelos.protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    ModeloRecordCatalogueRepositoryProtocol,
)
from ...domain.modelos.repository import upsert_work_unit
from ...domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ..calculations.observations_repository import (
    CalculationObservationRepositoryProtocol,
    ObservationEnvelopePayload,
    ObservationSourceKind,
)
from ..user_profile.custody_ports import default_profile_bucket_event_history_repository
from ..workflow.active_profile import require_active_profile_bucket_id
from ._calculation_helpers import external_filing_observations as _external_filing_observations
from ._registry_helpers import reject_unknown_import_casillas as _reject_unknown_import_casillas
from .action_errors import ExternalModeloImportError
from .calculation_repository import calculation_revision_catalogue_repository
from .filing_repository import modelo_record_catalogue_repository
from .justificante_repository import justificante_repository as resolve_justificante_repository
from .work_addressing import (
    ModeloWorkRevisionConflictError,
    ModeloWorkVisibleTargetAmbiguousError,
    law_selected_revision_for_work_target,
)
from .work_lifecycle import ActiveWorkUnitUse, create_work_unit, require_active_work_unit
from .work_lifecycle_ports import WorkLifecyclePorts
from .work_selection import (
    ModeloWorkResolution,
    ModeloWorkSelectionMode,
    ModeloWorkSelectorRequest,
    select_modelo_work_resolution,
)
from .work_unit_repository import work_unit_catalogue_repository

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from .filing_chain_reconciliation import FilingReconciliationResult


@dataclass(frozen=True, slots=True)
class ExternalFilingBaselineSource:
    """One source-only, casilla-complete external filing observation."""

    modelo: str
    filing_year: int
    period: Period
    evidence_kind: ExternalEvidenceKind
    evidence_reference_id: str
    tax_id: str
    casilla_lexicals: Mapping[CasillaId, str]
    registry_revision_id: str | None = None


@dataclass(frozen=True, slots=True)
class ExternalFilingTarget:
    """The filing coordinate an external filing is recorded against."""

    modelo: str
    filing_year: int
    period: Period
    registry_revision_id: str | None = None


@dataclass(frozen=True, slots=True)
class ExternalFilingRevisionDraft:
    """A validated, not yet persisted, presented revision for external filing content."""

    work_units: WorkUnitCatalogue
    work_unit: WorkUnit
    revisions: CalculationRevisionCatalogue
    revisions_revision_id: str
    revision: CalculationRevision
    evidence_reference_id: str
    snapshot: RegistrySnapshot
    canonical_values: Mapping[CasillaId, Decimal]


def _select_active_external_import_work_unit(
    target: ExternalFilingTarget,
    *,
    catalogue: WorkUnitCatalogue,
    bucket_id: str,
) -> ModeloWorkResolution:
    """Apply the canonical active-only cardinality policy to one captured catalogue."""
    return select_modelo_work_resolution(
        ModeloWorkSelectorRequest(
            bucket_id=bucket_id,
            modelo=ModeloCode(target.modelo),
            filing_year=target.filing_year,
            period=target.period,
            revision_id=target.registry_revision_id,
        ),
        catalogue=catalogue,
        bucket_id=bucket_id,
        mode=ModeloWorkSelectionMode.ACTIVE_NATURAL,
    )


def _validate_external_source_shape(source: ExternalFilingBaselineSource) -> None:
    """Reject source metadata that cannot identify a filing target or values."""
    if source.period.filing_year != source.filing_year:
        raise ExternalModeloImportError(
            translated_message="application.modelo.errors.external_import_source_period_mismatch",
        )
    if not source.casilla_lexicals:
        raise ExternalModeloImportError(
            translated_message="application.modelo.errors.external_filing_no_casilla_values",
        )


def _parse_external_source_values(
    source: ExternalFilingBaselineSource,
) -> tuple[dict[CasillaId, str], dict[CasillaId, Decimal]]:
    """Parse source lexicals while retaining their exact input representation."""
    lexical_values: dict[CasillaId, str] = {}
    decimal_values: dict[CasillaId, Decimal] = {}
    for raw_casilla_id, raw_lexical in source.casilla_lexicals.items():
        casilla_id = validated_casilla_id(raw_casilla_id, surface="external filing source")
        lexical = raw_lexical.strip()
        if not lexical:
            raise ExternalModeloImportError(
                translated_message="application.modelo.errors.external_import_source_lexical_blank",
                context={"casilla_id": casilla_id},
            )
        try:
            decimal_value = Decimal(
                normalize_decimal_separators(
                    lexical,
                    strip_thousands="." in lexical and "," in lexical,
                ),
            )
        except (InvalidOperation, ValueError) as exc:
            raise ExternalModeloImportError(
                translated_message="application.modelo.errors.external_import_source_lexical_non_numeric",
                context={"casilla_id": casilla_id},
            ) from exc
        lexical_values[casilla_id] = raw_lexical
        decimal_values[casilla_id] = decimal_value
    return lexical_values, decimal_values


def _validate_external_source_registry_values(
    *,
    snapshot: RegistrySnapshot,
    canonical_values: Mapping[CasillaId, Decimal],
    lexical_values: Mapping[CasillaId, str],
) -> None:
    """Require source values to cover every required numeric registry casilla."""
    _validated_source_lexicals(
        canonical_values=canonical_values,
        source_lexicals=lexical_values,
    )
    required_numeric_ids = {
        casilla.id
        for casilla in snapshot.revision.casillas
        if casilla.required and casilla.data_type in {"decimal", "money", "integer", "ratio", "boolean"}
    }
    missing_required = required_numeric_ids.difference(canonical_values)
    if missing_required:
        raise ExternalModeloImportError(
            translated_message="application.modelo.errors.external_import_source_incomplete",
            context={"missing_casilla_ids": ",".join(sorted(missing_required))},
        )


def _validate_external_source_requirements(
    *,
    source: ExternalFilingBaselineSource,
    bucket_id: str,
    filing_instance_evidence: FilingInstanceEvidence | None,
    actor: str,
    justificante_repository: JustificanteRepositoryProtocol | None,
) -> JustificanteRepositoryProtocol:
    """Validate actor/evidence requirements and return the receipt repository."""
    if source.modelo == Modelo("303").value and filing_instance_evidence is None:
        raise ExternalModeloImportError(
            translated_message="application.modelo.errors.external_import_m303_filing_evidence_required",
        )
    if not actor.strip():
        raise ExternalModeloImportError(
            translated_message="application.modelo.errors.external_import_source_actor_blank",
        )
    resolved_justificante_repository = justificante_repository or resolve_justificante_repository(bucket_id=bucket_id)
    require_bound_justificante_artifact(
        evidence_kind=source.evidence_kind,
        evidence_reference_id=source.evidence_reference_id.strip(),
        modelo=source.modelo,
        filing_year=source.filing_year,
        period=source.period,
        expected_tax_id=source.tax_id,
        justificante_repository=resolved_justificante_repository,
    )
    return resolved_justificante_repository


def _select_external_source_work_unit(
    target: ExternalFilingTarget,
    *,
    catalogue: WorkUnitCatalogue,
    bucket_id: str,
) -> ModeloWorkResolution:
    """Translate target-selection conflicts into import-domain refusals."""
    try:
        return _select_active_external_import_work_unit(
            target,
            catalogue=catalogue,
            bucket_id=bucket_id,
        )
    except ModeloWorkVisibleTargetAmbiguousError as exc:
        raise ExternalModeloImportError(
            translated_message="application.modelo.errors.external_import_source_work_unit_ambiguous",
        ) from exc
    except ModeloWorkRevisionConflictError as exc:
        raise ExternalModeloImportError(
            translated_message="application.modelo.errors.external_import_source_revision_mismatch",
        ) from exc


def _create_external_source_work_unit(
    target: ExternalFilingTarget,
    *,
    bucket_id: str,
    actor: str,
    ports: WorkLifecyclePorts,
    operation: PinnedAuthorityOperation,
    clock: datetime | None,
) -> WorkUnit:
    """Create a source import target using the law-selected registry revision."""
    revision_id = law_selected_revision_for_work_target(
        modelo=target.modelo,
        filing_year=target.filing_year,
        period=target.period,
        requested_revision_id=target.registry_revision_id,
        operation=operation,
    )
    return create_work_unit(
        bucket_id=bucket_id,
        modelo=target.modelo,
        filing_year=target.filing_year,
        period=target.period,
        revision_id=revision_id,
        actor=actor,
        ports=ports,
        operation=operation,
        clock=clock,
    )


def resolve_external_filing_work_unit(
    target: ExternalFilingTarget,
    *,
    bucket_id: str,
    actor: str,
    ports: WorkLifecyclePorts,
    operation: PinnedAuthorityOperation,
    clock: datetime | None,
) -> WorkUnit:
    """Resolve the active work unit for ``target``, creating one when it is absent."""
    resolution = _select_external_source_work_unit(
        target, catalogue=ports.work_unit_repository.load(), bucket_id=bucket_id
    )
    if resolution.work_unit is not None:
        return resolution.work_unit
    return _create_external_source_work_unit(
        target,
        bucket_id=bucket_id,
        actor=actor,
        ports=ports,
        operation=operation,
        clock=clock,
    )


def import_external_filing_source(
    source: ExternalFilingBaselineSource,
    *,
    bucket_id: str,
    work_lifecycle_ports: WorkLifecyclePorts,
    operation: PinnedAuthorityOperation,
    filing_instance_evidence: FilingInstanceEvidence | None = None,
    actor: str = "aeat-import",
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol | None = None,
    justificante_repository: JustificanteRepositoryProtocol | None = None,
    observation_repository: CalculationObservationRepositoryProtocol,
    clock: datetime | None = None,
) -> ExternalFilingImportResult:
    """Resolve or create the target work unit and reconcile an amendable baseline.

    Source lexical tokens are retained verbatim on the revision input snapshot;
    their independently parsed Decimal values feed the filing baseline.
    """
    _validate_external_source_shape(source)
    lexical_values, decimal_values = _parse_external_source_values(source)
    snapshot, canonical_values = _reject_unknown_import_casillas(
        modelo=source.modelo,
        filing_year=source.filing_year,
        period=source.period,
        casilla_values=decimal_values,
    )
    _validate_external_source_registry_values(
        snapshot=snapshot,
        canonical_values=canonical_values,
        lexical_values=lexical_values,
    )
    resolved_justificante_repository = _validate_external_source_requirements(
        source=source,
        bucket_id=bucket_id,
        filing_instance_evidence=filing_instance_evidence,
        actor=actor,
        justificante_repository=justificante_repository,
    )

    wu_repo = work_lifecycle_ports.work_unit_repository
    work_unit = resolve_external_filing_work_unit(
        ExternalFilingTarget(
            modelo=source.modelo,
            filing_year=source.filing_year,
            period=source.period,
            registry_revision_id=source.registry_revision_id,
        ),
        bucket_id=bucket_id,
        actor=actor,
        ports=work_lifecycle_ports,
        operation=operation,
        clock=clock,
    )
    return import_external_filing_evidence(
        work_unit_id=work_unit.work_unit_id,
        casilla_values=decimal_values,
        source_lexical_values_by_casilla_id=lexical_values,
        evidence_kind=source.evidence_kind,
        evidence_reference_id=source.evidence_reference_id,
        actor=actor,
        work_unit_repository=wu_repo,
        calculation_repository=calculation_repository,
        filing_repository=filing_repository,
        bucket_event_repository=work_lifecycle_ports.bucket_event_repository,
        justificante_repository=resolved_justificante_repository,
        observation_repository=observation_repository,
        expected_tax_id=source.tax_id,
        clock=clock,
        operation=operation,
    )


def _load_external_import_target[CasillaKey](
    *,
    work_unit_id: str,
    casilla_values: Mapping[CasillaKey, Decimal],
    evidence_reference_id: str,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol,
):
    cleaned_reference = _validated_external_reference(casilla_values, evidence_reference_id)

    work_units = work_unit_repository.load()
    work_unit = require_active_work_unit(
        work_units,
        work_unit_id=work_unit_id,
        repository_bucket_id=work_unit_repository.bucket_id,
        use=ActiveWorkUnitUse.IMPORT,
    )
    snapshot, canonical_values = _reject_unknown_import_casillas(
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        casilla_values=casilla_values,
    )
    return work_units, work_unit, snapshot, canonical_values, cleaned_reference


def _validated_source_lexicals[CasillaKey](
    *,
    canonical_values: Mapping[CasillaId, Decimal],
    source_lexicals: Mapping[CasillaKey, str] | None,
) -> dict[CasillaId, str]:
    if source_lexicals is None:
        return {}
    canonical_lexicals = {
        validated_casilla_id(raw_id, surface="external filing source"): value
        for raw_id, value in source_lexicals.items()
    }
    if canonical_lexicals.keys() != canonical_values.keys():
        raise ExternalModeloImportError(
            translated_message="application.modelo.errors.external_import_source_casilla_mismatch",
        )
    validated: dict[CasillaId, str] = {}
    for casilla_id, raw_value in canonical_lexicals.items():
        lexical = raw_value.strip()
        try:
            parsed = Decimal(
                normalize_decimal_separators(
                    lexical,
                    strip_thousands="." in lexical and "," in lexical,
                ),
            )
        except (InvalidOperation, ValueError) as exc:
            raise ExternalModeloImportError(
                translated_message="application.modelo.errors.external_import_source_lexical_non_numeric",
                context={"casilla_id": casilla_id},
            ) from exc
        if not lexical or parsed != canonical_values[casilla_id]:
            raise ExternalModeloImportError(
                translated_message="application.modelo.errors.external_import_source_lexical_value_mismatch",
                context={"casilla_id": casilla_id},
            )
        validated[casilla_id] = raw_value
    return validated


def _validate_external_import_evidence_requirements(
    *,
    work_unit: WorkUnit,
    evidence_kind: ExternalEvidenceKind,
    filing_instance_evidence: FilingInstanceEvidence | None,
    cleaned_reference: str,
    expected_tax_id: str | None,
    justificante_repository: JustificanteRepositoryProtocol | None,
) -> None:
    """Enforce filing-instance and receipt-bound evidence requirements."""
    if work_unit.modelo == Modelo("303").value and filing_instance_evidence is None:
        raise ExternalModeloImportError(
            translated_message="application.modelo.errors.external_import_m303_filing_evidence_required",
            context={"work_unit_id": work_unit.work_unit_id},
        )
    resolved_justificante_repository = justificante_repository or resolve_justificante_repository(
        bucket_id=work_unit.bucket_id,
    )
    require_bound_justificante_artifact(
        evidence_kind=evidence_kind,
        evidence_reference_id=cleaned_reference,
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        expected_tax_id=expected_tax_id,
        justificante_repository=resolved_justificante_repository,
    )


def _prepare_external_import_values[CasillaKey](
    *,
    canonical_values: Mapping[CasillaId, Decimal],
    source_lexical_values_by_casilla_id: Mapping[CasillaKey, str] | None,
    snapshot: RegistrySnapshot,
) -> tuple[dict[CasillaId, str], dict[CasillaId, Decimal], tuple[CasillaObservation, ...]]:
    """Validate source lexicals and project canonical values into observations."""
    input_values_by_casilla_id = _validated_source_lexicals(
        canonical_values=canonical_values,
        source_lexicals=source_lexical_values_by_casilla_id,
    )
    outputs = dict(canonical_values)
    observations = _external_filing_observations(casilla_values=outputs, snapshot=snapshot)
    return input_values_by_casilla_id, outputs, observations


def _prepare_external_import_revision(
    *,
    repository: CalculationRevisionCatalogueRepositoryProtocol,
    work_unit_id: str,
    registry_snapshot_ref: RegistrySnapshotRef,
    input_values_by_casilla_id: dict[CasillaId, str],
    outputs: dict[CasillaId, Decimal],
    observations: tuple[CasillaObservation, ...],
    filing_instance_evidence: FilingInstanceEvidence | None,
    actor: str,
    now: datetime,
) -> tuple[CalculationRevisionCatalogue, str, CalculationRevision]:
    """Build and insert the guarded presented revision for one external import."""
    binding_overrides: dict[BindingId, str] = {}
    relation_overrides: dict[RelationId, str] = {}
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id=input_values_by_casilla_id,
        binding_overrides=binding_overrides,
        relation_overrides=relation_overrides,
        casilla_values=outputs,
        filing_instance_evidence=filing_instance_evidence,
        m303_regimen_simplificado_annual_summary_handoff=None,
        source_provenance=(),
    )
    revisions, revisions_revision_id = repository.load_revisioned()
    if revision_id in revisions:
        raise ExternalModeloImportError(
            translated_message="application.modelo.errors.external_import_duplicate_revision",
            context={"calculation_revision_id": revision_id},
        )
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        registry_snapshot_ref=registry_snapshot_ref,
        state=CalculationRevisionState.PRESENTADO,
        input_values_by_casilla_id=input_values_by_casilla_id,
        binding_overrides=binding_overrides,
        relation_overrides=relation_overrides,
        casilla_values=outputs,
        created_at=now,
        updated_at=now,
        verified_at=now,
        verified_by=actor.strip(),
        filed_at=now,
        filed_by=actor.strip(),
        observations=observations,
        filing_instance_evidence=filing_instance_evidence,
        m303_regimen_simplificado_annual_summary_handoff=None,
        source_provenance=(),
    )
    return upsert_calculation_revision(revisions, revision), revisions_revision_id, revision


def advance_external_filing_work_unit(
    catalogue: WorkUnitCatalogue,
    *,
    work_unit: WorkUnit,
    revision_id: CalculationRevisionId,
    filing_record_id: str,
    now: datetime,
) -> WorkUnitCatalogue:
    """Point one work unit at the co-committed external filing and its revision."""
    return upsert_work_unit(
        catalogue,
        work_unit.model_copy(
            update={
                "current_calculation_revision_id": revision_id,
                "filed_calculation_revision_id": revision_id,
                "current_filing_record_id": filing_record_id,
                "updated_at": now,
            },
        ),
    )


def build_external_filing_observation_payload(
    *,
    evidence_kind: ExternalEvidenceKind,
    observation_repository: CalculationObservationRepositoryProtocol,
    work_unit: WorkUnit,
    revision: CalculationRevision,
    occurred_at: datetime,
    cleaned_reference: str,
    expected_tax_id: str | None,
    filing_record_id: str,
    source_headers: tuple[ObservedHeaderFact, ...],
) -> ObservationEnvelopePayload | None:
    """Build the CSV observation envelope when that evidence channel applies."""
    if evidence_kind is not ExternalEvidenceKind.AEAT_CSV_REGISTER:
        return None
    return observation_repository.prepare_observation_envelope(
        RegistryModeloObservation(
            modelo=work_unit.modelo,
            filing_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
            observations=revision.observations,
        ),
        source_kind=ObservationSourceKind.AEAT_CSV_REGISTER,
        source_headers=source_headers,
        captured_at=occurred_at,
        stamped_revision_id=work_unit.revision_id,
        source_metadata={
            "aeat_register_status": "ALTA",
            "aeat_expediente_id": cleaned_reference,
            "authenticated_identity": (expected_tax_id or "").strip(),
            "external_evidence_reference_id": cleaned_reference,
            "filing_record_id": filing_record_id,
        },
    )


@dataclass(frozen=True, slots=True)
class ExternalFilingImportResult:
    """The chain entry an external filing import left in force, and the decision that placed it."""

    filing_record: ModeloRecord
    reconciliation: FilingReconciliationResult


def import_external_filing_evidence[CasillaKey](
    *,
    work_unit_id: str,
    casilla_values: Mapping[CasillaKey, Decimal],
    source_lexical_values_by_casilla_id: Mapping[CasillaKey, str] | None = None,
    evidence_kind: ExternalEvidenceKind,
    evidence_reference_id: str,
    filing_instance_evidence: FilingInstanceEvidence | None = None,
    declared_kind: FilingDeclarationKind | None = None,
    actor: str = "aeat-import",
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None = None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    justificante_repository: JustificanteRepositoryProtocol | None = None,
    observation_repository: CalculationObservationRepositoryProtocol,
    expected_tax_id: str | None = None,
    clock: datetime | None = None,
    source_headers: tuple[ObservedHeaderFact, ...] = (),
    operation: PinnedAuthorityOperation | None = None,
) -> ExternalFilingImportResult:
    """Reconcile an externally filed return with its period's filing chain.

    The target :class:`WorkUnit` supplies the bucket, modelo, filing year,
    period, and registry revision used to validate imported casillas.
    Justificante-bound evidence requires stored receipt metadata matching that
    target; CSV-register evidence binds the imported file itself to the target,
    and ``source_headers`` carries the register's typed header facts, such as
    the Modelo 303 declaration type its carry ingress requires.

    The values go through
    :func:`~cadrumo.application.modelo.filing_chain_reconciliation.reconcile_aeat_register_entry`:
    a matching pending local filing is confirmed, a disagreeing one is
    superseded by the imported content, and otherwise the imported content is
    appended in force. ``declared_kind`` is the declaration kind AEAT states;
    importing after a confirmed declaration requires it.

    Returns:
        The in-force :class:`ModeloRecord` and the reconciliation result.

    Raises:
        ExternalModeloImportError: The evidence cannot be bound to the work
            unit, or the import cannot be reconciled with the chain.
    """
    if operation is None:
        with bundled_indexed_authority().operation() as indexed_operation:
            return import_external_filing_evidence(
                work_unit_id=work_unit_id,
                casilla_values=casilla_values,
                source_lexical_values_by_casilla_id=source_lexical_values_by_casilla_id,
                evidence_kind=evidence_kind,
                evidence_reference_id=evidence_reference_id,
                filing_instance_evidence=filing_instance_evidence,
                declared_kind=declared_kind,
                actor=actor,
                work_unit_repository=work_unit_repository,
                calculation_repository=calculation_repository,
                filing_repository=filing_repository,
                bucket_event_repository=bucket_event_repository,
                justificante_repository=justificante_repository,
                observation_repository=observation_repository,
                expected_tax_id=expected_tax_id,
                clock=clock,
                source_headers=source_headers,
                operation=indexed_operation,
            )
    from .filing_chain_reconciliation import (
        AeatRegisterEntry,
        FilingReconciliationOutcome,
        FilingReconciliationPorts,
        reconcile_aeat_register_entry,
    )

    wu_repo = work_unit_repository
    if wu_repo is None:
        wu_repo = work_unit_catalogue_repository(bucket_id=require_active_profile_bucket_id())
    _work_units, work_unit, _snapshot, canonical_values, cleaned_reference = _load_external_import_target(
        work_unit_id=work_unit_id,
        casilla_values=casilla_values,
        evidence_reference_id=evidence_reference_id,
        work_unit_repository=wu_repo,
    )
    jr_repo = justificante_repository or resolve_justificante_repository(bucket_id=work_unit.bucket_id)
    _validate_external_import_evidence_requirements(
        work_unit=work_unit,
        evidence_kind=evidence_kind,
        filing_instance_evidence=filing_instance_evidence,
        cleaned_reference=cleaned_reference,
        expected_tax_id=expected_tax_id,
        justificante_repository=jr_repo,
    )
    lexicals = _validated_source_lexicals(
        canonical_values=canonical_values,
        source_lexicals=source_lexical_values_by_casilla_id,
    )
    receipt = jr_repo.load(cleaned_reference) if is_receipt_bound_external_evidence(evidence_kind) else None
    fr_repo = filing_repository or modelo_record_catalogue_repository(bucket_id=work_unit.bucket_id)
    ports = FilingReconciliationPorts(
        filing_repository=fr_repo,
        calculation_repository=(
            calculation_repository or calculation_revision_catalogue_repository(bucket_id=work_unit.bucket_id)
        ),
        work_lifecycle=WorkLifecyclePorts(
            work_unit_repository=wu_repo,
            bucket_event_repository=bucket_event_repository or default_profile_bucket_event_history_repository(),
        ),
        observation_repository=observation_repository,
        justificante_repository=jr_repo,
    )
    result = reconcile_aeat_register_entry(
        AeatRegisterEntry(
            bucket_id=work_unit.bucket_id,
            modelo=str(work_unit.modelo),
            filing_year=work_unit.filing_year,
            period=work_unit.period,
            register=AeatRegisterRef(
                expediente_id=cleaned_reference,
                csv=receipt.csv if receipt is not None else None,
                justificante_number=receipt.presentation_id if receipt is not None else None,
            ),
            evidence_kind=evidence_kind,
            tax_id=(expected_tax_id or "").strip(),
            declared_kind=declared_kind,
            justificante=receipt,
            casilla_values=canonical_values,
            source_lexicals=lexicals or None,
            filing_instance_evidence=filing_instance_evidence,
            source_headers=source_headers,
            target_work_unit_id=work_unit.work_unit_id,
        ),
        ports=ports,
        operation=operation,
        actor=actor,
        clock=clock or _utc_now(),
    )
    record = fr_repo.load().get(result.filing_record_id) if result.filing_record_id is not None else None
    if result.outcome is FilingReconciliationOutcome.UNVERIFIABLE or record is None:
        raise ExternalModeloImportError(
            translated_message="application.modelo.errors.external_import_unverifiable",
            context={
                "work_unit_id": work_unit.work_unit_id,
                "notices": ",".join(notice.code.value for notice in result.notices),
            },
        )
    return ExternalFilingImportResult(filing_record=record, reconciliation=result)


def prepare_external_filing_revision[CasillaKey](
    *,
    work_unit_id: str,
    casilla_values: Mapping[CasillaKey, Decimal],
    source_lexical_values_by_casilla_id: Mapping[CasillaKey, str] | None,
    evidence_kind: ExternalEvidenceKind,
    evidence_reference_id: str,
    filing_instance_evidence: FilingInstanceEvidence | None,
    expected_tax_id: str | None,
    actor: str,
    now: datetime,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
    justificante_repository: JustificanteRepositoryProtocol | None,
) -> ExternalFilingRevisionDraft:
    """Validate external filing content and stage its presented revision in memory.

    Refuses undeclared casillas, missing filing-instance evidence and unbound
    receipt evidence, then inserts a ``PRESENTADO`` revision into a
    revision-guarded copy of the catalogue. Nothing is written: the caller
    co-commits the returned catalogues with its own filing transition.
    """
    work_units, work_unit, snapshot, canonical_values, cleaned_reference = _load_external_import_target(
        work_unit_id=work_unit_id,
        casilla_values=casilla_values,
        evidence_reference_id=evidence_reference_id,
        work_unit_repository=work_unit_repository,
    )
    _validate_external_import_evidence_requirements(
        work_unit=work_unit,
        evidence_kind=evidence_kind,
        filing_instance_evidence=filing_instance_evidence,
        cleaned_reference=cleaned_reference,
        expected_tax_id=expected_tax_id,
        justificante_repository=justificante_repository,
    )
    input_values_by_casilla_id, outputs, observations = _prepare_external_import_values(
        canonical_values=canonical_values,
        source_lexical_values_by_casilla_id=source_lexical_values_by_casilla_id,
        snapshot=snapshot,
    )
    # Revisioned: the catalogue is composed into the caller's co-commit, so an
    # unguarded read would write the whole singleton row back over a
    # concurrent writer's entry.
    revisions, revisions_revision_id, revision = _prepare_external_import_revision(
        repository=calculation_repository,
        work_unit_id=work_unit_id,
        registry_snapshot_ref=snapshot.snapshot_ref,
        input_values_by_casilla_id=input_values_by_casilla_id,
        outputs=outputs,
        observations=observations,
        filing_instance_evidence=filing_instance_evidence,
        actor=actor,
        now=now,
    )
    return ExternalFilingRevisionDraft(
        work_units=work_units,
        work_unit=work_unit,
        revisions=revisions,
        revisions_revision_id=revisions_revision_id,
        revision=revision,
        evidence_reference_id=cleaned_reference,
        snapshot=snapshot,
        canonical_values=canonical_values,
    )


def build_external_filing_record(
    *,
    filing_record_id: str,
    work_unit: WorkUnit,
    calculation_revision_id: CalculationRevisionId,
    filed_at: datetime,
    filed_by: str,
    evidence_kind: ExternalEvidenceKind,
    evidence_reference_id: str,
    declaration_kind: FilingDeclarationKind,
    member_nif: str | None = None,
    amends_filing_record_id: str | None = None,
    aeat_register: AeatRegisterRef | None = None,
) -> ModeloRecord:
    """Build the in-force, AEAT-origin chain entry for externally presented content."""
    return ModeloRecord(
        filing_record_id=filing_record_id,
        work_unit_id=work_unit.work_unit_id,
        calculation_revision_id=calculation_revision_id,
        bucket_id=work_unit.bucket_id,
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        member_nif=member_nif,
        filed_at=filed_at,
        filed_by=filed_by,
        notes=None,
        origin=FilingOrigin.AEAT,
        confirmation=AeatConfirmationState.CONFIRMADA,
        declaration_kind=declaration_kind,
        aeat_register=aeat_register,
        amends_filing_record_id=amends_filing_record_id,
        status=ModeloRecordStatus.VIGENTE,
        external_evidence=ExternalEvidence(
            kind=evidence_kind,
            reference_id=evidence_reference_id,
            imported_at=filed_at,
        ),
    )


def _validated_external_reference[CasillaKey](
    casilla_values: Mapping[CasillaKey, Decimal],
    evidence_reference_id: str,
) -> str:
    """Return a stripped evidence reference after basic import-shape checks."""
    if not casilla_values:
        raise ExternalModeloImportError(
            translated_message="application.modelo.errors.external_filing_no_casilla_values",
        )
    cleaned_reference = evidence_reference_id.strip()
    if not cleaned_reference:
        raise ExternalModeloImportError(
            translated_message="application.modelo.errors.external_filing_evidence_reference_blank",
        )
    return cleaned_reference


def require_bound_justificante_artifact(
    *,
    evidence_kind: ExternalEvidenceKind,
    evidence_reference_id: str,
    modelo: str,
    filing_year: int,
    period: Period,
    expected_tax_id: str | None,
    justificante_repository: JustificanteRepositoryProtocol,
) -> None:
    """Require matching stored :class:`Justificante` metadata.

    Justificante-PDF and live-capture imports are treated as receipt-bound
    baselines: the evidence reference must resolve to stored
    justificante metadata for the same taxpayer, modelo, filing year, and
    period. The taxpayer comparison is case-insensitive after stripping.
    """
    if not is_receipt_bound_external_evidence(evidence_kind):
        return
    cleaned_expected_tax_id = (expected_tax_id or "").strip()
    if not cleaned_expected_tax_id:
        raise ExternalModeloImportError(
            translated_message="application.modelo.errors.external_import_tax_id_missing",
            context={
                "evidence_reference_id": evidence_reference_id,
                "evidence_kind": evidence_kind.value,
            },
        )
    justificante = justificante_repository.load(evidence_reference_id)
    if justificante is None:
        raise ExternalModeloImportError(
            translated_message="application.modelo.errors.external_import_justificante_missing",
            context={
                "evidence_reference_id": evidence_reference_id,
                "evidence_kind": evidence_kind.value,
            },
        )
    if not _justificante_matches_import_target(
        justificante,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        expected_tax_id=cleaned_expected_tax_id,
    ):
        raise ExternalModeloImportError(
            translated_message="application.modelo.errors.external_import_justificante_mismatch",
            context={
                "evidence_reference_id": evidence_reference_id,
                "modelo": modelo,
                "filing_year": str(filing_year),
                "period": period.registry_token,
            },
        )


def _justificante_matches_import_target(
    justificante: Justificante,
    *,
    modelo: str,
    filing_year: int,
    period: Period,
    expected_tax_id: str,
) -> bool:
    """Return whether ``justificante`` matches the external-import target axis."""
    return justificante.matches_filing_target(
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        tax_id=expected_tax_id,
    )
