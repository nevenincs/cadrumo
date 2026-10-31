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

from datetime import datetime
from pathlib import Path
from typing import NamedTuple

from pydantic import BaseModel, Field, NonNegativeInt

from ...core.filing_year import FilingYear
from ...core.identity.bucket import BucketId
from ...core.identity.digest import ContentDigest, PrefixedContentDigest
from ...core.identity.hex_ids import CalculationRevisionId, WorkUnitId
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.operator_action_enums import ActionEvidenceProvenance
from ...core.payment_election import PaymentElection
from ...core.period import Period
from ...core.prior_domiciliation_election import PriorDomiciliationElection
from ...core.refund_election import RefundElection
from ...core.result_disposition import ResultDisposition
from ...domain.calculations.registry.schema_exports import ExportLayoutDefinition
from ...domain.filing.schema import ModeloCasillaProvenance
from ...domain.filing.software_identity import (
    AeatSoftwareIdentityGrade,
)
from ...domain.modelos.calculation_revision import (
    CalculationRevision,
)
from ...domain.modelos.calculation_revision_sources import RecordedCalculationNote
from ...domain.modelos.errors import (
    ModeloError,
    ModeloExportError,
)
from ...domain.modelos.work_unit import WorkUnit
from ...domain.transactions.own_accounts import (
    OwnAccountId,
    OwnAccountRole,
)
from ..calculations.observations_repository import (
    PriorDomiciliationElectionProjection,
)
from ..filing.export import export_layout_renderability_reason
from ..filing.producer_snapshot import (
    AmendmentEvidence,
    PresenterIdentity,
    TaxpayerIdentityFacts,
)
from ..filing.runtime import RegistrySchemaAccessor, build_runtime_schema_provider
from .action_errors import (
    ModeloPreconditionErrorMixin,
)
from .preconditions import (
    ModeloPreconditionFailure,
    build_modelo_precondition_failure_for_scenario,
)

_LOCAL_EXPORT_EVIDENCE_STATUS = "local_export_not_official_aeat_filing_evidence"
_LOCAL_EXPORT_OFFICIAL_EVIDENCE_MESSAGE = (
    "Local export wrote an AEAT-compatible fichero-BOE file only; it is not official AEAT filing evidence. "
    "Official evidence comes from AEAT after filing: justificante, consulta de declaraciones presentadas, "
    "or CSV cotejo."
)
_COMPLETENESS_UNVERIFIED_MESSAGE = (
    "This fichero-BOE was NOT completeness-verified: its modelo revision declares no calculation-completeness "
    "manifest, so the structural-parity gate could not confirm every required casilla reached disk. The file may "
    "be structurally thin. Review the exported casillas against the official Diseño de Registros before filing."
)


class ModeloExportReadinessRefusal(BaseModel):
    """Application-owned readiness fact and its declared operator outcome."""

    model_config = _STRICT_FROZEN

    reason: str
    context: dict[str, str]
    precondition_failure: ModeloPreconditionFailure


def _modelo_export_layout_readiness_refusal(
    *,
    modelo: str,
    layout: ExportLayoutDefinition | None,
) -> ModeloExportReadinessRefusal | None:
    """Project one resolved export layout into the application readiness contract."""
    reason = export_layout_renderability_reason(modelo, layout)
    if reason is None:
        return None
    context = {"modelo": modelo, "reason": reason}
    if layout is not None:
        context["layout_id"] = layout.id
        context["layout_format"] = str(layout.format)
    return ModeloExportReadinessRefusal(
        reason=reason,
        context=context,
        precondition_failure=build_modelo_precondition_failure_for_scenario(
            subject_leaf_key="modelo.readiness",
            scenario_id="modelo.readiness.export_layout.unrenderable",
            evidence_id="modelo.readiness.export_layout",
            evidence_values=context,
            provenance=ActionEvidenceProvenance.APPLICATION_STATE,
            action_argument_values={"modelo": modelo},
        ),
    )


def modelo_export_readiness_refusal(
    *,
    modelo: str,
    filing_year: int,
    period: Period,
    registry_ready: bool,
) -> ModeloExportReadinessRefusal | None:
    """Return the one declared readiness outcome when local export is unavailable.

    The application evaluates layout renderability and chooses the declared
    action.  The CLI may only resolve this returned verdict against its live
    surface before presentation.
    """
    if not registry_ready:
        return None
    provider = build_runtime_schema_provider(
        filing_year=filing_year,
        period=period,
        modelos=(modelo,),
    )
    subview = provider.get_subview(modelo)
    layout = subview.export_layouts[0] if subview.export_layouts else None
    return _modelo_export_layout_readiness_refusal(modelo=modelo, layout=layout)


