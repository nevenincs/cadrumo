"""Finite locale families emitted by the inventory workbench and commands."""

from __future__ import annotations

from typing import TYPE_CHECKING, get_args

if TYPE_CHECKING:
    from .fstring_registry import FStringKeyRegistration


def inventory_dynamic_registrations() -> tuple[FStringKeyRegistration, ...]:
    """Register inventory keys from their domain and command-spec vocabularies."""
    from cadrumo.application.inventory.registered_projections import InventoryLedgerChangeProjection
    from cadrumo.domain.contribuyente.inventory.corrections import INVENTORY_CORRECTION_REFUSAL_REASONS
    from cadrumo.domain.contribuyente.inventory.records import (
        InventoryCorrectionReason,
        InventoryHistoryKind,
        InventoryRetirementReason,
    )

    from .fstring_registry import FStringKeyRegistration

    label_keys = tuple(
        f"application.inventory.labels.{family}.{member.value}"
        for family, enum in (
            ("correction_reason", InventoryCorrectionReason),
            ("history_kind", InventoryHistoryKind),
            ("retirement_reason", InventoryRetirementReason),
        )
        for member in enum
    )
    refusal_keys = tuple(
        f"application.inventory.service.errors.{reason}" for reason in INVENTORY_CORRECTION_REFUSAL_REASONS
    )
    change_outcomes = get_args(InventoryLedgerChangeProjection.model_fields["outcome"].annotation)
    done_keys = tuple(
        f"application.inventory.workbench.done.{outcome}"
        for outcome in change_outcomes
        if outcome in {"applied", "replayed"}
    )
    state_keys = (
        "application.inventory.workbench.state.active",
        "application.inventory.workbench.state.retired",
    )

    from ._command_spec_scanner import scan_command_spec_keys

    command_keys = tuple(sorted(key for key in scan_command_spec_keys() if key.startswith("cli.app.ledger.inventory.")))
    if not command_keys:
        raise RuntimeError("The command-spec registry declared no CLI inventory translation keys")

    return (
        FStringKeyRegistration(
            description="application.inventory.labels.* (closed inventory reason and history enums)",
            key_factory=lambda key: key,
            values=label_keys,
        ),
        FStringKeyRegistration(
            description="application.inventory.service.errors.* (typed inventory correction refusal reasons)",
            key_factory=lambda key: key,
            values=refusal_keys,
        ),
        FStringKeyRegistration(
            description="application.inventory.workbench.done.* (successful inventory change outcomes)",
            key_factory=lambda key: key,
            values=done_keys,
        ),
        FStringKeyRegistration(
            description="application.inventory.workbench.state.* (inventory ledger states)",
            key_factory=lambda key: key,
            values=state_keys,
        ),
        FStringKeyRegistration(
            description="cli.app.ledger.inventory.* (live command-spec TranslationKey fields)",
            key_factory=lambda key: key,
            values=command_keys,
        ),
    )
