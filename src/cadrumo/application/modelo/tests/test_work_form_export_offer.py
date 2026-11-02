"""Exporting offers the same artefacts, elections and file format, and states the same receipt, for every frontend.

The elections are asked where each modelo's declared result codes, or the
law's two-instalment payment, give them something to choose, each with its
state for the declaration's result; the file
format is the one the revision's export layout declares; and the receipt is
verified only by an in-force filing the AEAT is seen to hold. Forms are built
by the real builder over the published registry; filing records are synthetic.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from ....core.export_layout_format import ExportLayoutFormat
from ....core.external_constants import OutputLanguage
from ....core.modelo_export_artefact import ModeloExportArtefact
from ....core.payment_election import PaymentElection
from ....core.payment_instalment_election import PaymentInstalmentElection
from ....core.period import Period
from ....core.prior_domiciliation_election import PriorDomiciliationElection
from ....core.refund_election import RefundElection
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.deadlines.festivos import DeadlineHolidayCoverage
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
from ....domain.transactions.own_accounts import (
    OwnAccountDesignation,
    OwnAccountHolding,
    OwnAccountRegister,
    OwnAccountRole,
    OwnBankAccountDetails,
)
from ..calculation_note_gate import gate_refuses
from ..calculation_notes import CALCULATION_NOTE_ATTENTION, CHECK_REFUSED_REASONS, GATE_REFUSED_REASONS
from ..work_form_declaration_facts import ModeloFormCalculationNote, ModeloFormDeadline, ModeloFormExport
from ..work_form_export_offer import (
    EXPORT_ARTEFACT_LOCALE_KEYS,
    ModeloFormElection,
    ModeloFormElectionQuestion,
    ModeloFormElectionReason,
    ModeloFormElectionState,
    ModeloFormUnavailable,
    asks_export_elections,
    form_export_offer,
    form_receipt,
    revision_file_format,
)
from ..work_form_header import export_hold
from ..work_form_models import (
    TYPED_EDITABILITIES,
    ModeloFormEditability,
    ModeloFormOrigin,
    ModeloWorkForm,
    map_form_fields,
    revised_field,
)
from ..work_form_typing_effect import (
    ModeloFormDisplacement,
    form_typing_effects,
    typing_effect_words,
)
from ..workbench_projection import project_modelo_workbench_form, restore_modelo_workbench_form
from .work_form_fixture import built_form, form_snapshot, read_before_calculation

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_EN = OutputLanguage.EN
_FILED_AT = datetime(2026, 4, 18, 9, 0, tzinfo=UTC)
_VERIFIED_AT = datetime(2026, 4, 20, 10, 0, tzinfo=UTC)


def _offer(operation: PinnedAuthorityOperation, modelo: str, year: int, code: str):
    form = built_form(operation, modelo, year, code, entered=frozenset())
    return form_export_offer(
        modelo, form_snapshot(operation, modelo, year, code), _EN, form=form, verified=False, filed=False
    )


def test_elections_are_asked_where_a_design_declares_a_carry_or_the_law_a_split(
    operation: PinnedAuthorityOperation,
) -> None:
    """Modelo 303 declares carrying a credit or refunding it; Modelo 100's result may be paid in two instalments."""
    asked = {modelo for modelo in operation.modelo_ids() if asks_export_elections(modelo)}

    assert asked == {"100", "303"}


def test_a_modelo_303_asks_its_three_elections_preset_to_their_neutral_defaults(
    operation: PinnedAuthorityOperation,
) -> None:
    offer = _offer(operation, "303", 2026, "1T")
    payable = _calculated(operation, "303", 2026, "1T", Decimal("120.00"))
    other = _offer(operation, "130", 2026, "1T")

    questions = {question.election: question for question in offer.elections}
    assert offer.asks_elections and set(questions) == {
        ModeloFormElection.REFUND,
        ModeloFormElection.PAYMENT,
        ModeloFormElection.PRIOR_DOMICILIATION,
    }
    assert questions[ModeloFormElection.REFUND].default == RefundElection.COMPENSAR.value
    assert questions[ModeloFormElection.PRIOR_DOMICILIATION].default == PriorDomiciliationElection.KEEP.value
    unknown = questions[ModeloFormElection.PAYMENT]
    assert unknown.state is ModeloFormElectionState.UNAVAILABLE
    assert unknown.reason is ModeloFormElectionReason.RESULT_UNKNOWN and unknown.state_words
    assert unknown.default is None and unknown.choices == ()
    payment = _questions(operation, payable)[ModeloFormElection.PAYMENT]
    assert payment.state is ModeloFormElectionState.AVAILABLE and payment.request_field == "payment_election"
    assert payment.default == PaymentElection.INGRESO.value
    assert {choice.value for choice in payment.choices} == {member.value for member in PaymentElection}
    assert all(choice.words != choice.value for question in offer.elections for choice in question.choices)
    assert not other.asks_elections and other.elections == ()


