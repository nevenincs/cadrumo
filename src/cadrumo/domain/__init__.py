"""Domain-layer package root for business vocabulary and authorities.

The root package is intentionally thin: it re-exports only
:class:`ModeloIdentifier` and does not aggregate every domain authority.
Callers import the exact public defining modules that own records,
repositories, schemas, and validation rules. For user-profile contracts,
those modules are :mod:`user_profile.values`, :mod:`user_profile.schema`,
:mod:`user_profile.loader`, :mod:`user_profile.errors`, and
:mod:`user_profile.registry_contract`.

Domain packages own business semantics: modelo work units and filing records,
calculation registry definitions, filing drafts, invoices, transactions,
deadlines, profile schema records, bucket events, and legal/manual reference
records. Application services compose these authorities with storage, CLI, and
adapter concerns; the domain root should stay import-light so importing
``cadrumo.domain`` never pulls registry, storage, browser, or workflow subtrees.

The domain root is also not the shared error hierarchy. Package-specific
``_errors`` modules own domain failure taxonomies, while the root validation
base remains in :mod:`_errors` for lightweight identifier parsing.

See Also:
    - :mod:`modelos` for modelo work units, calculation revisions,
      filing records, verification reports, and related catalogues.
    - :mod:`calculations.registry` for validated calculation
      registry authority and registry snapshot contracts.
    - :mod:`filing` for draft, review, export, amendment, and local
      filing-history records.
    - :mod:`user_profile.schema` and :mod:`user_profile.values` for
      user-profile schema and persisted profile value records.
    - :mod:`transactions` for ledger transaction records and
      catalogues.

"""

from __future__ import annotations

from ._identifiers import ModeloIdentifier, canonical_decimal_string

__all__ = [
    "ModeloIdentifier",
    "canonical_decimal_string",
]
