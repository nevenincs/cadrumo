# Shared acceptance execution pattern

Pattern ID: ACCEPTANCE-01. Revision: 1.7.
Applies to every income/IVA/retenciones/assets/calendar/profile/ledger and scoped live-acquisition CLI, TUI, and continuation session. Provider-neutral. Revision 1.7 adds invoice/transaction lifecycle replay and evidence-link scenarios; live and notification-access boundaries are unchanged.

This is the central convention for development acceptance drivers, temporary settings, run isolation, and receipts. Session leads apply it to their owned implementation; this document does not claim the current income driver already conforms in every detail.

Apply session-policy.md revision 1.8's mandatory Luna Max discovery cadence. Leads consume bounded source-map/audit reports and inspect only the relevant contracts, decision-critical findings, and code being edited. Missing context triggers a bounded delegated question, not an independent broad source sweep. This applies to the adoption audit below as well as tax-domain discovery.

## Code and run roots

- Acceptance orchestration code belongs under dev/acceptance/. Tax-family scenarios/oracles remain under their owning package, currently dev/acceptance/income_tax/; IVA, retenciones and assets follow the same convention. Harness tests live in the owning tests/ directory. Product code never imports dev/.
- A development code root is not a product storage root. Each execution allocates a unique, explicitly owned run location through the repository's existing run/temp path conventions. Store synthetic runtime state, exports, and diagnostics outside tracked source directories. Do not use dev/acceptance/ as a live profile/database directory.
- CLI-only and TUI-only get independent fresh secure stores. CLI-to-TUI and TUI-to-CLI each get a separate scenario store shared only by their sequential steps. Every period within a scenario deliberately uses that scenario's store. Separate scenarios and concurrent runs do not reuse stores.
- Refuse a nonempty store at a new-run boundary. Resume is explicit and checks scenario/run identity, source state, authority, and credentials; it does not silently ingest the same invoices/history again. Reopening for continuation is not a new-run boundary.
- Reuse existing canonical environment/path/storage primitives. Shared execution plumbing gets one defining owner within dev/acceptance/ when needed; IVA, retenciones and assets must not copy an income-specific environment builder, process runner, or receipt writer and let it drift. The exact implementation placement remains with the assigned owner and existing project boundaries.

## Temporary settings versus tax inputs

Temporary execution settings are permitted for isolation and reproducibility. They must use supported configuration channels and apply only to owned child processes or an explicitly restored scoped context. Do not change the user's persistent configuration, global environment, real profile, or canonical authority.

The current installed income driver establishes these concrete settings:

| Setting | Purpose | Contract |
| --- | --- | --- |
| CADRUMO_LOCAL_STORAGE_ROOT | Synthetic profile/storage location | Fresh scenario-owned root; still use the real encrypted persistence path |
| CADRUMO_AUTHORITY_ROOT | Selected calculation/export authority | Explicit existing authority; pin generation and revisions and verify identity through the run; no edits to make a case pass |
| CADRUMO_OUTPUT_LANGUAGE | Stable presentation | Fixed declared locale for comparisons; not a substitute for locale-specific tests |
| PYTHONIOENCODING | Child process text encoding | UTF-8 consistently across capture and parsing |

Build this environment once through the common owned implementation, then use it consistently for profile creation, every CLI command, and the installed TUI process. Remove ambient product-specific overrides and apply a documented allowlist; preserve the non-product environment needed to launch the executable. Audit .env/settings discovery, working directory, log/cache/temp roots, and OS-keychain effects separately: setting the local-storage root alone is not proof of complete isolation. Do not add PYTHONPATH/import tricks to make installed product code reach dev/.

Existing primitives to inspect/reuse: core/config.py and core/paths.py own storage-root and derived-path resolution; tests/env_scope.py and tests/settings_scope.py own in-process test isolation and async settings scope; dev/test_runs/logging.py owns run scratch/log environment; dev/test_runs/paths.py owns transient run locations. Product storage, authority, and diagnostic/scratch roots serve different purposes. Explicit database/provider/directory overrides can escape the local root, so verify effective settings rather than merely recording the requested root. Do not import test-fixture machinery into product runtime.

