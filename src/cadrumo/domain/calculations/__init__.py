"""Namespace root for AEAT calculation-domain authorities.

This package is a namespace container, not a public aggregation facade. Callers
import the filing-grade registry authority from
:mod:`registry.authority`, registry snapshots from :mod:`registry.schema`, and
the calculator from :mod:`registry.formula_runtime`.

The package initializer exports no symbols. The generic row-source identity
value object is imported from its defining module.

See Also:
    :mod:`registry`
        Legal calculation registry, snapshot, formula, binding, relation,
        export-layout, and observation authority.
    :mod:`application.calculations`
        Application-side source stores and prefill helpers that prepare
        registry binding and relation inputs without becoming domain authority.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
