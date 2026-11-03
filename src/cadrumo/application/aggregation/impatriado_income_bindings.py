"""Source resolver for the Modelo 100 income an impatriado taxpayer declares under the special regime."""

from __future__ import annotations

from collections.abc import Mapping
from typing import ClassVar

from ...core.aggregation import BindingSourceKind, CalculationSourceLineageRole
from ...core.casilla_id import CasillaId, validated_casilla_id
from ...core.period import PeriodError
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.binding_terminal_origin import TerminalOriginClass
from ...domain.calculations.registry.errors import RegistryError
from ...domain.calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ...domain.calculations.registry.ledger_impatriado_bindings import (
    resolve_ledger_impatriado_income_aggregation_binding_values,
    unsupported_ledger_impatriado_income_observations,
)
from ...domain.calculations.registry.schema_base import DateAxis
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ._modelo_bindings_invoice_iva import (
    out_of_window_summary_diagnostics,
)
from ._modelo_bindings_support import (
    STORAGE_DEGRADATION_ERRORS,
    empty_source_resolution,
    revision_has_binding_source,
)
from .impatriado_income_ledger import aggregate_impatriado_income_ledger_from_repositories
from .modelo_bindings import aggregation_period_for_modelo
from .source_mesh import (
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceProvenance,
    CalculationSourceResolution,
)
from .source_resolution_operations import sorted_source_ids as sorted_ids
from .source_resolution_operations import (
    source_context_operation,
    source_issue_diagnostics,
    storage_degradation_resolution,
)
from .source_resolution_operations import (
    source_provenance_for as _provenance_for,
)

_IMPATRIADO_REGISTRY_FACT_ID = "impatriado-income-ledger-registry-mapping"


_IMPATRIADO_REGISTRY_SOURCE_KIND = "ledger_impatriado_income_aggregation"


def _resolve_impatriado_registry_declarations(
    context: CalculationSourceContext,
    *,
    operation: PinnedAuthorityOperation | None = None,
) -> tuple[str, CasillaId, frozenset[str], frozenset[str]] | None:
    """Resolve the selected filing context's impatriado ledger declarations.

    A missing, stale, or malformed mapping is an unavailable source declaration.
    Returning ``None`` makes the caller return an empty source resolution rather
    than silently selecting a Python default.
    """
    if operation is None:
        with source_context_operation(context) as indexed_operation:
            return _resolve_impatriado_registry_declarations(context, operation=indexed_operation)
    try:
        resolved = operation.resolve_governed_fact(
            MappingFactQuery(
                fact_id=_IMPATRIADO_REGISTRY_FACT_ID,
                date_axis=DateAxis.FILING_PERIOD,
                effective_date=context.period.end_date,
                filing_year=context.filing_year,
                period=context.period.registry_token,
            ),
        )
    except (RegistryError, PeriodError, TypeError, ValueError):
        return None
    if not isinstance(resolved, ResolvedMappingFact):
        return None

    entries = _impatriado_mapping_entries(resolved)
    if entries is None:
        return None
    declaration_values = _impatriado_declaration_values(entries, context)
    if declaration_values is None:
        return None
    modelo, target_value, jurisdiction_value, category_value = declaration_values
    target_casilla_id = _impatriado_target_casilla(target_value)
    if target_casilla_id is None:
        return None
    source_jurisdictions = _impatriado_csv_tokens(jurisdiction_value, uppercase=True)
    eligible_income_categories = _impatriado_csv_tokens(category_value)
    if source_jurisdictions is None or eligible_income_categories is None:
        return None
    if not _impatriado_jurisdictions_are_canonical(source_jurisdictions):
        return None
    return modelo, target_casilla_id, source_jurisdictions, eligible_income_categories


def _impatriado_mapping_entries(resolved: ResolvedMappingFact) -> dict[str, str] | None:
    entries: dict[str, str] = {}
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            return None
        key = entry.key.strip()
        if not key or key in entries:
            return None
        value = entry.value.strip()
        if not value:
            return None
        entries[key] = value
    return entries


def _impatriado_declaration_values(
    entries: Mapping[str, str], context: CalculationSourceContext
) -> tuple[str, str, str, str] | None:
    modelo = entries.get("applicability.modelos")
    source_kind = entries.get("binding.source_kind")
    target_value = entries.get("target.casilla_id")
    jurisdiction_value = entries.get("source.jurisdictions")
    category_value = entries.get("eligible.income_categories")
    if (
        modelo is None
        or source_kind is None
        or target_value is None
        or jurisdiction_value is None
        or category_value is None
        or modelo != context.modelo
        or source_kind != _IMPATRIADO_REGISTRY_SOURCE_KIND
    ):
        return None
    return modelo, target_value, jurisdiction_value, category_value


def _impatriado_target_casilla(value: str) -> CasillaId | None:
    try:
        return validated_casilla_id(value, surface="impatriado registry target.casilla_id")
    except (TypeError, ValueError):
        return None


def _impatriado_csv_tokens(value: str, *, uppercase: bool = False) -> frozenset[str] | None:
    raw_tokens = value.split(",")
    if not raw_tokens or any(not token.strip() for token in raw_tokens):
        return None
    normalized = tuple(token.strip().upper() if uppercase else token.strip().casefold() for token in raw_tokens)
    if len(set(normalized)) != len(normalized):
        return None
    if any(not _impatriado_token_is_valid(token) for token in normalized):
        return None
    return frozenset(normalized)


