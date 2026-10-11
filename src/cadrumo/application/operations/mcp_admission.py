"""The recorded MCP decision for every registered operation.

Listing the MCP frontend on a definition is what opens an operation to an MCP
client, and a frontend is never granted silently. This table records, for each
operation, whether it may be opened and what still stands in the way, so a
definition can neither gain nor keep the frontend against its decision.

Each row also states two facts a narrower surface is derived from: whether the
operation can change the profile's records, and whether it reaches the network.
Neither fact is declared by a definition today, so both are recorded here from
reading the executors. Where reading did not settle a fact, the row records the
wider answer.

Rows are keyed by definition id text. This package owns no feature package's
constants, and importing them would invert the dependency.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final, NamedTuple


class McpRuling(StrEnum):
    """What an MCP client may do with one operation."""

    ADMITTED = "admitted"
    """The operation may list the MCP frontend."""
    ADMITTED_BEHIND_APPROVAL = "admitted_behind_approval"
    """A sensitive act: an MCP client runs it only after the person approves that exact act."""
    EXCLUDED = "excluded"
    """The operation stays off the MCP frontend for the recorded reason."""


class McpExclusionReason(StrEnum):
    """The closed grounds on which an operation stays off the MCP frontend."""

    CANNOT_RUN_FROM_MCP = "cannot_run_from_mcp"
    """A typed secret, an interaction other than a review, or a terminal-only flow."""
    ACCESS_ADMINISTRATION = "access_administration"
    """Authentication, certificates, keys and grants, locking and resuming."""
    MACHINE_ADMINISTRATION = "machine_administration"
    """Administration of the machine or its storage."""
    PERSON_PROJECTION = "person_projection"
    """A projection written for a person; an agent-facing sibling serves its content."""
    NOT_RUNNABLE = "not_runnable"
    """The definition has no access resolver or needs a typed secret."""


class McpAdmissionPrerequisite(StrEnum):
    """What still stands between a ruling to admit and listing the MCP frontend.

    A prerequisite gates the listing. It is not a list of the defects of an
    operation that already lists the frontend.
    """

    FILE_EXCHANGE = "file_exchange"
    """The operation takes or writes a host path, and how files reach it is not decided."""
    SAFEGUARD_MOVE = "safeguard_move"
    """A confirmation or validation still lives in the command line or terminal interface."""
    ADMISSION_CHECKLIST = "admission_checklist"
    """Nothing specific is outstanding, but the definition has not been taken through admission."""
    RESULT_TEXT_BOUND = "result_text_bound"
    """A result field carries text from outside the application that no contract bounds."""


@dataclass(frozen=True, slots=True)
class McpAdmissionDecision:
    """One operation's recorded MCP decision and the two facts a surface is derived from."""

    definition_id: str
    ruling: McpRuling
    changes_records: bool
    """The operation can commit a change: to the profile's stored records, or a file it writes."""
    reaches_network: bool
    """The operation can contact a host other than this machine."""
    exclusion_reason: McpExclusionReason | None = None
    agent_facing_sibling: str | None = None
    prerequisites: frozenset[McpAdmissionPrerequisite] = frozenset()
    sensitive_actions: tuple[str, ...] = ()
    """Acts inside an admitted definition that need the person's approval.

    A label is the definition's own action value where its request carries one,
    and otherwise names the request feature that carries the act.
    """

    def __post_init__(self) -> None:
        """Refuse a row whose parts contradict its ruling."""
        excluded = self.ruling is McpRuling.EXCLUDED
        if excluded != (self.exclusion_reason is not None):
            raise ValueError(f"{self.definition_id}: an exclusion reason belongs to an excluded row, and only to one")
        projection = self.exclusion_reason is McpExclusionReason.PERSON_PROJECTION
        if projection != (self.agent_facing_sibling is not None):
            raise ValueError(f"{self.definition_id}: an agent-facing sibling belongs to a person's projection")
        if self.agent_facing_sibling == self.definition_id:
            raise ValueError(f"{self.definition_id}: an operation is not its own agent-facing sibling")
        if excluded and self.prerequisites:
            raise ValueError(f"{self.definition_id}: an excluded row has no admission prerequisite")
        if self.sensitive_actions and self.ruling is not McpRuling.ADMITTED:
            raise ValueError(f"{self.definition_id}: sensitive actions are named only inside an admitted definition")
        if len(set(self.sensitive_actions)) != len(self.sensitive_actions):
            raise ValueError(f"{self.definition_id}: sensitive actions must be unique")


