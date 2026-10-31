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

from collections.abc import Mapping
from datetime import date, datetime
from typing import NamedTuple

from ...core.export_layout_format import ExportLayoutFormat
from ...core.modelo import Modelo
from ...core.prior_domiciliation_election import PriorDomiciliationElection
from ...core.result_disposition import ResultDisposition, result_disposition_is_refund
from ...core.time.clock import MADRID_TZ
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.form_codes import form_for_role
from ...domain.calculations.registry.m303_casilla_roles import m303_importe_rectificacion_casilla
from ...domain.deadlines.models import ChargeAccount, ModeloIVAProfile, RefundAccount, TaxpayerProfile
from ...domain.deadlines.plazo import resolve_filing_window
from ...domain.modelos.calculation_revision import (
    CalculationRevision,
)
from ...domain.modelos.errors import (
    ModeloExportError,
)
from ...domain.modelos.work_unit import WorkUnit
from ...domain.transactions.own_accounts import (
    OwnAccountRegister,
    OwnAccountRegisterError,
    OwnAccountRole,
    OwnBankAccount,
)
from ..aggregation.iva_ledger import (
    aggregate_iva_ledger_observations_from_repositories,
)
from ..aggregation.m303_arrivals import (
    resolve_m303_prorrata_transition_arrival,
    resolve_m303_supplier_regime_arrival,
)
from ..calculations.observations_repository import (
    PriorDomiciliationElectionProjection,
)
from ..filing.producer_snapshot import (
    AmendmentEvidence,
    FilingElectionFacts,
    FilingModelProfileFacts,
    FilingProducerSnapshot,
    FilingProducerSnapshotError,
    GeneralFilingProfileFacts,
    M303FilingFacts,
    Modelo111ProfileFacts,
    Modelo202ProducerProfile,
    PresenterIdentity,
    TaxpayerIdentityFacts,
    build_filing_producer_snapshot,
    resolve_m303_filing_facts,
)
from ..filing.producer_snapshot_m360 import Modelo360RepresentanteAccountChoice, Modelo360SolicitudEntry
from ..filing.runtime import RegistrySchemaAccessor
from ..prorrata_register.service import require_prorrata_register_coordinates_current
from .action_errors import (
    ModeloChargeAccountMissingError,
    ModeloDomiciliationPastCutoffError,
    ModeloRefundAccountMissingError,
)
from .export_contracts import (
    ModeloExportAccountReference,
    ModeloExportCommand,
    ModeloExportEvidenceMissingError,
)
from .export_ports import ModeloExportPorts
from .export_preparation import (
    require_m303_regimen_simplificado_scope_matches_profile,
    resolve_m303_export_arrivals,
)
from .filing_revision_persistence import require_filing_instance_evidence_for_work_unit
from .profile_export_binding import (
    resolve_declaration_contact,
    resolve_export_identity,
)
from .result_disposition_resolution import require_admissible_charge_account


class _ResolvedOwnAccount(NamedTuple):
    """One role's account as resolved for the filing, or why it cannot serve.

    ``embedded`` is the one account that is not an own account: a modelo 360
    solicitud's representante account, carried by the solicitud itself.
    """

    account: OwnBankAccount | None
    unavailable_reason: str | None = None
    embedded: RefundAccount | None = None


class _ExportAccounts(NamedTuple):
    """The charge and refund own accounts one export may place on its account page."""

    charge: _ResolvedOwnAccount
    refund: _ResolvedOwnAccount


def _resolve_own_account(
    register: OwnAccountRegister,
    *,
    role: OwnAccountRole,
    modelo: Modelo,
    explicit_id: str | None,
    on: date,
    context: Mapping[str, object],
) -> _ResolvedOwnAccount:
    """Resolve ``role``: the per-filing choice, else the modelo designation, else the ALL one.

    An explicit choice is the operator's deliberate instruction, so an unknown or
    closed account refuses at once. A designated account that is closed on the
    export date is only unavailable: the export refuses when the role is needed.
    """
    if explicit_id is not None:
        try:
            account = register.account(explicit_id)
        except OwnAccountRegisterError as exc:
            raise _missing_account_error(
                role, context={**context, "reason": "own_account_unregistered", "own_account_id": explicit_id}
            ) from exc
        if not account.open_on(on):
            raise _missing_account_error(
                role, context={**context, "reason": "own_account_closed", "own_account_id": explicit_id}
            )
        return _ResolvedOwnAccount(account=account)
    designated = register.designated(role, modelo)
    if designated is None:
        return _ResolvedOwnAccount(account=None)
    if not designated.open_on(on):
        return _ResolvedOwnAccount(account=designated, unavailable_reason="own_account_closed")
    return _ResolvedOwnAccount(account=designated)


