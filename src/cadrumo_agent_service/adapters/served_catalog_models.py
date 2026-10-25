"""The running agent's live catalogue entries for one lane, read from the document its gateway serves.

The service reads the document; this adapter only finds the lane in it and
takes, from each of its ``catalog.models[]``, the model value and the facts a
selection is checked against: vision, size, context window and licence. Every
other field is left unread. The facts are validated with the declared
catalogue's own rules, so a value either catalogue would refuse is refused
here too, and a lane whose entries do not validate yields no live catalogue
rather than a partial one.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Final, override

from pydantic import ValidationError

from ..providers.application.ports import LiveCatalogModels
from ..providers.domain.catalog import CatalogModelFacts

_FACT_FIELDS: Final = ("vision", "size_bytes", "context_length", "licence")
"""The served entry fields read besides the model value, each required, null where unstated."""


class ServedCatalogModels(LiveCatalogModels):
    """Read one lane's live entries from the document ``read`` returns."""

    def __init__(self, read: Callable[[], Mapping[str, object] | None]) -> None:
        """Bind the reader of the running agent's served catalogue; it returns ``None`` when none is running."""
        self._read = read

    @override
    def lane_models(self, provider: str, transport: str) -> tuple[CatalogModelFacts, ...] | None:
        """Return the lane's live entries, empty when the document lists no such lane, ``None`` when unread."""
        document = self._read()
        if document is None:
            return None
        records = document.get("providers")
        if not isinstance(records, list):
            return None
        for record in records:
            if not isinstance(record, Mapping) or (record.get("provider_id"), record.get("transport")) != (
                provider,
                transport,
            ):
                continue
            catalog = record.get("catalog")
            models = catalog.get("models") if isinstance(catalog, Mapping) else None
            if not isinstance(models, list):
                return None
            return _entries(models)
        return ()


def _entries(models: list[object]) -> tuple[CatalogModelFacts, ...] | None:
    entries: list[CatalogModelFacts] = []
    for model in models:
        if not isinstance(model, Mapping) or "model" not in model:
            return None
        read = {"id": model["model"]} | {field: model[field] for field in _FACT_FIELDS if field in model}
        try:
            entries.append(CatalogModelFacts.model_validate(read))
        except ValidationError:
            return None
    return tuple(entries)


__all__ = ["ServedCatalogModels"]
