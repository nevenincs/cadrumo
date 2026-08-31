"""Registry test-support helpers re-exported for cross-package reuse.

Colocated unit tests for :mod:`domain.calculations.registry` live next to the
modules they exercise and import their support helpers directly; this facade
exists only for the helpers that tests in *other* packages need, so a
cross-package consumer resolves here rather than reaching into a private
submodule -- or, for ``build_snapshot``, into a same-package sibling symbol
the production package deliberately excludes from its own ``__all__``.

It carries the bundled manual worked-example oracle reader from
:mod:`domain.calculations.registry.tests._manual_oracle_support`, read by the
``application.modelo.tests`` and ``application.calculations.tests`` oracle
suites against the same bundled corpus, and ``build_snapshot`` -- the
compile-only, non-filing-grade snapshot builder demoted from the production
package's ``__all__`` -- for tests across
``application.modelo.tests`` and ``application.filing.tests`` that need a
snapshot without the filing-grade legal-review gate
``build_validated_snapshot`` hardcodes.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
