"""What a declaration offers to export, the file format its revision writes, and its filing's receipt.

Every artefact an export publishes is offered. Each says whether it can be
created now, and why not, by the same rules the export and the filing gates apply: the
spreadsheet for review needs a calculation, the calculation report a checked
calculation, and the file for the AEAT, like recording the filing, nothing
that blocks filing or waits to be confirmed, as the header's hold says.
Recording the filing also refuses while the latest file was made from an
earlier calculation. Changes a frontend holds unapplied withhold both too; only
that frontend knows them, so it adds that itself. Each election is asked where
the modelo's official design declares what it chooses between: the refund and
prior-domiciliation elections where it declares both carrying a credit forward
and asking for its refund, the payment election and the account AEAT debits
where it declares direct debit, the account AEAT pays a refund into where it
declares a refund, and the two-instalment payment where the registry
declares the law admits it for the declaration's period. Each question says
whether the declaration's result makes it available, not applicable or
unavailable, and why, in the filer's words; accounts are offered by their
opaque register identity and named only by label and masked number. A result
to pay or refund is settled from the box the declaration settles, so while that
box holds no value, or settles another way than the result, the settlement
questions say so instead of offering an answer. The two-instalment question
states both instalments of the amount to pay, each marked advisory: the
registry declares the first instalment's share, but no official rule says
which instalment a rounded cent belongs to.
Every other modelo exports with the neutral defaults. The file format is the one the
revision's registry export layout declares. A declaration recorded as filed
says whether the AEAT receipt of that filing (its :class:`ModeloRecord`) has been
verified, and when; the export layout is read from the revision's
:class:`RegistrySnapshot`. Nothing here sends anything to the AEAT.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING, Final, Literal

from pydantic import BaseModel, Field, model_validator

from ...core.decimal.grammar import DECIMAL_TEXT_MAX_LENGTH, try_parse_canonical_decimal
from ...core.export_layout_format import ExportLayoutFormat
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import tr
from ...core.modelo import Modelo
from ...core.modelo_export_artefact import ModeloExportArtefact
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.payment_election import PaymentElection
from ...core.payment_instalment_election import (
    PaymentInstalmentElection,
    instalment_amounts,
    second_instalment_is_payable,
)
from ...core.prior_domiciliation_election import PriorDomiciliationElection
from ...core.refund_election import RefundElection
from ...core.result_disposition import ResultDisposition, result_disposition_declares
from ...core.time.clock import today_madrid
from ...domain.calculations.registry.payment_instalment_split import first_instalment_share
from ...domain.calculations.registry.schema_base import CasillaDataType
from ...domain.iva.refund_eligibility import RefundEligibilityOutcome
from ...domain.modelos.filing_record import AeatConfirmationState, ModeloRecordStatus
from ...domain.transactions.own_accounts import OwnAccountRegister, OwnAccountRole, OwnBankAccount
from .export_settlement import SettlementRefusal, declared_settlement
from .settlement_casilla import declaration_settlement_casilla_id
from .value_presentation import format_casilla_value
from .work_form_declaration_facts import ModeloFormResult, ModeloFormResultDirection
from .work_form_field_vocabulary import (
    ModeloFormCasillaAddressV1,
    ModeloFormOrigin,
)
from .work_form_header import ModeloFormExportHoldReason, export_hold, form_recorded
from .work_form_models import ModeloWorkForm
from .work_form_wording import day_text

if TYPE_CHECKING:
    from ...core.casilla_id import CasillaId
    from ...core.period import Period
    from ...domain.calculations.registry.schema import RegistrySnapshot
    from ...domain.modelos.filing_record import ModeloRecord

#: Each artefact in the filer's words, in the order an export offers them.
EXPORT_ARTEFACT_LOCALE_KEYS: Final[Mapping[ModeloExportArtefact, str]] = MappingProxyType(
    {
        ModeloExportArtefact.FICHERO_BOE: "tui.modelo.export.artefact.fichero_boe",
        ModeloExportArtefact.CALCULATION_REPORT_CSV: "tui.modelo.export.artefact.calculation_report_csv",
        ModeloExportArtefact.CALCULATION_REPORT_PDF: "tui.modelo.export.artefact.calculation_report_pdf",
        ModeloExportArtefact.CALCULATION_REVIEW_XLSX: "tui.modelo.export.artefact.calculation_review_xlsx",
    }
)
REFUND_ELECTION_LOCALE_KEYS: Final[Mapping[RefundElection, str]] = MappingProxyType(
    {
        RefundElection.COMPENSAR: "tui.modelo.export.refund_election.compensar",
        RefundElection.DEVOLVER: "tui.modelo.export.refund_election.devolver",
    }
)
PAYMENT_ELECTION_LOCALE_KEYS: Final[Mapping[PaymentElection, str]] = MappingProxyType(
    {
        PaymentElection.INGRESO: "tui.modelo.export.payment_election.ingreso",
        PaymentElection.DOMICILIACION: "tui.modelo.export.payment_election.domiciliacion",
        PaymentElection.CUENTA_CORRIENTE: "tui.modelo.export.payment_election.cuenta_corriente",
    }
)
PRIOR_DOMICILIATION_ELECTION_LOCALE_KEYS: Final[Mapping[PriorDomiciliationElection, str]] = MappingProxyType(
    {
        PriorDomiciliationElection.KEEP: "tui.modelo.export.prior_domiciliation_election.keep",
        PriorDomiciliationElection.CANCEL_OR_MODIFY: "tui.modelo.export.prior_domiciliation_election.cancel_or_modify",
    }
)
INSTALMENT_ELECTION_LOCALE_KEYS: Final[Mapping[PaymentInstalmentElection, str]] = MappingProxyType(
    {
        PaymentInstalmentElection.SINGLE: "tui.modelo.export.instalment_election.single",
        PaymentInstalmentElection.TWO_INSTALMENTS_SECOND_DEBITED: (
            "tui.modelo.export.instalment_election.two_instalments_second_debited"
        ),
        PaymentInstalmentElection.TWO_INSTALMENTS_SECOND_PAID: (
            "tui.modelo.export.instalment_election.two_instalments_second_paid"
        ),
    }
)
_INSTALMENT_CONDITIONS_LOCALE_KEY: Final = "tui.modelo.export.instalment_election.conditions"
_FIRST_INSTALMENT_LOCALE_KEY: Final = "workspace.modelo.export.instalment.first"
_SECOND_INSTALMENT_LOCALE_KEY: Final = "workspace.modelo.export.instalment.second"
_INSTALMENT_ADVISORY_LOCALE_KEY: Final = "workspace.modelo.export.instalment.advisory"
_CHARGE_ACCOUNT_LOCALE_KEY: Final = "tui.modelo.export.account.charge_label"
_REFUND_ACCOUNT_LOCALE_KEY: Final = "tui.modelo.export.account.refund_label"
_ACCOUNT_CHOICE_LOCALE_KEY: Final = "workspace.modelo.export.account_choice"
_DEBIT_ACCOUNT_COUNTRY: Final = "ES"
_FILE_FORMAT_LOCALE_KEYS: Final[Mapping[ExportLayoutFormat, str]] = MappingProxyType(
    {
        layout_format: f"workspace.modelo.export.file_format.{layout_format.value}"
        for layout_format in ExportLayoutFormat
    }
)
_RECEIPT_VERIFIED_LOCALE_KEY: Final = "workspace.modelo.receipt.verified"
_RECEIPT_MISSING_LOCALE_KEY: Final = "workspace.modelo.receipt.missing"


class ModeloFormElection(StrEnum):
    """One declaration-shaping choice an export asks."""

    REFUND = "refund"
    PAYMENT = "payment"
    PRIOR_DOMICILIATION = "prior_domiciliation"
    #: Whether a result to pay is paid at once or in two instalments, and how the second is paid.
    INSTALMENT = "instalment"
    #: Which own account AEAT debits for a direct-debited payment.
    CHARGE_ACCOUNT = "charge_account"
    #: Which own account AEAT pays a refund into.
    REFUND_ACCOUNT = "refund_account"


#: The export request field each election's answer is sent in.
type ModeloExportRequestField = Literal[
    "refund_election",
    "payment_election",
    "prior_domiciliation_election",
    "instalment_election",
    "charge_account_id",
    "refund_account_id",
]

_REQUEST_FIELDS: Final[Mapping[ModeloFormElection, ModeloExportRequestField]] = MappingProxyType(
    {
        ModeloFormElection.REFUND: "refund_election",
        ModeloFormElection.PAYMENT: "payment_election",
        ModeloFormElection.PRIOR_DOMICILIATION: "prior_domiciliation_election",
        ModeloFormElection.INSTALMENT: "instalment_election",
        ModeloFormElection.CHARGE_ACCOUNT: "charge_account_id",
        ModeloFormElection.REFUND_ACCOUNT: "refund_account_id",
    }
)


class ModeloFormElectionState(StrEnum):
    """Whether the filer can answer an election now."""

    AVAILABLE = "available"
    #: The declaration's result makes the election meaningless, so it is not sent.
    NOT_APPLICABLE = "not_applicable"
    #: The election would apply, but something stops it being answered now.
    UNAVAILABLE = "unavailable"


class ModeloFormElectionReason(StrEnum):
    """Why an election is not applicable or cannot be answered now."""

    #: Not applicable: the result is not an amount to pay.
    NOTHING_TO_PAY = "nothing_to_pay"
    #: Not applicable: the result is not a refund.
    NOTHING_TO_REFUND = "nothing_to_refund"
    #: Unavailable: the declaration has no calculated result yet.
    RESULT_UNKNOWN = "result_unknown"
    #: Unavailable: a corrective declaration cannot be paid in two instalments.
    AMENDMENT = "amendment"
    #: Unavailable: the filing period has ended, and two instalments need the return filed within it.
    PAST_FILING_WINDOW = "past_filing_window"
    #: Unavailable: the filing period is not known, so filing within it cannot be established.
    FILING_WINDOW_UNKNOWN = "filing_window_unknown"
    #: Unavailable: no own account is open to receive a refund.
    NO_OPEN_ACCOUNT = "no_open_account"
    #: Unavailable: no open Spanish own account can be debited.
    NO_SPANISH_ACCOUNT = "no_spanish_account"
    #: Unavailable: the amount the declaration settles goes another way than its result, such as a
    #: result to pay of which nothing remains to pay, and the official design gives no settlement for it.
    SETTLEMENT_UNSUPPORTED = "settlement_unsupported"
    #: Unavailable: the second instalment of the amount to pay would be nothing, so it is paid at once.
    SECOND_INSTALMENT_NOTHING = "second_instalment_nothing"
    #: Not applicable: the negative IVA result may only be carried forward, because the period is not
    #: the year's last and the filer is not inscribed in the Registro de devolución mensual.
    CARRY_FORWARD_ONLY = "carry_forward_only"
    #: Unavailable: outside the year's last period the refund needs the filer's REDEME inscription,
    #: which their profile does not state.
    REDEME_UNSTATED = "redeme_unstated"


_NOT_APPLICABLE_REASONS: Final = frozenset(
    {
        ModeloFormElectionReason.NOTHING_TO_PAY,
        ModeloFormElectionReason.NOTHING_TO_REFUND,
        ModeloFormElectionReason.CARRY_FORWARD_ONLY,
    },
)
_ELECTION_REASON_LOCALE_KEYS: Final[Mapping[ModeloFormElectionReason, str]] = MappingProxyType(
    {
        ModeloFormElectionReason.NOTHING_TO_PAY: "workspace.modelo.export.election.nothing_to_pay",
        ModeloFormElectionReason.NOTHING_TO_REFUND: "workspace.modelo.export.election.nothing_to_refund",
        ModeloFormElectionReason.RESULT_UNKNOWN: "workspace.modelo.export.election.result_unknown",
        ModeloFormElectionReason.AMENDMENT: "workspace.modelo.export.election.amendment",
        ModeloFormElectionReason.PAST_FILING_WINDOW: "workspace.modelo.export.election.past_filing_window",
        ModeloFormElectionReason.FILING_WINDOW_UNKNOWN: "workspace.modelo.export.election.filing_window_unknown",
        ModeloFormElectionReason.NO_OPEN_ACCOUNT: "workspace.modelo.export.election.no_open_account",
        ModeloFormElectionReason.NO_SPANISH_ACCOUNT: "workspace.modelo.export.election.no_spanish_account",
        ModeloFormElectionReason.SETTLEMENT_UNSUPPORTED: "workspace.modelo.export.election.settlement_unsupported",
        ModeloFormElectionReason.SECOND_INSTALMENT_NOTHING: (
            "workspace.modelo.export.election.second_instalment_nothing"
        ),
        ModeloFormElectionReason.CARRY_FORWARD_ONLY: "workspace.modelo.export.election.carry_forward_only",
        ModeloFormElectionReason.REDEME_UNSTATED: "workspace.modelo.export.election.redeme_unstated",
    }
)
_REFUND_ELIGIBILITY_REASONS: Final[Mapping[RefundEligibilityOutcome, ModeloFormElectionReason]] = MappingProxyType(
    {
        RefundEligibilityOutcome.CARRY_FORWARD_ONLY: ModeloFormElectionReason.CARRY_FORWARD_ONLY,
        RefundEligibilityOutcome.UNDETERMINED_REDEME_UNSTATED: ModeloFormElectionReason.REDEME_UNSTATED,
    }
)
"""The reason the refund is not offered, for each resolver outcome that withholds it; REFUND_ALLOWED has none."""


class ModeloFormUnavailable(StrEnum):
    """Why an export, or recording the filing, cannot be done now."""

    #: There is no calculation to export or record yet.
    NOT_CALCULATED = "not_calculated"
    #: The current calculation has not been checked.
    NOT_VERIFIED = "not_verified"
    #: Something blocks filing, found by the check or by the calculation.
    BLOCKS = "blocks"
    #: An assumed value waits for the filer to confirm it.
    CONFIRM = "confirm"
    #: The latest file for the AEAT was made from an earlier calculation, so it must be created again first.
    FILE_OUT_OF_DATE = "file_out_of_date"
    #: The declaration is already recorded as filed; changing it starts a correction.
    RECORDED = "recorded"


class ModeloFormAvailability(BaseModel):
    """Whether an export, or recording the filing, can be done now, and if not why, in the filer's words."""

    model_config = STRICT_FROZEN_CONFIG

    available: bool
    reason: ModeloFormUnavailable | None = None
    words: str | None = None

    @model_validator(mode="after")
    def _a_reason_exactly_when_unavailable(self) -> ModeloFormAvailability:
        if (self.reason is None) is not self.available or (self.words is None) is not self.available:
            raise ValueError("an unavailable action carries its reason and its words, and an available one neither")
        return self


