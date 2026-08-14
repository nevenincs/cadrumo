"""Registry test-support helpers re-exported for cross-package reuse.

Colocated unit tests for :mod:`domain.calculations.registry` live next to the
modules they exercise and import their support helpers directly; this facade
exists only for the helpers that tests in *other* packages need, so a
cross-package consumer resolves here rather than reaching into a private
submodule.

It carries the bundled manual worked-example oracle reader from
:mod:`domain.calculations.registry.tests._manual_oracle_support`, read by the
``application.modelo.tests`` and ``application.calculations.tests`` oracle
suites against the same bundled corpus.
"""

from __future__ import annotations

from ._manual_oracle_support import read_manual_worked_example

__all__ = [
    "read_manual_worked_example",
]
