"""The running agent's live catalogue for one lane, read from the document its gateway serves.

The service reads the document; this adapter only finds the lane in it and
takes two things. From each of its ``catalog.models[]`` it takes the model
value, the facts a selection is checked against: vision, size, context window
and licence, and whether the lane's local server holds the model. From its
``background_requests`` record it takes whether a background run may carry
images and PDFs, and the run options it honours, effort among them; with each
model's ``efforts``, the effort levels a run on that model may name. From its ``health`` it
takes only whether the agent states the lane's local engine not running: then
the agent did not read the server, and what it says the server holds is
unknown, as for a server that sleeps until a document is read.
Every other field is left unread. The model facts are validated with the
declared catalogue's own rules, so a value either catalogue would refuse is
refused here too, and a lane whose entries do not validate yields no live
catalogue rather than a partial one.

A :meth:`ServedCatalogModels.snapshot` reads the document once, when first
asked, and answers every later question from that one read.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from enum import Enum
from typing import Final, Literal, override

from pydantic import ValidationError

from cadrumo_client.contracts.model_runs import ModelRunMediaKind

from ..providers.application.ports import LiveCatalogModels, LiveLaneBackground
from ..providers.domain.catalog import BackgroundOption, EffortLevel, LiveCatalogModel
from ..providers.domain.record import LocalEngine

_FACT_FIELDS: Final = ("vision", "size_bytes", "context_length", "licence")
"""The served entry fields read besides the model value, each required, null where unstated."""

_INSTALLED_FIELD: Final = "installed"
"""Whether the lane's local server holds the model; an entry that does not state it leaves it unknown."""

_ENGINE_LANES: Final = frozenset(engine.value for engine in LocalEngine)
"""The provider identities of the lanes whose local server can hold a model."""

_ENGINE_NOT_RUNNING: Final = "not_running"
"""The engine state with which the agent says it could not read the lane's local server."""

_EFFORT_LEVEL: Final = re.compile(r"[a-z][a-z0-9_]{0,31}")
"""An effort level as the agent spells one; a model whose levels are not all spelled so offers none here."""

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
        # Only a local engine's lane has a server that holds models; a hosted lane's entries state no install.
        return _entries(models, server_read=_server_read(record) and provider in _ENGINE_LANES)

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
        media = _accepted_background_media(taken)
        listed = support.get("options")
        named = {name for name in listed if isinstance(name, str)} if isinstance(listed, list) else set()
        return LiveLaneBackground(
            accepted_media=media,
            options=tuple(option for option in BackgroundOption if option.value in named),
            model_efforts=_model_efforts(record),
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


def _model_efforts(record: Mapping[str, object]) -> dict[str, tuple[EffortLevel, ...]]:
    """Return each served model's effort levels, leaving out a model that states none or misspells one."""
    catalog = record.get("catalog")
    models = catalog.get("models") if isinstance(catalog, Mapping) else None
    efforts: dict[str, tuple[EffortLevel, ...]] = {}
    for model in models if isinstance(models, list) else ():
        if not isinstance(model, Mapping):
            continue
        value, levels = model.get("model"), model.get("efforts")
        if not isinstance(value, str) or not isinstance(levels, list) or not levels:
            continue
        spelled = tuple(level for level in levels if isinstance(level, str) and _EFFORT_LEVEL.fullmatch(level))
        if len(spelled) == len(levels):
            efforts[value] = spelled
    return efforts


def _accepted_background_media(taken: Sequence[object]) -> tuple[ModelRunMediaKind, ...] | None:
    """Keep unspecified media admission unknown rather than inventing support."""
    return (
        tuple(kind for (kind, _), accepted in zip(_MEDIA_FIELDS, taken, strict=True) if accepted)
        if all(isinstance(accepted, bool) for accepted in taken)
        else None
    )


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


def _server_read(record: Mapping[str, object]) -> bool:
    """Whether the agent read the lane's local server: not where it states the lane's engine not running."""
    health = record.get("health")
    engine = health.get("engine") if isinstance(health, Mapping) else None
    return not (isinstance(engine, Mapping) and engine.get("state") == _ENGINE_NOT_RUNNING)


def _entries(models: list[object], *, server_read: bool) -> tuple[LiveCatalogModel, ...] | None:
    entries: list[LiveCatalogModel] = []
    for model in models:
        if not isinstance(model, Mapping) or "model" not in model:
            return None
        installed = model.get(_INSTALLED_FIELD) if server_read else None
        read = {"id": model["model"], _INSTALLED_FIELD: installed} | {
            field: model[field] for field in _FACT_FIELDS if field in model
        }
        try:
            entries.append(LiveCatalogModel.model_validate(read))
        except ValidationError:
            return None
    return tuple(entries)


__all__ = ["ServedCatalogModels"]
