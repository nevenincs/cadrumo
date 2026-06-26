"""Source mesh resolver for user-profile backed registry bindings.

Accepts an optional :class:`RegistrySnapshot` at construction; when none
is supplied the resolver fetches it lazily from the resident registry
authority at resolution time.
"""

from __future__ import annotations

from collections.abc import Iterable

from ...core import BindingSourceKind
from ...domain.calculations.registry import BindingId, RegistrySnapshot
from ._source_mesh import (
    CalculationSourceContext,
    CalculationSourceProvenance,
    CalculationSourceResolution,
)


class ProfileSourceResolver:
    """Resolve formula-consumed ``source = "profile"`` bindings through the source mesh."""

    resolver_id = "profile"
    owned_sources: tuple[BindingSourceKind, ...] = (BindingSourceKind.PROFILE,)

    def __init__(
        self,
        *,
        caller_binding_ids: Iterable[BindingId] = (),
        registry_snapshot: RegistrySnapshot | None = None,
        profile_record: object | None = None,
    ) -> None:
        self._caller_binding_ids = frozenset(caller_binding_ids)
        self._registry_snapshot = registry_snapshot
        self._profile_record = profile_record

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        """Resolve all ``source="profile"`` bindings for the given calculation context.

        Fetches the :class:`RegistrySnapshot` lazily from the resident
        registry authority when none was supplied at construction.  Delegates
        binding resolution to ``resolve_profile_sourced_bindings`` and wraps
        each resolved binding in a :class:`CalculationSourceProvenance` entry
        so the engine can trace every value back to the originating profile
        record.

        Args:
            context: A :class:`CalculationSourceContext` carrying the modelo,
                filing year, period, and bucket identifier needed to select
                the correct registry snapshot.

        Returns:
            A :class:`CalculationSourceResolution` with typed binding maps
            and a provenance tuple covering every profile-sourced binding.
        """
        snapshot = self._registry_snapshot
        if snapshot is None:
            from ...core.resources import resources

            snapshot = resources().modelos.authority.snapshot(
                context.modelo,
                filing_year=context.filing_year,
                period=context.period.registry_token,
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
            date_binding_values=result.date_binding_values,
            provenance=tuple(
                CalculationSourceProvenance(
                    source_kind="profile",
                    source_ref=f"profile:{context.bucket_id}:binding:{binding_id}",
                    fingerprint=result.profile_record_fingerprint,
                )
                for binding_id in result.bindings_sourced_from_profile
            ),
        )


__all__ = ["ProfileSourceResolver"]
