"""The ``--ascendiente KEY=VALUE,...`` grammar, mapped onto the leaves an ascendant row stores.

Each key names exactly one stored leaf. The values stay text: the ascendants operation
the window also uses reads them, checks the NIF or NIE, the dates and the cohabiting
bound against the pinned authority, and refuses a row by its position.
"""

from __future__ import annotations

from typing import Final

from cadrumo_client.commands.errors import CliRefusedBoundaryError

from ....application.user_profile.ascendant_rows import ProfileAscendantFact, ProfileAscendantRow

_KEY_TO_LEAF: Final = {
    "NIF": "nif",
    "NACIMIENTO": "birth_date",
    "FALLECIMIENTO": "fallecimiento",
    "CONVIVIENTES": "convivientes",
}
_INVALID_FLAG_LOCALE_KEY: Final = "cli.config.profile.ascendiente.invalid_flag"
_INVALID_ROW_LOCALE_KEY: Final = "cli.config.profile.ascendiente.invalid_row"


def _refuse_row(key: str | None) -> CliRefusedBoundaryError:
    return CliRefusedBoundaryError(
        translated_message=_INVALID_ROW_LOCALE_KEY, context={"key": key} if key is not None else {}
    )


def parse_ascendiente_flag(raw: str) -> ProfileAscendantRow:
    """Read one ``--ascendiente`` value into a row; the keys are case-insensitive and each appears once."""
    pairs = [part.partition("=") for part in raw.split(",")]
    parts: dict[str, str] = {}
    for name, separator, value in pairs:
        key = name.strip().upper()
        if not separator or key not in _KEY_TO_LEAF or key in parts or not value.strip():
            raise _refuse_row(key if key in _KEY_TO_LEAF else None)
        parts[key] = value.strip()
    if "NACIMIENTO" not in parts:
        raise CliRefusedBoundaryError(translated_message=_INVALID_FLAG_LOCALE_KEY, context={"key": "NACIMIENTO"})
    return ProfileAscendantRow(
        facts=tuple(ProfileAscendantFact(field_key=_KEY_TO_LEAF[key], value=value) for key, value in parts.items())
    )


__all__ = ["parse_ascendiente_flag"]