def _missing_account_error(
    role: OwnAccountRole, *, context: Mapping[str, object]
) -> ModeloChargeAccountMissingError | ModeloRefundAccountMissingError:
    if role is OwnAccountRole.CHARGE:
        return ModeloChargeAccountMissingError(
            "a domiciliacion export requires a charge account on file",
            context=dict(context),
        )
    return ModeloRefundAccountMissingError(
        "the export's account page requires a refund account on file",
        context=dict(context),
    )


def _unavailable_context(context: Mapping[str, object], resolved: _ResolvedOwnAccount) -> dict[str, object]:
    """Name why a resolved account cannot serve, by its opaque id only."""
    if resolved.unavailable_reason is None:
        return dict(context)
    if resolved.account is None:
        return {**context, "reason": resolved.unavailable_reason}
    return {**context, "reason": resolved.unavailable_reason, "own_account_id": resolved.account.own_account_id}


def _resolve_m360_refund_account(
    register: OwnAccountRegister,
    entry: Modelo360SolicitudEntry,
    *,
    explicit_id: str | None,
    on: date,
    context: Mapping[str, object],
) -> _ResolvedOwnAccount:
    """Resolve the account a modelo 360 solicitud declares; designations never answer it.

    DR360 campo 114 makes the account part of the solicitud: the solicitante's own
    account by reference, or the representante's embedded in the solicitud. Campos
    115 and 116 are both obligatorio, so a referenced own account without a BIC is
    refused here rather than at the first blank position.
    """
    if explicit_id is not None:
        raise _missing_account_error(
            OwnAccountRole.REFUND,
            context={**context, "reason": "m360_account_declared_on_solicitud", "own_account_id": explicit_id},
        )
    choice = entry.account
    if choice is None:
        return _ResolvedOwnAccount(account=None, unavailable_reason="m360_account_undeclared")
    if isinstance(choice, Modelo360RepresentanteAccountChoice):
        return _ResolvedOwnAccount(account=None, embedded=choice.account)
    resolved = _resolve_own_account(
        register,
        role=OwnAccountRole.REFUND,
        modelo=Modelo("360"),
        explicit_id=choice.own_account_id,
        on=on,
        context=context,
    )
    if resolved.account is not None and not resolved.account.swift_bic:
        raise _missing_account_error(
            OwnAccountRole.REFUND,
            context={**context, "reason": "refund_account_bic_missing", "own_account_id": choice.own_account_id},
        )
    return resolved


def resolve_export_accounts(
    command: ModeloExportCommand,
    *,
    work_unit: WorkUnit,
    export_ports: ModeloExportPorts,
    exported_at: datetime,
    m360_solicitud: Modelo360SolicitudEntry | None,
) -> _ExportAccounts:
    """Resolve the filing's charge and refund own accounts from the ledger register.

    The one resolution point at the export boundary: every modelo's account page
    reads the same register, and which account it carries follows the resolved
    disposition, never the modelo's name. A modelo 360 solicitud declares its own
    refund account, so its refund role reads the solicitud instead.
    """
    register = export_ports.own_accounts.load()
    modelo = Modelo(str(work_unit.modelo))
    on = exported_at.astimezone(MADRID_TZ).date()
    context = {"calculation_revision_id": command.calculation_revision_id}
    if m360_solicitud is not None:
        refund = _resolve_m360_refund_account(
            register,
            m360_solicitud,
            explicit_id=command.refund_account_id,
            on=on,
            context=context,
        )
    else:
        refund = _resolve_own_account(
            register,
            role=OwnAccountRole.REFUND,
            modelo=modelo,
            explicit_id=command.refund_account_id,
            on=on,
            context=context,
        )
    return _ExportAccounts(
        charge=_resolve_own_account(
            register,
            role=OwnAccountRole.CHARGE,
            modelo=modelo,
            explicit_id=command.charge_account_id,
            on=on,
            context=context,
        ),
        refund=refund,
    )


