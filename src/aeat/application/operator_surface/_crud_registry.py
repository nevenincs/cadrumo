"""Registered noun-group catalogue for the CRUD verb contract.

Per apex ADR §12.b, every mutating noun-group in the redesigned CLI
registers a :class:`MutatingNounGroupContract`. The catalogue exposed
here is the **single source of truth** consumed by cross-cutting
conformance tests and W72-W77 reconciliation waves.

Entries shipped in this initial registry:

  - ``aeat app ledger evidence``     (W70.P333 locked CRUD reference)
  - ``aeat app ledger payable-invoice``      (W73A)
  - ``aeat app ledger collectible-invoice``  (W73A)
  - ``aeat app ledger ratios``       (key-value exception)
  - ``aeat app ledger inventory``    (lifecycle operations)
  - ``aeat config auth apoderado``   (W75A; lifecycle operations)

Each entry documents the noun-group's intended verb set plus its
declared exception class. The conformance harness in
:mod:`aeat.application.operator_surface.test_crud_registry` (and any
future CLI surface tests) consumes :data:`BUILTIN_CRUD_CATALOGUE` to
detect drift between shipped Typer subgroups and the locked design.
"""

from __future__ import annotations

from ._crud_contract import (
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
    # W70.P333 reference shape: strict 5-verb CRUD, no orthogonal axes.
)

PAYABLE_INVOICE = MutatingNounGroupContract(
    noun="payable_invoice",
    cli_path="aeat app ledger payable-invoice",
    # W73A: strict 5-verb CRUD with link-to-ledger-transaction orthogonal axis.
    orthogonal_axes=frozenset({OrthogonalAxis.LINK}),
)

COLLECTIBLE_INVOICE = MutatingNounGroupContract(
    noun="collectible_invoice",
    cli_path="aeat app ledger collectible-invoice",
    orthogonal_axes=frozenset({OrthogonalAxis.LINK}),
)

USAGE_RATIOS = MutatingNounGroupContract(
    noun="usage_ratio",
    cli_path="aeat app ledger ratios",
    # Key-value-as-record exception per W71 contract; the operator edits
    # keyed scalars (per-category proportions) rather than entities.
    exception=NounGroupExceptionKind.KEY_VALUE_AS_RECORD,
    crud_verbs=frozenset(),
    key_value_verbs=frozenset({KeyValueVerb.SET, KeyValueVerb.GET, KeyValueVerb.UNSET, KeyValueVerb.LIST}),
    # The 2026-05-13 ledger-ratios-eligible-and-validate ADR adds two
    # orthogonal read-only verbs (eligible, validate). They're not in
    # the OrthogonalAxis enum; documented inline as a noun-group
    # specific extension.
)

INVENTORY = MutatingNounGroupContract(
    noun="inventory_actividad",
    cli_path="aeat app ledger inventory",
    # Lifecycle-only exception: create + movement add + valuation
    # preview are distinct named operations rather than CRUD-shaped
    # CRUD per the inventory-placement ADR.
    exception=NounGroupExceptionKind.LIFECYCLE_OPERATIONS_ONLY,
    crud_verbs=frozenset(),
    lifecycle_state_verbs=frozenset({LifecycleStateVerb.RESET}),
)

APODERADO = MutatingNounGroupContract(
    noun="apoderado",
    cli_path="aeat config auth apoderado",
    # Lifecycle-only exception per apoderamientos-surface ADR §3.3:
    # configure + clear are state transitions, status + check are
    # read-only.
    exception=NounGroupExceptionKind.LIFECYCLE_OPERATIONS_ONLY,
    crud_verbs=frozenset(),
    lifecycle_state_verbs=frozenset({LifecycleStateVerb.RESET}),
)


BUILTIN_CRUD_CATALOGUE: CrudContractCatalogue = CrudContractCatalogue(
    entries=(
        EVIDENCE,
        PAYABLE_INVOICE,
        COLLECTIBLE_INVOICE,
        USAGE_RATIOS,
        INVENTORY,
        APODERADO,
    ),
)


def get_builtin_catalogue() -> CrudContractCatalogue:
    """Return the shipped noun-group catalogue.

    Indirection through a function lets future code substitute a
    catalogue per test fixture without mutating module-level state.
    """
    return BUILTIN_CRUD_CATALOGUE


__all__ = [
    "APODERADO",
    "BUILTIN_CRUD_CATALOGUE",
    "COLLECTIBLE_INVOICE",
    "EVIDENCE",
    "INVENTORY",
    "PAYABLE_INVOICE",
    "USAGE_RATIOS",
    "get_builtin_catalogue",
]
