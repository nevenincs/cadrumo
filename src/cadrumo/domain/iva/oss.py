"""Opaque OSS / IOSS regime tokens projected from the facts authority."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType

from ..calculations.registry.errors import RegistryValidationError
from ..calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ..calculations.registry.governed_fact_scope import GovernedFactSource, governed_facts_in_scope
from ..calculations.registry.schema_base import DateAxis

_FACT_ID = "modelo-369-exterior-oss-projection-catalogue"
_ORDER_KEY = "regime.order"
_COMMON_SEMANTICS_KEY = "regime.common_semantics"
_SELECTOR_KEY = "regime.selector"


class OssIossRegime(str):
    """Opaque registry-projected OSS / IOSS regime token."""

    __slots__ = ()

    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type: object, _handler: object) -> object:
        """Expose the opaque token as a string to Pydantic without a catalogue."""
        from pydantic_core import core_schema

        return core_schema.no_info_after_validator_function(cls, core_schema.str_schema())

    @property
    def value(self) -> str:
        """Return the opaque token for string-oriented serialization."""
        return str(self)


@dataclass(frozen=True, slots=True)
class OssIossRegimeDefinition:
    """One registry-declared OSS / IOSS regime and its legal semantics."""

    token: OssIossRegime
    description: str
    articles: str
    filing_cadence: str
    transaction_kinds: tuple[str, ...]
    intrinsic_value_ceiling_eur: str | None = None


@dataclass(frozen=True, slots=True)
class OssIossRegimeCatalogue:
    """Typed projection of the dated Modelo 369 OSS/IOSS mapping fact."""

    definitions: tuple[OssIossRegimeDefinition, ...]
    common_semantics: str
    selector_key: str

    @property
    def all_regimes(self) -> frozenset[OssIossRegime]:
        """Return every regime token declared by the registry."""
        return frozenset(definition.token for definition in self.definitions)

    def require(self, value: object) -> OssIossRegime:
        """Validate one opaque regime token against this projection."""
        if isinstance(value, OssIossRegime):
            token = value
        elif isinstance(value, str):
            token = OssIossRegime(value.strip())
        else:
            raise RegistryValidationError("OSS/IOSS regime must be a string token")
        if not str(token):
            raise RegistryValidationError("OSS/IOSS regime token must not be blank")
        if token not in self.all_regimes:
            raise RegistryValidationError(f"OSS/IOSS regime {str(token)!r} is not registry-declared")
        return token

    def definition(self, value: object) -> OssIossRegimeDefinition:
        """Return the registry definition for one regime token."""
        token = self.require(value)
        for definition in self.definitions:
            if definition.token == token:
                return definition
        raise RegistryValidationError(f"OSS/IOSS regime {str(token)!r} has no registry definition")

    def transaction_kinds_for(self, value: object) -> frozenset[str]:
        """Return transaction-kind values admitted by one registry regime."""
        return frozenset(self.definition(value).transaction_kinds)

    def regime_for_transaction_kind(self, transaction_kind: str) -> OssIossRegime:
        """Return the unique registry regime admitting a transaction kind."""
        matches = tuple(
            definition.token for definition in self.definitions if transaction_kind in definition.transaction_kinds
        )
        if len(matches) != 1:
            raise RegistryValidationError(
                f"transaction kind {transaction_kind!r} must map to exactly one OSS/IOSS regime",
            )
        return matches[0]


def _mapping_entries(resolved: ResolvedMappingFact) -> Mapping[str, str]:
    """Narrow a resolved mapping payload to a unique string-to-string map."""
    entries: dict[str, str] = {}
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise RegistryValidationError("OSS/IOSS regime entries must be string-to-string")
        if entry.key in entries:
            raise RegistryValidationError(f"duplicate OSS/IOSS regime key {entry.key!r}")
        entries[entry.key] = entry.value
    return MappingProxyType(entries)


def _required(entries: Mapping[str, str], key: str) -> str:
    value = entries.get(key)
    if value is None or not value.strip():
        raise RegistryValidationError(f"OSS/IOSS regime mapping is missing {key!r}")
    return value.strip()


def _csv_tokens(entries: Mapping[str, str], key: str) -> tuple[str, ...]:
    tokens = tuple(token.strip() for token in _required(entries, key).split(",") if token.strip())
    if not tokens or len(set(tokens)) != len(tokens):
        raise RegistryValidationError(f"OSS/IOSS regime mapping {key!r} must declare unique tokens")
    return tokens


def resolve_oss_ioss_regime_catalogue(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> OssIossRegimeCatalogue:
    """Resolve the complete OSS / IOSS regime catalogue through facts authority."""
    authority = authority or governed_facts_in_scope()
    if authority is None:
        raise RegistryValidationError(
            "OSS/IOSS regime catalogue requires an explicit authority operation or scope",
        )
    resolved = authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id=_FACT_ID,
            date_axis=DateAxis.TRANSACTION_DATE,
            effective_date=effective_date or date.today(),
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise RegistryValidationError("Modelo 369 OSS/IOSS projection must resolve as a mapping fact")
    entries = _mapping_entries(resolved)
    ordered_tokens = _csv_tokens(entries, _ORDER_KEY)
    definitions: list[OssIossRegimeDefinition] = []
    for token in ordered_tokens:
        prefix = f"regime.{token}"
        ceiling_key = f"{prefix}.intrinsic_value_ceiling_eur"
        definitions.append(
            OssIossRegimeDefinition(
                token=OssIossRegime(token),
                description=_required(entries, f"{prefix}.description"),
                articles=_required(entries, f"{prefix}.articles"),
                filing_cadence=_required(entries, f"{prefix}.filing_cadence"),
                transaction_kinds=_csv_tokens(entries, f"{prefix}.transaction_kinds"),
                intrinsic_value_ceiling_eur=entries.get(ceiling_key),
            ),
        )
    return OssIossRegimeCatalogue(
        definitions=tuple(definitions),
        common_semantics=_required(entries, _COMMON_SEMANTICS_KEY),
        selector_key=_required(entries, _SELECTOR_KEY),
    )


def require_oss_ioss_regime(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> OssIossRegime:
    """Return one registry-declared OSS/IOSS token or refuse it."""
    return resolve_oss_ioss_regime_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).require(value)


__all__ = [
    "OssIossRegime",
    "OssIossRegimeCatalogue",
    "OssIossRegimeDefinition",
    "require_oss_ioss_regime",
    "resolve_oss_ioss_regime_catalogue",
]
