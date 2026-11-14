"""Forward migration of stored profile records onto the current profile schema.

Each bump that changed what a stored value MEANS carries its own transition,
and every version this build has ever migrated stays a supported stored
source, so a profile that was not opened across one release still opens across
two.

- Schema 7 reads the dated payer facts (Modelos 347, 720, 721) as three-state.
- Schema 8 reads the withholding, capital-income, intracommunity, Art. 109
  coverage, IVA enrolment, large-company and fiscal-residency facts the same
  way: an absent fact is unanswered, and a stated value is the answer the
  taxpayer gave.
- Schema 9 retires the year-keyed art. 23.2 reduction tier. The tier of the
  reduction is derived from the facts of each lease, and a stored tier cannot be
  converted into those facts, so the migration clears whatever value is stored
  and the operator is asked to record the leases.
- Schema 10 adds the LIS art. 40.3 election of the Modelo 202 as an optional
  fact. It changes no stored value, so its transition clears nothing; a
  schema-9 record that already carries the field is refused.
- Schema 11 adds the Modelo 200 page 002 relations: the administradores, the
  participations in and of the entity, its representatives, its secretary, its
  dependent entities, its permanent establishments abroad, its SICAV holdings
  and whether it has any of each. It only adds fields, so it clears nothing.
- Schema 12 retires the disability key stored on an ascendant row. The Modelo 100
  key is derived from the grade, the assistance and the judicial incapacity of
  the row, and a stored key 1 or 2 cannot be converted into a grade, so the
  migration clears every stored key and the operator is asked for the grade and
  both circumstances of that row.
- Schema 13 adds the facts the Modelo 202 page 01 states about the entity:
  the principal CNAE and its classification, the datos adicionales régimen
  marks, and the constitution date and ejercicio closing that fix the período
  impositivo. It changes no stored value, so its transition clears nothing; a schema-12 record
  that already carries one of the fields is refused.
- Schema 14 adds the date a property was first let, or that it never was, to the
  property record. It only adds fields, so it clears nothing: a stored value that
  predates the field was never stated, and the pending-expense statement of a
  property lives on the calculation revision, not on the profile.
- Schema 15 adds the Modelo 840 facts: the AEAT delegacion and administracion,
  the coded fiscal-address provincia and municipio, the activity's provincia,
  municipio, local afecto indirectamente and Apartado VI B counts, and the IAE
  premises, their Regla 14 surface classes and the Apartado VI A tax elements as
  repeatable rows. It only adds fields, so it clears nothing; a schema-14 record
  that already carries one of them is refused.

Before each of those bumps the setup wizard pre-answered the affected
questions and wrote its default as an ordinary ``manual_cli`` fact, so the
stored default cannot be told apart from a question nobody answered. The
migration therefore drops exactly the stored value each path defaulted to --
``false`` for a yes/no fact and the old default token for the one select --
keeps every other stored value, and leaves every other fact untouched. A
record stored at schema 6 crosses both transitions in one run and has both
sets of defaults dropped. The cleared paths travel with the migration as
typed data so the operator can be asked to answer them again.

Dropping a real answer that happened to equal the default is the accepted
cost: the two are indistinguishable in storage, and re-asking a question
already answered is recoverable while reading a default as an answer silently
decides an obligation.

The transform is pure and deterministic: the same stored facts and the same
stored version always yield the same kept facts and the same cleared paths,
and a current record is never passed through it.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from types import MappingProxyType
from typing import Final, Self

from pydantic import BaseModel, Field, model_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.models import STRICT_FROZEN_CONFIG
from .errors import UserProfileValidationError
from .schema import ProfileSchemaDefinition
from .values import UserProfileFact, UserProfileRecord, section_field_key

MIGRATED_PROFILE_SCHEMA_VERSION: Final[int] = 15
"""The profile schema version the migration writes."""

_UNPROVEN_FALSE: Final[bool] = False
"""The stored value a defaulted yes/no question left behind."""

_DEFAULTED_VALUES_FROM_V6: Final[Mapping[str, object]] = MappingProxyType(
    {
        "obligations.third_party_transactions_above_347_threshold": _UNPROVEN_FALSE,
        "obligations.bienes_extranjero_above_threshold": _UNPROVEN_FALSE,
        "obligations.monedas_virtuales_extranjero_above_threshold": _UNPROVEN_FALSE,
    },
)
"""Schema-6 payer-fact paths mapped to the stored value that is not a proven answer.

