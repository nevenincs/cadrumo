"""Repository mutation helpers for modelo calculation and filing transitions.

The calculate path stores draft :class:`CalculationRevision` rows with their
provenance-bearing :class:`CasillaObservation` entries, advances the parent
:class:`WorkUnit` pointer, and emits ``modelo.calculation.created`` through the
:class:`BucketEventHistoryRepository` catalogue. The event is a lightweight join
record; full legal/source provenance remains on the persisted calculation
revision's observations, with ``has_provenance`` signalling that the join is
grounded.

The filing path runs here only after its caller has passed readiness, workflow,
and clean-state gates. It records the local/internal filing transition: create a
current :class:`ModeloRecord`, supersede any prior current filing for the work
target, move calculation revisions into ``PRESENTADO`` states, and co-emit
the :class:`~domain.modelos.TransactionRevisionParticipationIndex` writes,
cross-period observation projections, and Modelo 303 settlement prorrata
register writeback. It never submits to AEAT and never turns the non-official
``app_filing`` carry projection into filing-grade external evidence.

See Also:
    :func:`~application.modelo.file_modelo_revision`:
        Orchestrates preconditions and result-disposition resolution before
        delegating successful mutations here.
    :func:`~application.modelo.import_external_filing_evidence`:
        Separate import boundary that creates current records with
        :class:`~domain.modelos.ExternalEvidence`; this persistence helper
        deliberately creates local records without that payload.
    :func:`~application.modelo._filed_revision_observation.persist_filed_revision_observation`:
        Projects filed casilla observations into non-official cross-period
        carry evidence.
    :class:`~adapters.persistence.profile.prorrata_register.ProrrataRegisterRepository`:
        Profile-scoped encrypted repository co-emitted for Modelo 303
        settlement prorrata writeback.
    :class:`~domain.prorrata_register.ProrrataRegisterEntry`:
        Typed row updated with definitive percentage and annual volume inputs.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from ...adapters.persistence.profile.participation_index import TransactionParticipationIndexRepository
from ...adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
from ...core import (
    CasillaId,
    M210GrossIncomeSourceMode,
    Modelo,
    ProrrataRegisterRegime,
    ResultDisposition,
    validated_casilla_id,
)
from ...core.hashing import sha256_hex
from ...domain.buckets import (
    BucketEvent,
    BucketEventHistoryRepositoryProtocol,
    BucketEventObjectType,
    BucketEventType,
    bucket_event_history_write,
)
from ...domain.buckets import build_bucket_event as _build_domain_bucket_event
from ...domain.buckets import emit_bucket_event as _emit_domain_bucket_event
from ...domain.calculations import (
    DirectRowMaterializationProvenance,
    RowBindingKey,
    RowCasillaKey,
    RowSourceIdentity,
)
from ...domain.calculations.registry.bindings import CasillaObservation
from ...domain.calculations.registry.formula_runtime import RegistryCalculationUnresolvedOutcome
from ...domain.calculations.registry.ids import (
    BindingId,
    RelationId,
)
from ...domain.iva import is_m303_annual_settlement_period
from ...domain.modelos import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionCatalogueRepositoryProtocol,
    CalculationRevisionState,
    CalculationSourceIssue,
    CalculationSourceRef,
    FilingInstanceEvidence,
    LedgerFilingSnapshot,
    M303RegimenSimplificadoAnnualSummaryHandoff,
    ModeloDetailRow,
    ModeloRecord,
    ModeloRecordCatalogue,
    ModeloRecordCatalogueRepositoryProtocol,
    ModeloRecordStatus,
    TransactionRevisionParticipation,
    WorkUnit,
    WorkUnitCatalogue,
    derive_calculation_revision_id,
    derive_filing_record_id,
    upsert_calculation_revision,
    upsert_filing_record,
    upsert_transaction_participation,
    upsert_work_unit,
)
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ...domain.prorrata_register import (
    ProrrataRegister,
    ProrrataRegisterEntry,
    ProrrataRegisterRepositoryProtocol,
)
from ..calculations import CalculationObservationRepository, PriorDomiciliationElectionProjection
from ..filing import try_record_filing_retention_snapshot
from ._action_errors import M303FilingEvidenceError
from ._filed_revision_observation import persist_filed_revision_observation, require_filing_result_disposition
from ._m303_filing_evidence import m303_filing_evidence_failure

if TYPE_CHECKING:  # pragma: no cover - typing-only storage boundary import
    from ...adapters.persistence.storage import SecureObjectWrite

_BUCKET_EVENT_PAYLOAD_VERSION = 2
"""Schema version for the bucket-event payload dict emitted by modelo actions."""

_PRORRATA_VOLUMEN_TOTAL_CASILLA = validated_casilla_id(
    "iva.prorrata-volumen-total",
    surface="prorrata settlement volumen total casilla id",
)
_PRORRATA_VOLUMEN_CON_DERECHO_CASILLA = validated_casilla_id(
    "iva.prorrata-volumen-con-derecho",
    surface="prorrata settlement volumen con derecho casilla id",
)
_PRORRATA_PORCENTAJE_CASILLA = validated_casilla_id(
    "iva.prorrata-porcentaje",
    surface="prorrata settlement definitive percentage casilla id",
)


def emit_modelo_bucket_event(
    *,
    repository: BucketEventHistoryRepositoryProtocol,
    bucket_id: str,
    event_type: BucketEventType,
    occurred_at: datetime,
    actor: str,
    object_type: BucketEventObjectType,
    object_id: str,
    payload: Mapping[str, str],
) -> BucketEvent:
    """Emit one :class:`BucketEvent` under the modelo payload contract.

    Modelo's narrow wrapper over :func:`~domain.buckets.emit_bucket_event`: it
    supplies :data:`_BUCKET_EVENT_PAYLOAD_VERSION` so no modelo call site restates
    it, and adds nothing else. The shared derive-append-save sequence lives in the
    domain beside :func:`append_bucket_event`, because it composes only bucket
    domain types and every emitting domain needs it — keeping it here made this
    module a hub that peer application packages had to reach up into.

    The returned event is the durable bucket-scoped audit pointer for the modelo
    mutation. Payloads stay compact and reference the owning calculation revision,
    filing record, or work unit instead of duplicating their catalogued state.
    """
    return _emit_domain_bucket_event(
        repository=repository,
        bucket_id=bucket_id,
        event_type=event_type,
        occurred_at=occurred_at,
        actor=actor,
        object_type=object_type,
        object_id=object_id,
        payload=payload,
        payload_version=_BUCKET_EVENT_PAYLOAD_VERSION,
    )


def build_modelo_bucket_event(
    *,
    bucket_id: str,
    event_type: BucketEventType,
    occurred_at: datetime,
    actor: str,
    object_type: BucketEventObjectType,
    object_id: str,
    payload: Mapping[str, str],
) -> BucketEvent:
    """Derive one modelo :class:`BucketEvent` without persisting it.

    The non-saving counterpart of :func:`emit_modelo_bucket_event`, supplying the
    same :data:`_BUCKET_EVENT_PAYLOAD_VERSION` so a co-committed event cannot
    declare a different payload contract than an emitted one. Pair it with
    :func:`domain.buckets.bucket_event_history_write` to commit the event in the same unit of
    work as the catalogues it records.
    """
    return _build_domain_bucket_event(
        bucket_id=bucket_id,
        event_type=event_type,
        occurred_at=occurred_at,
        actor=actor,
        object_type=object_type,
        object_id=object_id,
        payload=payload,
        payload_version=_BUCKET_EVENT_PAYLOAD_VERSION,
    )


def _source_provenance_trace_sha256(source_provenance: tuple[CalculationSourceRef, ...]) -> str:
    """Deterministic digest of the persisted source-mesh provenance trace.

    Emitted on the ``modelo.calculation.created`` bucket event so an audit reader
    can detect a source-connectivity change without decrypting the calculation
    revision. The digest folds each provenance row's stable
    complete resolver, ownership, lineage, reference, and fingerprint identity in a sort-canonical
    order so the value is order-independent, mirroring the existing
    ``borrador_bindings_trace_sha256`` join-record pattern. An empty provenance
    tuple yields the digest of the empty string.
    """
    lines = sorted(
        f"{ref.resolver_id}\x1f{ref.resolved_binding_source.value}\x1f"
        f"{ref.contributor_source_kind}\x1f"
        f"{ref.contributor_binding_source.value if ref.contributor_binding_source is not None else ''}\x1f"
        f"{ref.lineage_role.value}\x1f{ref.source_ref}\x1f{ref.parent_source_ref or ''}\x1f"
        f"{ref.fingerprint or ''}"
        for ref in source_provenance
    )
    return sha256_hex("\n".join(lines).encode("utf-8"))


def persist_calculation_revision(
    *,
    work_unit_id: str,
    work_unit: WorkUnit,
    work_units: WorkUnitCatalogue,
    work_units_revision_id: str,
    input_values_by_casilla_id: dict[CasillaId, str],
    binding_overrides: dict[BindingId, str],
    row_binding_values: dict[BindingId, dict[str, str]],
    row_source_identities: Mapping[RowBindingKey, RowSourceIdentity],
    row_casilla_values: Mapping[RowCasillaKey, Decimal],
    row_casilla_provenance: Mapping[RowCasillaKey, DirectRowMaterializationProvenance],
    relation_overrides: dict[RelationId, str],
    casilla_values: dict[CasillaId, Decimal],
    source_transaction_ids: tuple[str, ...],
    borrador_snapshot_id: str | None,
    bindings_sourced_from_borrador: tuple[BindingId, ...],
    observations: tuple[CasillaObservation, ...],
    cleared_casilla_ids: tuple[CasillaId, ...] = (),
    unresolved_outcomes: tuple[RegistryCalculationUnresolvedOutcome, ...] = (),
    source_provenance: tuple[CalculationSourceRef, ...],
    source_issues: tuple[CalculationSourceIssue, ...] = (),
    filing_instance_evidence: FilingInstanceEvidence | None = None,
    m303_regimen_simplificado_annual_summary_handoff: M303RegimenSimplificadoAnnualSummaryHandoff | None = None,
    detail_rows: tuple[ModeloDetailRow, ...],
    formula_count: int,
    actor: str,
    now: datetime,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol,
    ledger_filing_snapshot: LedgerFilingSnapshot | None = None,
    m210_official_tipo_renta_code: str | None = None,
    m210_gross_income_source_mode: M210GrossIncomeSourceMode | None = None,
    additional_secure_object_writes_for_revision: (
        Callable[[str, str | None], tuple[SecureObjectWrite, ...]] | None
    ) = None,
) -> CalculationRevision:
    """Persist a freshly calculated draft revision and return the :class:`CalculationRevision`.

    Returns the existing duplicate when an identical revision is already persisted.
    The content-addressed revision id includes manual casilla inputs,
    binding/relation overrides, ledger source transactions, borrador provenance,
    detail rows, and calculated casilla values. The supplied
    :class:`CasillaObservation` rows carry the legal and source provenance
    persisted with a new calculation revision.

    The ``source_provenance`` tuple carries the resolver-level source-mesh trace
    (:class:`~domain.modelos.CalculationSourceRef` rows projected from the
    calculation source mesh) so the persisted revision records which resolver
    mesh and which upstream source objects produced it. The tuple is required at
    every call site (including an explicit empty decision) and participates in
    ``derive_calculation_revision_id`` through an order-canonical identity payload.

    ``ledger_filing_snapshot`` pins the ledger state the casilla values were
    computed FROM, for a ledger-derived draft. It is the anchor the verify-time
    drift gate compares against the live ledger, and it exists because the
    snapshot is otherwise captured only on a granted verify — leaving exactly
    the drafts that need guarding with nothing to compare. A granted verify
    overwrites it, alongside the evidence bundle, with the state it froze.

    The emitted :class:`BucketEvent` uses the revision id as ``object_id`` and
    includes a ``has_provenance`` payload flag plus a ``source_provenance_count``
    and an order-independent ``source_provenance_trace_sha256`` digest of the
    source-mesh trace. Audit readers can therefore use the event as a compact
    pointer back to the persisted :class:`CalculationRevision`, and detect a
    source-connectivity change from the digest without decrypting the revision,
    instead of treating bucket history as the standalone provenance store.

    The duplicate branch still advances or confirms the work-unit pointer under
    the SAME ``work_units_revision_id`` compare-and-swap guard the new-revision
    branch uses -- it never falls back to an unguarded pointer save, and it
    still invokes ``additional_secure_object_writes_for_revision`` when
    supplied, so a caller relying on a co-committed side effect (a guarded
    edit's result receipt, for instance) gets it on the duplicate path exactly
    as reliably as on the new-revision path.

    ``additional_secure_object_writes_for_revision`` lets a caller land its own
    atomic writes (an edit-contract mutation-result receipt, most notably) in
    the SAME secure-object transaction as the revision, pointer, and bucket
    event this function already commits, without this function knowing
    anything about the caller's payload shape. It is a FACTORY rather than a
    plain tuple because the content-addressed revision id (and, on the
    new-revision path only, the fresh bucket-event id) are not known until
    this function derives them -- a receipt needs the revision id, so the
    caller cannot build its write before calling in. The factory receives the
    resolved ``calculation_revision_id`` and the fresh bucket-event id, or
    ``None`` for the latter on the duplicate-result path where no new event is
    emitted, and returns the writes to co-commit. ``None`` by default, so
    every existing caller's write set is unchanged.
    """
    _require_filing_instance_evidence_for_work_unit(
        work_unit=work_unit,
        evidence=filing_instance_evidence,
        operation="calculation revision creation",
    )
    if any(item.materialization_rule_version != work_unit.revision_id for item in row_casilla_provenance.values()):
        raise ValueError("row casilla materialization rule version must equal the parent work-unit revision")
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id=input_values_by_casilla_id,
        binding_overrides=binding_overrides,
        row_binding_values=row_binding_values,
        row_source_identities=row_source_identities,
        row_casilla_values=row_casilla_values,
        row_casilla_provenance=row_casilla_provenance,
        relation_overrides=relation_overrides,
        casilla_values=casilla_values,
        source_transaction_ids=source_transaction_ids,
        m210_official_tipo_renta_code=m210_official_tipo_renta_code,
        m210_gross_income_source_mode=m210_gross_income_source_mode,
        borrador_snapshot_id=borrador_snapshot_id,
        bindings_sourced_from_borrador=bindings_sourced_from_borrador,
        detail_rows=detail_rows,
        source_issues=source_issues,
        source_provenance=source_provenance,
        filing_instance_evidence=filing_instance_evidence,
        m303_regimen_simplificado_annual_summary_handoff=m303_regimen_simplificado_annual_summary_handoff,
        cleared_casilla_ids=cleared_casilla_ids,
    )
    stamped_annual_summary_handoff = (
        m303_regimen_simplificado_annual_summary_handoff.stamped_for_target_calculation_revision(revision_id)
        if m303_regimen_simplificado_annual_summary_handoff is not None
        else None
    )
    # Revisioned: this catalogue is composed into a co-commit, so it cannot
    # use a self-committing mutation, and an unguarded read would write the
    # whole singleton row back over a revision another calculate run added.
    revisions, revisions_revision_id = calculation_repository.load_revisioned()
    existing = revisions.get(revision_id)
    if existing is not None:
        if (
            existing.state is CalculationRevisionState.BORRADOR
            and work_unit.current_calculation_revision_id != revision_id
        ):
            duplicate_work_units = upsert_work_unit(
                work_units,
                work_unit.model_copy(
                    update={
                        "current_calculation_revision_id": revision_id,
                        "updated_at": now,
                    },
                ),
            )
        else:
            duplicate_work_units = work_units
        duplicate_writes = (
            additional_secure_object_writes_for_revision(revision_id, None)
            if additional_secure_object_writes_for_revision is not None
            else ()
        )
        if duplicate_work_units is not work_units or duplicate_writes:
            # Guarded, never a bare `.save`: an unguarded write here would
            # silently discard a concurrent catalogue change this branch never
            # observed, and it is the one place a co-committed receipt write
            # could otherwise be dropped on the duplicate-result path.
            work_unit_repository.save_with_secure_object_writes(
                duplicate_work_units,
                duplicate_writes,
                expected_revision_id=work_units_revision_id,
            )
        return existing

    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id=input_values_by_casilla_id,
        binding_overrides=binding_overrides,
        row_binding_values=row_binding_values,
        row_source_identities=row_source_identities,
        row_casilla_values=row_casilla_values,
        row_casilla_provenance=row_casilla_provenance,
        relation_overrides=relation_overrides,
        source_transaction_ids=source_transaction_ids,
        m210_official_tipo_renta_code=m210_official_tipo_renta_code,
        m210_gross_income_source_mode=m210_gross_income_source_mode,
        borrador_snapshot_id=borrador_snapshot_id,
        bindings_sourced_from_borrador=bindings_sourced_from_borrador,
        cleared_casilla_ids=cleared_casilla_ids,
        casilla_values=casilla_values,
        observations=observations,
        unresolved_outcomes=unresolved_outcomes,
        source_provenance=source_provenance,
        source_issues=source_issues,
        detail_rows=detail_rows,
        ledger_filing_snapshot=ledger_filing_snapshot,
        filing_instance_evidence=filing_instance_evidence,
        m303_regimen_simplificado_annual_summary_handoff=stamped_annual_summary_handoff,
        created_at=now,
        updated_at=now,
    )
    advanced_work_units = upsert_work_unit(
        work_units,
        work_unit.model_copy(
            update={
                "current_calculation_revision_id": revision_id,
                "updated_at": now,
            },
        ),
    )
    created_event = build_modelo_bucket_event(
        bucket_id=work_unit.bucket_id,
        event_type=BucketEventType.MODELO_CALCULATION_CREATED,
        occurred_at=now,
        actor=actor,
        object_type=BucketEventObjectType.CALCULATION_REVISION,
        object_id=revision_id,
        payload={
            "calculation_revision_id": revision_id,
            "work_unit_id": work_unit_id,
            "modelo": work_unit.modelo,
            "filing_year": str(work_unit.filing_year),
            "period": work_unit.period.registry_token,
            "input_casilla_count": str(len(input_values_by_casilla_id)),
            "row_binding_count": str(sum(len(rows) for rows in row_binding_values.values())),
            "row_casilla_count": str(len(row_casilla_values)),
            "casilla_count": str(len(casilla_values)),
            "formula_count": str(formula_count),
            "source_transaction_count": str(len(source_transaction_ids)),
            "borrador_snapshot_id": borrador_snapshot_id or "",
            "borrador_participated": "true" if bindings_sourced_from_borrador else "false",
            "borrador_binding_count": str(len(bindings_sourced_from_borrador)),
            "borrador_bindings_trace_sha256": sha256_hex(
                "\n".join(bindings_sourced_from_borrador).encode("utf-8"),
            ),
            "has_provenance": "true" if observations else "false",
            "source_provenance_count": str(len(source_provenance)),
            "source_provenance_trace_sha256": _source_provenance_trace_sha256(source_provenance),
        },
    )
    # One unit of work: the draft revision, the advanced current-calculation
    # pointer, and MODELO_CALCULATION_CREATED. Emitted through a separate write,
    # an event-storage failure left the draft durable and pointed-at as current
    # while the history stayed unchanged, with no recovery marker or retry
    # contract naming the missing entry.
    calculation_repository.save_with_secure_object_writes(
        upsert_calculation_revision(revisions, revision),
        (
            work_unit_repository.to_secure_object_write(
                advanced_work_units,
                expected_revision_id=work_units_revision_id,
            ),
            bucket_event_history_write(bucket_event_repository, (created_event,)),
            *(
                additional_secure_object_writes_for_revision(revision_id, created_event.event_id)
                if additional_secure_object_writes_for_revision is not None
                else ()
            ),
        ),
        expected_revision_id=revisions_revision_id,
    )
    return revision


def require_filing_instance_evidence_for_work_unit(
    *,
    work_unit: WorkUnit,
    revision: CalculationRevision,
) -> FilingInstanceEvidence | None:
    """Return persisted evidence only when it is valid for the selected work unit."""
    return _require_filing_instance_evidence_for_work_unit(
        work_unit=work_unit,
        evidence=revision.filing_instance_evidence,
        operation="verification or export",
    )


def _require_filing_instance_evidence_for_work_unit(
    *,
    work_unit: WorkUnit,
    evidence: FilingInstanceEvidence | None,
    operation: str,
) -> FilingInstanceEvidence | None:
    """Validate the closed Modelo 303 evidence branch at creation or replay."""
    if work_unit.modelo == Modelo.M303.value:
        if evidence is None:
            raise M303FilingEvidenceError(
                precondition_failure=m303_filing_evidence_failure(
                    "missing",
                    {"modelo": str(work_unit.modelo), "evidence_present": False, "operation": operation},
                ),
            )
        if evidence.m303.period != work_unit.period:
            raise M303FilingEvidenceError(
                precondition_failure=m303_filing_evidence_failure(
                    "period_mismatch",
                    {
                        "work_unit_period": work_unit.period.registry_token,
                        "evidence_period": evidence.m303.period.registry_token,
                        "periods_match": False,
                    },
                ),
            )
        return evidence
    if evidence is not None:
        raise M303FilingEvidenceError(
            precondition_failure=m303_filing_evidence_failure(
                "unsupported_modelo",
                {"modelo": str(work_unit.modelo), "evidence_present": True},
            ),
        )
    return None


def _build_filed_participation_writes(
    *,
    filed_target: CalculationRevision,
    work_unit: WorkUnit,
    filing_record_id: str,
    participation_index_repository: TransactionParticipationIndexRepository,
) -> tuple[SecureObjectWrite, ...]:
    """Build the per-transaction participation writes for a filed revision.

    For each ``source_transaction_id`` of the filed revision, load that
    transaction's
    :class:`~domain.modelos.TransactionRevisionParticipationIndex`, upsert
    the ``PRESENTADO`` participation carrying the ``filing_record_id``
    (replacing the prior verified entry for the same revision in place), and
    return the resulting ``SecureObjectWrite`` so the caller co-emits them in
    the same atomic unit of work as the filing save.
    """
    writes: list[SecureObjectWrite] = []
    for transaction_id in filed_target.source_transaction_ids:
        index = participation_index_repository.load(transaction_id)
        participation = TransactionRevisionParticipation(
            calculation_revision_id=filed_target.calculation_revision_id,
            work_unit_id=work_unit.work_unit_id,
            modelo=work_unit.modelo,
            filing_year=work_unit.filing_year,
            period=work_unit.period,
            revision_state=CalculationRevisionState.PRESENTADO.value,
            filing_record_id=filing_record_id,
        )
        updated = upsert_transaction_participation(index, participation)
        writes.append(participation_index_repository.to_secure_object_write(updated))
    return tuple(writes)


def _participation_index_repository(
    repository: TransactionParticipationIndexRepository | None,
    *,
    bucket_id: str,
) -> TransactionParticipationIndexRepository:
    return repository or TransactionParticipationIndexRepository(bucket_id=bucket_id)


def _prorrata_register_repository(
    repository: ProrrataRegisterRepositoryProtocol | None,
    *,
    bucket_id: str,
) -> ProrrataRegisterRepositoryProtocol:
    return repository or ProrrataRegisterRepository(bucket_id=bucket_id)


def _build_prorrata_settlement_write(
    *,
    filed_target: CalculationRevision,
    work_unit: WorkUnit,
    prorrata_register_repository: ProrrataRegisterRepositoryProtocol,
) -> SecureObjectWrite | None:
    """Build the settlement prorrata-register write for an M303 year close."""
    values = _prorrata_settlement_values(filed_target=filed_target, work_unit=work_unit)
    if values is None:
        return None

    # Revisioned: the write this returns joins the caller's co-commit batch, so
    # it cannot self-commit, and an unguarded read would put the whole register
    # back over a sector entry another writer added in between.
    register, register_revision_id = prorrata_register_repository.load_revisioned()
    entry = _settled_prorrata_register_entry(
        work_unit=work_unit,
        register=register,
        volumen_total=values[0],
        volumen_con_derecho=values[1],
        definitive_percentage=values[2],
    )
    retained = tuple(
        existing
        for existing in register.entries
        if (existing.ejercicio, existing.sector_id) != (entry.ejercicio, entry.sector_id)
    )
    return prorrata_register_repository.to_secure_object_write(
        ProrrataRegister(
            entries=(*retained, entry),
            sector_definitions=register.sector_definitions,
            activity_rows=register.activity_rows,
        ),
        expected_revision_id=register_revision_id,
    )


def _prorrata_settlement_values(
    *,
    filed_target: CalculationRevision,
    work_unit: WorkUnit,
) -> tuple[Decimal, Decimal, Decimal] | None:
    if str(work_unit.modelo) != Modelo.M303.value:
        return None
    if not is_m303_annual_settlement_period(work_unit.period):
        return None

    casilla_values = filed_target.casilla_values
    volumen_total = casilla_values.get(_PRORRATA_VOLUMEN_TOTAL_CASILLA)
    volumen_con_derecho = casilla_values.get(_PRORRATA_VOLUMEN_CON_DERECHO_CASILLA)
    definitive_percentage = casilla_values.get(_PRORRATA_PORCENTAJE_CASILLA)
    if volumen_total is None or volumen_con_derecho is None or definitive_percentage is None:
        return None
    return volumen_total, volumen_con_derecho, definitive_percentage


def _settled_prorrata_register_entry(
    *,
    work_unit: WorkUnit,
    register: ProrrataRegister,
    volumen_total: Decimal,
    volumen_con_derecho: Decimal,
    definitive_percentage: Decimal,
) -> ProrrataRegisterEntry:
    volumen_sin_derecho = volumen_total - volumen_con_derecho
    settlement_fields = {
        "definitive_percentage": definitive_percentage,
        "definitive_volume_con_derecho": volumen_con_derecho,
        "definitive_volume_sin_derecho": volumen_sin_derecho,
    }
    existing = register.entry_for(work_unit.filing_year)
    if existing is not None:
        return ProrrataRegisterEntry.model_validate({**existing.model_dump(), **settlement_fields})

    regime = ProrrataRegisterRegime.GENERAL if volumen_sin_derecho > Decimal("0") else ProrrataRegisterRegime.NINGUNA
    return ProrrataRegisterEntry(
        ejercicio=work_unit.filing_year,
        regime=regime,
        especial_transition=None,
        definitive_percentage=definitive_percentage,
        definitive_volume_con_derecho=volumen_con_derecho,
        definitive_volume_sin_derecho=volumen_sin_derecho,
    )


def _new_local_filing_record(
    *,
    filing_record_id: str,
    target: CalculationRevision,
    work_unit: WorkUnit,
    notes: str | None,
    actor: str,
    now: datetime,
) -> ModeloRecord:
    return ModeloRecord(
        filing_record_id=filing_record_id,
        work_unit_id=target.work_unit_id,
        calculation_revision_id=target.calculation_revision_id,
        bucket_id=work_unit.bucket_id,
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        filed_at=now,
        filed_by=actor.strip(),
        notes=notes.strip() if notes else None,
        aeat_accepted=False,
        status=ModeloRecordStatus.VIGENTE,
        source_transaction_ids=target.source_transaction_ids,
    )


def _filed_calculation_revision(
    *,
    target: CalculationRevision,
    actor: str,
    now: datetime,
) -> CalculationRevision:
    return target.model_copy(
        update={
            "state": CalculationRevisionState.PRESENTADO,
            "filed_at": now,
            "filed_by": actor.strip(),
            "updated_at": now,
        },
    )


def _supersede_prior_current_filing(
    prior_current: ModeloRecord,
    *,
    filing_catalogue: ModeloRecordCatalogue,
    revisions: CalculationRevisionCatalogue,
    new_filing_id: str,
    now: datetime,
) -> tuple[ModeloRecordCatalogue, CalculationRevisionCatalogue]:
    """Supersede the prior current filing record and its PRESENTADO revision.

    Marks ``prior_current`` SUPERSEDIDO (stamped with ``new_filing_id``) and, when
    its calculation revision is still PRESENTADO, advances that revision to
    PRESENTADO_SUPERSEDIDO. Returns the updated ``(filing_catalogue, revisions)``.
    """
    superseded_prior = prior_current.model_copy(
        update={
            "status": ModeloRecordStatus.SUPERSEDIDO,
            "superseded_at": now,
            "superseded_by_filing_record_id": new_filing_id,
        },
    )
    updated_filing_catalogue = upsert_filing_record(filing_catalogue, superseded_prior)
    prior_revision = revisions.get(prior_current.calculation_revision_id)
    if prior_revision is not None and prior_revision.state is CalculationRevisionState.PRESENTADO:
        superseded_revision = prior_revision.model_copy(
            update={
                "state": CalculationRevisionState.PRESENTADO_SUPERSEDIDO,
                "superseded_at": now,
                "updated_at": now,
            },
        )
        revisions = upsert_calculation_revision(revisions, superseded_revision)
    return updated_filing_catalogue, revisions


def _prior_domiciliation_payload(
    election: PriorDomiciliationElectionProjection | None,
) -> dict[str, str]:
    """Project the prior-domiciliation election onto its ``MODELO_FILED`` payload keys.

    Every key is emitted in both branches, in one order, so the event payload
    shape never depends on whether an election was resolved. An absent
    election and an election with an absent baseline field are both recorded
    as the empty-string absence marker the payload contract already used.
    """
    if election is None:
        return {
            "prior_domiciliation_election": "",
            "prior_domiciliation_baseline_filing_record_id": "",
            "prior_domiciliation_baseline_evidence_reference_id": "",
            "prior_domiciliation_baseline_result_disposition": "",
            "prior_domiciliation_baseline_source_header_locator": "",
        }
    baseline_disposition = election.baseline_result_disposition
    return {
        "prior_domiciliation_election": election.election.value,
        "prior_domiciliation_baseline_filing_record_id": election.baseline_filing_record_id or "",
        "prior_domiciliation_baseline_evidence_reference_id": election.baseline_evidence_reference_id or "",
        "prior_domiciliation_baseline_result_disposition": (
            baseline_disposition.value if baseline_disposition is not None else ""
        ),
        "prior_domiciliation_baseline_source_header_locator": election.baseline_source_header_locator or "",
    }


def _refresh_filing_retention_snapshot(
    *,
    bucket_id: str,
    catalogue: ModeloRecordCatalogue,
    observed_at: datetime,
) -> None:
    """Record the filing facts a later deletion preflight will assess.

    Runs AFTER the catalogue has durably saved, and delegates the write to the
    filing package's best-effort recorder, which never raises. The ordering and
    the never-raising are the same decision from two sides: a filing that
    succeeded with a stale snapshot is recoverable, while a filing refused
    because a deletion-support record could not be written is not.

    This is the moment the retention position changes and the only moment a
    session for the bucket is held by construction, which is why the producer
    lives here rather than at the deletion preflight that consumes it.
    """
    try_record_filing_retention_snapshot(
        bucket_id=bucket_id,
        records=tuple(catalogue.records.values()),
        observed_at=observed_at,
    )


def persist_filed_revision(
    *,
    target: CalculationRevision,
    work_unit: WorkUnit,
    work_units: WorkUnitCatalogue,
    notes: str | None,
    actor: str,
    now: datetime,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol,
    calculation_observation_repository: CalculationObservationRepository | None = None,
    participation_index_repository: TransactionParticipationIndexRepository | None = None,
    prorrata_register_repository: ProrrataRegisterRepositoryProtocol | None = None,
    result_disposition: ResultDisposition | None = None,
    prior_domiciliation_election: PriorDomiciliationElectionProjection | None = None,
    taxpayer_nif: str | None = None,
) -> ModeloRecord:
    """Persist a verified-complete calculation revision and return a :class:`ModeloRecord`.

    The caller has already run verification/workflow/readiness gates. The
    ``target`` :class:`CalculationRevision` is the verified-complete source
    revision that becomes ``PRESENTADO`` when this transition succeeds.
    The parent :class:`WorkUnit` is advanced to the new current filing record
    after the calculation and filing catalogues are saved.

    When ``calculation_observation_repository`` is supplied, the filed revision's
    observations are co-emitted with ``MODELO_FILED`` through
    :func:`~application.modelo._filed_revision_observation.persist_filed_revision_observation`,
    so later calculations can carry them through the ``previous_filing`` resolver.
    The record is stamped with NON-official ``app_filing`` and never satisfies the
    cross-period clean-state filing gate; use
    :func:`~application.modelo.import_external_filing_evidence` when the
    current record must carry
    :class:`~domain.modelos.ExternalEvidence`.

    ``result_disposition`` is resolved once at the calculate/file boundary by
    ``resolve_modelo_result_disposition``. Modelo 303 observation persistence
    retains that typed fact with app-filing provenance and derives carry only
    through the shared canonical ingress; it never inherits a boolean default.

    For Modelo 303 settlement periods, the filed definitive prorrata percentage
    and annual volume inputs are also co-emitted to the profile
    :class:`~domain.prorrata_register.ProrrataRegister` through
    :class:`~adapters.persistence.profile.prorrata_register.ProrrataRegisterRepository`
    in the same secure-object save as the filing catalogue and filed
    calculation revision.
    """
    # Ahead of every write in this transition, not merely ahead of the
    # observation it guards. The same requirement is enforced again at the
    # observation write, which other callers reach directly, but that position
    # is downstream of the filing catalogue, the advanced WorkUnit pointer, the
    # participation index, any prorrata writeback and the MODELO_FILED events --
    # all of which have already landed by then. A filing refused there would be
    # refused after being filed. Conditioned on the observation repository being
    # supplied so the set of filings that must carry a disposition is unchanged;
    # only when the refusal happens moves.
    if calculation_observation_repository is not None:
        require_filing_result_disposition(work_unit=work_unit, result_disposition=result_disposition)
    calculation_revision_id = target.calculation_revision_id
    new_filing_id = derive_filing_record_id(
        work_unit_id=target.work_unit_id,
        calculation_revision_id=calculation_revision_id,
        filed_by=actor.strip(),
    )

    filing_catalogue = filing_repository.load()
    prior_current = filing_catalogue.current_for(
        bucket_id=work_unit.bucket_id,
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
    )

    new_filing = _new_local_filing_record(
        filing_record_id=new_filing_id,
        target=target,
        work_unit=work_unit,
        notes=notes,
        actor=actor,
        now=now,
    )

    # Revisioned: this catalogue is composed into a co-commit, so it cannot
    # use a self-committing mutation, and an unguarded read would write the
    # whole singleton row back over a revision another calculate run added.
    revisions, revisions_revision_id = calculation_repository.load_revisioned()
    updated_filing_catalogue = filing_catalogue
    if prior_current is not None:
        updated_filing_catalogue, revisions = _supersede_prior_current_filing(
            prior_current,
            filing_catalogue=updated_filing_catalogue,
            revisions=revisions,
            new_filing_id=new_filing_id,
            now=now,
        )

    updated_filing_catalogue = upsert_filing_record(updated_filing_catalogue, new_filing)
    filed_target = _filed_calculation_revision(target=target, actor=actor, now=now)
    revisions = upsert_calculation_revision(revisions, filed_target)

    participation_repo = _participation_index_repository(participation_index_repository, bucket_id=work_unit.bucket_id)
    participation_writes = _build_filed_participation_writes(
        filed_target=filed_target,
        work_unit=work_unit,
        filing_record_id=new_filing_id,
        participation_index_repository=participation_repo,
    )
    prorrata_repo = _prorrata_register_repository(prorrata_register_repository, bucket_id=work_unit.bucket_id)
    prorrata_write = _build_prorrata_settlement_write(
        filed_target=filed_target,
        work_unit=work_unit,
        prorrata_register_repository=prorrata_repo,
    )
    advanced_work_units = upsert_work_unit(
        work_units,
        work_unit.model_copy(
            update={
                "filed_calculation_revision_id": calculation_revision_id,
                "current_filing_record_id": new_filing_id,
                "updated_at": now,
            },
        ),
    )

    filed_events: list[BucketEvent] = []
    if prior_current is not None:
        filed_events.append(
            build_modelo_bucket_event(
                bucket_id=work_unit.bucket_id,
                event_type=BucketEventType.MODELO_FILED_SUPERSEDED,
                occurred_at=now,
                actor=actor,
                object_type=BucketEventObjectType.FILING_RECORD,
                object_id=prior_current.filing_record_id,
                payload={
                    "superseded_by_filing_record_id": new_filing_id,
                    "calculation_revision_id": prior_current.calculation_revision_id,
                    "modelo": work_unit.modelo,
                    "filing_year": str(work_unit.filing_year),
                    "period": work_unit.period.registry_token,
                },
            ),
        )
    filed_events.append(
        build_modelo_bucket_event(
            bucket_id=work_unit.bucket_id,
            event_type=BucketEventType.MODELO_FILED,
            occurred_at=now,
            actor=actor,
            object_type=BucketEventObjectType.FILING_RECORD,
            object_id=new_filing_id,
            payload={
                "calculation_revision_id": calculation_revision_id,
                "work_unit_id": target.work_unit_id,
                "modelo": work_unit.modelo,
                "filing_year": str(work_unit.filing_year),
                "period": work_unit.period.registry_token,
                "supersedes_filing_record_id": prior_current.filing_record_id if prior_current is not None else "",
                **_prior_domiciliation_payload(prior_domiciliation_election),
            },
        ),
    )

    extra_writes = (
        calculation_repository.to_secure_object_write(revisions, expected_revision_id=revisions_revision_id),
        *participation_writes,
    )
    if prorrata_write is not None:
        extra_writes = (*extra_writes, prorrata_write)
    extra_writes = (
        *extra_writes,
        work_unit_repository.to_secure_object_write(advanced_work_units),
        bucket_event_history_write(bucket_event_repository, tuple(filed_events)),
    )

    # One unit of work for the whole local filing transition: the filed revision,
    # the filing catalogue, the per-transaction participation index, any prorrata
    # settlement writeback, the advanced WorkUnit filing pointer, and the
    # supersession + mandatory MODELO_FILED events. The participation rows gain
    # filing_record_id in the same SQL transaction as the filing catalogue, so
    # transaction->filing cross-reference cannot drift from the receipt it names;
    # folding the pointer and the events in closes the seam that previously let a
    # VIGENTE filing and an advanced filed pointer come to rest with no matching
    # history entry.
    filing_repository.save_with_secure_object_writes(
        updated_filing_catalogue,
        extra_writes,
    )

    _refresh_filing_retention_snapshot(
        bucket_id=work_unit.bucket_id,
        catalogue=updated_filing_catalogue,
        observed_at=now,
    )

    # Cross-period carry projection (co-emitted with MODELO_FILED above): record
    # the filed casilla observations under the NON-official app_filing source so
    # a later period's calculate carries them forward through the previous_filing
    # resolver. Runs after the catalogue saves succeed so a failed filing never
    # leaves a carry row behind.
    if calculation_observation_repository is not None:
        persist_filed_revision_observation(
            revision=filed_target,
            work_unit=work_unit,
            repository=calculation_observation_repository,
            captured_at=now,
            result_disposition=result_disposition,
            prior_domiciliation_election=prior_domiciliation_election,
            taxpayer_nif=taxpayer_nif,
            filing_record_id=new_filing_id,
        )

    return new_filing


supersede_prior_current_filing = _supersede_prior_current_filing

__all__ = [
    "build_modelo_bucket_event",
    "emit_modelo_bucket_event",
    "persist_calculation_revision",
    "persist_filed_revision",
]
