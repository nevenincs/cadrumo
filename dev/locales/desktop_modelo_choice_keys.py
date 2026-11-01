"""The words the desktop shows for the choices a Modelo box serves.

The grammar serves each code with the key of its word; the codes come from the
shape that validates them, so a code gained is declared here with its word.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from cadrumo.application.modelo.edit_value_grammar import EDIT_CHOICE_LABEL_PREFIX
from cadrumo.core.spanish_postcode import SPANISH_PROVINCE_CODES

#: Every family of words a box's choices use, as ``prefix -> members``.
MODELO_CHOICE_FAMILIES: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType(
    {f"{EDIT_CHOICE_LABEL_PREFIX}province_code.": SPANISH_PROVINCE_CODES}
)

#: Every choice key the desktop words, each family member spelled out.
MODELO_CHOICE_KEYS: Final[frozenset[str]] = frozenset(
    f"{prefix}{member}" for prefix, members in MODELO_CHOICE_FAMILIES.items() for member in members
)
