"""A provider catalog the caller already obtained from cadrumo-agent."""

from __future__ import annotations

from typing import override

from ..domain.catalog import ProviderCatalog
from .ports import ProviderCatalogSource


class ProvidedProviderCatalogSource(ProviderCatalogSource):
    """Serve the catalog another process obtained from the agent and handed over, unchanged.

    The runtime locates and runs the agent; a profile worker that resolves
    credentials for it receives the validated document rather than running the
    agent a second time.
    """

    def __init__(self, catalog: ProviderCatalog) -> None:
        """Keep the handed-over catalog."""
        self._catalog = catalog

    @override
    def catalog(self) -> ProviderCatalog:
        """Return the handed-over catalog."""
        return self._catalog


__all__ = ["ProvidedProviderCatalogSource"]
