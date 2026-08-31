"""Public defining module for the ``modelo work verify`` revision selector.

The verify command advertises a narrowed selector set rather than the full
:class:`ModeloCalculationRevisionSelector`, and the CLI command spec resolves
this enum by name at parameter-build time, so the contract is required outside
its owning package and lives in a public module of its own.
"""

from __future__ import annotations

from enum import StrEnum

from .selectors import ModeloCalculationRevisionSelector


class ModeloVerifySelector(StrEnum):
    """Draft-reachable selector subset accepted by ``modelo work verify``.

    ``verify_modelo_revision`` refuses any revision not in state ``BORRADOR``,
    so the only selectors that can resolve to a verifiable revision are the ones
    that reach a draft: ``current`` (when the current revision is still a draft),
    ``latest-draft``, and ``explicit`` (an explicitly-named draft revision id).
    The post-draft selectors ``latest-verified`` and ``filed`` on the full
    :class:`ModeloCalculationRevisionSelector` name states verify rejects, so
    advertising them on the verify command would be an advertised-but-impossible
    combination. This narrowed enum is what the verify ``--select`` option advertises;
    other commands keep the full selector enum.
    """

    CURRENT = "current"
    LATEST_DRAFT = "latest-draft"
    EXPLICIT = "explicit"

    def to_calculation_revision_selector(self) -> ModeloCalculationRevisionSelector:
        """Map a verify selector to its :class:`ModeloCalculationRevisionSelector` member."""
        return ModeloCalculationRevisionSelector(self.value)


__all__ = ["ModeloVerifySelector"]
