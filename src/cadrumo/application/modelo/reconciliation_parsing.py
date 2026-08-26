"""Neutral parser boundary for modelo reconciliation evidence.

Application reconciliation consumes parsed filing observations. Inbound adapters
own PDF extraction and bind one parser implementation at the executable host.
"""

from __future__ import annotations

from collections.abc import Generator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Protocol

from ...core import Period
from ...domain.justificante import Justificante


class ReconciliationCasillaObservation(Protocol):
    """The numeric-or-text casilla facts reconciliation reads from a PDF."""

    @property
    def casilla_id(self) -> str:
        """Return the canonical casilla identifier."""
        ...

    @property
    def printed_value(self) -> object:
        """Return the parsed printed value, if any."""
        ...


class ReconciliationDeclaracionObservation(Protocol):
    """Minimal filed-declaración observation consumed by reconciliation."""

    @property
    def modelo(self) -> str:
        """Return the observed modelo code."""
        ...

    @property
    def period(self) -> Period:
        """Return the observed filing period."""
        ...

    @property
    def ejercicio(self) -> str:
        """Return the printed filing year."""
        ...

    @property
    def tax_id(self) -> str:
        """Return the printed taxpayer identifier."""
        ...

    @property
    def values(self) -> Sequence[ReconciliationCasillaObservation]:
        """Return the parsed casilla observations."""
        ...

    @property
    def extraction_profile_id(self) -> str:
        """Return the registry extraction-profile identifier."""
        ...

    @property
    def extraction_profile_provisional(self) -> bool:
        """Return whether the selected extraction profile is provisional."""
        ...


class ReconciliationEvidenceParserPort(Protocol):
    """Inbound parsing capabilities required by reconciliation."""

    def parse_justificante(self, source: Path) -> Justificante:
        """Parse one local justificante PDF."""
        ...

    def parse_justificante_bytes(self, source: bytes) -> Justificante:
        """Parse one in-memory justificante PDF."""
        ...

    def parse_declaracion(
        self,
        source: Path,
        *,
        modelo: str,
        filing_year: int,
        period: str,
    ) -> ReconciliationDeclaracionObservation:
        """Parse one local declaración PDF against its addressed work unit."""
        ...


_BOUND_RECONCILIATION_EVIDENCE_PARSER: ContextVar[ReconciliationEvidenceParserPort] = ContextVar(
    "cadrumo_reconciliation_evidence_parser"
)


@contextmanager
def bind_reconciliation_evidence_parser(
    parser: ReconciliationEvidenceParserPort,
) -> Generator[ReconciliationEvidenceParserPort]:
    """Bind the inbound parser implementation for one host lifetime."""
    token = _BOUND_RECONCILIATION_EVIDENCE_PARSER.set(parser)
    try:
        yield parser
    finally:
        _BOUND_RECONCILIATION_EVIDENCE_PARSER.reset(token)


def reconciliation_evidence_parser() -> ReconciliationEvidenceParserPort:
    """Resolve the explicitly composed reconciliation parser."""
    try:
        return _BOUND_RECONCILIATION_EVIDENCE_PARSER.get()
    except LookupError as error:
        raise RuntimeError("reconciliation evidence parsing has not been composed") from error


__all__ = [
    "ReconciliationCasillaObservation",
    "ReconciliationDeclaracionObservation",
    "ReconciliationEvidenceParserPort",
    "bind_reconciliation_evidence_parser",
    "reconciliation_evidence_parser",
]
