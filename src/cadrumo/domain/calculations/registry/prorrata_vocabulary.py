"""Typed projections for the 0116 prorrata lifecycle and input vocabularies.

The dated ``renta-iva-deduction-ratio-policy`` fact owns the prorrata kind
and art. 106 input-classification vocabularies.  This module is the only
runtime projection of those declarations; the IVA domain keeps opaque token
types and arithmetic mechanics, but no closed catalogue of legal values.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from types import MappingProxyType

from ....domain.iva.prorrata import InputClassification, ProrrataKind
from .errors import RegistryValidationError
from .facts.resolution import MappingFactQuery, ResolvedMappingFact
from .governed_fact_scope import GovernedFactSource, cache_governed_projection, governed_facts_in_scope
from .schema_base import DateAxis

_FACT_ID = "renta-iva-deduction-ratio-policy"
_KIND_ORDER_KEY = "prorrata.kind_order"
_KIND_PREFIX = "prorrata.kind."
_INPUT_ORDER_KEY = "prorrata.input_classification_order"
_INPUT_DEFAULT_KEY = "prorrata.input_classification.default"
_INPUT_PREFIX = "prorrata.input_classification."


@dataclass(frozen=True, slots=True)
class ProrrataKindDefinition:
    """One registry-declared prorrata lifecycle kind and its period policy."""

    token: ProrrataKind
    description: str
    legal_ref: str
    period_required: bool
    annual_only: bool


@dataclass(frozen=True, slots=True)
class ProrrataKindCatalogue:
    """Typed projection of the 0116 prorrata-kind vocabulary."""

    definitions: tuple[ProrrataKindDefinition, ...]

    @property
    def tokens(self) -> tuple[ProrrataKind, ...]:
        """Return the authority-declared kinds in authored order."""
        return tuple(definition.token for definition in self.definitions)

    @property
    def all_kinds(self) -> frozenset[ProrrataKind]:
        """Return every authority-declared kind."""
        return frozenset(self.tokens)

    def require(self, value: object) -> ProrrataKind:
        """Project one token only when the selected authority declares it."""
        token = _coerce_token(value, ProrrataKind, "prorrata kind")
        if token not in self.all_kinds:
            raise RegistryValidationError(
                f"prorrata kind {str(token)!r} is not declared by fact {_FACT_ID!r}",
            )
        return token

    def definition(self, value: object) -> ProrrataKindDefinition:
        """Return the selected kind's registry-owned semantics."""
        token = self.require(value)
        return next(definition for definition in self.definitions if definition.token == token)


@dataclass(frozen=True, slots=True)
class InputClassificationDefinition:
    """One registry-declared art. 106 input classification and deduction rule."""

    token: InputClassification
    description: str
    legal_ref: str
    deductible_percentage: Decimal | None
    uses_general_percentage: bool


@dataclass(frozen=True, slots=True)
class InputClassificationCatalogue:
    """Typed projection of the 0116 art. 106 input vocabulary."""

    definitions: tuple[InputClassificationDefinition, ...]
    default_classification: InputClassification

    @property
    def tokens(self) -> tuple[InputClassification, ...]:
        """Return the authority-declared classifications in authored order."""
        return tuple(definition.token for definition in self.definitions)

    @property
    def all_classifications(self) -> frozenset[InputClassification]:
        """Return every authority-declared classification."""
        return frozenset(self.tokens)

    def require(self, value: object) -> InputClassification:
        """Project one token only when the selected authority declares it."""
        token = _coerce_token(value, InputClassification, "input classification")
        if token not in self.all_classifications:
            raise RegistryValidationError(
                f"input classification {str(token)!r} is not declared by fact {_FACT_ID!r}",
            )
        return token

    def definition(self, value: object) -> InputClassificationDefinition:
        """Return the selected classification's registry-owned semantics."""
        token = self.require(value)
        return next(definition for definition in self.definitions if definition.token == token)