class ModeloFormArtefactOption(BaseModel):
    """One artefact the export offers, in the filer's words, and whether it can be created now."""

    model_config = STRICT_FROZEN_CONFIG

    artefact: ModeloExportArtefact
    words: str = Field(min_length=1)
    availability: ModeloFormAvailability


class ModeloFormElectionChoice(BaseModel):
    """One answer an election takes: the value the export request carries, and its words."""

    model_config = STRICT_FROZEN_CONFIG

    value: str = Field(min_length=1)
    words: str = Field(min_length=1)


class ModeloFormInstalment(StrEnum):
    """One instalment of an amount to pay in two."""

    FIRST = "first"
    SECOND = "second"


class ModeloFormElectionFigure(BaseModel):
    """One amount an election states, in the filer's words, and whether it is advisory.

    ``amount`` is the exact decimal text of a non-negative amount in cents, so
    the served contract carries the figure as written rather than a number a
    reader may round. An advisory figure is one Cadrumo works out where no
    official rule fixes it; ``advisory_words`` then says why, and only then.
    """

    model_config = STRICT_FROZEN_CONFIG

    instalment: ModeloFormInstalment
    amount: str = Field(min_length=1, max_length=DECIMAL_TEXT_MAX_LENGTH)
    words: str = Field(min_length=1)
    advisory: bool
    advisory_words: str | None = None

    @model_validator(mode="after")
    def _advisory_says_why(self) -> ModeloFormElectionFigure:
        if try_parse_canonical_decimal(self.amount, signed=False, max_fraction_digits=2) is None:
            raise ValueError("a figure's amount is the decimal text of a non-negative amount in cents")
        if self.advisory is (self.advisory_words is None):
            raise ValueError("an advisory figure carries its words, and only an advisory one")
        return self


