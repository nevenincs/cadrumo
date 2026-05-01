"""Builder ABC for the :mod:`aeat.application.filing` subpackage.

Concrete builders live under :mod:`aeat.application.filing._builders` and
register themselves on import. Callers from outside
:mod:`aeat.application.filing` MUST never import a builder directly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ._protocols import CasillaSchemaProvider, FilingInputs, FilingProfile
from ._schema import FilingDraft


class FilingBuilder(ABC):
    """Abstract base class for per-modelo draft builders."""

    #: The stable modelo string ID this builder produces drafts for.
    modelo_id: str

    @abstractmethod
    def build(
        self,
        *,
        period: str,
        profile: FilingProfile,
        inputs: FilingInputs,
        schema_provider: CasillaSchemaProvider,
    ) -> FilingDraft:
        """Build a :class:`FilingDraft` from raw inputs.

        Args:
            period: Period identifier (e.g. ``"2026Q1"``).
            profile: The :class:`FilingProfile` the draft is built
                for.
            inputs: Mapping of casilla ID → raw input value.
            schema_provider: Resolves the casilla collection for
                this builder's modelo.

        Returns:
            A frozen :class:`FilingDraft` with computed values
            populated. The draft's findings tuple is empty —
            validation is the validator's job, not the builder's.

        Raises:
            FilingComputationError: When a formula casilla cannot
                be evaluated (cycle, missing dependency, type
                mismatch).
        """