class _Facts(NamedTuple):
    changes_records: bool
    reaches_network: bool


_READS: Final = _Facts(changes_records=False, reaches_network=False)
_READS_ONLINE: Final = _Facts(changes_records=False, reaches_network=True)
_WRITES: Final = _Facts(changes_records=True, reaches_network=False)
_WRITES_ONLINE: Final = _Facts(changes_records=True, reaches_network=True)

_FILES: Final = McpAdmissionPrerequisite.FILE_EXCHANGE
_SAFEGUARD: Final = McpAdmissionPrerequisite.SAFEGUARD_MOVE
_CHECKLIST: Final = McpAdmissionPrerequisite.ADMISSION_CHECKLIST
_TEXT: Final = McpAdmissionPrerequisite.RESULT_TEXT_BOUND

_ACCESS: Final = McpExclusionReason.ACCESS_ADMINISTRATION
_CANNOT_RUN: Final = McpExclusionReason.CANNOT_RUN_FROM_MCP
_NOT_RUNNABLE: Final = McpExclusionReason.NOT_RUNNABLE


def _admit(
    definition_id: str,
    facts: _Facts,
    *pending: McpAdmissionPrerequisite,
    sensitive: tuple[str, ...] = (),
) -> McpAdmissionDecision:
    return McpAdmissionDecision(
        definition_id=definition_id,
        ruling=McpRuling.ADMITTED,
        changes_records=facts.changes_records,
        reaches_network=facts.reaches_network,
        prerequisites=frozenset(pending),
        sensitive_actions=sensitive,
    )


def _approve(definition_id: str, facts: _Facts, *pending: McpAdmissionPrerequisite) -> McpAdmissionDecision:
    return McpAdmissionDecision(
        definition_id=definition_id,
        ruling=McpRuling.ADMITTED_BEHIND_APPROVAL,
        changes_records=facts.changes_records,
        reaches_network=facts.reaches_network,
        prerequisites=frozenset(pending),
    )


def _exclude(definition_id: str, facts: _Facts, reason: McpExclusionReason) -> McpAdmissionDecision:
    return McpAdmissionDecision(
        definition_id=definition_id,
        ruling=McpRuling.EXCLUDED,
        changes_records=facts.changes_records,
        reaches_network=facts.reaches_network,
        exclusion_reason=reason,
    )


def _serve_by(definition_id: str, sibling: str) -> McpAdmissionDecision:
    return McpAdmissionDecision(
        definition_id=definition_id,
        ruling=McpRuling.EXCLUDED,
        changes_records=False,
        reaches_network=False,
        exclusion_reason=McpExclusionReason.PERSON_PROJECTION,
        agent_facing_sibling=sibling,
    )


_REVIEW_AND_DIAGNOSTICS: Final = (
    _admit("app.review.queue", _READS),
    _admit("app.review.view", _READS),
    _admit("diagnostics.read", _READS),
    _exclude("diagnostics.workstation.check", _READS, McpExclusionReason.MACHINE_ADMINISTRATION),
    *(
        _admit(f"overview.{kind}", _READS)
        for kind in ("agenda", "backlog", "calendar", "explain", "pipeline", "prepare", "status")
    ),
)