class ModeloFormElectionQuestion(BaseModel):
    """One election the export asks, its state, and its answers pre-set to the neutral default.

    An available question carries its choices; its ``default`` is one of them,
    or ``None`` when no answer is neutral (an account nothing designates), and
    the export then resolves the register's designation. A question that is not
    applicable or unavailable carries its reason and its words instead, no
    choices and no default, and is not sent. ``request_field`` is the export
    request field an answer is sent in.
    """

    model_config = STRICT_FROZEN_CONFIG

    election: ModeloFormElection
    request_field: ModeloExportRequestField
    words: str = Field(min_length=1)
    state: ModeloFormElectionState = ModeloFormElectionState.AVAILABLE
    reason: ModeloFormElectionReason | None = None
    #: Why the question is not applicable or unavailable, in the filer's words.
    state_words: str | None = None
    #: The conditions an answer carries, in the filer's words, where the law attaches any.
    help: str | None = None
    default: str | None = None
    choices: tuple[ModeloFormElectionChoice, ...] = ()
    #: The amounts an available answer states, such as the two instalments of a split payment.
    figures: tuple[ModeloFormElectionFigure, ...] = ()

    @model_validator(mode="after")
    def _state_shapes_the_question(self) -> ModeloFormElectionQuestion:
        if self.request_field != _REQUEST_FIELDS[self.election]:
            raise ValueError("an election is sent in its own request field")
        if self.figures and self.state is not ModeloFormElectionState.AVAILABLE:
            raise ValueError("only an available election states figures")
        if self.state is ModeloFormElectionState.AVAILABLE:
            _require_available_shape(self)
        else:
            _require_unanswerable_shape(self)
        return self


