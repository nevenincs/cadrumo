"""The parts of the four packed rental fields, served and accepted as typed sub-rows.

``usos``, ``valores_catastrales``, ``mejoras`` and ``inquilinos`` are stored as one packed
string each (see ``domain.contribuyente.inmueble_facts``). The profile view serves them
beside that text as a list of typed parts with the words of every token and a description of
each sub-field, and the row operations accept the same parts instead of the text. Both
directions go through the one grammar of ``inmueble_facts``: a part is judged by the entry
builder the text parser uses and rendered by the serialiser that writes the stored form, so
a surface neither parses nor composes the encoding.

A stored value that does not parse is served with no parts and an invalid marker; it is
never guessed. Private facts are carried here; nothing in this module logs them.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, Final, Literal

from pydantic import BaseModel, Field

from ...core.errors.hierarchy import ProfileAnswerTypeError
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import tr
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.contribuyente.arrendamiento_record import InquilinoEdad
from ...domain.contribuyente.inmueble_facts import (
    ARRENDAMIENTO_SECTION,
    INMUEBLE_SECTION,
    inquilino_from_entry,
    mejora_from_entry,
    money_text,
    parse_inquilinos,
    parse_mejoras,
    parse_usos,
    parse_valores_catastrales,
    serialise_inquilinos,
    serialise_mejoras,
    serialise_usos,
    serialise_valores_catastrales,
    uso_from_entry,
    valor_catastral_from_entry,
)
from ...domain.contribuyente.inmueble_record import UsoInmuebleTipo
from ...domain.user_profile.errors import ProfileSchemaValidationError
from ..operations.error_detail import served_words_language
from .record_group_reduction_words import TENANT_BAND_WORDS_LOCALE_KEYS

INVALID_LOCALE_KEY: Final = "application.user_profile.row_parts.invalid"
"""Why a stored value is not served by parts, and what the operator does."""


class RowPartKind(StrEnum):
    """Which typed sub-row a packed field holds."""

    USO = "uso"
    VALOR_CATASTRAL = "valor_catastral"
    MEJORA = "mejora"
    INQUILINO = "inquilino"


class RowPartValueType(StrEnum):
    """What one sub-field holds, so a surface offers the editor the value deserves."""

    DATE = "date"
    AMOUNT = "amount"
    YEAR = "year"
    CHOICE = "choice"
    BOOLEAN = "boolean"
    TAX_ID = "tax_id"


class ProfileRowUsoValues(BaseModel):
    """A use of a property other than letting it: its type token and the dated interval."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["uso"] = "uso"
    tipo: str
    #: A calendar date, ``YYYY-MM-DD``.
    desde: str
    #: A calendar date, or ``None`` when the use continues.
    hasta: str | None = None


class ProfileRowValorCatastralValues(BaseModel):
    """The cadastral values of one IBI year."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["valor_catastral"] = "valor_catastral"
    year: int
    #: An amount with two decimals.
    total: str
    construccion: str
    #: The year the collective valuation that set the values entered into force, when stated.
    vigor: int | None = None


class ProfileRowMejoraValues(BaseModel):
    """An improvement made before the ledger covers the property."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["mejora"] = "mejora"
    #: A calendar date, ``YYYY-MM-DD``.
    fecha: str
    #: An amount with two decimals.
    importe: str