_AUTHENTICATION: Final = (
    # The apoderado check contacts nothing: its remote step is not built.
    _admit("auth.apoderado.check", _READS),
    _exclude("auth.apoderado.clear", _WRITES, _ACCESS),
    _exclude("auth.apoderado.configure", _WRITES, _ACCESS),
    _admit("auth.apoderado.status", _READS),
    _exclude("auth.certificate.secret.remove", _WRITES, _ACCESS),
    _exclude("auth.certificate.secret.set", _WRITES, _ACCESS),
    _exclude("auth.certificate.source.check", _READS, _ACCESS),
    _exclude("auth.certificate.source.list", _READS, _ACCESS),
    _exclude("auth.certificate.source.register", _WRITES, _ACCESS),
    _exclude("auth.certificate.source.remove", _WRITES, _ACCESS),
    _exclude("auth.certificate.source.select", _WRITES, _ACCESS),
    _exclude("auth.diagnostics.phone-state-report", _WRITES, _ACCESS),
    _admit("auth.local-read", _READS),
    _exclude("auth.profile.passphrase-rotate", _WRITES, _ACCESS),
    _exclude("auth.provider.configure", _WRITES, _ACCESS),
    _exclude("auth.session.acquire", _WRITES_ONLINE, _ACCESS),
    _admit("auth.session.logout", _WRITES),
    _approve("auth.session.reset", _WRITES),
)

_GOOGLE_AND_SHARING: Final = (
    _approve("config.collab.recipient.add", _WRITES),
    _admit("config.collab.recipient.list", _READS),
    _approve("config.collab.recipient.remove", _WRITES),
    _approve("config.google.folder.organize", _WRITES_ONLINE),
    _admit("config.google.folder.view", _READS),
    # The person gives this consent in a browser.
    _exclude("config.google.login", _WRITES_ONLINE, _CANNOT_RUN),
    # Sign-out deletes the stored session and contacts nothing.
    _approve("config.google.logout", _WRITES),
    # The probe report's detail is the provider's own failure text, whatever it says.
    _admit("config.google.probe", _WRITES_ONLINE, _TEXT),
    _admit("config.google.status", _READS),
    _admit("export.calculation-review-xlsx", _WRITES, _FILES, _SAFEGUARD),
    _approve("export.google-review", _WRITES_ONLINE, _SAFEGUARD),
    _exclude("export.google-sheets", _WRITES_ONLINE, _NOT_RUNNABLE),
    _approve("profile.archive.export", _WRITES, _FILES),
    _approve("profile.archive.push", _WRITES_ONLINE),
    _approve("profile.archive.reconcile", _WRITES),
    _serve_by("profile.history", "profile.history.timeline"),
    _admit("profile.history.timeline", _READS),
)

# A ledger write that converts a foreign-currency amount looks its rate up at
# the central bank, so those rows reach the network.
_LEDGER_ENTRIES: Final = (
    _admit("ledger.add", _WRITES_ONLINE, _SAFEGUARD),
    _admit("ledger.allocate", _WRITES, _CHECKLIST),
    _admit("ledger.archive", _WRITES),
    # Attach links evidence already stored, by identifier, and takes no file.
    _admit("ledger.attach", _WRITES),
    _admit("ledger.check", _READS),
    _admit("ledger.classify.bulk", _WRITES),
    _admit("ledger.classify.iva-derive", _WRITES),
    # The model-backed reviews call the local reader at its endpoint setting, which can name another host.
    _admit("ledger.classify.review", _WRITES_ONLINE),
    _admit("ledger.classify.single", _WRITES, _SAFEGUARD),
    _admit("ledger.counterparty", _WRITES),
    # Detach removes one row's link and keeps the attachment's stored bytes.
    _admit("ledger.detach", _WRITES),
    _admit("ledger.exclude", _WRITES),
    _admit("ledger.export", _WRITES, _FILES),
    _serve_by("ledger.history", "ledger.history.typed"),
    _admit("ledger.history.typed", _READS),
    _admit("ledger.import", _WRITES_ONLINE, _FILES, _SAFEGUARD),
    _admit("ledger.link", _WRITES),
    _admit("ledger.list", _READS),
    _admit("ledger.llm-diagnostics", _READS),
    _approve("ledger.merge", _WRITES),
    _admit(
        "ledger.own_account",
        _WRITES,
        sensitive=("add", "update", "close", "remove", "designate", "undesignate"),
    ),
    _admit("ledger.participation", _READS),
    # The index is derived from stored revisions and filing records; a rebuild regenerates it.
    _admit("ledger.participation.rebuild", _WRITES),
    _admit("ledger.preflight", _READS),
    _admit("ledger.ratios.eligible", _READS),
    _admit("ledger.ratios.list", _READS),
    _admit("ledger.ratios.set", _WRITES),
    _admit("ledger.ratios.unset", _WRITES),
    _admit("ledger.ratios.validate", _READS),
    _approve("ledger.remove", _WRITES),
    _approve("ledger.reset", _WRITES),
    _admit("ledger.restore", _WRITES),
    _admit("ledger.review", _READS),
    _admit("ledger.rule.add", _WRITES),
    # A run that reaffirms replaces classifications set by hand and keeps no
    # earlier value, so an agent may preview it but not run it.
    _admit("ledger.rule.apply", _WRITES, sensitive=("reaffirm",)),
    _admit("ledger.rule.list", _READS),
    # A split keeps its parent stored; only the approval-bound merge recombines the cohort.
    _admit("ledger.split.manual", _WRITES),
    _admit("ledger.split.review", _WRITES_ONLINE),
    _admit("ledger.stash", _WRITES),
    _admit("ledger.status", _READS),
    _admit("ledger.track", _READS),
    _admit("ledger.update", _WRITES, _CHECKLIST),
    _admit("ledger.view", _READS),
)

