"""Full-screen Textual frontend for the paged interactive-flow substrate.

This package is a rendering adapter over
:class:`~cadrumo.application.flows.FlowState` and the engine transitions:
it contains zero flow logic. Every semantic — visibility, validation,
staleness, deferral, checkpoint availability, submit eligibility — is an
engine call whose result the screens render. The substrate never imports
this package; a host that cannot run the full-screen application
degrades to the line-mode frontend.
"""

from __future__ import annotations

from ._app import FlowTuiApp, run_flow_tui
from ._select import select_flow_frontend

__all__ = ["FlowTuiApp", "run_flow_tui", "select_flow_frontend"]
