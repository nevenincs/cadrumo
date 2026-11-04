"""The persona reader admits the catalogue's contract and refuses a departure from it."""

from __future__ import annotations

import copy
import tomllib
from typing import Any

import pytest

from .personas import (
    PERSONAS_ROOT,
    PersonaCatalogueError,
    YearEnvelope,
    identity_catalogue,
    parse_identity_catalogue,
    parse_persona,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: A synthetic envelope: the reader only shifts tokens against its bounds, so any ordered pair serves.
_ENVELOPE = YearEnvelope(floor=100, horizon=104)
_PERSONA = "asalariada-familia"


def _document(name: str) -> dict[str, Any]:
    return tomllib.loads((PERSONAS_ROOT / _PERSONA / name).read_text(encoding="utf-8"))


def _parse(persona_document: dict[str, Any], *, envelope: YearEnvelope = _ENVELOPE) -> None:
    parse_persona(
        _PERSONA,
        persona_document=persona_document,
        ledger_text=(PERSONAS_ROOT / _PERSONA / "ledger.csv").read_text(encoding="utf-8"),
        documents_document=_document("documents.toml"),
        expectations_document=_document("expectations.toml"),
        catalogue=identity_catalogue(),
        envelope=envelope,
    )


def _changed(path: tuple[str, ...], value: object) -> dict[str, Any]:
    document = copy.deepcopy(_document("persona.toml"))
    table = document
    for key in path[:-1]:
        table = table[key]
    table[path[-1]] = value
    return document


def test_the_unchanged_persona_is_admitted_with_a_birth_before_the_floor() -> None:
    document = _document("persona.toml")
    birth = document["profile"]["taxpayer-birth-date"]["year"]
    assert birth.startswith("horizon-") and int(birth.removeprefix("horizon-")) > _ENVELOPE.horizon - _ENVELOPE.floor
    _parse(document)


def test_an_unknown_format_is_refused() -> None:
    with pytest.raises(PersonaCatalogueError, match="format must be 1"):
        _parse(_changed(("format",), 2))
    with pytest.raises(PersonaCatalogueError, match="format must be 1"):
        parse_identity_catalogue({"format": 2, "convention": {}, "identities": []})


def test_an_unknown_identity_role_is_refused() -> None:
    with pytest.raises(PersonaCatalogueError, match="unknown identity role"):
        _parse(_changed(("profile", "tax-id"), {"identity": "asalariada.desconocida"}))


def test_another_personas_identity_role_is_refused() -> None:
    with pytest.raises(PersonaCatalogueError, match="belongs to persona"):
        _parse(_changed(("profile", "tax-id"), {"identity": "fontanero.titular"}))


def test_an_unknown_field_is_refused() -> None:
    with pytest.raises(PersonaCatalogueError, match="unknown fields"):
        _parse(_changed(("persona", "nickname"), "Lucía"))


@pytest.mark.parametrize(
    ("path", "token"),
    [
        (("persona", "fiscal_year"), "horizon+1"),
        (("persona", "fiscal_year"), "floor-1"),
        (("clock", "as_of"), {"year": "horizon+1", "month": 2, "day": 16}),
        (("profile", "taxpayer-birth-date"), {"year": "horizon+1", "month": 6, "day": 14}),
    ],
)
def test_a_year_outside_the_envelope_is_refused(path: tuple[str, ...], token: object) -> None:
    with pytest.raises(PersonaCatalogueError, match="outside the supported envelope"):
        _parse(_changed(path, token))


def test_a_literal_year_is_refused() -> None:
    with pytest.raises(PersonaCatalogueError, match="is not a year token"):
        _parse(_changed(("persona", "fiscal_year"), str(_ENVELOPE.horizon)))
