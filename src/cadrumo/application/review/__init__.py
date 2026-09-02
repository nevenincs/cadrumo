"""Review surface: queue projection and filters.

Inert namespace. Import directly from the owning module:
:mod:`~cadrumo.application.review.enums` for the closed review vocabularies
(:class:`ReviewSeverity`, :class:`ReviewState`, :class:`ReviewItemKind`),
:mod:`~cadrumo.application.review.models` for the queue records and rows,
:mod:`~cadrumo.application.review.filter` for filter-clause parsing,
:mod:`~cadrumo.application.review.operator` for the operator-facing queue
projection, and :mod:`~cadrumo.application.review.errors` for the error
hierarchy, including :class:`FilterParseError`.

This package previously carried a PEP 562 lazy re-export map. It is retired:
every consumer now imports the owning submodule directly, so the package does
nothing at import time.
"""

__all__: list[str] = []
