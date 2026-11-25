"""Read one declaration's editor workbench inside the profile worker.

These are the reads behind the workbench's registered operations: the form with
its lazily admitted edit baseline and the facts every action is judged against,
one casilla's help, the source boxes a refused Apply's prerequisite names, and
the filing state: what exporting and recording the filing rest on, from the
same form and the same builders as the form read, with no edit admitted.
They run under the worker's pinned authority against the profile's repositories;
the frontend receives only their typed results.

Opening a declaration's workbench is the start of its edit session, so the form
read admits the edit baseline that every parse and apply is judged against. An
admission refusal is part of the result, never hidden as "no edit surface".

Core types: :class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`.

It works with :class:`CalculationRevision`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ...core.casilla_id import CasillaId
from ...core.external_constants import OutputLanguage
from ...core.identity.documents import SpanishTaxIdFormat
from ...core.identity.hex_ids import CalculationRevisionId
from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.calculations.registry.bindings_previous_filing import PreviousFilingProvider
from ...domain.calculations.registry.form_codes import form_for_role
from ...domain.calculations.registry.tax_id_format import runtime_tax_id_format
from ...domain.modelos.calculation_revision import CalculationRevision
from ...domain.modelos.verification_report import VerificationReport
from ...domain.modelos.work_unit import WorkUnit
from ...domain.period import calculation_filing_date
from ...domain.user_profile.labels import profile_field_label
from ..actividad_asset.ports import ActivityAssetHistoryRepository
from ..user_profile.access_errors import ProfileAccessRefusedError
from ..user_profile.projections import record_to_path_values
from .calculation_preparation import ledger_hold_words, ledger_preflight_hold
from .casilla_help import ModeloCasillaHelpCardV1, build_casilla_help_card
from .credit_resolution_repository import CreditResolutionReader
from .edit_admission import admit_modelo_edit_baseline, modelo_edit_ground
from .edit_models import ModeloEditAdmissionResultV1, ModeloEditRefusedV1
from .edit_refusal_projection import ModeloEditCalculationPrerequisiteV1
from .edit_review_wording import edit_refusal_words
from .export_ports import M303ArrivalPorts
from .m303_exonerado_390_applicability_attestation import modelo_390_question_asked
from .profile_readiness_gate import modelo_work_profile_preflight_report
from .reconciliation_sources import (
    ReconciliationSourceNeed,
    ReconciliationSourceRequirementV1,
    reconciliation_source_requirements,
)
from .verification_report_facts import granting_verification_report
from .work_form_export_offer import ModeloFormExportOffer, ModeloFormReceipt, form_export_offer, form_receipt
from .work_form_facts import ModeloFormFacts
from .work_form_header import (
    ModeloFormFilingHeader,
    ModeloFormHeader,
    form_filing_header,
    form_header,
    form_recorded,
)
from .work_form_issue_lines import ModeloFormIssueLine, ModeloFormVerdict, form_issue_lines
from .work_form_next_step import ModeloFormNextStep, form_next_step, registry_grade_refusal
from .work_form_service import (
    ModeloWorkFormLoadV1,
    ModeloWorkFormSummaryLoad,
    load_modelo_work_form,
    load_modelo_work_form_summary,
    modelo_form_snapshot,
)
from .work_form_typing_effect import ModeloFormTypingEffect, form_typing_effects

if TYPE_CHECKING:
    from ...domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.calculations.registry.schema import RegistrySnapshot
    from ...domain.modelos.calculation_revision import CalculationRevisionCatalogue
    from ...domain.modelos.filing_record import ModeloRecordCatalogue
    from ...domain.modelos.protocols import (
        CalculationRevisionCatalogueRepositoryProtocol,
        ModeloRecordCatalogueRepositoryProtocol,
        VerificationReportCatalogueRepositoryProtocol,
    )
    from ...domain.modelos.work_unit import WorkUnitCatalogue
    from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
    from ...domain.transactions.own_accounts import OwnAccountRegister
    from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
    from ..calculations.observations_repository import CalculationObservationRepositoryProtocol
    from ..invoices.catalogue_reads_ports import InvoiceCatalogueReader
    from ..ledger.usage_ratio_repository import UsageRatioProfileLoader
    from ..live.borrador_100 import Borrador100SnapshotRepository
    from ..operations.registry import OperationPublicContractSetV1
    from .export_ports import OwnAccountRegisterReaderProtocol
    from .work_profile import ModeloWorkProfile


@dataclass(frozen=True, slots=True)
class ModeloWorkbenchLedgerPorts:
    """The profile's ledger, read so the to-do list names the movement calculation would refuse on."""

    transactions: TransactionCatalogueRepositoryProtocol
    invoices: InvoiceCatalogueReader
    usage_ratios: UsageRatioProfileLoader