class ProfileRowInquilinoValues(BaseModel):
    """A tenant as the lease states it."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["inquilino"] = "inquilino"
    nif: str
    franja_edad: str
    extranjero: bool


type ProfileRowPartInput = Annotated[
    ProfileRowUsoValues | ProfileRowValorCatastralValues | ProfileRowMejoraValues | ProfileRowInquilinoValues,
    Field(discriminator="kind"),
]
"""One part a row operation accepts in place of the packed text; the same shape a view serves."""


class ProfileFieldUsoPart(ProfileRowUsoValues):
    """A served use: its values and the words of its type."""

    tipo_words: str
    tipo_words_language: OutputLanguage


class ProfileFieldInquilinoPart(ProfileRowInquilinoValues):
    """A served tenant: its values and the words of its age band. The identifier is served as the view serves it."""

    franja_edad_words: str
    franja_edad_words_language: OutputLanguage


type ProfileFieldPart = Annotated[
    ProfileFieldUsoPart | ProfileRowValorCatastralValues | ProfileRowMejoraValues | ProfileFieldInquilinoPart,
    Field(discriminator="kind"),
]


class ProfileFieldPartChoice(BaseModel):
    """One token a sub-field may hold and its words."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    value: str
    label: str


class ProfileFieldPartField(BaseModel):
    """One sub-field of a part: its key within the part, its words and what it holds."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    key: str
    label: str
    help: str
    value_type: RowPartValueType
    required: bool
    choices: tuple[ProfileFieldPartChoice, ...] = ()


class ProfileFieldPartsSpec(BaseModel):
    """How a packed field is served by parts: what a part is, its sub-fields, and whether the value parsed."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    part_kind: RowPartKind
    #: What one part is, in words.
    part_words: str
    sub_fields: tuple[ProfileFieldPartField, ...]
    #: The language of every word in this description.
    words_language: OutputLanguage
    #: True when the stored value does not parse, so no parts are served.
    invalid: bool = False
    invalid_words: str | None = None


@dataclass(frozen=True, slots=True)
class _SubField:
    key: str
    value_type: RowPartValueType
    required: bool
    label_key: str
    help_key: str


@dataclass(frozen=True, slots=True)
class FieldParts:
    """The parts of one packed value and its sub-field description; both ``None`` for a field not served by parts."""

    parts: tuple[ProfileFieldPart, ...] | None
    spec: ProfileFieldPartsSpec | None