def refund_account_country(resolved: _ResolvedOwnAccount) -> str | None:
    """The country of the refund account the filing would be paid into, when one can serve."""
    projected = _refund_account_projection(resolved)
    return None if projected is None or projected.iban is None else projected.iban[:2]


def require_domiciliation_before_cutoff(
    command: ModeloExportCommand,
    *,
    work_unit: WorkUnit,
    resolved_result_disposition: ResultDisposition | None,
    exported_at: datetime,
    operation: PinnedAuthorityOperation,
) -> bool:
    """Refuse a domiciliación dated after the filing window's payment cutoff.

    The cutoff is compared with the export's Europe/Madrid civil date, since
    AEAT's direct-debit deadline is a Spanish-calendar day. Returns whether the
    export is a domiciliación the registry gives no cutoff for, which is an
    advisory rather than a refusal: an undeclared cutoff is unknown, not open.
    """
    if resolved_result_disposition is not ResultDisposition.DOMICILIACION:
        return False
    window = resolve_filing_window(
        str(work_unit.modelo),
        work_unit.filing_year,
        work_unit.period,
        authority=operation,
    )
    cutoff = None if window is None else window.payment_cutoff_on
    if cutoff is None:
        return True
    export_on = exported_at.astimezone(MADRID_TZ).date()
    if export_on <= cutoff:
        return False
    raise ModeloDomiciliationPastCutoffError(
        translated_message="errors.refused.refused_modelo_domiciliation_past_cutoff",
        context={
            "calculation_revision_id": command.calculation_revision_id,
            "modelo": str(work_unit.modelo),
            "filing_year": str(work_unit.filing_year),
            "period": work_unit.period.registry_token,
            "payment_cutoff_on": cutoff.isoformat(),
            "export_on": export_on.isoformat(),
        },
    )


def _charge_account_projection(resolved: _ResolvedOwnAccount) -> ChargeAccount | None:
    if resolved.account is None or resolved.unavailable_reason is not None:
        return None
    return ChargeAccount(iban=resolved.account.iban)


def _refund_account_projection(resolved: _ResolvedOwnAccount) -> RefundAccount | None:
    if resolved.embedded is not None:
        return resolved.embedded
    account = resolved.account
    if account is None or resolved.unavailable_reason is not None:
        return None
    return RefundAccount(
        iban=account.iban,
        swift_bic=account.swift_bic,
        bank_name=account.bank_name,
        bank_address=account.bank_address,
        bank_city=account.bank_city,
        bank_country_code=account.bank_country_code,
    )


def selected_account_reference(
    producer_snapshot: FilingProducerSnapshot,
    *,
    accounts: _ExportAccounts,
) -> ModeloExportAccountReference | None:
    """Name the carried account by role and opaque identity, never by its material."""
    selected = producer_snapshot.selected_account
    if selected is None:
        return None
    if selected.role == "charge":
        charge = accounts.charge.account
        return ModeloExportAccountReference(
            role=OwnAccountRole.CHARGE,
            own_account_id=None if charge is None else charge.own_account_id,
        )
    # An embedded representante account has no own-account id to record.
    refund = accounts.refund.account
    return ModeloExportAccountReference(
        role=OwnAccountRole.REFUND,
        own_account_id=None if refund is None else refund.own_account_id,
    )