class ModeloFormLedgerHold(BaseModel):
    """What in the ledger holds the declaration's calculation, in the form's language.

    ``transaction_id`` is the movement to open, ``None`` when the hold is about
    the whole period rather than one movement.
    """

    model_config = STRICT_FROZEN_CONFIG

    words: str = Field(min_length=1)
    transaction_id: str | None


@dataclass(frozen=True, slots=True)
class ModeloWorkbenchReadPorts:
    """The profile repositories one declaration's workbench is read from.

    ``borrador_snapshots`` is the profile's AEAT draft store, read to say when
    replayed AEAT data was imported; ``bucket_events`` is
    the profile's event history, read to say when the latest file for the AEAT
    was created and whether it still matches; ``filings`` is the profile's
    filing records, read to say whether a recorded filing's AEAT receipt is
    verified; ``own_accounts`` is the taxpayer's own-account register, read to
    offer the accounts AEAT debits and pays a refund into; ``credit_resolutions``
    is the store of accepted source disagreements, read so the form holds filing
    exactly where the gate does; ``profile`` loads the taxpayer profile, read so
    the to-do list names the profile details the readiness gate still asks for;
    ``ledger`` is the profile's ledger, read so the to-do list names the
    movement or period fact calculation would be refused for.
    ``m303_arrivals`` are the ledger and register repositories a Modelo 303 period
    facts are folded from, as its export folds them.
    ``reconciliation_sources`` reads where each declaration an annual summary
    sums stands, the same reader its calculation's refusal names them from.
    ``observations`` is the profile's store of captured filed observations; with
    ``filings`` it shows which earlier declarations the application holds nothing
    of, so the form offers a stated figure for a carry that follows them, and it
    shows whether one the calculation found nothing of is held now, so the form
    offers working it out again.
    """

    work_units: WorkUnitCatalogueRepositoryProtocol
    calculations: CalculationRevisionCatalogueRepositoryProtocol
    verifications: VerificationReportCatalogueRepositoryProtocol
    activity_assets: ActivityAssetHistoryRepository | None = None
    borrador_snapshots: Borrador100SnapshotRepository | None = None
    bucket_events: BucketEventHistoryRepositoryProtocol | None = None
    filings: ModeloRecordCatalogueRepositoryProtocol | None = None
    own_accounts: OwnAccountRegisterReaderProtocol | None = None
    credit_resolutions: CreditResolutionReader | None = None
    m303_arrivals: M303ArrivalPorts | None = None
    profile: Callable[[], ModeloWorkProfile | None] | None = None
    ledger: ModeloWorkbenchLedgerPorts | None = None
    reconciliation_sources: Callable[[WorkUnit, RegistrySnapshot], tuple[ReconciliationSourceNeed, ...]] | None = None
    observations: CalculationObservationRepositoryProtocol | None = None
    store_epoch: Callable[[], str] | None = None
    """A digest of every row of the profile store all the ports above read, changing on any write to it."""


type ModeloWorkbenchReadPortsFactory = Callable[[str, PinnedAuthorityOperation], ModeloWorkbenchReadPorts]
"""Bind the workbench repositories to one profile under the worker's pinned authority."""