_COMPOUND: Final[Mapping[tuple[str, str], RowPartKind]] = MappingProxyType(
    {
        (INMUEBLE_SECTION, "usos"): RowPartKind.USO,
        (INMUEBLE_SECTION, "valores_catastrales"): RowPartKind.VALOR_CATASTRAL,
        (INMUEBLE_SECTION, "mejoras"): RowPartKind.MEJORA,
        (ARRENDAMIENTO_SECTION, "inquilinos"): RowPartKind.INQUILINO,
    }
)
_KIND_WORDS_LOCALE_KEYS: Final[Mapping[RowPartKind, str]] = MappingProxyType(
    {
        RowPartKind.USO: "application.user_profile.row_parts.kind.uso",
        RowPartKind.VALOR_CATASTRAL: "application.user_profile.row_parts.kind.valor_catastral",
        RowPartKind.MEJORA: "application.user_profile.row_parts.kind.mejora",
        RowPartKind.INQUILINO: "application.user_profile.row_parts.kind.inquilino",
    }
)
_USO_TIPO_WORDS_LOCALE_KEYS: Final[Mapping[UsoInmuebleTipo, str]] = MappingProxyType(
    {
        UsoInmuebleTipo.VIVIENDA_HABITUAL: "application.user_profile.row_parts.choice.uso.tipo.vivienda_habitual",
        UsoInmuebleTipo.DISPOSICION_PROPIETARIO: (
            "application.user_profile.row_parts.choice.uso.tipo.disposicion_propietario"
        ),
        UsoInmuebleTipo.ACTIVIDAD_ECONOMICA: "application.user_profile.row_parts.choice.uso.tipo.actividad_economica",
    }
)
_SUB_FIELDS_LOCALE_KEYS: Final[Mapping[RowPartKind, tuple[_SubField, ...]]] = MappingProxyType(
    {
        RowPartKind.USO: (
            _SubField(
                "tipo",
                RowPartValueType.CHOICE,
                True,
                "application.user_profile.row_parts.field.uso.tipo.label",
                "application.user_profile.row_parts.field.uso.tipo.help",
            ),
            _SubField(
                "desde",
                RowPartValueType.DATE,
                True,
                "application.user_profile.row_parts.field.uso.desde.label",
                "application.user_profile.row_parts.field.uso.desde.help",
            ),
            _SubField(
                "hasta",
                RowPartValueType.DATE,
                False,
                "application.user_profile.row_parts.field.uso.hasta.label",
                "application.user_profile.row_parts.field.uso.hasta.help",
            ),
        ),
        RowPartKind.VALOR_CATASTRAL: (
            _SubField(
                "year",
                RowPartValueType.YEAR,
                True,
                "application.user_profile.row_parts.field.valor_catastral.year.label",
                "application.user_profile.row_parts.field.valor_catastral.year.help",
            ),
            _SubField(
                "total",
                RowPartValueType.AMOUNT,
                True,
                "application.user_profile.row_parts.field.valor_catastral.total.label",
                "application.user_profile.row_parts.field.valor_catastral.total.help",
            ),
            _SubField(
                "construccion",
                RowPartValueType.AMOUNT,
                True,
                "application.user_profile.row_parts.field.valor_catastral.construccion.label",
                "application.user_profile.row_parts.field.valor_catastral.construccion.help",
            ),
            _SubField(
                "vigor",
                RowPartValueType.YEAR,
                False,
                "application.user_profile.row_parts.field.valor_catastral.vigor.label",
                "application.user_profile.row_parts.field.valor_catastral.vigor.help",
            ),
        ),
        RowPartKind.MEJORA: (
            _SubField(
                "fecha",
                RowPartValueType.DATE,
                True,
                "application.user_profile.row_parts.field.mejora.fecha.label",
                "application.user_profile.row_parts.field.mejora.fecha.help",
            ),
            _SubField(
                "importe",
                RowPartValueType.AMOUNT,
                True,
                "application.user_profile.row_parts.field.mejora.importe.label",
                "application.user_profile.row_parts.field.mejora.importe.help",
            ),
        ),
        RowPartKind.INQUILINO: (
            _SubField(
                "nif",
                RowPartValueType.TAX_ID,
                True,
                "application.user_profile.row_parts.field.inquilino.nif.label",
                "application.user_profile.row_parts.field.inquilino.nif.help",
            ),
            _SubField(
                "franja_edad",
                RowPartValueType.CHOICE,
                True,
                "application.user_profile.row_parts.field.inquilino.franja_edad.label",
                "application.user_profile.row_parts.field.inquilino.franja_edad.help",
            ),
            _SubField(
                "extranjero",
                RowPartValueType.BOOLEAN,
                True,
                "application.user_profile.row_parts.field.inquilino.extranjero.label",
                "application.user_profile.row_parts.field.inquilino.extranjero.help",
            ),
        ),
    }
)


def _require_total_tables() -> None:
    if set(_KIND_WORDS_LOCALE_KEYS) != set(RowPartKind) or set(_SUB_FIELDS_LOCALE_KEYS) != set(RowPartKind):
        raise ValueError("every part kind needs its words and its sub-fields")
    if set(_USO_TIPO_WORDS_LOCALE_KEYS) != set(UsoInmuebleTipo) or set(TENANT_BAND_WORDS_LOCALE_KEYS) != set(
        InquilinoEdad
    ):
        raise ValueError("every part token needs its words")


_require_total_tables()


def compound_part_kind(section_key: str, field_key: str) -> RowPartKind | None:
    """Return which typed sub-row a row field packs, or ``None`` for a field that is not packed."""
    return _COMPOUND.get((section_key, field_key))


