"""Read the identity catalogue and resolve the identity roles a persona names."""

from __future__ import annotations

import re
from functools import cache

from .persona_toml import _bool, _choice, _date, _keys, _optional_string, _read_toml, _string, _Table, _tables
from .persona_types import (
    CATALOGUE_FORMAT,
    PERSONAS_ROOT,
    Identity,
    IdentityCatalogue,
    IdentityKind,
    IdentityRefusal,
    PersonaCatalogueError,
    _fail,
)

_KINDS: tuple[IdentityKind, ...] = ("nif", "nie", "cif", "nif_iva")


_PROVINCE = re.compile(r"0[1-9]|[1-4][0-9]|5[0-2]")


def _check_name_form(
    where: str,
    *,
    kind: IdentityKind,
    parts: tuple[str | None, str | None, str | None],
    razon_social: str | None,
    no_second_surname: bool,
) -> None:
    """Refuse an identity whose filing name is not exactly one of the two forms the designs take.

    A natural person states ``primer_apellido``, ``segundo_apellido`` and ``nombre``; a blank second
    surname never reads as absent, so a single surname says ``no_second_surname`` and leaves
    ``segundo_apellido`` out. An entity states one ``razon_social`` and no person part.
    """
    primer, segundo, nombre = parts
    if razon_social is not None:
        if any(part is not None for part in parts) or no_second_surname:
            raise _fail(where, "a razon_social identity states no person name part")
        if kind in ("nif", "nie"):
            raise _fail(where, f"a {kind} identifies a natural person and states primer_apellido and nombre")
        return
    if primer is None or nombre is None:
        raise _fail(where, "an identity states a razon_social, or a natural person's primer_apellido and nombre")
    if kind in ("cif",):
        raise _fail(where, "a cif identifies an entity and states a razon_social")
    if no_second_surname and segundo is not None:
        raise _fail(where, "no_second_surname contradicts a stated segundo_apellido")
    if segundo is None and not no_second_surname:
        raise _fail(where, "a natural person states segundo_apellido, or says no_second_surname")


def _renderings(table: _Table, where: str) -> tuple[tuple[int, str], ...]:
    """The operator's shorter renderings, one per field width, each fitting its width."""
    renderings: list[tuple[int, str]] = []
    for index, entry in enumerate(_tables(table.get("renderings"), f"{where} renderings")):
        here = f"{where} renderings[{index}]"
        _keys(entry, here, required=frozenset({"width", "text"}))
        width = entry["width"]
        if not isinstance(width, int) or isinstance(width, bool) or width <= 0:
            raise _fail(here, "a rendering states a positive field width")
        text = _string(entry, "text", here)
        if len(text) > width:
            raise _fail(here, "a rendering fits the width it is stated for")
        renderings.append((width, text))
    if len({width for width, _text in renderings}) != len(renderings):
        raise _fail(where, "one rendering per field width")
    return tuple(renderings)


def _identity(table: _Table, where: str) -> Identity:
    _keys(
        table,
        where,
        required=frozenset({"role", "persona", "kind", "value"}),
        optional=frozenset(
            {
                "primer_apellido",
                "segundo_apellido",
                "nombre",
                "razon_social",
                "no_second_surname",
                "renderings",
                "country",
                "primary",
                "province",
                "ceuta_melilla_deduction",
                "birth_date",
            }
        ),
    )
    province = _optional_string(table, "province", where)
    if province is not None and _PROVINCE.fullmatch(province) is None:
        raise _fail(where, f"province must be a two-digit Spanish province code 01-52, found {province!r}")
    kind = _choice(_string(table, "kind", where), _KINDS, where)
    primer = _optional_string(table, "primer_apellido", where)
    segundo = _optional_string(table, "segundo_apellido", where)
    nombre = _optional_string(table, "nombre", where)
    razon_social = _optional_string(table, "razon_social", where)
    no_second_surname = _bool(table, "no_second_surname", where) if "no_second_surname" in table else False
    renderings = _renderings(table, where)
    _check_name_form(
        where,
        kind=kind,
        parts=(primer, segundo, nombre),
        razon_social=razon_social,
        no_second_surname=no_second_surname,
    )
    return Identity(
        role=_string(table, "role", where),
        persona=_string(table, "persona", where),
        kind=kind,
        value=_string(table, "value", where),
        primer_apellido=primer,
        segundo_apellido=segundo,
        nombre=nombre,
        razon_social=razon_social,
        no_second_surname=no_second_surname,
        renderings=renderings,
        country=_optional_string(table, "country", where),
        primary=_bool(table, "primary", where) if "primary" in table else False,
        province=province,
        ceuta_melilla_deduction=(
            _bool(table, "ceuta_melilla_deduction", where) if "ceuta_melilla_deduction" in table else None
        ),
        birth_date=(
            _date(table["birth_date"], f"{where}.birth_date", biographical=True) if "birth_date" in table else None
        ),
    )


def parse_identity_catalogue(document: _Table, *, where: str = "identities.toml") -> IdentityCatalogue:
    """Validate a parsed ``identities.toml``: one value per role, one role per value."""
    if document.get("format") != CATALOGUE_FORMAT:
        raise _fail(where, f"format must be {CATALOGUE_FORMAT}, found {document.get('format')!r}")
    _keys(document, where, required=frozenset({"format", "convention", "identities"}), optional=frozenset({"refusals"}))
    identities = tuple(
        _identity(table, f"{where} identities[{index}]")
        for index, table in enumerate(_tables(document["identities"], where))
    )
    for attribute in ("role", "value"):
        seen = [getattr(identity, attribute) for identity in identities]
        if len(set(seen)) != len(seen):
            raise _fail(where, f"an identity {attribute} is declared twice")
    refusals: list[IdentityRefusal] = []
    for index, table in enumerate(_tables(document.get("refusals"), f"{where} refusals")):
        here = f"{where} refusals[{index}]"
        _keys(table, here, required=frozenset({"value", "kind", "reason"}))
        refusals.append(
            IdentityRefusal(
                value=_string(table, "value", here),
                kind=_choice(_string(table, "kind", here), _KINDS, here),
                reason=_string(table, "reason", here),
            )
        )
    if {refusal.value for refusal in refusals} & {identity.value for identity in identities}:
        raise _fail(where, "a refusal value is also bound to a role")
    return IdentityCatalogue(identities=identities, refusals=tuple(refusals))


@cache
def identity_catalogue() -> IdentityCatalogue:
    """Return the catalogue's ``identities.toml``."""
    return parse_identity_catalogue(_read_toml(PERSONAS_ROOT / "identities.toml"))


class _Roles:
    """Resolve every role a persona names, refusing an unknown one or another persona's."""

    def __init__(self, catalogue: IdentityCatalogue, persona_id: str) -> None:
        self._catalogue = catalogue
        self._persona_id = persona_id

    def __call__(self, role: object, where: str) -> str:
        if not isinstance(role, str):
            raise _fail(where, "an identity role must be a string")
        try:
            identity = self._catalogue.role(role)
        except PersonaCatalogueError as error:
            raise _fail(where, str(error)) from None
        if identity.persona != self._persona_id:
            raise _fail(where, f"identity role {role!r} belongs to persona {identity.persona!r}")
        return role


__all__ = [
    "identity_catalogue",
    "parse_identity_catalogue",
]
