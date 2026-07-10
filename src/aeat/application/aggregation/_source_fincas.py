"""Source-mesh readiness resolver adapter for the fincas domain.

Provisions the fincas calculation-source surface without enrolling it as a live
calculation source. The fincas domain is not yet ready to feed registry bindings
(:func:`~domain.fincas.fincas_source_readiness`), so this resolver resolves NO
binding value and emits a blocked-readiness
:class:`~application.aggregation.CalculationSourceDiagnostic`. It is deliberately
NOT registered in :func:`~application.aggregation.merge_source_resolutions`: it
exists so the surface is provisioned and its unreadiness is visible rather than a
silent blank (``no-dormant-source-resolvers``: provision the surface, refuse
visibly). When fincas persistence is hardened, the readiness flips and this
adapter is replaced by a real projecting resolver enrolled in the mesh.

See Also:
    :func:`~domain.fincas.fincas_source_readiness`
        Domain readiness fact that supplies the blocking reason.
    :class:`~application.aggregation.CalculationSourceResolution`
        Shared source-mesh envelope returned by this blocked resolver.
    :mod:`~application.aggregation._source_inventory`
        Sibling readiness adapter for the inventory calculation-source surface.
"""

from __future__ import annotations

from ...core import BindingSourceKind
from ...domain.fincas import fincas_source_readiness
from ._source_mesh import (
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceResolution,
)


class FincasSourceReadinessResolver:
    """Refuse the fincas calculation source visibly until it is ready.

    Owns no live binding source (``owned_sources = ()``) because fincas is not
    enrolled as a calculation source.
    :meth:`~FincasSourceReadinessResolver.resolve` returns an empty resolution
    carrying a blocked-readiness diagnostic whenever fincas is not ready.
    """

    resolver_id = "fincas_readiness"
    owned_sources: tuple[BindingSourceKind, ...] = ()

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        """Return an empty resolution plus a blocked-readiness diagnostic when unready.

        Args:
            context: The calculation source context. Unused: fincas readiness is a
                context-independent fact (unready regardless of modelo or period).

        Returns:
            A :class:`~application.aggregation.CalculationSourceResolution` that
            resolves no binding value and carries one
            ``source_domain_not_ready`` diagnostic while fincas is not ready.
        """
        del context
        readiness = fincas_source_readiness()
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


__all__ = ["FincasSourceReadinessResolver"]