def _choices(kind: RowPartKind, key: str) -> tuple[ProfileFieldPartChoice, ...]:
    if kind is RowPartKind.USO and key == "tipo":
        return tuple(
            ProfileFieldPartChoice(value=tipo.value, label=tr(_USO_TIPO_WORDS_LOCALE_KEYS[tipo]))
            for tipo in UsoInmuebleTipo
        )
    if kind is RowPartKind.INQUILINO and key == "franja_edad":
        return tuple(
            ProfileFieldPartChoice(value=band.value, label=tr(TENANT_BAND_WORDS_LOCALE_KEYS[band]))
            for band in InquilinoEdad
        )
    if kind is RowPartKind.INQUILINO and key == "extranjero":
        return (
            ProfileFieldPartChoice(value="true", label=tr("flows.confirm.yes")),
            ProfileFieldPartChoice(value="false", label=tr("flows.confirm.no")),
        )
    return ()


def _spec(kind: RowPartKind, *, invalid: bool) -> ProfileFieldPartsSpec:
    return ProfileFieldPartsSpec(
        part_kind=kind,
        part_words=tr(_KIND_WORDS_LOCALE_KEYS[kind]),
        sub_fields=tuple(
            ProfileFieldPartField(
                key=sub.key,
                label=tr(sub.label_key),
                help=tr(sub.help_key),
                value_type=sub.value_type,
                required=sub.required,
                choices=_choices(kind, sub.key),
            )
            for sub in _SUB_FIELDS_LOCALE_KEYS[kind]
        ),
        words_language=served_words_language(),
        invalid=invalid,
        invalid_words=tr(INVALID_LOCALE_KEY) if invalid else None,
    )


def _served_parts(kind: RowPartKind, raw: str, *, leaf: str) -> tuple[ProfileFieldPart, ...]:
    """Read ``raw`` with the canonical parser and shape each record as a served part."""
    language = served_words_language()
    match kind:
        case RowPartKind.USO:
            return tuple(
                ProfileFieldUsoPart(
                    tipo=uso.tipo.value,
                    desde=uso.desde.isoformat(),
                    hasta=None if uso.hasta is None else uso.hasta.isoformat(),
                    tipo_words=tr(_USO_TIPO_WORDS_LOCALE_KEYS[uso.tipo]),
                    tipo_words_language=language,
                )
                for uso in parse_usos(raw, leaf=leaf)
            )
        case RowPartKind.VALOR_CATASTRAL:
            return tuple(
                ProfileRowValorCatastralValues(
                    year=valor.year,
                    total=money_text(valor.total),
                    construccion=money_text(valor.construccion),
                    vigor=valor.vigor,
                )
                for valor in parse_valores_catastrales(raw, leaf=leaf)
            )
        case RowPartKind.MEJORA:
            return tuple(
                ProfileRowMejoraValues(fecha=mejora.fecha.isoformat(), importe=money_text(mejora.importe))
                for mejora in parse_mejoras(raw, leaf=leaf)
            )
        case RowPartKind.INQUILINO:
            return tuple(
                ProfileFieldInquilinoPart(
                    nif=inquilino.nif,
                    franja_edad=inquilino.franja_edad.value,
                    extranjero=inquilino.extranjero,
                    franja_edad_words=tr(TENANT_BAND_WORDS_LOCALE_KEYS[inquilino.franja_edad]),
                    franja_edad_words_language=language,
                )
                for inquilino in parse_inquilinos(raw, leaf=leaf)
            )


NOT_PACKED: Final = FieldParts(parts=None, spec=None)
"""What a field that is not packed, or whose value is masked, serves."""


def field_parts(section_key: str, field_key: str, raw: str | None, *, masked: bool = False) -> FieldParts:
    """Serve the parts of a packed field's stored text; a field that is not packed, or is masked, serves none.

    An unstated field has an empty list of parts. A value the canonical parser refuses has no
    parts and an invalid marker.
    """
    kind = compound_part_kind(section_key, field_key)
    if kind is None or masked:
        return NOT_PACKED
    if raw is None or not raw.strip():
        return FieldParts(parts=(), spec=_spec(kind, invalid=False))
    try:
        parts = _served_parts(kind, raw, leaf=field_key)
    except ProfileAnswerTypeError:
        return FieldParts(parts=None, spec=_spec(kind, invalid=True))
    return FieldParts(parts=parts, spec=_spec(kind, invalid=False))