Frozen with the transition it describes: a later schema that adds payer facts
does not rewrite what schema 6 stored.
"""

_DEFAULTED_VALUES_FROM_V7: Final[Mapping[str, object]] = MappingProxyType(
    {
        "censo.large_company": _UNPROVEN_FALSE,
        "irpf.art109_activity_income_withholding_ge_70pct": _UNPROVEN_FALSE,
        "iva.does_intracomunitario": _UNPROVEN_FALSE,
        "iva.group_dominant_entity_enrolled": _UNPROVEN_FALSE,
        "iva.group_member_enrolled": _UNPROVEN_FALSE,
        "iva.intracommunity_operations_exceed_50000_eur": _UNPROVEN_FALSE,
        "iva.oss_enrolled": _UNPROVEN_FALSE,
        "iva.roi_enrolled": _UNPROVEN_FALSE,
        "iva.sii_enrolled": _UNPROVEN_FALSE,
        "taxpayer_type.fiscal_residency": "resident_irpf",
        "withholding.has_employees": _UNPROVEN_FALSE,
        "withholding.pays_capital_income_with_retencion": _UNPROVEN_FALSE,
        "withholding.pays_professionals_with_retencion": _UNPROVEN_FALSE,
        "withholding.pays_rent_with_retencion": _UNPROVEN_FALSE,
    },
)
"""Schema-7 paths mapped to the stored value that is not a proven answer.

These gate Modelos 100, 111, 115, 117, 123, 126, 128, 130, 151, 180, 187, 188,
190, 193, 194, 200, 202, 210, 216, 296, 322, 347, 349, 353, 369 and 840 through
a three-state fact, and schema 7 pre-answered every one of them.

- The withholding and intracommunity facts are what a rule requires, so the
  stored ``false`` is what rules its modelos out.
- The Art. 109 RIRPF coverage fact is the Modelo 130 exclusion: a stored
  ``false`` says the exception does not hold and leaves the pago fraccionado
  due, so it has to be an answer the taxpayer gave.
- The IVA enrolments decide Modelos 322, 353 and 369 and the Modelo 349
  cadence, and together with ``censo.large_company`` they answer whether the
  IVA ledgers are kept through the SII, which decides Modelo 347 and the
  monthly cadence of Modelos 111, 115, 123, 216 and 303.
- ``taxpayer_type.fiscal_residency`` is the one select here. Habitual
  residence in Spain selects the tax itself, so its old ``resident_irpf``
  default admitted the resident declarations and ruled out Modelo 210 for a
  taxpayer nobody had asked. A stored ``resident_irpf`` is indistinguishable
  from that default and is dropped; ``non_resident_irnr`` was never the
  default and keeps its value.

The remaining two-state withholding facts and the censo enrolments schema 7
still pre-answers keep their stored values: neither can turn an unanswered
question into a not-applicable verdict.
"""

_DEFAULTED_VALUES_BY_TRANSITION: Final[Mapping[int, Mapping[str, object]]] = MappingProxyType(
    {
        6: _DEFAULTED_VALUES_FROM_V6,
        7: _DEFAULTED_VALUES_FROM_V7,
    },
)
"""What the transition that LEAVES each version clears, keyed by that version."""

_NO_PATHS: Final[frozenset[str]] = frozenset[str]()
_NO_DEFAULTS: Final[Mapping[str, object]] = MappingProxyType({})

RETIRED_RENTAL_TIER_PATH: Final[str] = "renta_rental.reduccion_art_23_2_tier_2024"
"""The schema-8 field that stored the art. 23.2 reduction tier for one ejercicio."""

_RETIRED_PATHS_BY_TRANSITION: Final[Mapping[int, frozenset[str]]] = MappingProxyType(
    {8: frozenset({RETIRED_RENTAL_TIER_PATH})},
)
"""Paths the transition that LEAVES each version retires: cleared whatever value they hold.

