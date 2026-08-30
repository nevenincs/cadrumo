"""Registered noun-group catalogue for the CRUD verb contract.

Every mutating noun-group in the operator-facing CLI registers a
:class:`MutatingNounGroupContract`. The catalogue exposed here is the
**single source of truth** consumed by cross-cutting conformance
tests.

Registered entries:

  - ``aeat app ledger evidence``     (locked CRUD reference shape)
  - ``aeat app ledger invoice``      (link-orthogonal CRUD, --kind issued|received)
  - ``aeat app ledger ratios``       (key-value-as-record exception)
  - ``aeat app ledger inventory``    (lifecycle operations)
  - ``aeat config auth apoderado``   (lifecycle operations)
  - ``aeat config storage``          (lifecycle operations)

Each entry documents the noun-group's intended verb set plus its
declared exception class. The conformance harness in
:mod:`cadrumo.application.operator_surface.tests.test_crud_registry` (and any
future CLI surface tests) consumes :data:`BUILTIN_CRUD_CATALOGUE` to
detect drift between shipped Typer subgroups and the locked design.
"""

from __future__ import annotations

from .crud_contract import (
    CrudContractCatalogue,
    KeyValueVerb,
    LifecycleStateVerb,
    MutatingNounGroupContract,
    NounGroupExceptionKind,
    OrthogonalAxis,
)

EVIDENCE = MutatingNounGroupContract(
    noun="purchase_invoice_evidence",
    cli_path="aeat app ledger evidence",
    # Reference shape: strict 5-verb CRUD, no orthogonal axes.
)

INVOICE = MutatingNounGroupContract(
    noun="invoice",
    cli_path="aeat app ledger invoice",
    # One unified invoice noun-group gated by ``--kind issued|received``.
    # The persisted payable_invoice / collectible_invoice taxonomy is
    # selected by --kind; the operator surface is a single CRUD noun-group
    # with the link-to-ledger-transaction orthogonal axis preserved (link
    # targets the rich InvoiceCatalogue, not this slim CRUD record).
    orthogonal_axes=frozenset({OrthogonalAxis.LINK}),
)

USAGE_RATIOS = MutatingNounGroupContract(
    noun="usage_ratio",
    cli_path="aeat app ledger ratios",
    # Key-value-as-record exception; the operator edits
    # keyed scalars (per-category proportions) rather than entities.
    exception=NounGroupExceptionKind.KEY_VALUE_AS_RECORD,
    crud_verbs=frozenset(),
    key_value_verbs=frozenset({KeyValueVerb.SET, KeyValueVerb.GET, KeyValueVerb.UNSET, KeyValueVerb.LIST}),
    # Two orthogonal read-only verbs (eligible, validate) sit outside
    # the OrthogonalAxis enum; documented inline as a noun-group
    # specific extension because they apply only to usage-ratio
    # records (eligibility check + parity validation against the
    # registry contract).
)

INVENTORY = MutatingNounGroupContract(
    noun="inventory_actividad",
    cli_path="aeat app ledger inventory",
    # Lifecycle-only exception: create + movement add + valuation
    # preview are distinct named operations rather than CRUD-shaped
    # surfaces — inventory entries do not behave as mutable records
    # the operator can edit field-by-field.
    exception=NounGroupExceptionKind.LIFECYCLE_OPERATIONS_ONLY,
    crud_verbs=frozenset(),
    lifecycle_state_verbs=frozenset({LifecycleStateVerb.RESET}),
)

APODERADO = MutatingNounGroupContract(
    noun="apoderado",
    cli_path="aeat config auth apoderado",
    # Lifecycle-only exception: an apoderado is configured or cleared
    # as a whole; configure + clear are state transitions and
    # status + check are read-only — there are no per-field CRUD
    # edits for an authorisation grant.
    exception=NounGroupExceptionKind.LIFECYCLE_OPERATIONS_ONLY,
    crud_verbs=frozenset(),
    lifecycle_state_verbs=frozenset({LifecycleStateVerb.RESET}),
)


STORAGE = MutatingNounGroupContract(
    noun="storage_area",
    cli_path="aeat config storage",
    # Lifecycle-only exception: the member set is fixed by the core storage
    # taxonomy, so an operator can neither add nor remove an aggregate area.
    # There is no per-field edit: ``reclaim`` resets regenerable contents,
    # ``init`` materialises the tree, and list / show / check read it.
    exception=NounGroupExceptionKind.LIFECYCLE_OPERATIONS_ONLY,
    crud_verbs=frozenset(),
    lifecycle_state_verbs=frozenset({LifecycleStateVerb.RESET}),
)


BUILTIN_CRUD_CATALOGUE: CrudContractCatalogue = CrudContractCatalogue(
    entries=(
        EVIDENCE,
        INVOICE,
        USAGE_RATIOS,
        INVENTORY,
        APODERADO,
        STORAGE,
    ),
)


def get_builtin_catalogue() -> CrudContractCatalogue:
    """Return the shipped :class:`CrudContractCatalogue`.

    Indirection through a function lets future code substitute a
    catalogue per test fixture without mutating module-level state.
    """
    return BUILTIN_CRUD_CATALOGUE


__all__ = [
    "APODERADO",
    "BUILTIN_CRUD_CATALOGUE",
    "EVIDENCE",
    "INVENTORY",
    "INVOICE",
    "STORAGE",
    "USAGE_RATIOS",
    "get_builtin_catalogue",
]