def _refuse_part(message: str, *, field_key: str) -> ProfileSchemaValidationError:
    return ProfileSchemaValidationError(message, context={"field": field_key})


def _checked[PartT: BaseModel](
    parts: Sequence[ProfileRowPartInput], kind: type[PartT], *, leaf: str
) -> tuple[PartT, ...]:
    """Return ``parts`` as the one kind this field holds, refusing a part of another kind."""
    checked = tuple(part for part in parts if isinstance(part, kind))
    if len(checked) != len(parts):
        raise _refuse_part("a part of another kind cannot be stated for this field", field_key=leaf)
    return checked


def _pack_usos(parts: Sequence[ProfileRowPartInput], leaf: str) -> str:
    usos = _checked(parts, ProfileRowUsoValues, leaf=leaf)
    return serialise_usos(tuple(uso_from_entry(p.tipo, p.desde, p.hasta or "", leaf=leaf) for p in usos))


def _pack_valores(parts: Sequence[ProfileRowPartInput], leaf: str) -> str:
    valores = _checked(parts, ProfileRowValorCatastralValues, leaf=leaf)
    return serialise_valores_catastrales(
        tuple(
            valor_catastral_from_entry(
                str(p.year), p.total, p.construccion, "" if p.vigor is None else str(p.vigor), leaf=leaf
            )
            for p in valores
        )
    )


def _pack_mejoras(parts: Sequence[ProfileRowPartInput], leaf: str) -> str:
    mejoras = _checked(parts, ProfileRowMejoraValues, leaf=leaf)
    return serialise_mejoras(tuple(mejora_from_entry(p.fecha, p.importe, leaf=leaf) for p in mejoras))


def _pack_inquilinos(parts: Sequence[ProfileRowPartInput], leaf: str) -> str:
    inquilinos = _checked(parts, ProfileRowInquilinoValues, leaf=leaf)
    return serialise_inquilinos(
        tuple(inquilino_from_entry(p.nif, p.franja_edad, "si" if p.extranjero else "no", leaf=leaf) for p in inquilinos)
    )


_PACKERS: Final[Mapping[RowPartKind, Callable[[Sequence[ProfileRowPartInput], str], str]]] = MappingProxyType(
    {
        RowPartKind.USO: _pack_usos,
        RowPartKind.VALOR_CATASTRAL: _pack_valores,
        RowPartKind.MEJORA: _pack_mejoras,
        RowPartKind.INQUILINO: _pack_inquilinos,
    }
)


def packed_text_of_parts(section_key: str, field_key: str, parts: Sequence[ProfileRowPartInput]) -> str:
    """Render the stored text of a packed field from its structured parts, refusing what the text path refuses.

    The parts are judged one by one by the builders the text parser uses, so a part a text entry
    would refuse is refused with the same message, and the result is the one canonical stored form.
    An empty list renders empty text, which the row operations refuse as a blank value.
    """
    kind = compound_part_kind(section_key, field_key)
    if kind is None:
        raise _refuse_part("this field takes no structured parts", field_key=field_key)
    return _PACKERS[kind](parts, field_key)


__all__ = [
    "INVALID_LOCALE_KEY",
    "NOT_PACKED",
    "FieldParts",
    "ProfileFieldInquilinoPart",
    "ProfileFieldPart",
    "ProfileFieldPartChoice",
    "ProfileFieldPartField",
    "ProfileFieldPartsSpec",
    "ProfileFieldUsoPart",
    "ProfileRowInquilinoValues",
    "ProfileRowMejoraValues",
    "ProfileRowPartInput",
    "ProfileRowUsoValues",
    "ProfileRowValorCatastralValues",
    "RowPartKind",
    "RowPartValueType",
    "compound_part_kind",
    "field_parts",
    "packed_text_of_parts",
]