_TODAY = date(2026, 5, 4)
_SPANISH_IBAN = "ES9121000418450200051332"
_GERMAN_IBAN = "DE89370400440532013000"


def _deadline(days: int) -> ModeloFormDeadline:
    closes = _TODAY + timedelta(days=days)
    return ModeloFormDeadline(
        closes_on=closes,
        nominal_closes_on=closes,
        holiday_coverage=DeadlineHolidayCoverage.NATIONAL_ONLY,
        reference_on=_TODAY,
        days_remaining=days if days >= 0 else None,
        days_overdue=-days if days < 0 else None,
    )


def _calculated(
    operation: PinnedAuthorityOperation,
    modelo: str,
    year: int,
    code: str,
    result: Decimal,
    *,
    deadline: ModeloFormDeadline | None = None,
) -> ModeloWorkForm:
    """A calculated form whose settlement box holds ``result``, built by the real builder."""
    blank = built_form(operation, modelo, year, code, entered=frozenset())
    assert blank.result is not None
    form = built_form(operation, modelo, year, code, held={str(blank.result.casilla_id): result}, entered=frozenset())
    return form.model_copy(update={"calculation_revision_id": "c" * 64, "deadline": deadline})


def _register(*accounts: tuple[str, str], designate: str | None = None) -> OwnAccountRegister:
    register = OwnAccountRegister()
    for label, iban in accounts:
        register = register.with_new_account(
            OwnBankAccountDetails(
                label=label,
                holding=OwnAccountHolding.TITULAR,
                iban=iban,
                swift_bic="" if iban.startswith("ES") else "COBADEFFXXX",
            )
        )
    if designate is not None:
        for role in OwnAccountRole:
            register = register.with_designation(OwnAccountDesignation(role=role, own_account_id=designate))
    return register


def _questions(
    operation: PinnedAuthorityOperation,
    form: ModeloWorkForm,
    *,
    own_accounts: OwnAccountRegister | None = None,
    amended: bool = False,
) -> dict[ModeloFormElection, ModeloFormElectionQuestion]:
    modelo = str(form.modelo)
    snapshot = form_snapshot(operation, modelo, form.filing_year, str(form.period.code))
    offer = form_export_offer(
        modelo, snapshot, _EN, form=form, verified=False, filed=False, own_accounts=own_accounts, amended=amended
    )
    return {question.election: question for question in offer.elections}


def test_a_modelo_100_to_pay_within_its_period_offers_the_split_and_the_debit_account(
    operation: PinnedAuthorityOperation,
) -> None:
    form = _calculated(operation, "100", 2025, "0A", Decimal("1000.00"), deadline=_deadline(30))
    register = _register(("Nómina", _SPANISH_IBAN), ("Berlin", _GERMAN_IBAN), designate="acc-01")

    questions = _questions(operation, form, own_accounts=register)

    assert set(questions) == {
        ModeloFormElection.PAYMENT,
        ModeloFormElection.INSTALMENT,
        ModeloFormElection.CHARGE_ACCOUNT,
        ModeloFormElection.REFUND_ACCOUNT,
    }
    instalment = questions[ModeloFormElection.INSTALMENT]
    assert instalment.state is ModeloFormElectionState.AVAILABLE
    assert instalment.request_field == "instalment_election" and instalment.help is not None
    assert instalment.default == PaymentInstalmentElection.SINGLE.value
    assert {choice.value for choice in instalment.choices} == {member.value for member in PaymentInstalmentElection}
    payment = questions[ModeloFormElection.PAYMENT]
    # Modelo 100 declares no "cuenta corriente tributaria" code, so that method is not offered.
    assert {choice.value for choice in payment.choices} == {
        PaymentElection.INGRESO.value,
        PaymentElection.DOMICILIACION.value,
    }
    charge = questions[ModeloFormElection.CHARGE_ACCOUNT]
    assert charge.state is ModeloFormElectionState.AVAILABLE and charge.request_field == "charge_account_id"
    assert [choice.value for choice in charge.choices] == ["acc-01"] and charge.default == "acc-01"
    refund = questions[ModeloFormElection.REFUND_ACCOUNT]
    assert refund.state is ModeloFormElectionState.NOT_APPLICABLE
    assert refund.reason is ModeloFormElectionReason.NOTHING_TO_REFUND and refund.choices == ()


