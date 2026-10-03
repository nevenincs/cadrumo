"""Derive casilla display vocabulary and resolve the documentation build language."""

from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING, Final

from dev._paths import REPO_ROOT

from ._locale_chrome import docs_chrome
from .legal_catalogue import load_legal_provisions

if TYPE_CHECKING:
    from cadrumo.core.external_constants import OutputLanguage
    from cadrumo.domain.calculations.registry.schema import ModeloDefinition
    from cadrumo.domain.calculations.registry.schema_surfaces import CasillaConstraints, CasillaDefinition


#: The catalogue namespace holding every display string this surface renders.
#: Nothing user-visible is authored as a Python literal: the vocabulary lives in
#: the four shared catalogues, Spanish first as the authoritative source, and is
#: resolved per build language through the shared
#: :func:`~dev.docs._locale_chrome.docs_chrome` resolver the sibling generated
#: surfaces use, so all three read chrome through one authority.
_DISPLAY_PREFIX: Final[str] = "docs.casilla"


#: The one exception, and it is not chrome: the official Spanish name of a legal
#: instrument. AEAT and BOE publish "Ley 37/1992" and "Real Decreto 1624/1992"
#: under those names in every language, exactly as a modelo's official name
#: stays Spanish, so translating them would name a norm that does not exist. The
#: DESCRIPTIVE kinds - AEAT's own dictionaries, manuals, record designs - are
#: not instrument names and live in the catalogue under ``legal_kind.*``.
_LEGAL_INSTRUMENT_NAMES: Final[dict[str, str]] = {
    "acuerdo_internacional": "Convenio",
    "acuerdo_parlamentario": "Acuerdo",
    "ley": "Ley",
    "orden": "Orden",
    "real_decreto": "Real Decreto",
    "real_decreto_legislativo": "Real Decreto Legislativo",
    "real_decreto_ley": "Real Decreto-ley",
    "reglamento": "Reglamento",
    "resolucion": "Resolución",
}


#: Registry section and tax-domain tokens that are AEAT acronyms, not words:
#: capitalising them as prose would render the tax itself as "Iva".
_ACRONYMS: Final[frozenset[str]] = frozenset(
    {"aeat", "cif", "iae", "irnr", "irpf", "is", "isp", "iva", "nif", "oss", "ue"},
)


#: Display keys with no enumeration behind them: page chrome and the
#: constraint phrasings. Everything else is derived from the schema's own closed
#: value sets by :func:`display_locale_keys`, so a new enum member surfaces as a
#: missing-string failure rather than as silently absent copy.
_UNENUMERATED_DISPLAY_KEYS: Final[tuple[str, ...]] = (
    "value_range.between",
    "value_range.at_least",
    "value_range.at_most",
    "length.between",
    "length.at_least",
    "length.at_most",
    "value_enum",
    "chrome.legal_basis",
    "chrome.established_by",
    "chrome.registry_identifiers",
    "chrome.required",
    "chrome.segmento",
    "chrome.not_on_official_form",
    "chrome.derived_from",
    "chrome.sections_nav",
    "chrome.casilla_id",
    "chrome.record_design_number",
    "chrome.semantic_role",
    "chrome.binding",
    "chrome.formula",
    "chrome.registry_section",
    "chrome.sources",
    "chrome.revisions",
    "chrome.casilla_count",
    "chrome.alternative_join",
    "chrome.list_and",
    "chrome.general_section",
    "chrome.index_title",
    "chrome.index_intro",
)


