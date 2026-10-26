"""The running agent's live catalogue for one lane, read from the document its gateway serves.

The service reads the document; this adapter only finds the lane in it and
takes two things. From each of its ``catalog.models[]`` it takes the model
value, the facts a selection is checked against: vision, size, context window
and licence, and whether the lane's local server holds the model. From its
``background_requests`` record it takes whether a background run may carry
images and PDFs, and the reply options it honours.
Every other field is left unread. The model facts are validated with the
declared catalogue's own rules, so a value either catalogue would refuse is
refused here too, and a lane whose entries do not validate yields no live
catalogue rather than a partial one.

A :meth:`ServedCatalogModels.snapshot` reads the document once, when first
asked, and answers every later question from that one read.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from enum import Enum
from typing import Final, Literal, override

from pydantic import ValidationError

from cadrumo_client.contracts.model_runs import ModelRunMediaKind

from ..providers.application.ports import LiveCatalogModels, LiveLaneBackground
from ..providers.domain.catalog import BackgroundOption, LiveCatalogModel

_FACT_FIELDS: Final = ("vision", "size_bytes", "context_length", "licence")
"""The served entry fields read besides the model value, each required, null where unstated."""

_INSTALLED_FIELD: Final = "installed"
"""Whether the lane's local server holds the model; an entry that does not state it leaves it unknown."""

_MEDIA_FIELDS: Final = ((ModelRunMediaKind.IMAGE, "accepts_images"), (ModelRunMediaKind.PDF, "accepts_pdfs"))
"""Each attachment family a background run may carry, and the served field that says whether the lane takes it."""


class ServedCatalogModels(LiveCatalogModels):
    """Read one lane's live entries and background support from the document ``read`` returns."""

    def __init__(self, read: Callable[[], Mapping[str, object] | None]) -> None:
        """Bind the reader of the running agent's served catalogue; it returns ``None`` when none is running."""
        self._read = read

    @override
    def snapshot(self) -> ServedCatalogModels:
        """Return a view over one read of the document, made when the view is first asked."""
        return ServedCatalogModels(_ReadOnce(self._read))

    @override
    def lane_models(self, provider: str, transport: str) -> tuple[LiveCatalogModel, ...] | None:
        """Return the lane's live entries, empty when the document lists no such lane, ``None`` when unread."""
        record = self._lane_record(provider, transport)
        if record is _Unread.UNREAD:
            return None
        if record is None:
            return ()
        catalog = record.get("catalog")
        models = catalog.get("models") if isinstance(catalog, Mapping) else None
        if not isinstance(models, list):
            return None
        return _entries(models)

    @override
    def lane_background(self, provider: str, transport: str) -> LiveLaneBackground | None:
        """Return what a background run on the lane takes, or ``None`` when the document does not say."""
        record = self._lane_record(provider, transport)
        if record is _Unread.UNREAD or record is None:
            return None
        support = record.get("background_requests")
        if not isinstance(support, Mapping):
            return None
        taken = [support.get(field) for _, field in _MEDIA_FIELDS]
        media = (
            tuple(kind for (kind, _), accepted in zip(_MEDIA_FIELDS, taken, strict=True) if accepted)
            if all(isinstance(accepted, bool) for accepted in taken)
            else None
        )
        listed = support.get("options")
        named = {name for name in listed if isinstance(name, str)} if isinstance(listed, list) else set()
        return LiveLaneBackground(
            accepted_media=media, options=tuple(option for option in BackgroundOption if option.value in named)
        )

    def _lane_record(self, provider: str, transport: str) -> Mapping[str, object] | Literal[_Unread.UNREAD] | None:
        """Return the lane's record, ``None`` when the document lists no such lane, ``UNREAD`` when it is unread."""
        document = self._read()
        if document is None:
            return _Unread.UNREAD
        records = document.get("providers")
        if not isinstance(records, list):
            return _Unread.UNREAD
        for record in records:
            if isinstance(record, Mapping) and (record.get("provider_id"), record.get("transport")) == (
                provider,
                transport,
            ):
                return {key: value for key, value in record.items() if isinstance(key, str)}
        return None


class _Unread(Enum):
    """No live catalogue to read: no agent is running, or its document is not one."""

    UNREAD = "unread"


class _ReadOnce:
    """Call ``read`` on first use and answer every later call with that result."""

    def __init__(self, read: Callable[[], Mapping[str, object] | None]) -> None:
        self._read: Callable[[], Mapping[str, object] | None] | None = read
        self._document: Mapping[str, object] | None = None

    def __call__(self) -> Mapping[str, object] | None:
        if self._read is not None:
            self._document, self._read = self._read(), None
        return self._document


def _entries(models: list[object]) -> tuple[LiveCatalogModel, ...] | None:
    entries: list[LiveCatalogModel] = []
    for model in models:
        if not isinstance(model, Mapping) or "model" not in model:
            return None
        read = {"id": model["model"], _INSTALLED_FIELD: model.get(_INSTALLED_FIELD)} | {
            field: model[field] for field in _FACT_FIELDS if field in model
        }
        try:
            entries.append(LiveCatalogModel.model_validate(read))
        except ValidationError:
            return None
    return tuple(entries)


__all__ = ["ServedCatalogModels"]
