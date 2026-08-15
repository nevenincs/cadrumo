"""Shared test-only support for exercising the declared command-risk table."""

from __future__ import annotations

import contextlib
from collections.abc import Iterator

from ....application.operator_surface import COMMAND_RISK, CommandRiskDeclaration


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
