"""Two facts about every registered operation, from which a narrower MCP surface is derived.

Every registered operation is open to every frontend, and nothing here opens
or closes one. A person may still start an MCP connection on a narrower
surface, and a surface is declared by two properties: whether anything on it
can change the profile's records, and whether anything on it reaches the
network. This module states both for each operation.

A definition declares its permitted effects and nothing about the network, so
the first fact follows the declaration except where a definition permits more
than its executor does, and the second is recorded from reading the executors.
Where reading did not settle a fact, the operation is recorded under the wider
answer.

Operations are named by definition id text. This package owns no feature
package's constants, and importing them would invert the dependency.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final


@dataclass(frozen=True, slots=True)
class OperationSurfaceFacts:
    """What one operation can do that a narrower surface may declare it does not."""

    definition_id: str
    changes_records: bool
    """The operation can commit a change: to the profile's stored records, or a file it writes."""
    reaches_network: bool
    """The operation can contact a host other than this machine."""


_LOCAL_READS: Final = (
    "app.review.queue",
    "app.review.view",
    # The apoderado check contacts nothing: its remote step is not built.
    "auth.apoderado.check",
    "auth.apoderado.status",
    "auth.certificate.source.check",
    "auth.certificate.source.list",
    # Reads stored authentication state, although its definition permits an update.
    "auth.local-read",
    "config.collab.recipient.list",
    "config.google.folder.view",
    "config.google.status",
    "diagnostics.read",
    "diagnostics.secure-objects.check",
    "ledger.actividad-asset.filing-handoff",
    "ledger.actividad-asset.forecast",
    "ledger.actividad-asset.inspect",
    # The register listings of bienes de inversión, inventory and prorrata read
    # only, although their definitions permit an update.
    "ledger.bienes_inversion.list",
    "ledger.check",
    "ledger.evidence.attachment_queue",
    "ledger.evidence.attachment_view",
    "ledger.evidence.consent.list",
    "ledger.evidence.list",
    "ledger.evidence.query",
    "ledger.evidence.review.list",
    "ledger.evidence.review.summary",
    "ledger.evidence.review.view",
    "ledger.evidence.view",
    "ledger.history",
    "ledger.history.typed",
    "ledger.inventory.list",
    "ledger.invoice.list",
    "ledger.invoice.view",
    "ledger.list",
    "ledger.llm-diagnostics",
    "ledger.participation",
    "ledger.preflight",
    "ledger.prorrata.list",
    "ledger.ratios.eligible",
    "ledger.ratios.list",
    "ledger.ratios.validate",
    "ledger.review",
    "ledger.rule.list",
    "ledger.status",
    "ledger.track",
    "ledger.view",
    # A capture reads the tax agency through a browser and stores what it saw.
    # The live operations listed here read what earlier captures stored.
    "live.borrador.100.query",
    "live.borrador.100.read",
    "live.expedientes.latest",
    "live.expedientes.list",
    "live.expedientes.show",
    "live.iva-wallet.history",
    "live.justificante.list",
    "live.justificante.show",
    "live.notifications.document.history",
    "live.notifications.document.view",
    "live.notifications.latest",
    "live.notifications.list",
    "live.notifications.show",
    "live.verify.latest",
    "live.verify.list",
    "live.verify.view",
    "modelo.036.query",
    "modelo.036.read",
    "modelo.audit.query",
    "modelo.audit.read",
    "modelo.bindings.list",
    "modelo.bindings.resolve",
    "modelo.bindings.resolve.typed",
    "modelo.filing_record.list",
    "modelo.filing_record.view",
    "modelo.history",
    "modelo.history.timeline",
    "modelo.iva-wallet.balance",
    "modelo.m145.validate",
    "modelo.readiness",
    "modelo.readiness.summary",
    "modelo.reconcile.list",
    "modelo.requires",
    "modelo.verification_report.list",
    "modelo.verification_report.view",
    "modelo.work.amendment_context",
    "modelo.work.compare_taxation",
    "modelo.work.dependencies",
    "modelo.work.filing_record",
    "modelo.work.history",
    "modelo.work.list",
    "modelo.work.metadata",
    "modelo.work.preview_maritime_exemption",
    # Verifying a report reads the named file and the profile's own key.
    "modelo.work.report_verify",
    "modelo.work.review",
    "modelo.work.revision",
    "modelo.work.revision_snapshot",
    "modelo.work.revisions",
    "modelo.work.wizard_context",
    "overview.agenda",
    "overview.backlog",
    "overview.calendar",
    "overview.explain",
    "overview.pipeline",
    "overview.prepare",
    "overview.status",
    "profile.history",
    "provider-settings.status",
    "profile.history.timeline",
    "user-profile.censo-prepare",
    "user-profile.recovery.status",
    "user-profile.view",
    "workflow.resume.context",
    "workflow.run.list",
    "workflow.run.read",
)

