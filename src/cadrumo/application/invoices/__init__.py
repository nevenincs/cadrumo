"""Application invoice orchestration.

The initializer is inert; import contracts from their defining modules.

See Also:
    :mod:`domain.invoices`
        Invoice catalogue, line arithmetic, payment state, and the
        reconciliation/link authority this package orchestrates.
    :mod:`application.ledger`
        Payable/collectible invoice CRUD and ledger evidence links that
        converge with catalogue data at source resolution.
    :mod:`application.aggregation`
        Source-mesh envelope receiving invoice binding values, diagnostics,
        detail rows and provenance.
    :mod:`domain.calculations.registry`
        Binding declarations and invoice observation contracts consumed by
        modelo calculation.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