def _require_available_shape(question: ModeloFormElectionQuestion) -> None:
    """An available election carries choices and no reason, and any default is one of its choices."""
    if question.reason is not None or question.state_words is not None or not question.choices:
        raise ValueError("an available election carries choices and no reason")
    if question.default is not None and question.default not in {choice.value for choice in question.choices}:
        raise ValueError("an election's default must be one of its choices")


def _require_unanswerable_shape(question: ModeloFormElectionQuestion) -> None:
    """A not-applicable or unavailable election carries its reason and words, matching its state, and no answers."""
    if question.reason is None or question.state_words is None or question.choices or question.default is not None:
        raise ValueError("an election that cannot be answered carries its reason and words, and no choices")
    if (question.reason in _NOT_APPLICABLE_REASONS) is not (question.state is ModeloFormElectionState.NOT_APPLICABLE):
        raise ValueError("an election's reason matches its state")


class ModeloFormReviewPackageOffer(BaseModel):
    """The package for the filer's accountant, in the filer's words, and whether it can be built now."""

    model_config = STRICT_FROZEN_CONFIG

    words: str = Field(min_length=1)
    availability: ModeloFormAvailability


class ModeloFormExportOffer(BaseModel):
    """What the declaration may export, whether the export asks elections, and the file its revision writes.

    ``elections`` is empty exactly when ``asks_elections`` is false; the export
    then carries each election's neutral default. ``file_format`` is ``None``
    when the revision declares no export layout.
    """

    model_config = STRICT_FROZEN_CONFIG

    artefacts: tuple[ModeloFormArtefactOption, ...] = Field(min_length=1)
    #: Whether the filing can be recorded now, and if not why.
    record: ModeloFormAvailability
    #: The package for the filer's accountant, which carries the file for the AEAT.
    review_package: ModeloFormReviewPackageOffer
    asks_elections: bool
    elections: tuple[ModeloFormElectionQuestion, ...]
    file_format: ExportLayoutFormat | None
    file_format_words: str | None

    @model_validator(mode="after")
    def _elections_follow_the_offer(self) -> ModeloFormExportOffer:
        if bool(self.elections) is not self.asks_elections:
            raise ValueError("an export offer carries its elections exactly when it asks them")
        if (self.file_format is None) is not (self.file_format_words is None):
            raise ValueError("a file format and its words are present together")
        return self


class ModeloFormReceipt(BaseModel):
    """Whether the AEAT receipt of the recorded filing has been verified, and when.

    ``verified_at`` is when the verified receipt was imported, and is set only
    when ``verified`` is.
    """

    model_config = STRICT_FROZEN_CONFIG

    recorded_at: datetime | None
    verified: bool
    verified_at: datetime | None
    words: str = Field(min_length=1)

    @model_validator(mode="after")
    def _verified_has_its_time(self) -> ModeloFormReceipt:
        if self.verified is (self.verified_at is None):
            raise ValueError("a verified receipt carries its time, and only a verified one")
        return self


def _declares_refund_or_carry(modelo: str) -> bool:
    return result_disposition_declares(modelo, ResultDisposition.COMPENSACION) and result_disposition_declares(
        modelo, ResultDisposition.DEVOLUCION
    )


def _instalment_share(modelo: str, period: Period) -> Decimal | None:
    return first_instalment_share(modelo, period_day=period.end_date)


def asks_export_elections(modelo: str, period: Period) -> bool:
    """Whether exporting ``modelo`` for ``period`` asks how its result settles.

    The refund election chooses between carrying a credit forward and asking
    for its refund, so it exists where the official design declares both; the
    two-instalment payment exists where the registry declares the law admits
    it for the period. Either makes the export ask its settlement elections.
    """
    return _declares_refund_or_carry(modelo) or _instalment_share(modelo, period) is not None


def _asked_elections(modelo: str, period: Period) -> tuple[ModeloFormElection, ...]:
    """The elections exporting ``modelo`` asks, each where its design declares what it chooses between."""
    if not asks_export_elections(modelo, period):
        return ()
    carry = _declares_refund_or_carry(modelo)
    debit = result_disposition_declares(modelo, ResultDisposition.DOMICILIACION)
    asked = {
        ModeloFormElection.REFUND: carry,
        ModeloFormElection.PAYMENT: debit,
        ModeloFormElection.PRIOR_DOMICILIATION: carry,
        ModeloFormElection.INSTALMENT: _instalment_share(modelo, period) is not None,
        ModeloFormElection.CHARGE_ACCOUNT: debit,
        ModeloFormElection.REFUND_ACCOUNT: result_disposition_declares(modelo, ResultDisposition.DEVOLUCION),
    }
    return tuple(election for election, is_asked in asked.items() if is_asked)


