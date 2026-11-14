"""Read the Modelo 840 Anexo premises from the stored IAE locales.

The Anexo "Relación de locales" lists the premises where the declared activity is
exercised; a local afecto indirectamente is declared in Apartado V, not here. One
Modelo 840 declares one activity, so when the exercised premises serve more than one
stored activity the export cannot tell which declaration they belong to and refuses
rather than mixing them onto one Anexo.
"""

from __future__ import annotations

from collections.abc import Mapping

from ...domain.contribuyente.iae_local_facts import IAE_LOCAL_SECTION, iae_locales_from_facts
from ...domain.contribuyente.iae_local_record import IaeLocalAfectacion, IaeLocalRecord
from ...domain.modelos.work_unit import WorkUnit
from ..filing.producer_snapshot_m840 import Modelo840LocalRow, Modelo840ProfileFacts
from .action_errors import ModeloProfileReadinessError
from .lifecycle_view_refusal_doors import profile_facts_verdict
from .profile_readiness_gate import open_profile_path_step

_ACTIVITY_PATH = f"{IAE_LOCAL_SECTION}.actividad"


def modelo_840_profile_facts(*, work_unit: WorkUnit, path_values: Mapping[str, object]) -> Modelo840ProfileFacts:
    """Build the Anexo premises rows from the profile's exercised locales, in stored order.

    ``path_values`` is the profile in force, keyed by canonical schema path.

    Raises:
        ModeloProfileReadinessError: When the exercised premises serve more than one activity.
    """
    locales = tuple(
        local for local in iae_locales_from_facts(path_values) if local.afectacion is IaeLocalAfectacion.EJERCICIO
    )
    activities = sorted({local.actividad for local in locales})
    if len(activities) > 1:
        raise _activities_ambiguous(work_unit, activities)
    return Modelo840ProfileFacts(local_rows=tuple(_row(local) for local in sorted(locales, key=_clave)))


def _clave(local: IaeLocalRecord) -> int:
    return local.clave


def _row(local: IaeLocalRecord) -> Modelo840LocalRow:
    return Modelo840LocalRow(
        sg_tabla=local.via_sg,
        nombre_via=local.via_nombre,
        numero=None if local.numero is None else str(local.numero),
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


def _activities_ambiguous(work_unit: WorkUnit, activities: list[int]) -> ModeloProfileReadinessError:
    modelo = str(work_unit.modelo)
    return ModeloProfileReadinessError(
        translated_message="application.modelo.errors.m840_anexo_activities_ambiguous",
        context={
            "modelo": modelo,
            "filing_year": work_unit.filing_year,
            "period": work_unit.period.registry_token,
            "reason": "m840_anexo_activities_ambiguous",
            "profile_section": IAE_LOCAL_SECTION,
            "profile_path": _ACTIVITY_PATH,
            "profile_requirements": _ACTIVITY_PATH,
            "activities": ", ".join(str(activity) for activity in activities),
        },
        profile_precondition_verdict=profile_facts_verdict((_ACTIVITY_PATH,), modelo=modelo),
        next_step=open_profile_path_step(_ACTIVITY_PATH),
    )


__all__ = ["modelo_840_profile_facts"]
