"""Declared filing context selects exact facts and refuses ambiguous source addresses."""

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.application.filing.producer_snapshot import (
    AmendmentEvidence,
    FilingElectionFacts,
    FilingProducerSnapshot,
    GeneralFilingProfileFacts,
    Modelo111ProfileFacts,
    PresenterIdentity,
    TaxpayerIdentityFacts,
    build_filing_producer_snapshot,
)
from cadrumo.application.modelo.work_form_context_values import form_context_value
from cadrumo.application.storage.calc_sheets.engine import build_export_plan
from cadrumo.application.storage.calc_sheets.form_workbook import add_form_workbook
from cadrumo.application.storage.calc_sheets.records import TabName
from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.config import override_settings
from cadrumo.core.filing_producer_key import FilingProducerKey
from cadrumo.core.i18n.render import lookup_translation
from cadrumo.core.modelo import Modelo
from cadrumo.core.payment_election import PaymentElection
from cadrumo.core.prior_domiciliation_election import PriorDomiciliationElection
from cadrumo.core.refund_election import RefundElection
from cadrumo.core.result_disposition import ResultDisposition
from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind
from cadrumo.domain.calculations.registry import form_context
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.export import derive_export_layouts_from_bindings
from cadrumo.domain.calculations.registry.export_semantics import ExportDraftAttribute
from cadrumo.domain.calculations.registry.form_context import resolve_form_context_field
from cadrumo.domain.calculations.registry.governed_fact_scope import validating_governed_facts
from cadrumo.domain.calculations.registry.schema_exports import ExportRecordRepeat
from cadrumo.domain.calculations.registry.schema_form_layouts import FormContextFieldBlock
from cadrumo.domain.modelos.calculation_revision_amendment import CalculationRevisionAmendmentKind

from ..compiler import form_layout_integrity
from ..compiler.authority import compiled_bundled_authority
from ..compiler.form_layout_integrity import form_layout_failures, form_layout_source_digest

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]


def _producer(*, modelo: str = "111", complementaria: bool = False) -> FilingProducerSnapshot:
    """Build fictional filing facts through the public validated producer boundary."""
    return build_filing_producer_snapshot(
        modelo=Modelo(modelo),
        taxpayer_tax_id="12345678Z",
        taxpayer_identity=TaxpayerIdentityFacts(
            legal_name=None, given_name="Ana", surnames="Prueba", full_name="Ana Prueba"
        ),
        presenter=PresenterIdentity(tax_id="00000000T", full_name="Gestoría Prueba"),
        model_profile=Modelo111ProfileFacts(colegio_concertado=False)
        if modelo == "111"
        else GeneralFilingProfileFacts(),
        elections=FilingElectionFacts(
            result_disposition=ResultDisposition.NEGATIVA if modelo == "111" else ResultDisposition.INGRESO,
            payment=PaymentElection.INGRESO,
            refund=RefundElection.COMPENSAR,
            prior_domiciliation=PriorDomiciliationElection.KEEP,
        ),
        amendment_evidence=AmendmentEvidence(
            kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
            m303_rectificativa_motive=None,
            original_aeat_receipt="1234567890123",
        )
        if complementaria
        else None,
        m303_filing_facts=None,
        refund_account=None,
        charge_account=None,
    )


@pytest.fixture(scope="module")
def snapshot():
    authority = compiled_bundled_authority()
    return authority.snapshot(
        "111",
        filing_year=2025,
        period="1T",
        on=date(2025, 3, 31),
        revision_id="2019-y-siguientes",
        grade=RegistryAuthorityGrade.CALCULATION,
    )


@pytest.fixture(autouse=True)
def governed_scope(snapshot):
    with validating_governed_facts(compiled_bundled_authority()):
        yield


def _blocks(snapshot):
    return {
        block.id: block
        for layout in snapshot.revision.form_layouts
        for page in layout.pages
        for section in page.sections
        for block in section.blocks
        if isinstance(block, FormContextFieldBlock)
    }


