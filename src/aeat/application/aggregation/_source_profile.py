"""Source mesh resolver for user-profile backed registry bindings."""

from __future__ import annotations

from collections.abc import Iterable

from ...domain.calculations.registry import RegistrySnapshot
from ._source_mesh import (
    CalculationSourceContext,
    CalculationSourceProvenance,
    CalculationSourceResolution,
)


class ProfileSourceResolver:
    """Resolve formula-consumed ``source = "profile"`` bindings through the source mesh."""

    resolver_id = "profile"
    owned_sources = ("profile",)

    def __init__(
        self,
        *,
        caller_binding_ids: Iterable[str] = (),
        registry_snapshot: RegistrySnapshot | None = None,
        profile_record: object | None = None,
    ) -> None:
        self._caller_binding_ids = frozenset(caller_binding_ids)
        self._registry_snapshot = registry_snapshot
        self._profile_record = profile_record

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        snapshot = self._registry_snapshot
        if snapshot is None:
            from ...core.resources import resources

            snapshot = resources().modelos.authority.snapshot(
                context.modelo,
                filing_year=context.filing_year,
                period=context.period,
            )

        from ..modelo._profile_binding import resolve_profile_sourced_bindings

        result = resolve_profile_sourced_bindings(
            snapshot,
            bucket_id=context.bucket_id,
            profile_record=self._profile_record,
            caller_binding_ids=self._caller_binding_ids,
        )
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values=result.binding_values,
            enum_binding_values=result.enum_binding_values,
            provenance=tuple(
                CalculationSourceProvenance(
                    source_kind="profile",
                    source_ref=f"profile:{context.bucket_id}:binding:{binding_id}",
                )
                for binding_id in result.bindings_sourced_from_profile
            ),
        )


__all__ = ["ProfileSourceResolver"]