def _coerce_token(value: object, token_type: type[str], label: str) -> str:
    if isinstance(value, token_type):
        token = value
    elif isinstance(value, str):
        raw = value.strip()
        if not raw:
            raise RegistryValidationError(f"{label} must be a non-empty string token")
        try:
            token = token_type._from_registry(raw)  # type: ignore[attr-defined]
        except (TypeError, ValueError) as exc:
            raise RegistryValidationError(f"{label} must be a non-empty registry token") from exc
    else:
        raise RegistryValidationError(f"{label} must be a registry-projected string token")
    if not str(token):
        raise RegistryValidationError(f"{label} must not be blank")
    return token


def _mapping_entries(resolved: ResolvedMappingFact) -> Mapping[str, str]:
    entries: dict[str, str] = {}
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise RegistryValidationError("prorrata vocabulary entries must be string-to-string")
        if entry.key in entries:
            raise RegistryValidationError(f"duplicate prorrata vocabulary key {entry.key!r}")
        entries[entry.key] = entry.value
    return MappingProxyType(entries)


def _required(entries: Mapping[str, str], key: str) -> str:
    value = entries.get(key)
    if value is None or not value.strip():
        raise RegistryValidationError(f"prorrata vocabulary is missing {key!r}")
    return value.strip()


def _optional(entries: Mapping[str, str], key: str) -> str | None:
    value = entries.get(key)
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


def _csv(entries: Mapping[str, str], key: str) -> tuple[str, ...]:
    values = tuple(token.strip() for token in _required(entries, key).split(",") if token.strip())
    if not values or len(values) != len(set(values)):
        raise RegistryValidationError(f"prorrata vocabulary {key!r} must contain unique tokens")
    return values


def _boolean(entries: Mapping[str, str], key: str) -> bool:
    value = _required(entries, key).lower()
    if value == "true":
        return True
    if value == "false":
        return False
    raise RegistryValidationError(f"prorrata vocabulary {key!r} must be true or false")


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


@cache_governed_projection(maxsize=64)
def _bundled_entries(effective_date: date) -> Mapping[str, str]:
    del effective_date
    raise RegistryValidationError("prorrata vocabulary requires an explicit authority operation or scope")


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


