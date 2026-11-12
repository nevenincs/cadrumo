"""The ``--ascendiente KEY=VALUE,...`` grammar, mapped onto the leaves an ascendant row stores.

Each key names exactly one stored leaf. The values stay text: the ascendants operation
the window also uses reads them, requires the birth date, checks the NIF or NIE, the
name's length, the dates, the cohabiting bound, the rentas amount, the yes-or-no
own-return answer and the disability grade against the pinned authority, and refuses
a row by its position. A value cannot contain ``,``, which separates the keys. An edit
names the same keys to replace and, through ``--clear``, the keys to drop.
"""

from __future__ import annotations

from typing import Final

from cadrumo_client.commands.errors import CliRefusedBoundaryError

from ....application.user_profile.ascendant_rows import ProfileAscendantFact, ProfileAscendantRow

_KEY_TO_LEAF: Final = {
    "NIF": "nif",
    "APELLIDOS_NOMBRE": "apellidos_nombre",
    "NACIMIENTO": "birth_date",
    "FALLECIMIENTO": "fallecimiento",
    "CONVIVIENTES": "convivientes",
    "RENTAS": "rentas_anuales",
    "DECLARACION_PROPIA": "declaracion_propia",
    "DISCAPACIDAD": "discapacidad",
}
_INVALID_ROW_LOCALE_KEY: Final = "cli.config.profile.ascendiente.invalid_row"
_EDIT_EMPTY_LOCALE_KEY: Final = "cli.config.profile.ascendiente.edit_empty"


def _refuse_row(key: str | None) -> CliRefusedBoundaryError:
    return CliRefusedBoundaryError(
        translated_message=_INVALID_ROW_LOCALE_KEY, context={"key": key} if key is not None else {}
    )


def _leaf_values(raw: str) -> dict[str, str]:
    """The stored leaves one value names, in typed order; every key is known, distinct and has a value."""
    parts: dict[str, str] = {}
    for name, separator, value in (part.partition("=") for part in raw.split(",")):
        key = name.strip().upper()
        if not separator or key not in _KEY_TO_LEAF or key in parts or not value.strip():
            raise _refuse_row(key if key in _KEY_TO_LEAF else None)
        parts[key] = value.strip()
    return {_KEY_TO_LEAF[key]: value for key, value in parts.items()}


def parse_ascendiente_flag(raw: str) -> ProfileAscendantRow:
    """Read one ``--ascendiente`` value into a row; the keys are case-insensitive and each appears once."""
    return ProfileAscendantRow(
        facts=tuple(ProfileAscendantFact(field_key=leaf, value=value) for leaf, value in _leaf_values(raw).items())
    )


def parse_ascendiente_edit(
    values: list[str] | None, clears: list[str] | None
) -> tuple[dict[str, str], tuple[str, ...]]:
    """Read an edit's replacements and the leaves it clears; a key may be named once across both.

    The values of several ``--ascendiente`` options are read as one, so a key given twice is refused
    wherever it repeats. Each ``--clear`` names one key.
    """
    replaced = _leaf_values(",".join(values)) if values is not None and len(values) > 0 else {}
    cleared: list[str] = []
    for name in clears or ():
        key = name.strip().upper()
        leaf = _KEY_TO_LEAF.get(key)
        if leaf is None or leaf in cleared or leaf in replaced:
            raise _refuse_row(key if leaf is not None else None)
        cleared.append(leaf)
    if not replaced and not cleared:
        raise CliRefusedBoundaryError(translated_message=_EDIT_EMPTY_LOCALE_KEY)
    return replaced, tuple(cleared)


__all__ = ["parse_ascendiente_edit", "parse_ascendiente_flag"]