def build_export_producer_snapshot(
    *,
    command: ModeloExportCommand,
    work_unit: WorkUnit,
    revision: CalculationRevision,
    workflow_profile: TaxpayerProfile,
    resolved_result_disposition: ResultDisposition | None,
    prior_domiciliation_election: PriorDomiciliationElectionProjection,
    amendment_evidence: AmendmentEvidence | None,
    accounts: _ExportAccounts,
    m360_solicitud: Modelo360SolicitudEntry | None,
    export_ports: ModeloExportPorts,
    operation: PinnedAuthorityOperation,
) -> FilingProducerSnapshot:
    """Build the sole typed producer boundary or refuse before any write.

    Takes ``revision`` as a :class:`CalculationRevision` and ``workflow_profile`` as a :class:`TaxpayerProfile`.
    """
    presenter, taxpayer_identity = _require_export_identity(
        command,
        work_unit=work_unit,
        operation=operation,
    )
    try:
        modelo = Modelo(str(work_unit.modelo))
        iva_profile = workflow_profile.iva
        refund_account = _refund_account_projection(accounts.refund)
        charge_account = _charge_account_projection(accounts.charge)
        nota_three_refund_account = _require_export_accounts(
            command,
            work_unit=work_unit,
            revision=revision,
            accounts=accounts,
            charge_account=charge_account,
            refund_account=refund_account,
            resolved_result_disposition=resolved_result_disposition,
            prior_domiciliation_election=prior_domiciliation_election.election,
            amendment_evidence=amendment_evidence,
            operation=operation,
        )
        model_profile, m303_filing_facts = _resolve_export_model_profile(
            modelo=modelo,
            work_unit=work_unit,
            revision=revision,
            workflow_profile=workflow_profile,
            iva_profile=iva_profile,
            export_ports=export_ports,
            operation=operation,
            m360_solicitud=m360_solicitud,
        )
        if m360_solicitud is not None:
            account_page_refund_account = refund_account is not None
        else:
            account_page_refund_account = nota_three_refund_account
        return build_filing_producer_snapshot(
            modelo=modelo,
            taxpayer_tax_id=workflow_profile.tax_id,
            taxpayer_identity=taxpayer_identity,
            presenter=presenter,
            model_profile=model_profile,
            elections=FilingElectionFacts(
                result_disposition=resolved_result_disposition,
                payment=command.payment_election,
                refund=command.refund_election,
                prior_domiciliation=prior_domiciliation_election.election,
            ),
            amendment_evidence=amendment_evidence,
            refund_account=refund_account,
            charge_account=charge_account,
            account_page_refund_account=account_page_refund_account,
            m303_filing_facts=m303_filing_facts,
            # Read separately from the identity pair: AEAT's "persona con quien
            # relacionarse" is a third party, and under a gestor it is routinely
            # neither the taxpayer nor the presenter.
            declaration_contact=resolve_declaration_contact(
                bucket_id=work_unit.bucket_id,
                operation=operation,
            ),
        )
    except (FilingProducerSnapshotError, ValueError) as exc:
        # A typed cause (FilingProducerSnapshotError, e.g. the M202 producer-facts
        # completeness refusal) may already carry structured context -- the
        # missing fact identifiers, a reason -- that a bare `cause_type` would
        # otherwise discard. Merge it forward so the operator-visible refusal
        # names what is actually missing instead of only that something failed.
        context: dict[str, object] = {
            "calculation_revision_id": command.calculation_revision_id,
            "cause_type": type(exc).__name__,
        }
        cause_context = getattr(exc, "context", None)
        if cause_context:
            context.update(cause_context)
        raise ModeloExportError(
            translated_message="application.modelo.errors.export_draft_write_failed",
            context=context,
        ) from exc


def m303_nota_three_requires_refund_account(
    work_unit: WorkUnit,
    revision: CalculationRevision,
    prior_domiciliation_election: PriorDomiciliationElection,
    amendment_evidence: AmendmentEvidence | None,
    *,
    operation: PinnedAuthorityOperation,
) -> bool:
    """Read Nota 3 only for a rectificativa that keeps the prior domiciliation.

    The rectified-amount box is the one the work unit's edition declares; an
    edition that declares none has no Nota 3 account requirement.

    Takes ``revision`` as a :class:`CalculationRevision`.
    """
    if (
        amendment_evidence is None
        or not amendment_evidence.is_rectificativa
        or prior_domiciliation_election is not PriorDomiciliationElection.KEEP
    ):
        return False
    rectificacion_casilla = m303_importe_rectificacion_casilla(
        operation.revision_for_context(
            str(work_unit.modelo),
            filing_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
        )
    )
    return rectificacion_casilla is not None and revision.casilla_values.get(rectificacion_casilla) is not None


def _export_refund_account_is_missing(refund_account: RefundAccount | None) -> bool:
    """Require a present refund account with its IBAN, the identity every account page renders."""
    return refund_account is None or refund_account.iban is None


