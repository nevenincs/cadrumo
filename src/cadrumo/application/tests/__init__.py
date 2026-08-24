"""Application test-support helpers re-exported for cross-package reuse.

Colocated tests for :mod:`application` subpackages live next to the modules
they exercise; this facade exists only for the helper other packages' tests
need, so a cross-package consumer resolves here rather than reaching into a
private submodule.

It carries the autouse session fixture that registers the wizard catalogue,
from :mod:`application.tests._wizard_catalogue_fixtures`, imported by e2e and
fold-in suites across ``application.modelo.tests``,
``application.calculations.tests`` and ``application.aggregation.tests`` that
exercise wizard-backed casillas.
"""

from __future__ import annotations

from ._profile_backend_fixtures import _isolated_backend as isolated_profile_backend
from ._wizard_catalogue_fixtures import register_wizard_catalogue

__all__ = [
    "isolated_profile_backend",
    "register_wizard_catalogue",
]
