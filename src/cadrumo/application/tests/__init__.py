"""Inert namespace for application test support.

Colocated tests for :mod:`application` subpackages live next to the modules
they exercise. Cross-package consumers import shared support from its defining
test-support module.

The wizard-catalogue fixture is defined in
:mod:`application.tests.wizard_catalogue_fixtures` and imported by e2e and
fold-in suites across ``application.modelo.tests``,
``application.calculations.tests`` and ``application.aggregation.tests`` that
exercise wizard-backed casillas.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