_NETWORK_READS: Final = (
    # The probe browses once to the tax agency's public landing page and reads its answer.
    "diagnostics.connectivity.probe",
    # The next four ask the local model runtime for its inventory at its
    # endpoint setting, which can name another host.
    "diagnostics.workstation.check",
    "ledger.evidence.reader-readiness",
    "local-reader.report",
    "local-reader.status",
)

_LOCAL_WRITES: Final = (
    "auth.apoderado.clear",
    "auth.apoderado.configure",
    "auth.certificate.secret.remove",
    "auth.certificate.secret.set",
    "auth.certificate.source.register",
    "auth.certificate.source.remove",
    "auth.certificate.source.select",
    "auth.diagnostics.phone-state-report",
    "auth.profile.passphrase-rotate",
    "auth.provider.configure",
    "auth.session.logout",
    "auth.session.reset",
    "config.collab.recipient.add",
    "config.collab.recipient.remove",
    # Sign-out deletes the stored session and contacts nothing.
    "config.google.logout",
    # Quarantine moves unreadable objects aside within the profile's own store.
    "diagnostics.secure-objects.quarantine",
    "diagnostics.workflow-progress.reset",
    "export.calculation-review-xlsx",
    "ledger.actividad-asset.claim",
    "ledger.actividad-asset.correct",
    "ledger.actividad-asset.create",
    "ledger.allocate",
    "ledger.archive",
    "ledger.attach",
    "ledger.bienes_inversion.declare",
    "ledger.classify.bulk",
    "ledger.classify.iva-derive",
    "ledger.classify.single",
    "ledger.counterparty",
    "ledger.detach",
    "ledger.evidence.add",
    "ledger.evidence.remove",
    "ledger.evidence.update",
    "ledger.exclude",
    "ledger.export",
    "ledger.inventory.closing-authority.record",
    "ledger.inventory.create",
    "ledger.inventory.movement.add",
    # The preview records valuation events despite its name.
    "ledger.inventory.valuation.preview",
    "ledger.invoice.remove",
    "ledger.invoice.update",
    "ledger.link",
    "ledger.merge",
    "ledger.own_account",
    # The index is derived from stored revisions and filing records; a rebuild regenerates it.
    "ledger.participation.rebuild",
    "ledger.prorrata.declare_sector",
    "ledger.prorrata.elect_especial",
    "ledger.prorrata.elect_general",
    "ledger.prorrata.revoke_especial",
    "ledger.prorrata.seed",
    "ledger.prorrata.seed_sector",
    "ledger.prorrata.settle_sector",
    "ledger.ratios.set",
    "ledger.ratios.unset",
    "ledger.remove",
    "ledger.reset",
    "ledger.restore",
    "ledger.rule.add",
    "ledger.rule.apply",
    "ledger.split.manual",
    "ledger.stash",
    "ledger.update",
    "live.borrador.100.import",
    "modelo.036.record",
    "modelo.aggregate.capture_received_invoice_retencion",
    "modelo.audit.export",
    # The next six, the workbench reads and the workbench generation, declare
    # no committed effect, yet their resolver holds the commit action for
    # every submission, and a form read admits an edit baseline. Reading did
    # not settle that nothing is stored, so each is recorded as able to commit.
    "modelo.edit.apply_prerequisite",
    "modelo.edit.preflight",
    "modelo.edit.renew",
    "modelo.work.casilla_help",
    "modelo.work.form",
    "workbench.generation",
    "modelo.export",
    "modelo.filing_record.import",
    "modelo.iva-wallet.correct",
    "modelo.iva-wallet.override",
    "modelo.iva-wallet.seed",
    "modelo.m145.create",
    "modelo.m145.export",
    "modelo.m145.mark_delivered_to_payer",
    "modelo.m145.mark_locally_completed",
    "modelo.m360_solicitud",
    "modelo.observation.local",
    "modelo.reconcile.export-xlsx",
    "modelo.reconcile.import",
    "modelo.reconcile.pull",
    "modelo.review_package.build",
    "modelo.review_package.counter_sign",
    "modelo.review_package.decrypt",
    "modelo.review_package.encrypt_feedback",
    "modelo.review_package.encrypt_for_recipient",
    "modelo.review_package.import_feedback",
    "modelo.review_package.sign",
    "modelo.spreadsheet.export",
    "modelo.work.amend",
    "modelo.work.create",
    "modelo.work.discard",
    "modelo.work.file",
    "modelo.work.m303_attestation",
    "modelo.work.rename",
    # Verification reads and writes the profile's own store; its provider step
    # builds local objects only and opens no browser or session.
    "modelo.work.verify",
    "profile.archive.export",
    "provider-settings.remove",
    "provider-settings.reset",
    "provider-settings.set",
    "user-profile.automation-approve",
    "user-profile.automation-decline",
    "user-profile.automation-inventory",
    "user-profile.automation-renew",
    "user-profile.automation-request",
    "user-profile.automation-rotate",
    "user-profile.automation-scope",
    "user-profile.bundle-export",
    # The certificate is read from a file on this machine and parsed here.
    "user-profile.censo-certificate-import",
    "user-profile.censo-file-import",
    "user-profile.complete-setup",
    "user-profile.descendants",
    "user-profile.field-mutation",
    "user-profile.patch",
    "user-profile.plantilla-media",
    "user-profile.recovery.revoke",
    "user-profile.repeatable-row-mutation",
    "user-profile.repeatable-row-remove",
    "user-profile.repeatable-row-update",
)