@dataclass(frozen=True, slots=True)
class ModeloWorkbenchFormReadV1:
    """One declaration's form and what every workbench action is judged against.

    ``admission`` is the edit baseline admitted with this read, or the typed
    refusal saying why the declaration cannot be edited. The calculation head
    and the verification report granting it are the ones the form shows, so
    Verify and File act on the revision the filer is looking at.
    """

    load: ModeloWorkFormLoadV1
    admission: ModeloEditAdmissionResultV1
    calculation_revision_id: str | None
    verification_report_id: str | None
    #: Whether the next calculation must first ask the ordinary Modelo 303 filing answers.
    asks_m303_evidence: bool
    #: Whether this Modelo 303 period asks the Modelo 390 exemption.
    asks_modelo_390: bool
    registry_revision_id: str
    #: The governed Spanish tax-identifier format the frontend parses NIF entries against.
    tax_id_format: SpanishTaxIdFormat
    #: What exporting offers: the artefacts this installation publishes, the elections and the file format.
    export_offer: ModeloFormExportOffer | None = None
    #: The recorded filing's AEAT receipt state; ``None`` when the declaration is not recorded as filed.
    receipt: ModeloFormReceipt | None = None
    #: The profile details the readiness gate still asks for before this declaration is worked out or filed,
    #: each as its label in the form's language; empty when the profile answers everything the gate asks.
    profile_requirements: tuple[str, ...] = ()
    #: What in the ledger holds calculating this declaration; ``None`` when its ledger is ready.
    ledger_hold: ModeloFormLedgerHold | None = None
    #: The declarations an annual summary sums whose filed figures are not there yet, each worded in the
    #: form's language with its step; the same answer its calculation's refusal names them from.
    source_requirements: tuple[ReconciliationSourceRequirementV1, ...] = ()

    @property
    def typing_effects(self) -> tuple[ModeloFormTypingEffect, ...]:
        """What typing a value over each box the filer can type on does, in the form's language."""
        form = self.load.form
        return form_typing_effects(form, form.language)

    @property
    def receipt_confirmed(self) -> bool | None:
        """Whether the recorded filing's AEAT receipt is verified; ``None`` when nothing is recorded or read."""
        return _receipt_confirmed(self.receipt)

    @property
    def rules_incomplete(self) -> bool:
        """Whether the registry rules for the revision stop short of calculation grade, so nothing can be worked out."""
        return registry_grade_refusal(self.admission)

    @property
    def admission_refusal_words(self) -> str | None:
        """Why the declaration cannot be edited, as one sentence in the form's language; ``None`` once admitted."""
        admission = self.admission
        if not isinstance(admission, ModeloEditRefusedV1):
            return None
        return edit_refusal_words(admission.refusal, self.load.form.language)

    @property
    def next_step(self) -> ModeloFormNextStep | None:
        """The one action the form offers next; ``None`` when the registry rules cannot calculate it at all."""
        load = self.load
        return _offered_next_step(
            load.form,
            verified=load.verified,
            filed=load.filed,
            rules_incomplete=self.rules_incomplete,
            receipt=self.receipt,
        )

    @property
    def header(self) -> ModeloFormHeader:
        """What the header states about the declaration, in the form's language."""
        load = self.load
        return form_header(load.form, load.form.language, verified=load.verified, filed=load.filed)

    @property
    def issue_lines(self) -> tuple[ModeloFormIssueLine, ...]:
        """What the check view lists, most urgent first, in the form's language."""
        form = self.load.form
        return form_issue_lines(form, form.language)

    @property
    def verdict(self) -> ModeloFormVerdict:
        """What the last check concluded, in the form's language."""
        return self.load.journey.verdict


def _receipt_confirmed(receipt: ModeloFormReceipt | None) -> bool | None:
    return None if receipt is None else receipt.verified


def _offered_next_step(
    form: ModeloFormFacts,
    *,
    verified: bool,
    filed: bool,
    rules_incomplete: bool,
    receipt: ModeloFormReceipt | None,
) -> ModeloFormNextStep | None:
    """The one action the form offers next, as both workbench reads state it; ``None`` when nothing is calculable."""
    if rules_incomplete:
        return None
    return form_next_step(form, verified=verified, filed=filed, receipt_confirmed=_receipt_confirmed(receipt))


def _work_unit(work_unit_id: str, *, bucket_id: str, ports: ModeloWorkbenchReadPorts) -> WorkUnit:
    return _owned_work_unit(ports.work_units.load(), work_unit_id, bucket_id=bucket_id)


def _owned_work_unit(catalogue: WorkUnitCatalogue, work_unit_id: str, *, bucket_id: str) -> WorkUnit:
    unit = catalogue.get(work_unit_id)
    if unit is None or unit.bucket_id != bucket_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return unit


