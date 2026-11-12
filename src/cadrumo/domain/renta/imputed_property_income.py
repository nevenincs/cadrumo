"""Imputed income from urban property neither let nor used (LIRPF art. 85).

Pure calculation of the per-property imputed amount that feeds the Modelo 100
property section (casillas 0083-0089). Every rate, fraction and look-back
count is supplied by the caller from the pinned registry; this module owns
only the arithmetic and the refusal discipline.

Rules implemented (law: art. 85 LIRPF; practical guidance: Manual Renta 2025):

- Only urban property (and rustic property with constructions that are not
  indispensable for farming) imputes; the primary home, unbuilt land,
  property under construction or unusable for urban-planning reasons, property
  tied to an economic activity and let property do not (art. 85.1).
- Base is the cadastral value; when the property has none, or it was not
  notified to the holder, the base is a fraction of the higher of the
  acquisition value and the value checked by the administration (art. 85.1).
- The reduced rate applies when a general collective cadastral valuation took
  effect in the period or the previous look-back periods, and always on the
  fallback base (art. 85.1).
- The amount is prorated by the days in the period the property was held and
  available, and by the holder's share (art. 85.1, 85.2 and art. 11.3).
- With a real right of enjoyment, the holder of the right imputes the income
  the owner would have; the bare owner imputes none (art. 85.2).
- A family dwelling whose use a court assigned to the ex-spouse and children
  does not impute; neither does a property occupied illegally once the
  eviction procedure has begun (Manual Renta 2025, regimen de imputacion).

An unstated fact is a typed refusal, never a zero.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from enum import StrEnum

from ...core.money.rounding import round_to_cents

__all__ = [
    "BaseOrigen",
    "ImputacionCalculada",
    "ImputacionNoImputable",
    "ImputacionRechazada",
    "InmuebleImputable",
    "IntervaloExcluyente",
    "MotivoNoImputable",
    "MotivoRechazo",
    "NaturalezaInmueble",
    "ParametrosImputacion",
    "ResultadoImputacion",
    "TipoIntervalo",
    "Titularidad",
    "calcular_imputacion_inmueble",
]

_HUNDRED = Decimal(100)


class Titularidad(StrEnum):
    """Kind of right the taxpayer holds over the property."""

    PLENO_DOMINIO = "pleno_dominio"
    NUDA_PROPIEDAD = "nuda_propiedad"
    USUFRUCTO = "usufructo"
    PLENO_DOMINIO_Y_USUFRUCTO = "pleno_dominio_y_usufructo"


class NaturalezaInmueble(StrEnum):
    """Cadastral nature of the property."""

    URBANA = "urbana"
    RUSTICA = "rustica"


class TipoIntervalo(StrEnum):
    """Kinds of date interval during which no income is imputed."""

    ARRENDADO = "arrendado"
    VIVIENDA_HABITUAL = "vivienda_habitual"
    ACTIVIDAD_ECONOMICA = "actividad_economica"
    EN_CONSTRUCCION_O_NO_USABLE = "en_construccion_o_no_usable"
    VIVIENDA_FAMILIAR_JUDICIAL = "vivienda_familiar_judicial"
    OCUPACION_ILEGAL_DESAHUCIO = "ocupacion_ilegal_desahucio"


class BaseOrigen(StrEnum):
    """Where the imputation base came from."""

    VALOR_CATASTRAL = "valor_catastral"
    VALOR_ADQUISICION_O_COMPROBADO = "valor_adquisicion_o_comprobado"


class MotivoNoImputable(StrEnum):
    """Reason a property produces no imputed income."""

    RUSTICO = "rustico"
    NUDA_PROPIEDAD = "nuda_propiedad"
    SIN_DIAS_A_DISPOSICION = "sin_dias_a_disposicion"


class MotivoRechazo(StrEnum):
    """The missing or inconsistent fact that blocks a calculation."""

    NATURALEZA_NO_DECLARADA = "naturaleza_no_declarada"
    TITULARIDAD_NO_RESUELTA = "titularidad_no_resuelta"
    PARTICIPACION_NO_DECLARADA = "participacion_no_declarada"
    PARTICIPACION_FUERA_DE_RANGO = "participacion_fuera_de_rango"
    FECHA_ADQUISICION_NO_DECLARADA = "fecha_adquisicion_no_declarada"
    INTERVALO_INCOHERENTE = "intervalo_incoherente"
    BASE_NO_DETERMINABLE = "base_no_determinable"
    VALOR_NO_POSITIVO = "valor_no_positivo"


@dataclass(frozen=True, slots=True)
class IntervaloExcluyente:
    """Inclusive date range where the property does not impute (open end allowed)."""

    tipo: TipoIntervalo
    desde: date
    hasta: date | None = None


@dataclass(frozen=True, slots=True)
class InmuebleImputable:
    """The facts art. 85 needs about one property, as the caller states them.

    ``valor_catastral`` is the cadastral value for the period; ``None`` means
    the property has none. ``revision_colectiva_vigor`` is the date a general
    collective valuation took effect, ``None`` when there was none. A rustic
    property imputes only when ``rustico_con_construcciones_no_indispensables``
    is true.
    """

    titularidad: Titularidad | None
    porcentaje_propiedad: Decimal | None
    porcentaje_usufructo: Decimal | None
    naturaleza: NaturalezaInmueble | None
    fecha_adquisicion: date | None
    fecha_transmision: date | None = None
    valor_catastral: Decimal | None = None
    valor_catastral_no_notificado: bool = False
    revision_colectiva_vigor: date | None = None
    importe_adquisicion: Decimal | None = None
    valor_comprobado_administracion: Decimal | None = None
    intervalos: tuple[IntervaloExcluyente, ...] = ()
    rustico_con_construcciones_no_indispensables: bool = False


@dataclass(frozen=True, slots=True)
class ParametrosImputacion:
    """Filing window and registry-supplied parameters (percent units, e.g. 2 for 2%).

    ``revision_vigor_desde`` is an optional caller-supplied earliest effective
    date that also qualifies a collective valuation for the reduced rate, for
    years where guidance states a fixed date instead of the ten-period rule.
    """

    periodo_desde: date
    periodo_hasta: date
    porcentaje_general: Decimal
    porcentaje_reducido: Decimal
    porcentaje_base_sin_valor_catastral: Decimal
    periodos_revision_previos: int
    revision_vigor_desde: date | None = None

    def __post_init__(self) -> None:
        """Reject an inverted filing window."""
        if self.periodo_desde > self.periodo_hasta:
            msg = "periodo_desde must not be after periodo_hasta"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class ImputacionCalculada:
    """A computed imputation for one property."""

    dias_imputables: int
    dias_periodo: int
    base: Decimal
    base_origen: BaseOrigen
    porcentaje_aplicado: Decimal
    participacion: Decimal
    importe: Decimal


@dataclass(frozen=True, slots=True)
class ImputacionNoImputable:
    """The property legitimately produces no imputed income."""

    motivo: MotivoNoImputable


@dataclass(frozen=True, slots=True)
class ImputacionRechazada:
    """A required fact is missing or inconsistent; no amount is produced."""

    motivo: MotivoRechazo


ResultadoImputacion = ImputacionCalculada | ImputacionNoImputable | ImputacionRechazada


def _participacion(inmueble: InmuebleImputable) -> Decimal | MotivoRechazo:
    """Return the holder's share in percent, or the reason it is unusable."""
    if inmueble.titularidad is Titularidad.PLENO_DOMINIO:
        valor = inmueble.porcentaje_propiedad
    else:
        valor = inmueble.porcentaje_usufructo
    if valor is None:
        return MotivoRechazo.PARTICIPACION_NO_DECLARADA
    if valor <= 0 or valor > _HUNDRED:
        return MotivoRechazo.PARTICIPACION_FUERA_DE_RANGO
    return valor


