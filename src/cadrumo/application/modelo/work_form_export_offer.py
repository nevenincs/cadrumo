"""What a declaration offers to export, the file format its revision writes, and its filing's receipt.

The artefacts offered are the ones this installation can publish, probed in
the worker that runs the export, so the filer never picks an export the
installation would refuse. The payment and refund elections are asked for a
modelo whose official design declares both carrying a credit forward and
asking for its refund, which is where the refund election exists; every other
modelo exports with the neutral defaults. The file format is the one the
revision's registry export layout declares. A declaration recorded as filed
says whether the AEAT receipt of that filing has been verified, and when;
nothing here sends anything to the AEAT.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, Field, model_validator

from ...core.export_layout_format import ExportLayoutFormat
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import tr
from ...core.modelo_export_artefact import ModeloExportArtefact
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.optional_extras import PDF_EXTRA, OptionalExtra, optional_extra_available
from ...core.payment_election import PaymentElection
from ...core.prior_domiciliation_election import PriorDomiciliationElection
from ...core.refund_election import RefundElection
from ...core.result_disposition import ResultDisposition, result_disposition_declares
from ...domain.modelos.filing_record import AeatConfirmationState, ModeloRecordStatus
from .work_form_wording import day_text

if TYPE_CHECKING:
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
#: An artefact that needs an optional extra is offered only when the extra is
#: installed, and no other artefact is ever published in its place.
_EXPORT_ARTEFACT_EXTRAS: Final[Mapping[ModeloExportArtefact, OptionalExtra]] = MappingProxyType(
    {ModeloExportArtefact.CALCULATION_REPORT_PDF: PDF_EXTRA},
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


class ModeloFormArtefactOption(BaseModel):
    """One artefact the export offers, in the filer's words."""

    model_config = STRICT_FROZEN_CONFIG

    artefact: ModeloExportArtefact
    words: str = Field(min_length=1)


class ModeloFormElectionChoice(BaseModel):
    """One answer an election takes: the value the export request carries, and its words."""

    model_config = STRICT_FROZEN_CONFIG

    value: str = Field(min_length=1)
    words: str = Field(min_length=1)


class ModeloFormElectionQuestion(BaseModel):
    """One election the export asks, pre-set to its neutral default and never blank."""

    model_config = STRICT_FROZEN_CONFIG

    election: ModeloFormElection
    words: str = Field(min_length=1)
    default: str = Field(min_length=1)
    choices: tuple[ModeloFormElectionChoice, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _default_is_a_choice(self) -> ModeloFormElectionQuestion:
        if self.default not in {choice.value for choice in self.choices}:
            raise ValueError("an election's default must be one of its choices")
        return self


class ModeloFormExportOffer(BaseModel):
    """What the declaration may export, whether the export asks elections, and the file its revision writes.

    ``elections`` is empty exactly when ``asks_elections`` is false; the export
    then carries each election's neutral default. ``file_format`` is ``None``
    when the revision declares no export layout.
    """

    model_config = STRICT_FROZEN_CONFIG

    artefacts: tuple[ModeloFormArtefactOption, ...] = Field(min_length=1)
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


def offered_export_artefacts() -> tuple[ModeloExportArtefact, ...]:
    """The artefacts this installation can publish, in the order an export offers them.

    Probed each time, through the same spec-only probe the export service's own
    refusal rests on.
    """
    return tuple(
        artefact
        for artefact in EXPORT_ARTEFACT_LOCALE_KEYS
        if (extra := _EXPORT_ARTEFACT_EXTRAS.get(artefact)) is None or optional_extra_available(extra)
    )


def asks_export_elections(modelo: str) -> bool:
    """Whether exporting ``modelo`` asks the payment and refund elections.

    The refund election chooses between carrying a credit forward and asking
    for its refund, so it exists where the official design declares both.
    """
    return result_disposition_declares(modelo, ResultDisposition.COMPENSACION) and result_disposition_declares(
        modelo, ResultDisposition.DEVOLUCION
    )


def revision_file_format(snapshot: RegistrySnapshot) -> ExportLayoutFormat | None:
    """The file format the revision's export layout declares, chosen as the export chooses its layout."""
    layouts = sorted(snapshot.revision.export_layouts, key=lambda item: item.id)
    return ExportLayoutFormat(layouts[0].format) if layouts else None


def _question[ElectionT: StrEnum](
    election: ModeloFormElection, keys: Mapping[ElectionT, str], default: ElectionT, locale: str
) -> ModeloFormElectionQuestion:
    return ModeloFormElectionQuestion(
        election=election,
        words=tr(f"tui.modelo.export.{election.value}_election.label", locale=locale),
        default=default.value,
        choices=tuple(
            ModeloFormElectionChoice(value=member.value, words=tr(key, locale=locale)) for member, key in keys.items()
        ),
    )


def form_export_offer(modelo: str, snapshot: RegistrySnapshot, language: OutputLanguage) -> ModeloFormExportOffer:
    """What exporting the declaration offers, in ``language``."""
    locale = language.value
    asks = asks_export_elections(modelo)
    file_format = revision_file_format(snapshot)
    return ModeloFormExportOffer(
        artefacts=tuple(
            ModeloFormArtefactOption(artefact=artefact, words=tr(EXPORT_ARTEFACT_LOCALE_KEYS[artefact], locale=locale))
            for artefact in offered_export_artefacts()
        ),
        asks_elections=asks,
        elections=(
            (
                _question(ModeloFormElection.REFUND, REFUND_ELECTION_LOCALE_KEYS, RefundElection.COMPENSAR, locale),
                _question(ModeloFormElection.PAYMENT, PAYMENT_ELECTION_LOCALE_KEYS, PaymentElection.INGRESO, locale),
                _question(
                    ModeloFormElection.PRIOR_DOMICILIATION,
                    PRIOR_DOMICILIATION_ELECTION_LOCALE_KEYS,
                    PriorDomiciliationElection.KEEP,
                    locale,
                ),
            )
            if asks
            else ()
        ),
        file_format=file_format,
        file_format_words=None if file_format is None else tr(_FILE_FORMAT_LOCALE_KEYS[file_format], locale=locale),
    )


def form_receipt(
    record: ModeloRecord | None, *, recorded_at: datetime | None, language: OutputLanguage
) -> ModeloFormReceipt:
    """The receipt state of a declaration recorded as filed, from its current filing record.

    The receipt is verified when that record is in force and the AEAT is seen
    to hold it, backed by the receipt imported for it.
    """
    evidence = record.external_evidence if record is not None else None
    verified = (
        record is not None
        and record.status is ModeloRecordStatus.VIGENTE
        and record.confirmation is AeatConfirmationState.CONFIRMADA
        and evidence is not None
    )
    verified_at = evidence.imported_at if verified and evidence is not None else None
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
    "PAYMENT_ELECTION_LOCALE_KEYS",
    "PRIOR_DOMICILIATION_ELECTION_LOCALE_KEYS",
    "REFUND_ELECTION_LOCALE_KEYS",
    "ModeloFormArtefactOption",
    "ModeloFormElection",
    "ModeloFormElectionChoice",
    "ModeloFormElectionQuestion",
    "ModeloFormExportOffer",
    "ModeloFormReceipt",
    "asks_export_elections",
    "form_export_offer",
    "form_receipt",
    "offered_export_artefacts",
    "revision_file_format",
]