def _require_export_accounts(
    command: ModeloExportCommand,
    *,
    work_unit: WorkUnit,
    revision: CalculationRevision,
    accounts: _ExportAccounts,
    charge_account: ChargeAccount | None,
    refund_account: RefundAccount | None,
    resolved_result_disposition: ResultDisposition | None,
    prior_domiciliation_election: PriorDomiciliationElection,
    amendment_evidence: AmendmentEvidence | None,
    operation: PinnedAuthorityOperation,
) -> bool:
    """Refuse an export whose bank-account page has no account to carry.

    Returns whether Modelo 303 Nota 3 requires the refund account on the
    account page even though the disposition itself is not a refund: a
    rectificativa stating the rectified amount under a kept prior domiciliation.
    """
    context: dict[str, object] = {"calculation_revision_id": command.calculation_revision_id}
    if resolved_result_disposition is ResultDisposition.DOMICILIACION:
        if charge_account is None:
            raise _missing_account_error(OwnAccountRole.CHARGE, context=_unavailable_context(context, accounts.charge))
        require_admissible_charge_account(work_unit=work_unit, charge_account=charge_account)
        return False
    nota_three = m303_nota_three_requires_refund_account(
        work_unit, revision, prior_domiciliation_election, amendment_evidence, operation=operation
    )
    refund = resolved_result_disposition is not None and result_disposition_is_refund(resolved_result_disposition)
    if (refund or nota_three) and _export_refund_account_is_missing(refund_account):
        raise _missing_account_error(OwnAccountRole.REFUND, context=_unavailable_context(context, accounts.refund))
    return nota_three and not refund


def _require_export_identity(
    command: ModeloExportCommand,
    *,
    work_unit: WorkUnit,
    operation: PinnedAuthorityOperation,
) -> tuple[PresenterIdentity, TaxpayerIdentityFacts]:
    """Resolve the producer identity, deriving it from the profile when unset.

    An explicit command identity wins, so a caller that knows better -- a
    future representative or gestor surface -- overrides without threading
    anything new through this path. Otherwise the identity is read from the
    filing profile in the work unit's OWN bucket, which is the same bucket the
    export's other profile-sourced values already resolve against; taking it
    from the active bucket instead would let a cross-bucket export stamp one
    taxpayer's declaration with another's name.

    The refusal survives derivation rather than being replaced by it: a profile
    that is absent, or that declares no tax id or no usable name, still refuses
    here instead of producing a filed artefact with a half-built identity.
    """
    if command.presenter is not None and command.taxpayer_identity is not None:
        return command.presenter, command.taxpayer_identity
    derived = resolve_export_identity(
        bucket_id=work_unit.bucket_id,
        operation=operation,
    )
    presenter = command.presenter or (derived[0] if derived else None)
    taxpayer_identity = command.taxpayer_identity or (derived[1] if derived else None)
    if presenter is None or taxpayer_identity is None:
        raise ModeloExportError(
            translated_message="application.modelo.errors.export_draft_write_failed",
            context={
                "calculation_revision_id": command.calculation_revision_id,
                "cause": "explicit presenter and taxpayer identity facts are required",
            },
        )
    return presenter, taxpayer_identity


def _require_m360_solicitud(
    *,
    modelo: Modelo,
    work_unit: WorkUnit,
    export_ports: ModeloExportPorts,
) -> Modelo360SolicitudEntry | None:
    """Return the modelo 360 solicitud the operator declared for the work unit's period.

    ``None`` for every other modelo. For modelo 360 an undeclared solicitud is refused
    here: its header, parties and account holder exist nowhere else, and a solicitud
    rendered without them would be a blank page 1, not a smaller one.
    """
    if modelo != form_for_role("iva.foreign_refund"):
        return None
    entry = export_ports.m360_solicitud.load().entry_for(work_unit.period)
    if entry is None:
        raise FilingProducerSnapshotError(
            "modelo 360 requires the solicitud facts declared for its period",
            context={
                "reason": "m360_solicitud_undeclared",
                "filing_year": work_unit.period.filing_year,
                "period": work_unit.period.registry_token,
            },
        )
    return entry


def require_m360_solicitud_for_export(
    command: ModeloExportCommand,
    *,
    work_unit: WorkUnit,
    export_ports: ModeloExportPorts,
) -> Modelo360SolicitudEntry | None:
    """Load the modelo 360 solicitud before any account resolves, refusing an undeclared one."""
    try:
        return _require_m360_solicitud(
            modelo=Modelo(str(work_unit.modelo)),
            work_unit=work_unit,
            export_ports=export_ports,
        )
    except FilingProducerSnapshotError as exc:
        raise ModeloExportError(
            translated_message="application.modelo.errors.export_draft_write_failed",
            context={
                "calculation_revision_id": command.calculation_revision_id,
                "cause_type": type(exc).__name__,
                **(exc.context or {}),
            },
        ) from exc