def revision_file_format(snapshot: RegistrySnapshot) -> ExportLayoutFormat | None:
    """The file format the revision's export layout declares, chosen as the export chooses its layout.

    Args:
        snapshot: The :class:`RegistrySnapshot` of the revision.
    """
    layouts = sorted(snapshot.revision.export_layouts, key=lambda item: item.id)
    return ExportLayoutFormat(layouts[0].format) if layouts else None


def _question[ElectionT: StrEnum](
    election: ModeloFormElection,
    keys: Mapping[ElectionT, str],
    default: ElectionT,
    locale: str,
    *,
    held: ModeloFormElectionReason | None = None,
    help_key: str | None = None,
    figures: tuple[ModeloFormElectionFigure, ...] = (),
) -> ModeloFormElectionQuestion:
    words = tr(f"tui.modelo.export.{election.value}_election.label", locale=locale)
    help_words = None if help_key is None else tr(help_key, locale=locale)
    if held is not None:
        return _held_question(election, words, held, locale, help_words=help_words)
    return ModeloFormElectionQuestion(
        election=election,
        request_field=_REQUEST_FIELDS[election],
        words=words,
        help=help_words,
        default=default.value,
        choices=tuple(
            ModeloFormElectionChoice(value=member.value, words=tr(key, locale=locale)) for member, key in keys.items()
        ),
        figures=figures,
    )


def _held_question(
    election: ModeloFormElection,
    words: str,
    reason: ModeloFormElectionReason,
    locale: str,
    *,
    help_words: str | None = None,
) -> ModeloFormElectionQuestion:
    not_applicable = reason in _NOT_APPLICABLE_REASONS
    return ModeloFormElectionQuestion(
        election=election,
        request_field=_REQUEST_FIELDS[election],
        words=words,
        state=ModeloFormElectionState.NOT_APPLICABLE if not_applicable else ModeloFormElectionState.UNAVAILABLE,
        reason=reason,
        state_words=tr(_ELECTION_REASON_LOCALE_KEYS[reason], locale=locale),
        help=help_words,
    )


def _account_question(
    election: ModeloFormElection,
    accounts: tuple[OwnBankAccount, ...],
    designated: OwnBankAccount | None,
    locale: str,
    *,
    held: ModeloFormElectionReason | None,
    none_open: ModeloFormElectionReason,
) -> ModeloFormElectionQuestion:
    """Offer the open own accounts by opaque identity, named by label and masked number only."""
    label_key = (
        _CHARGE_ACCOUNT_LOCALE_KEY if election is ModeloFormElection.CHARGE_ACCOUNT else _REFUND_ACCOUNT_LOCALE_KEY
    )
    words = tr(label_key, locale=locale)
    reason = held if held is not None else (none_open if not accounts else None)
    if reason is not None:
        return _held_question(election, words, reason, locale)
    choices = tuple(
        ModeloFormElectionChoice(
            value=account.own_account_id,
            words=tr(_ACCOUNT_CHOICE_LOCALE_KEY, label=account.label, account=account.masked_iban, locale=locale),
        )
        for account in accounts
    )
    offered = {account.own_account_id for account in accounts}
    default = designated.own_account_id if designated is not None and designated.own_account_id in offered else None
    return ModeloFormElectionQuestion(
        election=election, request_field=_REQUEST_FIELDS[election], words=words, default=default, choices=choices
    )


def _result_direction(form: ModeloWorkForm) -> ModeloFormResultDirection:
    result = form.result
    if form.calculation_revision_id is None or result is None:
        return ModeloFormResultDirection.UNKNOWN
    return result.direction


_ABSENT_VALUE_ORIGINS: Final = frozenset(
    {
        ModeloFormOrigin.NOT_APPLICABLE,
        ModeloFormOrigin.NOT_CALCULATED_YET,
        ModeloFormOrigin.CALCULATION_FAILED,
        ModeloFormOrigin.CLEARED,
        ModeloFormOrigin.NOT_IMPORTED_YET,
    }
)
_SETTLEMENT_REASONS: Final[Mapping[SettlementRefusal, ModeloFormElectionReason]] = MappingProxyType(
    {
        SettlementRefusal.RESULT_UNKNOWN: ModeloFormElectionReason.RESULT_UNKNOWN,
        SettlementRefusal.SETTLEMENT_UNSUPPORTED: ModeloFormElectionReason.SETTLEMENT_UNSUPPORTED,
    }
)


@dataclass(frozen=True, slots=True)
class _Settlement:
    """The amount the declaration settles as its form shows it, or why the settlement cannot be answered."""

    amount: Decimal | None
    held: ModeloFormElectionReason | None


def _form_values(form: ModeloWorkForm) -> dict[CasillaId, object]:
    """Every box the form shows a value for; a box that could not be worked out holds none."""
    return {
        field.address.casilla_id: field.value
        for field in form.fields()
        if isinstance(field.address, ModeloFormCasillaAddressV1)
        and field.value is not None
        and field.origin not in _ABSENT_VALUE_ORIGINS
    }


def _settlement(modelo: str, snapshot: RegistrySnapshot, form: ModeloWorkForm) -> _Settlement:
    """The settled amount, read as the export reads it, where the revision names a box it settles."""
    result = form.result
    if (
        form.calculation_revision_id is None
        or result is None
        or declaration_settlement_casilla_id(modelo, snapshot.revision) is None
    ):
        return _Settlement(None, None)
    settled = declared_settlement(modelo, snapshot.revision, _form_values(form), disposition=result.disposition)
    if settled.refusal is not None:
        return _Settlement(None, _SETTLEMENT_REASONS[settled.refusal])
    return _Settlement(settled.amount, None)