def test_real_111_context_selects_exact_eight_export_semantics(snapshot):
    expected = {
        "nif": FilingProducerKey.TAXPAYER_TAX_ID,
        "apellidos": FilingProducerKey.TAXPAYER_SURNAMES_OR_LEGAL_NAME,
        "nombre": FilingProducerKey.TAXPAYER_GIVEN_NAME,
        "iban": FilingProducerKey.SELECTED_ACCOUNT_IBAN,
        "declaracion-complementaria": FilingProducerKey.AMENDMENT_IS_COMPLEMENTARIA,
        "justificante-anterior": FilingProducerKey.AMENDMENT_ORIGINAL_AEAT_RECEIPT,
        "ejercicio": ExportDraftAttribute.FILING_YEAR,
        "periodo": ExportDraftAttribute.PERIOD_CODE,
    }
    blocks = _blocks(snapshot)
    assert set(blocks) == set(expected)
    for name, semantic in expected.items():
        field = resolve_form_context_field(snapshot.revision, blocks[name])
        if isinstance(semantic, FilingProducerKey):
            assert field.kind is CasillaFieldKind.HEADER
            assert field.producer_key is semantic
        else:
            assert field.kind is CasillaFieldKind.DRAFT
            assert field.draft_attribute is semantic


def test_absent_producer_leaves_identity_unknown_but_keeps_snapshot_coordinate(snapshot):
    values = {name: form_context_value(snapshot, block) for name, block in _blocks(snapshot).items()}
    assert values.pop("ejercicio") == 2025
    assert values.pop("periodo") == "1T"
    assert all(value is None for value in values.values())


def test_typed_producer_selects_identity_and_amendment_without_presenter_leak(snapshot):
    producer = _producer(complementaria=True)
    values = {
        name: form_context_value(snapshot, block, producer_snapshot=producer)
        for name, block in _blocks(snapshot).items()
    }
    assert values == {
        "nif": "12345678Z",
        "apellidos": "Prueba",
        "nombre": "Ana",
        "ejercicio": 2025,
        "periodo": "1T",
        "iban": None,
        "declaracion-complementaria": True,
        "justificante-anterior": "1234567890123",
    }
    assert producer.presenter.tax_id not in values.values()
    assert producer.presenter.full_name not in values.values()


@pytest.mark.parametrize("name", ("nif", "ejercicio", "periodo"))
def test_other_modelo_producer_is_refused_even_for_filing_coordinates(snapshot, name):
    with pytest.raises(RegistryValidationError, match="another modelo"):
        form_context_value(snapshot, _blocks(snapshot)[name], producer_snapshot=_producer(modelo="131"))


@pytest.mark.parametrize("attribute", ("export_layout_id", "export_record_id", "export_field_id"))
def test_unknown_or_wrong_export_address_is_refused(snapshot, attribute):
    block = _blocks(snapshot)["nif"].model_copy(update={attribute: "unknown-context-target"})
    with pytest.raises(RegistryValidationError, match="exactly one"):
        resolve_form_context_field(snapshot.revision, block)


def _alter_target(snapshot, block, *, field_change=None, repeat=False, duplicate=False):
    layouts = derive_export_layouts_from_bindings(snapshot.revision)
    changed = []
    for layout in layouts:
        records = []
        for record in layout.records:
            if layout.id == block.export_layout_id and record.id == block.export_record_id:
                fields = tuple(
                    field.model_copy(update=field_change)
                    if field.id == block.export_field_id and field_change
                    else field
                    for field in record.fields
                )
                if duplicate:
                    fields += tuple(field for field in fields if field.id == block.export_field_id)
                record = record.model_copy(
                    update={"fields": fields, "repeat": ExportRecordRepeat.BINDING_ROWS if repeat else record.repeat}
                )
            records.append(record)
        changed.append(layout.model_copy(update={"records": tuple(records)}))
    return tuple(changed)