def _resolve_export_model_profile(
    *,
    modelo: Modelo,
    work_unit: WorkUnit,
    revision: CalculationRevision,
    workflow_profile: TaxpayerProfile,
    iva_profile: ModeloIVAProfile | None,
    export_ports: ModeloExportPorts,
    operation: PinnedAuthorityOperation,
    m360_solicitud: Modelo360SolicitudEntry | None,
) -> tuple[FilingModelProfileFacts, M303FilingFacts | None]:
    if m360_solicitud is not None:
        return m360_solicitud.facts, None
    if modelo == form_for_role("iva.periodic"):
        if iva_profile is None:
            raise FilingProducerSnapshotError("modelo 303 requires an explicitly declared IVA profile")
        return iva_profile, _resolve_m303_filing_facts_for_export(
            work_unit=work_unit,
            revision=revision,
            workflow_profile=workflow_profile,
            export_ports=export_ports,
            operation=operation,
        )
    if modelo == form_for_role("sociedades.instalment"):
        return Modelo202ProducerProfile(taxpayer_profile=workflow_profile, activities=()), None
    if modelo == form_for_role("withholding.work_periodic"):
        return Modelo111ProfileFacts(colegio_concertado=workflow_profile.colegio_concertado), None
    return GeneralFilingProfileFacts(), None


def _resolve_m303_filing_facts_for_export(
    *,
    work_unit: WorkUnit,
    revision: CalculationRevision,
    workflow_profile: TaxpayerProfile,
    export_ports: ModeloExportPorts,
    operation: PinnedAuthorityOperation,
) -> M303FilingFacts:
    filing_instance_evidence = require_filing_instance_evidence_for_work_unit(
        work_unit=work_unit,
        revision=revision,
    )
    if filing_instance_evidence is None:
        raise ModeloExportEvidenceMissingError(
            f"work unit {work_unit.work_unit_id!r} carries no filing-instance evidence valid for its revision",
        )
    prorrata_register_repository = export_ports.prorrata_register
    prorrata_register = require_prorrata_register_coordinates_current(
        prorrata_register_repository.load(),
        operation=operation,
    )
    bienes_register = export_ports.bienes_inversion.load()
    iva_aggregation = aggregate_iva_ledger_observations_from_repositories(
        bucket_id=work_unit.bucket_id,
        period=work_unit.period,
        prorrata_register_repository=prorrata_register_repository,
        transaction_repository=export_ports.transaction,
        investment_asset_register=bienes_register,
        investment_asset_profile_id=work_unit.bucket_id,
        operation=operation,
    )
    (
        differentiated_contributions,
        bienes_register,
        regularisation_result,
        bienes_parameters,
    ) = resolve_m303_export_arrivals(
        period=filing_instance_evidence.m303.period,
        prorrata_register=prorrata_register,
        iva_aggregation=iva_aggregation,
        bienes_register=bienes_register,
        operation=operation,
    )
    filing_facts = resolve_m303_filing_facts(
        evidence=filing_instance_evidence,
        supplier_regime=resolve_m303_supplier_regime_arrival(
            period=work_unit.period,
            iva_aggregation=iva_aggregation,
        ),
        prorrata_transition=resolve_m303_prorrata_transition_arrival(
            period=work_unit.period,
            prorrata_register=prorrata_register,
            operation=operation,
        ),
        prorrata_register=prorrata_register,
        differentiated_contributions=differentiated_contributions,
        bienes_register=bienes_register,
        regularisation_result=regularisation_result,
        bienes_parameters=bienes_parameters,
    )
    require_m303_regimen_simplificado_scope_matches_profile(
        filing_facts=filing_facts,
        workflow_profile=workflow_profile,
    )
    return filing_facts


def export_completeness_unverified(work_unit: WorkUnit, schema_provider: RegistrySchemaAccessor) -> bool:
    """Re-read the export subview after publication and report missing completeness."""
    _export_subview = schema_provider.get_subview(str(work_unit.modelo))
    _export_layout = _export_subview.export_layouts[0] if _export_subview.export_layouts else None
    completeness_unverified = (
        _export_layout is not None
        and _export_layout.format is ExportLayoutFormat.FIXED_WIDTH
        and _export_subview.completeness_manifest is None
    )

    return completeness_unverified
