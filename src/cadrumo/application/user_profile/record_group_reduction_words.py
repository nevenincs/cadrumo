"""The words the grouped profile read serves beside the art. 23.2 LIRPF reduction of a lease.

The reduction is derived elsewhere; this module only says it. It names the facts the
derivation reads, the value a lease states for each, the tier the derivation reached,
and for a derivation that refuses which stored fact it lacked, so a surface renders
served sentences and composes none from the stored facts.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from types import MappingProxyType
from typing import Final

from ...core.i18n.render import tr
from ...domain.contribuyente.arrendamiento_record import InquilinoEdad
from ...domain.contribuyente.inmueble_facts import ARRENDAMIENTO_SECTION
from ...domain.renta.rental_reduction import RentalReductionArt232Tier
from ...domain.renta.rental_reduction_derivation import (
    TIER_50,
    TIER_60,
    TIER_70,
    TIER_90,
    RentalReductionRefusal,
)
from ...domain.user_profile.labels import profile_field_label_key

TITLE_LOCALE_KEY: Final = "application.user_profile.record_groups.reduction.title"
"""What the reduction block is."""

FACT_LOCALE_KEY: Final = "application.user_profile.record_groups.reduction.fact"
"""A fact's name joined to the value the lease states for it."""

FILL_IN_LOCALE_KEY: Final = "application.user_profile.record_groups.reduction.fill_in"
"""The label of the edit door that states a missing fact."""

NO_EJERCICIO_LOCALE_KEY: Final = "application.user_profile.record_groups.reduction.no_ejercicio"
"""Why no ejercicio can be spoken of, and what to do."""

APPLIES_LOCALE_KEY: Final = "application.user_profile.record_groups.reduction.year.applies"
DOES_NOT_APPLY_LOCALE_KEY: Final = "application.user_profile.record_groups.reduction.year.does_not_apply"

VALUE_WORDS_LOCALE_KEYS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "yes": "application.user_profile.record_groups.reduction.value.affirmative",
        "no": "application.user_profile.record_groups.reduction.value.negative",
        "not_stated": "application.user_profile.record_groups.reduction.value.not_stated",
        "not_readable": "application.user_profile.record_groups.reduction.value.not_readable",
    }
)
"""The words of a fact a lease states as yes or no, does not state, or states so that it cannot be read."""

TENANT_BAND_WORDS_LOCALE_KEYS: Final[Mapping[InquilinoEdad, str]] = MappingProxyType(
    {
        InquilinoEdad.DE_18_A_35: "application.user_profile.record_groups.reduction.tenant_band.ages_18_to_35",
        InquilinoEdad.OTRA: "application.user_profile.record_groups.reduction.tenant_band.other_ages",
        InquilinoEdad.NO_APLICA: "application.user_profile.record_groups.reduction.tenant_band.not_a_person",
    }
)
"""The words of the age band a tenant is stated in; no tenant identifier is ever served."""

TIER_WORDS_LOCALE_KEYS: Final[Mapping[RentalReductionArt232Tier, str]] = MappingProxyType(
    {
        TIER_90: "application.user_profile.record_groups.reduction.tier.tier_90",
        TIER_70: "application.user_profile.record_groups.reduction.tier.tier_70",
        TIER_60: "application.user_profile.record_groups.reduction.tier.tier_60",
        TIER_50: "application.user_profile.record_groups.reduction.tier.tier_50",
    }
)
LEGACY_TIER_WORDS_LOCALE_KEY: Final = "application.user_profile.record_groups.reduction.tier.legacy"
"""The words of the legacy reduction, whose token the registry names."""

REFUSAL_WORDS_LOCALE_KEYS: Final[Mapping[RentalReductionRefusal, str]] = MappingProxyType(
    {
        RentalReductionRefusal.NO_LEASE: "application.user_profile.record_groups.reduction.refusal.no_lease",
        RentalReductionRefusal.SEVERAL_LEASES: (
            "application.user_profile.record_groups.reduction.refusal.several_leases"
        ),
        RentalReductionRefusal.LEASE_UNREADABLE: (
            "application.user_profile.record_groups.reduction.refusal.lease_unreadable"
        ),
        RentalReductionRefusal.USO_VIVIENDA_UNSTATED: (
            "application.user_profile.record_groups.reduction.refusal.uso_vivienda_unstated"
        ),
        RentalReductionRefusal.ZONA_TENSIONADA_UNSTATED: (
            "application.user_profile.record_groups.reduction.refusal.zona_tensionada_unstated"
        ),
        RentalReductionRefusal.LAU_17_6_UNSTATED: (
            "application.user_profile.record_groups.reduction.refusal.lau_17_6_unstated"
        ),
        RentalReductionRefusal.MIXED_TENANT_AGES: (
            "application.user_profile.record_groups.reduction.refusal.mixed_tenant_ages"
        ),
    }
)
"""Why a derivation refused and what the operator does next."""

