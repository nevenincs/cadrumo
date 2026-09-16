"""Typed projections of the registry-owned prorrata-register vocabularies."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import Final

from ....core.prorrata_register import (
    ProrrataEspecialTransitionKind,
    ProrrataProvisionalProvenance,
    ProrrataRegisterRegime,
    SectorDiferenciadoLetra,
)
from .errors import RegistryValidationError
from .facts.resolution import MappingFactQuery, ResolvedMappingFact, required_mapping_entry
from .governed_fact_scope import GovernedFactSource, governed_facts_in_scope
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


@dataclass(frozen=True, slots=True)
class ProrrataRegisterRegimeDefinition:
    """One registry-declared register regime and its applicability metadata."""

    token: ProrrataRegisterRegime
    description: str
    legal_ref: str
    apportions: bool


@dataclass(frozen=True, slots=True)
class ProrrataTransitionDefinition:
    """One registry-declared special-prorrata transition kind."""

    token: ProrrataEspecialTransitionKind
    description: str
    legal_ref: str


@dataclass(frozen=True, slots=True)
class ProrrataProvenanceDefinition:
    """One registry-declared art. 105 provisional provenance."""

    token: ProrrataProvisionalProvenance
    description: str
    legal_ref: str
    authorisation_required: bool
    election_allowed: bool


@dataclass(frozen=True, slots=True)
class SectorDiferenciadoLetraDefinition:
    """One registry-declared LIVA art. 9.1.c sector letter."""

    token: SectorDiferenciadoLetra
    description: str
    legal_ref: str


@dataclass(frozen=True, slots=True)
class ProrrataRegisterCatalogue:
    """Complete typed projection of the dated 0116 register vocabulary."""

    regimes: tuple[ProrrataRegisterRegimeDefinition, ...]
    transition_kinds: tuple[ProrrataTransitionDefinition, ...]
    provenances: tuple[ProrrataProvenanceDefinition, ...]
    sector_letters: tuple[SectorDiferenciadoLetraDefinition, ...]

    @property
    def all_regimes(self) -> frozenset[ProrrataRegisterRegime]:
        """Return every register regime declared by the registry."""
        return frozenset(definition.token for definition in self.regimes)

    @property
    def apportioning_regimes(self) -> tuple[ProrrataRegisterRegime, ...]:
        """Return registry regimes that apportion deductible amounts."""
        return tuple(definition.token for definition in self.regimes if definition.apportions)

    @property
    def non_apportioning_regimes(self) -> tuple[ProrrataRegisterRegime, ...]:
        """Return registry regimes that do not apportion deductible amounts."""
        return tuple(definition.token for definition in self.regimes if not definition.apportions)

    @property
    def all_transition_kinds(self) -> frozenset[ProrrataEspecialTransitionKind]:
        """Return every special-prorrata transition declared by the registry."""
        return frozenset(definition.token for definition in self.transition_kinds)

    @property
    def all_provenances(self) -> frozenset[ProrrataProvisionalProvenance]:
        """Return every provisional provenance declared by the registry."""
        return frozenset(definition.token for definition in self.provenances)

    @property
    def all_sector_letters(self) -> frozenset[SectorDiferenciadoLetra]:
        """Return every differentiated-sector letter declared by the registry."""
        return frozenset(definition.token for definition in self.sector_letters)

    @property
    def referenced_provenances(self) -> frozenset[ProrrataProvisionalProvenance]:
        """Return provenances that require an authorisation reference."""
        return frozenset(definition.token for definition in self.provenances if definition.authorisation_required)

    @property
    def electable_provenances(self) -> tuple[ProrrataProvisionalProvenance, ...]:
        """Return provenances that the operator may elect."""
        return tuple(definition.token for definition in self.provenances if definition.election_allowed)

    def require_regime(self, value: object) -> ProrrataRegisterRegime:
        """Validate and return one registry-declared register regime."""
        token = _coerce_regime(value)
        if token not in self.all_regimes:
            raise RegistryValidationError(
                f"prorrata register regime {str(token)!r} is not declared by the facts registry",
            )
        return token

    def require_transition(self, value: object) -> ProrrataEspecialTransitionKind:
        """Validate and return one registry-declared transition kind."""
        token = _coerce_transition(value)
        if token not in self.all_transition_kinds:
            raise RegistryValidationError(
                f"prorrata especial transition {str(token)!r} is not declared by the facts registry",
            )
        return token

    def require_provenance(self, value: object) -> ProrrataProvisionalProvenance:
        """Validate and return one registry-declared provisional provenance."""
        token = _coerce_provenance(value)
        if token not in self.all_provenances:
            raise RegistryValidationError(
                f"prorrata provisional provenance {str(token)!r} is not declared by the facts registry",
            )
        return token

    def require_sector_letter(self, value: object) -> SectorDiferenciadoLetra:
        """Validate and return one registry-declared differentiated-sector letter."""
        token = _coerce_sector_letter(value)
        if token not in self.all_sector_letters:
            raise RegistryValidationError(
                f"differentiated-sector letter {str(token)!r} is not declared by the facts registry",
            )
        return token

    # The first two entries are the existing canonical general/especial order;
    # the additional register-only entries are appended by the fact. These
    # accessors keep consumers from copying either vocabulary or token values.
    @property
    def general_regime(self) -> ProrrataRegisterRegime:
        """Return the first, general regime in registry order."""
        return self.regimes[0].token

    @property
    def especial_regime(self) -> ProrrataRegisterRegime:
        """Return the second, special regime in registry order."""
        return self.regimes[1].token

    @property
    def no_prorrata_regime(self) -> ProrrataRegisterRegime:
        """Return the sole non-apportioning regime declared by the registry."""
        non_apportioning = self.non_apportioning_regimes
        if len(non_apportioning) != 1:
            raise RegistryValidationError("0116 must declare exactly one non-apportioning register regime")
        return non_apportioning[0]

    @property
    def opcion_transition(self) -> ProrrataEspecialTransitionKind:
        """Return the first special-prorrata transition in registry order."""
        return self.transition_kinds[0].token

    @property
    def revocacion_transition(self) -> ProrrataEspecialTransitionKind:
        """Return the second special-prorrata transition in registry order."""
        return self.transition_kinds[1].token

    @property
    def aeat_autorizada_provenance(self) -> ProrrataProvisionalProvenance:
        """Return the AEAT-authorised provenance in registry order."""
        return self.provenances[0].token

    @property
    def inicio_actividad_provenance(self) -> ProrrataProvisionalProvenance:
        """Return the activity-start provenance in registry order."""
        return self.provenances[1].token

    @property
    def carried_prior_definitiva_provenance(self) -> ProrrataProvisionalProvenance:
        """Return the carried prior definitive provenance in registry order."""
        return self.provenances[2].token

    @property
    def provenance_precedence(self) -> tuple[ProrrataProvisionalProvenance, ...]:
        """Return provisional provenances in their registry precedence order."""
        return tuple(definition.token for definition in self.provenances)


def _coerce_regime(value: object) -> ProrrataRegisterRegime:
    if isinstance(value, ProrrataRegisterRegime):
        token = value
    elif isinstance(value, str):
        try:
            token = ProrrataRegisterRegime.from_registry(value.strip())
        except (TypeError, ValueError) as exc:
            raise RegistryValidationError("prorrata register regime must be a non-empty registry token") from exc
    else:
        raise RegistryValidationError("prorrata register regime must be a registry-projected string token")
    if not str(token):
        raise RegistryValidationError("prorrata register regime must not be blank")
    return token


def _coerce_transition(value: object) -> ProrrataEspecialTransitionKind:
    if isinstance(value, ProrrataEspecialTransitionKind):
        token = value
    elif isinstance(value, str):
        try:
            token = ProrrataEspecialTransitionKind.from_registry(value.strip())
        except (TypeError, ValueError) as exc:
            raise RegistryValidationError("prorrata especial transition must be a non-empty registry token") from exc
    else:
        raise RegistryValidationError("prorrata especial transition must be a registry-projected string token")
    if not str(token):
        raise RegistryValidationError("prorrata especial transition must not be blank")
    return token


def _coerce_provenance(value: object) -> ProrrataProvisionalProvenance:
    if isinstance(value, ProrrataProvisionalProvenance):
        token = value
    elif isinstance(value, str):
        try:
            token = ProrrataProvisionalProvenance.from_registry(value.strip())
        except (TypeError, ValueError) as exc:
            raise RegistryValidationError("prorrata provisional provenance must be a non-empty registry token") from exc
    else:
        raise RegistryValidationError("prorrata provisional provenance must be a registry-projected string token")
    if not str(token):
        raise RegistryValidationError("prorrata provisional provenance must not be blank")
    return token


def _coerce_sector_letter(value: object) -> SectorDiferenciadoLetra:
    if isinstance(value, SectorDiferenciadoLetra):
        token = value
    elif isinstance(value, str):
        try:
            token = SectorDiferenciadoLetra.from_registry(value.strip())
        except (TypeError, ValueError) as exc:
            raise RegistryValidationError("differentiated-sector letter must be a non-empty registry token") from exc
    else:
        raise RegistryValidationError("differentiated-sector letter must be a registry-projected string token")
    if not str(token):
        raise RegistryValidationError("differentiated-sector letter must not be blank")
    return token


def _mapping_entries(resolved: ResolvedMappingFact) -> Mapping[str, str]:
    entries: dict[str, str] = {}
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise RegistryValidationError("prorrata register mapping entries must be string-to-string")
        if entry.key in entries:
            raise RegistryValidationError(f"duplicate prorrata register mapping key {entry.key!r}")
        entries[entry.key] = entry.value
    return MappingProxyType(entries)


def _csv(entries: Mapping[str, str], key: str) -> tuple[str, ...]:
    values = tuple(
        token.strip()
        for token in required_mapping_entry(entries, key, subject=_ENTRY_SUBJECT).split(",")
        if token.strip()
    )
    if not values or len(values) != len(set(values)):
        raise RegistryValidationError(f"prorrata register mapping {key!r} must contain unique tokens")
    return values


def _boolean(entries: Mapping[str, str], key: str) -> bool:
    value = required_mapping_entry(entries, key, subject=_ENTRY_SUBJECT).lower()
    if value == "true":
        return True
    if value == "false":
        return False
    raise RegistryValidationError(f"prorrata register mapping {key!r} must be true or false")


def _resolve_entries(*, effective_date: date, authority: GovernedFactSource) -> Mapping[str, str]:
    resolved = authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id=_FACT_ID,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise RegistryValidationError("Renta IVA ratio policy must resolve as a mapping fact")
    return _mapping_entries(resolved)


def resolve_prorrata_register_catalogue(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> ProrrataRegisterCatalogue:
    """Resolve all register vocabularies through the dated 0116 mapping fact."""
    coordinate = effective_date or date.today()
    selected = authority or governed_facts_in_scope()
    if selected is None:
        raise RegistryValidationError("prorrata register catalogue requires an explicit authority operation or scope")
    entries = _resolve_entries(effective_date=coordinate, authority=selected)

    regime_tokens = (*_csv(entries, _REGIME_ORDER_KEY), *_csv(entries, _REGISTER_REGIME_ADDITIONS_KEY))
    regimes: list[ProrrataRegisterRegimeDefinition] = []
    for raw_token in regime_tokens:
        prefix = f"{_REGIME_PREFIX}{raw_token}"
        token = ProrrataRegisterRegime.from_registry(
            required_mapping_entry(entries, f"{prefix}.value", subject=_ENTRY_SUBJECT)
        )
        if str(token) != raw_token:
            raise RegistryValidationError(f"register regime {raw_token!r} declares a mismatched value")
        regimes.append(
            ProrrataRegisterRegimeDefinition(
                token=token,
                description=required_mapping_entry(entries, f"{prefix}.description", subject=_ENTRY_SUBJECT),
                legal_ref=required_mapping_entry(entries, f"{prefix}.legal_ref", subject=_ENTRY_SUBJECT),
                apportions=_boolean(entries, f"{prefix}.apportions"),
            ),
        )

    transition_kinds: list[ProrrataTransitionDefinition] = []
    for raw_token in _csv(entries, _TRANSITION_ORDER_KEY):
        prefix = f"{_TRANSITION_PREFIX}{raw_token}"
        token = ProrrataEspecialTransitionKind.from_registry(
            required_mapping_entry(entries, f"{prefix}.value", subject=_ENTRY_SUBJECT)
        )
        if str(token) != raw_token:
            raise RegistryValidationError(f"transition {raw_token!r} declares a mismatched value")
        transition_kinds.append(
            ProrrataTransitionDefinition(
                token=token,
                description=required_mapping_entry(entries, f"{prefix}.description", subject=_ENTRY_SUBJECT),
                legal_ref=required_mapping_entry(entries, f"{prefix}.legal_ref", subject=_ENTRY_SUBJECT),
            ),
        )

    provenances: list[ProrrataProvenanceDefinition] = []
    for raw_token in _csv(entries, _PROVENANCE_ORDER_KEY):
        prefix = f"{_PROVENANCE_PREFIX}{raw_token}"
        token = ProrrataProvisionalProvenance.from_registry(
            required_mapping_entry(entries, f"{prefix}.value", subject=_ENTRY_SUBJECT)
        )
        if str(token) != raw_token:
            raise RegistryValidationError(f"provenance {raw_token!r} declares a mismatched value")
        provenances.append(
            ProrrataProvenanceDefinition(
                token=token,
                description=required_mapping_entry(entries, f"{prefix}.description", subject=_ENTRY_SUBJECT),
                legal_ref=required_mapping_entry(entries, f"{prefix}.legal_ref", subject=_ENTRY_SUBJECT),
                authorisation_required=_boolean(entries, f"{prefix}.authorisation_required"),
                election_allowed=_boolean(entries, f"{prefix}.election_allowed"),
            ),
        )

    sector_letters: list[SectorDiferenciadoLetraDefinition] = []
    for raw_token in _csv(entries, _SECTOR_ORDER_KEY):
        prefix = f"{_SECTOR_PREFIX}{raw_token}"
        token = SectorDiferenciadoLetra.from_registry(
            required_mapping_entry(entries, f"{prefix}.value", subject=_ENTRY_SUBJECT)
        )
        if str(token) != raw_token:
            raise RegistryValidationError(f"sector letter {raw_token!r} declares a mismatched value")
        sector_letters.append(
            SectorDiferenciadoLetraDefinition(
                token=token,
                description=required_mapping_entry(entries, f"{prefix}.description", subject=_ENTRY_SUBJECT),
                legal_ref=required_mapping_entry(entries, f"{prefix}.legal_ref", subject=_ENTRY_SUBJECT),
            ),
        )

    catalogue = ProrrataRegisterCatalogue(
        regimes=tuple(regimes),
        transition_kinds=tuple(transition_kinds),
        provenances=tuple(provenances),
        sector_letters=tuple(sector_letters),
    )
    if len(catalogue.regimes) < 3 or len(catalogue.apportioning_regimes) != 2:
        raise RegistryValidationError("0116 must retain the two canonical apportioning regimes and add register states")
    if len(catalogue.transition_kinds) != 2 or len(catalogue.provenances) != 4 or len(catalogue.sector_letters) != 4:
        raise RegistryValidationError("0116 register vocabulary cardinalities do not match the declared scope")
    if not set(catalogue.apportioning_regimes).issubset(catalogue.all_regimes):
        raise RegistryValidationError("0116 apportioning regimes must be declared in the regime vocabulary")
    return catalogue


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
    """Return the registry-declared inicio-de-actividad provenance token."""
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
    "ProrrataProvenanceDefinition",
    "ProrrataRegisterCatalogue",
    "ProrrataRegisterRegimeDefinition",
    "ProrrataTransitionDefinition",
    "SectorDiferenciadoLetraDefinition",
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