def _impatriado_token_is_valid(token: str) -> bool:
    return bool(token) and all(char.isalnum() or char in "_-." for char in token)


def _impatriado_jurisdictions_are_canonical(jurisdictions: frozenset[str]) -> bool:
    return all(len(value) == 2 and value.isalpha() and value == value.upper() for value in jurisdictions)


class LedgerImpatriadoIncomeAggregationSourceResolver:
    """Resolve ``ledger_impatriado_income_aggregation`` Modelo 151 base bindings.

    Owns :attr:`BindingSourceKind.LEDGER_IMPATRIADO_INCOME_AGGREGATION`. Modelo
    151 (régimen especial de impatriados, Ley Beckham) folds only Spanish-source
    (``source_jurisdiction == "ES"``) income into
    ``impatriado.base-liquidable-general`` over the full ejercicio; every
    foreign-source or jurisdiction-unresolved row is segregated by the classifier
    into a typed ``BECKHAM_FOREIGN_SOURCE_SEGREGATED`` issue and surfaced as a
    non-blocking source diagnostic rather than silently admitted or silently
    dropped (art. 93.2 LIRPF / art. 25.1.f TRLIRNR).
    """

    resolver_id: ClassVar[str] = "ledger_impatriado_income_aggregation"
    owned_sources: ClassVar[tuple[BindingSourceKind, ...]] = (BindingSourceKind.LEDGER_IMPATRIADO_INCOME_AGGREGATION,)

    def __init__(self, *, transaction_repository: TransactionCatalogueRepositoryProtocol) -> None:
        """Bind the transaction repository for this source."""
        self._transaction_repository = transaction_repository

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        """Resolve impatriado income for the calculation context."""
        if not revision_has_binding_source(context.revision, "ledger_impatriado_income_aggregation"):
            return empty_source_resolution(self.resolver_id, self.owned_sources)

        aggregation_period = aggregation_period_for_modelo(
            filing_year=context.filing_year,
            code=context.period.registry_token,
        )
        declarations = _resolve_impatriado_registry_declarations(context)
        if declarations is None:
            return empty_source_resolution(self.resolver_id, self.owned_sources)
        modelo, target_casilla_id, source_jurisdictions, eligible_income_categories = declarations
        try:
            aggregation = aggregate_impatriado_income_ledger_from_repositories(
                bucket_id=context.bucket_id,
                period=aggregation_period,
                modelo=modelo,
                target_casilla_id=target_casilla_id,
                source_jurisdictions=source_jurisdictions,
                eligible_income_categories=eligible_income_categories,
                transaction_repository=self._transaction_repository,
            )
        except STORAGE_DEGRADATION_ERRORS as exc:
            return storage_degradation_resolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                source_kinds=self.owned_sources,
                error=exc,
            )
        binding_values = resolve_ledger_impatriado_income_aggregation_binding_values(
            context.revision,
            aggregation.observations,
        )
        # Fail-closed advisory: a non-zero ES-source income whose target casilla
        # matches no ledger_impatriado_income_aggregation binding would otherwise
        # be silently dropped from the base (no-silent-under-declaration).
        unrouted = unsupported_ledger_impatriado_income_observations(context.revision, aggregation.observations)
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values=binding_values,
            source_transaction_ids=sorted_ids(aggregation.observations, lambda observation: observation.transaction_id),
            diagnostics=out_of_window_summary_diagnostics(
                aggregation.out_of_window_summary,
                source_kind="ledger_impatriado_income_aggregation",
                resolver_id=self.resolver_id,
            )
            + source_issue_diagnostics(
                aggregation.issues,
                source_kind="ledger_impatriado_income_aggregation",
                resolver_id=self.resolver_id,
            )
            + tuple(
                CalculationSourceDiagnostic(
                    reason="unrouted_observation",
                    source_kind="ledger_impatriado_income_aggregation",
                    resolver_id=self.resolver_id,
                    message=(
                        f"declarable impatriado ES-source income observation (target_casilla_id="
                        f"{observation.target_casilla_id!r}, gross_amount={observation.gross_amount}) "
                        f"is not consumed by any ledger_impatriado_income_aggregation binding on revision "
                        f"{context.revision.id!r}; its income is not declared on this calculation"
                    ),
                )
                for observation in unrouted
            ),
            provenance=_provenance_for(
                aggregation.observations,
                lambda observation: CalculationSourceProvenance(
                    resolver_id=self.resolver_id,
                    resolved_binding_source=BindingSourceKind.LEDGER_IMPATRIADO_INCOME_AGGREGATION,
                    contributor_source_kind="ledger_impatriado_income_aggregation",
                    contributor_binding_source=BindingSourceKind.LEDGER_IMPATRIADO_INCOME_AGGREGATION,
                    lineage_role=CalculationSourceLineageRole.PRIMARY,
                    source_ref=f"transaction:{observation.transaction_id}",
                    parent_source_ref=None,
                    terminal_origin=TerminalOriginClass.LEDGER_AGGREGATE,
                ),
            ),
        )
