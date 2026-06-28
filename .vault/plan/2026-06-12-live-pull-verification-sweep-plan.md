---
tags:
  - '#plan'
  - '#live-pull-verification-sweep'
date: '2026-06-12'
modified: '2026-06-13'
tier: L4
related:
  - '[[2026-06-05-live-censo-calendar-reconciliation-plan]]'
  - '[[2026-06-10-live-justificante-reconcile-plan]]'
  - '[[2026-04-27-live-submit-permanently-forbidden-plan]]'
  - '[[2026-04-27-live-submit-permanently-forbidden-adr]]'
  - '[[2026-05-26-no-synthetic-sede-live-surfaces-adr]]'
  - '[[2026-05-26-no-synthetic-sede-live-surfaces-research]]'
  - '[[2026-04-27-live-submit-permanently-forbidden-research]]'
  - '[[2026-06-05-live-auth-decomposition-research]]'
---


# `live-pull-verification-sweep` `authenticated pull-only live verification sweep` plan

## Epic intent

Deliver the authenticated pull-only live verification sweep for the AEAT application: every production live CLI command and backend live facade must be inventory-owned, pull-only, real-behavior tested, and manually exercised against authenticated AEAT where legally safe, with external blockers recorded as open work instead of completion. Project-management association: this is the live-pull verification umbrella for the active chore-476 restructure execution board and coordinates the existing live-censo-calendar-reconciliation, live-justificante-reconcile, live-submit-permanently-forbidden, and no-synthetic-sede-live-surfaces workstreams. Timeline: immediate post-terminology closeout through calculation/backend foundations; backend, CLI, storage, and QA agents execute one Step at a time with exec records and code-review gates.

## Wave `W01` - surface inventory and pull-only safety contract

Inventory every AEAT live surface first, classify each one by direction, and make the pull-only contract mechanically enforceable before any authenticated exercise is trusted.

### Phase `W01.P01` - live surface inventory

Produce a complete map of live CLI commands, backend facades, adapters, tests, and existing vault workstreams so later waves cannot miss a surface.

- [x] `W01.P01.S01` - Inventory every production live CLI command and backend live facade, including filed declarations, censo, expedientes, notifications, justificantes, IVA wallet, Borrador/Renta Web, portal opens, and verify commands; `src/aeat/entrypoints/cli src/aeat/application/live src/aeat/adapters/outbound/aeat .vault/audit`.
- [x] `W01.P01.S02` - Classify every inventoried surface as authenticated pull, local projection, local verification, or prohibited remote mutation, and record owners plus required manual evidence; `.vault/exec/2026-06-12-live-pull-verification-sweep`.
- [x] `W01.P01.S03` - Cross-link open predecessor gaps from live censo calendar, live justificante reconcile, live submit excision, and no synthetic sede surfaces into this umbrella without marking them complete; `.vault/plan .vault/index`.

### Phase `W01.P02` - pull-only safety gates

Turn the standing mandate into tests and code-review checks: AEAT interaction may pull authenticated information, but must never submit, mutate, notify, push, or treat local projection as AEAT state.

- [x] `W01.P02.S04` - Prove every live read routes through the central live-read access gate and every live write route permanently refuses before transport is constructed; `src/aeat/core/access_gate src/aeat/adapters/outbound/aeat/auth src/aeat/tests`.
- [x] `W01.P02.S05` - Audit remote-operation registry policy so only read-shaped AEAT operations are allowed and all write-shaped operations fail closed with typed diagnostics; `src/aeat/domain/calculations/registry/_remote_state_guard.py src/aeat/domain/calculations/registry/tests`.
- [x] `W01.P02.S06` - Add or refresh static guards that reject reintroduced submit, push, live-write, mutation, and synthetic-Sede shortcuts in production live surfaces; `src/aeat/entrypoints/cli/tests src/aeat/adapters/outbound/aeat/tests src/aeat/application/live/tests`.
- [x] `W01.P02.S07` - Retire or reword any operator-facing remote-state vocabulary that implies bidirectional sync, while preserving read-only pull/capture implementation semantics; `src/aeat/entrypoints/cli/_app_live.py src/aeat/application/live src/aeat/locales`.

## Wave `W02` - backend authenticated pull proof

Make every backend live-read facade meaningful and testable before CLI acceptance: authentication, parsing, secure persistence, projection, and typed failure outcomes must be exercised with real AEAT responses or recorded as live external blockers.