_LEDGER_EVIDENCE_AND_INVOICES: Final = (
    _admit("ledger.evidence.add", _WRITES, _FILES),
    _admit("ledger.evidence.attachment_queue", _READS),
    _admit("ledger.evidence.attachment_view", _READS),
    _admit("ledger.evidence.batch", _WRITES_ONLINE, _FILES),
    # Confirmation creates the invoice, which may need an exchange rate.
    _approve("ledger.evidence.confirm", _WRITES_ONLINE),
    _admit("ledger.evidence.consent.list", _READS),
    # Reading a document off the machine is a consent, never a field the caller sets.
    # An agent's read also runs only while the on-host reader answers on this machine.
    _admit("ledger.evidence.extract", _WRITES_ONLINE, sensitive=("off_host",)),
    _serve_by("ledger.evidence.list", "ledger.evidence.query"),
    _admit("ledger.evidence.query", _READS),
    _admit("ledger.evidence.reader-readiness", _READS_ONLINE),
    _approve("ledger.evidence.remove", _WRITES),
    _admit("ledger.evidence.review.list", _READS),
    _admit("ledger.evidence.review.summary", _READS),
    _serve_by("ledger.evidence.review.view", "ledger.evidence.review.summary"),
    # An update edits the record's descriptive fields; the stored bytes, a pending
    # draft and the invoice catalogue are out of its reach.
    _admit("ledger.evidence.update", _WRITES),
    _serve_by("ledger.evidence.view", "ledger.evidence.query"),
    _admit("ledger.invoice.add", _WRITES_ONLINE),
    _admit("ledger.invoice.import", _WRITES_ONLINE, _FILES),
    _admit("ledger.invoice.list", _READS),
    _approve("ledger.invoice.remove", _WRITES),
    _admit("ledger.invoice.update", _WRITES),
    _admit("ledger.invoice.view", _READS),
    # The wizard is a typed entry with every field stated up front, never a
    # prompt; an invoice in another currency looks its rate up.
    _admit("ledger.invoice.wizard", _WRITES_ONLINE),
)

_LEDGER_REGISTERS: Final = (
    _admit("ledger.actividad-asset.claim", _WRITES),
    _admit("ledger.actividad-asset.correct", _WRITES),
    _admit("ledger.actividad-asset.create", _WRITES),
    _admit("ledger.actividad-asset.filing-handoff", _READS),
    _admit("ledger.actividad-asset.forecast", _READS),
    _admit("ledger.actividad-asset.inspect", _READS),
    _admit("ledger.bienes_inversion.declare", _WRITES),
    _admit("ledger.bienes_inversion.list", _READS),
    _admit("ledger.inventory.closing-authority.record", _WRITES),
    _admit("ledger.inventory.create", _WRITES),
    _admit("ledger.inventory.list", _READS),
    _admit("ledger.inventory.movement.add", _WRITES),
    # The preview records valuation events despite its name.
    _admit("ledger.inventory.valuation.preview", _WRITES),
    _admit("ledger.prorrata.declare_sector", _WRITES),
    _approve("ledger.prorrata.elect_especial", _WRITES),
    _approve("ledger.prorrata.elect_general", _WRITES),
    _admit("ledger.prorrata.list", _READS),
    _approve("ledger.prorrata.revoke_especial", _WRITES),
    _admit("ledger.prorrata.seed", _WRITES),
    _admit("ledger.prorrata.seed_sector", _WRITES),
    _admit("ledger.prorrata.settle_sector", _WRITES),
)