def _dias_inclusivos(desde: date, hasta: date) -> int:
    return (hasta - desde).days + 1


def _dias_a_disposicion(
    ventana: tuple[date, date],
    intervalos: tuple[IntervaloExcluyente, ...],
) -> int | None:
    """Count window days not covered by any interval; ``None`` when one is inverted."""
    inicio, fin = ventana
    recortes: list[tuple[date, date]] = []
    for intervalo in intervalos:
        if intervalo.hasta is not None and intervalo.hasta < intervalo.desde:
            return None
        lo = max(intervalo.desde, inicio)
        hi = fin if intervalo.hasta is None else min(intervalo.hasta, fin)
        if lo <= hi:
            recortes.append((lo, hi))
    recortes.sort()
    cubiertos = 0
    corte = inicio - timedelta(days=1)
    for lo, hi in recortes:
        lo = max(lo, corte + timedelta(days=1))
        if lo <= hi:
            cubiertos += _dias_inclusivos(lo, hi)
            corte = hi
    return _dias_inclusivos(inicio, fin) - cubiertos


def _revision_aplicable(inmueble: InmuebleImputable, parametros: ParametrosImputacion) -> bool:
    vigor = inmueble.revision_colectiva_vigor
    if vigor is None or vigor > parametros.periodo_hasta:
        return False
    limite_periodos = parametros.periodo_hasta.year - parametros.periodos_revision_previos
    if vigor.year >= limite_periodos:
        return True
    return parametros.revision_vigor_desde is not None and vigor >= parametros.revision_vigor_desde


