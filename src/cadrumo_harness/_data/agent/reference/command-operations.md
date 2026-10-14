# Commands and the tools that do their work

Generated from the record the command line publishes of its own commands, the
registered operations each one can submit, the runtime requests each one
sends, and what serves the work a command does in its own process. Do not edit
it by hand.

A workflow skill names commands. Through MCP you do a command's work with the
tools its row names, so look the command up here as the skill spells it,
without its options and arguments.

- The second column lists every operation any mode of the command can submit,
  and you run one with `execute`. A command with one operation runs that
  operation. A command with several runs the one whose contract fits the step,
  and often a read first: the operation that resolves the identifier the write
  then takes.
- The third column lists every other route to the command's work: a tool, and
  after it the operation or query the tool is given. `execute` with an
  operation there means the command does that work in its own process and the
  operation does the same work for you. `authority` takes the name shown as its
  `query`. A tool shown alone takes no such name.
- `the person's act` in the third column means the command's work is the
  person's own: signing in or out, locking, sessions, keys, passwords and other
  secrets, recovery, and work outside this profile such as the profile list,
  storage, repair and resetting every profile. You cannot do it. Ask the person
  to do it in Cadrumo. An operation listed beside it that needs a secret, or
  that administers keys, is refused to you as the person's act too.
- `none` in both columns means the command has no work to do for you: it
  prints help, or it starts the terminal interface.
- A command's options are not the operation's fields. Read the operation's
  input schema with `describe` and fill it from the same facts the options
  carry.

## Commands

