"""Typed projections for the Modelo 210 tipo-renta catalogue in fact 0080."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from types import MappingProxyType

from ....core.irnr import TipoRentaIrnr
from .errors import RegistryValidationError
from .facts.resolution import MappingFactQuery, ResolvedMappingFact
from .governed_fact_scope import GovernedFactSource, governed_facts_in_scope
from .schema_base import DateAxis

_FACT_ID = "detail-m349-m210-catalogues"
_ORDER_KEY = "m210.tipo_renta.order"
_CODE_ORDER_KEY = "m210.tipo_renta.code_order"
_CODE_PROJECTION_ORDER_KEY = "m210.tipo_renta.code_projection_order"
_FETCH_GATED_KEY = "m210.tipo_renta.fetch_gated_codes"
_PREFIX = "m210.tipo_renta."
_PENSION_VALUE_KEY = "m210.tipo_renta.pension.value"
_INMOBILIARIA_VALUE_KEY = "m210.tipo_renta.inmobiliaria.value"


@dataclass(frozen=True, slots=True)
class TipoRentaIrnrDefinition:
    """One registry-declared IRNR income-type token and its semantics."""

    token: TipoRentaIrnr
    description: str
    legal_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class M210TipoRentaCodeDefinition:
    """One official Modelo 210 code and its registry projection."""

    code: str
    concept: TipoRentaIrnr | None
    rate_legal_ref: str | None
    grounding_tier: str | None
    fetch_gated: bool
    description: str | None


@dataclass(frozen=True, slots=True)
class TipoRentaIrnrCatalogue:
    """Complete typed projection of fact 0080's tipo-renta declarations."""

    definitions: tuple[TipoRentaIrnrDefinition, ...]
    code_definitions: tuple[M210TipoRentaCodeDefinition, ...]
    fetch_gated_codes: frozenset[str]

    @property
    def all_tokens(self) -> frozenset[TipoRentaIrnr]:
        return frozenset(definition.token for definition in self.definitions)

    @property
    def code_projection(self) -> Mapping[str, TipoRentaIrnr]:
        return MappingProxyType(
            {
                definition.code: definition.concept
                for definition in self.code_definitions
                if not definition.fetch_gated and definition.concept is not None
            },
        )

    @property
    def official_codes(self) -> tuple[str, ...]:
        return tuple(definition.code for definition in self.code_definitions)

    def require(self, value: object) -> TipoRentaIrnr:
        """Project one token only when fact 0080 declares it."""
        if isinstance(value, TipoRentaIrnr):
            token = value
        elif isinstance(value, str):
            try:
                token = TipoRentaIrnr._from_registry(value.strip())
            except (TypeError, ValueError) as exc:
                raise RegistryValidationError("tipo_renta must be a non-empty string token") from exc
        else:
            raise RegistryValidationError("tipo_renta must be a string token")
        if token not in self.all_tokens:
            raise RegistryValidationError(
                f"tipo_renta {token.value!r} is not declared by fact {_FACT_ID!r}",
            )
        return token

    def definition(self, value: object) -> TipoRentaIrnrDefinition:
        token = self.require(value)
        return next(definition for definition in self.definitions if definition.token == token)

    def require_code(self, value: object) -> M210TipoRentaCodeDefinition:
        """Resolve an official code, refusing unknown and fetch-gated codes."""
        code = value.strip() if isinstance(value, str) else ""
        definition = next((item for item in self.code_definitions if item.code == code), None)
        if definition is None:
            raise RegistryValidationError(
                f"official Modelo 210 tipo-renta code {code!r} is not declared by fact {_FACT_ID!r}",
            )
        if definition.fetch_gated:
            raise RegistryValidationError(
                f"official Modelo 210 tipo-renta code {code!r} is fetch-gated and has no grounded projection",
            )
        return definition


def _mapping_entries(resolved: ResolvedMappingFact) -> Mapping[str, str]:
    entries: dict[str, str] = {}
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise RegistryValidationError("M349/M210 catalogue entries must be string-to-string")
        if entry.key in entries:
            raise RegistryValidationError(f"duplicate M349/M210 catalogue key {entry.key!r}")
        entries[entry.key] = entry.value
    return MappingProxyType(entries)


def _required(entries: Mapping[str, str], key: str) -> str:
    value = entries.get(key)
    if value is None or not value.strip():
        raise RegistryValidationError(f"M349/M210 catalogue is missing {key!r}")
    return value.strip()


def _csv(entries: Mapping[str, str], key: str) -> tuple[str, ...]:
    values = tuple(token.strip() for token in _required(entries, key).split(",") if token.strip())
    if not values or len(values) != len(set(values)):
        raise RegistryValidationError(f"M349/M210 catalogue {key!r} must contain unique non-empty values")
    return values


def _csv_refs(entries: Mapping[str, str], key: str) -> tuple[str, ...]:
    value = entries.get(key)
    if value is None or not value.strip():
        return ()
    refs = tuple(token.strip() for token in value.split(",") if token.strip())
    if len(refs) != len(set(refs)):
        raise RegistryValidationError(f"M349/M210 catalogue {key!r} must contain unique references")
    return refs


def _resolve_entries(
    *,
    effective_date: date,
    authority: GovernedFactSource,
) -> Mapping[str, str]:
    resolved = authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id=_FACT_ID,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise RegistryValidationError("M349/M210 catalogue must resolve as a mapping fact")
    return _mapping_entries(resolved)


@lru_cache(maxsize=64)
def _bundled_entries(effective_date: date) -> Mapping[str, str]:
    from .authority import bundled_authority

    return _resolve_entries(effective_date=effective_date, authority=bundled_authority())


