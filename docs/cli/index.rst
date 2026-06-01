CLI reference
=============

The ``aeat`` CLI exposes two top-level command families: ``config`` (local configuration, profile lifecycle, diagnostics) and ``app`` (operational tax workflow). This reference documents all 186 leaf commands.

Help strings are rendered in English. At runtime the CLI respects the active output-language setting (``--language`` / ``AEAT_OUTPUT_LANGUAGE``).

The output schema section below lists every command that emits a ``SchemaEnvelope``-wrapped payload. Commands not listed there emit a bare payload; envelope adoption tracks the json-output-contract migration.

.. toctree::
   :maxdepth: 2
   :caption: Command families

   app
   config

Global flags
------------

These flags are accepted by the ``aeat`` root command and apply to every invocation.

``--language`` / ``--lang``
   Override the output language (``es``, ``en``, ``ca``, ``hu``).

``--profile``
   Activate a named profile for this invocation.

``--version`` / ``-V``
   Print the package version and exit.

``--detail``
   Print extended version information including registry summary.

``--help`` / ``-h``
   Print the curated help document and exit.

``--format``
   Output format (``text`` or ``json``).

``--quiet``
   Suppress informational output.

``--verbose``
   Enable verbose output.

``--debug``
   Enable debug-level logging.

Exit codes
----------

.. list-table::
   :header-rows: 1
   :widths: 10 90

   * - Code
     - Meaning
   * - ``0``
     - Success.
   * - ``1``
     - General error or refused operation.
   * - ``2``
     - Invalid CLI usage (bad flag, missing argument).
   * - ``3``
     - Authentication required or credentials expired.
   * - ``4``
     - Resource not found.
   * - ``5``
     - Conflict or precondition failure.
   * - ``6``
     - Validation error in user-supplied data.
   * - ``7``
     - External service unavailable.
   * - ``8``
     - Operation not permitted by policy.
   * - ``9``
     - Unexpected internal error.
   * - ``10``
     - Partial success (some items succeeded, some failed).

TTY and JSON output contract
----------------------------

When output is to a TTY the CLI emits human-readable rich text. When ``--format json`` is passed (or when output is redirected) the CLI emits a single JSON document per invocation. Commands that have adopted the ``SchemaEnvelope`` wrap their result as ``{schema_version, command, result, warnings}``. Commands not yet migrated emit their payload directly.

Output schema registry
----------------------

The following 186 command paths have a registered ``OutputSchema``.  Group-callback surfaces (2 entries: ``root.app``, ``root.status``) are listed separately.