class ModeloIvaWalletDecisionProvenance(BaseModel):
    """Redacted audit join for the Modelo 303 IVA wallet authority decision.

    This intentionally excludes taxpayer identifiers, wallet amounts, and local
    recurrence amounts. The fingerprint lets audits join back to encrypted
    secure-object storage without copying live fiscal values into export events
    or result payloads.
    """

    model_config = _STRICT_FROZEN

    decision_ref: PrefixedContentDigest
    selected_authority: str = Field(min_length=1, max_length=64)
    divergence: str = Field(min_length=1, max_length=64)
    target_year: FilingYear
    target_period: Period
    authority_source_kinds: tuple[str, ...] = Field(default_factory=tuple)
    authority_source_refs: tuple[PrefixedContentDigest, ...] = Field(default_factory=tuple)


class PreparedModeloExport(NamedTuple):
    """Validated inputs shared by draft approval and export persistence."""

    work_unit: WorkUnit
    revision: CalculationRevision
    period: Period
    schema_provider: RegistrySchemaAccessor
    iva_wallet_provenance: ModeloIvaWalletDecisionProvenance | None
    prior_domiciliation_election: PriorDomiciliationElectionProjection
    amendment_evidence: AmendmentEvidence | None


class ModeloExportCrossBucketRefusedError(ModeloError):
    """Raised when the addressed revision's parent work unit belongs to a bucket other than the active profile bucket.

    Bucket events must scope to the active bucket; allowing the service
    to emit into a foreign bucket would let any caller pollute another
    operator's history.
    """


class ModeloExportNoActiveBucketError(ModeloError):
    """Raised when no active profile bucket is configured.

    Export needs an active bucket because the resulting MODELO_EXPORTED
    event is scoped to a bucket id and the work-unit lookup is
    bucket-bound.
    """


class ModeloExportEvidenceMissingError(ModeloPreconditionErrorMixin, ModeloExportError):
    """Raised when a ledger-derived revision lacks exportable evidence."""


class ModeloExportUnsupportedError(ModeloExportError):
    """Raised when a modelo revision has no renderable local fichero-BOE export layout."""


class ModeloExportCommand(BaseModel):
    """Strict input contract for :func:`~cadrumo.application.modelo.export.export_modelo_revision`.

    Attributes:
        calculation_revision_id: SHA-256 hex id of the calculation
            revision to export. Must be in ``VERIFICADO_COMPLETO`` or
            ``FILED`` state.
        output_path: Absolute or working-directory-relative path to
            write the fichero-BOE artefact. Its parent directory must
            already exist; an existing file is refused unless
            ``replace_existing`` is set.
        actor: Operator identifier captured into the
            ``MODELO_EXPORTED`` event payload and used as the draft
            ``approved_by`` field for the transient export draft.
        refund_election: The operator's per-filing Modelo 303 negative-result
            disposition election threaded into the shared disposition resolver so
            the exported fichero "Tipo de declaración" matches the election made at
            filing. Defaults to ``COMPENSAR``; ``DEVOLVER`` requests the credit
            back and is honoured only for a lawful refund period (refused
            otherwise).
        payment_election: The operator's positive-result settlement election.
            ``INGRESO`` retains the standard declaration type, while a supported
            Modelo 303 ``DOMICILIACION`` resolves to ``U``. Unsupported or
            sign-incompatible elections are refused by the shared resolver.
        prior_domiciliation_election: Explicit Modelo 303 action for a prior
            domiciliation. ``None`` resolves the neutral ``KEEP`` value, except
            for a Modelo 303 rectificativa stating casilla 111, where the choice
            decides whether Nota 3 puts the refund account on the DID page and
            is therefore required.
        charge_account_id: Per-filing choice of the own account AEAT debits for
            a domiciliación. ``None`` resolves the register's CHARGE
            designation for the modelo, else its designation for every modelo.
        refund_account_id: Per-filing choice of the own account AEAT pays a
            refund into, resolved like ``charge_account_id`` from the REFUND
            designations when ``None``.
        replace_existing: Whether the operator explicitly chose to replace a
            file already at ``output_path``. An export is the artefact an
            operator carries to AEAT, so destroying an earlier one is never
            the default.
    """

    model_config = _STRICT_FROZEN

    calculation_revision_id: CalculationRevisionId
    output_path: Path
    actor: str = Field(min_length=1, max_length=128)
    presenter: PresenterIdentity | None = None
    taxpayer_identity: TaxpayerIdentityFacts | None = None
    amendment_evidence: AmendmentEvidence | None = None
    refund_election: RefundElection = RefundElection.COMPENSAR
    payment_election: PaymentElection = PaymentElection.INGRESO
    prior_domiciliation_election: PriorDomiciliationElection | None = None
    charge_account_id: OwnAccountId | None = None
    refund_account_id: OwnAccountId | None = None
    replace_existing: bool = False


