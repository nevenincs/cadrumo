"""Serve the art. 23.2 LIRPF reduction of each lease beside the lease in the grouped profile read.

The tier is the shared derivation's, handed one lease at a time exactly as the Modelo 100
rental chain hands it, so what is served is what the return would use. Its dated inputs are
the pinned registry's, resolved for the devengo of each Modelo 100 return the profile has
started: the reduction is stated for those ejercicios in which the lease runs, and for none
the profile has not started a return for. A lease that no started return reaches, or whose
facts do not read, is served as not determinable with its way out, never as a guess.

Facts read here are private; nothing in this module logs them.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Final

from ...core.errors.hierarchy import ProfileAnswerTypeError
from ...core.i18n.render import tr
from ...core.modelo import Modelo
from ...domain.calculations.registry.rental_reduction import (
    resolve_rental_reduction_art232_rates,
    resolve_rental_reduction_art232_rules,
)
from ...domain.contribuyente.arrendamiento_record import ArrendamientoRecord
from ...domain.contribuyente.inmueble_facts import ARRENDAMIENTO_SECTION, arrendamiento_from_row, parse_inquilinos
from ...domain.modelos.work_unit import WorkUnitState
from ...domain.renta.rental_reduction import RentalReductionArt232Tier
from ...domain.renta.rental_reduction_derivation import (
    RentalReductionArt232Rules,
    RentalReductionDerivation,
    RentalReductionRefusal,
    derive_rental_reduction,
    leases_active_in,
)
from ...domain.user_profile.labels import profile_choice_label
from .record_group_contracts import (
    ProfileRecordMissingFact,
    ProfileRecordReduction,
    ProfileRecordReductionFact,
    ProfileRecordReductionOutcome,
    ProfileRecordReductionYear,
)
from .record_group_reduction_words import (
    APPLIES_LOCALE_KEY,
    DOES_NOT_APPLY_LOCALE_KEY,
    FACT_FIELDS,
    FILL_IN_LOCALE_KEY,
    NO_EJERCICIO_LOCALE_KEY,
    REFUSAL_FIELDS,
    REFUSAL_WORDS_LOCALE_KEYS,
    TENANT_BAND_WORDS_LOCALE_KEYS,
    TITLE_LOCALE_KEY,
    fact_name_words,
    fact_words,
    tier_words,
    value_words,
)
from .record_group_words import field_door, member_kind_words

if TYPE_CHECKING:
    from ...core.external_constants import OutputLanguage
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.modelos.work_unit import WorkUnit
    from ...domain.user_profile.schema import ProfileSchemaDefinition

_ANNUAL_RETURN: Final = Modelo("100")
_FLAGS: Final = frozenset({"uso_vivienda", "zona_tensionada", "incumple_lau_17_6", "primer_arrendamiento_vivienda"})
_ENUMS: Final = frozenset({"arrendatario_entidad_tipo", "arrendatario_entidad_finalidad"})


@dataclass(frozen=True, slots=True)
class ReductionWork:
    """One Modelo 100 return the profile has started: the ejercicio it speaks for and the edition it is pinned to."""

    ejercicio: int
    revision_id: str
    devengo: date


def reduction_works(units: Iterable[WorkUnit]) -> tuple[ReductionWork, ...]:
    """Return each ejercicio the profile has an undiscarded Modelo 100 return for, in ejercicio order."""
    works = {
        (int(unit.filing_year), str(unit.revision_id)): ReductionWork(
            ejercicio=int(unit.filing_year), revision_id=str(unit.revision_id), devengo=unit.period.end_date
        )
        for unit in units
        if unit.modelo == _ANNUAL_RETURN and unit.state is not WorkUnitState.DESCARTADO
    }
    return tuple(sorted(works.values(), key=lambda work: (work.ejercicio, work.revision_id)))


@dataclass(frozen=True, slots=True)
class _Terms:
    rules: RentalReductionArt232Rules
    rates: Mapping[RentalReductionArt232Tier, Decimal]


class LeaseReductionServer:
    """Serve the reduction of any lease row over the same started returns and the same pinned authority."""

    def __init__(
        self,
        works: tuple[ReductionWork, ...],
        *,
        operation: PinnedAuthorityOperation,
        schema: ProfileSchemaDefinition,
        language: OutputLanguage,
    ) -> None:
        """Bind the started returns, the pinned authority that dates them and the language to word in."""
        self._works = works
        self._operation = operation
        self._schema = schema
        self._language = language
        self._terms: dict[ReductionWork, _Terms] = {}

    def serve(self, row_key: int, values: Mapping[str, str]) -> ProfileRecordReduction:
        """Return the reduction of the lease stored as ``values`` at ``row_key``."""
        try:
            lease = arrendamiento_from_row(row_key, values)
        except ProfileAnswerTypeError as error:
            years = self._unreadable(error)
        else:
            years = self._derived(lease)
        return ProfileRecordReduction(
            title_words=tr(TITLE_LOCALE_KEY),
            title_words_language=self._language,
            facts=tuple(self._fact(field, values.get(field)) for field in FACT_FIELDS),
            years=years or (self._without_ejercicio(),),
        )

    def _terms_for(self, work: ReductionWork) -> _Terms:
        known = self._terms.get(work)
        if known is None:
            modelo_id, operation = _ANNUAL_RETURN.value, self._operation
            known = _Terms(
                rules=resolve_rental_reduction_art232_rules(
                    modelo_id=modelo_id, revision_id=work.revision_id, devengo=work.devengo, operation=operation
                ),
                rates=resolve_rental_reduction_art232_rates(
                    modelo_id=modelo_id, revision_id=work.revision_id, devengo=work.devengo, operation=operation
                ),
            )
            self._terms[work] = known
        return known

    def _derived(self, lease: ArrendamientoRecord) -> tuple[ProfileRecordReductionYear, ...]:
        years: list[ProfileRecordReductionYear] = []
        for work in self._works:
            if not leases_active_in((lease,), year=work.ejercicio):
                continue
            terms = self._terms_for(work)
            outcome = derive_rental_reduction((lease,), devengo=work.devengo, rules=terms.rules)
            years.append(self._year(work.ejercicio, outcome, terms))
        return tuple(years)

    def _unreadable(self, error: ProfileAnswerTypeError) -> tuple[ProfileRecordReductionYear, ...]:
        """Serve a lease whose facts do not read as not determinable in every started return."""
        named = (error.context or {}).get("key")
        field = named if isinstance(named, str) and self._is_lease_field(named) else None
        return tuple(
            self._refused(work.ejercicio, RentalReductionRefusal.LEASE_UNREADABLE, field) for work in self._works
        )

    def _is_lease_field(self, field_key: str) -> bool:
        return any(field.key == field_key for field in self._schema.section(ARRENDAMIENTO_SECTION).fields)

    def _year(self, ejercicio: int, outcome: RentalReductionDerivation, terms: _Terms) -> ProfileRecordReductionYear:
        if outcome.refusal is not None:
            return self._refused(ejercicio, outcome.refusal, REFUSAL_FIELDS[outcome.refusal])
        if outcome.aplicable is True and outcome.tier is not None:
            words = tier_words(outcome.tier, terms.rates[outcome.tier], legacy=terms.rules.legacy_tier)
            return ProfileRecordReductionYear(
                ejercicio=ejercicio,
                outcome=ProfileRecordReductionOutcome.APPLIES,
                tier=str(outcome.tier),
                tier_words=words,
                tier_words_language=self._language,
                outcome_words=tr(APPLIES_LOCALE_KEY, ejercicio=ejercicio, tier=words),
                outcome_words_language=self._language,
            )
        return ProfileRecordReductionYear(
            ejercicio=ejercicio,
            outcome=ProfileRecordReductionOutcome.DOES_NOT_APPLY,
            outcome_words=tr(DOES_NOT_APPLY_LOCALE_KEY, ejercicio=ejercicio),
            outcome_words_language=self._language,
        )

    def _refused(
        self, ejercicio: int, refusal: RentalReductionRefusal, field: str | None
    ) -> ProfileRecordReductionYear:
        missing = None if field is None else self._missing(field)
        return ProfileRecordReductionYear(
            ejercicio=ejercicio,
            outcome=ProfileRecordReductionOutcome.NOT_DETERMINABLE,
            refusal_code=refusal,
            outcome_words=tr(
                REFUSAL_WORDS_LOCALE_KEYS[refusal],
                ejercicio=ejercicio,
                fact=member_kind_words(ARRENDAMIENTO_SECTION) if field is None else fact_name_words(field),
            ),
            outcome_words_language=self._language,
            missing_fact=missing,
        )

    def _missing(self, field: str) -> ProfileRecordMissingFact:
        name = fact_name_words(field)
        return ProfileRecordMissingFact(
            field_key=field,
            fact_words=name,
            fact_words_language=self._language,
            way_out=field_door(ARRENDAMIENTO_SECTION, field, tr(FILL_IN_LOCALE_KEY, fact=name), self._language),
        )

    def _without_ejercicio(self) -> ProfileRecordReductionYear:
        return ProfileRecordReductionYear(
            outcome=ProfileRecordReductionOutcome.NOT_DETERMINABLE,
            outcome_words=tr(NO_EJERCICIO_LOCALE_KEY),
            outcome_words_language=self._language,
        )

    def _fact(self, field: str, stated: str | None) -> ProfileRecordReductionFact:
        return ProfileRecordReductionFact(
            field_key=field,
            fact_words=fact_words(field, value_words("not_stated") if stated is None else self._value(field, stated)),
            fact_words_language=self._language,
            stated=stated is not None,
        )

    def _value(self, field: str, stated: str) -> str:
        """Word the value a lease states for ``field``; a tenant's identifier is never among the words."""
        if field in _FLAGS:
            return value_words({"true": "yes", "false": "no"}.get(stated, "not_readable"))
        if field in _ENUMS:
            enum_values = self._schema.field(f"{ARRENDAMIENTO_SECTION}.{field}").enum_values or ()
            if stated in enum_values:
                return profile_choice_label(ARRENDAMIENTO_SECTION, field, stated)
            return value_words("not_readable")
        if field == "inquilinos":
            try:
                tenants = parse_inquilinos(stated, leaf=field)
            except ProfileAnswerTypeError:
                return value_words("not_readable")
            return ", ".join(tr(TENANT_BAND_WORDS_LOCALE_KEYS[tenant.franja_edad]) for tenant in tenants)
        return stated


__all__ = ["LeaseReductionServer", "ReductionWork", "reduction_works"]
