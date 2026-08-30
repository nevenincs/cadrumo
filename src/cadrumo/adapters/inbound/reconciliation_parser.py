"""Inbound PDF parser composition for modelo reconciliation."""

from __future__ import annotations

from pathlib import Path
from typing import override

from ...application.modelo.reconciliation_parsing import (
    ReconciliationDeclaracionObservation,
    ReconciliationEvidenceParserPort,
)
from ...domain.filing.reconciliation.errors import ReconciliationDeclaracionParseError
from ...domain.justificante import Justificante
from .declaracion import DeclaracionParseError, parse_declaracion
from .justificante.parser import parse_justificante, parse_justificante_bytes


class InboundReconciliationEvidenceParser(ReconciliationEvidenceParserPort):
    """Compose the shipped declaración and justificante PDF parsers."""

    @override
    def parse_justificante(self, source: Path) -> Justificante:
        return parse_justificante(source)

    @override
    def parse_justificante_bytes(self, source: bytes) -> Justificante:
        return parse_justificante_bytes(source)

    @override
    def parse_declaracion(
        self,
        source: Path,
        *,
        modelo: str,
        filing_year: int,
        period: str,
    ) -> ReconciliationDeclaracionObservation:
        try:
            return parse_declaracion(
                source,
                modelo_override=modelo,
                año_override=filing_year,
                period_override=period,
            )
        except DeclaracionParseError as error:
            raise ReconciliationDeclaracionParseError(
                "filed declaración evidence could not be parsed",
            ) from error


__all__ = ["InboundReconciliationEvidenceParser"]
