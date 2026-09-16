"""Inbound PDF parser composition for modelo reconciliation."""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from ...application.modelo.reconciliation_parsing import (
    ReconciliationDeclaracionObservation,
    ReconciliationEvidenceParserPort,
)
from ...domain.filing.reconciliation.errors import ReconciliationDeclaracionParseError
from .declaracion.errors import DeclaracionParseError

if TYPE_CHECKING:
    from pathlib import Path

    from ...domain.calculations.registry.schema import RegistrySnapshot
    from ...domain.justificante.schema import Justificante


class InboundReconciliationEvidenceParser(ReconciliationEvidenceParserPort):
    """Compose the shipped declaración and justificante PDF parsers.

    The PDF parser trees load on first parse, not when the host binds this port.
    """

    @override
    def parse_justificante(self, source: Path) -> Justificante:
        from .justificante.parser import parse_justificante

        return parse_justificante(source)

    @override
    def parse_justificante_bytes(self, source: bytes) -> Justificante:
        from .justificante.parser import parse_justificante_bytes

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
        from .declaracion.parser import parse_declaracion

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

    @override
    def parse_declaracion_bytes(
        self,
        source: bytes,
        *,
        modelo: str,
        filing_year: int,
        period: str,
        registry_snapshot: RegistrySnapshot,
    ) -> ReconciliationDeclaracionObservation:
        from .declaracion.parser import parse_declaracion_bytes

        try:
            return parse_declaracion_bytes(
                source,
                source_label="secure declaration PDF",
                modelo_override=modelo,
                año_override=filing_year,
                period_override=period,
                registry_snapshot=registry_snapshot,
            )
        except DeclaracionParseError as error:
            raise ReconciliationDeclaracionParseError(
                "filed declaración evidence could not be parsed",
            ) from error


__all__ = ["InboundReconciliationEvidenceParser"]