A defaulted answer is cleared only when it equals its default. A retired field has
no successor to read its value, so every stored value goes.
"""


RETIRED_ASCENDANT_DISABILITY_KEY_GROUP: Final[str] = "renta_family.ascendiente"
"""The household group whose rows stored the disability key schema 12 retires."""
RETIRED_ASCENDANT_DISABILITY_KEY_LEAF: Final[str] = "discapacidad_clave"
"""The row leaf that stored the official disability key of an ascendant."""
_RETIRED_ASCENDANT_KEY_PATH: Final[re.Pattern[str]] = re.compile(
    rf"^{re.escape(RETIRED_ASCENDANT_DISABILITY_KEY_GROUP)}\.(\d+)\.{re.escape(RETIRED_ASCENDANT_DISABILITY_KEY_LEAF)}$"
)

_RETIRED_ROW_LEAVES_BY_TRANSITION: Final[Mapping[int, re.Pattern[str]]] = MappingProxyType(
    {11: _RETIRED_ASCENDANT_KEY_PATH},
)
"""Row leaves the transition that LEAVES each version retires on every row of their group, by path pattern."""

_ASCENDANT_DISABILITY_LEAVES: Final[tuple[str, ...]] = (
    "discapacidad",
    "discapacidad_asistencia",
    "incapacidad_judicial",
)
"""The row facts the retired key is derived from now, which a row whose key was cleared is asked for."""

_ADDITIVE_TRANSITIONS: Final[frozenset[int]] = frozenset({9, 10, 12, 13, 14})
"""Versions whose outgoing transition only adds fields, so it clears no stored value."""


def _transition_paths(version: int) -> frozenset[str]:
    defaulted: set[str] = set(_DEFAULTED_VALUES_BY_TRANSITION.get(version, _NO_DEFAULTS))
    return frozenset(defaulted | _RETIRED_PATHS_BY_TRANSITION.get(version, _NO_PATHS))


_CLEARED_PATHS_BY_TRANSITION: Final[Mapping[int, frozenset[str]]] = MappingProxyType(
    {
        version: _transition_paths(version)
        for version in (
            *_DEFAULTED_VALUES_BY_TRANSITION,
            *_RETIRED_PATHS_BY_TRANSITION,
            *_RETIRED_ROW_LEAVES_BY_TRANSITION,
            *_ADDITIVE_TRANSITIONS,
        )
    },
)
"""The same transitions as path sets, for the callers that only need the names."""

_PROPERTY_LEAVES: Final[tuple[str, ...]] = (
    "situacion",
    "referencia_catastral",
    "naturaleza",
    "direccion",
    "titularidad_regimen",
    "titular",
    "titular_hijo_ordinal",
    "porcentaje_propiedad",
    "porcentaje_usufructo",
    "adquisicion_titulo",
    "fecha_adquisicion",
    "fecha_transmision",
    "importe_adquisicion",
    "gastos_tributos_adquisicion",
    "valor_suelo",
    "mejoras",
    "valores_catastrales",
    "usos",
    "amortizacion_acumulada",
    "amortizacion_acumulada_desde",
    "inmueble_principal",
    "importes_movimientos",
)
_LEASE_LEAVES: Final[tuple[str, ...]] = (
    "inmueble",
    "fecha_contrato",
    "fecha_inicio",
    "fecha_fin",
    "uso_vivienda",
    "inquilinos",
    "zona_tensionada",
    "primer_arrendamiento_vivienda",
    "arrendatario_entidad_tipo",
    "arrendatario_entidad_finalidad",
    "rehabilitacion_fecha",
    "renta_inicial",
    "renta_ultima_contrato_anterior",
    "arrendatario_pariente_art24",
    "incumple_lau_17_6",
)

PATHS_INTRODUCED_IN_V7: Final[frozenset[str]] = frozenset(
    {
        "obligations.premio_loteria_gravamen_especial_sin_retencion",
        "obligations.premio_loteria_gravamen_especial_trimestres",
        "irpf.plantilla_media",
    },
)
"""Fields schema 6 did not declare; a schema-6 record carrying one is refused.