| Command | Operations it can submit | Other routes to its work |
| --- | --- | --- |
| `aeat` | none | `execute` `overview.status` |
| `aeat app` | none | none |
| `aeat app agent serve` | none | none |
| `aeat app diagnostics` | none | none |
| `aeat app diagnostics errors` | `diagnostics.read` | none |
| `aeat app diagnostics latency` | `diagnostics.read` | none |
| `aeat app diagnostics llm-usage` | `diagnostics.read` | none |
| `aeat app diagnostics run-health` | `diagnostics.read` | none |
| `aeat app diagnostics runs` | `diagnostics.read` | none |
| `aeat app ledger account add` | `ledger.own_account` | none |
| `aeat app ledger account close` | `ledger.own_account` | none |
| `aeat app ledger account designate` | `ledger.own_account` | none |
| `aeat app ledger account list` | `ledger.own_account` | none |
| `aeat app ledger account remove` | `ledger.own_account` | none |
| `aeat app ledger account show` | `ledger.own_account` | none |
| `aeat app ledger account undesignate` | `ledger.own_account` | none |
| `aeat app ledger account update` | `ledger.own_account` | none |
| `aeat app ledger actividad-asset claim` | `ledger.actividad-asset.claim` | none |
| `aeat app ledger actividad-asset correct` | `ledger.actividad-asset.correct` | none |
| `aeat app ledger actividad-asset create` | `ledger.actividad-asset.create` | none |
| `aeat app ledger actividad-asset filing-handoff` | `ledger.actividad-asset.filing-handoff` | none |
| `aeat app ledger actividad-asset forecast` | `ledger.actividad-asset.forecast` | none |
| `aeat app ledger actividad-asset inspect` | `ledger.actividad-asset.inspect` | none |
| `aeat app ledger add` | `ledger.add` | none |
| `aeat app ledger allocate` | `ledger.allocate` | none |
| `aeat app ledger archive` | `ledger.archive` | none |
| `aeat app ledger attach` | `ledger.attach` | none |
| `aeat app ledger bienes-inversion declare` | `ledger.bienes_inversion.declare` | none |
| `aeat app ledger bienes-inversion list` | `ledger.bienes_inversion.list` | none |
| `aeat app ledger categories` | none | `authority` `categories` |
| `aeat app ledger check` | `ledger.check` | none |
| `aeat app ledger classify` | `ledger.classify.bulk`, `ledger.classify.iva-derive`, `ledger.classify.review`, `ledger.classify.single` | none |
| `aeat app ledger counterparty confirm` | `ledger.counterparty` | none |
| `aeat app ledger counterparty view` | `ledger.counterparty` | none |
| `aeat app ledger counterparty withdraw` | `ledger.counterparty` | none |
| `aeat app ledger detach` | `ledger.detach` | none |
| `aeat app ledger evidence add` | `ledger.evidence.add` | none |
| `aeat app ledger evidence attachment-queue` | `ledger.evidence.attachment_queue` | none |
| `aeat app ledger evidence attachment-view` | `ledger.evidence.attachment_view` | none |
| `aeat app ledger evidence batch` | `ledger.evidence.batch` | none |
| `aeat app ledger evidence confirm` | `ledger.evidence.confirm` | none |
| `aeat app ledger evidence consent list` | `ledger.evidence.consent.list` | none |
| `aeat app ledger evidence extract` | `ledger.evidence.extract` | none |
| `aeat app ledger evidence list` | `ledger.evidence.list` | none |
| `aeat app ledger evidence remove` | `ledger.evidence.remove` | none |
| `aeat app ledger evidence review list` | `ledger.evidence.review.list` | none |
| `aeat app ledger evidence review view` | `ledger.evidence.review.view` | none |
| `aeat app ledger evidence update` | `ledger.evidence.update` | none |
| `aeat app ledger evidence view` | `ledger.evidence.view` | none |
| `aeat app ledger exclude` | `ledger.exclude` | none |
| `aeat app ledger export` | `ledger.export` | none |
| `aeat app ledger history` | `ledger.history` | none |
| `aeat app ledger import` | `ledger.import` | none |
| `aeat app ledger inventory closing-authority-record` | `ledger.inventory.closing-authority.record` | none |
| `aeat app ledger inventory create` | `ledger.inventory.create` | none |
| `aeat app ledger inventory list` | `ledger.inventory.list` | none |
| `aeat app ledger inventory movement add` | `ledger.inventory.movement.add` | none |
| `aeat app ledger inventory valuation preview` | `ledger.inventory.valuation.preview` | none |
| `aeat app ledger invoice add` | `ledger.invoice.add` | none |
| `aeat app ledger invoice import` | `ledger.invoice.import` | none |
| `aeat app ledger invoice list` | `ledger.invoice.list` | none |
| `aeat app ledger invoice remove` | `ledger.invoice.remove` | none |
| `aeat app ledger invoice update` | `ledger.invoice.update` | none |
| `aeat app ledger invoice view` | `ledger.invoice.view` | none |
| `aeat app ledger invoice wizard` | `ledger.invoice.wizard` | none |
| `aeat app ledger link` | `ledger.link` | none |
| `aeat app ledger list` | `ledger.list` | none |
| `aeat app ledger llm-diagnostics` | `ledger.llm-diagnostics` | none |
| `aeat app ledger merge` | `ledger.merge` | none |
| `aeat app ledger participation` | `ledger.participation`, `ledger.participation.rebuild` | none |
| `aeat app ledger participation rebuild` | `ledger.participation.rebuild` | none |
| `aeat app ledger preflight` | `ledger.preflight` | none |
| `aeat app ledger prorrata declare-sector` | `ledger.prorrata.declare_sector` | none |
| `aeat app ledger prorrata elect-especial` | `ledger.prorrata.elect_especial` | none |
| `aeat app ledger prorrata elect-general` | `ledger.prorrata.elect_general` | none |
| `aeat app ledger prorrata list` | `ledger.prorrata.list` | none |
| `aeat app ledger prorrata revoke-especial` | `ledger.prorrata.revoke_especial` | none |
| `aeat app ledger prorrata seed` | `ledger.prorrata.seed` | none |
| `aeat app ledger prorrata seed-sector` | `ledger.prorrata.seed_sector` | none |
| `aeat app ledger prorrata settle-sector` | `ledger.prorrata.settle_sector` | none |
| `aeat app ledger ratios eligible` | `ledger.ratios.eligible` | none |
| `aeat app ledger ratios list` | `ledger.ratios.list` | none |
| `aeat app ledger ratios set` | `ledger.ratios.set` | none |
| `aeat app ledger ratios unset` | `ledger.ratios.unset` | none |
| `aeat app ledger ratios validate` | `ledger.ratios.validate` | none |
| `aeat app ledger remove` | `ledger.remove` | none |
| `aeat app ledger reset` | `ledger.reset` | none |
| `aeat app ledger restore` | `ledger.restore` | none |
| `aeat app ledger review` | `ledger.review` | none |
| `aeat app ledger rule add` | `ledger.rule.add` | none |
| `aeat app ledger rule apply` | `ledger.rule.apply` | none |
| `aeat app ledger rule list` | `ledger.rule.list` | none |
| `aeat app ledger split` | `ledger.split.manual`, `ledger.split.review` | none |
| `aeat app ledger stash` | `ledger.stash` | none |
| `aeat app ledger status` | `ledger.status` | none |
| `aeat app ledger track` | `ledger.track` | none |
| `aeat app ledger update` | `ledger.update` | none |
| `aeat app ledger view` | `ledger.view` | none |
| `aeat app live borrador 100 import` | `live.borrador.100.import` | none |
| `aeat app live borrador 100 latest` | `live.borrador.100.read` | none |
| `aeat app live borrador 100 list` | `live.borrador.100.read` | none |
| `aeat app live borrador 100 view` | `live.borrador.100.read` | none |
| `aeat app live expedientes latest` | `live.expedientes.latest` | none |
| `aeat app live expedientes list` | `live.expedientes.list` | none |
| `aeat app live expedientes pull` | `live.expedientes.capture.bulk`, `live.expedientes.capture.single` | none |
| `aeat app live expedientes view` | `live.expedientes.show` | none |
| `aeat app live filed discover` | `live.filed-discover` | none |
| `aeat app live filed list` | `live.filed-list` | none |
| `aeat app live filed pull` | `live.filed-capture.bulk`, `live.filed-capture.single` | none |
| `aeat app live filed pull-all` | `live.filed-history.pull` | none |
| `aeat app live filed pull-sources` | `live.filed-capture.source` | none |
| `aeat app live iva-wallet history` | `live.iva-wallet.history` | none |
| `aeat app live iva-wallet pull` | `live.iva-wallet.capture` | none |
| `aeat app live iva-wallet pull-evidence` | `live.iva-wallet.evidence-capture` | none |
| `aeat app live iva-wallet pull-history` | `live.iva-wallet.history-capture` | none |
| `aeat app live justificante list` | `live.justificante.list` | none |
| `aeat app live justificante pull` | `live.justificante.capture` | none |
| `aeat app live justificante view` | `live.justificante.show` | none |
| `aeat app live notifications document history` | `live.notifications.document.history` | none |
| `aeat app live notifications document pull` | `live.notifications.document.capture` | none |
| `aeat app live notifications document view` | `live.notifications.document.view` | none |
| `aeat app live notifications latest` | `live.notifications.latest` | none |
| `aeat app live notifications list` | `live.notifications.list` | none |
| `aeat app live notifications pull` | `live.notifications.capture` | none |
| `aeat app live notifications view` | `live.notifications.show` | none |
| `aeat app live portals list` | none | `authority` `portals` |
| `aeat app live portals view` | none | `authority` `portal` |
| `aeat app live verify latest` | `live.verify.latest` | none |
| `aeat app live verify list` | `live.verify.list` | none |
| `aeat app live verify nif-iva` | `live.verify.nif-iva` | none |
| `aeat app live verify tgvi` | `live.verify.tgvi` | none |
| `aeat app live verify view` | `live.verify.view` | none |
| `aeat app modelo aggregate` | `modelo.aggregate`, `modelo.aggregate.capture_received_invoice_retencion` | none |
| `aeat app modelo audit check` | `modelo.audit.read` | none |
| `aeat app modelo audit export` | `modelo.audit.export` | none |
| `aeat app modelo audit view` | `modelo.audit.read` | none |
| `aeat app modelo bindings list` | `modelo.bindings.list` | none |
| `aeat app modelo bindings resolve` | `modelo.bindings.list`, `modelo.bindings.resolve` | none |
| `aeat app modelo casilla` | none | `authority` `casilla` |
| `aeat app modelo casillas` | none | `authority` `casillas` |
| `aeat app modelo compare` | `modelo.compare` | none |
| `aeat app modelo describe` | none | `authority` `describe` |
| `aeat app modelo export` | `modelo.export`, `modelo.work.revision` | none |
| `aeat app modelo filing-record export` | `export.calculation-review-xlsx`, `modelo.filing_record.view` | none |
| `aeat app modelo filing-record import` | `modelo.filing_record.import` | none |
| `aeat app modelo filing-record list` | `modelo.filing_record.list` | none |
| `aeat app modelo filing-record observe-local` | `modelo.observation.local` | none |
| `aeat app modelo filing-record view` | `modelo.filing_record.view` | none |
| `aeat app modelo formulas` | none | `authority` `formulas` |
| `aeat app modelo history` | `modelo.history` | none |
| `aeat app modelo iva-wallet balance` | `modelo.iva-wallet.balance` | none |
| `aeat app modelo iva-wallet correct` | `modelo.iva-wallet.correct` | none |
| `aeat app modelo iva-wallet override` | `modelo.iva-wallet.override` | none |
| `aeat app modelo iva-wallet seed` | `modelo.iva-wallet.seed` | none |
| `aeat app modelo list` | none | `authority` `modelos` |
| `aeat app modelo m036 alta` | `modelo.036.record` | none |
| `aeat app modelo m036 baja` | `modelo.036.record` | none |
| `aeat app modelo m036 list` | `modelo.036.read` | none |
| `aeat app modelo m036 modificacion` | `modelo.036.record` | none |
| `aeat app modelo m036 view` | `modelo.036.read` | none |
| `aeat app modelo m145 create` | `modelo.m145.create` | none |
| `aeat app modelo m145 export` | `modelo.m145.export` | none |
| `aeat app modelo m145 mark-delivered-to-payer` | `modelo.m145.mark_delivered_to_payer` | none |
| `aeat app modelo m145 mark-locally-completed` | `modelo.m145.mark_locally_completed` | none |
| `aeat app modelo m145 validate` | `modelo.m145.validate` | none |
| `aeat app modelo m360 declare` | `modelo.m360_solicitud` | none |
| `aeat app modelo m360 list` | `modelo.m360_solicitud` | none |
| `aeat app modelo m360 remove` | `modelo.m360_solicitud` | none |
| `aeat app modelo project` | `modelo.project` | none |
| `aeat app modelo readiness` | `modelo.readiness` | none |
| `aeat app modelo reconcile export` | `modelo.reconcile.export-xlsx` | none |
| `aeat app modelo reconcile import` | `modelo.reconcile.import` | none |
| `aeat app modelo reconcile list` | `modelo.reconcile.list` | none |
| `aeat app modelo reconcile pull` | `live.filed-capture.single`, `live.justificante.capture`, `modelo.reconcile.pull`, `modelo.work.metadata` | none |
| `aeat app modelo requires` | `modelo.requires` | none |
| `aeat app modelo review-package build` | `modelo.review_package.build`, `modelo.work.revision` | none |
| `aeat app modelo review-package counter-sign` | `modelo.review_package.counter_sign` | none |
| `aeat app modelo review-package decrypt` | `modelo.review_package.decrypt` | none |
| `aeat app modelo review-package encrypt-feedback` | `modelo.review_package.encrypt_feedback` | none |
| `aeat app modelo review-package encrypt-for-recipient` | `modelo.review_package.encrypt_for_recipient` | none |
| `aeat app modelo review-package import-feedback` | `modelo.review_package.import_feedback` | none |
| `aeat app modelo review-package sign` | `modelo.review_package.sign` | none |
| `aeat app modelo review-package verify` | none | the person's act |
| `aeat app modelo review-package verify-receipt` | none | the person's act |
| `aeat app modelo review-package verify-signature` | none | the person's act |
| `aeat app modelo spreadsheet export` | `modelo.spreadsheet.export` | none |
| `aeat app modelo spreadsheet publish` | `export.google-review` | none |
| `aeat app modelo spreadsheet push` | `export.google-sheets` | none |
| `aeat app modelo spreadsheet review` | `export.calculation-review-xlsx` | none |
| `aeat app modelo support-matrix` | none | `authority` `support` |
| `aeat app modelo verification-report list` | `modelo.verification_report.list` | none |
| `aeat app modelo verification-report view` | `modelo.verification_report.view` | none |
| `aeat app modelo work amend` | `modelo.work.amend`, `modelo.work.filing_record` | none |
| `aeat app modelo work amend-wizard` | `modelo.work.amend`, `modelo.work.amendment_context`, `modelo.work.metadata` | none |
| `aeat app modelo work attest-m303-exonerado-390` | `modelo.work.m303_attestation` | none |
| `aeat app modelo work calculate` | `modelo.work.calculate`, `modelo.work.metadata` | none |
| `aeat app modelo work compare-taxation` | `modelo.work.compare_taxation`, `modelo.work.metadata` | none |
| `aeat app modelo work create` | `modelo.work.create` | none |
| `aeat app modelo work dependencies` | `modelo.work.dependencies` | none |
| `aeat app modelo work discard` | `modelo.work.discard`, `modelo.work.metadata` | none |
| `aeat app modelo work file` | `modelo.work.file`, `modelo.work.revision` | none |
| `aeat app modelo work history` | `modelo.work.history`, `modelo.work.metadata` | none |
| `aeat app modelo work list` | `modelo.work.list` | none |
| `aeat app modelo work observations` | `modelo.work.revision`, `modelo.work.revision_snapshot` | none |
| `aeat app modelo work preview-maritime-exemption` | `modelo.work.preview_maritime_exemption` | none |
| `aeat app modelo work rename` | `modelo.work.metadata`, `modelo.work.rename` | none |
| `aeat app modelo work report` | `modelo.export`, `modelo.work.revision` | none |
| `aeat app modelo work report-verify` | `modelo.work.report_verify` | the person's act |
| `aeat app modelo work resume` | `workflow.resume.context` | none |
| `aeat app modelo work review` | `modelo.work.metadata`, `modelo.work.review` | none |
| `aeat app modelo work revision` | `modelo.work.revision`, `modelo.work.revision_snapshot` | none |
| `aeat app modelo work revisions` | `modelo.work.metadata`, `modelo.work.revisions` | none |
| `aeat app modelo work run` | `workflow.run.read` | none |
| `aeat app modelo work run-details` | `workflow.run.read` | none |
| `aeat app modelo work runs` | `workflow.run.list` | none |
| `aeat app modelo work select` | `modelo.work.list` | none |
| `aeat app modelo work status` | `modelo.work.metadata` | none |
| `aeat app modelo work verify` | `modelo.work.revision`, `modelo.work.verify` | none |
| `aeat app modelo work wizard` | `modelo.work.metadata`, `modelo.work.wizard_attempt`, `modelo.work.wizard_context` | none |
| `aeat app overview agenda` | `overview.agenda` | none |
| `aeat app overview backlog` | `overview.backlog` | none |
| `aeat app overview calendar` | `overview.calendar` | none |
| `aeat app overview explain` | `overview.explain` | none |
| `aeat app overview pipeline` | `overview.pipeline` | none |
| `aeat app overview prepare` | `overview.prepare` | none |
| `aeat app overview status` | `overview.status` | none |
| `aeat app quickfile` | `modelo.quickfile` | none |
| `aeat app review queue` | `app.review.queue` | none |
| `aeat app review view` | `app.review.view` | none |
| `aeat app tui` | none | none |
| `aeat config` | none | none |
| `aeat config auth apoderado check` | `auth.apoderado.check` | none |
| `aeat config auth apoderado clear` | `auth.apoderado.clear` | none |
| `aeat config auth apoderado configure` | `auth.apoderado.configure` | the person's act |
| `aeat config auth apoderado scopes list` | none | `authority` `apoderado_scopes` |
| `aeat config auth apoderado status` | `auth.apoderado.status` | none |
| `aeat config auth certificate check` | `auth.certificate.source.check` | none |
| `aeat config auth certificate list` | `auth.certificate.source.list` | none |
| `aeat config auth certificate register` | `auth.certificate.source.register` | none |
| `aeat config auth certificate remove` | `auth.certificate.source.remove` | none |
| `aeat config auth certificate secret remove` | `auth.certificate.secret.remove` | none |
| `aeat config auth certificate secret set` | `auth.certificate.secret.set` | the person's act |
| `aeat config auth certificate select` | `auth.certificate.source.select` | none |
| `aeat config auth configure` | `auth.provider.configure` | none |
| `aeat config auth diagnostics list` | `auth.local-read` | none |
| `aeat config auth diagnostics report` | `auth.diagnostics.phone-state-report` | none |
| `aeat config auth diagnostics view` | `auth.local-read` | none |
| `aeat config auth login` | `auth.session.acquire` | none |
| `aeat config auth logout` | `auth.session.logout` | none |
| `aeat config auth providers` | none | `authority` `auth_providers` |
| `aeat config auth reset` | `auth.session.reset` | none |
| `aeat config auth status` | `auth.local-read` | none |
| `aeat config auth test` | `auth.local-read` | none |
| `aeat config check` | `diagnostics.workstation.check` | none |
| `aeat config collab recipient add` | `config.collab.recipient.add` | none |
| `aeat config collab recipient list` | `config.collab.recipient.list` | none |
| `aeat config collab recipient remove` | `config.collab.recipient.remove` | none |
| `aeat config google folder organize` | `config.google.folder.organize` | none |
| `aeat config google folder view` | `config.google.folder.view` | none |
| `aeat config google login` | `config.google.login` | none |
| `aeat config google logout` | `config.google.logout` | none |
| `aeat config google probe` | `config.google.probe` | none |
| `aeat config google status` | `config.google.status` | none |
| `aeat config login` | none | the person's act |
| `aeat config logout` | none | the person's act |
| `aeat config passphrase change` | `auth.profile.passphrase-rotate` | the person's act |
| `aeat config passphrase reset` | none | the person's act |
| `aeat config profile add-row` | `user-profile.repeatable-row-mutation`, `user-profile.view` | none |
| `aeat config profile archive export` | `profile.archive.export` | none |
| `aeat config profile archive import` | none | the person's act |
| `aeat config profile archive inspect` | none | the person's act |
| `aeat config profile archive push` | `profile.archive.push` | none |
| `aeat config profile archive reconcile` | `profile.archive.reconcile` | none |
| `aeat config profile automation approve` | `user-profile.automation-approve`, `user-profile.automation-inventory` | the person's act |
| `aeat config profile automation change` | none | the person's act |
| `aeat config profile automation create` | none | the person's act |
| `aeat config profile automation decline` | `user-profile.automation-decline`, `user-profile.automation-inventory` | the person's act |
| `aeat config profile automation deny` | none | the person's act |
| `aeat config profile automation disclosures` | `user-profile.automation-inventory` | the person's act |
| `aeat config profile automation inspect` | `user-profile.automation-inventory` | the person's act |
| `aeat config profile automation list` | `user-profile.automation-inventory` | the person's act |
| `aeat config profile capabilities set` | `user-profile.field-mutation`, `user-profile.view` | none |
| `aeat config profile capabilities view` | `user-profile.view` | none |
| `aeat config profile censo import` | `user-profile.censo-file-import` | `execute` `user-profile.censo-certificate-import` |
| `aeat config profile censo pull` | `user-profile.censo-prepare`, `user-profile.censo-preview`, `user-profile.censo-review` | none |
| `aeat config profile censo show` | `user-profile.censo-prepare` | none |
| `aeat config profile complete-setup` | `user-profile.complete-setup`, `user-profile.view` | none |
| `aeat config profile create` | `user-profile.patch`, `user-profile.view` | none |
| `aeat config profile delete` | none | the person's act |
| `aeat config profile descendiente` | `user-profile.descendants`, `user-profile.view` | none |
| `aeat config profile descendiente add` | `user-profile.descendants`, `user-profile.view` | none |
| `aeat config profile descendiente list` | `user-profile.view` | none |
| `aeat config profile descendiente remove` | `user-profile.descendants`, `user-profile.view` | none |
| `aeat config profile disclosures` | none | `status` |
| `aeat config profile edit` | `user-profile.patch`, `user-profile.view` | none |
| `aeat config profile edit-row` | `user-profile.repeatable-row-update`, `user-profile.view` | none |
| `aeat config profile history` | `profile.history` | none |
| `aeat config profile list` | none | the person's act |
| `aeat config profile lock` | none | the person's act |
| `aeat config profile plantilla-media list` | `user-profile.view` | none |
| `aeat config profile plantilla-media remove` | `user-profile.plantilla-media`, `user-profile.view` | none |
| `aeat config profile plantilla-media set` | `user-profile.plantilla-media`, `user-profile.view` | none |
| `aeat config profile recovery disable` | none | the person's act |
| `aeat config profile recovery enable` | none | the person's act |
| `aeat config profile recovery status` | `user-profile.recovery.status` | none |
| `aeat config profile remove-row` | `user-profile.repeatable-row-remove`, `user-profile.view` | none |
| `aeat config profile resume` | none | the person's act |
| `aeat config profile sessions` | none | the person's act |
| `aeat config profile status` | `user-profile.view` | none |
| `aeat config profile validate` | `user-profile.view` | none |
| `aeat config profile view` | `user-profile.view` | none |
| `aeat config provider remove` | `provider-settings.remove` | the person's act |
| `aeat config provider reset` | `provider-settings.reset` | the person's act |
| `aeat config provider set` | `provider-settings.set` | the person's act |
| `aeat config provider status` | `provider-settings.status` | none |
| `aeat config provision browser` | none | `execute` `browser-runtime.provision` |
| `aeat config provision install` | none | `execute` `local-reader.provision` |
| `aeat config provision load` | none | `execute` `local-reader.provision` |
| `aeat config provision probe` | none | `execute` `local-reader.status` |
| `aeat config provision pull` | none | `execute` `local-reader.provision` |
| `aeat config provision remove` | none | `execute` `local-reader.provision` |
| `aeat config provision report` | none | `execute` `local-reader.report` |
| `aeat config provision setup` | none | `execute` `local-reader.provision` |
| `aeat config provision start` | none | `execute` `local-reader.provision` |
| `aeat config provision status` | none | `execute` `local-reader.status` |
| `aeat config provision verify` | none | `execute` `local-reader.provision` |
| `aeat config repair` | none | the person's act |
| `aeat config repair connectivity` | none | `execute` `diagnostics.connectivity.probe` |
| `aeat config repair integrity objects` | none | `execute` `diagnostics.secure-objects.check` |
| `aeat config repair logs` | none | the person's act |
| `aeat config repair profile` | none | the person's act |
| `aeat config repair quarantine` | none | `execute` `diagnostics.secure-objects.quarantine` |
| `aeat config repair reset-progress` | none | `execute` `diagnostics.workflow-progress.reset` |
| `aeat config reset resume` | none | the person's act |
| `aeat config reset start` | none | the person's act |
| `aeat config reset status` | none | the person's act |
| `aeat config sign-in-hold` | none | the person's act |
| `aeat config sign-in-status` | none | the person's act |
| `aeat config storage check` | none | the person's act |
| `aeat config storage init` | none | the person's act |
| `aeat config storage list` | none | the person's act |
| `aeat config storage reclaim` | none | the person's act |
| `aeat config storage view` | none | the person's act |

