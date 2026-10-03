"""Typed projections of the registry-owned prorrata-register vocabularies."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Final

from ....core.prorrata_register import (
    ProrrataEspecialTransitionKind,
    ProrrataProvisionalProvenance,
    ProrrataRegisterRegime,
    SectorDiferenciadoLetra,
)
from . import prorrata_register_models as _models
from .errors import RegistryValidationError
from .facts.resolution import required_mapping_entry, unique_mapping_tokens
from .facts.string_mapping import (
    BooleanTokenCase,
    MappingValueWhitespace,
    StringMappingFact,
    StringMappingPolicy,
    required_mapping_boolean,
)
from .governed_fact_scope import GovernedFactSource
from .schema_base import DateAxis

_ENTRY_SUBJECT: Final = "prorrata register mapping"

_FACT_ID = "renta-iva-deduction-ratio-policy"
_REGIME_ORDER_KEY = "prorrata.regime_order"
_REGISTER_REGIME_ADDITIONS_KEY = "prorrata.register_regime_additions"
_REGIME_PREFIX = "prorrata.regime."
_TRANSITION_ORDER_KEY = "prorrata.especial_transition_order"
_TRANSITION_PREFIX = "prorrata.especial_transition."
_PROVENANCE_ORDER_KEY = "prorrata.provisional_provenance_order"
_PROVENANCE_PREFIX = "prorrata.provisional_provenance."
_SECTOR_ORDER_KEY = "prorrata.sector_diferenciado_letra_order"
_SECTOR_PREFIX = "prorrata.sector_diferenciado_letra."


_ENTRIES_POLICY = StringMappingPolicy(subject=_ENTRY_SUBJECT, value_whitespace=MappingValueWhitespace.PRESERVE)


_ENTRIES_FACT = StringMappingFact(fact_id=_FACT_ID, date_axis=DateAxis.FILING_PERIOD, policy=_ENTRIES_POLICY)


def resolve_prorrata_register_catalogue(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> _models.ProrrataRegisterCatalogue:
    """Resolve all register vocabularies through the dated 0116 mapping fact."""
    entries = _ENTRIES_FACT.resolve_scoped_entries(effective_date=effective_date, authority=authority)
    catalogue = _models.ProrrataRegisterCatalogue(
        regimes=_prorrata_regimes(entries),
        transition_kinds=_prorrata_transition_kinds(entries),
        provenances=_prorrata_provenances(entries),
        sector_letters=_prorrata_sector_letters(entries),
    )
    _validate_prorrata_register_catalogue(catalogue)
    return catalogue


def _prorrata_regimes(entries: Mapping[str, str]) -> tuple[_models.ProrrataRegisterRegimeDefinition, ...]:
    regime_tokens = (
        *unique_mapping_tokens(entries, _REGIME_ORDER_KEY, subject=_ENTRY_SUBJECT),
        *unique_mapping_tokens(entries, _REGISTER_REGIME_ADDITIONS_KEY, subject=_ENTRY_SUBJECT),
    )
    regimes: list[_models.ProrrataRegisterRegimeDefinition] = []
    for raw_token in regime_tokens:
        prefix = f"{_REGIME_PREFIX}{raw_token}"
        token = ProrrataRegisterRegime.from_registry(
            required_mapping_entry(entries, f"{prefix}.value", subject=_ENTRY_SUBJECT)
        )
        if str(token) != raw_token:
            raise RegistryValidationError(f"register regime {raw_token!r} declares a mismatched value")
        regimes.append(
            _models.ProrrataRegisterRegimeDefinition(
                token=token,
                description=required_mapping_entry(entries, f"{prefix}.description", subject=_ENTRY_SUBJECT),
                legal_ref=required_mapping_entry(entries, f"{prefix}.legal_ref", subject=_ENTRY_SUBJECT),
                apportions=required_mapping_boolean(
                    entries, f"{prefix}.apportions", subject=_ENTRY_SUBJECT, case=BooleanTokenCase.CASE_INSENSITIVE
                ),
            ),
        )
    return tuple(regimes)


def _prorrata_transition_kinds(entries: Mapping[str, str]) -> tuple[_models.ProrrataTransitionDefinition, ...]:
    transition_kinds: list[_models.ProrrataTransitionDefinition] = []
    for raw_token in unique_mapping_tokens(entries, _TRANSITION_ORDER_KEY, subject=_ENTRY_SUBJECT):
        prefix = f"{_TRANSITION_PREFIX}{raw_token}"
        token = ProrrataEspecialTransitionKind.from_registry(
            required_mapping_entry(entries, f"{prefix}.value", subject=_ENTRY_SUBJECT)
        )
        if str(token) != raw_token:
            raise RegistryValidationError(f"transition {raw_token!r} declares a mismatched value")
        transition_kinds.append(
            _models.ProrrataTransitionDefinition(
                token=token,
                description=required_mapping_entry(entries, f"{prefix}.description", subject=_ENTRY_SUBJECT),
                legal_ref=required_mapping_entry(entries, f"{prefix}.legal_ref", subject=_ENTRY_SUBJECT),
            ),
        )
    return tuple(transition_kinds)


def _prorrata_provenances(entries: Mapping[str, str]) -> tuple[_models.ProrrataProvenanceDefinition, ...]:
    provenances: list[_models.ProrrataProvenanceDefinition] = []
    for raw_token in unique_mapping_tokens(entries, _PROVENANCE_ORDER_KEY, subject=_ENTRY_SUBJECT):
        prefix = f"{_PROVENANCE_PREFIX}{raw_token}"
        token = ProrrataProvisionalProvenance.from_registry(
            required_mapping_entry(entries, f"{prefix}.value", subject=_ENTRY_SUBJECT)
        )
        if str(token) != raw_token:
            raise RegistryValidationError(f"provenance {raw_token!r} declares a mismatched value")
        provenances.append(
            _models.ProrrataProvenanceDefinition(
                token=token,
                description=required_mapping_entry(entries, f"{prefix}.description", subject=_ENTRY_SUBJECT),
                legal_ref=required_mapping_entry(entries, f"{prefix}.legal_ref", subject=_ENTRY_SUBJECT),
                authorisation_required=required_mapping_boolean(
                    entries,
                    f"{prefix}.authorisation_required",
                    subject=_ENTRY_SUBJECT,
                    case=BooleanTokenCase.CASE_INSENSITIVE,
                ),
                election_allowed=required_mapping_boolean(
                    entries,
                    f"{prefix}.election_allowed",
                    subject=_ENTRY_SUBJECT,
                    case=BooleanTokenCase.CASE_INSENSITIVE,
                ),
            ),
        )
    return tuple(provenances)


def _prorrata_sector_letters(entries: Mapping[str, str]) -> tuple[_models.SectorDiferenciadoLetraDefinition, ...]:
    sector_letters: list[_models.SectorDiferenciadoLetraDefinition] = []
    for raw_token in unique_mapping_tokens(entries, _SECTOR_ORDER_KEY, subject=_ENTRY_SUBJECT):
        prefix = f"{_SECTOR_PREFIX}{raw_token}"
        token = SectorDiferenciadoLetra.from_registry(
            required_mapping_entry(entries, f"{prefix}.value", subject=_ENTRY_SUBJECT)
        )
        if str(token) != raw_token:
            raise RegistryValidationError(f"sector letter {raw_token!r} declares a mismatched value")
        sector_letters.append(
            _models.SectorDiferenciadoLetraDefinition(
                token=token,
                description=required_mapping_entry(entries, f"{prefix}.description", subject=_ENTRY_SUBJECT),
                legal_ref=required_mapping_entry(entries, f"{prefix}.legal_ref", subject=_ENTRY_SUBJECT),
            ),
        )
    return tuple(sector_letters)


def _validate_prorrata_register_catalogue(catalogue: _models.ProrrataRegisterCatalogue) -> None:
    if len(catalogue.regimes) < 3 or len(catalogue.apportioning_regimes) != 2:
        raise RegistryValidationError("0116 must retain the two canonical apportioning regimes and add register states")
    if len(catalogue.transition_kinds) != 2 or len(catalogue.provenances) != 4 or len(catalogue.sector_letters) != 4:
        raise RegistryValidationError("0116 register vocabulary cardinalities do not match the declared scope")
    if not set(catalogue.apportioning_regimes).issubset(catalogue.all_regimes):
        raise RegistryValidationError("0116 apportioning regimes must be declared in the regime vocabulary")


def general_prorrata_register_regime(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> ProrrataRegisterRegime:
    """Return the registry-declared general-prorrata regime token."""
    return resolve_prorrata_register_catalogue(effective_date=effective_date, authority=authority).general_regime


def especial_prorrata_register_regime(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> ProrrataRegisterRegime:
    """Return the registry-declared special-prorrata regime token."""
    return resolve_prorrata_register_catalogue(effective_date=effective_date, authority=authority).especial_regime


def ninguna_prorrata_register_regime(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> ProrrataRegisterRegime:
    """Return the registry-declared no-prorrata regime token."""
    return resolve_prorrata_register_catalogue(effective_date=effective_date, authority=authority).no_prorrata_regime


def opcion_prorrata_transition(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> ProrrataEspecialTransitionKind:
    """Return the registry-declared special-prorrata option transition token."""
    return resolve_prorrata_register_catalogue(effective_date=effective_date, authority=authority).opcion_transition


def revocacion_prorrata_transition(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> ProrrataEspecialTransitionKind:
    """Return the registry-declared special-prorrata revocation token."""
    return resolve_prorrata_register_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).revocacion_transition


def aeat_autorizada_prorrata_provenance(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> ProrrataProvisionalProvenance:
    """Return the registry-declared AEAT-authorised provenance token."""
    return resolve_prorrata_register_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).aeat_autorizada_provenance


def inicio_actividad_prorrata_provenance(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> ProrrataProvisionalProvenance:
    """Return the registry-declared start-of-activity provenance token."""
    return resolve_prorrata_register_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).inicio_actividad_provenance


def carried_prior_definitiva_prorrata_provenance(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> ProrrataProvisionalProvenance:
    """Return the registry-declared carried-prior-definitive provenance token."""
    return resolve_prorrata_register_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).carried_prior_definitiva_provenance


def prorrata_provenance_precedence(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> tuple[ProrrataProvisionalProvenance, ...]:
    """Return the registry-authored provisional-provenance precedence ladder."""
    return resolve_prorrata_register_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).provenance_precedence


def prorrata_referenced_provenances(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> frozenset[ProrrataProvisionalProvenance]:
    """Return registry provenances that require an operator-held reference."""
    return resolve_prorrata_register_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).referenced_provenances


def prorrata_electable_provenances(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> tuple[ProrrataProvisionalProvenance, ...]:
    """Return the registry-authored provenances that may be elected."""
    return resolve_prorrata_register_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).electable_provenances


def prorrata_sector_letters(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> tuple[SectorDiferenciadoLetra, ...]:
    """Return differentiated-sector letters in registry-authored order."""
    return tuple(
        definition.token
        for definition in resolve_prorrata_register_catalogue(
            effective_date=effective_date,
            authority=authority,
        ).sector_letters
    )


def regime_apportions_deduction(
    regime: ProrrataRegisterRegime,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> bool:
    """Return whether a registry-declared regime applies a percentage."""
    catalogue = resolve_prorrata_register_catalogue(effective_date=effective_date, authority=authority)
    token = catalogue.require_regime(regime)
    return token in catalogue.apportioning_regimes


def require_prorrata_register_regime(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> ProrrataRegisterRegime:
    """Validate one value against the dated prorrata register vocabulary."""
    return resolve_prorrata_register_catalogue(effective_date=effective_date, authority=authority).require_regime(value)


def require_prorrata_transition(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> ProrrataEspecialTransitionKind:
    """Validate one value against the dated prorrata transition vocabulary."""
    return resolve_prorrata_register_catalogue(effective_date=effective_date, authority=authority).require_transition(
        value
    )


def require_prorrata_provenance(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> ProrrataProvisionalProvenance:
    """Validate one value against the dated prorrata provenance vocabulary."""
    return resolve_prorrata_register_catalogue(effective_date=effective_date, authority=authority).require_provenance(
        value
    )


def require_sector_diferenciado_letra(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> SectorDiferenciadoLetra:
    """Validate one value against the dated differentiated-sector vocabulary."""
    return resolve_prorrata_register_catalogue(
        effective_date=effective_date, authority=authority
    ).require_sector_letter(value)


__all__ = [
    "aeat_autorizada_prorrata_provenance",
    "carried_prior_definitiva_prorrata_provenance",
    "especial_prorrata_register_regime",
    "general_prorrata_register_regime",
    "inicio_actividad_prorrata_provenance",
    "ninguna_prorrata_register_regime",
    "opcion_prorrata_transition",
    "prorrata_electable_provenances",
    "prorrata_provenance_precedence",
    "prorrata_referenced_provenances",
    "prorrata_sector_letters",
    "regime_apportions_deduction",
    "require_prorrata_provenance",
    "require_prorrata_register_regime",
    "require_prorrata_transition",
    "require_sector_diferenciado_letra",
    "resolve_prorrata_register_catalogue",
    "revocacion_prorrata_transition",
]