Taxpayer facts and synthetic financial values are versioned scenario inputs, not environment overrides or scattered temporary constants. Generate dates/periods from the selected year. Keep values, units (fraction versus percentage), profile facts, invoice/transaction identities, and history conditions in one scenario definition consumed by both frontend drivers. Per-year oracle constants must carry supported-year/evidence scope; date parameterization alone does not establish year-independent tax correctness.

Profile scenarios additionally record selected-entity identity, fact provenance and effective/evaluation dates where supported. Distinguish current configuration, imported census evidence and the context of an existing filing. Use two synthetic entities within an explicitly owned multi-entity scenario to prove selection isolation; other scenarios remain isolated. Exercise creation/editing through supported frontends and fresh-process reopening, including cancel/refusal paths. Do not seed private repositories directly and claim onboarding passed, or overwrite historical context to make a dependent tax scenario pass.

Ledger scenarios retain stable synthetic invoice, transaction, payment and evidence identities across intentional replays and corrections. Compare canonical persisted meaning and revision/link history, not only row counts. Exact replay, changed-content replay, partial import, failed related writes and explicit continuation are separate cases. Attachments use the real encrypted evidence boundary; a file path or digest alone does not prove custody. Reuse the same input definitions and unchanged lifecycle receipts across tax lanes without sharing mutable stores across independent runs.

Manual bindings/casilla values are allowed only where the scenario identifies a legitimate user-supplied fact through a supported product flow. They may not populate a quantity whose acceptance claim is automatic derivation from invoices, transactions, or filing history. Never patch guards, verification results, missing-history facts, production time, or authority definitions to turn a failed journey green. Any explicitly simulated historical/evidence state is labelled and its acquisition coverage kept separate.

## Real frontends and shared scenario

- Use the actual installed CLI executable and installed TUI composition for user-journey acceptance. Record executable/package/source identity and make sure it corresponds to the implementation under evaluation; an old installation cannot prove an edited tree works.
- Use supported user flows for product writes. Fresh-process reopening proves persistence. In-process unit/controller checks remain useful but are reported separately from installed-frontend acceptance.
- Resolve year, authority generation, and modelo revisions once at preflight, then pass that result to all drivers. Do not replace selected revisions with a hardcoded alias or derive a revision identifier from the year string unless the canonical resolver provides that identity.
- Oracle expectations remain independent from production outputs. Compare financial results, relevant persisted fields, provenance, history state, verification, and actual export structure/meaning. A successful command, file existence, size, or digest is not sufficient validation by itself.
- Default to synthetic/offline execution. A live AEAT acquisition run is separately scoped and labelled; captured evidence playback does not prove live connectivity. No live filing submission follows from acceptance authorization.

## Secrets, artifacts, and cleanup

### Explicitly authorized live read-only acquisition

This exception applies only to the service and taxpayer access the user has authorized, initially LIVE-WALLET-01. It does not convert synthetic test runs into production-data tests or authorize AEAT filings, payments, amendments, account changes or unrelated protected-service browsing.

Calendar/message reconciliation uses synthetic or already lawfully acquired encrypted evidence while live testing is blocked. Listing notification metadata is distinct from opening its content, acknowledging receipt or responding; content access may itself have legal effects. None of those consequential actions is implicitly authorized by calendar inspection, synchronization or a prior wallet-read permission. Require explicit action-specific authorization and preserve the legal event timestamp separately from local viewing/import timestamps.