### Phase `W02.P03` - authentication and session substrate

Prove the live authentication substrate can create, persist, resume, and clean up authenticated sessions without enabling remote mutation.

- [x] `W02.P03.S08` - Run authenticated Clave Movil or certificate session acquisition with the operator present, capture exact success or external blocker, and verify storage-state persistence remains encrypted; `src/aeat/adapters/outbound/aeat/auth .vault/exec/2026-06-12-live-pull-verification-sweep`.
- [x] `W02.P03.S09` - Run the focused live auth pytest lane under explicit opt-in and prove skips are either absent or recorded as open blockers for acceptance; `src/aeat/adapters/outbound/aeat/auth/tests src/aeat/tests/live_gate.py`.

### Phase `W02.P04` - backend pull facades

Exercise each backend facade through the real implementation path, persisting only authorised local evidence and refusing ambiguous or synthetic data.

- [ ] `W02.P04.S10` - Prove censo pull and profile reconciliation fetch authenticated Modelo 036 or censo information and derive taxpayer facts without inventing missing obligations; `src/aeat/application/live/_censo.py src/aeat/application/user_profile/_censo_sync.py src/aeat/adapters/outbound/aeat/sede/_censo_live.py`.
- [ ] `W02.P04.S11` - Prove filed-declaration list, single pull, bulk pull, and source pull fetch authenticated AEAT register data and persist only stamped official evidence; `src/aeat/application/live/_filed_data.py src/aeat/application/live/_filed_data_capture.py src/aeat/application/live/_filed_observation_persistence.py`.
- [ ] `W02.P04.S12` - Prove expedientes pull fetches authenticated expediente rows with typed empty, timeout, and portal-drift outcomes; `src/aeat/application/live/_expedientes.py src/aeat/adapters/outbound/aeat/sede`.
- [ ] `W02.P04.S13` - Prove notifications pull fetches authenticated notification rows with read-only parsing and no acknowledgement or mutation path; `src/aeat/application/live src/aeat/adapters/outbound/aeat/sede src/aeat/entrypoints/cli/_app_live_notifications_cli.py`.
- [ ] `W02.P04.S14` - Prove justificante pull and reconcile fetch the filed-period receipt, persist the official artefact, and refuse mismatched or unstamped evidence; `src/aeat/application/live/_justificante.py src/aeat/entrypoints/cli/_app_live_justificante_cli.py`.
- [ ] `W02.P04.S15` - Prove IVA wallet and IVA remote acquisition are pull-only captures over filed history and wallet evidence, with no remote-state return or push semantics; `src/aeat/application/live/_iva_remote_state.py src/aeat/application/live/_iva_remote_state_outcomes.py src/aeat/entrypoints/cli/_app_live.py`.
- [ ] `W02.P04.S16` - Prove Borrador/Renta Web and portal-open live surfaces are safe read or navigation probes, never submission or form mutation flows; `src/aeat/application/live/_borrador_100.py src/aeat/entrypoints/cli/_app_live_borrador_cli.py src/aeat/entrypoints/cli/_app_live_portals_cli.py src/aeat/adapters/outbound/aeat/sede/tests`.

## Wave `W03` - CLI and manual authenticated exercises

After backend proof exists, exercise every operator-facing command with the same authenticated pull-only contract and persist manual evidence that a human can reproduce.

### Phase `W03.P05` - CLI command coverage

Every live command must have conformance tests, useful JSON/text output, typed failure outcomes, and no path that reports success without backend evidence.