# A capture reads the tax agency through a browser and stores what it saw. The
# other live operations read what earlier captures stored.
_LIVE: Final = (
    _admit("live.borrador.100.import", _WRITES, _FILES),
    _admit("live.borrador.100.query", _READS),
    _serve_by("live.borrador.100.read", "live.borrador.100.query"),
    _admit("live.expedientes.capture.bulk", _WRITES_ONLINE),
    _admit("live.expedientes.capture.single", _WRITES_ONLINE),
    _admit("live.expedientes.latest", _READS),
    _admit("live.expedientes.list", _READS),
    _admit("live.expedientes.show", _READS),
    _admit("live.filed-capture.bulk", _WRITES_ONLINE),
    _admit("live.filed-capture.single", _WRITES_ONLINE),
    _admit("live.filed-capture.source", _WRITES_ONLINE),
    _admit("live.filed-discover", _WRITES_ONLINE),
    _admit("live.filed-history.pull", _WRITES_ONLINE),
    _admit("live.filed-list", _WRITES_ONLINE),
    _admit("live.iva-wallet.capture", _WRITES_ONLINE),
    _admit("live.iva-wallet.evidence-capture", _WRITES_ONLINE),
    _admit("live.iva-wallet.history", _READS),
    _admit("live.iva-wallet.history-capture", _WRITES_ONLINE),
    _admit("live.justificante.capture", _WRITES_ONLINE),
    _admit("live.justificante.list", _READS),
    _admit("live.justificante.show", _READS),
    _admit("live.notifications.capture", _WRITES_ONLINE),
    _admit("live.notifications.document.capture", _WRITES_ONLINE),
    _admit("live.notifications.document.history", _READS),
    _admit("live.notifications.document.view", _READS),
    _admit("live.notifications.latest", _READS),
    _admit("live.notifications.list", _READS),
    _admit("live.notifications.show", _READS),
    _admit("live.verify.latest", _READS),
    _admit("live.verify.list", _READS),
    _admit("live.verify.nif-iva", _WRITES_ONLINE),
    _admit("live.verify.tgvi", _WRITES_ONLINE),
    _admit("live.verify.view", _READS),
)

