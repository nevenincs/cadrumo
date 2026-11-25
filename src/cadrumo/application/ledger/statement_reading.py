"""Inward port for reading bank-statement movements out of a document's text.

A statement in an arbitrary layout and language is read in two stages. The
acquisition stage turns each page into a
:class:`~application.ledger.document_transcription.DocumentTranscription`: the
deterministic text layer where the page carries one, a vision-model
transcription where it does not. The semantic stage then proposes the
movements printed on that page. Both stages that need a model are an outbound
capability, so inbound providers depend on this structural port and an
outer composition root binds the implementation.

Everything a reader returns is a proposal of PRINTED forms: the date, amount
and balance strings exactly as the page shows them. Nothing here parses a
number or a date. The inbound provider anchors each proposal to a printed line
and reconciles the printed balances before a single movement reaches the
ledger, so a value the page does not print is dropped rather than imported.
"""

from __future__ import annotations

from collections.abc import Callable, Generator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable

from .document_transcription import DocumentTranscription


class ProposedDirection(StrEnum):
    """Which way a proposed movement moves money, as the reader understood it."""

    IN = "in"
    OUT = "out"


@dataclass(frozen=True, slots=True)
class ProposedStatementMovement:
    """One movement a reader proposes, every value in its printed form.

    Attributes:
        booked_date: The booking or transaction date as printed.
        value_date: The separate value date as printed, when the page prints one.
        description: The movement's printed text.
        counterparty: The other party's name, when printed apart from the text.
        amount: The movement amount as printed, sign and currency marks included.
        direction: The reader's reading of the flow. A printed sign on
            ``amount`` outranks it.
        balance: The running balance printed on the movement's line, if any.
    """

    booked_date: str | None
    value_date: str | None
    description: str | None
    counterparty: str | None
    amount: str | None
    direction: ProposedDirection | None
    balance: str | None


@dataclass(frozen=True, slots=True)
class ProposedStatementPage:
    """Everything a reader proposes for one page.

    Attributes:
        movements: The proposed movements in the page's reading order.
        opening_balance: The balance printed before the page's first movement.
        closing_balance: The balance printed after the page's last movement.
        currency: The currency code or symbol the amounts are printed in.
        reply_usable: ``False`` when the reader's reply carried no usable
            object, so the page contributed nothing rather than nothing being
            printed on it.
    """

    movements: tuple[ProposedStatementMovement, ...]
    opening_balance: str | None
    closing_balance: str | None
    currency: str | None
    reply_usable: bool = True


@runtime_checkable
class StatementReaderPort(Protocol):
    """Reads statement pages that need a model."""

    @property
    def decided_by(self) -> str:
        """Return the provenance stamp naming the transport and model of the read."""
        ...

    def transcribe_scanned_pages(
        self,
        pdf_bytes: bytes,
        *,
        page_numbers: tuple[int, ...],
        source_content_sha256: str,
    ) -> Mapping[int, DocumentTranscription]:
        """Transcribe the named one-based pages that carry no text layer.

        A page the reader could not transcribe is absent from the result.
        """
        ...

    def propose_page(self, transcription: DocumentTranscription) -> ProposedStatementPage:
        """Propose the movements printed on one transcribed page."""
        ...


StatementReaderFactory = Callable[[], StatementReaderPort]
"""Builds the reader when a statement actually needs one.

A factory rather than an instance, so a reader is built only when a PDF is
actually read.
"""


_BOUND_STATEMENT_READER_FACTORY: ContextVar[StatementReaderFactory] = ContextVar(
    "cadrumo_statement_reader_factory",
)


@contextmanager
def bind_statement_reader_factory(factory: StatementReaderFactory) -> Generator[StatementReaderFactory]:
    """Bind the outward statement reader for one runtime scope."""
    token = _BOUND_STATEMENT_READER_FACTORY.set(factory)
    try:
        yield factory
    finally:
        _BOUND_STATEMENT_READER_FACTORY.reset(token)


def statement_reader_factory() -> StatementReaderFactory | None:
    """Return the factory installed by an outer composition root, if any."""
    return _BOUND_STATEMENT_READER_FACTORY.get(None)


__all__ = [
    "ProposedDirection",
    "ProposedStatementMovement",
    "ProposedStatementPage",
    "StatementReaderFactory",
    "StatementReaderPort",
    "bind_statement_reader_factory",
    "statement_reader_factory",
]
