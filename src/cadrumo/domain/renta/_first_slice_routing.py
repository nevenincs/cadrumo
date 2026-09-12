"""First-slice Modelo 100 expense routing table.

This is the BOE-prescribed routing table from :class:`SpendingCategory`
to the Modelo 100 *estimacion directa* expense casilla that receives
the deductible amount for that category.

The mapping is canonical: it stores the registry ``casilla.id`` values
for the Modelo 100 instructions. Every consumer (the renta-deductibility
observation validator, the renta-ledger aggregator, the snapshot-time
referential-integrity gate) reads from the single
:data:`FIRST_SLICE_EXPENSE_CASILLAS` constant declared here.

The companion :mod:`.first_slice_routing_integrity` module registers a
snapshot-time referential-integrity check, but it validates a NARROWER
claim than "every casilla this table mentions exists on every
revision": casilla ids are added, split, and renumbered across Modelo
100 revisions (e.g. "Aportaciones a mutualidades alternativas" shares
casilla ``0186`` with Seguridad Social contributions on the 2020-2022
revisions but gets its own dedicated casilla ``0195`` from 2023
onward), so a target this table names may legitimately be absent from
an older revision that predates the split. The registered check
instead asserts that every casilla a REVISION'S OWN
``ledger_renta_gastos_estimacion_directa_aggregation`` bindings target actually exists on
that same revision -- see
:func:`cadrumo.domain.calculations.registry.renta_first_slice_binding_target_casillas`.
A regression in either the registry or a revision's own bindings
surfaces as a typed ``RegistryValidationError`` at snapshot
construction.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date
from enum import Enum
from typing import TYPE_CHECKING

from ...core.casilla_id import CasillaId, validated_casilla_id
from ...domain.calculations.registry.authority import bundled_authority
from ...domain.calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ...domain.calculations.registry.queries import RegistryQueryService
from ...domain.calculations.registry.schema_base import DateAxis
from ..categories.spending_category import SpendingCategory

FIRST_SLICE_EXPENSE_CASILLAS: Mapping[SpendingCategory, CasillaId] = {
    # -- casilla 0183: Otros consumos de explotacion --------------------
    SpendingCategory.SUMINISTROS_CLIENTE_DIRECTOS: validated_casilla_id(
        "0183",
        surface="FIRST_SLICE_EXPENSE_CASILLAS.SUMINISTROS_CLIENTE_DIRECTOS",
    ),
    # -- casilla 0186: Seguridad Social del titular de la actividad ------
    SpendingCategory.CUOTAS_AUTONOMOS_SS: validated_casilla_id(
        "0186",
        surface="FIRST_SLICE_EXPENSE_CASILLAS.CUOTAS_AUTONOMOS_SS",
    ),
    # -- casilla 0191: Gastos de manutencion del contribuyente -----------
    SpendingCategory.MANUTENCION_DIETAS_NACIONAL: validated_casilla_id(
        "0191",
        surface="FIRST_SLICE_EXPENSE_CASILLAS.MANUTENCION_DIETAS_NACIONAL",
    ),
    SpendingCategory.MANUTENCION_DIETAS_EXTRANJERO: validated_casilla_id(
        "0191",
        surface="FIRST_SLICE_EXPENSE_CASILLAS.MANUTENCION_DIETAS_EXTRANJERO",
    ),
    # -- casilla 0192: Arrendamientos y canones ---------------------------
    SpendingCategory.ARRENDAMIENTO_LOCAL: validated_casilla_id(
        "0192",
        surface="FIRST_SLICE_EXPENSE_CASILLAS.ARRENDAMIENTO_LOCAL",
    ),
    SpendingCategory.ARRENDAMIENTO_VIVIENDA_AFECTO: validated_casilla_id(
        "0192",
        surface="FIRST_SLICE_EXPENSE_CASILLAS.ARRENDAMIENTO_VIVIENDA_AFECTO",
    ),
    # -- casilla 0193: Reparaciones y conservacion -------------------------
    SpendingCategory.REPARACIONES_CONSERVACION: validated_casilla_id(
        "0193",
        surface="FIRST_SLICE_EXPENSE_CASILLAS.REPARACIONES_CONSERVACION",
    ),
    SpendingCategory.VEHICULO_MANTENIMIENTO: validated_casilla_id(
        "0193",
        surface="FIRST_SLICE_EXPENSE_CASILLAS.VEHICULO_MANTENIMIENTO",
    ),
    # -- casilla 0194: Suministros --------------------------------------
    # Two legally distinct populations share this box. Utilities of premises
    # used for the activity deduct in full: the immovable property where the
    # activity is carried on is afecto under art. 29.1.a), so its costs are
    # ordinary deductible expense under art. 28.1. Utilities of a DWELLING
    # only partly given over to the activity are governed instead by the
    # art. 30.2.5.a b) carve-out, which grants 30 % of the affected floor-area
    # proportion precisely because a vivienda habitual cannot be exclusively
    # affected. Routing a local's bills through a home-office category applies
    # an article that does not govern the taxpayer, so the two keep separate
    # members.
    SpendingCategory.SUMINISTROS_LOCAL_AFECTO: validated_casilla_id(
        "0194",
        surface="FIRST_SLICE_EXPENSE_CASILLAS.SUMINISTROS_LOCAL_AFECTO",
    ),
    SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ: validated_casilla_id(
        "0194",
        surface="FIRST_SLICE_EXPENSE_CASILLAS.SUMINISTROS_HOME_OFFICE_LUZ",
    ),
    SpendingCategory.SUMINISTROS_HOME_OFFICE_AGUA: validated_casilla_id(
        "0194",
        surface="FIRST_SLICE_EXPENSE_CASILLAS.SUMINISTROS_HOME_OFFICE_AGUA",
    ),
    SpendingCategory.SUMINISTROS_HOME_OFFICE_GAS: validated_casilla_id(
        "0194",
        surface="FIRST_SLICE_EXPENSE_CASILLAS.SUMINISTROS_HOME_OFFICE_GAS",
    ),
    SpendingCategory.SUMINISTROS_HOME_OFFICE_INTERNET: validated_casilla_id(
        "0194",
        surface="FIRST_SLICE_EXPENSE_CASILLAS.SUMINISTROS_HOME_OFFICE_INTERNET",
    ),
    SpendingCategory.TELEFONIA_FIJA: validated_casilla_id(
        "0194",
        surface="FIRST_SLICE_EXPENSE_CASILLAS.TELEFONIA_FIJA",
    ),
    # -- casilla 0195: Aportaciones a mutualidades alternativas ----------
    SpendingCategory.MUTUALIDAD_ALTERNATIVA: validated_casilla_id(
        "0195",
        surface="FIRST_SLICE_EXPENSE_CASILLAS.MUTUALIDAD_ALTERNATIVA",
    ),
    # -- casilla 0199: Servicios de profesionales independientes ----------
    SpendingCategory.ASESORIA_CONTABLE: validated_casilla_id(
        "0199",
        surface="FIRST_SLICE_EXPENSE_CASILLAS.ASESORIA_CONTABLE",
    ),
    SpendingCategory.ASESORIA_FISCAL: validated_casilla_id(
        "0199",
        surface="FIRST_SLICE_EXPENSE_CASILLAS.ASESORIA_FISCAL",
    ),
    SpendingCategory.ASESORIA_JURIDICA: validated_casilla_id(
        "0199",
        surface="FIRST_SLICE_EXPENSE_CASILLAS.ASESORIA_JURIDICA",
    ),
    SpendingCategory.MATERIAL_OFICINA: validated_casilla_id(
        "0199",
        surface="FIRST_SLICE_EXPENSE_CASILLAS.MATERIAL_OFICINA",
    ),
    SpendingCategory.SOFTWARE_SUSCRIPCION: validated_casilla_id(
        "0199",
        surface="FIRST_SLICE_EXPENSE_CASILLAS.SOFTWARE_SUSCRIPCION",
    ),
    SpendingCategory.TELEFONIA_MOVIL: validated_casilla_id(
        "0199",
        surface="FIRST_SLICE_EXPENSE_CASILLAS.TELEFONIA_MOVIL",
    ),
    SpendingCategory.PUBLICIDAD_MARKETING: validated_casilla_id(
        "0199",
        surface="FIRST_SLICE_EXPENSE_CASILLAS.PUBLICIDAD_MARKETING",
    ),
    SpendingCategory.SUBCONTRATACION: validated_casilla_id(
        "0199",
        surface="FIRST_SLICE_EXPENSE_CASILLAS.SUBCONTRATACION",
    ),
    # -- casilla 0200: Primas de seguros ----------------------------------
    SpendingCategory.SEGUROS_RESPONSABILIDAD_CIVIL: validated_casilla_id(
        "0200",
        surface="FIRST_SLICE_EXPENSE_CASILLAS.SEGUROS_RESPONSABILIDAD_CIVIL",
    ),
    SpendingCategory.SEGUROS_SALUD_AUTONOMO: validated_casilla_id(
        "0200",
        surface="FIRST_SLICE_EXPENSE_CASILLAS.SEGUROS_SALUD_AUTONOMO",
    ),
    SpendingCategory.VEHICULO_SEGURO: validated_casilla_id(
        "0200",
        surface="FIRST_SLICE_EXPENSE_CASILLAS.VEHICULO_SEGURO",
    ),
    # -- casilla 0202: Otros servicios exteriores -------------------------
    SpendingCategory.VEHICULO_COMBUSTIBLE: validated_casilla_id(
        "0202",
        surface="FIRST_SLICE_EXPENSE_CASILLAS.VEHICULO_COMBUSTIBLE",
    ),
    SpendingCategory.VEHICULO_PEAJE: validated_casilla_id(
        "0202",
        surface="FIRST_SLICE_EXPENSE_CASILLAS.VEHICULO_PEAJE",
    ),
    SpendingCategory.VEHICULO_PARKING: validated_casilla_id(
        "0202",
        surface="FIRST_SLICE_EXPENSE_CASILLAS.VEHICULO_PARKING",
    ),
    SpendingCategory.FORMACION_PROFESIONAL: validated_casilla_id(
        "0202",
        surface="FIRST_SLICE_EXPENSE_CASILLAS.FORMACION_PROFESIONAL",
    ),
    SpendingCategory.VIAJES_TRANSPORTE: validated_casilla_id(
        "0202",
        surface="FIRST_SLICE_EXPENSE_CASILLAS.VIAJES_TRANSPORTE",
    ),
    SpendingCategory.VIAJES_ALOJAMIENTO: validated_casilla_id(
        "0202",
        surface="FIRST_SLICE_EXPENSE_CASILLAS.VIAJES_ALOJAMIENTO",
    ),
    # -- casilla 0203: Gastos financieros ----------------------------------
    SpendingCategory.GASTOS_BANCARIOS: validated_casilla_id(
        "0203",
        surface="FIRST_SLICE_EXPENSE_CASILLAS.GASTOS_BANCARIOS",
    ),
    SpendingCategory.GASTOS_FINANCIEROS: validated_casilla_id(
        "0203",
        surface="FIRST_SLICE_EXPENSE_CASILLAS.GASTOS_FINANCIEROS",
    ),
    # -- casilla 0206: Otros tributos fiscalmente deducibles --------------
    SpendingCategory.IBI_LOCAL_AFECTO: validated_casilla_id(
        "0206",
        surface="FIRST_SLICE_EXPENSE_CASILLAS.IBI_LOCAL_AFECTO",
    ),
    SpendingCategory.IBI_VIVIENDA_AFECTO: validated_casilla_id(
        "0206",
        surface="FIRST_SLICE_EXPENSE_CASILLAS.IBI_VIVIENDA_AFECTO",
    ),
    SpendingCategory.TRIBUTOS_FISCALMENTE_DEDUCIBLES: validated_casilla_id(
        "0206",
        surface="FIRST_SLICE_EXPENSE_CASILLAS.TRIBUTOS_FISCALMENTE_DEDUCIBLES",
    ),
    # -- casilla 0208: Amortizacion del inmovilizado material -------------
    SpendingCategory.AMORTIZACION_VIVIENDA_AFECTO: validated_casilla_id(
        "0208",
        surface="FIRST_SLICE_EXPENSE_CASILLAS.AMORTIZACION_VIVIENDA_AFECTO",
    ),
    SpendingCategory.HARDWARE_AMORTIZABLE: validated_casilla_id(
        "0208",
        surface="FIRST_SLICE_EXPENSE_CASILLAS.HARDWARE_AMORTIZABLE",
    ),
    SpendingCategory.MOBILIARIO_AMORTIZABLE: validated_casilla_id(
        "0208",
        surface="FIRST_SLICE_EXPENSE_CASILLAS.MOBILIARIO_AMORTIZABLE",
    ),
    # -- casilla 0217: Otros conceptos fiscalmente deducibles -------------
    # (excepto provisiones) -- catch-all for deductible concepts with no
    # dedicated estimacion-directa box: professional membership dues and
    # comunidad-de-propietarios charges on an affected home are not
    # enumerated separately elsewhere on the form.
    SpendingCategory.CUOTAS_COLEGIALES: validated_casilla_id(
        "0217",
        surface="FIRST_SLICE_EXPENSE_CASILLAS.CUOTAS_COLEGIALES",
    ),
    SpendingCategory.COMUNIDAD_VIVIENDA_AFECTO: validated_casilla_id(
        "0217",
        surface="FIRST_SLICE_EXPENSE_CASILLAS.COMUNIDAD_VIVIENDA_AFECTO",
    ),
}
"""SpendingCategory -> Modelo 100 estimacion directa expense casilla.

