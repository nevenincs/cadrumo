"""Leaf-module shim for the ``filed`` filing-status token.

This module exists so :mod:`aeat.application.operator_surface._contract`
can reference the same ``"filed"`` token that
:class:`aeat.application.overview._status.FilingStatus` exposes, WITHOUT
importing the overview package at module load (the overview package
pulls the registry, which the state-free ``aeat --help`` surface gate
forbids).

The token here MUST stay equal to
``aeat.application.overview._status.FilingStatus.FILED.value`` — a
unit test in
:mod:`aeat.application.operator_surface.test_filing_status_token`
asserts the equality on every run so the duplication cannot drift.
"""

from __future__ import annotations

from typing import Final

FILED: Final[str] = "filed"
"""The ``filed`` token used by the LIVE family's command tuple.

Mirrors :attr:`aeat.application.overview._status.FilingStatus.FILED`
without importing the overview package.
"""
