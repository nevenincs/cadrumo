---
tags:
  - '#research'
  - '#censal-sync-control'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:461a5fe6ea5212effa562c635d051eca5f4526835abb3b6f4ee618882aa090f7'
related:
  - '[[2026-07-25-censal-profile-autofill-adr]]'
  - '[[2026-08-08-sync-control-surface-adr]]'
---
# `censal-sync-control` research: `architecture`

Modelo 036 census synchronization currently has different consent semantics in
the CLI and TUI, no durable object representing what the operator reviewed, and
no typed lifecycle shared by authentication, acquisition, review, apply, status,
and busy presentation. The evidence favors an application-owned, persisted
census synchronization request projected by both frontends; the ADR must settle
its state machine, concurrency guard, per-field intent vocabulary, and which
older accepted census decisions it supersedes.

## Findings

### The TUI commits a pull that the CLI previews

The CLI fetches and reconciles the current AEAT read, but persists only inside
its `--apply` branch. The profile-manager action performs the same acquisition
and then unconditionally saves `apply_censal_read`, without a review or approval
transition. One capability therefore has two consent contracts at current HEAD
`07d63e7ac53fa8a4ea10628f9799ac00cc74fe26`.
`src/cadrumo/entrypoints/cli/_config/_censo_file.py:142`
`src/cadrumo/entrypoints/cli/_config/_censo_file.py:183`
`src/cadrumo/entrypoints/cli/_config/_manager_actions.py:153`
`src/cadrumo/entrypoints/cli/_config/_manager_actions.py:210`

### No durable review operand or per-field intent exists

`CensalReconciliation` carries only facts inferred as adopted and pairs inferred
as divergences. `apply_censal_read` recomputes that split against the current
profile and immediately delegates to the single `apply_cotejo` writer. The
complete remote observation, local baseline, suggested action, operator choice,
approval, and baseline fingerprint are not persisted together. A preview cannot
therefore be resumed or applied later as the exact reviewed input, and a second
CLI invocation re-reads AEAT instead of consuming the prior preview.
`src/cadrumo/application/user_profile/_censo_sync.py:186`
`src/cadrumo/application/user_profile/_censo_sync.py:275`
`src/cadrumo/application/user_profile/_censo_sync.py:380`
`src/cadrumo/application/user_profile/_cotejo_apply.py:246`

### Status and spinner observe presentation mechanics rather than sync state

The manager's outcome can carry only a message, optional rebuilt overview,
close signal, and disposition. AEAT progress is an optional callback carrying a
message and timeout; the TUI marshals it onto Textual's task. The loading
indicator is toggled by generic worker start and settlement, so it knows only
that a wrapper thread exists. Authentication approval, authenticated landing,
census navigation, parse, review readiness, and apply have no shared operation
identifier or typed stage. The initial Cl@ve countdown can consequently remain
visible after the internal auth state has advanced, while the spinner cannot say
which stage is active.
`src/cadrumo/adapters/inbound/tui/_manager_screen.py:81`
`src/cadrumo/adapters/inbound/tui/_manager_screen.py:729`
`src/cadrumo/adapters/inbound/tui/_manager_screen.py:854`
`src/cadrumo/adapters/inbound/tui/_manager_screen.py:865`
`src/cadrumo/core/_operator_progress.py:10`
`src/cadrumo/adapters/outbound/aeat/auth/_clave_movil_support.py:203`
`src/cadrumo/adapters/outbound/aeat/auth/_clave_movil.py:1015`

### Existing tests prove seams, not the real lifecycle

The manager progress test injects one synthetic progress message and waits; the
mounted census action test reaches an auth-field refusal. Neither drives the
production auth, browser, read, review, approval, apply, redraw, and spinner
sequence. Application reconciliation tests construct typed census results
directly. Missing coverage includes no-write-before-approval, per-field and
approve-all selection, stale-review refusal, every operation-stage transition,
and spinner termination on success, refusal, failure, and cancellation.
`src/cadrumo/adapters/inbound/tui/tests/test_manager_screen.py:360`
`src/cadrumo/adapters/inbound/tui/tests/test_manager_screen.py:448`
`src/cadrumo/application/user_profile/tests/test_censal_sync.py:1`

### Accepted decisions conflict and require explicit reconciliation

