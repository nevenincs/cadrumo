"""Syntax-validated Modelo identifiers with authority-owned membership."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Set
from datetime import date

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

from .errors.hierarchy import CoreValidationError

__all__ = ["NON_REGISTRY_MODELOS", "OUT_OF_SCOPE_OBLIGATIONS", "UNMODELED_OBLIGATIONS", "Modelo"]


class Modelo(str):
    """Three-digit Modelo identifier; published authority owns membership."""

    __slots__ = ()

    def __new__(cls, value: str) -> Modelo:
        raw = str(value)
        if len(raw) != 3 or not raw.isascii() or not raw.isdigit():
            raise CoreValidationError(f"modelo code must be a three-digit ASCII string, got {value!r}")
        return str.__new__(cls, raw)

    @property
    def value(self) -> str:
        """Return the stable string representation used on the wire."""
        return str(self)

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: type[object],
        handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        """Validate from and serialize to the canonical JSON string shape."""
        del source_type, handler
        return core_schema.no_info_after_validator_function(
            cls,
            core_schema.str_schema(pattern=r"^[0-9]{3}$"),
            serialization=core_schema.to_string_ser_schema(),
        )


def _csv(value: str) -> tuple[str, ...]:
    values = tuple(token.strip() for token in value.split(",") if token.strip())
    if not values:
        raise CoreValidationError("Modelo catalogue declaration must not be empty")
    return values


def _scope_partitions() -> tuple[Mapping[Modelo, str], frozenset[Modelo]]:
    """Resolve product-scope partitions through the current published authority.

    The authority owns artifact identity and republication detection. Keeping a
    second process-lifetime cache here would serve partitions from an older
    publication after the authority has advanced.
    """
    from ..domain.calculations.registry.authority import bundled_authority
    from ..domain.calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
    from ..domain.calculations.registry.schema_base import DateAxis

    resolved = bundled_authority().resolve_governed_fact(
        MappingFactQuery(
            fact_id="modelo-obligation-scope-mapping",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=date.today(),
        )
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise CoreValidationError("Modelo obligation scope did not resolve as a mapping")
    declarations = {str(entry.key): str(entry.value) for entry in resolved.payload.entries}
    catalogue = frozenset(_csv(declarations["catalogue.codes"]))
    suppressed = frozenset(_csv(declarations["scope.suppressed.codes"]))
    registry_out = frozenset(_csv(declarations["scope.registry_out_of_scope.codes"]))
    reasons: dict[str, str] = {}
    groups: dict[str, dict[str, str]] = {}
    for key, value in declarations.items():
        if key.startswith("scope.code.") and key.endswith(".reason"):
            reasons[key.removeprefix("scope.code.").removesuffix(".reason")] = value
        elif key.startswith("scope.group."):
            _, _, group, field = key.split(".", 3)
            groups.setdefault(group, {})[field] = value
    for group, fields in groups.items():
        reason = fields.get("reason", "").strip()
        if not reason:
            raise CoreValidationError(f"Modelo scope group {group!r} has no reason")
        for code in _csv(fields.get("codes", "")):
            if code in reasons and reasons[code] != reason:
                raise CoreValidationError(f"Modelo scope code {code!r} has conflicting reasons")
            reasons[code] = reason
    if not set(reasons).issubset(catalogue) or not suppressed.issubset(reasons) or not registry_out.issubset(reasons):
        raise CoreValidationError("Modelo scope partitions disagree with the published catalogue")
    out_of_scope = {Modelo(code): reason for code, reason in reasons.items() if code not in suppressed}
    non_registry = frozenset(Modelo(code) for code in reasons if code not in registry_out)
    return out_of_scope, non_registry


class _ScopeMapping(Mapping[Modelo, str]):
    def __iter__(self) -> Iterator[Modelo]:
        return iter(_scope_partitions()[0])

    def __len__(self) -> int:
        return len(_scope_partitions()[0])

    def __getitem__(self, key: Modelo) -> str:
        return _scope_partitions()[0][key]


class _NonRegistryModelos(Set[Modelo]):
    def __contains__(self, value: object) -> bool:
        return value in _scope_partitions()[1]

    def __iter__(self) -> Iterator[Modelo]:
        return iter(_scope_partitions()[1])

    def __len__(self) -> int:
        return len(_scope_partitions()[1])


OUT_OF_SCOPE_OBLIGATIONS: Mapping[Modelo, str] = _ScopeMapping()
UNMODELED_OBLIGATIONS: Mapping[Modelo, str] = {}
NON_REGISTRY_MODELOS: Set[Modelo] = _NonRegistryModelos()
