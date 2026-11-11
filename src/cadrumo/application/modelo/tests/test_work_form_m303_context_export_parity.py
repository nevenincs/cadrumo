"""The Modelo 303 form shows every identification answer the exported file carries.

One real form load and one real envelope render read the same saved filing
evidence, the same profile and the same ledger and register arrivals, for every
filing year the registry supports. The expected codes are the ones the form
layout's own choices declare, written down independently of the producers.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import cast

import pytest

from ....core.external_constants import OutputLanguage
from ....core.modelo import Modelo
from ....core.period import Period
from ....core.prior_domiciliation_election import PriorDomiciliationElection
from ....core.prorrata_register import ProrrataEspecialTransitionKind, ProrrataRegisterRegime
from ....core.result_disposition import ResultDisposition
from ....domain.bienes_inversion.register import BienesInversionIvaRegister
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.schema_exports import ExportLayoutDefinition
from ....domain.calculations.registry.schema_form_layouts import FormContextFieldBlock
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.calculations.registry.tests.published_authority import (
    leased_profile_create_context,
    published_supported_filing_years,
)
from ....domain.filing.schema import ModeloDraft
from ....domain.filing.software_identity import AeatProductSoftwareEvidence, AeatProductSoftwareIdentity
from ....domain.invoices.catalogue import InvoiceCatalogue
from ....domain.iva.schema import IvaCashAccountingPaymentEvidence, IvaCashAccountingTreatment
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.calculation_revision_m303_handoff import FilingInstanceEvidence, M303FilingInstanceEvidence
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    VerificationReportCatalogueRepositoryProtocol,
)
from ....domain.modelos.verification_report import VerificationReportCatalogue
from ....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from ....domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ....domain.prorrata_register.register import (
    ProrrataEspecialTransitionEvidence,
    ProrrataRegister,
    ProrrataRegisterEntry,
)
from ....domain.submission.models import ModeloDraftStatus
from ....domain.transactions.date_partition import LedgerDatePartition
from ....domain.transactions.enums import TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.user_profile.errors import ProfileNotFoundError
from ....domain.user_profile.values import (
    ProfileSetupState,
    UserProfileFact,
    UserProfileRecord,
    create_user_profile_record,
)
from ...aggregation.tests.iva_cash_accounting_support import cash_accounting_transaction
from ...calculations.tests.filing_evidence import general_m303_filing_evidence
from ...filing.export import render_filing_envelope
from ...filing.export_envelope import FilingEnvelopeRenderRequest
from ...filing.producer_snapshot import (
    FilingModelProfileFacts,
    FilingProducerSnapshot,
    build_filing_producer_snapshot,
)
from ...filing.tests.producer_snapshot_support import (
    elections,
    m303_profile,
)
from ...user_profile.profile_record_repository import ProfileRecordRepository
from ..export_accounts import resolve_m303_filing_facts_from_arrivals
from ..export_ports import M303ArrivalPorts
from ..profile_export_binding import resolve_declaration_contact, resolve_export_identity
from ..value_presentation import absent_value_text
from ..work_form_localization import localized_heading
from ..work_form_models import ModeloFormContextFieldBlock, ModeloWorkForm
from ..work_form_service import load_modelo_work_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "13000000-0000-4000-8000-000000000456"
_NOW = datetime(2026, 1, 1, tzinfo=UTC)
_TAX_ID = "12345678Z"
_FIRST_PERIOD = "1T"
_LAST_PERIOD = "4T"
_SUPPORT = published_supported_filing_years()
assert _SUPPORT is not None
_YEARS = _SUPPORT.years

_IDENTITY_FACTS = {
    "identity.tax_id": _TAX_ID,
    "identity.name": "Ana",
    "identity.surnames": "Prueba Ejemplo",
    "taxpayer_type.entity_type": "natural_person",
}
#: What the operator answered. The form layout's choices declare the code each
#: answer prints: redeme yes = 1, general regime only = 3, cash accounting no = 2,
#: voluntary SII yes = 1; the joint return answer (yes = 1) is saved filing evidence.
_PROFILE_FACTS = {
    **_IDENTITY_FACTS,
    "tax_residence.jurisdiction_scope": "common_regime",
    "iva.m303_regime_composition": "general",
    "iva.redeme_enrolled": "true",
    "iva.cash_accounting_regime_enrolled": "false",
    "iva.voluntary_sii_enrolled": "true",
    "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
}


class _ProfileStore:
    record: UserProfileRecord | None = None

    def load(self, profile_id: str) -> UserProfileRecord:
        assert profile_id == _BUCKET
        if self.record is None:
            raise ProfileNotFoundError("synthetic absent profile")
        return self.record


class _ReadCatalogue[Catalogue]:
    def __init__(self, catalogue: Catalogue) -> None:
        self.catalogue = catalogue

    def load(self, *, operation: PinnedAuthorityOperation | None = None) -> Catalogue:
        return self.catalogue


class _Register:
    """The bucket's prorrata register, held in memory; the arrival fold only reads it."""

    bucket_id = _BUCKET

    def __init__(self, register: ProrrataRegister) -> None:
        self._register = register

    def load(self) -> ProrrataRegister:
        return self._register

    def load_revisioned(self) -> tuple[ProrrataRegister, str]:
        raise NotImplementedError

    def to_secure_object_write(self, register: ProrrataRegister, *, expected_revision_id: str | None = None):
        raise NotImplementedError


