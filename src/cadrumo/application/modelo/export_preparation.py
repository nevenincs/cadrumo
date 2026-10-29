"""Modelo declaration export: write a verified-complete or filed calculation revision to a local AEAT-compatible file.

:func:`~cadrumo.application.modelo.export.export_modelo_revision` accepts a
:class:`~CalculationRevision` id, rebuilds and approves a
:class:`~domain.filing.schema.ModeloDraft` from the revision replay inputs,
then writes a fichero-BOE-formatted artefact to the operator-supplied output
path. A ``MODELO_EXPORTED`` event is appended to the
:class:`~adapters.persistence.profile.buckets.BucketEventHistoryRepository`.

Export consumes the registry-authored fichero-BOE layouts through the filing
runtime schema provider; Python code owns orchestration and safety checks, while
the registry remains the authority for record fields, casillas, header keys, and
provenance. The service refuses non-exportable revision states, cross-bucket
targets, missing profile facts, unclean cross-period prerequisites, unmatched IVA
wallet decisions, missing ledger evidence, Modelo 193 settled prior-accrual rows
whose amounts no official source settles, and unusable output paths before the
operator-visible file is committed.

The service is local-only: it never contacts AEAT and never invokes
``require_live_read``. Export is fundamentally an offline operation
that produces a file the operator presents through sede.agenciatributaria.gob.es
themselves.

The CLI verb ``aeat app modelo export`` is a thin delegate over this
service.

See Also:
    :func:`~cadrumo.application.modelo.revision_replay_inputs.revision_filing_replay_inputs`:
        Reconstructs the filing inputs from the persisted revision.
    :func:`~cadrumo.application.filing.draft_construction.build_draft`:
        Builds the transient registry-backed draft that is exported.
    ``cadrumo.application.filing.export_draft``:
        Serializes the approved draft through registry export layouts.
    :func:`~cadrumo.application.modelo.verification_cross_period.require_cross_period_clean_state`:
        Rechecks cross-period filing prerequisites before writing the export.
    :func:`~cadrumo.application.modelo.result_disposition_resolution.resolve_modelo_result_disposition`:
        Determines the fichero declaration type and refund disposition.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

from ...core.filing_producer_key import FilingProducerKey
from ...core.hashing import prefixed_digest
from ...core.modelo import Modelo
from ...core.period import Period
from ...core.prior_domiciliation_election import PriorDomiciliationElection
from ...domain.bienes_inversion.register import (
    BienesInversionIvaRegister,
    RegistroRegularizacionResult,
    compute_registro_regularizacion,
)
from ...domain.bienes_inversion.regularizacion_parameters import (
    BienesInversionRegularizacionParameters,
    resolve_bienes_inversion_regularizacion_parameters,
)
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.schema import BindingDefinition
from ...domain.calculations.registry.schema_exports import ExportLayoutDefinition
from ...domain.deadlines.models import TaxpayerProfile
from ...domain.filing.errors import FilingExportError
from ...domain.filing.protocols import ModeloInputs
from ...domain.filing.schema import ModeloDraft
from ...domain.filing.software_identity import (
    DEVELOPMENT_MOCK_SOFTWARE_IDENTITY_FACT_ID,
    AeatProductSoftwareIdentity,
)
from ...domain.iva_compensation.reconciliation import IvaCompensationReconciliationDecision
from ...domain.modelos.calculation_revision import (
    SEALED_REVISION_STATES,
    CalculationRevision,
)
from ...domain.modelos.errors import (
    ModeloExportError,
)
from ...domain.modelos.work_unit import WorkUnit
from ...domain.prorrata_register.register import ProrrataRegister
from ..aggregation.iva_ledger import IvaDifferentiatedDeductionContribution, IvaLedgerAggregation
from ..aggregation.iva_ledger_apportionment import resolve_iva_differentiated_deduction_contributions
from ..calculations.observations_repository import (
    PriorDomiciliationElectionProjection,
)
from ..filing.draft_construction import build_draft
from ..filing.draft_review import approve_draft
from ..filing.draft_review_ports import DraftReviewPorts
from ..filing.export import export_layout_renderability_reason
from ..filing.producer_snapshot import (
    FilingProducerSnapshotError,
    M303FilingFacts,
    TaxpayerIdentityFacts,
)
from ..filing.runtime import RegistrySchemaAccessor, filing_profile_from_taxpayer
from ._row_source_identity_replay import attach_revision_row_source_identities
from .action_errors import (
    CalculationRevisionStateError,
    ModeloPriorDomiciliationElectionRefusedError,
)
from .export_contracts import (
    ModeloExportCommand,
    ModeloExportEvidenceMissingError,
    ModeloExportUnsupportedError,
    ModeloIvaWalletDecisionProvenance,
)
from .export_sink import LocalFileExportSink
from .m303_regimen_simplificado_scope import (
    m303_regimen_simplificado_scope_for_profile,
)
from .profile_export_binding import (
    resolve_profile_export_values,
)
from .revision_replay_inputs import revision_filing_replay_inputs


def envelope_stamped_software_identity(
    export_layout: ExportLayoutDefinition | None,
    *,
    product_software_identity: AeatProductSoftwareIdentity,
) -> AeatProductSoftwareIdentity | None:
    """Return the identity the selected layout's header reserves, or ``None``.

    AEAT reserves the program identifier and developer NIF slots in an envelope
    prefix or auxiliary envelope header. A fixed-record layout that authors its
    envelope as an ordinary record stamps them through literals bound to the
    development mock identity fact instead. A layout doing neither carries no
    software identity at all, and claiming one for it would state a header fact
    the file does not hold. Both the fichero-BOE writer and the calculation
    report answer the question here so a report cannot name a grade the filing
    file would not carry.
    """
    if export_layout is None:
        return None
    if envelope_requires_product_identity(export_layout):
        return product_software_identity
    if _stamps_development_mock_identity(export_layout):
        return product_software_identity
    return None


def envelope_requires_product_identity(export_layout: ExportLayoutDefinition | None) -> bool:
    """Whether the declared envelope has a product identity input slot.

    A layout stamping the identity through fact-bound literals already carries
    the bytes, so the renderer is not handed an identity it has no slot for.
    """
    return export_layout is not None and (
        export_layout.auxiliary_envelope_header is not None
        or (
            export_layout.filing_envelope is not None
            and export_layout.filing_envelope.product_identity_requirement is not None
        )
    )


def _stamps_development_mock_identity(export_layout: ExportLayoutDefinition) -> bool:
    """Whether any record field takes its literal from the development mock identity fact."""
    return any(
        field.literal_fact is not None and field.literal_fact.fact_id == DEVELOPMENT_MOCK_SOFTWARE_IDENTITY_FACT_ID
        for record in export_layout.records
        for field in record.fields
    )


def _sha256_ref(value: str) -> str:
    return prefixed_digest(value.encode("utf-8"))


def export_sink(command: ModeloExportCommand) -> LocalFileExportSink:
    """Create the local sink selected by the export command."""
    return LocalFileExportSink(path=command.output_path, replace_existing=command.replace_existing)


def iva_wallet_decision_export_provenance(
    decision: IvaCompensationReconciliationDecision | None,
) -> ModeloIvaWalletDecisionProvenance | None:
    """Project an IVA wallet decision into a redacted export/event join record."""
    if decision is None:
        return None
    return ModeloIvaWalletDecisionProvenance(
        decision_ref=_sha256_ref(decision.model_dump_json()),
        selected_authority=str(decision.selected_authority),
        divergence=str(decision.divergence),
        target_year=decision.target_year,
        target_period=decision.target_period,
        authority_source_kinds=tuple(str(source.source_kind) for source in decision.authority_sources),
        authority_source_refs=tuple(_sha256_ref(source.source_locator) for source in decision.authority_sources),
    )


def raise_if_ledger_export_evidence_missing(revision: CalculationRevision) -> None:
    """Refuse ledger-derived exports that lack bundled evidence or a reference.

    Takes ``revision`` as a :class:`CalculationRevision`.
    """
    if any(
        issue.reason
        in {
            "iva_selected_scope_evidence_failure",
            "iva_compensation_annual_source_evidence_failure",
        }
        for issue in revision.source_issues
    ):
        raise ModeloExportEvidenceMissingError(
            translated_message="application.modelo.errors.export_ledger_evidence_missing",
            context={"calculation_revision_id": revision.calculation_revision_id},
        )
    if not revision.source_transaction_ids:
        return
    if revision.ledger_filing_evidence is not None:
        return
    if revision.ledger_filing_snapshot is not None:
        return
    raise ModeloExportEvidenceMissingError(
        translated_message="application.modelo.errors.export_ledger_evidence_missing",
        context={"calculation_revision_id": revision.calculation_revision_id},
    )


def require_exportable_revision_state(revision: CalculationRevision) -> None:
    """Refuse a revision no export artefact may be produced from.

    Only a sealed :class:`CalculationRevision` -- verificado-completo, presentado, or a superseded
    presentado -- describes a settled calculation. A draft is still being
    edited, so any artefact rendered from it would claim a state the revision
    does not hold. Every modelo export destination applies this one rule rather
    than restating the state set.

    Raises:
        CalculationRevisionStateError: The revision is not sealed.
    """
    if revision.state not in SEALED_REVISION_STATES:
        raise CalculationRevisionStateError(
            translated_message="application.modelo.errors.export_revision_state_refused",
            context={
                "calculation_revision_id": revision.calculation_revision_id,
                "state": revision.state.value,
            },
        )


def compose_export_dictionary_values(
    *,
    draft: ModeloDraft,
    taxpayer_identity: TaxpayerIdentityFacts,
    bucket_id: str,
    operation: PinnedAuthorityOperation,
    profile_export_bindings: Sequence[BindingDefinition] = (),
) -> dict[str, object]:
    """Resolve typed XML dictionary values from canonical profile bindings.

    Takes ``draft`` as a :class:`ModeloDraft`.
    """
    values: dict[str, object] = dict(
        resolve_profile_export_values(profile_export_bindings, bucket_id=bucket_id, operation=operation),
    )
    if taxpayer_identity.full_name is None:
        raise ModeloExportError(
            translated_message="application.modelo.errors.export_draft_write_failed",
            context={"cause": "XML dictionary export requires exact taxpayer full_name"},
        )
    values["DPNIF_D"] = draft.profile_tax_id
    values["DP_APENOM_D"] = taxpayer_identity.full_name
    return values


def resolve_work_unit_period(work_unit: WorkUnit) -> Period:
    """Return the typed :class:`~cadrumo.core.period.Period` carried by the work unit."""
    if work_unit.period.filing_year != work_unit.filing_year:
        raise ModeloExportError(
            translated_message="application.modelo.errors.export_period_unmappable",
            context={"work_unit_id": work_unit.work_unit_id, "period": work_unit.period.registry_token},
        )
    return work_unit.period


def raise_if_export_layout_unsupported(*, work_unit: WorkUnit, schema_provider: RegistrySchemaAccessor) -> None:
    """Refuse a modelo whose registry snapshot cannot render fichero-BOE bytes."""
    modelo = str(work_unit.modelo)
    subview = schema_provider.get_subview(modelo)
    layout = subview.export_layouts[0] if subview.export_layouts else None
    reason = export_layout_renderability_reason(modelo, layout)
    if reason is None:
        return
    context = {
        "modelo": modelo,
        "reason": reason,
    }
    if layout is not None:
        context["layout_id"] = layout.id
        context["layout_format"] = layout.format
    raise ModeloExportUnsupportedError(
        translated_message="application.modelo.errors.export_unsupported",
        context=context,
    )


def requireprior_domiciliation_marker_layout(
    *,
    work_unit: WorkUnit,
    prior_domiciliation_election: PriorDomiciliationElectionProjection,
    schema_provider: RegistrySchemaAccessor,
) -> None:
    """Require the selected registry revision to own the rectificativa ``X`` field."""
    if prior_domiciliation_election.election is PriorDomiciliationElection.KEEP:
        return
    marker_producer_key = FilingProducerKey.PRIOR_DOMICILIATION_ACTION
    layouts = schema_provider.get_subview(str(work_unit.modelo)).export_layouts
    if any(
        field.producer_key is marker_producer_key
        for layout in layouts
        for record in layout.records
        for field in record.fields
    ):
        return
    raise ModeloPriorDomiciliationElectionRefusedError(
        translated_message="errors.refused.refused_modeloprior_domiciliation_election",
        context={
            "modelo": str(work_unit.modelo),
            "revision_id": work_unit.revision_id,
            "producer_key": marker_producer_key.value,
            "revision_renders_action_marker": False,
        },
    )


def approve_export_draft(
    *,
    work_unit: WorkUnit,
    revision: CalculationRevision,
    workflow_profile: TaxpayerProfile,
    actor: str,
    approved_at: datetime,
    period: Period,
    schema_provider: RegistrySchemaAccessor,
    ports: DraftReviewPorts,
    operation: PinnedAuthorityOperation,
) -> tuple[Period, ModeloDraft]:
    """Build and approve the export draft for one :class:`~CalculationRevision`.

    The :class:`~cadrumo.domain.deadlines.models.TaxpayerProfile` is forwarded to
    :func:`~cadrumo.application.modelo.revision_replay_inputs.revision_filing_replay_inputs`
    so export uses the same profile-applicability relation inputs as the filing
    workflow gate. Returns the resolved :class:`~cadrumo.core.period.Period` and approved
    :class:`~domain.filing.schema.ModeloDraft`.
    """
    inputs: ModeloInputs = revision_filing_replay_inputs(
        revision=revision,
        work_unit=work_unit,
        workflow_profile=workflow_profile,
    )
    try:
        draft = build_draft(
            modelo=work_unit.modelo,
            period=period,
            profile=filing_profile_from_taxpayer(workflow_profile),
            inputs=inputs,
            closed_record_row_sets=revision.closed_record_row_sets,
            schema_provider=schema_provider,
        )
        draft = attach_revision_row_source_identities(draft=draft, revision=revision)
        approved = approve_draft(
            draft,
            bucket_id=work_unit.bucket_id,
            approved_by=actor,
            schema_provider=schema_provider,
            ports=ports,
            operation=operation,
            approved_at=approved_at,
        )
    except FilingExportError as exc:
        raise ModeloExportError(
            translated_message="application.modelo.errors.export_draft_approval_failed",
            context={"calculation_revision_id": revision.calculation_revision_id},
        ) from exc
    return period, approved


def resolve_m303_export_arrivals(
    *,
    period: Period,
    prorrata_register: ProrrataRegister,
    iva_aggregation: IvaLedgerAggregation,
    bienes_register: BienesInversionIvaRegister,
    operation: PinnedAuthorityOperation,
) -> tuple[
    tuple[IvaDifferentiatedDeductionContribution, ...],
    BienesInversionIvaRegister,
    RegistroRegularizacionResult,
    BienesInversionRegularizacionParameters,
]:
    """Assemble current canonical register arrivals from the work-unit-bound register."""
    snapshot = operation.snapshot(
        Modelo("303").value,
        filing_year=period.filing_year,
        period=period.registry_token,
    )
    if prorrata_register.is_sectorized:
        apportionment = iva_aggregation.prorrata_apportionment
        if apportionment is None or not apportionment.sector_apportionments:
            raise FilingProducerSnapshotError(
                "modelo 303 differentiated sectors require canonical sector apportionment",
            )
        contributions = resolve_iva_differentiated_deduction_contributions(
            snapshot.revision, iva_aggregation.observations, apportionment=apportionment, operation=operation
        )
    else:
        contributions = ()
    bienes_parameters = resolve_bienes_inversion_regularizacion_parameters(
        snapshot.revision,
        modelo_id=Modelo("303").value,
        filing_period_date=period.end_date,
    )
    definitive_by_identifier: dict[str, Decimal] = {}
    for record in bienes_register.in_window_records(period.filing_year, parameters=bienes_parameters):
        entry = prorrata_register.entry_for(
            period.filing_year,
            sector_id=record.prorrata_sector_id,
        )
        if entry is not None and entry.definitive_percentage is not None:
            definitive_by_identifier[record.identifier] = entry.definitive_percentage
    regularisation_result = compute_registro_regularizacion(
        bienes_register,
        regularizacion_year=period.filing_year,
        prorrata_definitiva_by_identifier=definitive_by_identifier,
        parameters=bienes_parameters,
    )
    if regularisation_result.pending_percentage_count:
        raise FilingProducerSnapshotError(
            "modelo 303 Bienes de inversión regularisation requires definitive prorrata evidence",
        )
    # The bundle travels out beside the result it produced, so the facts the
    # oracle later checks cannot be handed a bundle other than the one the
    # projection actually used.
    return contributions, bienes_register, regularisation_result, bienes_parameters


def require_m303_regimen_simplificado_scope_matches_profile(
    *,
    filing_facts: M303FilingFacts,
    workflow_profile: TaxpayerProfile,
) -> None:
    """Require persisted M303 evidence to agree with the canonical profile scope.

    Takes ``workflow_profile`` as a :class:`TaxpayerProfile`.
    """
    expected_scope = m303_regimen_simplificado_scope_for_profile(workflow_profile)
    if filing_facts.regimen_simplificado.scope_decision != expected_scope:
        raise FilingProducerSnapshotError(
            "modelo 303 simplified-regime filing evidence disagrees with the canonical IVA profile composition",
        )