Compared by declared ``section.field``, so an indexed instance path such as
``irpf.plantilla_media.0.year`` counts as its field.
"""

PATHS_INTRODUCED_IN_V9: Final[frozenset[str]] = frozenset(
    {
        *(f"renta_inmueble.{leaf}" for leaf in _PROPERTY_LEAVES),
        *(f"renta_arrendamiento.{leaf}" for leaf in _LEASE_LEAVES),
    },
)
"""Fields schema 8 did not declare: the property and lease records."""

PATHS_INTRODUCED_IN_V10: Final[frozenset[str]] = frozenset({"taxpayer_type.pago_fraccionado_art_40_3_elected"})
"""Fields schema 9 did not declare: the LIS art. 40.3 election of the Modelo 202."""

_M200_RELATION_LEAVES: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType(
    {
        "m200_administrador": (
            "nif",
            "apellidos_nombre_razon_social",
            "forma_juridica",
            "representante",
            "domicilio_fiscal",
            "codigo_provincia",
        ),
        "m200_participacion_socio": (
            "nif",
            "representante",
            "forma_juridica",
            "apellidos_nombre_razon_social",
            "codigo_provincia_pais",
            "nominal",
            "porcentaje_participacion",
        ),
        "m200_representante_legal": ("apellidos_y_nombre", "nif", "fecha_poder", "notaria_otros"),
        "m200_secretario_consejo": ("apellidos_y_nombre", "nif"),
        "m200_participacion_directa": (
            "nif",
            "nombre_o_razon_social",
            "codigo_provincia_pais",
            "porcentaje_participacion",
            "valor_nominal_total",
            "valor_en_libros",
            "ingresos_por_dividendos",
            "correccion_valor_perdidas_ganancias",
            "reversion_perdidas_deterioro_valores",
            "eliminacion_deterioro_contable",
            "eliminacion_deterioro_valores_participacion",
            "ajuste_valor_razonable",
            "efecto_correccion_valorativa_base_imponible",
            "saldo_correcciones_fiscales_pendientes",
            "capital",
            "reservas_y_otras_partidas_fondos_propios",
            "otras_partidas_patrimonio_neto",
            "resultado_ultimo_ejercicio",
        ),
        "m200_entidad_menor_dependiente": ("nif", "nombre_o_razon_social"),
        "m200_establecimiento_permanente": (
            "identificacion",
            "pais_residencia_fiscal",
            "volumen_operaciones",
            "beneficio_o_perdida",
            "suma_ajustes_resultado_contable",
            "suma_deducciones_di_internacional_anteriores",
        ),
        "m200_socio_sicav_disolucion": ("nif_sociedad_disuelta", "nif_iic_reinversion"),
        "m200_relaciones": (
            "has_participacion_socio",
            "has_representante_legal",
            "has_secretario_consejo",
            "has_participacion_directa",
            "has_entidad_menor_dependiente",
            "has_establecimiento_permanente",
            "has_socio_sicav_disolucion",
        ),
    },
)

PATHS_INTRODUCED_IN_V11: Final[frozenset[str]] = frozenset(
    f"{section}.{leaf}" for section, leaves in _M200_RELATION_LEAVES.items() for leaf in leaves
)
"""Fields schema 10 did not declare: the Modelo 200 page 002 relations."""

PATHS_INTRODUCED_IN_V13: Final[frozenset[str]] = frozenset(
    f"taxpayer_type.{key}"
    for key in (
        "principal_cnae",
        "principal_cnae_classification",
        "regimen_ley_49_2002",
        "regimen_socimi",
        "regimen_entidad_capital_riesgo",
        "regimen_entidades_navieras_tonelaje",
        "erd_tipo_gravamen_especifico",
        "cooperativa_fiscalmente_protegida",
        "marca_instrumental",
        "fecha_constitucion",
        "cierre_ejercicio_dia",
        "cierre_ejercicio_mes",
    )
)
"""Fields schema 12 did not declare: the entity facts the Modelo 202 page 01 states."""

PATHS_INTRODUCED_IN_V14: Final[frozenset[str]] = frozenset(
    {"renta_inmueble.arrendado_desde", "renta_inmueble.sin_arrendar"},
)
"""Fields schema 13 did not declare: when the property was first let, or that it never was."""

_M840_LEAVES: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType(
    {
        "censo": ("aeat_delegacion_code", "aeat_administracion_code", "aeat_administracion_name"),
        "contact": (
            "fiscal_address_province_code",
            "fiscal_address_municipality_code",
            "fiscal_address_municipality_name",
        ),
        "activities": (
            "province_code",
            "municipality_code",
            "municipality_name",
            "cuota_provincial_province_code",
            "local_afecto_indirectamente",
            "maquinas_recreativas_tipo_a",
            "maquinas_recreativas_tipo_b",
            "expositores_autoventa",
        ),
        "iae_local": (
            "actividad",
            "afectacion",
            "via_sg",
            "via_nombre",
            "numero",
            "km",
            "portal",
            "escalera",
            "piso",
            "puerta",
            "postcode",
            "province_code",
            "municipality_code",
            "municipality_name",
            "telefono",
            "uso_destino_code",
            "uso_destino_description",
            "superficie_total",
            "superficie_rectificada",
            "superficie_computable",
        ),
        "iae_local_superficie": ("local", "clase", "total", "rectificada", "computable"),
        "iae_elemento_tributario": ("actividad", "linea", "code", "description", "numero"),
    },
)

PATHS_INTRODUCED_IN_V15: Final[frozenset[str]] = frozenset(
    f"{section}.{leaf}" for section, leaves in _M840_LEAVES.items() for leaf in leaves
)
"""Fields schema 14 did not declare: the Modelo 840 facts, premises, surface classes and tax elements."""

_PATHS_INTRODUCED_BY_VERSION: Final[Mapping[int, frozenset[str]]] = MappingProxyType(
    {
        7: PATHS_INTRODUCED_IN_V7,
        9: PATHS_INTRODUCED_IN_V9,
        10: PATHS_INTRODUCED_IN_V10,
        11: PATHS_INTRODUCED_IN_V11,
        13: PATHS_INTRODUCED_IN_V13,
        14: PATHS_INTRODUCED_IN_V14,
        15: PATHS_INTRODUCED_IN_V15,
    },
)
"""Fields each version ADDED. Schema 8 adds none; it only re-reads stored values."""

SUPPORTED_LEGACY_PROFILE_SCHEMA_VERSIONS: Final[tuple[int, ...]] = tuple(sorted(_CLEARED_PATHS_BY_TRANSITION))
"""Every stored profile schema version this build still migrates forward.