class _Bienes:
    def load(self) -> BienesInversionIvaRegister:
        return BienesInversionIvaRegister()

    def add(self, record: object) -> BienesInversionIvaRegister:
        raise NotImplementedError


class _Ledger:
    """The bucket's transactions, held in memory, every one inside the requested window."""

    bucket_id = _BUCKET

    def __init__(self, transactions: Iterable[Transaction]) -> None:
        self._catalogue = TransactionCatalogue.from_transactions(transactions)

    def exists(self) -> bool:
        return True

    def load(self) -> TransactionCatalogue:
        return self._catalogue

    def load_for_date_range(self, start: date, end: date) -> TransactionCatalogue:
        return self._catalogue

    def load_by_ids(self, transaction_ids: Iterable[str]) -> TransactionCatalogue:
        wanted = set(transaction_ids)
        return TransactionCatalogue.from_transactions(
            transaction for transaction in self._catalogue if transaction.transaction_id in wanted
        )

    def partition_by_date_range(self, start: date, end: date) -> LedgerDatePartition:
        return LedgerDatePartition(in_window=self._catalogue, index_complete=True)

    def save(self, catalogue: TransactionCatalogue) -> None:
        raise NotImplementedError


class _Invoices:
    bucket_id = _BUCKET

    def load(self) -> InvoiceCatalogue:
        return InvoiceCatalogue()


def _ports(register: ProrrataRegister, transactions: Iterable[Transaction] = ()) -> M303ArrivalPorts:
    return M303ArrivalPorts(
        prorrata_register=_Register(register),
        bienes_inversion=_Bienes(),
        transaction=_Ledger(transactions),
        invoices=_Invoices(),
    )


def _entry(year: int, regime: str, transition: ProrrataEspecialTransitionKind | None = None) -> ProrrataRegisterEntry:
    return ProrrataRegisterEntry(
        ejercicio=year,
        regime=ProrrataRegisterRegime.from_registry(regime),
        especial_transition=None
        if transition is None
        else ProrrataEspecialTransitionEvidence(kind=transition, evidence_reference=f"test:parity:{year}"),
        source_registry_snapshot_refs=(),
    )


def _cash_supplier_purchase(period: Period) -> Transaction:
    day = date(period.filing_year, period.start_date.month, 10)
    return cash_accounting_transaction(
        "supplier-regime-parity",
        direction=TransactionDirection.OUTGOING,
        booked_date=day,
        taxable_base=Decimal("100.00"),
        iva_amount=Decimal("21.00"),
        cash_accounting_treatment=IvaCashAccountingTreatment("supplier_regime"),
        operation_date=day,
        cash_accounting_payment_evidence=(
            IvaCashAccountingPaymentEvidence(
                payment_date=day, taxable_base=Decimal("100.00"), iva_amount=Decimal("21.00")
            ),
        ),
    )


@dataclass(frozen=True)
class _Scenario:
    """A ledger and register state and the codes the layout's choices declare for what it means."""

    name: str
    period_code: str
    arrivals: Callable[[int, Period], M303ArrivalPorts]
    #: destinatario-caja, opcion-prorrata, revocacion-prorrata; 0 is the code of a question the period does not ask.
    expected: dict[str, str]