def _payable(form: ModeloWorkForm, settlement: _Settlement) -> ModeloFormElectionReason | None:
    """Why the result is not one to pay, or its settlement cannot be answered, or ``None`` when it can."""
    direction = _result_direction(form)
    if direction is ModeloFormResultDirection.UNKNOWN:
        return ModeloFormElectionReason.RESULT_UNKNOWN
    if direction is ModeloFormResultDirection.TO_PAY:
        return settlement.held
    return ModeloFormElectionReason.NOTHING_TO_PAY


def _refundable(form: ModeloWorkForm, settlement: _Settlement) -> ModeloFormElectionReason | None:
    """Why AEAT would not pay the result out, or ``None`` when it would or the refund election can make it."""
    direction = _result_direction(form)
    if direction is ModeloFormResultDirection.UNKNOWN:
        return ModeloFormElectionReason.RESULT_UNKNOWN
    result = form.result
    if direction is ModeloFormResultDirection.TO_REFUND:
        return settlement.held
    if result is not None and result.election_may_change:
        return None
    withheld = _refund_election_withheld(result)
    if withheld is not None:
        return withheld
    return ModeloFormElectionReason.NOTHING_TO_REFUND


def _refund_election_withheld(result: ModeloFormResult | None) -> ModeloFormElectionReason | None:
    """Why a carried IVA credit is not offered as a refund, or ``None`` when no such rule withheld it.

    The refusal is the shared resolver's, never a period test here: outside the
    year's last period the refund is lawful only for a filer inscribed in the
    Registro de devolución mensual (LIVA art. 115), and an unstated inscription
    names the missing fact rather than standing as a no.
    """
    eligibility = None if result is None else result.refund_eligibility
    if eligibility is None:
        return None
    return _REFUND_ELIGIBILITY_REASONS.get(eligibility.outcome)


def _instalment_figures(
    modelo: str, form: ModeloWorkForm, settlement: _Settlement, language: OutputLanguage
) -> tuple[ModeloFormElectionFigure, ...]:
    """Both instalments of the amount to pay, each advisory because no official rule rounds the cent."""
    share = _instalment_share(modelo, form.period)
    amount = settlement.amount
    if share is None or amount is None or amount <= 0:
        return ()
    first, second = instalment_amounts(amount, first_share=share)
    locale = language.value
    advisory_words = tr(_INSTALMENT_ADVISORY_LOCALE_KEY, locale=locale)
    first_percent = (share * 100).normalize()
    second_percent = ((1 - share) * 100).normalize()
    return tuple(
        ModeloFormElectionFigure(
            instalment=instalment,
            amount=f"{figure:f}",
            words=tr(
                key,
                share=f"{percent:f}",
                amount=format_casilla_value(figure, data_type=CasillaDataType.MONEY, language=language),
                locale=locale,
            ),
            advisory=True,
            advisory_words=advisory_words,
        )
        for instalment, key, percent, figure in (
            (ModeloFormInstalment.FIRST, _FIRST_INSTALMENT_LOCALE_KEY, first_percent, first),
            (ModeloFormInstalment.SECOND, _SECOND_INSTALMENT_LOCALE_KEY, second_percent, second),
        )
    )


def _splittable(
    modelo: str, form: ModeloWorkForm, settlement: _Settlement, *, amended: bool
) -> ModeloFormElectionReason | None:
    """Why the result may not be paid in two instalments, or ``None`` when it may.

    RD 439/2007 art. 62.2, with the conditions the Manual práctico de Renta
    states: a result to pay, not a corrective declaration, filed within its
    period. No source states a smallest amount to split, but an amount whose
    second instalment would be nothing is paid at once.
    """
    payable = _payable(form, settlement)
    if payable is not None:
        return payable
    if amended:
        return ModeloFormElectionReason.AMENDMENT
    deadline = form.deadline
    if deadline is None:
        return ModeloFormElectionReason.FILING_WINDOW_UNKNOWN
    if deadline.days_overdue is not None:
        return ModeloFormElectionReason.PAST_FILING_WINDOW
    share = _instalment_share(modelo, form.period)
    if (
        share is not None
        and settlement.amount is not None
        and not second_instalment_is_payable(settlement.amount, first_share=share)
    ):
        return ModeloFormElectionReason.SECOND_INSTALMENT_NOTHING
    return None


def _payment_keys(modelo: str) -> Mapping[PaymentElection, str]:
    """The payment methods ``modelo``'s design declares: the tax current account only where it declares it."""
    if result_disposition_declares(modelo, ResultDisposition.CUENTA_CORRIENTE_INGRESO):
        return PAYMENT_ELECTION_LOCALE_KEYS
    return MappingProxyType(
        {
            member: key
            for member, key in PAYMENT_ELECTION_LOCALE_KEYS.items()
            if member is not PaymentElection.CUENTA_CORRIENTE
        }
    )