- Reserve one authentication/browser owner globally, identify the read-only service, establish user availability for interactive approval, and set a finite timeout/retry budget before starting. Stop on cancellation, unsupported authentication or unknown navigation; do not bypass an access challenge or create repeated mobile requests.
- Load supplied credentials using the existing supported configuration/secret boundary. Report only field presence/validity, not values. Never print .env, put NIE/support/password/OTP values in command arguments, request them in chat, or create a new plaintext credential file. A credential-file location is not proof the app loads it. Preserve user files/configuration.
- NIE/support number is identity/contrast input, not proof of completed Cl@ve authentication. AEAT credentials, local encrypted-profile unlock credentials and browser session material are distinct. Do not manufacture, reset or substitute any of them to make a check pass.
- Use an explicitly selected secure profile/bucket and supported non-destructive configuration. Agree whether existing or isolated encrypted persistence is used before pulling. Do not overwrite an active user's profile, write private observations into synthetic stores, or copy all user secrets to a new root. Existing stores are never new-run cleanup targets.
- Audit live stdout/stderr, exceptions, screenshot/HTML/PDF/HAR downloads, Playwright traces/video, browser storage-state and cookie persistence before execution. Real payloads may be retained only through approved encrypted storage; receipts/transcripts contain safe statuses and opaque evidence references. If the runner cannot meet this boundary, report a safety blocker; do not launch it and attempt to redact after disclosure.
- Report stages independently: configuration loaded; authentication requested; user approval accepted; protected service reached; result or explicit empty state recognized; canonical schema parsed; encrypted observation stored; frontend presented; reconciliation checked. No balance value, identity, OTP, QR payload, cookie or raw page is needed in the agent report. A legitimate empty wallet is different from a login page, parse failure or unavailable service.
- Reuse one live acquisition receipt across backend and frontend consumers when it proves the same unchanged contract. Separate synthetic CLI/TUI tests prove deterministic setup/refusal/parity; live execution proves actual access. Cached data and fixture playback are never relabelled as a fresh live result. If both frontends require live execution proof, run sequentially under the same reservation and report each separately.
- Close owned browser contexts and processes, apply the existing secure session-retention policy, and release the reservation explicitly. Do not delete the user's .env, certificate, profile or credential store. Keep only sanitized receipt metadata and approved encrypted evidence.

For synthetic runs, generate per-run credentials and deliver them through approved stdin/secret channels. Never put them in argv, receipts, exceptions, logs, or committed fixtures. Continuation drivers must obtain the same run credential through the approved channel, without a plaintext handoff file. Encrypted product storage remains mandatory even for the acceptance profile. Live runs use the explicitly selected existing credential boundary described above, not synthetic AEAT credentials.

Sanitize failure paths as well as success receipts. Never interpolate raw stdout/stderr, entire JSON documents, raw argument lists, or financial payloads into an exception. Preserve command identity, return code, error/notice code, failed assertion identity and a sanitized diagnostic. Keep full authorized diagnostics only in their proper bounded diagnostic storage, not conversation transcripts.

Each run declares retention: keep sanitized receipt and required synthetic validated artifacts, dispose of transient material after owned processes close, and preserve only approved failure evidence. Resolve exact owned paths before cleanup; never delete a shared temp root, workspace, user storage, another run, or an active continuation store. Report cleanup failure rather than concealing it.

## Receipt and outcome contract

Every driver emits the same conceptual fields: pattern/brief/scenario versions; run/session/path identity; year/as-of date; authority generation and revisions; executable/source state; nonsecret effective settings/root identities; commands and return codes; acceptance-case outcome; oracle comparisons; selected checks/counts; artifact validation results/digests; refusal/blocker codes; and retention/cleanup state. Use the existing versioned receipt implementation where it fits; extend it once under one writer rather than defining incompatible tax-family formats.

Outcomes distinguish proven, failed, blocked, and not exercised. Partial calculation/verification/export progress is preserved even if a later command fails. A receipt successfully written is not acceptance success: process exit/status must distinguish incomplete/failed acceptance from completion. A diagnostic capability-report command may itself succeed while reporting a blocked capability, but it must be labelled as such and must never be consumed as a passing journey.

Record the brief/pattern revision actually used; do not relabel old evidence after the brief changes. All checks follow the coordinator's one reservation list across tax families and frontends. No duplicate full lanes or repeated aggregate checks for unchanged relevant inputs.

## Adoption checklist for current session leads

1. Read this pattern and the current family brief; report the exact revisions consumed.
2. Identify the one owner of shared acceptance execution plumbing and consume that implementation from both families.
3. Delegate bounded factual checks of assigned acceptance-driver surfaces to Luna Max: duplicated environment construction, unisolated settings/log/cache/keychain paths, raw failure payloads, hardcoded authority revisions, and false-success receipts/exit status. Consume the compact report and verify relevant findings with targeted reads; do not load the entire harness into lead context.
4. Make any required changes only within assigned ownership; do not repair another active session's files.
5. Verify the smallest relevant isolation/driver cases and report conformance gaps explicitly. This preflight does not reserve or run those checks on the implementation session's behalf.