_SCENARIOS = (
    _Scenario(
        "quarter-with-no-supplier-operations",
        _FIRST_PERIOD,
        lambda year, period: _ports(ProrrataRegister(entries=(_entry(year, "ninguna"),))),
        {"destinatario-caja": "2", "opcion-prorrata": "0", "revocacion-prorrata": "0"},
    ),
    _Scenario(
        "quarter-with-a-supplier-regime-purchase",
        _FIRST_PERIOD,
        lambda year, period: _ports(
            ProrrataRegister(entries=(_entry(year, "ninguna"),)), (_cash_supplier_purchase(period),)
        ),
        {"destinatario-caja": "1", "opcion-prorrata": "0", "revocacion-prorrata": "0"},
    ),
    _Scenario(
        "last-period-without-a-transition",
        _LAST_PERIOD,
        lambda year, period: _ports(ProrrataRegister(entries=(_entry(year, "ninguna"),))),
        {"destinatario-caja": "2", "opcion-prorrata": "2", "revocacion-prorrata": "2"},
    ),
    _Scenario(
        "last-period-with-the-special-option",
        _LAST_PERIOD,
        lambda year, period: _ports(
            ProrrataRegister(
                entries=(_entry(year, "especial", ProrrataEspecialTransitionKind.from_registry("opcion")),)
            )
        ),
        {"destinatario-caja": "2", "opcion-prorrata": "1", "revocacion-prorrata": "2"},
    ),
    _Scenario(
        "last-period-with-the-revocation",
        _LAST_PERIOD,
        lambda year, period: _ports(
            ProrrataRegister(
                entries=(
                    _entry(year - 1, "especial"),
                    _entry(year, "general", ProrrataEspecialTransitionKind.from_registry("revocacion")),
                )
            )
        ),
        {"destinatario-caja": "2", "opcion-prorrata": "2", "revocacion-prorrata": "1"},
    ),
)

#: The identification answers the profile and the saved evidence carry, by context id.
_EXPECTED = {
    "foral": "2",
    "redeme": "1",
    "regimen": "3",
    "conjunta": "1",
    "criterio-caja": "2",
    "sii": "1",
    "concurso": "2",
}


@pytest.fixture
def profile_store(monkeypatch: pytest.MonkeyPatch) -> _ProfileStore:
    """Stand in only for encrypted record I/O; fact indexing, projection and shaping run unchanged."""
    repository = _ProfileStore()
    monkeypatch.setattr(ProfileRecordRepository, "for_current_session", lambda *_args, **_kwargs: repository)
    return repository


def _record(facts: dict[str, str]) -> UserProfileRecord:
    return create_user_profile_record(
        profile_id=_BUCKET,
        setup_state=ProfileSetupState.COMPLETE,
        facts=tuple(UserProfileFact(path=path, value=value) for path, value in facts.items()),
        created_at=_NOW,
        updated_at=_NOW,
        context=leased_profile_create_context(),
    )


def _export_profile() -> FilingModelProfileFacts:
    """The IVA profile the operator's answers in ``_PROFILE_FACTS`` build, written out directly."""
    return m303_profile().model_copy(
        update={"redeme_enrolled": True, "cash_accounting_regime_enrolled": False, "voluntary_sii_enrolled": True}
    )


def _evidence(
    operation: PinnedAuthorityOperation, period: Period, *, joint_return_elected: bool
) -> FilingInstanceEvidence:
    saved = general_m303_filing_evidence(period, reference="test:context-parity", operation=operation).m303
    return FilingInstanceEvidence(
        m303=M303FilingInstanceEvidence(
            period=saved.period,
            joint_return_elected=joint_return_elected,
            annual_volume_nonzero=saved.annual_volume_nonzero,
            insolvency=saved.insolvency,
            exonerado_390=saved.exonerado_390,
            regimen_simplificado=saved.regimen_simplificado,
        )
    )


def _revision(snapshot: RegistrySnapshot, work_id: str, evidence: FilingInstanceEvidence) -> CalculationRevision:
    return CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id=work_id,
            input_values_by_casilla_id={},
            binding_overrides={},
            casilla_values={},
            source_transaction_ids=(),
            filing_instance_evidence=evidence,
            source_provenance=(),
        ),
        work_unit_id=work_id,
        registry_snapshot_ref=snapshot.snapshot_ref,
        state=CalculationRevisionState.BORRADOR,
        created_at=_NOW,
        updated_at=_NOW,
        filing_instance_evidence=evidence,
        source_provenance=(),
    )