# A calculation that values foreign assets looks exchange rates up at the
# central bank, so the rows that calculate reach the network.
_MODELO_WORK: Final = (
    _admit("modelo.aggregate", _WRITES_ONLINE),
    _admit("modelo.aggregate.capture_received_invoice_retencion", _WRITES),
    _admit("modelo.bindings.list", _READS),
    _serve_by("modelo.bindings.resolve", "modelo.bindings.resolve.typed"),
    _admit("modelo.bindings.resolve.typed", _READS),
    _admit("modelo.compare", _WRITES_ONLINE),
    _exclude("modelo.edit.apply", _WRITES, _CANNOT_RUN),
    _exclude("modelo.edit.apply_prerequisite", _READS, _CANNOT_RUN),
    _exclude("modelo.edit.preflight", _READS, _CANNOT_RUN),
    _exclude("modelo.edit.renew", _READS, _CANNOT_RUN),
    _approve("modelo.export", _WRITES, _FILES, _SAFEGUARD),
    # Every import that writes leaves a record that reads as confirmed by the tax agency, from
    # values the caller states: it confirms or retires a pending local filing in the same act.
    _approve("modelo.filing_record.import", _WRITES, _FILES),
    _admit("modelo.filing_record.list", _READS),
    _admit("modelo.filing_record.view", _READS),
    _serve_by("modelo.history", "modelo.history.timeline"),
    _admit("modelo.history.timeline", _READS),
    # An operator figure is never official evidence and blocks the verification that needs it.
    # Clearing one keeps no copy. An agent's figure also never replaces a local filing's observation.
    _admit("modelo.observation.local", _WRITES, sensitive=("clear",)),
    _admit("modelo.project", _WRITES_ONLINE),
    # The chain calculates and verifies before it exports.
    _approve("modelo.quickfile", _WRITES_ONLINE, _FILES, _SAFEGUARD),
    _serve_by("modelo.readiness", "modelo.readiness.summary"),
    _admit("modelo.readiness.summary", _READS),
    _admit("modelo.reconcile.export-xlsx", _WRITES, _FILES, _SAFEGUARD),
    # An agent may originate the import: it compares a document with the local
    # record, stores the comparison, and returns the verdict and differences
    # for the person to review.
    _admit("modelo.reconcile.import", _WRITES),
    _admit("modelo.reconcile.list", _READS),
    _admit("modelo.reconcile.pull", _WRITES),
    _admit("modelo.requires", _READS),
    _admit("modelo.spreadsheet.export", _WRITES, _FILES),
    _admit("modelo.verification_report.list", _READS),
    _admit("modelo.verification_report.view", _READS),
    # Amending verifies and records the correction as filed locally in one act,
    # and retires the record it corrects: the same act as marking a return filed.
    _approve("modelo.work.amend", _WRITES, _SAFEGUARD),
    _exclude("modelo.work.amendment_context", _READS, _CANNOT_RUN),
    # An explicit calculation stores its inputs as the person's own entries, and the
    # Modelo 303 election and exemption attestation are the person's statements.
    _admit("modelo.work.calculate", _WRITES_ONLINE, sensitive=("explicit", "ordinary_m303_filing_evidence")),
    _exclude("modelo.work.casilla_help", _READS, _CANNOT_RUN),
    _admit("modelo.work.compare_taxation", _READS),
    _admit("modelo.work.create", _WRITES),
    _admit("modelo.work.dependencies", _READS),
    _approve("modelo.work.discard", _WRITES),
    _approve("modelo.work.file", _WRITES, _SAFEGUARD),
    _admit("modelo.work.filing_record", _READS),
    _exclude("modelo.work.form", _READS, _CANNOT_RUN),
    _serve_by("modelo.work.history", "modelo.history.timeline"),
    _admit("modelo.work.list", _READS),
    _approve("modelo.work.m303_attestation", _WRITES),
    _admit("modelo.work.metadata", _READS),
    _admit("modelo.work.preview_maritime_exemption", _READS),
    _admit("modelo.work.rename", _WRITES),
    _admit("modelo.work.report_verify", _READS, _FILES),
    _admit("modelo.work.review", _READS),
    _admit("modelo.work.revision", _READS),
    _admit("modelo.work.revision_snapshot", _READS),
    _admit("modelo.work.revisions", _READS),
    # Verification reads and writes the profile's own store; its provider step builds
    # local objects only and opens no browser or session.
    _admit("modelo.work.verify", _WRITES),
    _exclude("modelo.work.wizard_attempt", _WRITES_ONLINE, _CANNOT_RUN),
    _exclude("modelo.work.wizard_context", _READS, _CANNOT_RUN),
    _exclude("workbench.generation", _READS, _CANNOT_RUN),
    _admit("workflow.resume.context", _READS),
    _admit("workflow.run.list", _READS),
    _admit("workflow.run.read", _READS),
)

