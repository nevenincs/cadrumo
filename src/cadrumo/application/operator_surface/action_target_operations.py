"""The registered operations each command a catalogue action targets can submit.

A frontend routes an offered recovery action by the registered operation
definitions its target command submits, not by the command's spelling. This
process holds no command graph, so the relation is recorded here for every
command a catalogue action targets, in the order the command-operation table
lists it. A command that submits no registered operation, or belongs to
another executable, has no entry. The record is checked against the
command-operation table, so a command whose operations change fails that check
until this record follows it.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

ACTION_TARGET_OPERATION_IDS: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType(
    {
        "app.live.filed.pull": ("live.filed-capture.bulk", "live.filed-capture.single"),
        "app.live.filed.pull_all": ("live.filed-history.pull",),
        "app.live.notifications.list": ("live.notifications.list",),
        "config.profile.archive.reconcile": ("profile.archive.reconcile",),
        "config.profile.arrendamiento.list": ("user-profile.view",),
        "config.profile.ascendiente.list": ("user-profile.view",),
        "config.profile.complete_setup": ("user-profile.complete-setup", "user-profile.view"),
        "config.profile.create": ("user-profile.patch", "user-profile.view"),
        "config.profile.descendiente.list": ("user-profile.view",),
        "config.profile.edit": ("user-profile.patch", "user-profile.view"),
        "config.profile.status": ("user-profile.view",),
        "ledger.account.add": ("ledger.own_account",),
        "ledger.actividad_asset.correct": ("ledger.actividad-asset.correct",),
        "ledger.classify": (
            "ledger.classify.bulk",
            "ledger.classify.iva-derive",
            "ledger.classify.review",
            "ledger.classify.single",
            "ledger.view",
        ),
        "ledger.counterparty.filing_name": ("ledger.counterparty",),
        "ledger.evidence.review.list": ("ledger.evidence.review.list",),
        "ledger.inventory.movement.claim": ("ledger.inventory.movement.claim",),
        "ledger.invoice.update": ("ledger.invoice.update",),
        "ledger.link": ("ledger.link",),
        "ledger.preflight": ("ledger.preflight",),
        "ledger.prorrata.list": ("ledger.prorrata.list",),
        "ledger.review": ("ledger.review",),
        "modelo.bindings.list": ("modelo.bindings.list",),
        "modelo.export": ("modelo.export", "modelo.work.revision"),
        "modelo.filing_record.import": ("modelo.filing_record.import",),
        "modelo.filing_record.list": ("modelo.filing_record.list",),
        "modelo.iva_wallet.override": ("modelo.iva-wallet.override",),
        "modelo.iva_wallet.seed": ("modelo.iva-wallet.seed",),
        "modelo.verification_report.list": ("modelo.verification_report.list",),
        "modelo.work.attest_m303_exonerado_390": ("modelo.work.m303_attestation",),
        "modelo.work.attest_prior_carries": ("modelo.edit.apply", "modelo.edit.preflight", "modelo.work.form"),
        "modelo.work.attest_prior_value": ("modelo.edit.apply", "modelo.edit.preflight", "modelo.work.form"),
        "modelo.work.attest_work_income": ("modelo.edit.apply", "modelo.edit.preflight", "modelo.work.form"),
        "modelo.work.calculate": ("modelo.work.calculate", "modelo.work.metadata"),
        "modelo.work.create": ("modelo.work.create",),
        "modelo.work.file": ("modelo.work.file", "modelo.work.revision"),
        "modelo.work.list": ("modelo.work.list",),
        "modelo.work.override": ("modelo.edit.apply", "modelo.edit.preflight", "modelo.work.form"),
        "modelo.work.revisions": ("modelo.work.metadata", "modelo.work.revisions"),
        "modelo.work.set_value": ("modelo.edit.apply", "modelo.edit.preflight", "modelo.work.form"),
        "modelo.work.status": ("modelo.work.metadata",),
        "modelo.work.verify": ("modelo.work.revision", "modelo.work.verify"),
        "overview.explain": ("overview.explain",),
        "overview.status": ("overview.status",),
    }
)
"""Ordered registered operation ids keyed by the catalogue's target command key."""


def target_operation_ids(command_key: str) -> tuple[str, ...]:
    """The registered operations ``command_key`` submits, in recorded order; empty when it submits none."""
    return ACTION_TARGET_OPERATION_IDS.get(command_key, ())


__all__ = ["ACTION_TARGET_OPERATION_IDS", "target_operation_ids"]