Lowest first. A record stored at any of these opens; anything older is refused
on read, because no transition out of it is declared here.
"""


_EVENT_FROM_KEY: Final[str] = "schema_migration_from"
_EVENT_TO_KEY: Final[str] = "schema_migration_to"
_EVENT_CLEARED_KEY: Final[str] = "schema_migration_cleared_paths"
_PATH_SEPARATOR: Final[str] = "|"


def cleared_payer_fact_paths_between(from_version: int, to_version: int) -> frozenset[str]:
    """Return every path the transitions from ``from_version`` to ``to_version`` clear.

    Raises:
        UserProfileValidationError: When the range is empty or names a version
            no declared transition covers.
    """
    if from_version >= to_version:
        raise UserProfileValidationError(
            f"profile schema migration must move forward, not {from_version} to {to_version}",
        )
    missing = [version for version in range(from_version, to_version) if version not in _CLEARED_PATHS_BY_TRANSITION]
    if missing:
        raise UserProfileValidationError(f"no profile schema transition leaves version(s) {missing!r}")
    return frozenset(
        path for version in range(from_version, to_version) for path in _CLEARED_PATHS_BY_TRANSITION[version]
    )


def _defaulted_values_between(from_version: int, to_version: int) -> Mapping[str, object]:
    """Return each clearable path mapped to the stored value that is not an answer.

    A path named by two crossed transitions keeps the value the EARLIER one
    declared, because that is the default the record was stored under.
    """
    cleared_payer_fact_paths_between(from_version, to_version)
    defaulted: dict[str, object] = {}
    for version in range(from_version, to_version):
        for path, value in _DEFAULTED_VALUES_BY_TRANSITION.get(version, _NO_DEFAULTS).items():
            defaulted.setdefault(path, value)
    return defaulted


def _is_retired_row_leaf(path: str, from_version: int, to_version: int) -> bool:
    """Report whether a transition from ``from_version`` to ``to_version`` retires the row leaf at ``path``."""
    return any(
        pattern.match(path) is not None
        for version, pattern in _RETIRED_ROW_LEAVES_BY_TRANSITION.items()
        if from_version <= version < to_version
    )


def _retired_paths_between(from_version: int, to_version: int) -> frozenset[str]:
    """Return the paths the transitions from ``from_version`` to ``to_version`` retire."""
    retired: set[str] = set()
    for version in range(from_version, to_version):
        retired |= _RETIRED_PATHS_BY_TRANSITION.get(version, _NO_PATHS)
    return frozenset(retired)


def _is_stored_default(fact: UserProfileFact, defaulted: Mapping[str, object]) -> bool:
    """Report whether ``fact`` holds exactly the default its transition pre-answered.

    Compared by type and value so a boolean path never clears on the integer
    ``0`` and the residency path never clears on an unrelated token.
    """
    if fact.path not in defaulted:
        return False
    unproven = defaulted[fact.path]
    return type(fact.value) is type(unproven) and fact.value == unproven


def _paths_introduced_after(version: int) -> frozenset[str]:
    """Return the fields every version later than ``version`` added."""
    return frozenset(
        path
        for introduced_in, paths in _PATHS_INTRODUCED_BY_VERSION.items()
        if introduced_in > version
        for path in paths
    )


def legacy_profile_schema(
    current: ProfileSchemaDefinition,
    *,
    version: int,
) -> ProfileSchemaDefinition:
    """Return the schema a record stored at ``version`` is authenticated against.

    Every later schema only ADDED optional fields or retired a field whose stored
    value the migration clears, so the legacy schema is the current declaration
    stamped with the legacy version; :func:`migrate_profile_facts` separately
    refuses a legacy record that carries a field its own version never declared.

    Raises:
        UserProfileValidationError: When ``current`` is not the schema this
            migration writes, or ``version`` is not a supported stored version.
    """
    if current.version != MIGRATED_PROFILE_SCHEMA_VERSION:
        raise UserProfileValidationError(
            f"profile schema {current.version} is not the schema this build migrates records onto",
        )
    if version not in SUPPORTED_LEGACY_PROFILE_SCHEMA_VERSIONS:
        raise UserProfileValidationError(f"profile schema {version} has no forward migration in this build")
    return current.model_copy(update={"version": version})


class ProfileSchemaMigration(BaseModel):
    """The typed outcome of migrating one stored record's facts."""

    model_config = STRICT_FROZEN_CONFIG

    from_version: int = SUPPORTED_LEGACY_PROFILE_SCHEMA_VERSIONS[-1]
    to_version: int = MIGRATED_PROFILE_SCHEMA_VERSION
    cleared_paths: tuple[str, ...] = Field(default=())

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_cleared_paths(self) -> Self:
        if tuple(sorted(set(self.cleared_paths))) != self.cleared_paths:
            raise UserProfileValidationError("cleared payer-fact paths must be sorted and unique")
        clearable = cleared_payer_fact_paths_between(self.from_version, self.to_version)
        unknown = {
            path
            for path in set(self.cleared_paths) - clearable
            if not _is_retired_row_leaf(path, self.from_version, self.to_version)
        }
        if unknown:
            raise UserProfileValidationError(f"migration names paths it never clears: {sorted(unknown)!r}")
        return self

    def to_event_payload(self) -> dict[str, str]:
        """Return the string payload persisted on the migration's history event."""
        return {
            _EVENT_FROM_KEY: str(self.from_version),
            _EVENT_TO_KEY: str(self.to_version),
            _EVENT_CLEARED_KEY: _PATH_SEPARATOR.join(self.cleared_paths),
        }

    @classmethod
    def from_event_payload(cls, payload: Mapping[str, str]) -> Self:
        """Parse the payload :meth:`to_event_payload` wrote.

        Raises:
            UserProfileValidationError: When a key is missing or malformed.
        """
        try:
            from_version = int(payload[_EVENT_FROM_KEY])
            to_version = int(payload[_EVENT_TO_KEY])
            cleared = payload[_EVENT_CLEARED_KEY]
        except (KeyError, ValueError) as exc:
            raise UserProfileValidationError("profile schema migration event payload is malformed") from exc
        return cls(
            from_version=from_version,
            to_version=to_version,
            cleared_paths=tuple(path for path in cleared.split(_PATH_SEPARATOR) if path),
        )


