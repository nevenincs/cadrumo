"""Typed models for the registry-owned prorrata-register vocabulary."""

from __future__ import annotations

from dataclasses import dataclass

from ....core.prorrata_register import (
    ProrrataEspecialTransitionKind,
    ProrrataProvisionalProvenance,
    ProrrataRegisterRegime,
    SectorDiferenciadoLetra,
)
from .errors import RegistryValidationError


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
    # register-only entries are appended by the fact. These accessors keep
    # consumers from copying either vocabulary or token values.
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


__all__ = [
    "ProrrataProvenanceDefinition",
    "ProrrataRegisterCatalogue",
    "ProrrataRegisterRegimeDefinition",
    "ProrrataTransitionDefinition",
    "SectorDiferenciadoLetraDefinition",
]
