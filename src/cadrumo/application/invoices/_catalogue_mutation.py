"""The one guarded write seam every catalogue-mutating service goes through.

The invoice catalogue is a SINGLETON encrypted row: adding, correcting or
removing one invoice is really read-whole-catalogue, rebuild, write-whole
catalogue. Performed unguarded, two services touching DIFFERENT invoices both
read the same catalogue and the later write discards the earlier one -- silently,
because the two invoices never met and no uniqueness constraint sees them. On a
financial catalogue that lost row is a dropped invoice, which under-declares.

This module exists so the three mutating services share ONE answer to that,
rather than each growing its own load-modify-save and drifting.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from ...domain.invoices import InvoiceCatalogue, InvoiceCatalogueRepositoryProtocol


def mutate_catalogue(
    repository: InvoiceCatalogueRepositoryProtocol,
    mutation: Callable[[InvoiceCatalogue], InvoiceCatalogue],
) -> InvoiceCatalogue:
    """Apply ``mutation`` to the stored catalogue as one revision-guarded unit of work.

    ``mutation`` MUST be a pure function of the catalogue it is handed. It is
    called once per attempt, so every refusal and every merge inside it is
    re-judged against the catalogue the write actually lands on -- which is the
    point of routing through here rather than deciding once against a catalogue
    that may already be superseded.

    Args:
        repository: The catalogue repository to write through.
        mutation: Builds the next catalogue from the current one. Raising
            refuses the whole mutation, unretried; a refusal is not the
            contention the retry exists for.

    Returns:
        The catalogue as written.
    """
    guarded = getattr(repository, "mutate", None)
    if guarded is not None:
        return guarded(mutation)
    return _unguarded_protocol_fallback(repository, mutation)


def _unguarded_protocol_fallback(
    repository: InvoiceCatalogueRepositoryProtocol,
    mutation: Callable[[InvoiceCatalogue], InvoiceCatalogue],
) -> InvoiceCatalogue:
    """Load-then-save for a repository that offers no guarded path.

    The narrow domain protocol promises only ``exists``/``load``/``save``, so an
    injected alternative may provide exactly that and no more. Such a repository
    carries the lost-update exposure this fallback cannot close; it is reachable
    only by a caller that injects one, never by the production path, which
    resolves the concrete repository and takes the guarded branch above.
    """
    catalogue = repository.load()
    updated = mutation(catalogue)
    repository.save(updated)
    return updated


__all__ = ["mutate_catalogue"]