def migrate_profile_facts(
    facts: Iterable[UserProfileFact],
    *,
    from_version: int,
) -> tuple[tuple[UserProfileFact, ...], ProfileSchemaMigration]:
    """Return the current-schema facts and the outcome for facts stored at ``from_version``.

    Raises:
        UserProfileValidationError: When a stored fact names a path the record's
            own schema version did not declare, or ``from_version`` is not a
            supported stored version.
    """
    if from_version not in SUPPORTED_LEGACY_PROFILE_SCHEMA_VERSIONS:
        raise UserProfileValidationError(f"profile schema {from_version} has no forward migration in this build")
    stored = tuple(facts)
    later_fields = _paths_introduced_after(from_version)
    introduced = sorted({fact.path for fact in stored if section_field_key(fact.path) in later_fields})
    if introduced:
        raise UserProfileValidationError(
            f"schema-{from_version} profile record carries later-schema paths {introduced!r}",
        )
    defaulted = _defaulted_values_between(from_version, MIGRATED_PROFILE_SCHEMA_VERSION)
    retired = _retired_paths_between(from_version, MIGRATED_PROFILE_SCHEMA_VERSION)
    kept: list[UserProfileFact] = []
    cleared: set[str] = set()
    for fact in stored:
        if (
            fact.path in retired
            or _is_retired_row_leaf(fact.path, from_version, MIGRATED_PROFILE_SCHEMA_VERSION)
            or _is_stored_default(fact, defaulted)
        ):
            cleared.add(fact.path)
            continue
        kept.append(fact)
    migration = ProfileSchemaMigration(
        from_version=from_version,
        to_version=MIGRATED_PROFILE_SCHEMA_VERSION,
        cleared_paths=tuple(sorted(cleared)),
    )
    return tuple(kept), migration


