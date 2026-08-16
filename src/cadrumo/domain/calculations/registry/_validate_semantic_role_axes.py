"""Semantic-role sibling exception helpers for typo detection."""

from __future__ import annotations

import re
from typing import Final

from ....core import Modelo

_MODELO_PREFIXED_ROLE_RE: Final = re.compile(r"^m(\d{3})_(.+)$")
_MODELO_VALUES: Final[frozenset[str]] = frozenset(member.value for member in Modelo)

#: Month names AEAT uses to enumerate the per-period rows of a single concept.
#: A closed calendar axis, so two roles differing only in this trailing token
#: are deliberate siblings. Several are one character apart -- ``junio`` and
#: ``julio``, ``enero`` and ``febrero`` -- which is what drew the typo
#: detector to them.
_MONTH_AXIS_TOKENS: Final[frozenset[str]] = frozenset(
    (
        "enero",
        "febrero",
        "marzo",
        "abril",
        "mayo",
        "junio",
        "julio",
        "agosto",
        "septiembre",
        "octubre",
        "noviembre",
        "diciembre",
    )
)


#: Quarter tokens AEAT uses to enumerate the per-trimestre columns of a single
#: concept. The same closed-calendar-axis argument as :data:`_MONTH_AXIS_TOKENS`,
#: one period grain up: Modelo 347's Tipo 2 record declares "IMPORTE PERCIBIDO
#: POR TRANSMISIONES DE INMUEBLES SUJETAS A IVA {PRIMER,SEGUNDO,TERCER,CUARTO}
#: TRIMESTRE" as four sixteen-byte columns, so the four roles carrying them are
#: deliberate siblings rather than four spellings of one name. They differ by
#: exactly one digit, which is what drew the typo detector to them.
_QUARTER_AXIS_TOKENS: Final[frozenset[str]] = frozenset(("q1", "q2", "q3", "q4"))


def semantic_roles_are_quarter_axis_siblings(left: str, right: str) -> bool:
    """Return whether two roles differ only in a trailing calendar-quarter token."""
    return _differ_only_in_trailing_token(left, right, _QUARTER_AXIS_TOKENS)


def _differ_only_in_trailing_token(left: str, right: str, axis_tokens: frozenset[str]) -> bool:
    """Return whether two roles share a stem and end in two distinct axis tokens."""
    left_parts = left.split("_")
    right_parts = right.split("_")
    return (
        len(left_parts) > 1
        and len(right_parts) > 1
        and left_parts[:-1] == right_parts[:-1]
        and left_parts[-1] in axis_tokens
        and right_parts[-1] in axis_tokens
        and left_parts[-1] != right_parts[-1]
    )


def semantic_roles_are_modelo_prefix_siblings(left: str, right: str) -> bool:
    """Return whether two roles are the same concept scoped to different modelos.

    The ``mNNN_`` prefix is a namespace axis exactly like the tax-domain and
    declared-axis suffixes: the registry deliberately carries one stem across
    several modelos, and ``persona_relacion`` alone already ships under four
    prefixes. Whether the detector fired was decided by how textually similar
    the two modelo NUMBERS happened to be -- ``m156_``/``m345_`` passes while
    ``m156_``/``m165_`` refuses on a digit transposition -- which is a property
    of the numbering, not of the data.

    Modelo numbers are a closed set, so the prefix is the one machine-verifiable
    part of these strings. Both prefixes must name a real :class:`Modelo`; a
    genuinely mistyped prefix names none and stays a typo. The stems must match
    exactly, so a misspelt stem under one prefix is still caught.
    """
    left_modelo, left_stem = _split_modelo_prefix(left)
    right_modelo, right_stem = _split_modelo_prefix(right)
    if left_stem is None or right_stem is None:
        return False
    return left_stem == right_stem and left_modelo != right_modelo


def _split_modelo_prefix(role: str) -> tuple[str | None, str | None]:
    match = _MODELO_PREFIXED_ROLE_RE.match(role)
    if match is None:
        return None, None
    modelo = match.group(1)
    if modelo not in _MODELO_VALUES:
        return None, None
    return modelo, match.group(2)


def semantic_roles_are_month_axis_siblings(left: str, right: str) -> bool:
    """Return whether two roles differ only in a trailing calendar-month token."""
    return _differ_only_in_trailing_token(left, right, _MONTH_AXIS_TOKENS)


def semantic_roles_are_tax_domain_siblings(left: str, right: str) -> bool:
    domain_suffixes = {"irpf", "is", "iva"}
    left_parts = left.split("_")
    right_parts = right.split("_")
    return (
        len(left_parts) > 1
        and len(right_parts) > 1
        and left_parts[:-1] == right_parts[:-1]
        and left_parts[-1] in domain_suffixes
        and right_parts[-1] in domain_suffixes
    )


_SEMANTIC_ROLE_AXIS_SUFFIXES: tuple[tuple[str, ...], ...] = (
    ("permanente", "aumento"),
    ("permanente", "disminucion"),
    ("temporaria", "ejercicio", "aumento"),
    ("temporaria", "ejercicio", "disminucion"),
    ("temporaria", "anteriores", "aumento"),
    ("temporaria", "anteriores", "disminucion"),
    ("saldo", "inicial", "aumento"),
    ("saldo", "final", "aumento"),
)


def semantic_roles_are_axis_siblings(left: str, right: str) -> bool:
    left_stem, left_axis = _split_semantic_role_axis_suffix(left)
    right_stem, right_axis = _split_semantic_role_axis_suffix(right)
    if left_stem is not None and right_stem is not None and left_stem == right_stem and left_axis != right_axis:
        return True
    return _semantic_roles_are_axis_token_siblings(left, right)


def _split_semantic_role_axis_suffix(role: str) -> tuple[tuple[str, ...] | None, tuple[str, ...] | None]:
    parts = tuple(role.split("_"))
    for suffix in _SEMANTIC_ROLE_AXIS_SUFFIXES:
        if len(parts) <= len(suffix):
            continue
        if parts[-len(suffix) :] == suffix:
            return parts[: -len(suffix)], suffix
    return None, None


def _semantic_roles_are_axis_token_siblings(left: str, right: str) -> bool:
    left_parts = tuple(left.split("_"))
    right_parts = tuple(right.split("_"))
    return _semantic_role_related_party_row_slot_siblings(left_parts, right_parts)


def _semantic_role_related_party_row_slot_siblings(left: tuple[str, ...], right: tuple[str, ...]) -> bool:
    if len(left) < 4 or left[:-1] != right[:-1] or left[-1] == right[-1]:
        return False
    return (
        left[:2] == ("related", "party")
        and left[-1] in {"1", "2", "3", "4", "5"}
        and right[-1] in {"1", "2", "3", "4", "5"}
    )