@pytest.mark.parametrize("invalid", ("noncontext", "repeating", "duplicate", "unsupported_draft"))
def test_invalid_export_semantics_are_refused(snapshot, monkeypatch, invalid):
    block = _blocks(snapshot)["ejercicio" if invalid == "unsupported_draft" else "nif"]
    change = (
        {"kind": CasillaFieldKind.FILLER, "producer_key": None}
        if invalid == "noncontext"
        else {"draft_attribute": ExportDraftAttribute.PERIOD_START_DATE}
        if invalid == "unsupported_draft"
        else None
    )
    layouts = _alter_target(
        snapshot, block, field_change=change, repeat=invalid == "repeating", duplicate=invalid == "duplicate"
    )
    monkeypatch.setattr(form_context, "derive_export_layouts_from_bindings", lambda _: layouts)
    with pytest.raises(RegistryValidationError):
        resolve_form_context_field(snapshot.revision, block)


@pytest.mark.parametrize(
    ("name", "change"),
    (
        ("nif", {"producer_key": FilingProducerKey.PRESENTER_TAX_ID}),
        ("ejercicio", {"draft_attribute": ExportDraftAttribute.PERIOD_CODE}),
    ),
)
def test_context_source_digest_tracks_semantic_remapping(snapshot, monkeypatch, name, change):
    before = form_layout_source_digest(snapshot.revision)
    layouts = _alter_target(snapshot, _blocks(snapshot)[name], field_change=change)
    monkeypatch.setattr(form_layout_integrity, "derive_export_layouts_from_bindings", lambda _: layouts)
    assert form_layout_source_digest(snapshot.revision) != before
    assert any("stale" in failure for failure in form_layout_failures(snapshot.revision))


def test_repeated_context_display_uses_same_fact_without_ambiguity(snapshot):
    layout = snapshot.revision.form_layouts[0]
    page = layout.pages[0]
    section = page.sections[0]
    repeated = _blocks(snapshot)["nif"].model_copy(update={"id": "duplicate-taxpayer-nif"})
    section = section.model_copy(update={"blocks": (*section.blocks, repeated)})
    page = page.model_copy(update={"sections": (section, *page.sections[1:])})
    layout = layout.model_copy(update={"pages": (page, *layout.pages[1:])})
    revision = snapshot.revision.model_copy(update={"form_layouts": (layout,)})
    assert not form_layout_failures(revision)
    assert resolve_form_context_field(revision, repeated) == resolve_form_context_field(
        revision, _blocks(snapshot)["nif"]
    )


@pytest.mark.parametrize("include_producer", (False, True))
def test_real_workbook_shows_only_selected_context_and_known_coordinate(snapshot, include_producer):
    producer = _producer(complementaria=True) if include_producer else None
    with override_settings(cadrumo_output_language="es"), validating_governed_facts(compiled_bundled_authority()):
        plan = add_form_workbook(build_export_plan(snapshot), snapshot, producer_snapshot=producer)
    cells = {
        (cell.address.row, cell.address.column): cell.value
        for cell in plan.value_cells
        if cell.address.tab is TabName.FORM
    }
    for name, block in _blocks(snapshot).items():
        heading = lookup_translation(block.heading_key, locale="es") or block.official_heading
        rows = [row for (row, column), value in cells.items() if column == 2 and value == heading]
        assert len(rows) == 1
        shown = cells[rows[0], 9]
        if name == "ejercicio":
            assert shown == Decimal(2025)
        elif name == "periodo":
            assert shown == "1T"
        elif not include_producer or name == "iban":
            assert shown == "Sin dato"
        elif name == "declaracion-complementaria":
            assert shown == "Sí"
        else:
            assert shown == form_context_value(snapshot, block, producer_snapshot=producer)
    if producer:
        all_values = [cell.value for cell in plan.value_cells]
        assert producer.presenter.tax_id not in all_values
        assert producer.presenter.full_name not in all_values