def pending_cleared_payer_fact_paths(
    record: UserProfileRecord,
    migrations: Iterable[ProfileSchemaMigration],
) -> tuple[str, ...]:
    """Return cleared payer-fact paths the current record has not answered again.

    A path counts as answered once the record carries a fact on it with a
    value, whether yes or no; a cleared (``None``) fact is still unanswered.
    A retired path is not a payer fact and is never offered here: its finding is
    :func:`rental_tier_finding_pending` or :func:`ascendant_disability_rows_pending`.

    Core types:
    :class:`~cadrumo.domain.user_profile.values.UserProfileRecord`.
    """
    answered = {fact.path for fact in record.facts if fact.value is not None}
    retired = _retired_paths_between(0, MIGRATED_PROFILE_SCHEMA_VERSION)
    cleared = {
        path
        for migration in migrations
        for path in migration.cleared_paths
        if not _is_retired_row_leaf(path, 0, MIGRATED_PROFILE_SCHEMA_VERSION)
    } - retired
    return tuple(sorted(cleared - answered))


def rental_tier_finding_pending(
    record: UserProfileRecord,
    migrations: Iterable[ProfileSchemaMigration],
) -> bool:
    """Report whether a migration cleared a stored reduction tier and no lease has been recorded since.

    The tier cannot be converted into lease facts, so the finding stands until the
    profile holds at least one lease with a stated value.

    Core types:
    :class:`~cadrumo.domain.user_profile.values.UserProfileRecord`.
    """
    if not any(RETIRED_RENTAL_TIER_PATH in migration.cleared_paths for migration in migrations):
        return False
    return not any(fact.value is not None and fact.path.startswith("renta_arrendamiento.") for fact in record.facts)