def resolve_prorrata_kind_catalogue(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> ProrrataKindCatalogue:
    """Resolve the dated prorrata lifecycle vocabulary from fact 0116."""
    entries = _selected_entries(effective_date=effective_date, authority=authority)
    definitions: list[ProrrataKindDefinition] = []
    for raw_token in _csv(entries, _KIND_ORDER_KEY):
        prefix = f"{_KIND_PREFIX}{raw_token}"
        declared_value = _required(entries, f"{prefix}.value")
        if declared_value != raw_token:
            raise RegistryValidationError(f"prorrata kind {raw_token!r} declares a mismatched value")
        definitions.append(
            ProrrataKindDefinition(
                token=ProrrataKind._from_registry(declared_value),
                description=_required(entries, f"{prefix}.description"),
                legal_ref=_required(entries, f"{prefix}.legal_ref"),
                period_required=_boolean(entries, f"{prefix}.period_required"),
                annual_only=_boolean(entries, f"{prefix}.annual_only"),
            ),
        )
    catalogue = ProrrataKindCatalogue(definitions=tuple(definitions))
    if len(catalogue.definitions) != len(catalogue.all_kinds):
        raise RegistryValidationError("prorrata kind vocabulary contains duplicate tokens")
    return catalogue


def require_prorrata_kind(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> ProrrataKind:
    """Project one prorrata lifecycle token through fact 0116."""
    return resolve_prorrata_kind_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).require(value)


def resolve_prorrata_kind_definition(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> ProrrataKindDefinition:
    """Return one prorrata lifecycle token's period policy."""
    return resolve_prorrata_kind_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).definition(value)


def definitive_prorrata_kind(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> ProrrataKind:
    """Return the uniquely annual-only kind declared by fact 0116."""
    catalogue = resolve_prorrata_kind_catalogue(
        effective_date=effective_date,
        authority=authority,
    )
    annual_only = tuple(definition.token for definition in catalogue.definitions if definition.annual_only)
    if len(annual_only) != 1:
        raise RegistryValidationError("0116 must declare exactly one annual-only prorrata kind")
    return annual_only[0]


def resolve_input_classification_catalogue(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> InputClassificationCatalogue:
    """Resolve the dated art. 106 input vocabulary from fact 0116."""
    entries = _selected_entries(effective_date=effective_date, authority=authority)
    definitions: list[InputClassificationDefinition] = []
    for raw_token in _csv(entries, _INPUT_ORDER_KEY):
        prefix = f"{_INPUT_PREFIX}{raw_token}"
        declared_value = _required(entries, f"{prefix}.value")
        if declared_value != raw_token:
            raise RegistryValidationError(f"input classification {raw_token!r} declares a mismatched value")
        uses_general_percentage = _boolean(entries, f"{prefix}.uses_general_percentage")
        fixed_percentage_text = _optional(entries, f"{prefix}.deductible_percentage")
        if (fixed_percentage_text is None) != uses_general_percentage:
            raise RegistryValidationError(
                f"input classification {raw_token!r} must declare exactly one deduction percentage source",
            )
        fixed_percentage: Decimal | None = None
        if fixed_percentage_text is not None:
            try:
                fixed_percentage = Decimal(fixed_percentage_text)
            except InvalidOperation as exc:
                raise RegistryValidationError(
                    f"input classification {raw_token!r} has an invalid deductible percentage",
                ) from exc
            if fixed_percentage < Decimal("0") or fixed_percentage > Decimal("100"):
                raise RegistryValidationError(
                    f"input classification {raw_token!r} deductible percentage is outside 0..100",
                )
        definitions.append(
            InputClassificationDefinition(
                token=InputClassification._from_registry(declared_value),
                description=_required(entries, f"{prefix}.description"),
                legal_ref=_required(entries, f"{prefix}.legal_ref"),
                deductible_percentage=fixed_percentage,
                uses_general_percentage=uses_general_percentage,
            ),
        )
    default = InputClassification._from_registry(_required(entries, _INPUT_DEFAULT_KEY))
    catalogue = InputClassificationCatalogue(
        definitions=tuple(definitions),
        default_classification=default,
    )
    if len(catalogue.definitions) != len(catalogue.all_classifications):
        raise RegistryValidationError("input classification vocabulary contains duplicate tokens")
    if default not in catalogue.all_classifications:
        raise RegistryValidationError("0116 input classification default is not declared in its order")
    return catalogue


def require_input_classification(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> InputClassification:
    """Project one art. 106 input token through fact 0116."""
    return resolve_input_classification_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).require(value)


def resolve_input_classification_definition(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> InputClassificationDefinition:
    """Return one input classification's registry-owned deduction semantics."""
    return resolve_input_classification_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).definition(value)


def input_classification_tokens(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> tuple[InputClassification, ...]:
    """Return the selected art. 106 classifications in registry order."""
    return resolve_input_classification_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).tokens


def default_input_classification(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> InputClassification:
    """Return the 0116-declared mixed-use default classification."""
    return resolve_input_classification_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).default_classification


__all__ = [
    "InputClassificationCatalogue",
    "InputClassificationDefinition",
    "ProrrataKindCatalogue",
    "ProrrataKindDefinition",
    "default_input_classification",
    "definitive_prorrata_kind",
    "input_classification_tokens",
    "require_input_classification",
    "require_prorrata_kind",
    "resolve_input_classification_catalogue",
    "resolve_input_classification_definition",
    "resolve_prorrata_kind_catalogue",
    "resolve_prorrata_kind_definition",
]