def _settlement_question(
    election: ModeloFormElection,
    modelo: str,
    form: ModeloWorkForm,
    language: OutputLanguage,
    settlement: _Settlement,
    *,
    amended: bool,
) -> ModeloFormElectionQuestion:
    locale = language.value
    if election is ModeloFormElection.REFUND:
        # The carry-forward is always lawful; the refund is the gated answer, so
        # the choice is offered only where the shared resolver admits it.
        return _question(
            election,
            REFUND_ELECTION_LOCALE_KEYS,
            RefundElection.COMPENSAR,
            locale,
            held=_refund_election_withheld(form.result),
        )
    if election is ModeloFormElection.PAYMENT:
        return _question(
            election, _payment_keys(modelo), PaymentElection.INGRESO, locale, held=_payable(form, settlement)
        )
    if election is ModeloFormElection.PRIOR_DOMICILIATION:
        return _question(election, PRIOR_DOMICILIATION_ELECTION_LOCALE_KEYS, PriorDomiciliationElection.KEEP, locale)
    held = _splittable(modelo, form, settlement, amended=amended)
    return _question(
        election,
        INSTALMENT_ELECTION_LOCALE_KEYS,
        PaymentInstalmentElection.SINGLE,
        locale,
        held=held,
        help_key=_INSTALMENT_CONDITIONS_LOCALE_KEY,
        figures=() if held is not None else _instalment_figures(modelo, form, settlement, language),
    )


def _own_account_question(
    election: ModeloFormElection,
    modelo: str,
    form: ModeloWorkForm,
    locale: str,
    register: OwnAccountRegister,
    settlement: _Settlement,
) -> ModeloFormElectionQuestion:
    today = today_madrid()
    open_accounts = tuple(account for account in register.accounts if account.open_on(today))
    if election is ModeloFormElection.CHARGE_ACCOUNT:
        # AEAT admits a direct debit here only from a Spanish account.
        spanish = tuple(account for account in open_accounts if account.country_code == _DEBIT_ACCOUNT_COUNTRY)
        return _account_question(
            election,
            spanish,
            register.designated(OwnAccountRole.CHARGE, Modelo(modelo)),
            locale,
            held=_payable(form, settlement),
            none_open=ModeloFormElectionReason.NO_SPANISH_ACCOUNT,
        )
    return _account_question(
        election,
        open_accounts,
        register.designated(OwnAccountRole.REFUND, Modelo(modelo)),
        locale,
        held=_refundable(form, settlement),
        none_open=ModeloFormElectionReason.NO_OPEN_ACCOUNT,
    )


_ACCOUNT_ELECTIONS: Final = frozenset({ModeloFormElection.CHARGE_ACCOUNT, ModeloFormElection.REFUND_ACCOUNT})


def _election_questions(
    modelo: str,
    snapshot: RegistrySnapshot,
    form: ModeloWorkForm,
    language: OutputLanguage,
    *,
    own_accounts: OwnAccountRegister | None,
    amended: bool,
) -> tuple[ModeloFormElectionQuestion, ...]:
    """Every election exporting ``modelo`` asks, in a stable order, with its state for this declaration.

    The account elections are asked only when the register was read.
    """
    asked = _asked_elections(modelo, form.period)
    if not asked:
        return ()
    settlement = _settlement(modelo, snapshot, form)
    questions: list[ModeloFormElectionQuestion] = []
    for election in asked:
        if election not in _ACCOUNT_ELECTIONS:
            questions.append(_settlement_question(election, modelo, form, language, settlement, amended=amended))
        elif own_accounts is not None:
            questions.append(_own_account_question(election, modelo, form, language.value, own_accounts, settlement))
    return tuple(questions)


_AVAILABLE: Final = ModeloFormAvailability(available=True)
_HOLD_REASONS: Final[Mapping[ModeloFormExportHoldReason, ModeloFormUnavailable]] = MappingProxyType(
    {
        ModeloFormExportHoldReason.BLOCKS: ModeloFormUnavailable.BLOCKS,
        ModeloFormExportHoldReason.CONFIRM: ModeloFormUnavailable.CONFIRM,
        ModeloFormExportHoldReason.VERIFY: ModeloFormUnavailable.NOT_VERIFIED,
    }
)
_NOT_CALCULATED_LOCALE_KEY: Final = "workspace.modelo.next.calculate"
_NOT_VERIFIED_LOCALE_KEY: Final = "workspace.modelo.export.verify_first"
_RECORDED_LOCALE_KEY: Final = "workspace.modelo.filed.read_only"
_FILE_OUT_OF_DATE_LOCALE_KEY: Final = "workspace.modelo.record.refused_file_out_of_date"
_REVIEW_PACKAGE_LOCALE_KEY: Final = "workspace.modelo.filing.copy.package.title"


def _unavailable(reason: ModeloFormUnavailable, words: str) -> ModeloFormAvailability:
    return ModeloFormAvailability(available=False, reason=reason, words=words)


def _held(form: ModeloWorkForm, language: OutputLanguage, *, verified: bool) -> ModeloFormAvailability | None:
    """What withholds the file for the AEAT and recording the filing, as the header's hold says; ``None`` if nothing."""
    locale = language.value
    if form.calculation_revision_id is None:
        return _unavailable(ModeloFormUnavailable.NOT_CALCULATED, tr(_NOT_CALCULATED_LOCALE_KEY, locale=locale))
    hold = export_hold(form, language, verified=verified, recorded=False)
    if hold is None:
        return None
    return _unavailable(_HOLD_REASONS[hold.reason], hold.words)


def artefact_availability(
    artefact: ModeloExportArtefact, form: ModeloWorkForm, language: OutputLanguage, *, verified: bool
) -> ModeloFormAvailability:
    """Whether ``artefact`` can be created from the declaration now, by the rules its export applies.

    The spreadsheet for review is made from any calculation; a calculation
    report only from a checked one; the file for the AEAT only once nothing
    withholds filing.
    """
    locale = language.value
    if form.calculation_revision_id is None:
        return _unavailable(ModeloFormUnavailable.NOT_CALCULATED, tr(_NOT_CALCULATED_LOCALE_KEY, locale=locale))
    if artefact is ModeloExportArtefact.CALCULATION_REVIEW_XLSX:
        return _AVAILABLE
    if artefact is ModeloExportArtefact.FICHERO_BOE:
        return _held(form, language, verified=verified) or _AVAILABLE
    if not verified:
        return _unavailable(ModeloFormUnavailable.NOT_VERIFIED, tr(_NOT_VERIFIED_LOCALE_KEY, locale=locale))
    return _AVAILABLE