REFUSAL_FIELDS: Final[Mapping[RentalReductionRefusal, str | None]] = MappingProxyType(
    {
        RentalReductionRefusal.NO_LEASE: None,
        RentalReductionRefusal.SEVERAL_LEASES: None,
        RentalReductionRefusal.LEASE_UNREADABLE: None,
        RentalReductionRefusal.USO_VIVIENDA_UNSTATED: "uso_vivienda",
        RentalReductionRefusal.ZONA_TENSIONADA_UNSTATED: "zona_tensionada",
        RentalReductionRefusal.LAU_17_6_UNSTATED: "incumple_lau_17_6",
        RentalReductionRefusal.MIXED_TENANT_AGES: "inquilinos",
    }
)
"""The lease field each refusal lacks; a refusal that lacks none, or whose field is read from the error, has none."""

FACT_FIELDS: Final = (
    "fecha_contrato",
    "uso_vivienda",
    "zona_tensionada",
    "incumple_lau_17_6",
    "primer_arrendamiento_vivienda",
    "inquilinos",
    "arrendatario_entidad_tipo",
    "arrendatario_entidad_finalidad",
    "rehabilitacion_fecha",
    "renta_inicial",
    "renta_ultima_contrato_anterior",
)
"""The leaves of a lease the derivation reads, in the order the law reads them."""


def fact_name_words(field_key: str) -> str:
    """Return the name of a lease field, in the output language."""
    return tr(profile_field_label_key(ARRENDAMIENTO_SECTION, field_key))


def value_words(kind: str) -> str:
    """Return the words of a value a lease states as ``yes``, ``no``, ``not_stated`` or ``not_readable``."""
    return tr(VALUE_WORDS_LOCALE_KEYS[kind])


def fact_words(field_key: str, value: str) -> str:
    """Return a fact's name joined to the ``value`` words the lease states for it."""
    return tr(FACT_LOCALE_KEY, name=fact_name_words(field_key), value=value)


def tier_words(tier: RentalReductionArt232Tier, rate: Decimal, *, legacy: RentalReductionArt232Tier) -> str:
    """Return what ``tier`` reduces by, in the output language; the registry names the ``legacy`` token."""
    key = LEGACY_TIER_WORDS_LOCALE_KEY if tier == legacy else TIER_WORDS_LOCALE_KEYS[tier]
    return tr(key, rate=format((rate * 100).normalize(), "f"))


def _require_total_tables() -> None:
    if set(REFUSAL_WORDS_LOCALE_KEYS) != set(RentalReductionRefusal) or set(REFUSAL_FIELDS) != set(
        RentalReductionRefusal
    ):
        raise ValueError("every reduction refusal needs its words and its field")
    if set(TENANT_BAND_WORDS_LOCALE_KEYS) != set(InquilinoEdad):
        raise ValueError("every tenant age band needs its words")
    if any(field not in FACT_FIELDS for field in REFUSAL_FIELDS.values() if field is not None):
        raise ValueError("a refusal can only lack a fact the derivation reads")


_require_total_tables()

__all__ = [
    "APPLIES_LOCALE_KEY",
    "DOES_NOT_APPLY_LOCALE_KEY",
    "FACT_FIELDS",
    "FACT_LOCALE_KEY",
    "FILL_IN_LOCALE_KEY",
    "LEGACY_TIER_WORDS_LOCALE_KEY",
    "NO_EJERCICIO_LOCALE_KEY",
    "REFUSAL_FIELDS",
    "REFUSAL_WORDS_LOCALE_KEYS",
    "TENANT_BAND_WORDS_LOCALE_KEYS",
    "TIER_WORDS_LOCALE_KEYS",
    "TITLE_LOCALE_KEY",
    "VALUE_WORDS_LOCALE_KEYS",
    "fact_name_words",
    "fact_words",
    "tier_words",
    "value_words",
]