def _load_form(
    operation: PinnedAuthorityOperation,
    year: int,
    evidence: FilingInstanceEvidence | None,
    *,
    period_code: str = _FIRST_PERIOD,
    arrivals: M303ArrivalPorts | None = None,
) -> tuple[ModeloWorkForm, RegistrySnapshot]:
    period = Period.from_year_and_code(year, period_code)
    snapshot = operation.reading_snapshot("303", filing_year=year, period=period_code)
    work_id = derive_work_unit_id(
        bucket_id=_BUCKET, modelo="303", filing_year=year, period=period, revision_id=snapshot.revision.id
    )
    revision = None if evidence is None else _revision(snapshot, work_id, evidence)
    unit = WorkUnit(
        work_unit_id=work_id,
        bucket_id=_BUCKET,
        modelo="303",
        filing_year=year,
        period=period,
        revision_id=snapshot.revision.id,
        name="Synthetic declaration",
        created_at=_NOW,
        updated_at=_NOW,
        current_calculation_revision_id=None if revision is None else revision.calculation_revision_id,
    )
    work_repository = cast(
        WorkUnitCatalogueRepositoryProtocol, cast(object, _ReadCatalogue(WorkUnitCatalogue(work_units={work_id: unit})))
    )
    calculation_repository = cast(
        CalculationRevisionCatalogueRepositoryProtocol,
        cast(
            object,
            _ReadCatalogue(
                CalculationRevisionCatalogue(
                    revisions={} if revision is None else {revision.calculation_revision_id: revision}
                )
            ),
        ),
    )
    verification_repository = cast(
        VerificationReportCatalogueRepositoryProtocol, cast(object, _ReadCatalogue(VerificationReportCatalogue()))
    )
    loaded = load_modelo_work_form(
        _BUCKET,
        ModeloCode("303"),
        year,
        period,
        operation=operation,
        work_unit_repository=work_repository,
        calculation_repository=calculation_repository,
        verification_repository=verification_repository,
        admission=None,
        language=OutputLanguage.ES,
        reference_on=_NOW.date(),
        m303_arrivals=arrivals,
    )
    return loaded.form, snapshot


def _context_blocks(
    operation: PinnedAuthorityOperation, snapshot: RegistrySnapshot
) -> dict[str, FormContextFieldBlock]:
    layout = operation.form_layout("303", snapshot.revision.id)
    assert layout is not None
    return {
        block.id: block
        for page in layout.pages
        for section in page.sections
        for block in section.blocks
        if isinstance(block, FormContextFieldBlock)
    }


def _shown(form: ModeloWorkForm) -> dict[str, str | None]:
    """Every context block the form shows, by id, as the words the operator reads."""
    return {
        block.id: block.value_text
        for page in form.pages
        for section in page.sections
        for block in section.blocks
        if isinstance(block, ModeloFormContextFieldBlock)
    }


def _choice_text(operation: PinnedAuthorityOperation, snapshot: RegistrySnapshot, context_id: str, code: str) -> str:
    choice = next(choice for choice in _context_blocks(operation, snapshot)[context_id].choices if choice.value == code)
    return localized_heading(choice.heading_key, choice.official_heading, "Opcion", OutputLanguage.ES).text


def _producer_snapshot(
    operation: PinnedAuthorityOperation,
    evidence: FilingInstanceEvidence,
    arrivals: M303ArrivalPorts,
) -> FilingProducerSnapshot:
    record = _record(_PROFILE_FACTS)
    identity = resolve_export_identity(bucket_id=_BUCKET, operation=operation, profile_record=record)
    assert identity is not None
    presenter, taxpayer = identity
    return build_filing_producer_snapshot(
        modelo=Modelo("303"),
        taxpayer_tax_id=_TAX_ID,
        taxpayer_identity=taxpayer,
        presenter=presenter,
        declaration_contact=resolve_declaration_contact(bucket_id=_BUCKET, operation=operation, profile_record=record),
        model_profile=_export_profile(),
        elections=elections(ResultDisposition.INGRESO),
        amendment_evidence=None,
        refund_account=None,
        charge_account=None,
        m303_filing_facts=resolve_m303_filing_facts_from_arrivals(
            bucket_id=_BUCKET,
            period=evidence.m303.period,
            evidence=evidence,
            arrivals=arrivals,
            operation=operation,
        ),
    )