@dataclass(frozen=True, slots=True)
class ModeloWorkbenchFilingStateReadV1:
    """What exporting and recording one declaration's filing rest on, read as the form read reads it.

    Every field is the one :class:`ModeloWorkbenchFormReadV1` holds under its
    name, built by the same functions from the summary the form read presents,
    so the two reads of one stored state agree. It admits no edit baseline:
    nothing it states depends on what may be edited, and whether the rules
    reach calculation grade is decided by the admission's own checks without
    issuing one.
    """

    load: ModeloWorkFormSummaryLoad
    calculation_revision_id: str | None
    verification_report_id: str | None
    #: What exporting offers: the artefacts, whether recording is available, the elections and the file format.
    export_offer: ModeloFormExportOffer
    #: The recorded filing's AEAT receipt state; ``None`` when the declaration is not recorded as filed.
    receipt: ModeloFormReceipt | None
    #: Whether the registry rules for the revision stop short of calculation grade, so nothing can be worked out.
    rules_incomplete: bool

    @property
    def header(self) -> ModeloFormFilingHeader:
        """The result, the latest file and the export hold the form's header states, in the form's language."""
        load = self.load
        summary = load.summary
        return form_filing_header(summary, summary.language, verified=load.verified, filed=load.filed)

    @property
    def next_step(self) -> ModeloFormNextStep | None:
        """The one action the form offers next; ``None`` when the registry rules cannot calculate it at all."""
        load = self.load
        return _offered_next_step(
            load.summary,
            verified=load.verified,
            filed=load.filed,
            rules_incomplete=self.rules_incomplete,
            receipt=self.receipt,
        )


@dataclass(frozen=True, slots=True)
class _FilingFacts:
    """The calculation head, its granting report and what exporting and recording the form offer."""

    head: CalculationRevision | None
    verification_report_id: str | None
    snapshot: RegistrySnapshot
    export_offer: ModeloFormExportOffer
    receipt: ModeloFormReceipt | None


def _load_form(
    unit: WorkUnit,
    *,
    ports: ModeloWorkbenchReadPorts,
    operation: PinnedAuthorityOperation,
    calculation_catalogue: CalculationRevisionCatalogue,
    admission: ModeloEditAdmissionResultV1 | None,
    language: OutputLanguage,
) -> ModeloWorkFormLoadV1:
    """The declaration's form, read from the workbench's repositories."""
    return load_modelo_work_form(
        unit.bucket_id,
        unit.modelo,
        unit.filing_year,
        unit.period,
        operation=operation,
        work_unit_repository=ports.work_units,
        calculation_repository=ports.calculations,
        verification_repository=ports.verifications,
        calculation_catalogue=calculation_catalogue,
        admission=admission,
        language=language,
        borrador_snapshots=ports.borrador_snapshots,
        bucket_events=ports.bucket_events,
        activity_assets=ports.activity_assets,
        credit_resolutions=ports.credit_resolutions,
        transactions=_ledger_transactions(ports),
        m303_arrivals=ports.m303_arrivals,
        observations=ports.observations,
    )


def _filing_facts(
    unit: WorkUnit,
    form: ModeloFormFacts,
    *,
    verified: bool,
    filed: bool,
    ports: ModeloWorkbenchReadPorts,
    operation: PinnedAuthorityOperation,
    language: OutputLanguage,
) -> _FilingFacts:
    """The head the form shows, the report granting it, and what exporting and recording offer now."""
    head, report = _head_and_report(form.calculation_revision_id, ports=ports, operation=operation)
    snapshot = modelo_form_snapshot(operation, unit.modelo, unit.filing_year, unit.period, form.registry_revision_id)
    return _FilingFacts(
        head=head,
        verification_report_id=None if report is None else report.verification_report_id,
        snapshot=snapshot,
        export_offer=form_export_offer(
            str(unit.modelo),
            snapshot,
            language,
            form=form,
            verified=verified,
            filed=filed,
            own_accounts=_own_accounts(ports),
            amended=_is_amendment(head),
        ),
        receipt=_receipt(unit, form, filed=filed, ports=ports, language=language),
    )


def _admit(
    work_unit_id: str,
    *,
    ports: ModeloWorkbenchReadPorts,
    operation: PinnedAuthorityOperation,
    operation_contracts: OperationPublicContractSetV1,
    calculation_catalogue: CalculationRevisionCatalogue,
) -> ModeloEditAdmissionResultV1:
    return admit_modelo_edit_baseline(
        work_unit_id=work_unit_id,
        work_catalogue=ports.work_units.load(),
        calculation_catalogue=calculation_catalogue,
        operation=operation,
        operation_contracts=operation_contracts,
        observation_repository=ports.observations,
        filing_catalogue=_filing_catalogue(ports),
    )


