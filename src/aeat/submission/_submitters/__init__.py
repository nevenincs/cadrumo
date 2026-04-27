"""Submitter ABC and concrete per-modelo dry-run implementations.

Each concrete :class:`Submitter` drives the AEAT portal walk for one
modelo. The ABC defines the dry-run coroutine
:meth:`Submitter.dry_run`, which takes the
narrow :class:`BrowserSessionLike` Protocol so unit tests can pass
deterministic Protocol implementations without spinning up Playwright.
"""

from __future__ import annotations

import abc

from .._models import SubmissionAttempt
from .._protocols import (
    CasillaCatalogue,
    FilingDraftLike,
    Portal,
)
from ._contract import BrowserSessionLike


class Submitter(abc.ABC):
    """Abstract base class for per-modelo portal walkers.

    Concrete subclasses walk the AEAT portal for one modelo, fill
    casilla-keyed inputs from :attr:`FilingDraftLike.values`, and
    abort before the final "Firmar y Enviar" click.
    """

    @property
    @abc.abstractmethod
    def modelo(self) -> str:
        """Return the modelo identifier this submitter handles."""

    @abc.abstractmethod
    async def dry_run(
        self,
        *,
        draft: FilingDraftLike,
        session: BrowserSessionLike,
        casilla_catalogue: CasillaCatalogue,
        portal: Portal,
        amendment_kind: str | None = None,
        original_csv: str | None = None,
    ) -> SubmissionAttempt:
        """Perform every portal step EXCEPT the final "Firmar y Enviar" click.

        Args:
            draft: The ready-to-submit filing draft.
            session: Browser session Protocol implementation.
            casilla_catalogue: Casilla metadata catalogue.
            portal: The AEAT portal descriptor for this modelo.
            amendment_kind: Optional AEAT amendment mode when the
                filing is being submitted as a complementaria or
                sustitutiva.
            original_csv: Optional justificante CSV of the original
                filing being amended.

        Returns:
            A :class:`SubmissionAttempt` recording the dry-run outcome.
        """


__all__ = ["BrowserSessionLike", "Submitter"]
