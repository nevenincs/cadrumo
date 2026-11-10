"""Profile contact survives calculation, encrypted replay, form projection and local export."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    load_test_profile_record,
    replace_test_profile_record,
)
from cadrumo.application.filing.draft_construction import build_draft
from cadrumo.application.filing.export import export_draft
from cadrumo.application.filing.producer_snapshot import (
    FilingElectionFacts,
    GeneralFilingProfileFacts,
    build_filing_producer_snapshot,
)
from cadrumo.application.filing.runtime import ModeloOperatorProfile, build_runtime_schema_provider
from cadrumo.application.modelo.calculation_bucket_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from cadrumo.application.modelo.profile_binding import resolve_profile_sourced_bindings
from cadrumo.application.modelo.profile_export_binding import resolve_declaration_contact, resolve_export_identity
from cadrumo.application.modelo.revision_replay_inputs import revision_filing_replay_inputs
from cadrumo.application.modelo.work_form_field_vocabulary import ModeloFormBindingAddressV1
from cadrumo.application.modelo.work_form_models import ModeloFormContextFieldBlock
from cadrumo.application.modelo.work_form_service import load_modelo_work_form
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.application.modelo.work_profile import ModeloWorkProfile
from cadrumo.core.aggregation import BindingSourceKind
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.modelo import Modelo
from cadrumo.core.payment_election import PaymentElection
from cadrumo.core.period import Period
from cadrumo.core.prior_domiciliation_election import PriorDomiciliationElection
from cadrumo.core.refund_election import RefundElection
from cadrumo.core.result_disposition import ResultDisposition
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.form_context import resolve_form_context_field
from cadrumo.domain.calculations.registry.profile_bindings import ProfileProvider
from cadrumo.domain.calculations.registry.schema_form_layouts import FormContextFieldBlock
from cadrumo.domain.modelos.calculation_revision import CalculationRevision
from cadrumo.domain.modelos.work_unit import WorkUnit
from cadrumo.domain.submission.models import ModeloDraftStatus
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record

from .file_flow_test_support import T0, Repos, calculation_ports_for_test

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PHONE = "modelo-720.type_1.telefono-contacto"
_NAME = "modelo-720.type_1.nombre-contacto"
_CONTACT = {"contact.contact_person_phone": "900000000", "contact.contact_person_name": "Contacto Prueba Berta"}
# Type-2 asset inputs remain manual; DR720 repeats the declarant identity there.
_DECLARED_ASSET_ROW = {
    "modelo-720.type_2.clave-tipo-de-bien-o-derecho": {"1": "V"},
    "modelo-720.type_2.codigo-de-pais": {"1": "DE"},
    "modelo-720.type_2.identificacion-de-valores": {"1": "DE0007164600"},
}


def test_contact_bindings_resolve_with_unchanged_export_geometry_in_every_supported_year(
    operation: PinnedAuthorityOperation,
) -> None:
    bucket_id = "13000000-0000-4000-8000-000000000455"
    record = create_user_profile_record(
        profile_id=bucket_id,
        setup_state=ProfileSetupState.COMPLETE,
        facts=tuple(UserProfileFact(path=path, value=value) for path, value in _CONTACT.items()),
        created_at=T0,
        updated_at=T0,
        context=operation.profile_create_context(),
    )
    years = operation.supported_filing_years().years
    assert years
    for year in years:
        snapshot = operation.reading_snapshot("720", filing_year=year, period="0A")
        resolution = resolve_profile_sourced_bindings(
            snapshot, bucket_id=bucket_id, operation=operation, profile_record=record
        )
        assert resolution.enum_binding_values[_PHONE] == "900000000", year
        assert resolution.enum_binding_values[_NAME] == "Contacto Prueba Berta", year
        fields = {
            field.binding: field
            for layout in snapshot.revision.export_layouts
            for record in layout.records
            for field in record.fields
            if field.binding in {_PHONE, _NAME}
        }
        assert (fields[_PHONE].offset, fields[_PHONE].length, fields[_PHONE].required) == (59, 9, False), year
        assert (fields[_NAME].offset, fields[_NAME].length, fields[_NAME].required) == (68, 40, False), year


def _created_work(
    repos: Repos,
    operation: PinnedAuthorityOperation,
    facts: dict[str, str],
) -> tuple[WorkUnit, ModeloWorkProfile]:
    work_repo, _, _, _, events = repos
    bucket_id = work_repo.bucket_id
    assert bucket_id is not None
    record = load_test_profile_record(bucket_id)
    record = replace_test_profile_record(
        record.model_copy(
            update={
                "facts": (
                    *(
                        fact
                        for fact in record.facts
                        if fact.path not in _CONTACT
                        and fact.path not in facts
                        and fact.path != "obligations.bienes_extranjero_above_threshold"
                    ),
                    *(UserProfileFact(path=path, value=value) for path, value in facts.items()),
                    UserProfileFact(path="obligations.bienes_extranjero_above_threshold", value=True),
                )
            }
        )
    )
    year = operation.supported_filing_years().horizon
    period = Period.from_year_and_code(year, "0A")
    snapshot = operation.reading_snapshot("720", filing_year=year, period="0A")
    bindings = {binding.id: binding for binding in snapshot.revision.bindings}
    assert isinstance(bindings[_PHONE].provider, ProfileProvider)
    assert isinstance(bindings[_NAME].provider, ProfileProvider)
    profile = ModeloWorkProfile(record=record, profile_decode_context=operation.profile_decode_context())
    unit = create_work_unit(
        bucket_id=bucket_id,
        modelo="720",
        filing_year=year,
        period=period,
        revision_id=snapshot.revision.id,
        name="Synthetic foreign-assets declaration",
        ports=WorkLifecyclePorts(work_unit_repository=work_repo, bucket_event_repository=events),
        operation=operation,
        clock=T0,
        profile=profile,
    )
    return unit, profile


def _calculate(
    repos: Repos,
    operation: PinnedAuthorityOperation,
    facts: dict[str, str],
    *,
    caller: dict[str, str] | None = None,
) -> tuple[WorkUnit, CalculationRevision, ModeloWorkProfile]:
    unit, profile = _created_work(repos, operation, facts)
    work_repo, calculation_repo, filing_repo, _, events = repos
    with calculation_ports_for_test(
        bucket_id=unit.bucket_id,
        work_unit_repository=work_repo,
        calculation_repository=calculation_repo,
        filing_repository=filing_repo,
        bucket_event_repository=events,
    ) as ports:
        calculated = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            unit.work_unit_id,
            ports=ports,
            enum_binding_values=caller,
            record_operator_layer=True,
            profile=profile,
            clock=T0,
        ).revision
    saved = calculation_repo.load(operation=operation).get(calculated.calculation_revision_id)
    assert saved is not None
    assert saved == calculated
    return unit, saved, profile


def _contact_provenance(revision: CalculationRevision, unit: WorkUnit) -> set[str]:
    references = set()
    for source in revision.source_provenance:
        if source.resolved_binding_source is BindingSourceKind.PROFILE:
            assert source.fingerprint is not None
            for binding_id in (_PHONE, _NAME):
                if source.source_ref == f"profile:{unit.bucket_id}:binding:{binding_id}":
                    references.add(binding_id)
    return references


def _contact_contexts(
    repos: Repos, unit: WorkUnit, operation: PinnedAuthorityOperation
) -> dict[str, ModeloFormContextFieldBlock]:
    work_repo, calculation_repo, _, verification_repo, _ = repos
    form = load_modelo_work_form(
        unit.bucket_id,
        unit.modelo,
        unit.filing_year,
        unit.period,
        operation=operation,
        work_unit_repository=work_repo,
        calculation_repository=calculation_repo,
        verification_repository=verification_repo,
        admission=None,
        language=OutputLanguage.ES,
    ).form
    snapshot = operation.reading_snapshot("720", filing_year=unit.filing_year, period=unit.period.registry_token)
    layout = operation.form_layout("720", form.registry_revision_id)
    assert layout is not None
    contexts = {}
    for declared_page, page in zip(layout.pages, form.pages, strict=True):
        for declared_section, section in zip(declared_page.sections, page.sections, strict=True):
            for declared, block in zip(declared_section.blocks, section.blocks, strict=True):
                if not isinstance(declared, FormContextFieldBlock):
                    continue
                owner = resolve_form_context_field(snapshot.revision, declared)
                if owner.binding not in {_PHONE, _NAME}:
                    continue
                assert isinstance(block, ModeloFormContextFieldBlock)
                assert "address" not in block.model_dump()
                contexts[owner.binding] = block
    assert set(contexts) == {_PHONE, _NAME}
    assert not any(
        isinstance(field.address, ModeloFormBindingAddressV1) and field.address.binding_id in {_PHONE, _NAME}
        for field in form.fields()
    )
    return contexts


@pytest.mark.parametrize("facts", [_CONTACT, {}, {"contact.contact_person_phone": "900000000"}])
def test_first_create_opens_profile_contact_without_calculation_or_read_mutation(
    repos: Repos, operation: PinnedAuthorityOperation, facts: dict[str, str]
) -> None:
    unit, _ = _created_work(repos, operation, facts)
    assert unit.current_calculation_revision_id is None
    work_repo, calculation_repo, _, _, events = repos
    before_work = work_repo.load_revisioned()
    before_calculations = calculation_repo.load_revisioned(operation=operation)
    before_events = events.load()
    contexts = _contact_contexts(repos, unit, operation)
    assert contexts[_PHONE].value == facts.get("contact.contact_person_phone")
    assert contexts[_NAME].value == facts.get("contact.contact_person_name")
    assert work_repo.load_revisioned() == before_work
    assert calculation_repo.load_revisioned(operation=operation) == before_calculations
    assert events.load() == before_events


@pytest.mark.parametrize("caller_name", [None, "Otro Contacto Clara"])
def test_contact_reaches_encrypted_revision_form_and_export_with_caller_precedence(
    repos: Repos, operation: PinnedAuthorityOperation, tmp_path: Path, caller_name: str | None
) -> None:
    caller = {} if caller_name is None else {_NAME: caller_name}
    unit, saved, profile = _calculate(repos, operation, _CONTACT, caller=caller)
    name = _CONTACT["contact.contact_person_name"] if caller_name is None else caller_name
    assert saved.binding_overrides[_PHONE] == "900000000"
    assert saved.binding_overrides[_NAME] == name
    # Provenance records every considered tier; operator_layer records the
    # caller's selected answer without erasing the lower-tier profile evidence.
    assert _contact_provenance(saved, unit) == {_PHONE, _NAME}
    assert saved.operator_layer is not None
    assert dict(saved.operator_layer.binding_overrides) == caller
    contexts = _contact_contexts(repos, unit, operation)
    assert contexts[_PHONE].value == "900000000"
    assert contexts[_NAME].value == name
    provider = build_runtime_schema_provider(
        modelos=("720",), filing_year=unit.filing_year, period=unit.period, operation=operation
    )
    identity = resolve_export_identity(bucket_id=unit.bucket_id, operation=operation, profile_record=profile.record)
    assert identity is not None
    presenter, taxpayer = identity
    draft = build_draft(
        modelo="720",
        period=unit.period,
        profile=ModeloOperatorProfile(tax_id=presenter.tax_id, display_name=presenter.full_name),
        inputs={
            **revision_filing_replay_inputs(revision=saved, work_unit=unit, operation=operation),
            **_DECLARED_ASSET_ROW,
            "modelo-720.type_2.n-i-f-del-declarado": {"1": presenter.tax_id},
            "modelo-720.type_2.apellidos-y-nombre-razon-social-o-denominacion-del-declarado": {
                "1": presenter.full_name,
            },
        },
        schema_provider=provider,
    )
    output = tmp_path / "modelo-720.txt"
    export_draft(
        draft.model_copy(update={"status": ModeloDraftStatus.APROBADO}),
        output_path=output,
        schema_provider=provider,
        producer_snapshot=build_filing_producer_snapshot(
            modelo=Modelo("720"),
            taxpayer_tax_id=presenter.tax_id,
            taxpayer_identity=taxpayer,
            presenter=presenter,
            declaration_contact=resolve_declaration_contact(
                bucket_id=unit.bucket_id, operation=operation, profile_record=profile.record
            ),
            model_profile=GeneralFilingProfileFacts(),
            elections=FilingElectionFacts(
                result_disposition=ResultDisposition.NEGATIVA,
                payment=PaymentElection.INGRESO,
                refund=RefundElection.COMPENSAR,
                prior_domiciliation=PriorDomiciliationElection.KEEP,
            ),
            amendment_evidence=None,
            m303_filing_facts=None,
            refund_account=None,
            charge_account=None,
        ),
    )
    # Independent wire positions come from DR720, printed page 15.
    header, declared = output.read_bytes().splitlines()
    assert header[58:67] == b"900000000"
    assert header[67:107] == name.encode("iso-8859-1").ljust(40, b" ")
    assert declared[17:26] == header[8:17] == presenter.tax_id.encode("iso-8859-1")
    assert declared[35:75] == header[17:57] == presenter.full_name.encode("iso-8859-1").ljust(40, b" ")
    assert header[67:107] != declared[35:75]


@pytest.mark.parametrize(
    "facts",
    [
        {},
        {"contact.contact_person_phone": "900000000"},
        # A blank or whitespace-only stored name is no answer: it stays absent.
        {"contact.contact_person_phone": "900000000", "contact.contact_person_name": ""},
        {"contact.contact_person_phone": "900000000", "contact.contact_person_name": "   "},
    ],
)
def test_absent_contact_components_remain_absent_in_encrypted_replay(
    repos: Repos, operation: PinnedAuthorityOperation, facts: dict[str, str]
) -> None:
    unit, saved, profile = _calculate(repos, operation, facts)
    replay = revision_filing_replay_inputs(revision=saved, work_unit=unit, operation=operation)
    assert _NAME not in saved.binding_overrides
    assert _NAME not in replay
    contexts = _contact_contexts(repos, unit, operation)
    assert contexts[_NAME].value is None
    snapshot = operation.reading_snapshot("720", filing_year=unit.filing_year, period=unit.period.registry_token)
    resolution = resolve_profile_sourced_bindings(
        snapshot, bucket_id=unit.bucket_id, operation=operation, profile_record=profile.record
    )
    # Neither optional contact slot is a formula prerequisite: absence remains
    # unknown, without inventing a required-input refusal or a placeholder.
    assert not {_PHONE, _NAME}.intersection(resolution.unresolved_binding_ids)
    assert not any(
        diagnostic.reason == "unresolved_binding" and diagnostic.binding_id in {_PHONE, _NAME}
        for diagnostic in resolution.diagnostics
    )
    if facts:
        assert replay[_PHONE] == "900000000"
        assert _contact_provenance(saved, unit) == {_PHONE}
        assert contexts[_PHONE].value == "900000000"
    else:
        assert _PHONE not in replay
        assert _contact_provenance(saved, unit) == set()
        assert contexts[_PHONE].value is None


def test_changed_profile_evidence_changes_revision_identity_even_when_contact_values_match(
    repos: Repos, operation: PinnedAuthorityOperation
) -> None:
    _, first, _ = _calculate(repos, operation, {**_CONTACT, "identity.email": "first@example.invalid"})
    _, second, _ = _calculate(repos, operation, {**_CONTACT, "identity.email": "second@example.invalid"})
    assert first.binding_overrides == second.binding_overrides
    assert first.calculation_revision_id != second.calculation_revision_id
    first_fingerprints = {row.fingerprint for row in first.source_provenance if row.resolver_id == "profile"}
    second_fingerprints = {row.fingerprint for row in second.source_provenance if row.resolver_id == "profile"}
    assert first_fingerprints
    assert first_fingerprints != second_fingerprints
