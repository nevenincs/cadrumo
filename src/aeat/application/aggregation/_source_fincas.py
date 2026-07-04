"""Source-mesh readiness resolver adapter for the fincas domain.

Provisions the fincas calculation-source surface without enrolling it as a live
calculation source. The fincas domain is not yet ready to feed registry bindings
(:func:`~domain.fincas.fincas_source_readiness`), so this resolver resolves NO
binding value and emits a blocked-readiness :class:`CalculationSourceDiagnostic`.
It is deliberately NOT registered in ``merge_source_resolutions``: it exists so the
surface is provisioned and its unreadiness is visible rather than a silent blank
(``no-dormant-source-resolvers``: provision the surface, refuse visibly). When
fincas persistence is hardened, the readiness flips and this adapter is replaced by
a real projecting resolver enrolled in the mesh.
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
    enrolled as a calculation source. :meth:`resolve` returns an empty resolution
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
            A :class:`CalculationSourceResolution` that resolves no binding value
            and carries one ``source_domain_not_ready`` diagnostic while fincas is
            not ready.
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
