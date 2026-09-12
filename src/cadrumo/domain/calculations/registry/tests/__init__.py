"""Inert namespace for registry test support.

Colocated unit tests for :mod:`domain.calculations.registry` live next to the
modules they exercise. Tests in other packages import shared helpers directly
from their defining test-support modules.

It carries the bundled manual worked-example oracle reader from
:mod:`domain.calculations.registry.tests.manual_oracle_support`, read by the
``application.modelo.tests`` and ``application.calculations.tests`` oracle
suites against the same bundled corpus, and the compile-only,
non-filing-grade ``build_snapshot`` helper for tests across
``application.modelo.tests`` and ``application.filing.tests`` that need a
snapshot without the filing-grade legal-review gate
``build_validated_snapshot`` hardcodes.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
