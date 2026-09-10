"""No production command authority for bundled-registry authoring work.

The shipped application consumes the immutable bundled registry while
calculating and filing. Inspection, corpus verification, revision comparison,
and filed-state comparisons belong to development conformance tooling.
"""

from __future__ import annotations

from .command_spec import CommandSpec

REGISTRY_COMMAND_SPECS: tuple[CommandSpec, ...] = ()

__all__ = ["REGISTRY_COMMAND_SPECS"]