The May foundation amendment makes AEAT automatically authoritative and calls
for ACTIVE/SUPERSEDED snapshots plus refresh, show, compare, and apply. The July
25 autofill decision instead protects operator-declared fields, adopts blanks,
and persists disagreements for operator adjudication. The current code follows
the latter policy but retains a `CensoSyncService` whose documentation says
snapshot capture, compare, and apply were retired. A new implementation without
an explicit supersession ruling would deepen an already contradictory accepted
corpus.
`.vault/adr/2026-05-12-cli-workflow-redesign-modelo-036-037-foundation-adr.md:64`
`.vault/adr/2026-07-25-censal-profile-autofill-adr.md:228`
`src/cadrumo/application/user_profile/_censo_sync.py:412`

### The application-owned request is the only option that closes every defect

A modal bolted onto the current manager action is cheap but remains ephemeral,
frontend-owned, and vulnerable to review/apply time-of-check drift. Reusing the
existing compare-select TUI primitives improves presentation but still leaves
the frontend as synchronization authority unless an application aggregate owns
the reviewed data and transitions. The evidence therefore favors a persisted
request containing the immutable AEAT observation and provenance, local baseline
and fingerprint, typed per-field proposed and selected intent, approval facts,
and a lifecycle such as pulling, awaiting review, approved, applying, applied,
failed, and stale. Both CLI and the dedicated TUI would project that request;
final writes would still delegate to `apply_cotejo` rather than introduce a
parallel writer.

### Live validation found adjacent setup defects and then hit unrelated WIP

On 2026-08-11, isolated local roots were used and secret values were never
printed. The advertised non-interactive profile-create flow twice refused with
`REFUSED_PROFILE_SCHEMA_VALIDATION` because
`tax_residence.jurisdiction_scope` remained absent even when an explicit CCAA
was supplied. Canonical application registration succeeded. `auth configure`
then succeeded, while a new profile without a persisted Cl@ve route refused
`auth login` with `REFUSED_CLAVE_CREDENTIALS_INCOMPLETE`; provisioning
`app_request` closed that preflight gap. The final exact console retry could not
reach AEAT because unrelated shared-worktree IVA refactoring left
`M303RegimenSimplificadoCensoApplicability` imported but absent from the public
facade. No live census read or AEAT mutation was completed, and these attempts
must not be described as end-to-end proof.

### Not investigated

No production implementation, AEAT write, live completed device authentication,
or live TUI replay was performed. The exact persistence namespace, retention
policy, intent enum, optimistic-concurrency fingerprint, and supersession set
remain ADR questions.

## Sources

- `src/cadrumo/entrypoints/cli/_config/_censo_file.py:142`
- `src/cadrumo/entrypoints/cli/_config/_censo_file.py:183`
- `src/cadrumo/entrypoints/cli/_config/_manager_actions.py:153`
- `src/cadrumo/entrypoints/cli/_config/_manager_actions.py:210`
- `src/cadrumo/application/user_profile/_censo_sync.py:186`
- `src/cadrumo/application/user_profile/_censo_sync.py:275`
- `src/cadrumo/application/user_profile/_censo_sync.py:380`
- `src/cadrumo/application/user_profile/_censo_sync.py:412`
- `src/cadrumo/application/user_profile/_cotejo_apply.py:246`
- `src/cadrumo/adapters/inbound/tui/_manager_screen.py:81`
- `src/cadrumo/adapters/inbound/tui/_manager_screen.py:729`
- `src/cadrumo/adapters/inbound/tui/_manager_screen.py:854`
- `src/cadrumo/adapters/inbound/tui/_manager_screen.py:865`
- `src/cadrumo/core/_operator_progress.py:10`
- `src/cadrumo/adapters/outbound/aeat/auth/_clave_movil_support.py:203`
- `src/cadrumo/adapters/outbound/aeat/auth/_clave_movil.py:1015`
- `src/cadrumo/adapters/inbound/tui/tests/test_manager_screen.py:360`
- `src/cadrumo/adapters/inbound/tui/tests/test_manager_screen.py:448`
- `src/cadrumo/application/user_profile/tests/test_censal_sync.py:1`
- `.vault/adr/2026-05-12-cli-workflow-redesign-modelo-036-037-foundation-adr.md:64`
- `.vault/adr/2026-07-25-censal-profile-autofill-adr.md:228`
- commit `07d63e7ac53fa8a4ea10628f9799ac00cc74fe26`
- Live local-console attempt, 2026-08-11; no reusable secret-bearing transcript
  was persisted.
