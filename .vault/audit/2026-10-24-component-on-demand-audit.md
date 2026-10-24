---
tags:
  - '#audit'
  - '#component-on-demand'
date: '2026-10-24'
modified: '2026-10-24'
body_schema: 'body-v2'
body_hash: 'sha256:2f856a44307763d6292e580e24ca7cc956ea3fb588754f27201a0075b210f570'
related:
  - "[[2026-10-24-component-on-demand-plan]]"
  - "[[2026-10-18-dependency-provisioning-unified-setup-adr]]"
---

# `component-on-demand` audit: `Component on-demand review`

## Scope

Plan-close integrated review of `2026-10-24-component-on-demand-plan` (L1, S01 to S13 closed), diff base `9410079da8^`, target `a49df6aa83` (the plan's last ledger close), on `feature/tui`. Governing decisions: `2026-10-18-dependency-provisioning-unified-setup-adr` D8 to D10 and `2026-10-24-rust-component-provisioning-adr` constraint 13. The review traced these journeys end to end: AEAT live capture and sign-in with no browser; evidence extraction (scan and text) with no local AI; bank CSV import and invoice bulk intake that need the column model; PDF statement import; ledger classification; batch ingest pause; and a hardware-refused role. It also covered the withdrawn-provisioning state from `c002a7769a` and `754fbcee5b`, where a missing component reads blocked `not_in_this_build`. Uncommitted work from other sessions sits in the working tree: the record-based browser probe in `src/cadrumo/application/provisioning_browser.py` and `session.py`, plus unrelated desktop, borrador and native files. The review attributes none of it to this plan.

Verification reused: the ledger's per-Step results. Verification run here: 165 focused tests (plan tests, the consumer gate, the wording, CLI, TUI modal and setup tests, and the settlement suites) gave 164 passed and 1 failed. The failure comes from uncommitted work (last finding). The caller suites (auth definitions, invoice intake, batch CLI, TUI label reading, statement reading, mapped tabular, vision CLI, TUI operations and setup) gave 243 passed and 18 failed. The 18 are the TUI catalogue tests failing on `ModeloEditOperatorInputV2` schema closure, which the S11 ledger already records as pre-existing. `lint-imports` kept 30 of 30 contracts, and the desktop `tsc --noEmit` passed. The desktop Playwright scenarios were not run, because they rebuild the shared preview.

## Findings

### import-reader-refusal-swallowed | high | A bank CSV or PDF statement import that needs the local AI still reads as an unreadable statement on every surface

`src/cadrumo/application/ledger/actions_import.py:746` raises `LedgerImportReaderUnavailableError` with the reader verdict. That error subclasses `TransactionValidationError`. The registered `ledger.import` executor catches that base class at `src/cadrumo/application/ledger/import_operation.py:481` and turns it into a `LedgerImportFileRefusal` with `reason_code="transaction_validation"`, so the verdict is discarded. The definition (`import_operation.py:733`) also does not publish its error detail. The CLI therefore raises `cli.ledger.import.statement_refused` with a no-recovery verdict (`src/cadrumo/entrypoints/cli/ledger_import_commands.py:151-159`). The TUI and the desktop show the `transaction_validation` reason "Could not be read as a bank statement" (`src/cadrumo/locales/en/common.yml:1973`), MCP gets no `recovery_action_id`, and no surface offers setup. This is the silent decline S03 set out to remove, and it now also catches the S13 statement reader refusal. The S03 and S13 tests drive `prepare_ledger_source_import` and `build_operation_error_detail` in process, and the S09 gate drives the composed resolver, so none of them runs the registered executor. Fix: carry the verdict through the operation. Either refuse the whole `ledger.import` REFUSED with `public_error_detail=True`, or add a typed file-refusal reason that carries the recovery action id into `LedgerImportResultProjection` and route it on the CLI, TUI and desktop. Prove it with a real supervisor settlement test like those of S11 and S12.

### invoice-import-detail-unpublished | high | Invoice bulk intake refuses with the reader verdict but never publishes it, so other processes lose the setup route

S10 makes `read_bulk_invoice_import_source` raise `LedgerImportReaderUnavailableError`, and `InvoiceIntakeExecutor` lets it settle REFUSED. `ledger.invoice.import` is built at `src/cadrumo/application/invoices/catalogue_intake_operation.py:35-52` without `public_error_detail`; a live registry read confirms `public_error_detail=False`. A CLI, TUI, MCP or desktop client in another process therefore receives only `REFUSED_LEDGER_IMPORT_READER`, renders `errors.transaction.ledger_import_failed` without its reason, and gets no verdict. The test (`src/cadrumo/application/invoices/tests/test_catalogue_intake_operation.py`) calls `build_operation_error_detail` directly, which proves the shape but not the publication. Fix: opt the invoice import definition into public error detail, as S12 did for classification, regenerate the contract manifest, and add a supervisor settlement test that reads the detail back.

### batch-pause-not-routed | high | A batch ingest paused for the local AI offers no setup on the TUI or the desktop

`ledger.evidence.batch` settles successfully with `inference_pause` carrying a verdict that names `operator.provision.local_ai`. S12 proves that the verdict reaches the result. Nothing in the TUI or the desktop reads it. The TUI prints "Reading paused because the model reader could not be admitted" (`src/cadrumo/entrypoints/tui/ledger/evidence_files_batch.py:75-76`, `src/cadrumo/locales/en/common.yml:5709`): it names no component, uses internal vocabulary ("admitted"), and offers no action. The desktop's `applyDocuments` keeps only `run.items` and `run.unresolved`, so `inference_pause` is dropped (`native/desktop/frontend/src/components/ledger/transfer/importModel.ts:432-434`), and `routeProvisioningRefusals` acts only on refused outcomes. Constraint 13 requires that every surface route the verdict to setup. Folder intake is the desktop's main document path. Fix: route `inference_pause` to the setup offer on both surfaces, with the local AI sentence in four languages.

### off-host-read-misattributed | medium | A failed off-host vision read is told to set up the local AI

`src/cadrumo/application/ledger/invoice_draft_extraction.py:962-966` falls back to `probe_local_reader(VISION_TRANSCRIPTION)` whenever the unavailable-reader error carries no verdict. The composition deliberately returns no verdict for an off-host read (`src/cadrumo/entrypoints/ledger_evidence_extraction_composition.py:142-153`). When the agent-provider read fails and the local runtime is absent, the refusal becomes "Local AI is not ready, so nothing was read. Set it up", and every surface routes to a local AI setup the person did not choose. S01 gave this verdict its action, which turned a pre-existing fallback into wrong guidance. Fix: probe only when `off_host_provider` is `None` or `LOCAL`.

### setup-offered-when-blocked | medium | CLI, TUI and the desktop auto-prompt offer setup for an item that reads blocked not_in_this_build

Consumer verdicts always name `operator.provision.<item>`. Because provisioning is withdrawn, the CLI prints "To fix it, run: aeat config provision pull", which then refuses with "This version of Cadrumo does not include this." (`src/cadrumo/entrypoints/cli/_component_setup_rendering.py:16-33`). The TUI modal labels its button "Set up: Local AI" (`src/cadrumo/entrypoints/tui/operations/modal.py:349-360`). The desktop `offerSetup` opens the prompt with a primary "Open setup" button on a blocked row (`native/desktop/frontend/src/App.tsx:900-913`, `native/desktop/frontend/src/components/setup/SetupPrompt.tsx:47`). The refusal sentences say "Set it up, then try again". Only `SetupOffer` checks `needsSetup`. `src/cadrumo/application/dependency_withdrawal.py:5-6` states that no surface offers a setup. Nothing crashes, and the setup surface ends with an honest sentence, but the person reaches a dead end two steps later. Fix: before offering, every surface reads the current row of the item and its recovery, as `SetupOffer` does. When that recovery is none, show the row sentence and no action.

### hardware-refusal-unreachable | medium | A computer that cannot run a role still gets a setup offer in the common case

`_reader_status_from_inventory` checks for an unreachable runtime (`src/cadrumo/application/local_reader.py:477-490`) before it checks for a refused selection (`src/cadrumo/application/local_reader.py:491-500`). A below-floor computer without the local AI program running is therefore told to set it up. The extraction roles return their setting as written (`src/cadrumo/application/local_reader.py:309-310`), so they never reach the no-action branch at all. The S01 claim that a role the catalogue cannot serve on this hardware keeps its no-action verdict holds only for the mapping and supply-nature roles, and only while the runtime answers. Fix: judge selection and hardware before reachability, and apply the hardware floor to the extraction roles, or let the item row decide (previous finding).

### gate-stops-at-consumer | medium | The consumer gate stops at the composed consumer, and its stated scope does not say so

`src/cadrumo/entrypoints/tests/test_dependency_consumer_gating.py:1-62` proves that each discovered consumer refuses with the setup action before any request. It does not prove that the owning registered operation preserves or publishes that verdict. Its "Where it stops" list (`src/cadrumo/entrypoints/tests/test_dependency_consumer_gating.py:39`) names exemptions and executor ordering but not verdict propagation, and that gap is how the three high findings passed. Fix: add an operation row. For each registered definition whose composition reaches a gated consumer, settle through the real supervisor with the component missing, and assert that the published detail or the result carries the action. Add a falsifier fixture with an executor that swallows the refusal, and state the remaining limit in the docstring.

### batch-cli-raw-facts | low | CLI batch pause text prints raw verdict facts and does not name the local AI

`src/cadrumo/entrypoints/cli/ledger_evidence_batch_commands.py:392-401` emits `paused.facts.<key>` lines such as `runtime_url` and `runtime_reachable`. The deferred notice says that no reading model could be run and asks for a re-run once the cause below is cleared (`src/cadrumo/locales/en/cli.yml:108-110`). The setup command line is correct. Fix: drop the facts lines from text output (JSON keeps them) and use the local AI sentence.

### tui-label-fallback-no-action | low | The TUI label-reading line says to set up the local AI but offers no way there

`src/cadrumo/entrypoints/tui/ledger/evidence_draft.py:281-287` selects the `local_ai_not_ready` sentence when the fallback carries a recovery action, but the draft view posts no `SetupItemRequested`. The desktop offers `SetupOffer` in the same place. Fix: post the same setup request from the draft view.

### verdict-paths-published | low | Browser verdict evidence publishes an absolute browsers-root path to MCP clients

`src/cadrumo/application/provisioning_browser.py:307` and `src/cadrumo/application/provisioning_browser.py:327` put `browser_cache_root`, an absolute path under the storage root of the user, into the verdict evidence. Since S04 every live preflight refusal publishes that evidence through `OperationErrorDetailV1` to MCP replies (`src/cadrumo_mcp/mcp/admitted_operations.py:494-503`), which may reach a hosted agent. The fact predates the plan, at launch, but now ships on every refusal. Fix: carry storage-relative facts, or none, in published verdict evidence.

### browser-code-key-mismatch | low | REFUSED_BROWSER_NOT_READY registers the set-up sentence even for the not-usable case

`src/cadrumo/core/errors/registry/_adapters_part1.py:160-168` gives the code `message_key="adapters.browser.errors.not_provisioned"`, while `src/cadrumo/adapters/outbound/aeat/browser/session.py:99-103` passes `not_usable` as the translated message when setup cannot repair the browser. A reader that has only the code, with no detail authority, renders "Set it up" for an unusable driver. Fix: a second code, or a code-level key that offers no setup.

### uncommitted-browser-test-failure | low | The live capture contrast test fails in the working tree because of uncommitted probe work from another session

`src/cadrumo/entrypoints/tests/test_live_browser_readiness_refusal.py:149` fails because the completion markers of the contrast root no longer satisfy the record-based probe in the uncommitted `src/cadrumo/application/provisioning_browser.py`. Committed code passes, and that session is editing the test. Record it as pending for the owner of the record-based probe, not as a defect of this plan.

## Recommendations

- The three high findings reopen S03 and S13 (import refusal propagation), S10 (invoice import detail publication) and S07 and S08 (batch pause routing). Each fix needs a real supervisor settlement test that reads the refusal back the way a client in another process does.
- Extend the S09 gate with an operation-level propagation row and its falsifier, so a swallowed or unpublished verdict fails mechanically.
- Follow-on decision for an ADR amendment to unified-setup D10 or rust-component constraint 13: whether a consumer verdict names the setup action of its item unconditionally, with surfaces reading the item row before they offer, or names an action only when the current recovery of the item can act. This decides how surfaces behave while components read `not_in_this_build`, and whether the hardware floor moves into the consumer verdict.
- Wording reviewed in en, es, ca and hu for the S05, S09 and S13 keys: informal singular throughout (es tú, ca tu, hu te) and no internal vocabulary. The remaining wording gaps are the TUI batch pause line and the CLI batch deferred notice.