def _base_y_porcentaje(
    inmueble: InmuebleImputable,
    parametros: ParametrosImputacion,
) -> tuple[Decimal, BaseOrigen, Decimal] | MotivoRechazo:
    """Choose the imputation base and rate (art. 85.1)."""
    catastral = inmueble.valor_catastral
    if catastral is not None and not inmueble.valor_catastral_no_notificado:
        if catastral <= 0:
            return MotivoRechazo.VALOR_NO_POSITIVO
        reducido = _revision_aplicable(inmueble, parametros)
        porcentaje = parametros.porcentaje_reducido if reducido else parametros.porcentaje_general
        return catastral, BaseOrigen.VALOR_CATASTRAL, porcentaje
    candidatos = [
        valor for valor in (inmueble.importe_adquisicion, inmueble.valor_comprobado_administracion) if valor is not None
    ]
    if not candidatos:
        return MotivoRechazo.BASE_NO_DETERMINABLE
    mayor = max(candidatos)
    if mayor <= 0:
        return MotivoRechazo.VALOR_NO_POSITIVO
    base = mayor * parametros.porcentaje_base_sin_valor_catastral / _HUNDRED
    return base, BaseOrigen.VALOR_ADQUISICION_O_COMPROBADO, parametros.porcentaje_reducido


def _preliminar(inmueble: InmuebleImputable) -> ImputacionNoImputable | ImputacionRechazada | None:
    """Apply the nature and title gates that precede any arithmetic."""
    if inmueble.naturaleza is None:
        return ImputacionRechazada(MotivoRechazo.NATURALEZA_NO_DECLARADA)
    if inmueble.naturaleza is NaturalezaInmueble.RUSTICA and not inmueble.rustico_con_construcciones_no_indispensables:
        return ImputacionNoImputable(MotivoNoImputable.RUSTICO)
    if inmueble.titularidad is Titularidad.NUDA_PROPIEDAD:
        return ImputacionNoImputable(MotivoNoImputable.NUDA_PROPIEDAD)
    if inmueble.titularidad is None or inmueble.titularidad is Titularidad.PLENO_DOMINIO_Y_USUFRUCTO:
        return ImputacionRechazada(MotivoRechazo.TITULARIDAD_NO_RESUELTA)
    if inmueble.fecha_adquisicion is None:
        return ImputacionRechazada(MotivoRechazo.FECHA_ADQUISICION_NO_DECLARADA)
    return None


def _dias_de_titularidad(
    inmueble: InmuebleImputable,
    parametros: ParametrosImputacion,
) -> int | ImputacionNoImputable | ImputacionRechazada:
    """Count held-and-available days in the window, or explain why none."""
    adquisicion = inmueble.fecha_adquisicion
    if adquisicion is None:  # unreachable after _preliminar; keeps the type narrow
        return ImputacionRechazada(MotivoRechazo.FECHA_ADQUISICION_NO_DECLARADA)
    transmision = inmueble.fecha_transmision
    if transmision is not None and transmision < adquisicion:
        return ImputacionRechazada(MotivoRechazo.INTERVALO_INCOHERENTE)
    inicio = max(parametros.periodo_desde, adquisicion)
    fin = parametros.periodo_hasta if transmision is None else min(parametros.periodo_hasta, transmision)
    if inicio > fin:
        return ImputacionNoImputable(MotivoNoImputable.SIN_DIAS_A_DISPOSICION)
    dias = _dias_a_disposicion((inicio, fin), inmueble.intervalos)
    if dias is None:
        return ImputacionRechazada(MotivoRechazo.INTERVALO_INCOHERENTE)
    if dias == 0:
        return ImputacionNoImputable(MotivoNoImputable.SIN_DIAS_A_DISPOSICION)
    return dias


def calcular_imputacion_inmueble(
    inmueble: InmuebleImputable,
    parametros: ParametrosImputacion,
) -> ResultadoImputacion:
    """Compute the art. 85 imputed income of one property for the filing window.

    Ownership counts from the acquisition date through the transmission date,
    both inclusive. The day denominator is the number of days in the window, so
    leap years follow date arithmetic.
    """
    previo = _preliminar(inmueble)
    if previo is not None:
        return previo
    participacion = _participacion(inmueble)
    if isinstance(participacion, MotivoRechazo):
        return ImputacionRechazada(participacion)
    dias = _dias_de_titularidad(inmueble, parametros)
    if not isinstance(dias, int):
        return dias
    elegido = _base_y_porcentaje(inmueble, parametros)
    if isinstance(elegido, MotivoRechazo):
        return ImputacionRechazada(elegido)
    base, origen, porcentaje = elegido
    dias_periodo = _dias_inclusivos(parametros.periodo_desde, parametros.periodo_hasta)
    importe = round_to_cents(base * porcentaje / _HUNDRED * dias / dias_periodo * participacion / _HUNDRED)
    return ImputacionCalculada(
        dias_imputables=dias,
        dias_periodo=dias_periodo,
        base=base,
        base_origen=origen,
        porcentaje_aplicado=porcentaje,
        participacion=participacion,
        importe=importe,
    )