def _decoded_export_fields(
    snapshot: RegistrySnapshot, producer_snapshot: FilingProducerSnapshot, addressed: frozenset[tuple[str, str]]
) -> dict[tuple[str, str], str]:
    """Render the real envelope for the addressed records and slice each addressed field back out."""
    (layout,) = snapshot.revision.export_layouts
    assert layout.filing_envelope is not None
    kept = {
        record.id: tuple(field for field in record.fields if (record.id, field.id) in addressed)
        for record in layout.records
        if any(record.id == record_id for record_id, _ in addressed)
    }
    assert {(record_id, field.id) for record_id, fields in kept.items() for field in fields} == addressed
    narrowed: ExportLayoutDefinition = layout.model_copy(
        update={
            "records": tuple(
                record.model_copy(update={"fields": kept[record.id]}) for record in layout.records if record.id in kept
            ),
            "filing_envelope": layout.filing_envelope.model_copy(update={"body_record_ids": tuple(kept)}),
        }
    )
    narrowed_snapshot = snapshot.model_copy(
        update={"revision": snapshot.revision.model_copy(update={"export_layouts": (narrowed,)})}
    )
    period = snapshot.filing_period
    assert period is not None
    draft = ModeloDraft(
        draft_id="d" + "0" * 63,
        modelo="303",
        period=period,
        profile_tax_id=_TAX_ID,
        subject_tax_id=_TAX_ID,
        snapshot_ref=RegistrySnapshotRef(
            modelo="303", revision_id=snapshot.revision.id, modelo_year=period.filing_year, period=period.registry_token
        ),
        status=ModeloDraftStatus.APROBADO,
        values=(),
        created_at=_NOW,
        updated_at=_NOW,
        schema_version=f"registry:303:{snapshot.revision.id}",
    )
    rendered = render_filing_envelope(
        FilingEnvelopeRenderRequest(
            registry_snapshot=narrowed_snapshot,
            layout=narrowed,
            draft=draft,
            producer_snapshot=producer_snapshot,
            prior_domiciliation_election=PriorDomiciliationElection.KEEP,
            product_software_identity=AeatProductSoftwareIdentity(
                program_identifier="C303",
                developer_tax_id="Y0001006P",
                evidence=(AeatProductSoftwareEvidence(reference="aeat-software-registration:parity", digest="a" * 64),),
            ),
        )
    )
    payloads = {item.record_id: item.payload for item in rendered.occurrences}
    decoded: dict[tuple[str, str], str] = {}
    for record in narrowed.records:
        for field in record.fields:
            assert field.offset is not None
            assert field.length is not None
            payload = payloads.get(record.id)
            raw = b"" if payload is None else payload[field.offset - 1 : field.offset - 1 + field.length]
            decoded[(record.id, field.id)] = raw.decode(record.encoding).strip()
    return decoded


def _expected_text(
    operation: PinnedAuthorityOperation, snapshot: RegistrySnapshot, block: FormContextFieldBlock, decoded: str
) -> str:
    """The words the form must show for what the export carries: a blank is no data, a code its choice."""
    if not decoded:
        return absent_value_text(OutputLanguage.ES)
    if block.choices:
        return _choice_text(operation, snapshot, block.id, decoded)
    return decoded


@pytest.mark.parametrize("year", _YEARS)
def test_form_identification_answers_equal_the_exported_fields(
    operation: PinnedAuthorityOperation, profile_store: _ProfileStore, year: int
) -> None:
    profile_store.record = _record(_PROFILE_FACTS)
    period = Period.from_year_and_code(year, _FIRST_PERIOD)
    evidence = _evidence(operation, period, joint_return_elected=True)
    arrivals = _SCENARIOS[0].arrivals(year, period)
    form, snapshot = _load_form(operation, year, evidence, arrivals=arrivals)
    blocks = _context_blocks(operation, snapshot)
    field_ids = {context_id: blocks[context_id].export_field_id for context_id in _EXPECTED}
    decoded = _decoded_export_fields(
        snapshot,
        _producer_snapshot(operation, evidence, arrivals),
        frozenset(("m303-declaration", field_id) for field_id in field_ids.values()),
    )
    shown = _shown(form)

    for context_id, expected_code in _EXPECTED.items():
        assert decoded[("m303-declaration", field_ids[context_id])] == expected_code, context_id
        assert shown[context_id] == _choice_text(operation, snapshot, context_id, expected_code), context_id


