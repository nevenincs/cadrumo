"""Source-mesh resolver for user-profile backed registry bindings.

Owns :attr:`~core.BindingSourceKind.PROFILE` and returns the
profile-sourced values as a :class:`~._source_mesh.CalculationSourceResolution`.
Accepts an optional
:class:`~domain.calculations.registry.RegistrySnapshot` at construction;
when none is supplied the resolver fetches the matching snapshot lazily from the
resident registry authority at resolution time.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import ClassVar

from ...core import BindingSourceKind
from ...domain.calculations.registry import BindingId, RegistrySnapshot
from ._source_mesh import (
    CalculationSourceContext,
    CalculationSourceResolution,
)


class ProfileSourceResolver:
    """Resolve calculation-relevant ``source = "profile"`` bindings."""

    resolver_id: ClassVar[str] = "profile"
    owned_sources: ClassVar[tuple[BindingSourceKind, ...]] = (BindingSourceKind.PROFILE,)

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
        registry authority when none was supplied at construction, then
        delegates to ``resolve_profile_sourced_bindings``, which returns the
        complete :class:`CalculationSourceResolution` (typed binding channels
        plus a :class:`CalculationSourceProvenance` row per profile-sourced
        binding).

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

        from ..modelo import resolve_profile_sourced_bindings

        return resolve_profile_sourced_bindings(
            snapshot,
            bucket_id=context.bucket_id,
            profile_record=self._profile_record,
            caller_binding_ids=self._caller_binding_ids,
        )


__all__ = ["ProfileSourceResolver"]