Every :class:`SpendingCategory` member routes to a real Modelo 100
``estimacion_directa`` expense casilla; the table is total (see
:mod:`cadrumo.domain.renta.tests.test_first_slice_routing`), so no member
is silently unrouted (``no-silent-under-declaration``,
``aeat-calculation-aggregation``).
"""


if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import ValidatedRegistryAuthority


def resolve_first_slice_expense_routing(
    *,
    category_type: type[Enum],
    casilla_factory: Callable[[object], CasillaId],
    model_code: str,
    fact_id: str,
    effective_date: date,
    authority: ValidatedRegistryAuthority | None = None,
) -> dict[Enum, CasillaId]:
    """Resolve one dated routing map from the selected registry authority."""
    selected_authority = authority or bundled_authority()
    RegistryQueryService(selected_authority).describe_modelo(model_code, as_of=effective_date)
    resolved = selected_authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id=fact_id,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise TypeError("first-slice routing declaration must resolve as a mapping fact")

    routing: dict[Enum, CasillaId] = {}
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise TypeError("first-slice routing entries must be string-to-string")
        prefix, separator, member_name = entry.key.partition(".")
        if separator != "." or prefix != "selector":
            continue
        try:
            category = category_type[member_name]
        except KeyError as exc:
            raise ValueError(f"registry routing names unknown category member {member_name!r}") from exc
        if category in routing:
            raise ValueError(f"registry routing repeats category member {member_name!r}")
        routing[category] = casilla_factory(entry.value)

    expected = set(category_type)
    if set(routing) != expected:
        missing = sorted(member.name for member in expected - set(routing))
        extra = sorted(member.name for member in set(routing) - expected)
        raise ValueError(f"registry routing coverage mismatch; missing={missing!r}, extra={extra!r}")
    return routing


__all__ = ["FIRST_SLICE_EXPENSE_CASILLAS", "resolve_first_slice_expense_routing"]
