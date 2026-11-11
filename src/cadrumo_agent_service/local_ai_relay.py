"""The selected local engine's lane as the runtime manager serves it, in the catalogue the window is relayed.

The local AI server sleeps until a document is read on this computer, so the
agent, which reads the server to describe its lane, finds nothing listening and
says the engine does not run and holds no model. The runtime manager owns the
supervised server's state: the desktop hands its served facts with a catalogue
read, and they replace the agent's probe on that one lane. A sleeping or
running server leaves the lane available; only a demanded start that failed
leaves it not running. Which models the server holds is read from the model
files on this computer. Without the manager's facts, a lane whose server the
agent could not read is unknown rather than down.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Annotated, Final, cast

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from cadrumo_client.contracts.model_runs import MODEL_RUN_MODEL_ID_PATTERN

from .providers.domain.record import LocalEngine

MAXIMUM_LOCAL_AI_MODELS: Final = 32
"""The most model facts one catalogue read carries, which keeps the read inside one administration document."""

_NOT_RUNNING: Final = "not_running"
_AVAILABLE: Final = "available"
_UNKNOWN: Final = "unknown"
_AUTHENTICATED: Final = frozenset({"authenticated", "not_applicable"})
_SELECTABLE_ADMISSIONS: Final = frozenset({"admitted", "unproven"})


class LocalAiServer(StrEnum):
    """What the manager serves of the selected engine's server."""

    DORMANT = "dormant"
    """No server runs and no demanded start failed: it starts when a document is read."""
    RUNNING = "running"
    """The server runs."""
    START_FAILED = "start_failed"
    """A demanded start failed: the server does not run."""


class LocalAiModel(BaseModel):
    """Whether one model on the person's local lists is stored on this computer."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, hide_input_in_errors=True)
    name: Annotated[str, Field(pattern=MODEL_RUN_MODEL_ID_PATTERN)]
    stored: bool


class LocalAiFacts(BaseModel):
    """The manager's served facts of the selected local engine, read from files and its supervision alone."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, hide_input_in_errors=True)
    engine: LocalEngine
    server: LocalAiServer
    models: Annotated[tuple[LocalAiModel, ...], Field(max_length=MAXIMUM_LOCAL_AI_MODELS)] = ()


def relay_local_ai(document: JsonValue, facts: LocalAiFacts | None) -> JsonValue:
    """``document`` with the local engines' lanes described by ``facts``, or unknown where the agent read no server.

    A document that lists no lanes, such as a refusal, is returned as it is.
    """
    if not isinstance(document, dict):
        return document
    lanes = document.get("providers")
    if isinstance(lanes, list):
        relayed: list[JsonValue] = [cast(JsonValue, _lane(lane, facts)) for lane in lanes]
        return {**document, "providers": relayed}
    catalog = document.get("catalog")
    if isinstance(catalog, dict) and isinstance(catalog.get("providers"), list):
        return {**document, "catalog": relay_local_ai(catalog, facts)}
    return document


def _lane(lane: object, facts: LocalAiFacts | None) -> object:
    """One lane, rewritten where it is a local engine's lane the facts, or their absence, describe."""
    if not isinstance(lane, Mapping):
        return lane
    record = cast(Mapping[str, object], lane)
    engine = _engine_of(record)
    if engine is None:
        return lane
    if facts is None:
        return _unknown(record) if _unread(record) else lane
    if facts.engine is not engine:
        return lane
    return _served(record, facts)


def _engine_of(record: Mapping[str, object]) -> LocalEngine | None:
    """The local engine a lane runs on, by its provider identity; ``None`` for any other lane."""
    provider = record.get("provider_id", record.get("provider"))
    try:
        return LocalEngine(provider) if isinstance(provider, str) else None
    except ValueError:
        return None


def _health(record: Mapping[str, object]) -> dict[str, object]:
    health = record.get("health")
    return dict(cast(Mapping[str, object], health)) if isinstance(health, Mapping) else {}


def _unread(record: Mapping[str, object]) -> bool:
    """Whether the agent says it could not read the lane's server."""
    engine = _health(record).get("engine")
    return isinstance(engine, Mapping) and cast(Mapping[str, object], engine).get("state") == _NOT_RUNNING


def _unknown(record: Mapping[str, object]) -> dict[str, object]:
    """A lane whose server nobody read: its transport and what it holds are unknown, not down."""
    health = _health(record) | {"transport": _UNKNOWN, "selectable": False, "engine": None, "reasons": []}
    return {**record, "health": health, "catalog": _models(record, {}, unread=True)}


def _served(record: Mapping[str, object], facts: LocalAiFacts) -> dict[str, object]:
    """The selected engine's lane as the manager serves it."""
    health = _health(record)
    unread = _unread(record)
    if facts.server is not LocalAiServer.START_FAILED and unread:
        health |= {"transport": _AVAILABLE, "engine": None, "reasons": []}
        health["selectable"] = _selectable(health)
    stored = {model.name: model.stored for model in facts.models}
    return {**record, "health": health, "catalog": _models(record, stored, unread=unread)}


def _selectable(health: Mapping[str, object]) -> bool:
    """Whether every axis the agent requires of a selectable lane holds."""
    return (
        health.get("configured") == _AVAILABLE
        and health.get("transport") == _AVAILABLE
        and health.get("authentication") in _AUTHENTICATED
        and health.get("catalog") == _AVAILABLE
        and health.get("admission") in _SELECTABLE_ADMISSIONS
    )


def _models(record: Mapping[str, object], stored: Mapping[str, bool], *, unread: bool) -> object:
    """The lane's catalogue, each model held as its files say.

    A model no fact names keeps what the agent read of a server it reached, and
    is held unknown where the agent read no server.
    """
    catalog = record.get("catalog")
    if not isinstance(catalog, Mapping):
        return catalog
    fields = cast(Mapping[str, object], catalog)
    models = fields.get("models")
    if not isinstance(models, list):
        return catalog
    return {**fields, "models": [_model(model, stored, unread=unread) for model in cast(list[object], models)]}


def _model(model: object, stored: Mapping[str, bool], *, unread: bool) -> object:
    if not isinstance(model, Mapping):
        return model
    entry = dict(cast(Mapping[str, object], model))
    name = entry.get("model")
    held = stored.get(name) if isinstance(name, str) else None
    if held is not None:
        return entry | {"installed": held}
    if unread:
        entry.pop("installed", None)
    return entry


__all__ = [
    "MAXIMUM_LOCAL_AI_MODELS",
    "LocalAiFacts",
    "LocalAiModel",
    "LocalAiServer",
    "relay_local_ai",
]
