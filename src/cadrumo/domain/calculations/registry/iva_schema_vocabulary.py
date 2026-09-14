"""Typed projections for the IVA schema vocabulary fact (0098)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from types import MappingProxyType
from typing import TypeVar

from ....domain.deadlines.models import IVARegime, M303RegimeComposition, M303TaxTerritory
from ....domain.iva.regimen_simplificado_rows import M303RegimenSimplificadoScope
from ....domain.iva.schema import IvaArt69DosService, IvaCashAccountingTreatment, IvaExemptionArticle
from .errors import RegistryValidationError
from .facts.resolution import MappingFactQuery, ResolvedMappingFact
from .governed_fact_scope import GovernedFactSource, governed_facts_in_scope
from .schema_base import DateAxis

_FACT_ID = "iva-statutory-schema-vocabulary"
_CASH_ORDER_KEY = "cash_accounting.order"
_CASH_NONE_KEY = "cash_accounting.none_token"
_CASH_SUPPLIER_KEY = "cash_accounting.supplier_regime_token"
_EXEMPTION_ORDER_KEY = "exemption_article.order"
_SERVICE_ORDER_KEY = "art_69_dos_service.order"
_REGIME_ORDER_KEY = "iva_regime.order"
_REGIME_DEFAULT_KEY = "iva_regime.default_token"
_REGIME_NO_APLICA_KEY = "iva_regime.no_aplica_token"
_REGIME_SELF_ASSESSMENT_KEY = "iva_regime.self_assessment_order"
_REGIME_SIMPLIFICADO_KEY = "iva_regime.simplificado_token"
_REGIME_REAGP_KEY = "iva_regime.reagp_token"
_REGIME_EXENTO_KEY = "iva_regime.exento_token"
_TERRITORY_ORDER_KEY = "tax_territory.order"
_COMPOSITION_ORDER_KEY = "m303_regime_composition.order"
_CASH_PREFIX = "cash_accounting."
_EXEMPTION_PREFIX = "exemption_article."
_SERVICE_PREFIX = "art_69_dos_service."
_REGIME_PREFIX = "iva_regime."
_TERRITORY_PREFIX = "tax_territory."
_COMPOSITION_PREFIX = "m303_regime_composition."

TokenT = TypeVar(
    "TokenT",
    IVARegime,
    M303RegimeComposition,
    IvaCashAccountingTreatment,
    IvaExemptionArticle,
    IvaArt69DosService,
)


@dataclass(frozen=True, slots=True)
class IvaCashAccountingTreatmentDefinition:
    """One registry-declared cash-accounting treatment and its semantics."""

    token: IvaCashAccountingTreatment
    description: str
    legal_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class IvaCashAccountingTreatmentCatalogue:
    """Typed projection of the dated cash-accounting vocabulary."""

    definitions: tuple[IvaCashAccountingTreatmentDefinition, ...]
    none_token: IvaCashAccountingTreatment
    supplier_regime_token: IvaCashAccountingTreatment

    @property
    def all_treatments(self) -> frozenset[IvaCashAccountingTreatment]:
        return frozenset(definition.token for definition in self.definitions)

    def require(self, value: object) -> IvaCashAccountingTreatment:
        if isinstance(value, IvaCashAccountingTreatment):
            token = value
        elif isinstance(value, str):
            token = IvaCashAccountingTreatment(value.strip())
        else:
            raise RegistryValidationError("cash-accounting treatment must be a string token")
        if not str(token) or token not in self.all_treatments:
            raise RegistryValidationError(
                f"cash-accounting treatment {str(token)!r} is not declared by the facts registry",
            )
        return token

    def definition(self, value: object) -> IvaCashAccountingTreatmentDefinition:
        token = self.require(value)
        return next(definition for definition in self.definitions if definition.token == token)


@dataclass(frozen=True, slots=True)
class IvaRegimeDefinition:
    """One registry-declared IVA regime and its deadline semantics."""

    token: IVARegime
    description: str
    deadline_applicability: str
    legal_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class IvaRegimeCatalogue:
    """Typed projection of the dated IVA regime vocabulary."""

    definitions: tuple[IvaRegimeDefinition, ...]
    default_token: IVARegime
    no_aplica_token: IVARegime
    self_assessment_tokens: frozenset[IVARegime]

    @property
    def all_regimes(self) -> frozenset[IVARegime]:
        return frozenset(definition.token for definition in self.definitions)

    @property
    def selectable_regimes(self) -> tuple[IVARegime, ...]:
        return tuple(definition.token for definition in self.definitions if definition.token != self.no_aplica_token)

    def require(self, value: object) -> IVARegime:
        return _require_token(value, IVARegime, self.all_regimes, "IVA regime")

    def definition(self, value: object) -> IvaRegimeDefinition:
        token = self.require(value)
        return next(definition for definition in self.definitions if definition.token == token)


@dataclass(frozen=True, slots=True)
class M303TaxTerritoryDefinition:
    """One registry-declared Modelo 303 tax-territory token and semantics."""

    token: M303TaxTerritory
    description: str
    legal_refs: tuple[str, ...]
    is_foral: bool
    state_attribution_ratio: Decimal
    exclusively_foral_mark: str


@dataclass(frozen=True, slots=True)
class M303TaxTerritoryCatalogue:
    """Typed projection of the dated Modelo 303 territory vocabulary."""

    definitions: tuple[M303TaxTerritoryDefinition, ...]

    @property
    def all_territories(self) -> frozenset[M303TaxTerritory]:
        return frozenset(definition.token for definition in self.definitions)

    @property
    def choices(self) -> tuple[M303TaxTerritory, ...]:
        return tuple(definition.token for definition in self.definitions)

    @property
    def foral_token(self) -> M303TaxTerritory:
        matches = tuple(definition.token for definition in self.definitions if definition.is_foral)
        if len(matches) != 1:
            raise RegistryValidationError("Modelo 303 tax-territory catalogue must declare exactly one foral token")
        return matches[0]

    def require(self, value: object) -> M303TaxTerritory:
        if isinstance(value, M303TaxTerritory):
            token = value
        elif isinstance(value, str):
            raw = value.strip()
            if not raw:
                raise RegistryValidationError("Modelo 303 tax-territory token must be non-empty")
            if raw not in {str(member) for member in self.all_territories}:
                raise RegistryValidationError(
                    f"Modelo 303 tax-territory token {raw!r} is not declared by the facts registry",
                )
            token = M303TaxTerritory._from_registry(raw)
        else:
            raise RegistryValidationError("Modelo 303 tax-territory token must be a string token")
        if token not in self.all_territories:
            raise RegistryValidationError(
                f"Modelo 303 tax-territory token {str(token)!r} is not declared by the facts registry",
            )
        return token

    def definition(self, value: object) -> M303TaxTerritoryDefinition:
        token = self.require(value)
        return next(definition for definition in self.definitions if definition.token == token)


@dataclass(frozen=True, slots=True)
class M303RegimeCompositionDefinition:
    """One registry-declared Modelo 303 regime-composition token and semantics."""

    token: M303RegimeComposition
    description: str
    export_code: str
    simplified_scope: str
    legal_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class M303RegimeCompositionCatalogue:
    """Typed projection of the dated Modelo 303 composition vocabulary."""

    definitions: tuple[M303RegimeCompositionDefinition, ...]

    @property
    def all_compositions(self) -> frozenset[M303RegimeComposition]:
        return frozenset(definition.token for definition in self.definitions)

    @property
    def choices(self) -> tuple[M303RegimeComposition, ...]:
        return tuple(definition.token for definition in self.definitions)

    def require(self, value: object) -> M303RegimeComposition:
        if isinstance(value, M303RegimeComposition):
            token = value
        elif isinstance(value, str):
            raw = value.strip()
            if not raw:
                raise RegistryValidationError("Modelo 303 regime-composition token must be non-empty")
            if raw not in {str(member) for member in self.all_compositions}:
                raise RegistryValidationError(
                    f"Modelo 303 regime-composition token {raw!r} is not declared by the facts registry",
                )
            token = M303RegimeComposition._from_registry(raw)
        else:
            raise RegistryValidationError("Modelo 303 regime-composition token must be a string token")
        if token not in self.all_compositions:
            raise RegistryValidationError(
                f"Modelo 303 regime-composition token {str(token)!r} is not declared by the facts registry",
            )
        return token

    def definition(self, value: object) -> M303RegimeCompositionDefinition:
        token = self.require(value)
        return next(definition for definition in self.definitions if definition.token == token)


@dataclass(frozen=True, slots=True)
class IvaExemptionArticleDefinition:
    """One registry-declared IVA exemption article token and semantics."""

    token: IvaExemptionArticle
    description: str
    legal_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class IvaExemptionArticleCatalogue:
    """Typed projection of the dated exemption-article vocabulary."""

    definitions: tuple[IvaExemptionArticleDefinition, ...]

    @property
    def all_articles(self) -> frozenset[IvaExemptionArticle]:
        return frozenset(definition.token for definition in self.definitions)

    def require(self, value: object) -> IvaExemptionArticle:
        return _require_token(value, IvaExemptionArticle, self.all_articles, "exemption article")

    def definition(self, value: object) -> IvaExemptionArticleDefinition:
        token = self.require(value)
        return next(definition for definition in self.definitions if definition.token == token)


@dataclass(frozen=True, slots=True)
class IvaArt69DosServiceDefinition:
    """One registry-declared Art. 69.Dos service token and semantics."""

    token: IvaArt69DosService
    description: str
    legal_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class IvaArt69DosServiceCatalogue:
    """Typed projection of the dated Art. 69.Dos service vocabulary."""

    definitions: tuple[IvaArt69DosServiceDefinition, ...]

    @property
    def all_services(self) -> frozenset[IvaArt69DosService]:
        return frozenset(definition.token for definition in self.definitions)

    def require(self, value: object) -> IvaArt69DosService:
        return _require_token(value, IvaArt69DosService, self.all_services, "Art. 69.Dos service")

    def definition(self, value: object) -> IvaArt69DosServiceDefinition:
        token = self.require(value)
        return next(definition for definition in self.definitions if definition.token == token)


def _require_token(
    value: object,
    token_type: type[TokenT],
    members: frozenset[TokenT],
    label: str,
) -> TokenT:
    if isinstance(value, token_type):
        token = value
    elif isinstance(value, str):
        token = token_type(value.strip())
    else:
        raise RegistryValidationError(f"{label} must be a string token")
    if not str(token) or token not in members:
        raise RegistryValidationError(f"{label} {str(token)!r} is not declared by the facts registry")
    return token


def _mapping_entries(resolved: ResolvedMappingFact) -> Mapping[str, str]:
    entries: dict[str, str] = {}
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise RegistryValidationError("IVA schema vocabulary entries must be string-to-string")
        if entry.key in entries:
            raise RegistryValidationError(f"duplicate IVA schema vocabulary key {entry.key!r}")
        entries[entry.key] = entry.value
    return MappingProxyType(entries)


def _required(entries: Mapping[str, str], key: str) -> str:
    value = entries.get(key)
    if value is None or not value.strip():
        raise RegistryValidationError(f"IVA schema vocabulary is missing {key!r}")
    return value.strip()


def _csv_tokens(entries: Mapping[str, str], key: str) -> tuple[str, ...]:
    tokens = tuple(token.strip() for token in _required(entries, key).split(",") if token.strip())
    if not tokens or len(set(tokens)) != len(tokens):
        raise RegistryValidationError(f"IVA schema vocabulary {key!r} must contain unique non-empty tokens")
    return tokens


def _csv_refs(entries: Mapping[str, str], key: str, *, required: bool) -> tuple[str, ...]:
    value = entries.get(key)
    if value is None or not value.strip():
        if required:
            raise RegistryValidationError(f"IVA schema vocabulary is missing {key!r}")
        return ()
    refs = tuple(token.strip() for token in value.split(",") if token.strip())
    if len(set(refs)) != len(refs):
        raise RegistryValidationError(f"IVA schema vocabulary {key!r} must contain unique references")
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
        raise RegistryValidationError("IVA statutory schema vocabulary must resolve as a mapping fact")
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
    selected_date = effective_date or date.today()
    selected = authority or governed_facts_in_scope()
    if selected is None:
        return _bundled_entries(selected_date)
    return _resolve_entries(effective_date=selected_date, authority=selected)


def resolve_iva_cash_accounting_catalogue(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IvaCashAccountingTreatmentCatalogue:
    entries = _selected_entries(effective_date=effective_date, authority=authority)
    definitions: list[IvaCashAccountingTreatmentDefinition] = []
    for raw_token in _csv_tokens(entries, _CASH_ORDER_KEY):
        token = IvaCashAccountingTreatment(raw_token)
        prefix = f"{_CASH_PREFIX}{raw_token}"
        if _required(entries, f"{prefix}.value") != raw_token:
            raise RegistryValidationError(f"cash-accounting token {raw_token!r} declares a mismatched value")
        definitions.append(
            IvaCashAccountingTreatmentDefinition(
                token=token,
                description=_required(entries, f"{prefix}.description"),
                legal_refs=_csv_refs(entries, f"{prefix}.legal_refs", required=False),
            ),
        )
    catalogue = IvaCashAccountingTreatmentCatalogue(
        definitions=tuple(definitions),
        none_token=IvaCashAccountingTreatment(_required(entries, _CASH_NONE_KEY)),
        supplier_regime_token=IvaCashAccountingTreatment(_required(entries, _CASH_SUPPLIER_KEY)),
    )
    if catalogue.none_token not in catalogue.all_treatments:
        raise RegistryValidationError("cash-accounting none token is not declared in the treatment order")
    if catalogue.supplier_regime_token not in catalogue.all_treatments:
        raise RegistryValidationError("cash-accounting supplier token is not declared in the treatment order")
    return catalogue


def resolve_iva_regime_catalogue(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IvaRegimeCatalogue:
    entries = _selected_entries(effective_date=effective_date, authority=authority)
    definitions: list[IvaRegimeDefinition] = []
    for raw_token in _csv_tokens(entries, _REGIME_ORDER_KEY):
        token = IVARegime(raw_token)
        prefix = f"{_REGIME_PREFIX}{raw_token}"
        if _required(entries, f"{prefix}.value") != raw_token:
            raise RegistryValidationError(f"IVA regime token {raw_token!r} declares a mismatched value")
        definitions.append(
            IvaRegimeDefinition(
                token=token,
                description=_required(entries, f"{prefix}.description"),
                deadline_applicability=_required(entries, f"{prefix}.deadline_applicability"),
                legal_refs=_csv_refs(entries, f"{prefix}.legal_refs", required=False),
            ),
        )
    catalogue = IvaRegimeCatalogue(
        definitions=tuple(definitions),
        default_token=IVARegime(_required(entries, _REGIME_DEFAULT_KEY)),
        no_aplica_token=IVARegime(_required(entries, _REGIME_NO_APLICA_KEY)),
        self_assessment_tokens=frozenset(
            IVARegime(raw_token) for raw_token in _csv_tokens(entries, _REGIME_SELF_ASSESSMENT_KEY)
        ),
    )
    if catalogue.default_token not in catalogue.all_regimes:
        raise RegistryValidationError("IVA default regime is not declared in the regime order")
    if catalogue.no_aplica_token not in catalogue.all_regimes:
        raise RegistryValidationError("IVA NO_APLICA regime is not declared in the regime order")
    if not catalogue.self_assessment_tokens.issubset(catalogue.all_regimes):
        raise RegistryValidationError("IVA self-assessment regimes must be declared in the regime order")
    for semantic_key in (_REGIME_SIMPLIFICADO_KEY, _REGIME_REAGP_KEY, _REGIME_EXENTO_KEY):
        semantic_token = IVARegime(_required(entries, semantic_key))
        if semantic_token not in catalogue.all_regimes:
            raise RegistryValidationError(f"IVA regime semantic token {semantic_key!r} is not declared")
    return catalogue


def resolve_m303_tax_territory_catalogue(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> M303TaxTerritoryCatalogue:
    """Resolve the dated Modelo 303 territory vocabulary and semantics."""
    entries = _selected_entries(effective_date=effective_date, authority=authority)
    definitions: list[M303TaxTerritoryDefinition] = []
    for raw_token in _csv_tokens(entries, _TERRITORY_ORDER_KEY):
        try:
            token = M303TaxTerritory._from_registry(raw_token)
            declared_value = _required(entries, f"{_TERRITORY_PREFIX}{raw_token}.value")
            description = _required(entries, f"{_TERRITORY_PREFIX}{raw_token}.description")
            raw_is_foral = _required(entries, f"{_TERRITORY_PREFIX}{raw_token}.is_foral")
            raw_ratio = _required(entries, f"{_TERRITORY_PREFIX}{raw_token}.state_attribution_ratio")
            exclusively_foral_mark = _required(
                entries,
                f"{_TERRITORY_PREFIX}{raw_token}.exclusively_foral_mark",
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise RegistryValidationError(
                f"Modelo 303 tax-territory catalogue is missing or invalid for {raw_token!r}",
            ) from exc
        if declared_value != raw_token:
            raise RegistryValidationError(f"Modelo 303 tax-territory token {raw_token!r} declares a mismatched value")
        if raw_is_foral not in {"true", "false"}:
            raise RegistryValidationError(f"Modelo 303 tax-territory token {raw_token!r} has invalid foral status")
        try:
            ratio = Decimal(raw_ratio)
        except InvalidOperation as exc:
            raise RegistryValidationError(
                f"Modelo 303 tax-territory token {raw_token!r} has an invalid state-attribution ratio",
            ) from exc
        if ratio < 0 or ratio > 100:
            raise RegistryValidationError(
                f"Modelo 303 tax-territory token {raw_token!r} has an out-of-range state-attribution ratio",
            )
        definitions.append(
            M303TaxTerritoryDefinition(
                token=token,
                description=description,
                legal_refs=_csv_refs(
                    entries,
                    f"{_TERRITORY_PREFIX}{raw_token}.legal_refs",
                    required=True,
                ),
                is_foral=raw_is_foral == "true",
                state_attribution_ratio=ratio,
                exclusively_foral_mark=exclusively_foral_mark,
            ),
        )
    catalogue = M303TaxTerritoryCatalogue(definitions=tuple(definitions))
    if len(catalogue.all_territories) != len(definitions):
        raise RegistryValidationError("Modelo 303 tax-territory catalogue has duplicate tokens")
    _ = catalogue.foral_token
    return catalogue


def resolve_m303_regime_composition_catalogue(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> M303RegimeCompositionCatalogue:
    """Resolve the dated Modelo 303 regime-composition vocabulary."""
    entries = _selected_entries(effective_date=effective_date, authority=authority)
    definitions: list[M303RegimeCompositionDefinition] = []
    for raw_token in _csv_tokens(entries, _COMPOSITION_ORDER_KEY):
        try:
            token = M303RegimeComposition._from_registry(raw_token)
            declared_value = _required(entries, f"{_COMPOSITION_PREFIX}{raw_token}.value")
            description = _required(entries, f"{_COMPOSITION_PREFIX}{raw_token}.description")
            export_code = _required(entries, f"{_COMPOSITION_PREFIX}{raw_token}.export_code")
            simplified_scope = _required(entries, f"{_COMPOSITION_PREFIX}{raw_token}.simplified_scope")
        except (KeyError, TypeError, ValueError) as exc:
            raise RegistryValidationError(
                f"Modelo 303 regime-composition catalogue is missing or invalid for {raw_token!r}",
            ) from exc
        if declared_value != raw_token:
            raise RegistryValidationError(
                f"Modelo 303 regime-composition token {raw_token!r} declares a mismatched value",
            )
        if simplified_scope not in {"not_claimed", "evidence_required"}:
            raise RegistryValidationError(
                f"Modelo 303 regime-composition token {raw_token!r} has invalid simplified scope",
            )
        definitions.append(
            M303RegimeCompositionDefinition(
                token=token,
                description=description,
                export_code=export_code,
                simplified_scope=simplified_scope,
                legal_refs=_csv_refs(
                    entries,
                    f"{_COMPOSITION_PREFIX}{raw_token}.legal_refs",
                    required=True,
                ),
            ),
        )
    catalogue = M303RegimeCompositionCatalogue(definitions=tuple(definitions))
    if len(catalogue.all_compositions) != len(definitions):
        raise RegistryValidationError("Modelo 303 regime-composition catalogue has duplicate tokens")
    return catalogue


def resolve_iva_exemption_article_catalogue(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IvaExemptionArticleCatalogue:
    entries = _selected_entries(effective_date=effective_date, authority=authority)
    definitions: list[IvaExemptionArticleDefinition] = []
    for raw_token in _csv_tokens(entries, _EXEMPTION_ORDER_KEY):
        token = IvaExemptionArticle(raw_token)
        prefix = f"{_EXEMPTION_PREFIX}{raw_token}"
        if _required(entries, f"{prefix}.value") != raw_token:
            raise RegistryValidationError(f"exemption article token {raw_token!r} declares a mismatched value")
        definitions.append(
            IvaExemptionArticleDefinition(
                token=token,
                description=_required(entries, f"{prefix}.description"),
                legal_refs=_csv_refs(entries, f"{prefix}.legal_refs", required=True),
            ),
        )
    return IvaExemptionArticleCatalogue(definitions=tuple(definitions))


def resolve_iva_art69_dos_service_catalogue(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IvaArt69DosServiceCatalogue:
    entries = _selected_entries(effective_date=effective_date, authority=authority)
    definitions: list[IvaArt69DosServiceDefinition] = []
    for raw_token in _csv_tokens(entries, _SERVICE_ORDER_KEY):
        token = IvaArt69DosService(raw_token)
        prefix = f"{_SERVICE_PREFIX}{raw_token}"
        if _required(entries, f"{prefix}.value") != raw_token:
            raise RegistryValidationError(f"Art. 69.Dos service token {raw_token!r} declares a mismatched value")
        definitions.append(
            IvaArt69DosServiceDefinition(
                token=token,
                description=_required(entries, f"{prefix}.description"),
                legal_refs=_csv_refs(entries, f"{prefix}.legal_refs", required=True),
            ),
        )
    return IvaArt69DosServiceCatalogue(definitions=tuple(definitions))


def default_iva_regime(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IVARegime:
    return resolve_iva_regime_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).default_token


def require_iva_regime(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IVARegime:
    return resolve_iva_regime_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).require(value)


def require_m303_tax_territory(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> M303TaxTerritory:
    """Project one Modelo 303 territory token only when the registry governs it."""
    return resolve_m303_tax_territory_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).require(value)


def m303_tax_territory_choices(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> tuple[M303TaxTerritory, ...]:
    """Return the registry-declared territory choice order."""
    return resolve_m303_tax_territory_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).choices


def m303_tax_territory_is_foral(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> bool:
    """Return the registry-declared foral classification for one token."""
    catalogue = resolve_m303_tax_territory_catalogue(
        effective_date=effective_date,
        authority=authority,
    )
    return catalogue.definition(value).is_foral


def m303_tax_territory_state_attribution_ratio(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> Decimal:
    """Return the registry-declared State-attribution ratio for one token."""
    catalogue = resolve_m303_tax_territory_catalogue(
        effective_date=effective_date,
        authority=authority,
    )
    return catalogue.definition(value).state_attribution_ratio


def m303_tax_territory_exclusively_foral_mark(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> str:
    """Return the registry-declared Modelo 303 territory output mark."""
    catalogue = resolve_m303_tax_territory_catalogue(
        effective_date=effective_date,
        authority=authority,
    )
    return catalogue.definition(value).exclusively_foral_mark


def require_m303_regime_composition(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> M303RegimeComposition:
    """Project one Modelo 303 regime-composition token from the facts registry."""
    return resolve_m303_regime_composition_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).require(value)


def m303_regime_composition_choices(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> tuple[M303RegimeComposition, ...]:
    """Return the registry-declared Modelo 303 composition choice order."""
    return resolve_m303_regime_composition_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).choices


def m303_regime_composition_export_code(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> str:
    """Return the registry-declared Modelo 303 composition export code."""
    return (
        resolve_m303_regime_composition_catalogue(
            effective_date=effective_date,
            authority=authority,
        )
        .definition(value)
        .export_code
    )


def m303_regime_composition_simplified_scope(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> M303RegimenSimplificadoScope:
    """Project the registry-declared simplified-regime scope for a composition."""
    scope = (
        resolve_m303_regime_composition_catalogue(
            effective_date=effective_date,
            authority=authority,
        )
        .definition(value)
        .simplified_scope
    )
    return M303RegimenSimplificadoScope._from_registry(scope)


def iva_regime_choices(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> tuple[IVARegime, ...]:
    return resolve_iva_regime_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).selectable_regimes


def iva_regime_no_aplica_token(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IVARegime:
    return resolve_iva_regime_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).no_aplica_token


def iva_regime_self_assessment_tokens(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> frozenset[IVARegime]:
    return resolve_iva_regime_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).self_assessment_tokens


def _iva_regime_semantic_token(
    key: str,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IVARegime:
    entries = _selected_entries(effective_date=effective_date, authority=authority)
    return require_iva_regime(_required(entries, key), effective_date=effective_date, authority=authority)


def iva_regime_simplificado_token(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IVARegime:
    return _iva_regime_semantic_token(
        _REGIME_SIMPLIFICADO_KEY,
        effective_date=effective_date,
        authority=authority,
    )


def iva_regime_reagp_token(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IVARegime:
    return _iva_regime_semantic_token(
        _REGIME_REAGP_KEY,
        effective_date=effective_date,
        authority=authority,
    )


def iva_regime_exento_token(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IVARegime:
    return _iva_regime_semantic_token(
        _REGIME_EXENTO_KEY,
        effective_date=effective_date,
        authority=authority,
    )


def default_iva_cash_accounting_treatment(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IvaCashAccountingTreatment:
    return resolve_iva_cash_accounting_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).none_token


def require_iva_cash_accounting_treatment(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IvaCashAccountingTreatment:
    return resolve_iva_cash_accounting_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).require(value)


def require_registry_declared_iva_cash_accounting_treatment(
    value: object,
    *,
    effective_date: date,
) -> IvaCashAccountingTreatment:
    """Return one treatment token declared by the facts a validation is validating.

    A registry validator resolves its vocabulary from the candidate in scope,
    never from the published authority: the artifact reader validates the
    document it has just decoded while holding the shared-artifact lock, so a
    validator reaching for the bundle asks that lock for the artifact it is in
    the middle of producing. Absence of a scope is a refusal rather than a
    fallback, because the fallback is the deadlock.
    """
    authority = governed_facts_in_scope()
    if authority is None:
        raise RegistryValidationError(
            "IVA cash-accounting validation requires the governed facts being validated to be "
            "in scope; registry validation must not resolve a treatment through the published "
            "authority artifact",
        )
    return resolve_iva_cash_accounting_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).require(value)


def require_iva_exemption_article(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IvaExemptionArticle:
    return resolve_iva_exemption_article_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).require(value)


def require_iva_art69_dos_service(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IvaArt69DosService:
    return resolve_iva_art69_dos_service_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).require(value)


__all__ = [
    "IvaArt69DosServiceCatalogue",
    "IvaArt69DosServiceDefinition",
    "IvaCashAccountingTreatmentCatalogue",
    "IvaCashAccountingTreatmentDefinition",
    "IvaExemptionArticleCatalogue",
    "IvaExemptionArticleDefinition",
    "IvaRegimeCatalogue",
    "IvaRegimeDefinition",
    "M303RegimeCompositionCatalogue",
    "M303RegimeCompositionDefinition",
    "M303TaxTerritoryCatalogue",
    "M303TaxTerritoryDefinition",
    "default_iva_cash_accounting_treatment",
    "default_iva_regime",
    "iva_regime_choices",
    "iva_regime_exento_token",
    "iva_regime_no_aplica_token",
    "iva_regime_reagp_token",
    "iva_regime_self_assessment_tokens",
    "iva_regime_simplificado_token",
    "m303_regime_composition_choices",
    "m303_regime_composition_export_code",
    "m303_regime_composition_simplified_scope",
    "m303_tax_territory_choices",
    "m303_tax_territory_exclusively_foral_mark",
    "m303_tax_territory_is_foral",
    "m303_tax_territory_state_attribution_ratio",
    "require_iva_art69_dos_service",
    "require_iva_cash_accounting_treatment",
    "require_iva_exemption_article",
    "require_iva_regime",
    "require_m303_regime_composition",
    "require_m303_tax_territory",
    "require_registry_declared_iva_cash_accounting_treatment",
    "resolve_iva_art69_dos_service_catalogue",
    "resolve_iva_cash_accounting_catalogue",
    "resolve_iva_exemption_article_catalogue",
    "resolve_iva_regime_catalogue",
    "resolve_m303_regime_composition_catalogue",
    "resolve_m303_tax_territory_catalogue",
]