def review_package_availability(
    form: ModeloWorkForm, language: OutputLanguage, *, verified: bool
) -> ModeloFormAvailability:
    """Whether the package for the filer's accountant can be built now.

    The package carries the file for the AEAT, built by the same export, so it
    is available exactly when that file is.
    """
    return artefact_availability(ModeloExportArtefact.FICHERO_BOE, form, language, verified=verified)


def record_availability(
    form: ModeloWorkForm, language: OutputLanguage, *, verified: bool, filed: bool
) -> ModeloFormAvailability:
    """Whether the filing can be recorded now: not again, not while anything withholds it, not from a stale file."""
    locale = language.value
    if form_recorded(form, filed=filed):
        return _unavailable(ModeloFormUnavailable.RECORDED, tr(_RECORDED_LOCALE_KEY, locale=locale))
    held = _held(form, language, verified=verified)
    if held is not None:
        return held
    export = form.last_export
    if export is not None and not export.current:
        words = tr(_FILE_OUT_OF_DATE_LOCALE_KEY, date=day_text(export.exported_at, language), locale=locale)
        return _unavailable(ModeloFormUnavailable.FILE_OUT_OF_DATE, words)
    return _AVAILABLE


def form_export_offer(
    modelo: str,
    snapshot: RegistrySnapshot,
    language: OutputLanguage,
    *,
    form: ModeloWorkForm,
    verified: bool,
    filed: bool,
    own_accounts: OwnAccountRegister | None = None,
    amended: bool = False,
) -> ModeloFormExportOffer:
    """What exporting the declaration offers, in ``language``, and what of it can be done now.

    Args:
        modelo: The modelo number.
        snapshot: The :class:`RegistrySnapshot` whose export layout names the file format.
        language: The filer's language.
        form: The declaration's form.
        verified: Whether the AEAT receipt of the filing is verified.
        filed: Whether the declaration is recorded as filed.
        own_accounts: The taxpayer's :class:`OwnAccountRegister`; ``None`` asks no account election.
        amended: Whether the current calculation corrects an earlier filing.
    """
    locale = language.value
    asks = asks_export_elections(modelo, form.period)
    file_format = revision_file_format(snapshot)
    return ModeloFormExportOffer(
        artefacts=tuple(
            ModeloFormArtefactOption(
                artefact=artefact,
                words=tr(EXPORT_ARTEFACT_LOCALE_KEYS[artefact], locale=locale),
                availability=artefact_availability(artefact, form, language, verified=verified),
            )
            for artefact in EXPORT_ARTEFACT_LOCALE_KEYS
        ),
        record=record_availability(form, language, verified=verified, filed=filed),
        review_package=ModeloFormReviewPackageOffer(
            words=tr(_REVIEW_PACKAGE_LOCALE_KEY, locale=locale),
            availability=review_package_availability(form, language, verified=verified),
        ),
        asks_elections=asks,
        elections=_election_questions(modelo, snapshot, form, language, own_accounts=own_accounts, amended=amended),
        file_format=file_format,
        file_format_words=None if file_format is None else tr(_FILE_FORMAT_LOCALE_KEYS[file_format], locale=locale),
    )


def form_receipt(
    record: ModeloRecord | None, *, recorded_at: datetime | None, language: OutputLanguage
) -> ModeloFormReceipt:
    """The receipt state of a declaration recorded as filed, from its current filing record.

    The receipt is verified when that record is in force and the AEAT is seen
    to hold it, backed by the receipt imported for it.

    Args:
        record: The current :class:`ModeloRecord` of the filing, if any.
        recorded_at: When the filing was recorded.
        language: The filer's language.
    """
    evidence = record.external_evidence if record is not None else None
    in_force = (
        record is not None
        and record.status is ModeloRecordStatus.VIGENTE
        and record.confirmation is AeatConfirmationState.CONFIRMADA
    )
    verified_evidence = evidence if in_force else None
    verified = verified_evidence is not None
    verified_at = None if verified_evidence is None else verified_evidence.imported_at
    locale = language.value
    return ModeloFormReceipt(
        recorded_at=recorded_at,
        verified=verified,
        verified_at=verified_at,
        words=(
            tr(_RECEIPT_VERIFIED_LOCALE_KEY, date=day_text(verified_at, language), locale=locale)
            if verified_at is not None
            else tr(_RECEIPT_MISSING_LOCALE_KEY, locale=locale)
        ),
    )


__all__ = [
    "EXPORT_ARTEFACT_LOCALE_KEYS",
    "INSTALMENT_ELECTION_LOCALE_KEYS",
    "PAYMENT_ELECTION_LOCALE_KEYS",
    "PRIOR_DOMICILIATION_ELECTION_LOCALE_KEYS",
    "REFUND_ELECTION_LOCALE_KEYS",
    "ModeloExportRequestField",
    "ModeloFormArtefactOption",
    "ModeloFormAvailability",
    "ModeloFormElection",
    "ModeloFormElectionChoice",
    "ModeloFormElectionFigure",
    "ModeloFormElectionQuestion",
    "ModeloFormElectionReason",
    "ModeloFormElectionState",
    "ModeloFormExportOffer",
    "ModeloFormInstalment",
    "ModeloFormReceipt",
    "ModeloFormReviewPackageOffer",
    "ModeloFormUnavailable",
    "artefact_availability",
    "asks_export_elections",
    "form_export_offer",
    "form_receipt",
    "record_availability",
    "review_package_availability",
    "revision_file_format",
]
