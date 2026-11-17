"""Shared fixtures for the persona reader tests: the synthetic envelope and the unchanged persona files."""

from __future__ import annotations

import copy
import tomllib
from typing import Any

from .persona_identities import identity_catalogue
from .persona_types import PERSONAS_ROOT, Persona, YearEnvelope
from .personas import parse_persona

#: A synthetic envelope: the reader only shifts tokens against its bounds, so any ordered pair serves.
_ENVELOPE = YearEnvelope(floor=100, horizon=104)


_PERSONA = "asalariada-familia"


def _document(name: str) -> dict[str, Any]:
    return tomllib.loads((PERSONAS_ROOT / _PERSONA / name).read_text(encoding="utf-8"))


def _parse(
    persona_document: dict[str, Any],
    *,
    envelope: YearEnvelope = _ENVELOPE,
    expectations_document: dict[str, Any] | None = None,
    omit_below_floor: bool = False,
) -> Persona:
    return parse_persona(
        _PERSONA,
        persona_document=persona_document,
        ledger_text=(PERSONAS_ROOT / _PERSONA / "ledger.csv").read_text(encoding="utf-8"),
        documents_document=_document("documents.toml"),
        expectations_document=_document("expectations.toml")
        if expectations_document is None
        else expectations_document,
        catalogue=identity_catalogue(),
        envelope=envelope,
        omit_below_floor=omit_below_floor,
    )


def _changed(path: tuple[str, ...], value: object) -> dict[str, Any]:
    document = copy.deepcopy(_document("persona.toml"))
    table = document
    for key in path[:-1]:
        table = table[key]
    table[path[-1]] = value
    return document


#: The synthetic envelope with its horizon lowered one year above the floor, as a replay of an earlier year reads it.
_LOWERED = YearEnvelope(floor=_ENVELOPE.floor, horizon=_ENVELOPE.floor + 1)


def _with_filed_returns(*blocks: dict[str, object]) -> dict[str, Any]:
    document = copy.deepcopy(_document("persona.toml"))
    document["filed_returns"] = list(blocks)
    return document