def test_an_account_is_offered_by_its_label_and_mask_never_its_number(operation: PinnedAuthorityOperation) -> None:
    form = _calculated(operation, "100", 2025, "0A", Decimal("-310.40"), deadline=_deadline(30))
    register = _register(("Nómina", _SPANISH_IBAN), ("Berlin", _GERMAN_IBAN))

    questions = _questions(operation, form, own_accounts=register)

    refund = questions[ModeloFormElection.REFUND_ACCOUNT]
    assert refund.state is ModeloFormElectionState.AVAILABLE and refund.request_field == "refund_account_id"
    assert [choice.value for choice in refund.choices] == ["acc-01", "acc-02"]
    assert refund.default is None
    assert all(choice.words.startswith(("Nómina (ES", "Berlin (DE")) for choice in refund.choices)
    served = repr(questions)
    assert _SPANISH_IBAN not in served and _GERMAN_IBAN not in served
    for election in (ModeloFormElection.PAYMENT, ModeloFormElection.INSTALMENT, ModeloFormElection.CHARGE_ACCOUNT):
        assert questions[election].state is ModeloFormElectionState.NOT_APPLICABLE, election
        assert questions[election].reason is ModeloFormElectionReason.NOTHING_TO_PAY, election


@pytest.mark.parametrize(
    ("deadline", "amended", "reason"),
    [
        (_deadline(-1), False, ModeloFormElectionReason.PAST_FILING_WINDOW),
        (None, False, ModeloFormElectionReason.FILING_WINDOW_UNKNOWN),
        (_deadline(30), True, ModeloFormElectionReason.AMENDMENT),
    ],
)
def test_the_split_is_withheld_with_its_reason_where_the_law_refuses_it(
    operation: PinnedAuthorityOperation,
    deadline: ModeloFormDeadline | None,
    amended: bool,
    reason: ModeloFormElectionReason,
) -> None:
    form = _calculated(operation, "100", 2025, "0A", Decimal("1000.00"), deadline=deadline)

    questions = _questions(operation, form, amended=amended)

    instalment = questions[ModeloFormElection.INSTALMENT]
    assert instalment.state is ModeloFormElectionState.UNAVAILABLE and instalment.reason is reason
    assert instalment.state_words is not None and instalment.default is None and instalment.choices == ()
    assert questions[ModeloFormElection.PAYMENT].state is ModeloFormElectionState.AVAILABLE


def test_a_nil_or_uncalculated_modelo_100_offers_no_settlement(operation: PinnedAuthorityOperation) -> None:
    nil = _questions(operation, _calculated(operation, "100", 2025, "0A", Decimal("0.00"), deadline=_deadline(30)))
    unknown = _questions(operation, built_form(operation, "100", 2025, "0A", entered=frozenset()))

    assert {question.reason for question in nil.values()} == {ModeloFormElectionReason.NOTHING_TO_PAY}
    assert {question.state for question in nil.values()} == {ModeloFormElectionState.NOT_APPLICABLE}
    assert {question.reason for question in unknown.values()} == {ModeloFormElectionReason.RESULT_UNKNOWN}
    assert {question.state for question in unknown.values()} == {ModeloFormElectionState.UNAVAILABLE}


def test_without_an_open_spanish_account_the_debit_account_cannot_be_chosen(
    operation: PinnedAuthorityOperation,
) -> None:
    form = _calculated(operation, "100", 2025, "0A", Decimal("1000.00"), deadline=_deadline(30))
    closed = _register(("Nómina", _SPANISH_IBAN), ("Berlin", _GERMAN_IBAN)).with_closed_account(
        "acc-01", date(2020, 1, 31)
    )

    charge = _questions(operation, form, own_accounts=closed)[ModeloFormElection.CHARGE_ACCOUNT]
    refund = _questions(
        operation,
        _calculated(operation, "100", 2025, "0A", Decimal("-5.00"), deadline=_deadline(30)),
        own_accounts=_register(),
    )[ModeloFormElection.REFUND_ACCOUNT]

    assert charge.state is ModeloFormElectionState.UNAVAILABLE
    assert charge.reason is ModeloFormElectionReason.NO_SPANISH_ACCOUNT
    assert refund.state is ModeloFormElectionState.UNAVAILABLE
    assert refund.reason is ModeloFormElectionReason.NO_OPEN_ACCOUNT


def test_every_export_artefact_is_offered_in_order(operation: PinnedAuthorityOperation) -> None:
    offer = _offer(operation, "130", 2026, "1T")

    artefacts = tuple(option.artefact for option in offer.artefacts)
    assert artefacts[0] is ModeloExportArtefact.FICHERO_BOE
    assert artefacts == tuple(EXPORT_ARTEFACT_LOCALE_KEYS)


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
    read = read_before_calculation(
        form,
        operation,
        verified=True,
        filed=True,
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
