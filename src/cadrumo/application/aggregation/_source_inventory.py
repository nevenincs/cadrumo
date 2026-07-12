"""Source-mesh readiness resolver adapter for inventory.

Provisions the inventory calculation-source surface without enrolling it as a live
calculation source. Inventory is not yet ready to feed registry bindings
(:func:`~application.inventory.inventory_source_readiness`), so this resolver
resolves NO binding value and emits a blocked-readiness
:class:`~application.aggregation.CalculationSourceDiagnostic`. It is deliberately
NOT registered in :func:`~application.aggregation.merge_source_resolutions`: it
exists so the surface is provisioned and its unreadiness is visible rather than a
silent blank (``no-dormant-source-resolvers``: provision the surface, refuse
visibly). When inventory persistence is hardened, the readiness flips and this
adapter is replaced by a real projecting resolver enrolled in the mesh.

See Also:
    :func:`~application.inventory.inventory_source_readiness`
        Application readiness fact that supplies the blocking reason.
    :class:`~application.aggregation.CalculationSourceResolution`
        Shared source-mesh envelope returned by this blocked resolver.
    :mod:`~application.aggregation._source_fincas`
        Sibling readiness adapter for the fincas calculation-source surface.
"""

from __future__ import annotations

from ...core import BindingSourceKind
from ..inventory import inventory_source_readiness
from ._source_mesh import (
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceResolution,
)


class InventorySourceReadinessResolver:
    """Refuse the inventory calculation source visibly until it is ready.

    Owns no live binding source (``owned_sources = ()``) because inventory is not
    enrolled as a calculation source.
    :meth:`~InventorySourceReadinessResolver.resolve` returns an empty resolution
    carrying a blocked-readiness diagnostic whenever inventory is not ready.
    """

    resolver_id = "inventory_readiness"
    owned_sources: tuple[BindingSourceKind, ...] = ()

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        """Return an empty resolution plus a blocked-readiness diagnostic when unready.

        Args:
            context: The calculation source context. Unused: inventory readiness is
                a context-independent fact (unready regardless of modelo or period).

        Returns:
            A :class:`~application.aggregation.CalculationSourceResolution` that
            resolves no binding value and carries one
            ``source_domain_not_ready`` diagnostic while inventory is not ready.
        """
        del context
        readiness = inventory_source_readiness()
        diagnostics: tuple[CalculationSourceDiagnostic, ...] = ()
        if not readiness.ready:
            diagnostics = (
                CalculationSourceDiagnostic(
                    reason="source_domain_not_ready",
                    source_kind=readiness.source_kind,
                    message=readiness.reason,
                    resolver_id=self.resolver_id,
                ),
            )
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=(),
            diagnostics=diagnostics,
        )


__all__ = ["InventorySourceReadinessResolver"]
