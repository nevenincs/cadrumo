"""Shared test-only support for exercising the declared command-risk table.

Reached by cross-package consumers through this module's own path
(``from cadrumo.tests.declared_command_risk import declared_live_write``), per
this package's documented convention (see ``cadrumo/tests/__init__.py``) of
submodule-direct reach rather than promotion to the package facade.

Consolidated from three independently-authored copies: two under
``cadrumo_harness/mcp/tests/`` and one under the agent-evaluation test tree. Only the
first two shared a common owner narrower than this package -- the third
consumer is outside ``cadrumo_harness/mcp`` entirely, so ``cadrumo_harness/mcp/tests/``
was never a valid narrowest-common-owner home for all three, only an accident
of which two sites were authored first.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator

from ..application.operator_surface import COMMAND_RISK, CommandRiskDeclaration

__all__ = ["declared_live_write"]


@contextlib.contextmanager
def declared_live_write(command_key: str) -> Iterator[None]:
    """Declare ``command_key`` a live-write in the risk table for the test body.

    A live-write BLOCK now fires from the DECLARED risk table, not a leaf-name
    heuristic: no real command declares live_write (never-submit is enforced as
    "no such tool exists"), so a test that exercises the defensive BLOCK branch
    must supply a declared live-write row and restore the table after - test
    data, not a mocked behaviour.
    """
    previous = COMMAND_RISK.get(command_key)
    COMMAND_RISK[command_key] = CommandRiskDeclaration(live_write=True)
    try:
        yield
    finally:
        if previous is None:
            COMMAND_RISK.pop(command_key, None)
        else:
            COMMAND_RISK[command_key] = previous
