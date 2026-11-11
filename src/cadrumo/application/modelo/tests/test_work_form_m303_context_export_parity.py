"""The Modelo 303 form shows the identification answers the exported file carries.

One real form load and one real envelope render read the same saved filing
evidence and the same profile, for every filing year the registry supports.
The expected codes are the ones the form layout's own choices declare.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

import pytest

from ....core.external_constants import OutputLanguage
from ....core.modelo import Modelo
from ....core.period import Period
from ....core.prior_domiciliation_election import PriorDomiciliationElection
from ....core.result_disposition import ResultDisposition
from ....domain.bienes_inversion.tests.explicit_parameters import params_for
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
from ....domain.submission.models import ModeloDraftStatus
from ....domain.user_profile.errors import ProfileNotFoundError
from ....domain.user_profile.values import (
    ProfileSetupState,
    UserProfileFact,
    UserProfileRecord,
    create_user_profile_record,
)
from ...aggregation.m303_arrivals import M303SupplierRegimeArrival, resolve_m303_prorrata_transition_arrival
from ...calculations.tests.filing_evidence import general_m303_filing_evidence
from ...filing.export import render_filing_envelope
from ...filing.export_envelope import FilingEnvelopeRenderRequest
from ...filing.producer_snapshot import (
    FilingModelProfileFacts,
    FilingProducerSnapshot,
    build_filing_producer_snapshot,
    resolve_m303_filing_facts,
)
from ...filing.tests.producer_snapshot_support import (
    elections,
    empty_m303_export_arrivals,
    m303_profile,
    producer_snapshot_presenter,
    taxpayer_identity,
)
from ...user_profile.profile_record_repository import ProfileRecordRepository
from ..value_presentation import absent_value_text
from ..work_form_localization import localized_heading
from ..work_form_models import ModeloFormContextFieldBlock, ModeloWorkForm
from ..work_form_service import load_modelo_work_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "13000000-0000-4000-8000-000000000456"
_NOW = datetime(2026, 1, 1, tzinfo=UTC)
_TAX_ID = "12345678Z"
_PERIOD_CODE = "1T"
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
_EXPECTED = {
    "foral": "2",
    "redeme": "1",
    "regimen": "3",
    "conjunta": "1",
    "criterio-caja": "2",
    "sii": "1",
    "concurso": "2",
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
    operation: PinnedAuthorityOperation, year: int, evidence: FilingInstanceEvidence | None
) -> tuple[ModeloWorkForm, RegistrySnapshot]:
    period = Period.from_year_and_code(year, _PERIOD_CODE)
    snapshot = operation.reading_snapshot("303", filing_year=year, period=_PERIOD_CODE)
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


def _shown_text(form: ModeloWorkForm, context_id: str) -> str | None:
    return next(
        block.value_text
        for page in form.pages
        for section in page.sections
        for block in section.blocks
        if isinstance(block, ModeloFormContextFieldBlock) and block.id == context_id
    )


def _choice_text(operation: PinnedAuthorityOperation, snapshot: RegistrySnapshot, context_id: str, code: str) -> str:
    choice = next(choice for choice in _context_blocks(operation, snapshot)[context_id].choices if choice.value == code)
    return localized_heading(choice.heading_key, choice.official_heading, "Opcion", OutputLanguage.ES).text


def _producer_snapshot(
    operation: PinnedAuthorityOperation, evidence: FilingInstanceEvidence, model_profile: FilingModelProfileFacts
) -> FilingProducerSnapshot:
    period = evidence.m303.period
    register, bienes_register, regularisation = empty_m303_export_arrivals(period.filing_year)
    facts = resolve_m303_filing_facts(
        evidence=evidence,
        supplier_regime=M303SupplierRegimeArrival(
            period=period, recipient_of_cash_accounting_operations=False, source_ledger_ids=()
        ),
        prorrata_transition=resolve_m303_prorrata_transition_arrival(
            period=period, prorrata_register=register, operation=operation
        ),
        prorrata_register=register,
        differentiated_contributions=(),
        bienes_register=bienes_register,
        regularisation_result=regularisation,
        bienes_parameters=params_for(period.filing_year),
    )
    return build_filing_producer_snapshot(
        modelo=Modelo("303"),
        taxpayer_tax_id=_TAX_ID,
        taxpayer_identity=taxpayer_identity(),
        presenter=producer_snapshot_presenter(),
        model_profile=model_profile,
        elections=elections(ResultDisposition.INGRESO),
        amendment_evidence=None,
        refund_account=None,
        charge_account=None,
        m303_filing_facts=facts,
    )


def _decoded_export_fields(
    snapshot: RegistrySnapshot, producer_snapshot: FilingProducerSnapshot, export_field_ids: frozenset[str]
) -> dict[str, str]:
    """Render the real envelope for the addressed fields only and slice each back out of its record."""
    (layout,) = snapshot.revision.export_layouts
    assert layout.filing_envelope is not None
    record = next(record for record in layout.records if record.id == "m303-declaration")
    kept = tuple(field for field in record.fields if field.id in export_field_ids)
    assert {field.id for field in kept} == export_field_ids
    narrowed: ExportLayoutDefinition = layout.model_copy(
        update={
            "records": (record.model_copy(update={"fields": kept}),),
            "filing_envelope": layout.filing_envelope.model_copy(update={"body_record_ids": (record.id,)}),
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
    (occurrence,) = rendered.occurrences
    body = occurrence.payload
    decoded: dict[str, str] = {}
    for field in kept:
        assert field.offset is not None
        assert field.length is not None
        decoded[field.id] = body[field.offset - 1 : field.offset - 1 + field.length].decode(record.encoding).strip()
    return decoded


@pytest.mark.parametrize("year", _YEARS)
def test_form_identification_answers_equal_the_exported_fields(
    operation: PinnedAuthorityOperation, profile_store: _ProfileStore, year: int
) -> None:
    profile_store.record = _record(_PROFILE_FACTS)
    evidence = _evidence(operation, Period.from_year_and_code(year, _PERIOD_CODE), joint_return_elected=True)
    form, snapshot = _load_form(operation, year, evidence)
    producer_snapshot = _producer_snapshot(
        operation,
        evidence,
        m303_profile().model_copy(
            update={"redeme_enrolled": True, "cash_accounting_regime_enrolled": False, "voluntary_sii_enrolled": True}
        ),
    )
    blocks = _context_blocks(operation, snapshot)
    field_ids = {context_id: blocks[context_id].export_field_id for context_id in _EXPECTED}
    decoded = _decoded_export_fields(snapshot, producer_snapshot, frozenset(field_ids.values()))

    for context_id, expected_code in _EXPECTED.items():
        assert decoded[field_ids[context_id]] == expected_code, context_id
        assert _shown_text(form, context_id) == _choice_text(operation, snapshot, context_id, expected_code), context_id


@pytest.mark.parametrize("year", _YEARS)
def test_form_shows_an_answered_no_and_an_unanswered_fact_differently(
    operation: PinnedAuthorityOperation, profile_store: _ProfileStore, year: int
) -> None:
    unanswered_form, snapshot = _load_form(operation, year, None)
    absent = absent_value_text(OutputLanguage.ES)
    for context_id in _EXPECTED:
        assert _shown_text(unanswered_form, context_id) == absent, context_id

    profile_store.record = _record(
        {**_PROFILE_FACTS, "iva.redeme_enrolled": "false", "iva.voluntary_sii_enrolled": "false"}
    )
    evidence = _evidence(operation, Period.from_year_and_code(year, _PERIOD_CODE), joint_return_elected=False)
    answered_form, _ = _load_form(operation, year, evidence)
    for context_id in ("redeme", "conjunta", "criterio-caja", "sii"):
        assert _shown_text(answered_form, context_id) == _choice_text(operation, snapshot, context_id, "2"), context_id


def test_incomplete_iva_block_leaves_the_enrolments_unknown_and_the_form_open(
    operation: PinnedAuthorityOperation, profile_store: _ProfileStore
) -> None:
    year = _YEARS[-1]
    profile_store.record = _record({**_IDENTITY_FACTS, "iva.redeme_enrolled": "true"})
    evidence = _evidence(operation, Period.from_year_and_code(year, _PERIOD_CODE), joint_return_elected=True)
    form, snapshot = _load_form(operation, year, evidence)
    absent = absent_value_text(OutputLanguage.ES)
    for context_id in ("foral", "redeme", "regimen", "criterio-caja", "sii"):
        assert _shown_text(form, context_id) == absent, context_id
    assert _shown_text(form, "conjunta") == _choice_text(operation, snapshot, "conjunta", "1")
