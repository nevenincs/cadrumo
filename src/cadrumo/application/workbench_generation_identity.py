"""The registered identity of the workbench generation operation.

Kept apart from the operation's module: the runtime compares every released
operation against it, and that comparison must not load the generation's
ledger, Modelo and registry graph.
"""

from __future__ import annotations

from typing import Final

WORKBENCH_GENERATION_OPERATION_DEFINITION_ID: Final = "workbench.generation"

__all__ = ["WORKBENCH_GENERATION_OPERATION_DEFINITION_ID"]