def admit_workbench_form_edit(
    work_unit_id: str,
    *,
    bucket_id: str,
    ports: ModeloWorkbenchReadPorts,
    operation: PinnedAuthorityOperation,
    operation_contracts: OperationPublicContractSetV1,
) -> ModeloEditAdmissionResultV1:
    """Admit the edit baseline a form read issues, as that read would, for a declaration of this profile."""
    _work_unit(work_unit_id, bucket_id=bucket_id, ports=ports)
    return _admit(
        work_unit_id,
        ports=ports,
        operation=operation,
        operation_contracts=operation_contracts,
        calculation_catalogue=ports.calculations.load(operation=operation),
    )


def read_modelo_workbench_form(
    work_unit_id: str,
    *,
    bucket_id: str,
    ports: ModeloWorkbenchReadPorts,
    operation: PinnedAuthorityOperation,
    operation_contracts: OperationPublicContractSetV1,
    language: OutputLanguage,
    admission: ModeloEditAdmissionResultV1 | None = None,
) -> ModeloWorkbenchFormReadV1:
    """Admit an edit baseline, read the declaration's form and the facts its actions need.

    ``admission`` is one the caller admitted for this declaration just before, through
    :func:`admit_workbench_form_edit`; without it the read admits its own.
    """
    unit = _work_unit(work_unit_id, bucket_id=bucket_id, ports=ports)
    calculation_catalogue = ports.calculations.load(operation=operation)
    if admission is None:
        admission = _admit(
            work_unit_id,
            ports=ports,
            operation=operation,
            operation_contracts=operation_contracts,
            calculation_catalogue=calculation_catalogue,
        )
    loaded = _load_form(
        unit,
        ports=ports,
        operation=operation,
        calculation_catalogue=calculation_catalogue,
        admission=admission,
        language=language,
    )
    form = loaded.form
    facts = _filing_facts(
        unit,
        form,
        verified=loaded.verified,
        filed=loaded.filed,
        ports=ports,
        operation=operation,
        language=language,
    )
    is_m303 = str(unit.modelo) == form_for_role("iva.periodic")
    profile = _loaded_profile(ports)
    return ModeloWorkbenchFormReadV1(
        load=loaded,
        admission=admission,
        calculation_revision_id=form.calculation_revision_id,
        verification_report_id=facts.verification_report_id,
        asks_m303_evidence=is_m303 and _lacks_filing_instance_evidence(facts.head),
        asks_modelo_390=is_m303 and modelo_390_question_asked(unit.period, operation=operation),
        registry_revision_id=form.registry_revision_id,
        tax_id_format=runtime_tax_id_format(authority=operation),
        export_offer=facts.export_offer,
        receipt=facts.receipt,
        profile_requirements=_profile_requirements(unit, profile, operation=operation, language=language),
        ledger_hold=_ledger_hold(
            unit, form.registry_revision_id, profile, ports=ports, operation=operation, language=language
        ),
        source_requirements=_source_requirements(unit, facts.snapshot, ports=ports, language=language),
    )


def read_modelo_workbench_filing_state(
    work_unit_id: str,
    *,
    bucket_id: str,
    ports: ModeloWorkbenchReadPorts,
    operation: PinnedAuthorityOperation,
    language: OutputLanguage,
) -> ModeloWorkbenchFilingStateReadV1:
    """Read the declaration's classified form and what exporting and recording its filing rest on, admitting no edit.

    The summary is the one the form read presents
    (:func:`~.work_form_service.load_modelo_work_form_summary`): the export
    hold, the result, the next step, the journey and the elections count over
    its classified boxes, and no field is presented.
    What may be edited never enters those answers, so no edit baseline is
    admitted. Whether the rules reach calculation grade is the refusal the
    admission's own ground checks reach, so the next step is withheld exactly
    where the form read withholds it.
    """
    work_catalogue = ports.work_units.load()
    unit = _owned_work_unit(work_catalogue, work_unit_id, bucket_id=bucket_id)
    calculation_catalogue = ports.calculations.load(operation=operation)
    ground = modelo_edit_ground(
        work_unit_id=work_unit_id,
        work_catalogue=work_catalogue,
        calculation_catalogue=calculation_catalogue,
        operation=operation,
    )
    loaded = load_modelo_work_form_summary(
        unit.bucket_id,
        unit.modelo,
        unit.filing_year,
        unit.period,
        operation=operation,
        work_unit_repository=ports.work_units,
        calculation_repository=ports.calculations,
        verification_repository=ports.verifications,
        calculation_catalogue=calculation_catalogue,
        language=language,
        bucket_events=ports.bucket_events,
        activity_assets=ports.activity_assets,
        credit_resolutions=ports.credit_resolutions,
        transactions=_ledger_transactions(ports),
        observations=ports.observations,
    )
    facts = _filing_facts(
        unit,
        loaded.summary,
        verified=loaded.verified,
        filed=loaded.filed,
        ports=ports,
        operation=operation,
        language=language,
    )
    return ModeloWorkbenchFilingStateReadV1(
        load=loaded,
        calculation_revision_id=loaded.summary.calculation_revision_id,
        verification_report_id=facts.verification_report_id,
        export_offer=facts.export_offer,
        receipt=facts.receipt,
        rules_incomplete=isinstance(ground, ModeloEditRefusedV1) and registry_grade_refusal(ground),
    )


