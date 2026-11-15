"""Read the Modelo 840 facts of the declared activity from the stored profile.

One Modelo 840 declares one activity. The activity is the one the stored IAE premises
and Apartado VI A lines name; when none names one, it is the one activity row that
states a fact the declaration prints. Facts naming more than one activity are refused
rather than mixed onto one declaration.

The Anexo "Relación de locales" lists the premises where the declared activity is
exercised. A local afecto indirectamente is declared in Apartado V, which holds one
local. Apartado VI C "Local (Cuota municipal)" states the Regla 14 surface classes of
one local: under Regla 10.ª 3 of the IAE Instrucción an activity exercised in several
locales pays a cuota mínima municipal for each, so the surface classes of two exercised
locales are refused rather than added together. Regla 14.ª 1.F) a) takes the surface of
the locales where the activity is exercised, so a class stated for an indirect local is
not printed there.

Every value is a stored fact; an unstated one stays absent and is never zeroed.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from ...domain.contribuyente.iae_local_facts import (
    IAE_ELEMENTO_TRIBUTARIO_SECTION,
    IAE_LOCAL_SECTION,
    IAE_LOCAL_SUPERFICIE_SECTION,
    iae_elementos_from_facts,
    iae_locales_from_facts,
    iae_superficies_from_facts,
)
from ...domain.contribuyente.iae_local_record import (
    IaeElementoTributarioRecord,
    IaeLocalAfectacion,
    IaeLocalRecord,
    IaeLocalSuperficieRecord,
)
from ...domain.contribuyente.inmueble_facts import rows_from_facts
from ...domain.modelos.work_unit import WorkUnit
from ..filing.producer_snapshot_m840 import (
    Modelo840ElementoLinea,
    Modelo840LocalRow,
    Modelo840ProfileFacts,
    Modelo840SuperficieClase,
)
from .action_errors import ModeloProfileReadinessError
from .lifecycle_view_refusal_doors import profile_facts_verdict
from .profile_readiness_gate import open_profile_path_step

_ACTIVITIES_SECTION: Final = "activities"
_DELEGACION_PATH: Final = "censo.aeat_delegacion_code"
_ADMINISTRACION_CODE_PATH: Final = "censo.aeat_administracion_code"
_ADMINISTRACION_NAME_PATH: Final = "censo.aeat_administracion_name"
_FISCAL_MUNICIPIO_PATH: Final = "contact.fiscal_address_municipality_name"

_PROVINCIA_LEAF: Final = "cuota_provincial_province_code"
_MUNICIPIO_LEAF: Final = "municipality_name"
_MAQUINAS_A_LEAF: Final = "maquinas_recreativas_tipo_a"
_MAQUINAS_B_LEAF: Final = "maquinas_recreativas_tipo_b"
_EXPOSITORES_LEAF: Final = "expositores_autoventa"
#: The activity-row leaves a Modelo 840 prints from the stored profile.
_ACTIVITY_LEAVES: Final = frozenset(
    {_PROVINCIA_LEAF, _MUNICIPIO_LEAF, _MAQUINAS_A_LEAF, _MAQUINAS_B_LEAF, _EXPOSITORES_LEAF}
)

#: DR840 widths: Delegación "Tabla" of two, Administración "3 Cod+20 Descrip", Municipio 30,
#: provincia "Tabla" of two, and the seven-digit "Número" of Apartado VI B.
_DELEGACION_DIGITS: Final = 2
_ADMINISTRACION_DIGITS: Final = 3
_PROVINCIA_DIGITS: Final = 2
_UNITS_DIGITS: Final = 7
_UNITS: Final = re.compile(rf"^\d{{1,{_UNITS_DIGITS}}}$")
_ADMINISTRACION_NAME_WIDTH: Final = 20
_MUNICIPIO_WIDTH: Final = 30

#: This module reads the facts of one modelo; its refusals name it.
_MODELO: Final = "840"
_APARTADO_V: Final = "V"
_APARTADO_VI_C: Final = "VI C"
_NO_ROW: Final[Mapping[str, str]] = MappingProxyType[str, str]({})


def modelo_840_profile_facts(*, work_unit: WorkUnit, path_values: Mapping[str, object]) -> Modelo840ProfileFacts:
    """Build the Modelo 840 facts of the declared activity; the Anexo premises keep stored order.

    ``path_values`` is the profile in force, keyed by canonical schema path.

    Raises:
        ModeloProfileReadinessError: When the facts name more than one activity, when
            Apartado V or VI C would have to describe more than one local, or when a stored
            fact does not have the shape DR840 prints.
    """
    locales = iae_locales_from_facts(path_values)
    elementos = iae_elementos_from_facts(path_values)
    activity_rows = rows_from_facts(_ACTIVITIES_SECTION, path_values)
    activity = _declared_activity(work_unit, locales, elementos, activity_rows)
    exercised = _activity_locales(locales, activity, IaeLocalAfectacion.EJERCICIO)
    indirect = _activity_locales(locales, activity, IaeLocalAfectacion.INDIRECTA)
    row: Mapping[str, str] = activity_rows.get(activity, _NO_ROW) if activity is not None else _NO_ROW
    return Modelo840ProfileFacts(
        local_rows=tuple(_row(local) for local in exercised),
        delegacion_codigo=_code(path_values, _DELEGACION_PATH, _DELEGACION_DIGITS, field=_DELEGACION_PATH),
        administracion_codigo=_code(
            path_values, _ADMINISTRACION_CODE_PATH, _ADMINISTRACION_DIGITS, field=_ADMINISTRACION_CODE_PATH
        ),
        administracion_nombre=_text(
            path_values, _ADMINISTRACION_NAME_PATH, _ADMINISTRACION_NAME_WIDTH, field=_ADMINISTRACION_NAME_PATH
        ),
        sujeto_pasivo_municipio=_text(
            path_values, _FISCAL_MUNICIPIO_PATH, _MUNICIPIO_WIDTH, field=_FISCAL_MUNICIPIO_PATH
        ),
        actividad_provincia_codigo=_code(
            row, _PROVINCIA_LEAF, _PROVINCIA_DIGITS, field=_activity_path(_PROVINCIA_LEAF)
        ),
        actividad_municipio=_text(row, _MUNICIPIO_LEAF, _MUNICIPIO_WIDTH, field=_activity_path(_MUNICIPIO_LEAF)),
        local_indirecto_municipio=_local_indirecto_municipio(work_unit, activity, indirect),
        elementos=tuple(_elemento(elemento) for elemento in elementos if elemento.actividad == activity),
        maquinas_tipo_a=_units(row, _MAQUINAS_A_LEAF),
        maquinas_tipo_b=_units(row, _MAQUINAS_B_LEAF),
        expositores_autoventa=_units(row, _EXPOSITORES_LEAF),
        superficies=_superficies(work_unit, activity, exercised, iae_superficies_from_facts(path_values)),
    )


def _activity_path(leaf: str) -> str:
    return f"{_ACTIVITIES_SECTION}.{leaf}"


def _stated(values: Mapping[str, object], key: str) -> str | None:
    """The stored text of ``key``; an absent or cleared fact states nothing."""
    raw = values.get(key)
    text = "" if raw is None else str(raw)
    return text or None


def _refuse(reason: str, *, field: str, **shape: int) -> ModeloProfileReadinessError:
    """Refuse a stored fact DR840 cannot print, offering the profile detail that states it."""
    return ModeloProfileReadinessError(
        translated_message=f"application.modelo.errors.{reason}",
        context={
            "modelo": _MODELO,
            "reason": reason,
            "key": field,
            "profile_section": field.partition(".")[0],
            "profile_path": field,
            "profile_requirements": field,
            **{name: str(value) for name, value in shape.items()},
        },
        profile_precondition_verdict=profile_facts_verdict((field,), modelo=_MODELO),
        next_step=open_profile_path_step(field),
    )


def _code(values: Mapping[str, object], key: str, digits: int, *, field: str) -> str | None:
    value = _stated(values, key)
    if value is not None and not (len(value) == digits and value.isascii() and value.isdigit()):
        raise _refuse("m840_fact_code_digits", field=field, digits=digits)
    return value


def _text(values: Mapping[str, object], key: str, width: int, *, field: str) -> str | None:
    value = _stated(values, key)
    if value is not None and (not value.strip() or len(value) > width):
        raise _refuse("m840_fact_text_width", field=field, width=width)
    return value


def _units(row: Mapping[str, str], leaf: str) -> int | None:
    value = _stated(row, leaf)
    if value is None:
        return None
    if not _UNITS.fullmatch(value):
        raise _refuse("m840_fact_units", field=_activity_path(leaf), digits=_UNITS_DIGITS)
    return int(value)


def _declared_activity(
    work_unit: WorkUnit,
    locales: tuple[IaeLocalRecord, ...],
    elementos: tuple[IaeElementoTributarioRecord, ...],
    activity_rows: Mapping[int, Mapping[str, str]],
) -> int | None:
    """The one activity the stored Modelo 840 facts name, or ``None`` when none does."""
    named = _named_activities(locales, elementos, activity_rows)
    activities = sorted({activity for ids in named.values() for activity in ids})
    if len(activities) > 1:
        raise _activities_ambiguous(work_unit, activities, sections=[section for section, ids in named.items() if ids])
    return activities[0] if activities else None


def _named_activities(
    locales: tuple[IaeLocalRecord, ...],
    elementos: tuple[IaeElementoTributarioRecord, ...],
    activity_rows: Mapping[int, Mapping[str, str]],
) -> dict[str, set[int]]:
    """The activities each section names; the activity rows answer only when no IAE row names one."""
    named: dict[str, set[int]] = {
        IAE_LOCAL_SECTION: {local.actividad for local in locales},
        IAE_ELEMENTO_TRIBUTARIO_SECTION: {elemento.actividad for elemento in elementos},
    }
    if any(named.values()):
        return named
    return {_ACTIVITIES_SECTION: {row for row, leaves in activity_rows.items() if _ACTIVITY_LEAVES & leaves.keys()}}


def _activity_locales(
    locales: tuple[IaeLocalRecord, ...], activity: int | None, afectacion: IaeLocalAfectacion
) -> tuple[IaeLocalRecord, ...]:
    return tuple(
        sorted(
            (local for local in locales if local.actividad == activity and local.afectacion is afectacion),
            key=_clave,
        )
    )


def _clave(local: IaeLocalRecord) -> int:
    return local.clave


def _row(local: IaeLocalRecord) -> Modelo840LocalRow:
    return Modelo840LocalRow(
        sg_tabla=local.via_sg,
        nombre_via=local.via_nombre,
        numero=local.numero,
        km=local.km,
        escalera=local.escalera,
        piso=local.piso,
        puerta=local.puerta,
        codigo_postal=local.postcode,
        provincia_codigo=local.province_code,
        municipio_codigo=local.municipality_code,
        municipio_nombre=local.municipality_name,
        total=local.superficie_total,
        rectificada=local.superficie_rectificada,
        computable=local.superficie_computable,
    )


def _elemento(elemento: IaeElementoTributarioRecord) -> Modelo840ElementoLinea:
    return Modelo840ElementoLinea(
        linea=elemento.linea, codigo=elemento.code, descripcion=elemento.description, numero=elemento.numero
    )


def _local_indirecto_municipio(
    work_unit: WorkUnit, activity: int | None, indirect: tuple[IaeLocalRecord, ...]
) -> str | None:
    """Apartado V describes one local afecto indirectamente; two cannot share it."""
    if len(indirect) > 1:
        raise _local_ambiguous(
            work_unit,
            apartado=_APARTADO_V,
            activity=activity,
            locales=[local.clave for local in indirect],
            path=f"{IAE_LOCAL_SECTION}.afectacion",
        )
    return indirect[0].municipality_name if indirect else None


def _superficies(
    work_unit: WorkUnit,
    activity: int | None,
    exercised: tuple[IaeLocalRecord, ...],
    superficies: tuple[IaeLocalSuperficieRecord, ...],
) -> tuple[Modelo840SuperficieClase, ...]:
    """The Regla 14 classes of the one exercised local that states them."""
    claves = {local.clave for local in exercised}
    stated = [superficie for superficie in superficies if superficie.local in claves]
    locales = sorted({superficie.local for superficie in stated})
    if len(locales) > 1:
        raise _local_ambiguous(
            work_unit,
            apartado=_APARTADO_VI_C,
            activity=activity,
            locales=locales,
            path=f"{IAE_LOCAL_SUPERFICIE_SECTION}.local",
        )
    return tuple(
        Modelo840SuperficieClase(
            clase=superficie.clase,
            total=superficie.total,
            rectificada=superficie.rectificada,
            computable=superficie.computable,
        )
        for superficie in sorted(stated, key=lambda superficie: superficie.clase.value)
    )


def _work_unit_context(work_unit: WorkUnit) -> dict[str, object]:
    return {
        "modelo": str(work_unit.modelo),
        "filing_year": work_unit.filing_year,
        "period": work_unit.period.registry_token,
    }


def _activities_ambiguous(
    work_unit: WorkUnit, activities: list[int], *, sections: list[str]
) -> ModeloProfileReadinessError:
    paths = tuple(
        f"{section}.description" if section == _ACTIVITIES_SECTION else f"{section}.actividad" for section in sections
    )
    modelo = str(work_unit.modelo)
    return ModeloProfileReadinessError(
        translated_message="application.modelo.errors.m840_anexo_activities_ambiguous",
        context={
            **_work_unit_context(work_unit),
            "reason": "m840_anexo_activities_ambiguous",
            "profile_section": ", ".join(sections),
            "profile_path": paths[0],
            "profile_requirements": ", ".join(paths),
            "activities": ", ".join(str(activity) for activity in activities),
        },
        profile_precondition_verdict=profile_facts_verdict(paths, modelo=modelo),
        next_step=open_profile_path_step(paths[0]),
    )


def _local_ambiguous(
    work_unit: WorkUnit, *, apartado: str, activity: int | None, locales: list[int], path: str
) -> ModeloProfileReadinessError:
    modelo = str(work_unit.modelo)
    section = path.partition(".")[0]
    return ModeloProfileReadinessError(
        translated_message="application.modelo.errors.m840_apartado_locales_ambiguous",
        context={
            **_work_unit_context(work_unit),
            "reason": "m840_apartado_locales_ambiguous",
            "apartado": apartado,
            "activity": "" if activity is None else str(activity),
            "locales": ", ".join(str(local) for local in locales),
            "profile_section": section,
            "profile_path": path,
            "profile_requirements": path,
        },
        profile_precondition_verdict=profile_facts_verdict((path,), modelo=modelo),
        next_step=open_profile_path_step(path),
    )


__all__ = ["modelo_840_profile_facts"]
