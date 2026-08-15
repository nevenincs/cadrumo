"""Declared per-command risk classification, keyed by full command key.

The MCP console's tool annotations and its human-in-the-loop confirmation tier
need each command's risk posture: is it destructive, a filing handoff, or a
(never-exposed) AEAT live-write? The accepted `mcp-protocol-hardening` H3 ruled
this "becomes declared data keyed by command key ... with a parity gate asserting
every mutating verb carries an explicit classification". The first implementation
shipped hand-listed leaf-NAME frozensets instead, matching on the command key's
trailing word - so a new mutating verb named `purge`/`wipe`/`finalize` fell
through every set, classified non-destructive, and auto-approved (the safety
finding of the 2026-07-08 MCP console review).

This module is that declared table. Every command in a LOCAL_STATE_MUTATING family
carries EXACTLY ONE row; a row with no flags is the explicit declaration "this
command mutates local state but is not destructive, not a handoff, and not a
live-write" - not a silent default. The no-silent-default parity gate
(`test_risk_table_parity.py`) fails the build when a mutating-family command has
no row, so a new verb cannot slip through unclassified. Read-only families derive
their classification from the manifest mutability and need no rows here;
`idempotent` is derived (read-only) and `open_world` is derived from the
`app.live.`/`pull` facts - only the three genuinely-judgment axes are declared.

The two rows the frozensets got wrong, corrected in the human-review pass:
`quickfile` runs the readiness->calculate->verify->file chain and so produces a
filing-grade artefact (handoff), and `config.profile.sandbox.prune` irreversibly
removes sandboxes (destructive).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

_STRICT_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")


class CommandRiskDeclaration(BaseModel):
    """The declared risk flags for one mutating command.

    All three default False: a bare declaration states "mutating but safe". The
    axes are the genuinely-judgment ones - `destructive` (irreversibly destroys or
    overwrites local state), `handoff` (produces a filing-grade artefact a human
    files outside the app), `live_write` (would write to AEAT; never exposed, but
    declared so the permanent block is data, not a leaf-string heuristic).
    """

    model_config = _STRICT_FROZEN

    destructive: bool = False
    handoff: bool = False
    live_write: bool = False


#: The declared risk table. One row per LOCAL_STATE_MUTATING-family command,
#: keyed by full command key. Read-only families are absent (derived).
COMMAND_RISK: dict[str, CommandRiskDeclaration] = {
    "app.live.borrador.100.latest": CommandRiskDeclaration(),
    "app.live.borrador.100.list": CommandRiskDeclaration(),
    "app.live.borrador.100.view": CommandRiskDeclaration(),
    "app.live.expedientes.latest": CommandRiskDeclaration(),
    "app.live.expedientes.list": CommandRiskDeclaration(),
    "app.live.expedientes.pull": CommandRiskDeclaration(),
    "app.live.expedientes.view": CommandRiskDeclaration(),
    "app.live.filed.list": CommandRiskDeclaration(),
    "app.live.filed.pull": CommandRiskDeclaration(),
    "app.live.filed.pull_sources": CommandRiskDeclaration(),
    "app.live.iva_wallet.history": CommandRiskDeclaration(),
    "app.live.iva_wallet.pull": CommandRiskDeclaration(),
    "app.live.iva_wallet.pull_evidence": CommandRiskDeclaration(),
    "app.live.iva_wallet.pull_history": CommandRiskDeclaration(),
    "app.live.justificante.list": CommandRiskDeclaration(),
    "app.live.justificante.pull": CommandRiskDeclaration(),
    "app.live.justificante.view": CommandRiskDeclaration(),
    "app.live.notifications.latest": CommandRiskDeclaration(),
    "app.live.notifications.list": CommandRiskDeclaration(),
    "app.live.notifications.pull": CommandRiskDeclaration(),
    "app.live.notifications.view": CommandRiskDeclaration(),
    "app.live.portals.list": CommandRiskDeclaration(),
    "app.live.portals.view": CommandRiskDeclaration(),
    "app.live.verify.latest": CommandRiskDeclaration(),
    "app.live.verify.list": CommandRiskDeclaration(),
    "app.live.verify.nif_iva": CommandRiskDeclaration(),
    "app.live.verify.tgvi": CommandRiskDeclaration(),
    "app.live.verify.view": CommandRiskDeclaration(),
    # Reconciliation irreversibly deletes a crashed export's leftover cleartext
    # staged file. That deletion is the whole point (those bytes must not sit on
    # disk), but it is still an unrecoverable local delete, so it is declared
    # destructive rather than classified on the recovery intent behind it.
    "app.maintenance.reconcile": CommandRiskDeclaration(destructive=True),
    "config.auth.apoderado.check": CommandRiskDeclaration(),
    "config.auth.apoderado.clear": CommandRiskDeclaration(destructive=True),
    "config.auth.apoderado.configure": CommandRiskDeclaration(),
    "config.auth.apoderado.scopes.list": CommandRiskDeclaration(),
    "config.auth.apoderado.status": CommandRiskDeclaration(),
    "config.auth.certificate.check": CommandRiskDeclaration(),
    "config.auth.certificate.list": CommandRiskDeclaration(),
    "config.auth.certificate.register": CommandRiskDeclaration(),
    "config.auth.certificate.remove": CommandRiskDeclaration(destructive=True),
    "config.auth.certificate.secret.remove": CommandRiskDeclaration(destructive=True),
    "config.auth.certificate.secret.set": CommandRiskDeclaration(),
    "config.auth.certificate.select": CommandRiskDeclaration(),
    "config.auth.logout": CommandRiskDeclaration(),
    "config.auth.reset": CommandRiskDeclaration(destructive=True),
    "config.auth.configure": CommandRiskDeclaration(),
    "config.auth.diagnostics.list": CommandRiskDeclaration(),
    "config.auth.diagnostics.report": CommandRiskDeclaration(),
    "config.auth.diagnostics.show": CommandRiskDeclaration(),
    "config.auth.login": CommandRiskDeclaration(),
    "config.auth.providers": CommandRiskDeclaration(),
    "config.auth.status": CommandRiskDeclaration(),
    "config.auth.test": CommandRiskDeclaration(),
    "config.bucket.history": CommandRiskDeclaration(),
    "config.collab.recipient.add": CommandRiskDeclaration(),
    "config.collab.recipient.list": CommandRiskDeclaration(),
    "config.collab.recipient.remove": CommandRiskDeclaration(destructive=True),
    "config.google.credential_source.set": CommandRiskDeclaration(),
    "config.google.credential_source.show": CommandRiskDeclaration(),
    "config.google.folder.get": CommandRiskDeclaration(),
    "config.google.folder.set": CommandRiskDeclaration(),
    "config.google.login": CommandRiskDeclaration(),
    "config.google.logout": CommandRiskDeclaration(destructive=True),
    "config.google.register": CommandRiskDeclaration(),
    "config.google.status": CommandRiskDeclaration(),
    "config.google.sync.calc.compute": CommandRiskDeclaration(),
    "config.google.sync.calc.export": CommandRiskDeclaration(handoff=True),
    "config.google.sync.calc.pull": CommandRiskDeclaration(),
    "config.google.sync.calc.verify": CommandRiskDeclaration(),
    "config.google.sync.probe": CommandRiskDeclaration(),
    "config.google.sync.push": CommandRiskDeclaration(),
    "config.profile.capabilities.set": CommandRiskDeclaration(),
    "config.profile.capabilities.show": CommandRiskDeclaration(),
    # Reads an operator-supplied censal artefact and, under `--apply`, enrolls
    # its facts through the single cotejo apply authority. Preview is the
    # default posture and the write updates profile fields in place, the same
    # shape as `capabilities.set` and `edit` - it destroys no record, produces
    # no filing-grade artefact, and never reaches AEAT.
    "config.profile.censo.file": CommandRiskDeclaration(),
    # The live sibling of `censo.file`: reads AEAT's censal consulta and, under
    # `--apply`, enrolls through the same single cotejo apply authority. It is
    # not a live-write - the read never submits a form, and the only write is
    # local. It writes a field only where the operator has declared nothing to
    # lose: an unset path, or one whose current value a previous censal read
    # wrote and the authority has since changed. A value the operator declared,
    # and a path they deliberately cleared, are reported for them to adjudicate
    # and never overwritten. So it destroys no record and produces no
    # filing-grade artefact.
    "config.profile.censo.pull": CommandRiskDeclaration(),
    "config.profile.create": CommandRiskDeclaration(),
    # Irreversibly destroys one named profile capsule and every encrypted
    # financial record inside it. Its default posture is a preflight that
    # writes nothing, but the risk axis describes what the verb CAN do under
    # `--yes`, so it must elicit human confirmation on the MCP surface and
    # never auto-approve. It produces no filing-grade artefact and never
    # reaches AEAT.
    "config.profile.delete": CommandRiskDeclaration(destructive=True),
    "config.profile.descendiente.add": CommandRiskDeclaration(),
    "config.profile.descendiente.list": CommandRiskDeclaration(),
    "config.profile.descendiente.remove": CommandRiskDeclaration(destructive=True),
    "config.profile.edit": CommandRiskDeclaration(),
    "config.profile.list": CommandRiskDeclaration(),
    "config.profile.preflight": CommandRiskDeclaration(),
    "config.profile.show": CommandRiskDeclaration(),
    "config.profile.status": CommandRiskDeclaration(),
    "config.profile.validate": CommandRiskDeclaration(),
    "config.repair": CommandRiskDeclaration(),
    "config.repair.connectivity": CommandRiskDeclaration(),
    "config.repair.integrity.objects": CommandRiskDeclaration(),
    "config.repair.integrity.registry": CommandRiskDeclaration(),
    "config.repair.logs": CommandRiskDeclaration(),
    "config.repair.profile": CommandRiskDeclaration(),
    "config.repair.quarantine": CommandRiskDeclaration(),
    "config.repair.reset_progress": CommandRiskDeclaration(),
    # The reset lifecycle inherits the pre-split ``config.reset`` destructive
    # declaration: start and resume irreversibly wipe local state, so they must
    # elicit human confirmation on the MCP surface, never auto-approve. ``status``
    # is a read of the in-progress reset.
    "config.reset.resume": CommandRiskDeclaration(destructive=True),
    "config.reset.start": CommandRiskDeclaration(destructive=True),
    "config.reset.status": CommandRiskDeclaration(),
    # Storage lifecycle: ``list``/``show``/``check`` only read the tree, and
    # ``init`` creates missing directories while preserving every existing one.
    # ``reclaim`` irreversibly deletes a category's contents, which is the whole
    # point of the verb and exactly why it is declared destructive: its own
    # lifecycle guard already refuses the categories that must never be deleted,
    # but the operator confirmation this flag drives is a separate protection
    # covering the categories where deleting IS permitted.
    "config.storage.check": CommandRiskDeclaration(),
    "config.storage.init": CommandRiskDeclaration(),
    "config.storage.list": CommandRiskDeclaration(),
    "config.storage.reclaim": CommandRiskDeclaration(destructive=True),
    "config.storage.show": CommandRiskDeclaration(),
    "config.login": CommandRiskDeclaration(),
    "config.logout": CommandRiskDeclaration(destructive=True),
    # Diagnostics reads run-health, latency, error, and LLM-usage telemetry and
    # flush/inspect the local telemetry store: a mutating family, none destructive
    # (a flush prunes bounded local telemetry, not taxpayer state) and no handoff
    # or live-write - one bare row each, per the no-silent-default contract.
    "diagnostics.errors": CommandRiskDeclaration(),
    "diagnostics.latency": CommandRiskDeclaration(),
    "diagnostics.llm_usage": CommandRiskDeclaration(),
    "diagnostics.run_health": CommandRiskDeclaration(),
    "diagnostics.runs": CommandRiskDeclaration(),
    "diagnostics.telemetry.flush": CommandRiskDeclaration(),
    "diagnostics.telemetry.status": CommandRiskDeclaration(),
    "ledger.add": CommandRiskDeclaration(),
    "ledger.allocate": CommandRiskDeclaration(),
    "ledger.archive": CommandRiskDeclaration(),
    "ledger.attach": CommandRiskDeclaration(),
    "ledger.bienes_inversion.declare": CommandRiskDeclaration(),
    "ledger.bienes_inversion.list": CommandRiskDeclaration(),
    "ledger.categories": CommandRiskDeclaration(),
    "ledger.check": CommandRiskDeclaration(),
    "ledger.classify": CommandRiskDeclaration(),
    "ledger.doclink": CommandRiskDeclaration(),
    "ledger.evidence.add": CommandRiskDeclaration(),
    "ledger.evidence.confirm": CommandRiskDeclaration(),
    "ledger.evidence.extract": CommandRiskDeclaration(),
    "ledger.evidence.list": CommandRiskDeclaration(),
    "ledger.evidence.remove": CommandRiskDeclaration(destructive=True),
    "ledger.evidence.update": CommandRiskDeclaration(),
    "ledger.evidence.view": CommandRiskDeclaration(),
    "ledger.exclude": CommandRiskDeclaration(),
    "ledger.export": CommandRiskDeclaration(handoff=True),
    "ledger.history": CommandRiskDeclaration(),
    "ledger.import": CommandRiskDeclaration(),
    "ledger.inventory.create": CommandRiskDeclaration(),
    "ledger.inventory.list": CommandRiskDeclaration(),
    "ledger.inventory.movement.add": CommandRiskDeclaration(),
    "ledger.inventory.valuation.preview": CommandRiskDeclaration(),
    "ledger.invoice.add": CommandRiskDeclaration(),
    "ledger.invoice.import": CommandRiskDeclaration(),
    "ledger.invoice.list": CommandRiskDeclaration(),
    "ledger.invoice.remove": CommandRiskDeclaration(destructive=True),
    "ledger.invoice.update": CommandRiskDeclaration(),
    "ledger.invoice.view": CommandRiskDeclaration(),
    "ledger.invoice.wizard": CommandRiskDeclaration(),
    "ledger.link": CommandRiskDeclaration(),
    "ledger.list": CommandRiskDeclaration(),
    "ledger.llm_diagnostics": CommandRiskDeclaration(),
    "ledger.merge": CommandRiskDeclaration(destructive=True),
    "ledger.participation": CommandRiskDeclaration(),
    "ledger.participation.rebuild": CommandRiskDeclaration(),
    "ledger.preflight": CommandRiskDeclaration(),
    "ledger.prorrata.declare_sector": CommandRiskDeclaration(),
    "ledger.prorrata.elect_especial": CommandRiskDeclaration(),
    "ledger.prorrata.elect_general": CommandRiskDeclaration(),
    "ledger.prorrata.list": CommandRiskDeclaration(),
    "ledger.prorrata.revoke_especial": CommandRiskDeclaration(),
    "ledger.pull_folder": CommandRiskDeclaration(),
    "ledger.ratios.eligible": CommandRiskDeclaration(),
    "ledger.ratios.list": CommandRiskDeclaration(),
    "ledger.ratios.set": CommandRiskDeclaration(),
    "ledger.ratios.unset": CommandRiskDeclaration(),
    "ledger.ratios.validate": CommandRiskDeclaration(),
    "ledger.remove": CommandRiskDeclaration(destructive=True),
    "ledger.reset": CommandRiskDeclaration(destructive=True),
    "ledger.restore": CommandRiskDeclaration(),
    "ledger.review": CommandRiskDeclaration(),
    "ledger.rule.add": CommandRiskDeclaration(),
    "ledger.rule.apply": CommandRiskDeclaration(),
    "ledger.rule.list": CommandRiskDeclaration(),
    "ledger.split": CommandRiskDeclaration(),
    "ledger.stash": CommandRiskDeclaration(destructive=True),
    "ledger.status": CommandRiskDeclaration(),
    "ledger.track": CommandRiskDeclaration(),
    "ledger.update": CommandRiskDeclaration(),
    "ledger.view": CommandRiskDeclaration(),
    "modelo.aggregate": CommandRiskDeclaration(),
    "modelo.audit.check": CommandRiskDeclaration(),
    "modelo.audit.export": CommandRiskDeclaration(handoff=True),
    "modelo.audit.show": CommandRiskDeclaration(),
    "modelo.bindings.list": CommandRiskDeclaration(),
    "modelo.bindings.resolve": CommandRiskDeclaration(),
    "modelo.casilla": CommandRiskDeclaration(),
    "modelo.casillas": CommandRiskDeclaration(),
    "modelo.compare": CommandRiskDeclaration(),
    "modelo.describe": CommandRiskDeclaration(),
    "modelo.export": CommandRiskDeclaration(handoff=True),
    "modelo.filing_record.import": CommandRiskDeclaration(),
    "modelo.filing_record.list": CommandRiskDeclaration(),
    "modelo.filing_record.observe_local": CommandRiskDeclaration(),
    "modelo.filing_record.view": CommandRiskDeclaration(),
    "modelo.formulas": CommandRiskDeclaration(),
    "modelo.history": CommandRiskDeclaration(),
    "modelo.iva_wallet.balance": CommandRiskDeclaration(),
    "modelo.iva_wallet.correct": CommandRiskDeclaration(),
    "modelo.iva_wallet.override": CommandRiskDeclaration(),
    "modelo.iva_wallet.seed": CommandRiskDeclaration(),
    "modelo.list": CommandRiskDeclaration(),
    "modelo.m036.alta": CommandRiskDeclaration(),
    "modelo.m036.baja": CommandRiskDeclaration(),
    "modelo.m036.list": CommandRiskDeclaration(),
    "modelo.m036.modificacion": CommandRiskDeclaration(),
    "modelo.m036.view": CommandRiskDeclaration(),
    "modelo.m145.create": CommandRiskDeclaration(),
    "modelo.m145.export": CommandRiskDeclaration(handoff=True),
    "modelo.m145.mark_delivered_to_payer": CommandRiskDeclaration(),
    "modelo.m145.mark_locally_completed": CommandRiskDeclaration(),
    "modelo.m145.validate": CommandRiskDeclaration(),
    "modelo.project": CommandRiskDeclaration(),
    "modelo.readiness": CommandRiskDeclaration(),
    "modelo.reconcile.file": CommandRiskDeclaration(handoff=True),
    "modelo.reconcile.history": CommandRiskDeclaration(),
    "modelo.reconcile.pull": CommandRiskDeclaration(),
    "modelo.requires": CommandRiskDeclaration(),
    "modelo.review_package.build": CommandRiskDeclaration(),
    "modelo.review_package.counter_sign": CommandRiskDeclaration(),
    "modelo.review_package.decrypt": CommandRiskDeclaration(),
    "modelo.review_package.encrypt_feedback": CommandRiskDeclaration(),
    "modelo.review_package.encrypt_for_recipient": CommandRiskDeclaration(),
    "modelo.review_package.import_feedback": CommandRiskDeclaration(),
    "modelo.review_package.sign": CommandRiskDeclaration(),
    "modelo.review_package.verify": CommandRiskDeclaration(),
    "modelo.review_package.verify_receipt": CommandRiskDeclaration(),
    "modelo.review_package.verify_signature": CommandRiskDeclaration(),
    "modelo.support_matrix": CommandRiskDeclaration(),
    "modelo.verification_report.list": CommandRiskDeclaration(),
    "modelo.verification_report.view": CommandRiskDeclaration(),
    "modelo.work.amend": CommandRiskDeclaration(),
    "modelo.work.amend_wizard": CommandRiskDeclaration(),
    "modelo.work.calculate": CommandRiskDeclaration(),
    "modelo.work.compare_taxation": CommandRiskDeclaration(),
    "modelo.work.create": CommandRiskDeclaration(),
    "modelo.work.dependencies": CommandRiskDeclaration(),
    "modelo.work.discard": CommandRiskDeclaration(destructive=True),
    "modelo.work.file": CommandRiskDeclaration(handoff=True),
    "modelo.work.history": CommandRiskDeclaration(),
    "modelo.work.list": CommandRiskDeclaration(),
    "modelo.work.observations": CommandRiskDeclaration(),
    "modelo.work.preview_maritime_exemption": CommandRiskDeclaration(),
    "modelo.work.rename": CommandRiskDeclaration(),
    "modelo.work.resume": CommandRiskDeclaration(),
    "modelo.work.revision": CommandRiskDeclaration(),
    "modelo.work.revisions": CommandRiskDeclaration(),
    "modelo.work.runs": CommandRiskDeclaration(),
    "modelo.work.status": CommandRiskDeclaration(),
    "modelo.work.verify": CommandRiskDeclaration(),
    "modelo.work.wizard": CommandRiskDeclaration(),
    "quickfile": CommandRiskDeclaration(handoff=True),
}


def declared_risk(command_key: str) -> CommandRiskDeclaration | None:
    """Return the declared risk row for `command_key`, or None when absent.

    Absent means the command's family is read-only (classification is derived) OR
    - the case the parity gate exists to catch - a mutating command was added
    without a declaration. `classify_command` treats an absent row for a mutating
    command as all-false at runtime; the gate makes that state a build failure.
    """
    return COMMAND_RISK.get(command_key)
