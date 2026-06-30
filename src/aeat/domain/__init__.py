"""Domain-layer package root for business vocabulary and authorities.

The root package is intentionally thin: it re-exports only
:class:`ModeloIdentifier` and does not aggregate every domain authority.
Callers import focused package facades such as :mod:`aeat.domain.modelos`,
:mod:`aeat.domain.filing`, :mod:`aeat.domain.user_profile`,
:mod:`aeat.domain.transactions`, and
:mod:`aeat.domain.calculations.registry` for records, repositories, schemas,
and validation rules.

Domain packages own business semantics: modelo work units and filing records,
calculation registry definitions, filing drafts, invoices, transactions,
deadlines, profile schema records, bucket events, and legal/manual reference
records. Application services compose these authorities with storage, CLI, and
adapter concerns; the domain root should stay import-light so importing
``aeat.domain`` never pulls registry, storage, browser, or workflow subtrees.

The domain root is also not the shared error hierarchy. Package-specific
``_errors`` modules own domain failure taxonomies, while the root validation
base remains in :mod:`aeat.domain._errors` for lightweight identifier parsing.

See Also:
    - :mod:`aeat.domain.modelos` for modelo work units, calculation revisions,
      filing records, verification reports, and related catalogues.
    - :mod:`aeat.domain.calculations.registry` for validated calculation
      registry authority and registry snapshot contracts.
    - :mod:`aeat.domain.filing` for draft, review, export, amendment, and local
      filing-history records.
    - :mod:`aeat.domain.user_profile` for user-profile schema and persisted
      profile value records.
    - :mod:`aeat.domain.transactions` for ledger transaction records and
      catalogues.

"""

from __future__ import annotations

from ._identifiers import ModeloIdentifier

__all__ = [
    "ModeloIdentifier",
]