@pytest.mark.parametrize("scenario", _SCENARIOS, ids=lambda scenario: scenario.name)
@pytest.mark.parametrize("year", _YEARS)
def test_every_declared_context_field_equals_its_exported_field(
    operation: PinnedAuthorityOperation, profile_store: _ProfileStore, year: int, scenario: _Scenario
) -> None:
    profile_store.record = _record(_PROFILE_FACTS)
    period = Period.from_year_and_code(year, scenario.period_code)
    evidence = _evidence(operation, period, joint_return_elected=True)
    arrivals = scenario.arrivals(year, period)
    form, snapshot = _load_form(operation, year, evidence, period_code=scenario.period_code, arrivals=arrivals)
    shown = _shown(form)
    # Every context field the registry layout declares for the filing, not a hand list.
    declared = {
        context_id: block for context_id, block in _context_blocks(operation, snapshot).items() if context_id in shown
    }
    assert declared
    decoded = _decoded_export_fields(
        snapshot,
        _producer_snapshot(operation, evidence, arrivals),
        frozenset((block.export_record_id, block.export_field_id) for block in declared.values()),
    )

    for context_id, block in declared.items():
        code = decoded[(block.export_record_id, block.export_field_id)]
        assert shown[context_id] == _expected_text(operation, snapshot, block, code), (
            context_id,
            shown[context_id],
            code,
        )
    for context_id, expected_code in scenario.expected.items():
        block = declared[context_id]
        assert decoded[(block.export_record_id, block.export_field_id)] == expected_code, context_id
        assert shown[context_id] == _expected_text(operation, snapshot, block, expected_code), context_id


@pytest.mark.parametrize("year", _YEARS)
def test_form_shows_an_answered_no_and_an_unanswered_fact_differently(
    operation: PinnedAuthorityOperation, profile_store: _ProfileStore, year: int
) -> None:
    unanswered_form, snapshot = _load_form(operation, year, None)
    absent = absent_value_text(OutputLanguage.ES)
    for context_id in _EXPECTED:
        assert _shown(unanswered_form)[context_id] == absent, context_id

    profile_store.record = _record(
        {**_PROFILE_FACTS, "iva.redeme_enrolled": "false", "iva.voluntary_sii_enrolled": "false"}
    )
    period = Period.from_year_and_code(year, _FIRST_PERIOD)
    evidence = _evidence(operation, period, joint_return_elected=False)
    arrivals = _SCENARIOS[0].arrivals(year, period)
    answered_form, _ = _load_form(operation, year, evidence, arrivals=arrivals)
    shown = _shown(answered_form)
    for context_id in ("redeme", "conjunta", "criterio-caja", "sii", "destinatario-caja"):
        assert shown[context_id] == _choice_text(operation, snapshot, context_id, "2"), context_id


def test_incomplete_iva_block_leaves_the_enrolments_unknown_and_the_form_open(
    operation: PinnedAuthorityOperation, profile_store: _ProfileStore
) -> None:
    year = _YEARS[-1]
    profile_store.record = _record({**_IDENTITY_FACTS, "iva.redeme_enrolled": "true"})
    period = Period.from_year_and_code(year, _FIRST_PERIOD)
    evidence = _evidence(operation, period, joint_return_elected=True)
    form, snapshot = _load_form(operation, year, evidence, arrivals=_SCENARIOS[0].arrivals(year, period))
    absent = absent_value_text(OutputLanguage.ES)
    shown = _shown(form)
    for context_id in ("foral", "redeme", "regimen", "criterio-caja", "sii"):
        assert shown[context_id] == absent, context_id
    assert shown["conjunta"] == _choice_text(operation, snapshot, "conjunta", "1")


def test_a_refused_arrival_fold_leaves_only_its_answers_unknown_and_the_form_open(
    operation: PinnedAuthorityOperation, profile_store: _ProfileStore
) -> None:
    year = _YEARS[-1]
    profile_store.record = _record(_PROFILE_FACTS)
    period = Period.from_year_and_code(year, _LAST_PERIOD)
    evidence = _evidence(operation, period, joint_return_elected=True)
    # The final period needs the year's register entry; its absence refuses the export's fold.
    form, snapshot = _load_form(
        operation, year, evidence, period_code=_LAST_PERIOD, arrivals=_ports(ProrrataRegister(entries=()))
    )
    shown = _shown(form)
    absent = absent_value_text(OutputLanguage.ES)
    for context_id in ("destinatario-caja", "opcion-prorrata", "revocacion-prorrata"):
        assert shown[context_id] == absent, context_id
    assert shown["conjunta"] == _choice_text(operation, snapshot, "conjunta", "1")
