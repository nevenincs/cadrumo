"""Protocol stubs for sibling features that are still in flight.

These definitions deliberately mirror the planned external surfaces used by the
casillas package without importing from sibling-owned modules. Replace them
with the real imports when issues #9, #21, and #25 land on `main`.
"""

from __future__ import annotations

from datetime import date
from typing import Protocol, runtime_checkable

from ..i18n import Translatable


@runtime_checkable
class FormulaNode(Protocol):
    """Structural contract for a parsed formula node from issue #9."""

    expression: str
    references_casillas: tuple[str, ...]


@runtime_checkable
class ValidationRule(Protocol):
    """Structural contract for a validation rule from issue #9."""

    rule: str
    value: str | int | float | bool | None
    description: str | None


@runtime_checkable
class Casilla(Protocol):
    """Structural contract for a schema-level casilla from issue #9."""

    casilla_id: str
    label: Translatable


@runtime_checkable
class Rule(Protocol):
    """Structural contract for manual/rulebook entries from issue #25."""

    rule_id: str
    statement: Translatable


@runtime_checkable
class LLMExtractionClient(Protocol):
    """Draft-generation surface expected from issue #21."""

    def extract_casillas(self, *, modelo: str, period: str, source_text: str) -> str:
        """Return a JSON draft payload for the requested modelo and period."""


@runtime_checkable
class BulkTranslator(Protocol):
    """Bulk translation surface expected from issue #21."""

    def translate_translatable(
        self,
        *,
        text: Translatable,
        reviewed_at: date | None = None,
    ) -> Translatable:
        """Return translated text while preserving the authoritative Spanish field."""
