"""Declared header context reads the profile through the real form-loading path."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import cast

import pytest

from ....core.external_constants import OutputLanguage
from ....core.filing_producer_key import FilingProducerKey
from ....core.period import Period
from ....core.text_bounds import FILING_TEXT_CAPACITY
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.bindings import CasillaObservation
from ....domain.calculations.registry.export import derive_export_layouts_from_bindings
from ....domain.calculations.registry.form_context import resolve_form_context_field
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.schema_form_layouts import FormContextFieldBlock
from ....domain.calculations.registry.tests.published_authority import leased_profile_create_context
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.calculation_revision_operator_layer import CalculationOperatorLayer
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    VerificationReportCatalogueRepositoryProtocol,
)
from ....domain.modelos.verification_report import VerificationReportCatalogue
from ....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from ....domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ....domain.user_profile.errors import ProfileNotFoundError, ProfileSchemaValidationError
from ....domain.user_profile.values import (
    ProfileSetupState,
    UserProfileFact,
    UserProfileRecord,
    create_user_profile_record,
)
from ...filing.identity_contact_producer import identity_contact_producer_values
from ...user_profile.profile_record_repository import ProfileRecordRepository
from ..profile_export_binding import (
    resolve_declaration_contact,
    resolve_export_identity,
    resolve_profile_identity_producer_values,
)
from ..work_form_context_values import form_context_value
from ..work_form_models import ModeloFormContextFieldBlock, ModeloFormOrigin, ModeloFormScalar, ModeloWorkForm
from ..work_form_service import load_modelo_work_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "13000000-0000-4000-8000-000000000455"
_NOW = datetime(2026, 1, 1, tzinfo=UTC)
# This NIF belongs to the canonical generic fixture pool, independently of any persona.
_IDENTITY = {
    "identity.tax_id": "12345678Z",
    "identity.name": "Ana",
    "identity.surnames": "Prueba Ejemplo",
    "taxpayer_type.entity_type": "natural_person",
}


def _record(facts: dict[str, str]) -> UserProfileRecord:
    return create_user_profile_record(
        profile_id=_BUCKET,
        setup_state=ProfileSetupState.COMPLETE,
        facts=tuple(UserProfileFact(path=path, value=value) for path, value in facts.items()),
        created_at=_NOW,
        updated_at=_NOW,
        context=leased_profile_create_context(),
    )


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
    """Stand in only for encrypted record I/O; fact indexing and shaping run unchanged."""
    repository = _ProfileStore()
    monkeypatch.setattr(ProfileRecordRepository, "for_current_session", lambda *_args, **_kwargs: repository)
    return repository


def _load(
    operation: PinnedAuthorityOperation,
    modelo: str,
    *,
    year: int | None = None,
    period_code: str = "1T",
    state: CalculationRevisionState | None = None,
    entered: bool = False,
) -> tuple[ModeloWorkForm, RegistrySnapshot]:
    if year is None:
        year = operation.supported_filing_years().horizon
    period = Period.from_year_and_code(year, period_code)
    snapshot = operation.reading_snapshot(modelo, filing_year=year, period=period_code)
    work_id = derive_work_unit_id(
        bucket_id=_BUCKET, modelo=modelo, filing_year=year, period=period, revision_id=snapshot.revision.id
    )
    revision = None if state is None else _revision(snapshot, work_id, state, entered=entered)
    unit = WorkUnit(
        work_unit_id=work_id,
        bucket_id=_BUCKET,
        modelo=modelo,
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
        ModeloCode(modelo),
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


def _revision(
    snapshot: RegistrySnapshot, work_id: str, state: CalculationRevisionState, *, entered: bool
) -> CalculationRevision:
    inputs = {"06": "19"} if entered else {}
    values = {"06": Decimal("19")} if entered else {}
    casilla = next(casilla for casilla in snapshot.revision.casillas if casilla.id == "06")
    observations = (
        (
            CasillaObservation(
                casilla_id="06", value=Decimal("19"), legal_refs=casilla.legal_refs, source_refs=casilla.source_refs
            ),
        )
        if entered
        else ()
    )
    layer = CalculationOperatorLayer(decimal_casilla_inputs=inputs)
    filed = state in (CalculationRevisionState.PRESENTADO, CalculationRevisionState.PRESENTADO_SUPERSEDIDO)
    discarded = state is CalculationRevisionState.DESCARTADO
    return CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id=work_id,
            input_values_by_casilla_id=inputs,
            binding_overrides={},
            casilla_values=values,
            filing_instance_evidence=None,
            source_provenance=(),
            operator_layer=layer,
        ),
        work_unit_id=work_id,
        registry_snapshot_ref=snapshot.snapshot_ref,
        state=state,
        input_values_by_casilla_id=inputs,
        casilla_values=values,
        observations=observations,
        operator_layer=layer,
        filing_instance_evidence=None,
        source_provenance=(),
        created_at=_NOW,
        updated_at=_NOW,
        verified_at=_NOW if filed else None,
        verified_by="test" if filed else None,
        filed_at=_NOW if filed else None,
        filed_by="test" if filed else None,
        superseded_at=_NOW if state is CalculationRevisionState.PRESENTADO_SUPERSEDIDO else None,
        discarded_at=_NOW if discarded else None,
        discarded_by="test" if discarded else None,
    )


def _context_values(
    form: ModeloWorkForm, snapshot: RegistrySnapshot, operation: PinnedAuthorityOperation
) -> dict[FilingProducerKey, ModeloFormScalar]:
    layout = operation.form_layout(str(form.modelo), snapshot.revision.id)
    assert layout is not None
    values = {}
    for declared_page, page in zip(layout.pages, form.pages, strict=True):
        for declared_section, section in zip(declared_page.sections, page.sections, strict=True):
            for declared, block in zip(declared_section.blocks, section.blocks, strict=True):
                if not isinstance(declared, FormContextFieldBlock):
                    continue
                assert isinstance(block, ModeloFormContextFieldBlock)
                assert "address" not in block.model_dump()
                owner = resolve_form_context_field(snapshot.revision, declared)
                if owner.producer_key is not None:
                    values[owner.producer_key] = block.value
    return values


@pytest.mark.parametrize("modelo", ["111", "115", "130", "131"])
def test_populated_identity_reaches_declared_context_and_agrees_with_export(
    operation: PinnedAuthorityOperation, profile_store: _ProfileStore, modelo: str
) -> None:
    record = _record(_IDENTITY)
    profile_store.record = record
    form, snapshot = _load(operation, modelo)
    values = _context_values(form, snapshot, operation)
    expected = {
        FilingProducerKey.TAXPAYER_TAX_ID: "12345678Z",
        FilingProducerKey.TAXPAYER_GIVEN_NAME: "Ana",
        FilingProducerKey.TAXPAYER_SURNAMES_OR_LEGAL_NAME: "Prueba Ejemplo",
        FilingProducerKey.TAXPAYER_FULL_NAME: "Prueba Ejemplo Ana",
        FilingProducerKey.TAXPAYER_SURNAMES: "Prueba Ejemplo",
        FilingProducerKey.TAXPAYER_LEGAL_NAME: None,
    }
    assert values[FilingProducerKey.TAXPAYER_TAX_ID] == "12345678Z"
    if FilingProducerKey.SELECTED_ACCOUNT_IBAN in values:
        assert values[FilingProducerKey.SELECTED_ACCOUNT_IBAN] is None
    assert any(key in values for key in expected if key is not FilingProducerKey.TAXPAYER_TAX_ID)
    for key, value in expected.items():
        if key in values:
            assert values[key] == value
    export_identity = resolve_export_identity(bucket_id=_BUCKET, operation=operation, profile_record=record)
    assert export_identity is not None
    export_values = identity_contact_producer_values(
        taxpayer_tax_id=export_identity[0].tax_id,
        identity=export_identity[1],
        contact=resolve_declaration_contact(bucket_id=_BUCKET, operation=operation, profile_record=record),
    )
    assert all(values[key] == value for key, value in export_values.items() if key in values)


@pytest.mark.parametrize(
    ("facts", "tax_id", "given_name"),
    [
        ({"identity.tax_id": "12345678Z"}, "12345678Z", None),
        ({"identity.name": "Ana"}, None, "Ana"),
        ({}, None, None),
    ],
)
def test_partial_profile_preserves_each_declared_component(
    operation: PinnedAuthorityOperation,
    profile_store: _ProfileStore,
    facts: dict[str, str],
    tax_id: str | None,
    given_name: str | None,
) -> None:
    profile_store.record = _record({"taxpayer_type.entity_type": "natural_person", **facts})
    form, snapshot = _load(operation, "130")
    values = _context_values(form, snapshot, operation)
    assert values[FilingProducerKey.TAXPAYER_TAX_ID] == tax_id
    assert values[FilingProducerKey.TAXPAYER_GIVEN_NAME] == given_name
    assert values[FilingProducerKey.TAXPAYER_SURNAMES] is None


def test_absent_profile_leaves_header_unknown(
    operation: PinnedAuthorityOperation, profile_store: _ProfileStore
) -> None:
    form, snapshot = _load(operation, "130")
    values = _context_values(form, snapshot, operation)
    assert values[FilingProducerKey.TAXPAYER_TAX_ID] is None
    assert values[FilingProducerKey.TAXPAYER_GIVEN_NAME] is None


def test_stored_name_past_the_producer_bound_leaves_header_unknown_and_the_form_open(
    operation: PinnedAuthorityOperation, profile_store: _ProfileStore
) -> None:
    profile_store.record = _record({**_IDENTITY, "identity.name": "N" * (FILING_TEXT_CAPACITY + 1)})
    with pytest.raises(ProfileSchemaValidationError):
        resolve_profile_identity_producer_values(bucket_id=_BUCKET, operation=operation)
    form, snapshot = _load(operation, "130")
    values = _context_values(form, snapshot, operation)
    assert values[FilingProducerKey.TAXPAYER_TAX_ID] is None
    assert values[FilingProducerKey.TAXPAYER_GIVEN_NAME] is None


def test_contact_and_irnr_parties_are_not_replaced_by_taxpayer_or_operator_email(
    operation: PinnedAuthorityOperation, profile_store: _ProfileStore
) -> None:
    profile_store.record = _record(
        {
            **_IDENTITY,
            "identity.email": "operator@example.invalid",
            "contact.contact_person_name": "Contacto Declaracion",
            "contact.contact_person_phone": "900000000",
        }
    )
    form, snapshot = _load(operation, "180", period_code="0A")
    values = _context_values(form, snapshot, operation)
    assert values[FilingProducerKey.CONTACT_PERSON_NAME] == "Contacto Declaracion"
    assert values[FilingProducerKey.CONTACT_PERSON_PHONE] == "900000000"
    assert values[FilingProducerKey.TAXPAYER_FULL_NAME] == "Prueba Ejemplo Ana"
    producer_values = resolve_profile_identity_producer_values(bucket_id=_BUCKET, operation=operation)
    irnr = operation.reading_snapshot("210", filing_year=operation.supported_filing_years().horizon, period="0A")
    for key in (
        FilingProducerKey.CONTACT_PERSON_EMAIL,
        FilingProducerKey.CONTACT_PERSON_SECONDARY_PHONE,
        FilingProducerKey.IRNR_REPRESENTANTE_TAX_ID,
        FilingProducerKey.IRNR_CONTRIBUYENTE_TAX_ID,
    ):
        export, record, field = next(
            (export, record, field)
            for export in derive_export_layouts_from_bindings(irnr.revision)
            for record in export.records
            for field in record.fields
            if record.repeat is None and field.producer_key is key
        )
        block = FormContextFieldBlock(
            id="party-context",
            export_layout_id=export.id,
            export_record_id=record.id,
            export_field_id=field.id,
            heading_key="test.party.context",
            official_heading="Dato de la parte",
        )
        assert form_context_value(irnr, block, producer_values=producer_values) is None


@pytest.mark.parametrize(
    "state",
    [
        CalculationRevisionState.PRESENTADO,
        CalculationRevisionState.PRESENTADO_SUPERSEDIDO,
        CalculationRevisionState.DESCARTADO,
    ],
)
def test_historical_head_does_not_display_current_profile_as_filed_identity(
    operation: PinnedAuthorityOperation, profile_store: _ProfileStore, state: CalculationRevisionState
) -> None:
    profile_store.record = _record(_IDENTITY)
    form, snapshot = _load(operation, "130", state=state)
    values = _context_values(form, snapshot, operation)
    assert values[FilingProducerKey.TAXPAYER_TAX_ID] is None
    assert values[FilingProducerKey.TAXPAYER_GIVEN_NAME] is None


def test_profile_context_preserves_explicit_casilla_and_supported_year_selection(
    operation: PinnedAuthorityOperation, profile_store: _ProfileStore
) -> None:
    profile_store.record = _record(_IDENTITY)
    year = operation.supported_filing_years().horizon
    form, snapshot = _load(operation, "130", year=year, state=CalculationRevisionState.BORRADOR, entered=True)
    assert form.filing_year == year
    assert form.registry_revision_id == snapshot.revision.id
    assert _context_values(form, snapshot, operation)[FilingProducerKey.TAXPAYER_TAX_ID] == "12345678Z"
    field = next(field for field in form.fields() if getattr(field.address, "casilla_id", None) == "06")
    assert field.value == Decimal("19")
    assert field.origin is ModeloFormOrigin.ENTERED