def ascendant_disability_rows_pending(
    record: UserProfileRecord,
    migrations: Iterable[ProfileSchemaMigration],
) -> tuple[str, ...]:
    """Return the ascendant rows whose stored disability key a migration cleared and that still owe its facts.

    A key 1 or 2 cannot be converted into a grade, so the finding stands for a row until
    it states the grade, the assistance and the judicial incapacity. The rows are named
    by their stored number, the index the ascendant edit takes, in ascending order.

    Core types:
    :class:`~cadrumo.domain.user_profile.values.UserProfileRecord`.
    """
    cleared_rows = {
        match.group(1)
        for migration in migrations
        for path in migration.cleared_paths
        if (match := _RETIRED_ASCENDANT_KEY_PATH.match(path)) is not None
    }
    stated = {fact.path for fact in record.facts if fact.value is not None}
    pending = (
        row
        for row in cleared_rows
        if any(
            f"{RETIRED_ASCENDANT_DISABILITY_KEY_GROUP}.{row}.{leaf}" not in stated
            for leaf in _ASCENDANT_DISABILITY_LEAVES
        )
    )
    ordered: list[str] = sorted(pending, key=int)
    return tuple(ordered)


__all__ = [
    "MIGRATED_PROFILE_SCHEMA_VERSION",
    "PATHS_INTRODUCED_IN_V7",
    "PATHS_INTRODUCED_IN_V9",
    "PATHS_INTRODUCED_IN_V10",
    "PATHS_INTRODUCED_IN_V11",
    "PATHS_INTRODUCED_IN_V13",
    "PATHS_INTRODUCED_IN_V14",
    "PATHS_INTRODUCED_IN_V15",
    "RETIRED_ASCENDANT_DISABILITY_KEY_GROUP",
    "RETIRED_ASCENDANT_DISABILITY_KEY_LEAF",
    "RETIRED_RENTAL_TIER_PATH",
    "SUPPORTED_LEGACY_PROFILE_SCHEMA_VERSIONS",
    "ProfileSchemaMigration",
    "ascendant_disability_rows_pending",
    "cleared_payer_fact_paths_between",
    "legacy_profile_schema",
    "migrate_profile_facts",
    "pending_cleared_payer_fact_paths",
    "rental_tier_finding_pending",
]