_MODELO_RECORDS: Final = (
    _admit("modelo.036.query", _READS),
    _serve_by("modelo.036.read", "modelo.036.query"),
    _approve("modelo.036.record", _WRITES),
    _admit("modelo.audit.export", _WRITES, _FILES),
    _admit("modelo.audit.query", _READS),
    _serve_by("modelo.audit.read", "modelo.audit.query"),
    _admit("modelo.iva-wallet.balance", _READS),
    _approve("modelo.iva-wallet.correct", _WRITES, _SAFEGUARD),
    _approve("modelo.iva-wallet.override", _WRITES, _SAFEGUARD),
    _approve("modelo.iva-wallet.seed", _WRITES, _SAFEGUARD),
    # A draft that fills the worker's signature block or the payer's acknowledgement states a signature.
    _admit("modelo.m145.create", _WRITES, sensitive=("signed_block",)),
    _admit("modelo.m145.export", _WRITES, _FILES),
    _approve("modelo.m145.mark_delivered_to_payer", _WRITES),
    _approve("modelo.m145.mark_locally_completed", _WRITES),
    _admit("modelo.m145.validate", _READS),
    _admit("modelo.m360_solicitud", _WRITES, sensitive=("declare", "remove")),
    _admit("modelo.review_package.build", _WRITES, _FILES),
    _approve("modelo.review_package.counter_sign", _WRITES, _FILES),
    _approve("modelo.review_package.decrypt", _WRITES, _FILES),
    _approve("modelo.review_package.encrypt_feedback", _WRITES, _FILES),
    _approve("modelo.review_package.encrypt_for_recipient", _WRITES, _FILES),
    _approve("modelo.review_package.import_feedback", _WRITES, _FILES),
    _approve("modelo.review_package.sign", _WRITES, _FILES),
)

_PROFILE: Final = (
    # The component download needs the network.
    _exclude("local-reader.provision", _WRITES_ONLINE, _NOT_RUNNABLE),
    _exclude("user-profile.automation-approve", _WRITES, _ACCESS),
    _exclude("user-profile.automation-decline", _WRITES, _ACCESS),
    _exclude("user-profile.automation-inventory", _WRITES, _ACCESS),
    _exclude("user-profile.automation-renew", _WRITES, _NOT_RUNNABLE),
    _exclude("user-profile.automation-request", _WRITES, _NOT_RUNNABLE),
    _exclude("user-profile.automation-rotate", _WRITES, _NOT_RUNNABLE),
    _exclude("user-profile.automation-scope", _WRITES, _NOT_RUNNABLE),
    _exclude("user-profile.bundle-export", _WRITES, _NOT_RUNNABLE),
    _admit("user-profile.censo-file-import", _WRITES, _FILES),
    _admit("user-profile.censo-prepare", _READS),
    _admit("user-profile.censo-preview", _WRITES_ONLINE),
    _approve("user-profile.censo-review", _WRITES_ONLINE),
    _admit("user-profile.complete-setup", _WRITES),
    _admit("user-profile.descendants", _WRITES),
    # Opting a service capability in is a consent, whichever operation writes it.
    _admit("user-profile.field-mutation", _WRITES, sensitive=("capabilities",)),
    _admit("user-profile.patch", _WRITES, sensitive=("capabilities",)),
    _admit("user-profile.plantilla-media", _WRITES),
    _admit("user-profile.recovery.status", _READS),
    _admit("user-profile.repeatable-row-mutation", _WRITES),
    _admit("user-profile.repeatable-row-remove", _WRITES),
    _admit("user-profile.repeatable-row-update", _WRITES),
    _admit("user-profile.view", _READS),
)


def _index(rows: tuple[McpAdmissionDecision, ...]) -> Mapping[str, McpAdmissionDecision]:
    indexed: dict[str, McpAdmissionDecision] = {}
    for row in rows:
        if row.definition_id in indexed:
            raise ValueError(f"{row.definition_id}: an operation has exactly one recorded MCP decision")
        indexed[row.definition_id] = row
    return MappingProxyType(dict(sorted(indexed.items())))


_BY_DEFINITION_ID: Final = _index(
    (
        *_REVIEW_AND_DIAGNOSTICS,
        *_AUTHENTICATION,
        *_GOOGLE_AND_SHARING,
        *_LEDGER_ENTRIES,
        *_LEDGER_EVIDENCE_AND_INVOICES,
        *_LEDGER_REGISTERS,
        *_LIVE,
        *_MODELO_WORK,
        *_MODELO_RECORDS,
        *_PROFILE,
    )
)

