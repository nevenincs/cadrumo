"""Review surface: queue projection, filters, edits and review-state actions.

Inert namespace. Import directly from the owning module:
:mod:`~cadrumo.application.review.enums` for the closed review vocabularies
(:class:`ReviewSeverity`, :class:`ReviewState`, :class:`ReviewItemKind`),
:mod:`~cadrumo.application.review.models` for the queue records and rows,
:mod:`~cadrumo.application.review.filter` for filter-clause parsing,
:mod:`~cadrumo.application.review.actions` for the review-state mutations,
:mod:`~cadrumo.application.review.operator` for the operator-facing queue
projection, and :mod:`~cadrumo.application.review.errors` for the error
hierarchy -- including :class:`FilterParseError` and :class:`EditParseError`,
which are DEFINED there rather than in the modules that parse.

This package previously carried a PEP 562 lazy re-export map. It is retired:
every consumer now imports the owning submodule directly, so the package does
nothing at import time. The map is not merely gone but was actively
misleading -- it named ``._filter`` as the home of :class:`FilterParseError`
and ``._edit`` as the home of :class:`EditParseError`, when both are defined
in :mod:`~cadrumo.application.review.errors` and were only re-exported by the
parsers. A consumer following the map reached a re-export shim rather than
the defining module.
"""

__all__: list[str] = []