## Operations no command submits

These are registered operations too, and `search` finds them. No command
submits them. One that does the work a command does in its own process is
named in that command's row above.

- `browser-runtime.provision`
- `diagnostics.connectivity.probe`
- `diagnostics.secure-objects.check`
- `diagnostics.secure-objects.quarantine`
- `diagnostics.workflow-progress.reset`
- `ledger.evidence.query`
- `ledger.evidence.reader-readiness`
- `ledger.evidence.review.summary`
- `ledger.history.typed`
- `live.borrador.100.query`
- `local-reader.provision`
- `local-reader.report`
- `local-reader.status`
- `modelo.036.query`
- `modelo.audit.query`
- `modelo.bindings.resolve.typed`
- `modelo.edit.apply`
- `modelo.edit.apply_prerequisite`
- `modelo.edit.preflight`
- `modelo.edit.renew`
- `modelo.history.timeline`
- `modelo.readiness.summary`
- `modelo.work.casilla_help`
- `modelo.work.form`
- `profile.history.timeline`
- `user-profile.automation-renew`
- `user-profile.automation-request`
- `user-profile.automation-rotate`
- `user-profile.automation-scope`
- `user-profile.bundle-export`
- `user-profile.censo-certificate-import`
- `user-profile.recovery.revoke`
- `workbench.generation`