* ``app.live.borrador.100.latest`` → ``aeat.entrypoints.cli._app_live_payloads.Borrador100LatestResult``
* ``app.live.borrador.100.list`` → ``aeat.entrypoints.cli._app_live_payloads.Borrador100ListResult``
* ``app.live.borrador.100.view`` → ``aeat.entrypoints.cli._app_live_payloads.Borrador100ViewResult``
* ``app.live.expedientes.capture`` → ``aeat.entrypoints.cli._app_live_payloads.ExpedientesCaptureResult``
* ``app.live.expedientes.latest`` → ``aeat.entrypoints.cli._app_live_payloads.ExpedientesLatestResult``
* ``app.live.expedientes.list`` → ``aeat.entrypoints.cli._app_live_payloads.ExpedientesListResult``
* ``app.live.expedientes.view`` → ``aeat.entrypoints.cli._app_live_payloads.ExpedientesViewResult``
* ``app.live.filed.capture`` → ``aeat.entrypoints.cli._app_live_payloads.FiledCaptureResult``
* ``app.live.filed.capture_sources`` → ``aeat.entrypoints.cli._app_live_payloads.FiledCaptureSourcesResult``
* ``app.live.filed.list`` → ``aeat.entrypoints.cli._app_live_payloads.FiledListResult``
* ``app.live.iva_wallet.capture_history`` → ``aeat.entrypoints.cli._app_live_payloads.IvaWalletCaptureHistoryResult``
* ``app.live.iva_wallet.capture_remote_state`` → ``aeat.entrypoints.cli._app_live_payloads.IvaWalletCaptureRemoteStateResult``
* ``app.live.iva_wallet.history`` → ``aeat.entrypoints.cli._app_live_payloads.IvaWalletHistoryResult``
* ``app.live.iva_wallet.pull`` → ``aeat.entrypoints.cli._app_live_payloads.IvaWalletPullResult``
* ``app.live.notifications.capture`` → ``aeat.entrypoints.cli._app_live_payloads.NotificationsCaptureResult``
* ``app.live.notifications.list`` → ``aeat.entrypoints.cli._app_live_payloads.NotificationsListResult``
* ``app.live.notifications.view`` → ``aeat.entrypoints.cli._app_live_payloads.NotificationsViewResult``
* ``app.live.portals.list`` → ``aeat.entrypoints.cli._app_live_payloads.PortalsListResult``
* ``app.live.portals.view`` → ``aeat.entrypoints.cli._app_live_payloads.PortalsViewResult``
* ``app.live.verify.latest`` → ``aeat.entrypoints.cli._app_live_payloads.VerifyLatestResult``
* ``app.live.verify.list`` → ``aeat.entrypoints.cli._app_live_payloads.VerifyListResult``
* ``app.live.verify.nif_iva`` → ``aeat.entrypoints.cli._app_live_payloads.VerifyNifIvaResult``
* ``app.live.verify.tgvi`` → ``aeat.entrypoints.cli._app_live_payloads.VerifyTgviResult``
* ``app.live.verify.view`` → ``aeat.entrypoints.cli._app_live_payloads.VerifyViewResult``
* ``config.auth.apoderado.check`` → ``aeat.entrypoints.cli._config_payloads.ApoderadoCheckResult``
* ``config.auth.apoderado.clear`` → ``aeat.entrypoints.cli._config_payloads.ApoderadoClearResult``
* ``config.auth.apoderado.configure`` → ``aeat.entrypoints.cli._config_payloads.ApoderadoConfigureResult``
* ``config.auth.apoderado.scopes.list`` → ``aeat.entrypoints.cli._config_payloads.ApoderadoScopesListResult``
* ``config.auth.apoderado.status`` → ``aeat.entrypoints.cli._config_payloads.ApoderadoStatusResult``
* ``config.auth.clear`` → ``aeat.entrypoints.cli._config_payloads.AuthClearResult``
* ``config.auth.configure`` → ``aeat.entrypoints.cli._config_payloads.AuthConfigureResult``
* ``config.auth.diagnostics.list`` → ``aeat.entrypoints.cli._config_payloads.AuthDiagnosticsListResult``
* ``config.auth.diagnostics.report`` → ``aeat.entrypoints.cli._config_payloads.AuthDiagnosticsReportResult``
* ``config.auth.diagnostics.show`` → ``aeat.entrypoints.cli._config_payloads.AuthDiagnosticsShowResult``
* ``config.auth.login`` → ``aeat.entrypoints.cli._config_payloads.AuthLoginResult``
* ``config.auth.providers`` → ``aeat.entrypoints.cli._config_payloads.AuthProvidersResult``
* ``config.auth.status`` → ``aeat.entrypoints.cli._config_payloads.AuthStatusResult``
* ``config.auth.test`` → ``aeat.entrypoints.cli._config_payloads.AuthTestResult``
* ``config.bucket.history`` → ``aeat.entrypoints.cli._config_payloads.BucketHistoryResult``
* ``config.google.folder.get`` → ``aeat.entrypoints.cli._config._google_payloads.GoogleFolderGetResult``
* ``config.google.folder.set`` → ``aeat.entrypoints.cli._config._google_payloads.GoogleFolderSetResult``
* ``config.google.login`` → ``aeat.entrypoints.cli._config._google_payloads.GoogleLoginResult``
* ``config.google.logout`` → ``aeat.entrypoints.cli._config._google_payloads.GoogleLogoutResult``
* ``config.google.register`` → ``aeat.entrypoints.cli._config._google_payloads.GoogleRegisterResult``
* ``config.google.status`` → ``aeat.entrypoints.cli._config._google_payloads.GoogleStatusResult``
* ``config.google.sync.calc.export`` → ``aeat.entrypoints.cli._config._google_payloads.GoogleSyncCalcExportResult``
* ``config.google.sync.calc.pull`` → ``aeat.entrypoints.cli._config._google_payloads.GoogleSyncCalcPullResult``
* ``config.google.sync.calc.verify`` → ``aeat.entrypoints.cli._config._google_payloads.GoogleSyncCalcVerifyResult``
* ``config.google.sync.probe`` → ``aeat.entrypoints.cli._config._google_payloads.GoogleSyncProbeResult``
* ``config.google.sync.push`` → ``aeat.entrypoints.cli._config._google_payloads.GoogleSyncPushResult``
* ``config.profile.census.apply`` → ``aeat.entrypoints.cli._config._profile_census_payloads.CensusApplyResult``
* ``config.profile.census.compare`` → ``aeat.entrypoints.cli._config._profile_census_payloads.CensusCompareResult``
* ``config.profile.census.refresh`` → ``aeat.entrypoints.cli._config._profile_census_payloads.CensusRefreshResult``
* ``config.profile.census.show`` → ``aeat.entrypoints.cli._config._profile_census_payloads.CensusShowResult``
* ``config.profile.create`` → ``aeat.entrypoints.cli._config_payloads.ConfigProfileCreateResult``
* ``config.profile.delete`` → ``aeat.entrypoints.cli._config_payloads.ConfigProfileDeleteResult``
* ``config.profile.duplicate`` → ``aeat.entrypoints.cli._config_payloads.ConfigProfileDuplicateResult``
* ``config.profile.edit`` → ``aeat.entrypoints.cli._config_payloads.ConfigProfileEditResult``
* ``config.profile.export`` → ``aeat.entrypoints.cli._config_payloads.ConfigProfileExportResult``
* ``config.profile.import`` → ``aeat.entrypoints.cli._config_payloads.ConfigProfileImportResult``
* ``config.profile.list`` → ``aeat.entrypoints.cli._config_payloads.ConfigListResult``
* ``config.profile.logout`` → ``aeat.entrypoints.cli._config_payloads.ConfigProfileLogoutResult``
* ``config.profile.rename`` → ``aeat.entrypoints.cli._config_payloads.ConfigProfileRenameResult``
* ``config.profile.show`` → ``aeat.entrypoints.cli._config_payloads.ConfigProfileShowResult``
* ``config.profile.status`` → ``aeat.entrypoints.cli._config_payloads.ConfigStatusResult``
* ``config.profile.switch`` → ``aeat.entrypoints.cli._config_payloads.ConfigProfileSwitchResult``
* ``config.repair.connectivity`` → ``aeat.entrypoints.cli._config_payloads.RepairConnectivityResult``
* ``config.repair.integrity.objects`` → ``aeat.entrypoints.cli._config_payloads.RepairIntegrityObjectsResult``
* ``config.repair.integrity.registry`` → ``aeat.entrypoints.cli._config_payloads.RepairIntegrityRegistryResult``
* ``config.repair.logs`` → ``aeat.entrypoints.cli._config_payloads.RepairLogsResult``
* ``config.repair.profile`` → ``aeat.entrypoints.cli._config_payloads.RepairProfileResult``
* ``config.repair.quarantine`` → ``aeat.entrypoints.cli._config_payloads.RepairQuarantineResult``
* ``config.repair.reset_state`` → ``aeat.entrypoints.cli._config_payloads.RepairResetStateResult``
* ``config.reset`` → ``aeat.entrypoints.cli._config_payloads.ConfigResetResult``
* ``ledger.add`` → ``aeat.entrypoints.cli._ledger_payloads.LedgerAddResult``
* ``ledger.allocate`` → ``aeat.entrypoints.cli._ledger_payloads.LedgerAllocateResult``
* ``ledger.archive`` → ``aeat.entrypoints.cli._ledger_payloads.LedgerArchiveResult``
* ``ledger.attach`` → ``aeat.entrypoints.cli._ledger_payloads.LedgerAttachResult``
* ``ledger.categories`` → ``aeat.entrypoints.cli._ledger_payloads.LedgerCategoriesResult``
* ``ledger.check`` → ``aeat.entrypoints.cli._ledger_payloads.LedgerCheckResult``
* ``ledger.classify`` → ``aeat.entrypoints.cli._ledger_payloads.LedgerClassifyResult``
* ``ledger.collectible_invoice.add`` → ``aeat.entrypoints.cli._ledger_payloads.CollectibleInvoiceAddResult``
* ``ledger.collectible_invoice.list`` → ``aeat.entrypoints.cli._ledger_payloads.CollectibleInvoiceListResult``
* ``ledger.collectible_invoice.remove`` → ``aeat.entrypoints.cli._ledger_payloads.CollectibleInvoiceRemoveResult``
* ``ledger.collectible_invoice.update`` → ``aeat.entrypoints.cli._ledger_payloads.CollectibleInvoiceUpdateResult``
* ``ledger.collectible_invoice.view`` → ``aeat.entrypoints.cli._ledger_payloads.CollectibleInvoiceViewResult``
* ``ledger.evidence.add`` → ``aeat.entrypoints.cli._ledger_payloads.EvidenceAddResult``
* ``ledger.evidence.list`` → ``aeat.entrypoints.cli._ledger_payloads.EvidenceListResult``
* ``ledger.evidence.remove`` → ``aeat.entrypoints.cli._ledger_payloads.EvidenceRemoveResult``
* ``ledger.evidence.update`` → ``aeat.entrypoints.cli._ledger_payloads.EvidenceUpdateResult``
* ``ledger.evidence.view`` → ``aeat.entrypoints.cli._ledger_payloads.EvidenceViewResult``
* ``ledger.export`` → ``aeat.entrypoints.cli._ledger_payloads.LedgerExportResult``
* ``ledger.history`` → ``aeat.entrypoints.cli._ledger_payloads.LedgerHistoryResult``
* ``ledger.import`` → ``aeat.entrypoints.cli._ledger_payloads.LedgerImportResult``
* ``ledger.inventory.create`` → ``aeat.entrypoints.cli._ledger_payloads.InventoryCreateResult``
* ``ledger.inventory.list`` → ``aeat.entrypoints.cli._ledger_payloads.InventoryListResult``
* ``ledger.inventory.movement.add`` → ``aeat.entrypoints.cli._ledger_payloads.InventoryMovementAddResult``
* ``ledger.inventory.valuation.preview`` → ``aeat.entrypoints.cli._ledger_payloads.InventoryValuationPreviewResult``
* ``ledger.link`` → ``aeat.entrypoints.cli._ledger_payloads.LedgerLinkResult``
* ``ledger.list`` → ``aeat.entrypoints.cli._ledger_payloads.LedgerListResult``
* ``ledger.merge`` → ``aeat.entrypoints.cli._ledger_payloads.LedgerMergeResult``
* ``ledger.payable_invoice.add`` → ``aeat.entrypoints.cli._ledger_payloads.PayableInvoiceAddResult``
* ``ledger.payable_invoice.list`` → ``aeat.entrypoints.cli._ledger_payloads.PayableInvoiceListResult``
* ``ledger.payable_invoice.remove`` → ``aeat.entrypoints.cli._ledger_payloads.PayableInvoiceRemoveResult``
* ``ledger.payable_invoice.update`` → ``aeat.entrypoints.cli._ledger_payloads.PayableInvoiceUpdateResult``
* ``ledger.payable_invoice.view`` → ``aeat.entrypoints.cli._ledger_payloads.PayableInvoiceViewResult``
* ``ledger.preflight`` → ``aeat.entrypoints.cli._ledger_payloads.LedgerPreflightResult``
* ``ledger.ratios.eligible`` → ``aeat.entrypoints.cli._ledger_payloads.RatiosEligibleResult``
* ``ledger.ratios.list`` → ``aeat.entrypoints.cli._ledger_payloads.RatiosListResult``
* ``ledger.ratios.set`` → ``aeat.entrypoints.cli._ledger_payloads.RatiosSetResult``
* ``ledger.ratios.unset`` → ``aeat.entrypoints.cli._ledger_payloads.RatiosUnsetResult``
* ``ledger.ratios.validate`` → ``aeat.entrypoints.cli._ledger_payloads.RatiosValidateResult``
* ``ledger.remove`` → ``aeat.entrypoints.cli._ledger_payloads.LedgerRemoveResult``
* ``ledger.reset`` → ``aeat.entrypoints.cli._ledger_payloads.LedgerResetResult``
* ``ledger.review`` → ``aeat.entrypoints.cli._ledger_payloads.LedgerReviewResult``
* ``ledger.rule.add`` → ``aeat.entrypoints.cli._ledger_payloads.RuleAddResult``
* ``ledger.rule.apply`` → ``aeat.entrypoints.cli._ledger_payloads.RuleApplyResult``
* ``ledger.rule.list`` → ``aeat.entrypoints.cli._ledger_payloads.RuleListResult``
* ``ledger.split`` → ``aeat.entrypoints.cli._ledger_payloads.LedgerSplitResult``
* ``ledger.stash`` → ``aeat.entrypoints.cli._ledger_payloads.LedgerStashResult``
* ``ledger.status`` → ``aeat.entrypoints.cli._ledger_payloads.LedgerStatusResult``
* ``ledger.track`` → ``aeat.entrypoints.cli._ledger_payloads.LedgerTrackResult``
* ``ledger.update`` → ``aeat.entrypoints.cli._ledger_payloads.LedgerUpdateResult``
* ``ledger.view`` → ``aeat.entrypoints.cli._ledger_payloads.LedgerViewResult``
* ``modelo.aggregate`` → ``aeat.entrypoints.cli._modelo_payloads.ModeloAggregateResult``
* ``modelo.audit.check`` → ``aeat.entrypoints.cli._modelo_payloads.ModeloAuditCheckResult``
* ``modelo.audit.export`` → ``aeat.entrypoints.cli._modelo_payloads.ModeloAuditExportResult``
* ``modelo.audit.replay`` → ``aeat.entrypoints.cli._modelo_payloads.ModeloAuditReplayResult``
* ``modelo.audit.show`` → ``aeat.entrypoints.cli._modelo_payloads.ModeloAuditShowResult``
* ``modelo.bindings.list`` → ``aeat.entrypoints.cli._modelo_payloads.ModeloBindingsListResult``
* ``modelo.bindings.preview`` → ``aeat.entrypoints.cli._modelo_payloads.ModeloBindingsPreviewResult``
* ``modelo.casillas`` → ``aeat.entrypoints.cli._modelo_payloads.ModeloCasillasResult``
* ``modelo.compare`` → ``aeat.entrypoints.cli._modelo_payloads.ModeloCompareResult``
* ``modelo.describe`` → ``aeat.entrypoints.cli._modelo_payloads.ModeloDescribeResult``
* ``modelo.export`` → ``aeat.entrypoints.cli._modelo_payloads.ModeloExportResult``
* ``modelo.filing_record.import`` → ``aeat.entrypoints.cli._modelo_payloads.FilingRecordImportResult``
* ``modelo.filing_record.list`` → ``aeat.entrypoints.cli._modelo_payloads.ModeloRecordListResult``
* ``modelo.filing_record.view`` → ``aeat.entrypoints.cli._modelo_payloads.ModeloRecordShowResult``
* ``modelo.formulas`` → ``aeat.entrypoints.cli._modelo_payloads.FormulasResult``
* ``modelo.history`` → ``aeat.entrypoints.cli._modelo_payloads.ModeloHistoryResult``
* ``modelo.iva_wallet.balance`` → ``aeat.entrypoints.cli._modelo_payloads.IvaWalletBalanceResult``
* ``modelo.iva_wallet.seed`` → ``aeat.entrypoints.cli._modelo_payloads.IvaWalletSeedResult``
* ``modelo.list`` → ``aeat.entrypoints.cli._modelo_payloads.ModeloListResult``
* ``modelo.project`` → ``aeat.entrypoints.cli._modelo_payloads.ModeloProjectResult``
* ``modelo.readiness`` → ``aeat.entrypoints.cli._modelo_payloads.ModeloReadinessResult``
* ``modelo.reconcile`` → ``aeat.entrypoints.cli._modelo_payloads.ModeloReconcileResult``
* ``modelo.reconcile_from_justificante`` → ``aeat.entrypoints.cli._modelo_payloads.ModeloReconcileResult``
* ``modelo.verification_report.list`` → ``aeat.entrypoints.cli._modelo_payloads.VerificationReportListResult``
* ``modelo.verification_report.view`` → ``aeat.entrypoints.cli._modelo_payloads.VerificationReportShowResult``
* ``modelo.work.amend`` → ``aeat.entrypoints.cli._modelo_payloads.WorkAmendResult``
* ``modelo.work.calculate`` → ``aeat.entrypoints.cli._modelo_payloads.WorkCalculateResult``
* ``modelo.work.compare_taxation`` → ``aeat.entrypoints.cli._modelo_payloads.WorkCompareTaxationResult``
* ``modelo.work.create`` → ``aeat.entrypoints.cli._modelo_payloads.WorkCreateResult``
* ``modelo.work.discard`` → ``aeat.entrypoints.cli._modelo_payloads.WorkDiscardResult``
* ``modelo.work.file`` → ``aeat.entrypoints.cli._modelo_payloads.WorkFileResult``
* ``modelo.work.history`` → ``aeat.entrypoints.cli._modelo_payloads.WorkHistoryResult``
* ``modelo.work.list`` → ``aeat.entrypoints.cli._modelo_payloads.WorkListResult``
* ``modelo.work.preview_maritime_exemption`` → ``aeat.entrypoints.cli._modelo_payloads.WorkPreviewMaritimeExemptionResult``
* ``modelo.work.rename`` → ``aeat.entrypoints.cli._modelo_payloads.WorkRenameResult``
* ``modelo.work.resume`` → ``aeat.entrypoints.cli._modelo_payloads.WorkResumeResult``
* ``modelo.work.revision`` → ``aeat.entrypoints.cli._modelo_payloads.WorkRevisionResult``
* ``modelo.work.revisions`` → ``aeat.entrypoints.cli._modelo_payloads.WorkRevisionsResult``
* ``modelo.work.runs`` → ``aeat.entrypoints.cli._modelo_payloads.WorkRunsResult``
* ``modelo.work.status`` → ``aeat.entrypoints.cli._modelo_payloads.WorkStatusResult``
* ``modelo.work.verify`` → ``aeat.entrypoints.cli._modelo_payloads.WorkVerifyResult``
* ``overview.agenda`` → ``aeat.entrypoints.cli._overview_payloads.OverviewAgendaResult``
* ``overview.backlog`` → ``aeat.entrypoints.cli._overview_payloads.OverviewBacklogResult``
* ``overview.calendar`` → ``aeat.entrypoints.cli._overview_payloads.OverviewCalendarResult``
* ``overview.explain`` → ``aeat.entrypoints.cli._overview_payloads.OverviewExplainResult``
* ``overview.status`` → ``aeat.entrypoints.cli._overview_payloads.OverviewStatusResult``
* ``registry.audit_oracles`` → ``aeat.entrypoints.cli._registry_payloads.RegistryAuditOraclesResult``
* ``registry.citations.list`` → ``aeat.entrypoints.cli._registry_corpus_payloads.CitationListResult``
* ``registry.citations.verify`` → ``aeat.entrypoints.cli._registry_corpus_payloads.CitationVerifyResult``
* ``registry.citations.view`` → ``aeat.entrypoints.cli._registry_corpus_payloads.CitationShowResult``
* ``registry.inspect`` → ``aeat.entrypoints.cli._registry_payloads.RegistryInspectResult``
* ``registry.manuals.list`` → ``aeat.entrypoints.cli._registry_corpus_payloads.ManualListResult``
* ``registry.manuals.rules`` → ``aeat.entrypoints.cli._registry_corpus_payloads.ManualRulesListResult``
* ``registry.manuals.verify`` → ``aeat.entrypoints.cli._registry_corpus_payloads.ManualVerifyResult``
* ``registry.manuals.view`` → ``aeat.entrypoints.cli._registry_corpus_payloads.ManualShowResult``
* ``registry.parity.replay`` → ``aeat.entrypoints.cli._registry_payloads.RegistryParityReplayResult``
* ``registry.parity.run`` → ``aeat.entrypoints.cli._registry_payloads.RegistryParityRunResult``
* ``registry.verify`` → ``aeat.entrypoints.cli._registry_payloads.RegistryVerifyResult``
* ``registry.verify_filed_state`` → ``aeat.entrypoints.cli._registry_payloads.RegistryVerifyFiledStateResult``
* ``registry.workbooks.verify`` → ``aeat.entrypoints.cli._registry_payloads.RegistryWorkbooksVerifyResult``
* ``review.queue`` → ``aeat.entrypoints.cli._review_payloads.ReviewQueueResult``
* ``review.view`` → ``aeat.entrypoints.cli._review_payloads.ReviewViewResult``

