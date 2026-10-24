"""Exporting offers the same artefacts, elections and file format, and states the same receipt, for every frontend.

The elections are asked exactly where the terminal workbench asked them, now
read from each modelo's declared result codes rather than its name; the file
format is the one the revision's export layout declares; and the receipt is
verified only by an in-force filing the AEAT is seen to hold. Forms are built
by the real builder over the published registry; filing records are synthetic.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from ....core.export_layout_format import ExportLayoutFormat
from ....core.external_constants import OutputLanguage
from ....core.modelo_export_artefact import ModeloExportArtefact
from ....core.optional_extras import PDF_EXTRA, optional_extra_available
from ....core.payment_election import PaymentElection
from ....core.period import Period
from ....core.prior_domiciliation_election import PriorDomiciliationElection
from ....core.refund_election import RefundElection
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tax_id_format import runtime_tax_id_format
from ....domain.modelos.calculation_revision import CalculationRevisionState
from ....domain.modelos.filing_record import (
    AeatConfirmationState,
    ExternalEvidence,
    ExternalEvidenceKind,
    FilingDeclarationKind,
    FilingOrigin,
    ModeloRecord,
    ModeloRecordStatus,
    derive_filing_record_id,
)
from ....domain.modelos.verification_report import VerificationCompletenessStatus
from ..calculation_note_gate import gate_refuses
from ..calculation_notes import CALCULATION_NOTE_ATTENTION, CHECK_REFUSED_REASONS, GATE_REFUSED_REASONS
from ..edit_admission import RESPONSIBLE_OWNER
from ..edit_models import ModeloEditDomainRefusalV1, ModeloEditRefusalCode, ModeloEditRefusedV1
from ..work_form_export_offer import (
    ModeloFormElection,
    ModeloFormUnavailable,
    asks_export_elections,
    form_export_offer,
    form_receipt,
    revision_file_format,
)
from ..work_form_header import export_hold
from ..work_form_models import (
    TYPED_EDITABILITIES,
    ModeloFormCalculationNote,
    ModeloFormEditability,
    ModeloFormExport,
    ModeloFormOrigin,
    ModeloWorkForm,
    map_form_fields,
    revised_field,
)
from ..work_form_service import ModeloWorkFormLoadV1
from ..work_form_typing_effect import (
    ModeloFormDisplacement,
    form_typing_effects,
    typing_effect_words,
)
from ..workbench_projection import project_modelo_workbench_form, restore_modelo_workbench_form
from ..workbench_read import ModeloWorkbenchFormReadV1
from .work_form_fixture import built_form, form_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_EN = OutputLanguage.EN
_FILED_AT = datetime(2026, 4, 18, 9, 0, tzinfo=UTC)
_VERIFIED_AT = datetime(2026, 4, 20, 10, 0, tzinfo=UTC)


def _offer(operation: PinnedAuthorityOperation, modelo: str, year: int, code: str):
    form = built_form(operation, modelo, year, code, entered=frozenset())
    return form_export_offer(
        modelo, form_snapshot(operation, modelo, year, code), _EN, form=form, verified=False, filed=False
    )


def test_elections_are_asked_exactly_where_the_terminal_asked_them(operation: PinnedAuthorityOperation) -> None:
    """The workbench asked the payment and refund elections for Modelo 303 and no other modelo."""
    asked = {modelo for modelo in operation.modelo_ids() if asks_export_elections(modelo)}

    assert asked == {"303"}


def test_a_modelo_303_asks_its_three_elections_preset_to_their_neutral_defaults(
    operation: PinnedAuthorityOperation,
) -> None:
    offer = _offer(operation, "303", 2026, "1T")
    other = _offer(operation, "130", 2026, "1T")

    questions = {question.election: question for question in offer.elections}
    assert offer.asks_elections and set(questions) == set(ModeloFormElection)
    assert questions[ModeloFormElection.REFUND].default == RefundElection.COMPENSAR.value
    assert questions[ModeloFormElection.PAYMENT].default == PaymentElection.INGRESO.value
    assert questions[ModeloFormElection.PRIOR_DOMICILIATION].default == PriorDomiciliationElection.KEEP.value
    assert {choice.value for choice in questions[ModeloFormElection.PAYMENT].choices} == {
        member.value for member in PaymentElection
    }
    assert all(choice.words != choice.value for question in offer.elections for choice in question.choices)
    assert not other.asks_elections and other.elections == ()


def test_the_artefacts_offered_follow_the_installed_extras(operation: PinnedAuthorityOperation) -> None:
    offer = _offer(operation, "130", 2026, "1T")

    artefacts = tuple(option.artefact for option in offer.artefacts)
    assert artefacts[0] is ModeloExportArtefact.FICHERO_BOE
    assert (ModeloExportArtefact.CALCULATION_REPORT_PDF in artefacts) is optional_extra_available(PDF_EXTRA)
    assert ModeloExportArtefact.CALCULATION_REPORT_CSV in artefacts


@pytest.mark.parametrize(
    ("modelo", "year", "code", "expected"),
    [
        ("303", 2026, "1T", ExportLayoutFormat.FIXED_WIDTH),
        ("130", 2026, "1T", ExportLayoutFormat.FIXED_WIDTH),
        ("100", 2024, "0A", ExportLayoutFormat.XML_DICTIONARY),
    ],
)
def test_the_file_format_is_the_one_the_revisions_export_layout_declares(
    operation: PinnedAuthorityOperation, modelo: str, year: int, code: str, expected: ExportLayoutFormat
) -> None:
    snapshot = form_snapshot(operation, modelo, year, code)
    offer = _offer(operation, modelo, year, code)

    assert revision_file_format(snapshot) is expected
    assert offer.file_format is expected and offer.file_format_words


def _record(**update: object) -> ModeloRecord:
    fields: dict[str, object] = {
        "filing_record_id": derive_filing_record_id(
            work_unit_id="b" * 64, calculation_revision_id="a" * 64, filed_by="x"
        ),
        "work_unit_id": "b" * 64,
        "calculation_revision_id": "a" * 64,
        "bucket_id": "13000000-0000-4000-8000-000000000455",
        "modelo": "130",
        "filing_year": 2026,
        "period": Period.from_year_and_code(2026, "1T"),
        "filed_at": _FILED_AT,
        "filed_by": "x",
        "origin": FilingOrigin.LOCAL,
        "confirmation": AeatConfirmationState.PENDIENTE,
        "declaration_kind": FilingDeclarationKind.ORIGINAL,
    }
    return ModeloRecord.model_validate(fields | update)


def test_a_receipt_is_verified_only_by_an_in_force_filing_the_aeat_holds() -> None:
    evidence = ExternalEvidence(
        kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF, reference_id="c" * 64, imported_at=_VERIFIED_AT
    )
    confirmed = _record(confirmation=AeatConfirmationState.CONFIRMADA, external_evidence=evidence)
    replaced = _record(
        confirmation=AeatConfirmationState.CONFIRMADA,
        external_evidence=evidence,
        status=ModeloRecordStatus.SUPERSEDIDO,
        superseded_at=_VERIFIED_AT,
        superseded_by_filing_record_id="d" * 64,
    )

    verified = form_receipt(confirmed, recorded_at=_FILED_AT, language=_EN)
    pending = form_receipt(_record(), recorded_at=_FILED_AT, language=_EN)
    superseded = form_receipt(replaced, recorded_at=_FILED_AT, language=_EN)
    unread = form_receipt(None, recorded_at=None, language=_EN)

    assert (verified.verified, verified.verified_at, verified.recorded_at) == (True, _VERIFIED_AT, _FILED_AT)
    assert not pending.verified and pending.verified_at is None
    assert not superseded.verified and not unread.verified
    assert verified.words != pending.words


def test_typing_over_a_box_is_worded_as_the_review_words_its_change(operation: PinnedAuthorityOperation) -> None:
    """Only a box the filer types on is worded, once, and a calculated box says its figure is replaced."""
    built = built_form(operation, "130", 2026, "1T", held={"01": Decimal("1200.00")}, entered=frozenset({"01"}))
    form = map_form_fields(
        built,
        lambda field: (
            revised_field(
                field,
                editability=ModeloFormEditability.EDITABLE_VALUE,
                not_writable_reason=None,
                origin=ModeloFormOrigin.CALCULATED if field.value is not None else field.origin,
            )
            if field.box == "01"
            else field
        ),
    )
    effects = {effect.address: effect.words for effect in form_typing_effects(form, _EN)}

    typed = [field for field in form.fields() if field.editability in TYPED_EDITABILITIES]
    assert typed
    assert set(effects) == {field.address for field in typed}
    assert all(effects[field.address] == typing_effect_words(field, _EN) for field in typed)
    calculated = [field for field in typed if field.origin is ModeloFormOrigin.CALCULATED]
    assert calculated
    assert all(effects[field.address] == "replaces the calculated value" for field in calculated)
    displaced = {effect.address: effect.displaces for effect in form_typing_effects(form, _EN)}
    assert all(displaced[field.address] is ModeloFormDisplacement.CALCULATION for field in calculated)
    assert all(field.address not in effects for field in form.fields() if field.editability not in TYPED_EDITABILITIES)


def test_the_public_read_carries_the_offer_receipt_and_typing_words(operation: PinnedAuthorityOperation) -> None:
    form = built_form(operation, "303", 2026, "1T", entered=frozenset(), lifecycle=CalculationRevisionState.PRESENTADO)
    read = ModeloWorkbenchFormReadV1(
        load=ModeloWorkFormLoadV1(form=form, verified=True, filed=True),
        admission=ModeloEditRefusedV1(
            refusal=ModeloEditDomainRefusalV1(
                code=ModeloEditRefusalCode.ADMISSION_DENIED,
                facts=("current_calculation_revision_id",),
                responsible_owner=RESPONSIBLE_OWNER,
                reconsideration_condition="calculate the declaration before editing it",
            )
        ),
        calculation_revision_id=None,
        verification_report_id=None,
        asks_m303_evidence=False,
        asks_modelo_390=False,
        registry_revision_id=form.registry_revision_id,
        tax_id_format=runtime_tax_id_format(authority=operation),
        export_offer=form_export_offer(
            "303", form_snapshot(operation, "303", 2026, "1T"), _EN, form=form, verified=True, filed=True
        ),
        receipt=form_receipt(_record(), recorded_at=_FILED_AT, language=_EN),
    )

    projection = project_modelo_workbench_form(UUID("13000000-0000-4000-8000-000000000455"), form.work_unit_id, read)
    restored = restore_modelo_workbench_form(type(projection).model_validate_json(projection.model_dump_json()))

    assert projection.export_offer == read.export_offer and projection.receipt == read.receipt
    assert projection.typing_effects == read.typing_effects
    assert restored == read and restored.receipt_confirmed is False


_HELD_210: dict[str, Decimal | str] = {"rendimientos_integros": Decimal("1200.00"), "tipo_renta": "01"}


def _availability(form: ModeloWorkForm, operation: PinnedAuthorityOperation, *, verified: bool, filed: bool = False):
    offer = form_export_offer(
        "210", form_snapshot(operation, "210", 2025, "0A"), _EN, form=form, verified=verified, filed=filed
    )
    return {option.artefact: option.availability for option in offer.artefacts}, offer.record


def _package(form: ModeloWorkForm, operation: PinnedAuthorityOperation, *, verified: bool):
    offer = form_export_offer(
        "210", form_snapshot(operation, "210", 2025, "0A"), _EN, form=form, verified=verified, filed=False
    )
    assert offer.review_package.words
    return offer.review_package.availability


def _entered_210(operation: PinnedAuthorityOperation, **update: object) -> ModeloWorkForm:
    form = built_form(operation, "210", 2025, "0A", held=_HELD_210, entered=frozenset(_HELD_210))
    return form.model_copy(update=update)


def test_nothing_is_offered_before_a_calculation(operation: PinnedAuthorityOperation) -> None:
    artefacts, record = _availability(_entered_210(operation), operation, verified=False)

    assert {item.reason for item in (*artefacts.values(), record)} == {ModeloFormUnavailable.NOT_CALCULATED}
    assert all(item.words for item in (*artefacts.values(), record))


def test_an_unchecked_calculation_offers_only_the_review_spreadsheet(operation: PinnedAuthorityOperation) -> None:
    artefacts, record = _availability(
        _entered_210(operation, calculation_revision_id="c" * 64), operation, verified=False
    )

    assert artefacts[ModeloExportArtefact.CALCULATION_REVIEW_XLSX].available
    package = _package(_entered_210(operation, calculation_revision_id="c" * 64), operation, verified=False)
    assert package.reason is ModeloFormUnavailable.NOT_VERIFIED
    for artefact in (ModeloExportArtefact.FICHERO_BOE, ModeloExportArtefact.CALCULATION_REPORT_CSV):
        assert artefacts[artefact].reason is ModeloFormUnavailable.NOT_VERIFIED, artefact
    assert record.reason is ModeloFormUnavailable.NOT_VERIFIED


def test_a_checked_clean_calculation_offers_every_artefact_and_the_recording(
    operation: PinnedAuthorityOperation,
) -> None:
    form = _entered_210(
        operation, calculation_revision_id="c" * 64, verification=VerificationCompletenessStatus.COMPLETE
    )

    artefacts, record = _availability(form, operation, verified=True)

    assert all(item.available for item in artefacts.values()), artefacts
    assert record.available
    assert _package(form, operation, verified=True).available


def test_what_blocks_filing_withholds_the_file_and_the_recording_but_not_the_reports(
    operation: PinnedAuthorityOperation,
) -> None:
    reason = sorted(GATE_REFUSED_REASONS - CHECK_REFUSED_REASONS)[0]
    note = ModeloFormCalculationNote(
        reason=reason, attention=CALCULATION_NOTE_ATTENTION[reason], withholds_filing=gate_refuses(reason, None)
    )
    form = _entered_210(
        operation,
        calculation_revision_id="c" * 64,
        verification=VerificationCompletenessStatus.COMPLETE,
        calculation_notes=(note,),
    )

    artefacts, record = _availability(form, operation, verified=True)
    hold = export_hold(form, _EN, verified=True, recorded=False)

    assert hold is not None
    assert artefacts[ModeloExportArtefact.FICHERO_BOE].reason is ModeloFormUnavailable.BLOCKS
    assert artefacts[ModeloExportArtefact.FICHERO_BOE].words == hold.words
    assert record.reason is ModeloFormUnavailable.BLOCKS
    assert _package(form, operation, verified=True).reason is ModeloFormUnavailable.BLOCKS
    assert artefacts[ModeloExportArtefact.CALCULATION_REPORT_CSV].available


def test_a_file_from_an_earlier_calculation_withholds_the_recording_and_a_recorded_one_is_not_recorded_again(
    operation: PinnedAuthorityOperation,
) -> None:
    clean = _entered_210(
        operation, calculation_revision_id="c" * 64, verification=VerificationCompletenessStatus.COMPLETE
    )
    stale = clean.model_copy(
        update={"last_export": ModeloFormExport(exported_at=_FILED_AT, calculation_revision_id="d" * 64, current=False)}
    )

    artefacts, record = _availability(stale, operation, verified=True)
    _, recorded = _availability(clean, operation, verified=True, filed=True)

    assert artefacts[ModeloExportArtefact.FICHERO_BOE].available
    assert record.reason is ModeloFormUnavailable.FILE_OUT_OF_DATE
    assert recorded.reason is ModeloFormUnavailable.RECORDED