- [x] `W03.P05.S17` - Verify the live command tree exposes only allowed pull, list, view, verify, and portal-read commands; `bulk filed and expedientes acquisition must live under `pull` options only, with no submit, push, sync-write, or pull-all aliases; `src/aeat/entrypoints/cli/_app_live.py src/aeat/entrypoints/cli/tests/test_live_read_subgroups.py src/aeat/entrypoints/cli/tests/test_registry_cli.py`.
- [ ] `W03.P05.S18` - Exercise filed CLI commands for list, pull, and pull-sources with JSON and text output, proving backend evidence is required before success and that `pull` is the only acquisition verb (`pull-all` remains absent); `src/aeat/entrypoints/cli/_app_live.py src/aeat/entrypoints/cli/tests`.
- [ ] `W03.P05.S19` - Exercise censo CLI commands for pull, show, compare, apply, and calendar projection, proving authenticated Modelo 036 facts drive obligations and typed `core.Period` identities connect those obligations to filed/justificante evidence; `src/aeat/entrypoints/cli/_config/_profile_censo.py src/aeat/entrypoints/cli/tests/test_profile_censo_verbs.py src/aeat/entrypoints/cli/_overview.py`.
- [ ] `W03.P05.S20` - Exercise expedientes CLI commands with authenticated results, typed empty-state output, and no local-only success masquerading as AEAT evidence; `src/aeat/entrypoints/cli/_app_live_expedientes_cli.py src/aeat/entrypoints/cli/tests`.
- [ ] `W03.P05.S21` - Exercise notifications CLI commands with authenticated results and prove no acknowledgement, dismissal, or remote mutation is reachable; `src/aeat/entrypoints/cli/_app_live_notifications_cli.py src/aeat/entrypoints/cli/tests/test_live_notifications_verbs.py`.
- [ ] `W03.P05.S22` - Exercise justificante CLI commands for pull, list, view, and reconcile-from-persisted evidence; `src/aeat/entrypoints/cli/_app_live_justificante_cli.py src/aeat/entrypoints/cli/tests/test_live_justificante_verbs.py`.
- [ ] `W03.P05.S23` - Exercise IVA wallet CLI commands after any remote-state wording correction and prove the outputs report pull-only capture status; `src/aeat/entrypoints/cli/_app_live.py src/aeat/entrypoints/cli/tests`.
- [ ] `W03.P05.S24` - Exercise verify and portal CLI commands as safe read/navigation probes with explicit refusal for anything write-shaped; `src/aeat/entrypoints/cli/_app_live_verify_cli.py src/aeat/entrypoints/cli/_app_live_portals_cli.py src/aeat/entrypoints/cli/tests/test_live_portals_verbs.py`.

Tracking update 2026-06-13: the active CLI verb-drift watch is `pull` versus
`pull-all`. Bulk filed and expedientes acquisition remains valid only as
options on `pull`; no production command, help surface, exec record, or runbook
may ask the operator to use `pull-all`. The focused guard is the registry CLI
help/conformance lane plus the filed rendering lane, and live authentication
must exercise `aeat app live filed pull`, `aeat app live filed pull-sources`,
and `aeat app live expedientes pull` only.

### Phase `W03.P06` - manual live evidence runbook

Manual acceptance requires authenticated evidence captured in exec records, with secret handling and redaction explicit enough for review.

- [ ] `W03.P06.S25` - Author the authenticated live exercise runbook as an exec template covering operator auth prompts, redaction, command order, expected evidence, and blocker recording; `.vault/exec/2026-06-12-live-pull-verification-sweep`.
- [ ] `W03.P06.S26` - Run the manual authenticated sweep with the operator present and create one exec record per completed command group; `.vault/exec/2026-06-12-live-pull-verification-sweep`.
- [ ] `W03.P06.S27` - Project live-backed censo, filed, expedientes, notifications, justificante, and IVA evidence into overview or registry views and verify the user-visible calendar distinguishes local ready-to-file calculations from AEAT-submitted filings with justificante checks; `src/aeat/application/overview src/aeat/entrypoints/cli/_overview.py src/aeat/entrypoints/cli/registry.py`.

## Wave `W04` - green gates and closeout

Close only after live lanes, manual evidence, local regression gates, code review, and vault checks agree; otherwise leave exact blockers open for the next workstream.

### Phase `W04.P07` - live and local test gates

Acceptance requires opted-in live tests plus focused offline tests over every touched surface, without weakening skips or expectations to get green.

- [ ] `W04.P07.S28` - Run the curated AEAT live pytest lane under explicit opt-in and record pass, skip, fail, and external-auth blocker counts without treating skips as green acceptance; `src/aeat/adapters/outbound/aeat src/aeat/application/live src/aeat/entrypoints/cli/tests .vault/exec/2026-06-12-live-pull-verification-sweep`.
- [x] `W04.P07.S29` - Run focused unit and integration tests for live backends, CLI payloads, overview projection, registry filed-state verification, and access gates; `src/aeat/application/live src/aeat/entrypoints/cli/tests src/aeat/application/overview src/aeat/domain/calculations/registry src/aeat/core/access_gate`.
- [ ] `W04.P07.S30` - Run lint, typing, locale parity, command conformance, and docs/API scaffold checks for every touched live surface; `src/aeat docs dev/docs src/aeat/locales`.

### Phase `W04.P08` - review and plan closure

Make closure auditable: every checked row must have exec evidence, live blockers must remain open, and the next calculation/backend brief must inherit unresolved facts.

- [ ] `W04.P08.S31` - Run code review over the live pull sweep changes and persist findings or no-findings audit before any plan row is checked; `.vault/audit src/aeat`.
- [ ] `W04.P08.S32` - Run feature-scoped vault checks and rebuild the live-pull-verification-sweep feature index; `.vault/index .vault/plan .vault/exec .vault/audit`.
- [ ] `W04.P08.S33` - Write the closeout audit listing satisfied rows, real remaining work, touched files, tests and live manual exercises run, and whether the plan can close; `.vault/audit/2026-06-12-live-pull-verification-sweep-closeout-audit.md`.

## Description

This umbrella plan scopes the remaining acceptance work after the terminology
search closeout exposed the broader live-verification gap. It does not reopen
completed implementation rows and it does not mark predecessor gaps complete.
It exists to make the next workstream explicit: every AEAT-facing live surface
must be inventoried, classified, exercised through its backend implementation,
exercised through its CLI command, and manually run with authenticated operator
participation where AEAT allows read-only access.

The governing invariant is pull only. AEAT interaction may fetch, list, view,
verify, capture, or project authenticated information. It must not submit,
push, acknowledge, dismiss, mutate, notify, synchronize back to AEAT, or let a
local projection masquerade as AEAT remote state. Existing names such as
`remote_state` are treated as suspect operator vocabulary until reviewed:
their implementation may remain if it is a read-only capture, but user-facing
commands and payloads must not imply bidirectional sync or a remote-state
return path.

The plan deliberately separates backend proof from CLI proof. A CLI command is
not meaningful until its application facade has real behavior, typed failure
outcomes, and authenticated evidence or an explicit external blocker. A backend
facade is not acceptable until at least one CLI command exercises it in text
and JSON output with realistic operator ergonomics. Manual authenticated
exercise is a first-class acceptance gate, not an optional testimonial.

## Parallelization

W01 is strictly first. No authenticated exercise should be trusted until the
surface inventory and pull-only safety gates are complete enough to identify
what is being tested and what is permanently prohibited.

Within W02, P03 authentication substrate work precedes the live backend facade
proofs in P04. The P04 backend rows may then parallelize by surface when they
do not touch the same modules: censo, filed declarations, expedientes,
notifications, justificantes, IVA wallet, and Borrador/Renta Web can be owned
separately, but any shared auth, storage, access-gate, locale, or CLI payload
edit must be serialized.

W03 depends on W02. CLI command coverage should follow the matching backend
row, not run ahead of it. The manual runbook in P06 can be drafted while P05 is
landing, but the authenticated sweep row cannot close until every command group
being claimed has backend and CLI evidence.

W04 is last. Test-gate rows may run in parallel once the touched file set is
stable, but review, vault checks, index rebuild, and closeout remain ordered:
code review before checked rows, vault checks before close audit, close audit
only after exec evidence exists for every claimed completion.

## Verification

The plan is complete only when every Step is checked and each checked Step has
a matching exec record or a close audit explicitly records why it remains a
deferred carry-forward. The project-management association named in the Epic
intent must also report this umbrella closed.

Mission success criteria:

1. The live surface inventory names every production AEAT live CLI command,
   backend facade, adapter, and live test lane, with no catch-all row standing
   in for unknown surfaces.
2. Static and behavioral gates prove AEAT remote mutation remains impossible:
   no submit, push, sync-write, acknowledgement, dismissal, or write-shaped
   command can reach transport.
3. `remote_state` or similar vocabulary is either retired from operator-facing
   surfaces or proven to mean read-only pull/capture with no bidirectional
   semantics.
4. Authentication is manually exercised with the operator present and recorded
   as success or as an external blocker. A blocker keeps the relevant Step
   open.
5. Each backend live facade has focused real-behavior tests and either
   authenticated live evidence or an explicit, reproducible live blocker.
6. Each CLI command group has text and JSON output exercised against the real
   backend path and cannot report local-only success as AEAT evidence.
7. The curated `aeat_live` lane runs under explicit opt-in. Skips and external
   auth blockers are counted and do not count as green acceptance.
8. Focused unit, integration, lint, typing, locale, command-conformance,
   docs/API scaffold, code-review, vault-check, and feature-index gates are
   clean for the touched live surfaces.