_NETWORK_WRITES: Final = (
    "auth.session.acquire",
    # The browser build is downloaded.
    "browser-runtime.provision",
    "config.google.folder.organize",
    "config.google.login",
    "config.google.probe",
    "export.google-review",
    "export.google-sheets",
    # A ledger or invoice write that converts a foreign-currency amount looks
    # its rate up at the central bank.
    "ledger.add",
    # The model-backed reviews and the extraction call the local reader at its
    # endpoint setting, which can name another host.
    "ledger.classify.review",
    "ledger.evidence.batch",
    # Confirmation creates the invoice, which may need an exchange rate.
    "ledger.evidence.confirm",
    "ledger.evidence.extract",
    "ledger.import",
    "ledger.invoice.add",
    "ledger.invoice.import",
    "ledger.invoice.wizard",
    "ledger.split.review",
    "live.expedientes.capture.bulk",
    "live.expedientes.capture.single",
    "live.filed-capture.bulk",
    "live.filed-capture.single",
    "live.filed-capture.source",
    "live.filed-discover",
    "live.filed-history.pull",
    "live.filed-list",
    "live.iva-wallet.capture",
    "live.iva-wallet.evidence-capture",
    "live.iva-wallet.history-capture",
    "live.justificante.capture",
    "live.notifications.capture",
    "live.notifications.document.capture",
    "live.verify.nif-iva",
    "live.verify.tgvi",
    # The component download needs the network.
    "local-reader.provision",
    # A calculation that values foreign assets looks exchange rates up at the
    # central bank, so the operations that calculate reach the network.
    "modelo.aggregate",
    "modelo.compare",
    # An apply calculates; reading did not settle that it never reaches the rate lookup.
    "modelo.edit.apply",
    "modelo.project",
    # The chain calculates and verifies before it exports.
    "modelo.quickfile",
    "modelo.work.calculate",
    "modelo.work.wizard_attempt",
    "profile.archive.push",
    # Reconciling export journals goes through the mirror port; reading did not
    # settle that it never asks the remote provider.
    "profile.archive.reconcile",
    "user-profile.censo-preview",
    "user-profile.censo-review",
)


def _index() -> Mapping[str, OperationSurfaceFacts]:
    groups = (
        (_LOCAL_READS, False, False),
        (_NETWORK_READS, False, True),
        (_LOCAL_WRITES, True, False),
        (_NETWORK_WRITES, True, True),
    )
    indexed: dict[str, OperationSurfaceFacts] = {}
    for definition_ids, changes_records, reaches_network in groups:
        for definition_id in definition_ids:
            if definition_id in indexed:
                raise ValueError(f"{definition_id}: an operation has exactly one record of its surface facts")
            indexed[definition_id] = OperationSurfaceFacts(
                definition_id=definition_id, changes_records=changes_records, reaches_network=reaches_network
            )
    return MappingProxyType(dict(sorted(indexed.items())))


_BY_DEFINITION_ID: Final = _index()

OPERATION_SURFACE_FACTS: Final[tuple[OperationSurfaceFacts, ...]] = tuple(_BY_DEFINITION_ID.values())
"""The recorded facts of every operation, sorted by definition id."""


def operation_surface_facts(definition_id: str) -> OperationSurfaceFacts:
    """Return the recorded facts of one operation, or fail closed."""
    try:
        return _BY_DEFINITION_ID[definition_id]
    except KeyError:
        raise KeyError(f"operation has no recorded surface facts: {definition_id!r}") from None


__all__ = ["OPERATION_SURFACE_FACTS", "OperationSurfaceFacts", "operation_surface_facts"]