Retired surfaces
----------------

The following command roots or families have been retired. They are listed here with redirect guidance so operators can update their tooling.

``aeat setup`` (retired)
~~~~~~~~~~~~~~~~~~~~~~~~
setup and config are consolidated under the config root.

**Use instead:** ``aeat config profile create NAME``

``aeat archive`` (retired)
~~~~~~~~~~~~~~~~~~~~~~~~~~
archive is consolidated under config bucket.

**Use instead:** ``aeat config bucket``

``aeat data`` (retired)
~~~~~~~~~~~~~~~~~~~~~~~
data work is consolidated under app ledger.

**Use instead:** ``aeat app ledger``

``aeat filing`` (retired)
~~~~~~~~~~~~~~~~~~~~~~~~~
filing work is consolidated under app modelo.

**Use instead:** ``aeat app modelo``

``aeat financial`` (retired)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
financial work is consolidated under app ledger.

**Use instead:** ``aeat app ledger``

``aeat invoice`` (retired)
~~~~~~~~~~~~~~~~~~~~~~~~~~
invoice work is consolidated under app ledger.

**Use instead:** ``aeat app ledger``

``aeat declaration`` (retired)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
declaration work is consolidated under app modelo.

**Use instead:** ``aeat app modelo``

``aeat sanitize`` (retired)
~~~~~~~~~~~~~~~~~~~~~~~~~~~
ledger checks are exposed under app ledger check.

**Use instead:** ``aeat app ledger check``

``aeat llm`` (retired)
~~~~~~~~~~~~~~~~~~~~~~
classification is exposed under app ledger classify.

**Use instead:** ``aeat app ledger classify``

``aeat topic`` (retired)
~~~~~~~~~~~~~~~~~~~~~~~~
topic lookup is consolidated under app registry citations.

**Use instead:** ``aeat app registry citations``

``aeat submit`` (retired)
~~~~~~~~~~~~~~~~~~~~~~~~~
live submission is permanently disabled.

**Status:** Permanently removed. No replacement is available.

``aeat presentation`` (retired)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
exports belong to app modelo export.

**Use instead:** ``aeat app modelo export``

``aeat preflight`` (retired)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
preflight belongs to modelo verification.

**Use instead:** ``aeat app modelo verify``

``aeat workflow`` (retired)
~~~~~~~~~~~~~~~~~~~~~~~~~~~
workflow operations are consolidated under app modelo.

**Use instead:** ``aeat app modelo``