def display_locale_keys() -> tuple[str, ...]:
    """Every catalogue key this surface can render, fully qualified.

    One derivation serving two consumers: the gate that proves each key resolves
    in all four languages, and the locale scaffold's registration (the AST key
    scan walks ``src/cadrumo`` only, so keys this dev-side surface consumes are
    invisible to it and would be pruned as stale without an explicit
    registration).

    The enum-backed families are read from the schema's own closed value sets
    rather than listed, so adding a ``BindingSourceKind`` member or a
    ``data_type`` immediately demands its string instead of rendering nothing.
    """

    from cadrumo.core.aggregation import BindingSourceKind
    from cadrumo.domain.calculations.registry.schema_input_kind import InputKind

    keys: list[str] = [f"{_DISPLAY_PREFIX}.{suffix}" for suffix in _UNENUMERATED_DISPLAY_KEYS]
    for member in InputKind:
        keys.append(f"{_DISPLAY_PREFIX}.input_kind.{member.value}")
        keys.append(f"{_DISPLAY_PREFIX}.input_kind_count.{member.value}")
    keys.extend(f"{_DISPLAY_PREFIX}.binding_source.{member.value}" for member in BindingSourceKind)
    keys.extend(_schema_display_keys())
    kinds = {provision.kind for provision in load_legal_provisions(REPO_ROOT)}
    keys.extend(f"{_DISPLAY_PREFIX}.legal_kind.{kind}" for kind in sorted(kinds) if kind not in _LEGAL_INSTRUMENT_NAMES)
    return tuple(dict.fromkeys(keys))


def _schema_display_keys() -> tuple[str, ...]:
    from cadrumo.domain.calculations.registry.schema import ModeloDefinition
    from cadrumo.domain.calculations.registry.schema_surfaces import CasillaConstraints, CasillaDefinition

    keys = [f"{_DISPLAY_PREFIX}.data_type.{value}" for value in _closed_values(CasillaDefinition, "data_type")]
    keys.extend(f"{_DISPLAY_PREFIX}.cadence.{value}" for value in _closed_values(ModeloDefinition, "cadence"))
    keys.extend(
        f"{_DISPLAY_PREFIX}.value_range.{value}"
        for value in _closed_values(CasillaConstraints, "sign")
        if value != "any"
    )
    return tuple(keys)


def _humanise_token(token: str) -> str:
    """Read a snake_case registry token as prose (``rdto_trabajo`` -> ``Rdto trabajo``)."""
    words = token.replace("_", " ").replace("-", " ").strip()
    return words[:1].upper() + words[1:] if words else ""


def _token_display(token: str) -> str:
    """Render a registry token, preserving AEAT acronyms in upper case."""
    return token.upper() if token.lower() in _ACRONYMS else _humanise_token(token)


def _section_display(section: tuple[str, ...], language: OutputLanguage) -> str:
    """The human display for a registry section path, token by token."""
    return " › ".join(_token_display(part) for part in section if part) or docs_chrome(
        "docs.casilla.chrome.general_section", language
    )


def _section_anchor(section: tuple[str, ...]) -> str:
    """A page-local id for one section group, distinct from the casilla ids."""
    joined = "-".join(part for part in section if part) or "general"
    slug = re.sub(r"[^a-z0-9]+", "-", joined.lower()).strip("-")
    return f"section-{slug or 'general'}"


def _display_language() -> OutputLanguage:
    """The one language this build renders, read from the shared build signal."""
    from .build import docs_build_language

    return docs_build_language(os.environ)


def _closed_values(
    model: type[CasillaDefinition | ModeloDefinition | CasillaConstraints],
    field: str,
) -> tuple[str, ...]:
    """Every value a closed field admits, whether it is a Literal or an Enum.

    This read ``get_args`` alone, which answers for ``Literal["money", ...]``
    and returns an EMPTY TUPLE for an ``Enum`` annotation. All three fields
    it is asked about have since become enums, so it had been quietly
    yielding nothing -- and yielding nothing is indistinguishable here from
    a family with no members, so the derivation this docstring calls a
    guarantee ("adding a member immediately demands its string") had stopped
    making any demand at all. Twenty-six shipped keys the surface renders on
    every page were reported as stale copy.

    An unreadable field raises rather than returning empty: silence is the
    exact failure being repaired, and a family that yields nothing is never
    a fact this function is entitled to assert.
    """
    from enum import Enum
    from typing import get_args

    field_info = model.model_fields.get(field)
    if field_info is None:
        raise LookupError(f"{model.__name__} declares no field {field!r} to derive display keys from")
    annotation = field_info.annotation
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return tuple(str(member.value) for member in annotation)
    values = tuple(str(value) for value in get_args(annotation))
    if not values:
        raise LookupError(f"{model.__name__}.{field} is neither an Enum nor a Literal, so its values are unknown")
    return values
