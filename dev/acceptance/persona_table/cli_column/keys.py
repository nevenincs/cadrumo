"""The exact list of returns a rerun drives: one JSON file of persona, modelo, year, period and, where known, horizon.

``unmatched`` writes the file from a table and the frontend results; ``sweep --keys-file`` reads it. A key without a
horizon is driven at every horizon of the replay whose plan emits it; a key with one only at that horizon, which is
the horizon of the table row it stands for.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from .world_report import ReturnKey


class KeysFileError(ValueError):
    """A keys file the schema refuses; the message names the file and the entry."""


@dataclass(frozen=True, slots=True)
class RerunKey:
    """One return of one persona to drive again, at the horizon of its table row when that is known."""

    persona: str
    modelo: str
    year: int
    period: str
    horizon: int | None = None

    @property
    def return_key(self) -> ReturnKey:
        """The return's key, ``(modelo, year, period)``."""
        return (self.modelo, self.year, self.period)

    def record(self) -> dict[str, object]:
        """The JSON object that carries the key; the horizon is left out when unknown."""
        data: dict[str, object] = {
            "persona": self.persona,
            "modelo": self.modelo,
            "year": self.year,
            "period": self.period,
        }
        if self.horizon is not None:
            data["horizon"] = self.horizon
        return data


def keys_json(keys: Iterable[RerunKey]) -> str:
    """The keys as the JSON list a keys file holds, in the order given."""
    return json.dumps([key.record() for key in keys], indent=2) + "\n"


def write_keys(path: Path, keys: Iterable[RerunKey]) -> None:
    """Write ``keys`` to ``path`` as a keys file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(keys_json(keys), encoding="utf-8", newline="\n")


def _text(path: Path, index: int, item: dict[str, object], name: str) -> str:
    value = item.get(name)
    if not isinstance(value, str) or not value:
        raise KeysFileError(f"{path}: entry {index}: {name} must be non-empty text")
    return value


def _whole(path: Path, index: int, item: dict[str, object], name: str) -> int | None:
    value = item.get(name)
    if value is None and name == "horizon":
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise KeysFileError(f"{path}: entry {index}: {name} must be a whole number")
    return value


def _key(path: Path, index: int, raw: object) -> RerunKey:
    if not isinstance(raw, dict):
        raise KeysFileError(f"{path}: entry {index}: must be an object")
    item = {str(name): value for name, value in raw.items()}
    year = _whole(path, index, item, "year")
    if year is None:
        raise KeysFileError(f"{path}: entry {index}: year must be a whole number")
    return RerunKey(
        _text(path, index, item, "persona"),
        _text(path, index, item, "modelo"),
        year,
        _text(path, index, item, "period"),
        _whole(path, index, item, "horizon"),
    )


def read_keys(path: Path) -> tuple[RerunKey, ...]:
    """The keys ``path`` holds, in file order and without repeats; a malformed file or entry is refused."""
    try:
        data: object = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as error:
        raise KeysFileError(f"{path}: not JSON: {error}") from error
    if not isinstance(data, list):
        raise KeysFileError(f"{path}: must hold a list of keys")
    return tuple(dict.fromkeys(_key(path, index, raw) for index, raw in enumerate(data)))


def personas_of(keys: Sequence[RerunKey]) -> tuple[str, ...]:
    """The personas the keys name, in order of first appearance."""
    return tuple(dict.fromkeys(key.persona for key in keys))


def allowed_at(keys: Sequence[RerunKey], persona: str, horizon: int) -> frozenset[ReturnKey]:
    """The returns of ``persona`` the keys ask for at ``horizon``: those without a horizon and those at it."""
    return frozenset(key.return_key for key in keys if key.persona == persona and key.horizon in (None, horizon))
