"""A deterministic stand-in for the statement reader port, for provider tests.

The statement provider's own logic -- text extraction, anchoring, direction,
parsing and balance reconciliation -- is what its tests exercise. The model
behind the reader port is an external dependency with its own measured
accuracy, so provider tests read pages with this stand-in instead: it proposes
whatever a line pattern finds on the synthetic statement fixtures, and it can
add the mistakes the local text model was measured making (balances and totals
listed as movements, movements the page does not print) so the grounding stage
is tested against them.

Nothing here is used by production code.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field

from ......application.ledger.document_transcription import DocumentTranscription
from ......application.ledger.statement_reading import (
    ProposedDirection,
    ProposedStatementMovement,
    ProposedStatementPage,
)

__all__ = ["LinePatternStatementReader", "invented_movement"]

#: A movement line of the synthetic statements: text, booking date, signed amount.
_MOVEMENT_LINE = re.compile(r"^(?P<text>.+?) (?P<date>\d{2}\.\d{2}\.\d{4}) (?P<amount>[+-]?[\d.,]+ ?EUR)$")

#: A continuation line carrying a value date: words, then one date.
_VALUE_DATE_LINE = re.compile(r"^[^\d]+ (?P<date>\d{2}\.\d{2}\.\d{4})$")

#: A line printing a label and an amount but no date, such as a balance or total.
_AMOUNT_ONLY_LINE = re.compile(r"^(?P<label>[^\d+-]+?) (?P<amount>[+-]?[\d.,]+ ?EUR)$")

#: Any printed date, for the summary-echo mistake.
_ANY_DATE = re.compile(r"\d{2}\.\d{2}\.\d{4}")


def invented_movement(*, booked_date: str, amount: str) -> ProposedStatementMovement:
    """Return a proposal for a movement no page prints."""
    return ProposedStatementMovement(
        booked_date=booked_date,
        value_date=None,
        description="Zahlung",
        counterparty=None,
        amount=amount,
        direction=ProposedDirection.OUT,
        balance=None,
    )


@dataclass
class LinePatternStatementReader:
    """Propose the movements a line pattern finds, optionally with model-like mistakes.

    Attributes:
        opening_label: Printed label whose amount is proposed as the opening balance.
        closing_label: Printed label whose amount is proposed as the closing balance.
        echo_summary_lines: Also propose every dated-less amount line as a movement
            carrying the page's first printed date, as the local model did on
            summary pages.
        invented: Proposals appended to every page, for movements nobody printed.
        drop_signs: Propose amounts without their sign, so direction must come
            from the proposed direction.
        reverse_directions: Propose the opposite direction for every movement.
        decided_by: Provenance stamp this stand-in reports.
        pages_read: Count of pages proposed, to observe how often the provider reads.
        scanned: Transcriptions to return for scanned pages, by page number.
    """

    opening_label: str | None = None
    closing_label: str | None = None
    echo_summary_lines: bool = False
    invented: tuple[ProposedStatementMovement, ...] = ()
    drop_signs: bool = False
    reverse_directions: bool = False
    decided_by: str = "test:line-pattern-reader"
    pages_read: int = 0
    scanned: Mapping[int, DocumentTranscription] = field(default_factory=dict)

    def transcribe_scanned_pages(
        self,
        pdf_bytes: bytes,
        *,
        page_numbers: tuple[int, ...],
        source_content_sha256: str,
    ) -> Mapping[int, DocumentTranscription]:
        """Return the configured transcriptions for the named pages."""
        del pdf_bytes, source_content_sha256
        return {number: self.scanned[number] for number in page_numbers if number in self.scanned}

    def propose_page(self, transcription: DocumentTranscription) -> ProposedStatementPage:
        """Propose the page's movements and balances from its printed lines."""
        self.pages_read += 1
        lines = [line.strip() for line in transcription.text.splitlines() if line.strip()]
        movements: list[ProposedStatementMovement] = []
        opening: str | None = None
        closing: str | None = None
        first_date = next((match.group(0) for line in lines if (match := _ANY_DATE.search(line))), None)
        for index, line in enumerate(lines):
            movement = _MOVEMENT_LINE.match(line)
            if movement is not None:
                movements.append(self._movement(movement, lines[index + 1 :]))
                continue
            amount_only = _AMOUNT_ONLY_LINE.match(line)
            if amount_only is None:
                continue
            label, amount = str(amount_only.group("label")), str(amount_only.group("amount"))
            if self.opening_label is not None and self.opening_label in label:
                opening = amount
            elif self.closing_label is not None and self.closing_label in label:
                closing = amount
            if self.echo_summary_lines and first_date is not None:
                movements.append(
                    ProposedStatementMovement(
                        booked_date=first_date,
                        value_date=None,
                        description=label,
                        counterparty=None,
                        amount=amount,
                        direction=ProposedDirection.OUT if amount.startswith("-") else ProposedDirection.IN,
                        balance=None,
                    ),
                )
        return ProposedStatementPage(
            movements=(*movements, *self.invented),
            opening_balance=opening,
            closing_balance=closing,
            currency="EUR" if "EUR" in transcription.text else None,
        )

    def _movement(self, match: re.Match[str], following: list[str]) -> ProposedStatementMovement:
        """Build one proposal from a movement line and the lines after it."""
        amount = match.group("amount")
        direction = ProposedDirection.OUT if amount.startswith("-") else ProposedDirection.IN
        if self.reverse_directions:
            direction = ProposedDirection.IN if direction is ProposedDirection.OUT else ProposedDirection.OUT
        value_date = None
        for line in following:
            if _MOVEMENT_LINE.match(line):
                break
            value_line = _VALUE_DATE_LINE.match(line)
            if value_line is not None:
                value_date = value_line.group("date")
                break
        return ProposedStatementMovement(
            booked_date=match.group("date"),
            value_date=value_date,
            description=match.group("text"),
            counterparty=None,
            amount=amount.lstrip("+-") if self.drop_signs else amount,
            direction=direction,
            balance=None,
        )