def _selected_entries(
    *,
    effective_date: date | None,
    authority: GovernedFactSource | None,
) -> Mapping[str, str]:
    coordinate = effective_date or date.today()
    selected = authority or governed_facts_in_scope()
    if selected is None:
        return _bundled_entries(coordinate)
    return _resolve_entries(effective_date=coordinate, authority=selected)


def resolve_tipo_renta_irnr_catalogue(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> TipoRentaIrnrCatalogue:
    """Resolve and validate every tipo-renta/category/code declaration in 0080."""
    entries = _selected_entries(effective_date=effective_date, authority=authority)
    definitions: list[TipoRentaIrnrDefinition] = []
    for raw_token in _csv(entries, _ORDER_KEY):
        token = TipoRentaIrnr._from_registry(raw_token)
        prefix = f"{_PREFIX}{raw_token}"
        if _required(entries, f"{prefix}.value") != raw_token:
            raise RegistryValidationError(f"tipo-renta token {raw_token!r} declares a mismatched value")
        definitions.append(
            TipoRentaIrnrDefinition(
                token=token,
                description=_required(entries, f"{prefix}.description"),
                legal_refs=_csv_refs(entries, f"{prefix}.legal_refs"),
            ),
        )

    catalogue = TipoRentaIrnrCatalogue(
        definitions=tuple(definitions),
        code_definitions=(),
        fetch_gated_codes=frozenset(_csv(entries, _FETCH_GATED_KEY)),
    )
    all_tokens = catalogue.all_tokens
    projection_codes = _csv(entries, _CODE_PROJECTION_ORDER_KEY)
    official_codes = _csv(entries, _CODE_ORDER_KEY)
    if set(catalogue.fetch_gated_codes) - set(official_codes):
        raise RegistryValidationError("fetch-gated tipo-renta codes must be present in code_order")
    if set(projection_codes) & catalogue.fetch_gated_codes:
        raise RegistryValidationError("projected and fetch-gated tipo-renta codes must be disjoint")
    if set(projection_codes) | catalogue.fetch_gated_codes != set(official_codes):
        raise RegistryValidationError("tipo-renta code_order must equal projected plus fetch-gated codes")

    code_definitions: list[M210TipoRentaCodeDefinition] = []
    for code in official_codes:
        if len(code) != 2 or not code.isdecimal():
            raise RegistryValidationError(f"official tipo-renta code {code!r} must be a two-digit decimal token")
        prefix = f"{_PREFIX}code.{code}"
        if code in catalogue.fetch_gated_codes:
            if _required(entries, f"{prefix}.status") != "fetch_gated":
                raise RegistryValidationError(f"fetch-gated tipo-renta code {code!r} lacks fetch_gated status")
            code_definitions.append(
                M210TipoRentaCodeDefinition(
                    code=code,
                    concept=None,
                    rate_legal_ref=None,
                    grounding_tier=None,
                    fetch_gated=True,
                    description=_required(entries, f"{prefix}.description"),
                ),
            )
            continue
        if code not in projection_codes:
            raise RegistryValidationError(f"tipo-renta code {code!r} is neither projected nor fetch-gated")
        concept = catalogue.require(_required(entries, f"{prefix}.concept"))
        code_definitions.append(
            M210TipoRentaCodeDefinition(
                code=code,
                concept=concept,
                rate_legal_ref=_required(entries, f"{prefix}.rate_legal_ref"),
                grounding_tier=_required(entries, f"{prefix}.grounding_tier"),
                fetch_gated=False,
                description=None,
            ),
        )
    if not all(definition.concept in all_tokens for definition in code_definitions if definition.concept is not None):
        raise RegistryValidationError("tipo-renta code projection contains an undeclared concept")
    return TipoRentaIrnrCatalogue(
        definitions=tuple(definitions),
        code_definitions=tuple(code_definitions),
        fetch_gated_codes=catalogue.fetch_gated_codes,
    )


def require_tipo_renta_irnr(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> TipoRentaIrnr:
    """Return a tipo-renta token only when the selected 0080 fact declares it."""
    return resolve_tipo_renta_irnr_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).require(value)


def m210_tipo_renta_code_projection(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> Mapping[str, TipoRentaIrnr]:
    """Return the published-code to conceptual-token projection from 0080."""
    return resolve_tipo_renta_irnr_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).code_projection


def m210_fetch_gated_tipo_renta_codes(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> frozenset[str]:
    """Return official codes whose rate projection is explicitly fetch-gated."""
    return resolve_tipo_renta_irnr_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).fetch_gated_codes


def tipo_renta_pension_token(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> TipoRentaIrnr:
    """Return the pension semantic token declared by fact 0080."""
    entries = _selected_entries(effective_date=effective_date, authority=authority)
    return require_tipo_renta_irnr(
        _required(entries, _PENSION_VALUE_KEY),
        effective_date=effective_date,
        authority=authority,
    )


def tipo_renta_inmobiliaria_token(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> TipoRentaIrnr:
    """Return the real-estate income token declared by fact 0080."""
    entries = _selected_entries(effective_date=effective_date, authority=authority)
    return require_tipo_renta_irnr(
        _required(entries, _INMOBILIARIA_VALUE_KEY),
        effective_date=effective_date,
        authority=authority,
    )


__all__ = [
    "M210TipoRentaCodeDefinition",
    "TipoRentaIrnrCatalogue",
    "TipoRentaIrnrDefinition",
    "m210_fetch_gated_tipo_renta_codes",
    "m210_tipo_renta_code_projection",
    "require_tipo_renta_irnr",
    "resolve_tipo_renta_irnr_catalogue",
    "tipo_renta_inmobiliaria_token",
    "tipo_renta_pension_token",
]