def _filing_catalogue(ports: ModeloWorkbenchReadPorts) -> ModeloRecordCatalogue | None:
    return None if ports.filings is None else ports.filings.load()


def _ledger_transactions(ports: ModeloWorkbenchReadPorts) -> TransactionCatalogueRepositoryProtocol | None:
    return None if ports.ledger is None else ports.ledger.transactions


def _loaded_profile(ports: ModeloWorkbenchReadPorts) -> ModeloWorkProfile | None:
    load_profile = ports.profile
    return None if load_profile is None else load_profile()


def _own_accounts(ports: ModeloWorkbenchReadPorts) -> OwnAccountRegister | None:
    return None if ports.own_accounts is None else ports.own_accounts.load()


def _lacks_filing_instance_evidence(head: CalculationRevision | None) -> bool:
    return head is None or head.filing_instance_evidence is None


def _is_amendment(head: CalculationRevision | None) -> bool:
    return head is not None and head.amendment_identity is not None


def _source_requirements(
    unit: WorkUnit, snapshot: RegistrySnapshot, *, ports: ModeloWorkbenchReadPorts, language: OutputLanguage
) -> tuple[ReconciliationSourceRequirementV1, ...]:
    """The sources an annual summary reconciles against, worded in ``language``; none without a reader."""
    if ports.reconciliation_sources is None:
        return ()
    return reconciliation_source_requirements(ports.reconciliation_sources(unit, snapshot), language)


def _head_and_report(
    head_id: CalculationRevisionId | None, *, ports: ModeloWorkbenchReadPorts, operation: PinnedAuthorityOperation
) -> tuple[CalculationRevision | None, VerificationReport | None]:
    """The form's calculation head and the verification report granting it, both absent without a head."""
    if head_id is None:
        return None, None
    head = ports.calculations.load(operation=operation).get(head_id)
    if head is None:
        return None, None
    return head, granting_verification_report(ports.verifications.load(operation=operation), head)


def _ledger_hold(
    unit: WorkUnit,
    registry_revision_id: str,
    profile: ModeloWorkProfile | None,
    *,
    ports: ModeloWorkbenchReadPorts,
    operation: PinnedAuthorityOperation,
    language: OutputLanguage,
) -> ModeloFormLedgerHold | None:
    """The ledger issue calculating this declaration would be refused for, read through the refusal's own check."""
    ledger = ports.ledger
    if ledger is None:
        return None
    hold = ledger_preflight_hold(
        work_unit=unit,
        revision=modelo_form_snapshot(
            operation, unit.modelo, unit.filing_year, unit.period, registry_revision_id
        ).revision,
        transaction_repository=ledger.transactions,
        invoice_reader=ledger.invoices,
        usage_ratio_profile_loader=ledger.usage_ratios,
        operation=operation,
        profile_values={} if profile is None else record_to_path_values(profile.record),
        language=language,
    )
    if hold is None:
        return None
    movement = hold.movement
    return ModeloFormLedgerHold(
        words=ledger_hold_words(hold, language),
        transaction_id=None if movement is None else movement.transaction_id,
    )