MCP_ADMISSION_DECISIONS: Final[tuple[McpAdmissionDecision, ...]] = tuple(_BY_DEFINITION_ID.values())
"""Every recorded decision, sorted by definition id."""

MCP_OVER_DECLARED_EFFECTS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "auth.local-read": "reads stored authentication state under an update capability set",
        "ledger.bienes_inversion.list": "lists the register under its family's update capability set",
        "ledger.inventory.list": "lists the register under its family's update capability set",
        "ledger.prorrata.list": "lists the register under its family's update capability set",
    }
)
"""Definitions that permit a committed effect although the operation only reads.

Each is recorded as not changing records. An entry leaves this mapping when its
definition stops permitting the effect; nothing is added without reading the
executor.
"""


@dataclass(frozen=True, slots=True)
class McpHostPathFields:
    """The members of one operation's request and result that carry a host filesystem path.

    A member is named by its dotted path from the model root, and ``[]`` marks
    a member of a sequence or mapping value.
    """

    request: frozenset[str] = frozenset()
    result: frozenset[str] = frozenset()


MCP_HOST_PATH_FIELDS: Final[Mapping[str, McpHostPathFields]] = MappingProxyType(
    {
        # A capture's output root is checked for its form and echoed. The captured
        # records go to the profile's encrypted object store, and nothing is
        # opened or written under the root.
        "live.filed-capture.bulk": McpHostPathFields(
            request=frozenset({"output_root"}), result=frozenset({"output_root"})
        ),
        "live.filed-capture.single": McpHostPathFields(
            request=frozenset({"output_root"}), result=frozenset({"output_root"})
        ),
        "live.filed-capture.source": McpHostPathFields(
            request=frozenset({"output_root"}), result=frozenset({"output_root"})
        ),
        "live.filed-history.pull": McpHostPathFields(request=frozenset({"output_root"})),
        "live.iva-wallet.evidence-capture": McpHostPathFields(
            request=frozenset({"output_root"}), result=frozenset({"output_root"})
        ),
        "live.iva-wallet.history-capture": McpHostPathFields(
            request=frozenset({"output_root"}), result=frozenset({"output_root"})
        ),
        # An agent's execution seals the stored file name alone in this member.
        "ledger.evidence.update": McpHostPathFields(result=frozenset({"record.source_path"})),
        # The import opens and reads the named file and returns its path; a listing
        # and a pull return the reference an earlier import recorded. An agent's
        # execution seals a typed path to its file name in each result member;
        # a handle on stored evidence names no directory and passes through.
        "modelo.reconcile.import": McpHostPathFields(
            request=frozenset({"source_path"}), result=frozenset({"source_path"})
        ),
        "modelo.reconcile.list": McpHostPathFields(result=frozenset({"reconciliations[].source_path"})),
        "modelo.reconcile.pull": McpHostPathFields(result=frozenset({"source_path"})),
        # The configured certificate file's path appears in the stored authentication
        # state. An agent's execution seals the file name alone in these members.
        "auth.local-read": McpHostPathFields(result=frozenset({"status.certificate_path", "test.certificate_path"})),
    }
)
"""Operations open to MCP whose request or result carries a host filesystem path.

No operation open to MCP takes a host path or returns one until how files reach
an agent is decided, so each entry is a recorded exception, not a permission.
An entry leaves this mapping when its definition stops carrying the path or
stops listing MCP; nothing is added without reading the executor. A test holds
the mapping to the registered models in both directions.
"""


def mcp_admission_decision(definition_id: str) -> McpAdmissionDecision:
    """Return the recorded decision for one operation, or fail closed."""
    try:
        return _BY_DEFINITION_ID[definition_id]
    except KeyError:
        raise KeyError(f"operation has no recorded MCP decision: {definition_id!r}") from None


__all__ = [
    "MCP_ADMISSION_DECISIONS",
    "MCP_HOST_PATH_FIELDS",
    "MCP_OVER_DECLARED_EFFECTS",
    "McpAdmissionDecision",
    "McpAdmissionPrerequisite",
    "McpExclusionReason",
    "McpHostPathFields",
    "McpRuling",
    "mcp_admission_decision",
]