class ModeloExportAccountReference(BaseModel):
    """Which account the exported fichero carries, without any account material.

    Attributes:
        role: Whether the account page carries a charge or a refund account.
        own_account_id: The own account resolved for that role, or ``None`` when
            the account is embedded in the filing's own facts (a modelo 360
            solicitud's account).
    """

    model_config = _STRICT_FROZEN

    role: OwnAccountRole
    own_account_id: OwnAccountId | None = None


class ModeloExportResult(BaseModel):
    """Receipt produced by :func:`~cadrumo.application.modelo.export.export_modelo_revision`.

    Composes the lower-level
    :class:`~cadrumo.application.filing.export_verification.DeclaracionExportResult` (already a
    byte-level receipt of the written file) with the work-unit-level
    identity the operator addresses.

    Attributes:
        calculation_revision_id: The exported revision id.
        work_unit_id: The parent work unit's id.
        bucket_id: The bucket the work unit lives in (always equal to
            the active profile bucket at export time).
        modelo: AEAT modelo identifier.
        filing_year: AEAT filing year.
        period: Filing period as a typed :class:`~cadrumo.core.period.Period` value.
        output_path: Absolute path the file was written to.
        byte_size: Size of the written file in bytes.
        file_sha256: Hex-encoded SHA-256 of the written bytes.
        format: Wire format string (currently always ``"fichero-boe"``).
        exported_at: UTC timestamp of the write.
        actor: Operator identifier captured into the event.
        bucket_event_id: Id of the ``MODELO_EXPORTED`` event appended
            to the catalogue.
        resolved_result_disposition: The single resolved AEAT declaration type,
            or ``None`` for a modelo whose design carries no disposition.
        payment_election: The semantic positive-result election when applicable.
        refund_election: The semantic negative-result election when applicable.
        selected_account: The role and own-account identity of the account the
            fichero carries, or ``None`` when it carries no account.
        casilla_provenance: Regulatory grounding for casillas covered
            by the exported fichero-BOE layout.
        software_identity_grade: Grade of the program identifier and
            developer NIF stamped into an envelope-prefixed header, or
            ``None`` when the selected layout renders no such header.
        calculation_notes: What the exported revision's calculation noted about
            the taxpayer's assets, in the words the form uses.
    """

    model_config = _STRICT_FROZEN

    calculation_revision_id: CalculationRevisionId
    work_unit_id: WorkUnitId
    bucket_id: BucketId
    modelo: str = Field(min_length=1, max_length=8)
    filing_year: FilingYear
    period: Period
    output_path: Path
    byte_size: NonNegativeInt
    file_sha256: ContentDigest
    format: str = Field(min_length=1)
    exported_at: datetime
    actor: str = Field(min_length=1, max_length=128)
    bucket_event_id: str = Field(min_length=1, max_length=128)
    resolved_result_disposition: ResultDisposition | None = ResultDisposition.INGRESO
    payment_election: PaymentElection | None = None
    refund_election: RefundElection | None = None
    prior_domiciliation_election: PriorDomiciliationElectionProjection = Field(
        default_factory=lambda: PriorDomiciliationElectionProjection(
            election=PriorDomiciliationElection.KEEP,
        ),
    )
    selected_account: ModeloExportAccountReference | None = None
    casilla_provenance: tuple[ModeloCasillaProvenance, ...] = Field(default_factory=tuple)
    iva_wallet_decision_provenance: ModeloIvaWalletDecisionProvenance | None = None
    software_identity_grade: AeatSoftwareIdentityGrade | None = None
    calculation_notes: tuple[RecordedCalculationNote, ...] = ()
    local_evidence_status: str = Field(default=_LOCAL_EXPORT_EVIDENCE_STATUS, min_length=1)
    official_evidence_message: str = Field(default=_LOCAL_EXPORT_OFFICIAL_EVIDENCE_MESSAGE, min_length=1)
    domiciliation_cutoff_unverified: bool = Field(
        default=False,
        description=(
            "True when a domiciliación (U) export was not checked against a direct-debit cutoff because the filing "
            "window declares no payment cutoff date. The CLI surfaces a non-blocking advisory when set. False for "
            "every other disposition and whenever a cutoff was declared and met."
        ),
    )
    completeness_unverified: bool = Field(
        default=False,
        description=(
            "True when a fixed-width fichero-BOE export could not be completeness-verified because the modelo "
            "revision declares no calculation-completeness manifest, so the structural-parity gate did not run. "
            "The CLI surfaces a non-blocking coverage advisory when set. False when the gate ran (manifest present) "
            "or the transport is not the fixed-width fichero-BOE."
        ),
    )

    @property
    def completeness_advisory_message(self) -> str:
        """Operator-facing coverage advisory text for a completeness-unverified export."""
        return _COMPLETENESS_UNVERIFIED_MESSAGE