def _profile_requirements(
    unit: WorkUnit,
    profile: ModeloWorkProfile | None,
    *,
    operation: PinnedAuthorityOperation,
    language: OutputLanguage,
) -> tuple[str, ...]:
    """The labels of the profile details the readiness gate refuses this declaration's work without.

    Read from the same report the gate enforces, so the to-do list asks exactly what
    calculating or filing would be refused for, such as the fact deciding the period.
    """
    if profile is None:
        return ()
    report = modelo_work_profile_preflight_report(
        record=profile.record,
        modelo=str(unit.modelo),
        revision_id=unit.revision_id,
        filing_year=unit.filing_year,
        period=unit.period,
        profile_decode_context=profile.profile_decode_context,
        operation=operation,
    )
    schema = profile.profile_decode_context.schema
    labels: list[str] = []
    for requirement in report.missing:
        section = next((item for item in schema.sections if item.key == requirement.section_key), None)
        field = None if section is None else next((f for f in section.fields if f.key == requirement.field_key), None)
        labels.append(
            requirement.label
            if field is None
            else profile_field_label(requirement.section_key, field, locale=language.value)
        )
    return tuple(labels)


def _receipt(
    unit: WorkUnit,
    form: ModeloFormFacts,
    *,
    filed: bool,
    ports: ModeloWorkbenchReadPorts,
    language: OutputLanguage,
) -> ModeloFormReceipt | None:
    """The recorded filing's receipt state, read from the unit's current filing record."""
    if ports.filings is None or not form_recorded(form, filed=filed):
        return None
    record_id = unit.current_filing_record_id
    record = None if record_id is None else ports.filings.load().get(record_id)
    if record is not None and (record.bucket_id != unit.bucket_id or record.work_unit_id != unit.work_unit_id):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    filing = form.filing
    return form_receipt(record, recorded_at=None if filing is None else filing.recorded_at, language=language)


def read_modelo_casilla_help(
    work_unit_id: str,
    casilla_id: CasillaId,
    *,
    bucket_id: str,
    registry_revision_id: str,
    calculation_revision_id: str | None,
    ports: ModeloWorkbenchReadPorts,
    operation: PinnedAuthorityOperation,
    language: OutputLanguage,
) -> ModeloCasillaHelpCardV1:
    """Assemble one casilla's help from the revision and the calculation the form showed."""
    unit = _work_unit(work_unit_id, bucket_id=bucket_id, ports=ports)
    snapshot = modelo_form_snapshot(operation, unit.modelo, unit.filing_year, unit.period, registry_revision_id)
    head = (
        None
        if calculation_revision_id is None
        else ports.calculations.load(operation=operation).get(calculation_revision_id)
    )
    if head is not None and head.work_unit_id != unit.work_unit_id:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    observation = (
        None if head is None else next((item for item in head.observations if item.casilla_id == casilla_id), None)
    )
    return build_casilla_help_card(
        casilla_id,
        snapshot=snapshot,
        operation=operation,
        language=language,
        on=calculation_filing_date(unit.period, authority=operation),
        observation=observation,
    )


def modelo_edit_prerequisite_source_boxes(
    prerequisite: ModeloEditCalculationPrerequisiteV1,
    *,
    bucket_id: str,
    registry_revision_id: str,
    ports: ModeloWorkbenchReadPorts,
    operation: PinnedAuthorityOperation,
) -> tuple[CasillaId, ...]:
    """Name the earlier-filing boxes the prerequisite's bindings read, in declaration order."""
    unit = _work_unit(prerequisite.work_unit_id, bucket_id=bucket_id, ports=ports)
    snapshot = modelo_form_snapshot(operation, unit.modelo, unit.filing_year, unit.period, registry_revision_id)
    providers = (binding.provider for binding in snapshot.revision.bindings if binding.id in prerequisite.binding_ids)
    return tuple(
        dict.fromkeys(
            box
            for provider in providers
            if isinstance(provider, PreviousFilingProvider)
            for box in (
                *provider.source_casilla_ids,
                *(
                    (provider.source_casilla_id,)
                    if (provider.source_casilla_id is not None and provider.source_casilla_id)
                    else ()
                ),
            )
        )
    )


__all__ = [
    "ModeloWorkbenchFilingStateReadV1",
    "ModeloWorkbenchFormReadV1",
    "ModeloWorkbenchReadPorts",
    "ModeloWorkbenchReadPortsFactory",
    "admit_workbench_form_edit",
    "modelo_edit_prerequisite_source_boxes",
    "read_modelo_casilla_help",
    "read_modelo_workbench_filing_state",
    "read_modelo_workbench_form",
]
