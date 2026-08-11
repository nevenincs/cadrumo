---
tags:
  - '#research'
  - '#tui-architecture'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:2ddb13042f7b9aede4b6ce4ee3da2c10243c30611f5f6b24861ade5d1c890c22'
related:
  - "[[2026-08-11-censal-sync-control-architecture-research]]"
  - "[[2026-08-09-cli-action-envelope-hardening-adr]]"
  - "[[2026-08-08-sync-control-surface-adr]]"
  - "[[2026-06-10-cli-envelope-notice-standardisation-adr]]"
  - "[[2026-06-30-agent-harness-adr]]"
  - '[[2026-08-11-tui-interface-research]]'
---

# `tui-architecture` research: `Canonical operation envelope and supervisor API`

The TUI can present success, warning, refusal, and progress, but no
application-owned component supervises the lifecycle that produces them. The
census synchronization defect is therefore a worked symptom of an
application-wide architecture gap: every current and future TUI tool call must
otherwise reinvent execution, human interaction, cancellation, timeout,
cleanup, diagnostics, and settlement inside a frontend. The evidence favors a
typed application operation envelope plus supervisor API, projected separately
by the TUI, CLI, and MCP surfaces; the ADR must settle its ownership, state
axes, durability capabilities, cancellation guarantees, interaction protocol,
and migration gate.

## Findings

### The TUI has presentation contracts but no operation contract

`ManagerAction` binds a label to a raw synchronous callable, while
`ManagerActionOutcome` carries only message, overview, close-session, and a
presentation disposition. Textual worker identity and a generic busy flag are
then treated as operation state. There is no operation identity, typed request,
phase, approval, authoritative terminal receipt, retry or recovery reference,
resource ownership, or resumable snapshot.
`src/cadrumo/adapters/inbound/tui/_manager_screen.py:72`
`src/cadrumo/adapters/inbound/tui/_manager_screen.py:108`
`src/cadrumo/adapters/inbound/tui/_manager_screen.py:729`
`src/cadrumo/adapters/inbound/tui/_manager_screen.py:906`

Credential acquisition is a second, disconnected worker harness. Its outcome
is either a value or refusal prose, and its settlement handler recognizes only
Textual success and error. A cancelled attempt leaves `_attempt` populated and
the controls busy. The flow TUI is a third mechanism: a synchronous application
flow projection with review and checkpoints, but no external-operation runner.
The codebase therefore has no one lifecycle that all TUI operations enter.
`src/cadrumo/adapters/inbound/tui/_credential_screen.py:50`
`src/cadrumo/adapters/inbound/tui/_credential_screen.py:83`
`src/cadrumo/adapters/inbound/tui/_credential_screen.py:121`
`src/cadrumo/adapters/inbound/tui/_app.py:344`
`src/cadrumo/adapters/inbound/tui/_app.py:353`

### Cancellation cancels observation, not the running operation

Manager actions run opaque synchronous callables in Textual thread workers,
and live actions create private event loops with `asyncio.run`. Textual thread
worker cancellation cannot terminate the backing thread; cooperative
cancellation must be implemented by the callable. The callable receives no
cancellation scope or token, so cancellation cannot propagate into the inner
async task, browser, session, or child process. A wrapper may therefore become
cancelled while owned work continues, and the action can outlive the TUI. The
existing seam test documents that exact limitation.
`src/cadrumo/adapters/inbound/tui/_manager_screen.py:906`
`src/cadrumo/entrypoints/cli/_config/_manager_actions.py:200`
`src/cadrumo/entrypoints/cli/_config/_manager_actions.py:414`
`src/cadrumo/entrypoints/cli/_config/tests/test_manager_action_seam.py:349`
https://textual.textualize.io/guide/workers/

### The displayed timeout is only a countdown

`OperatorProgress` is localized presentation prose plus an optional duration.
The status bar pauses its countdown at zero but neither requests cancellation
nor changes the operation's terminal condition. Local Playwright timeouts do
not provide an aggregate deadline, heartbeat watchdog, cleanup deadline, or
escalation policy for a TUI operation.
`src/cadrumo/core/_operator_progress.py:10`
`src/cadrumo/adapters/inbound/tui/_status_bar.py:129`
`src/cadrumo/adapters/inbound/tui/_status_bar.py:157`

### The same defect covers every current manager operation

Field edits, authentication configuration, passphrase rotation, census pull,
filed-history pull, profile-bundle export, repeatable-row creation, Google
export, and logout all execute through presentation-owned callbacks. Census
performs an immediate profile commit; filed-history creates a private async
loop; Google export reaches from the CLI frontend into outbound Google and
private CLI helpers. These are independent effect shapes with the same missing
supervision boundary, so fixing only sync would leave the architecture unsafe
for the next operation.
`src/cadrumo/entrypoints/cli/_config/_manager_actions.py:134`
`src/cadrumo/entrypoints/cli/_config/_manager_actions.py:361`
`src/cadrumo/entrypoints/cli/_config/_manager_actions.py:636`
`src/cadrumo/entrypoints/cli/_config/_manager_actions.py:1366`
`src/cadrumo/entrypoints/cli/_config/_manager_actions.py:1488`
`src/cadrumo/entrypoints/cli/_config/_manager_actions.py:1566`

### Modelo 036 census pull fits the envelope only when acquisition and apply are split

The current TUI callback loads its local baseline, performs authenticated live
acquisition, reconciles, and saves immediately. The live door itself is already
cleanly layered: it authorizes a live read, acquires or reuses an authenticated
session, opens a separate browser/context/page, resolves AEAT's dispatched
origin, enforces read-only landing policy, captures and parses the census page,
and closes browser resources in `finally`. The envelope does not need to
abstract those adapters away; it needs to supervise their sequence, resource
scope, typed phases, and outcome.
`src/cadrumo/entrypoints/cli/_config/_manager_actions.py:198`
`src/cadrumo/entrypoints/cli/_config/_manager_actions.py:210`
`src/cadrumo/application/live/__init__.py:389`
`src/cadrumo/application/live/_session.py:27`
`src/cadrumo/adapters/outbound/aeat/sede/_censal_datos.py:575`
`src/cadrumo/adapters/outbound/aeat/sede/_censal_datos.py:622`

One operation ID can cover preflight, session probe/acquisition, external
Cl@ve-device wait, session verification, census navigation, landing validation,
capture, parse, proposal construction, local review, apply, and cleanup. Two
waits have different semantics: phone approval is `WAITING_FOR_EXTERNAL` and is
observed rather than answered by the app; local review is
`WAITING_FOR_INTERACTION` and consumes an exact `APPLY` or `REJECT` response.
The current one-message Cl@ve callback reports neither the post-auth landing nor
the later census phases.
`src/cadrumo/adapters/outbound/aeat/auth/_clave_movil_support.py:203`
`src/cadrumo/adapters/outbound/aeat/auth/_clave_movil_page_flow.py:516`

The domain proposal must retain the encrypted remote observation, local
baseline revision and digest, suggested field intents, and proposed-effect
digest. Raw HTML, session objects, NIF-bearing URLs, addresses, and cadastral
references cannot enter generic events or logs. Apply must consume that exact
proposal rather than recompute against an unboundedly stale baseline. The
irreversible local commit is initially non-cancellable; an apply or cleanup
failure must retain `UPDATED`, `PARTIAL`, or `UNKNOWN` effect truth.
`src/cadrumo/adapters/outbound/aeat/sede/_censal_datos.py:295`
`src/cadrumo/application/user_profile/_censo_sync.py:233`
`src/cadrumo/application/user_profile/_censo_sync.py:380`
`src/cadrumo/application/user_profile/_cotejo_apply.py:246`

### Previous-filing history pull fits the envelope as a recorded partial-effect operation

The history pull is a composed long-running operation, not one atomic sync. It
discovers the modelo/year scope, opens another authenticated register session,
walks each pair under a local timeout, captures declarations, persists evidence
incrementally, finalizes calculation observations, writes completed filed-sync
provenance, then separately acquires remote IVA-wallet and notification state.
Pair and declaration failures are absorbed and processing continues; wallet and
notification exceptions are flattened into stage-failure strings.
`src/cadrumo/application/live/_filed_data_capture.py:1806`
`src/cadrumo/application/live/_filed_data_capture.py:1848`
`src/cadrumo/application/live/_filed_data_capture.py:1864`
`src/cadrumo/application/live/_filed_data_capture.py:1909`
`src/cadrumo/application/live/_filed_data_capture.py:1925`

The operation therefore needs typed phases for scope discovery, register open,
pair walk, declaration capture, evidence persistence, filed finalization,
sync-provenance recording, IVA wallet, notifications, and result construction.
Live events need stage and unit progress with safe pair/declaration counters;
failures need operation, stage, pair, or declaration scope plus retryability.
The current manager collapses the result into prose and can render success when
filed pairs were refused because its warning disposition considers only later
`stage_failures`.
`src/cadrumo/application/live/_filed_data_capture.py:258`
`src/cadrumo/application/live/_filed_data_capture.py:803`
`src/cadrumo/application/live/_filed_data_capture.py:871`
`src/cadrumo/application/live/_filed_data_capture.py:887`
`src/cadrumo/entrypoints/cli/_config/_manager_actions.py:421`

`SyncRunRecord` is valid completed filed-surface provenance, but it carries no
outer operation identity, discovery/wallet/notification state, resource state,
cancellation, or partial effect across the composed stages. The canonical
operation should initially be `RECORDED`, not claim resumability, and declare
cancellation unsupported until phase checkpoints and idempotent recovery exist.
Its effect moves from `NONE` to `UPDATED` on the first local write and to
`PARTIAL` for refused units or failed later stages; interruption at an unsafe
write boundary may be `UNKNOWN`. Its terminal result must reference the child
filed sync record, captured evidence, wallet decision, and notification snapshot
under one operation ID.
`src/cadrumo/application/storage/sync_runs/_records.py:161`
`src/cadrumo/application/storage/sync_runs/_persist.py:51`

Review remains operation-specific. Refused versus genuinely empty pairs,
recapture divergences, blocked wallet decisions, evidence notices, truncation,
and denominator limitations all require a viewable result projection. If a
future policy requires approval before recapture or wallet mutation, that
executor must stage an exact proposal and enter `REVIEW_READY` before writing;
a modal shown after the current incremental upsert cannot retroactively provide
consent.

### A generic operation modal is a projection attachment, not the process owner

A reusable modal is the correct TUI form: it can be operation-agnostic and
render title, lifecycle, phase, spinner, live event/log stream, failure detail,
review payload, apply/reject, cancellation availability, and terminal receipt
from registered schemas. Its local state is limited to operation ID, event
cursor, latest envelope revision, and pending interaction ID.

Tying task or subprocess truth to modal mount state is unsafe. The current form
bridge blocks an action thread on a screen-owned event, and the manager refuses
quit while an action is pending because it cannot safely stop that work. A
screen dismissal cannot establish that auth locks, Playwright children,
browser/context/page resources, persistence, or cleanup have settled. Mounting
subscribes; unmounting detaches. Explicit cancel sends a supervisor request and
the modal remains capable of showing `CANCELLATION_REQUESTED` and `SETTLING`
until authoritative settlement.
`src/cadrumo/adapters/inbound/tui/_manager_screen.py:937`
`src/cadrumo/adapters/inbound/tui/_manager_screen.py:1000`

Close behavior is case-dependent operation policy projected by the same modal:
detach, request cancellation and await settlement, or refuse close during an
irreversible section. Even when an executor uses a contained subprocess, the
supervisor owns its handle, heartbeat, termination, reaping, and reconciliation;
the modal never kills it directly.

### The current package graph does not provide a canonical TUI boundary

The Textual implementation currently lives under
`cadrumo.adapters.inbound.tui`, but CLI command modules import its actions,
forms, outcome DTOs, status views, and flow frontend directly. Application flow
tests and shared test helpers also import it. In the other direction,
`_manager_actions.py` is a CLI module that owns application orchestration and
imports TUI types, so neither package is independently replaceable and a wizard
frontend restructuring campaign would collide with operation-harness work.
`src/cadrumo/entrypoints/cli/_config/_manager_actions.py:49`
`src/cadrumo/entrypoints/cli/_config/_manager_frontend.py:334`
`src/cadrumo/entrypoints/cli/_modelo_work_wizard_cli.py:51`
`src/cadrumo/entrypoints/cli/_modelo_amend_wizard_cli.py:53`
`src/cadrumo/application/flows/tests/test_frontend_parity.py:36`
`src/cadrumo/tests/manager_pilot.py:30`

The accepted hexagonal architecture fixes external invocation and composition
under `cadrumo.entrypoints`, alongside the existing CLI and MCP roots. The
cohesive TUI home is therefore `cadrumo.entrypoints.tui`, not a new top-level
package. Backend production and test packages must never import it; TUI-specific
tests and pilots live under the TUI entrypoint package. Packaging may name its
public `main` directly without creating a Python import edge from the CLI.
Within the TUI, operation presentation and wizard-flow presentation need
separate owned subpackages so the operation campaign and future interface
campaign do not share implementation files.
`pyproject.toml:125`
`.codex/rules/aeat-architecture-boundaries.md:31`

The parallel `2026-08-11-tui-interface-research` independently decomposes the
same flat adapter into TUI-local visual mechanics, profile tasks, ephemeral
secret entry, generic flow rendering, operation projection, and reserved Modelo
view/edit ownership. Reconciliation against the accepted hexagonal meaning of
`cadrumo.core` favors `entrypoints.tui.components` for the presentation-only
common layer. The two campaigns have a clean join when they share the
`entrypoints.tui` root, keep `operations` independent from `flows`, and move TUI
tests and pilot/replay tooling under that root.

### Input collection is not an approval protocol

The generic form validates a `dict[str, str]` and dismisses itself; the manager
then resumes the waiting callback immediately. The only generic confirmation
screen is tied to restarting a flow. There is no typed preview, review,
approval, rejection, response token, baseline version, or continuation. Future
tool calls therefore inherit execution-on-save unless each callback invents
its own policy. The related census research demonstrates the resulting consent
failure, but its per-field merge request is a domain payload rather than the
platform envelope.
`src/cadrumo/adapters/inbound/tui/_form_screen.py:467`
`src/cadrumo/adapters/inbound/tui/_manager_screen.py:937`
`src/cadrumo/adapters/inbound/tui/_confirm_screen.py:43`

### Diagnostics and completion provenance cannot supervise recovery

Known `CadrumoError` instances can be translated, but unexpected exceptions are
replaced by generic operator prose and retained only on ephemeral frontend
objects. There is no durable operation ID or redacted diagnostic reference.
Sync-run persistence records completion provenance, not lifecycle, so a crash
or detached task leaves no queued, running, cancellation-requested, timed-out,
interrupted, or orphaned state to reconcile on startup.
`src/cadrumo/adapters/inbound/tui/_manager_screen.py:817`
`src/cadrumo/adapters/inbound/tui/_credential_screen.py:85`
`src/cadrumo/application/storage/sync_runs/_records.py:161`

### The CLI schema envelope is not the missing application envelope

`SchemaEnvelope` explicitly defines a command wire contract rather than a
dispatcher, and CLI output schemas are presentation projections over
authoritative application or domain results. Reusing it internally would leak
command paths, active-profile labels, terminal stdout semantics, and CLI action
resolution into the TUI. MCP intentionally consumes that CLI wire surface and
separately owns transport timeouts and process-tree termination; it is not the
application lifecycle precedent.
`src/cadrumo/core/json_contract.py:385`
`src/cadrumo/entrypoints/cli/_modelo_payloads.py:1`
`src/cadrumo/entrypoints/mcp/_inprocess.py:1`
`src/cadrumo/entrypoints/mcp/_call_runtime.py:67`

The accepted action-envelope decision already places policy and stable action
identity in application/domain code while treating CLI, MCP, TUI, locales, and
help as consumers. A TUI operation contract should compose those action
references and verdicts, not create another action catalogue. The older CLI
envelope and agent-harness decisions remain correct for terminal and agent
surfaces and must not be silently generalized into an internal bus.
`.vault/adr/2026-08-09-cli-action-envelope-hardening-adr.md:27`
`.vault/adr/2026-06-10-cli-envelope-notice-standardisation-adr.md:19`
`.vault/adr/2026-06-30-agent-harness-adr.md:18`

### Application-owned supervision is the only option that closes the class

Expanding `ManagerActionOutcome` is locally cheap but leaves lifecycle and
policy in Textual. Sharing events while retaining raw services improves status
reporting but still leaves concurrency, cancellation, interaction, deadlines,
and resource cleanup unowned. Reusing `SchemaEnvelope` imports a terminal wire
contract into the application. The evidence instead favors an
application-owned supervisor with a typed invocation and operation ID;
independent lifecycle, terminal-condition, and effect axes; structured phase
events; start, observe, await, respond, and cancel operations; owned async and
process resources; redacted diagnostics; and explicit per-operation durability,
approval, idempotency, baseline, and cancellation capabilities.

Future extension requires more than a snapshot API. Long-running asynchronous
operations need an ordered, cursor-based stream of typed phase, progress, log,
interaction, effect, and terminal events so a frontend may detach and resume
without losing the operation's history. Human-readable logs and live feedback
must be projections of structured, redacted records with severity, timestamp,
safe facts, and diagnostic correlation; they cannot become lifecycle authority.
Reviewable operations also need a generic continuation through which a produced
proposal or outcome can wait for a typed apply or reject response before any
governed effect occurs. Spinner visibility must derive from the authoritative
executing lifecycle and settling state, never from a frontend worker or event
stream connection.

The TUI would project that state into native controls, forms, status, and
progress. CLI would continue projecting application results into
`OutputSchema`, `SchemaEnvelope`, text, and exit codes; MCP may continue its
CLI-backed contract. Localized prose, CLI paths, spinner state, Textual worker
identities, and secret material do not belong in the application envelope.

### Existing application precedents are substrates, not a supervisor

Configuration reset and bundle publication already model operation-specific
identities, phases, timestamps, snapshots, and prepared/completed states. The
shared journal repository supplies atomic persistence while explicitly owning
no orchestration. These can inform the generic invariants without forcing every
ephemeral read to persist or coercing all domain workflows into one global
state machine.
`src/cadrumo/application/_config_reset_models.py:26`
`src/cadrumo/application/_config_reset_models.py:193`
`src/cadrumo/application/user_profile/_bundle_export_operation.py:92`
`src/cadrumo/application/_journal_repository.py:1`

### Verification currently proves rendering seams, not lifecycle ownership

Thirty-nine TUI integration tests and four unit-marked status-bar tests passed
on 2026-08-11. They cover rendering, synthetic loop ownership, refusal
handling, and form handoff. The production seam deliberately substitutes a
synthetic `asyncio.run` callback rather than start a live browser, and progress
coverage emits synthetic prose. No test propagates real cancellation, enforces
an aggregate timeout, awaits cleanup, reaps a process, reconciles an orphan,
binds approval to an exact baseline, or executes an authenticated
TUI-to-browser lifecycle.
`src/cadrumo/entrypoints/cli/_config/tests/test_manager_action_seam.py:166`
`src/cadrumo/adapters/inbound/tui/tests/test_manager_screen.py:364`

### The ADR must settle the conformance boundary

The candidate contract needs three independent axes: lifecycle such as queued,
running, cancellation requested, and terminal; terminal condition such as
succeeded, refused, failed, cancelled, timed out, and interrupted; and effect
such as none, updated, and partial. It must also decide which operation classes
require a durable journal, how cancellation capability and irreversible
sections are declared, how typed operator-interaction continuations bind to an
exact request, how cleanup gates terminal settlement, and how every future TUI
tool call is prevented from bypassing the supervisor. It must additionally
settle ordered live-event and log cursors, redaction and retention policy,
detach/reconnect semantics, backpressure, and how a reviewable asynchronous
outcome enters an exact apply/reject continuation without conflating a proposed
result with a terminal receipt.

### Not investigated

No authenticated AEAT/browser operation or live cancellation was executed in
this read-only architecture review. The passing tests do not prove production
process reaping or cleanup. No production implementation was changed. Current
HEAD was `07d63e7ac53fa8a4ea10628f9799ac00cc74fe26`; the shared worktree also
contained unrelated in-flight sync-run changes, which were preserved.

## Sources

- `src/cadrumo/adapters/inbound/tui/_manager_screen.py:72`
- `src/cadrumo/adapters/inbound/tui/_manager_screen.py:108`
- `src/cadrumo/adapters/inbound/tui/_manager_screen.py:729`
- `src/cadrumo/adapters/inbound/tui/_manager_screen.py:817`
- `src/cadrumo/adapters/inbound/tui/_manager_screen.py:906`
- `src/cadrumo/adapters/inbound/tui/_manager_screen.py:937`
- `src/cadrumo/adapters/inbound/tui/_credential_screen.py:50`
- `src/cadrumo/adapters/inbound/tui/_credential_screen.py:83`
- `src/cadrumo/adapters/inbound/tui/_credential_screen.py:85`
- `src/cadrumo/adapters/inbound/tui/_credential_screen.py:121`
- `src/cadrumo/adapters/inbound/tui/_app.py:344`
- `src/cadrumo/adapters/inbound/tui/_app.py:353`
- `src/cadrumo/adapters/inbound/tui/_status_bar.py:129`
- `src/cadrumo/adapters/inbound/tui/_status_bar.py:157`
- `src/cadrumo/adapters/inbound/tui/_form_screen.py:467`
- `src/cadrumo/adapters/inbound/tui/_confirm_screen.py:43`
- `src/cadrumo/core/_operator_progress.py:10`
- `src/cadrumo/core/json_contract.py:385`
- `src/cadrumo/entrypoints/cli/_modelo_payloads.py:1`
- `src/cadrumo/entrypoints/cli/_config/_manager_actions.py:134`
- `src/cadrumo/entrypoints/cli/_config/_manager_actions.py:200`
- `src/cadrumo/entrypoints/cli/_config/_manager_actions.py:361`
- `src/cadrumo/entrypoints/cli/_config/_manager_actions.py:414`
- `src/cadrumo/entrypoints/cli/_config/_manager_actions.py:636`
- `src/cadrumo/entrypoints/cli/_config/_manager_actions.py:1366`
- `src/cadrumo/entrypoints/cli/_config/_manager_actions.py:1488`
- `src/cadrumo/entrypoints/cli/_config/_manager_actions.py:1566`
- `src/cadrumo/application/live/__init__.py:389`
- `src/cadrumo/application/live/_session.py:27`
- `src/cadrumo/adapters/outbound/aeat/sede/_censal_datos.py:295`
- `src/cadrumo/adapters/outbound/aeat/sede/_censal_datos.py:575`
- `src/cadrumo/adapters/outbound/aeat/sede/_censal_datos.py:622`
- `src/cadrumo/adapters/outbound/aeat/auth/_clave_movil_support.py:203`
- `src/cadrumo/adapters/outbound/aeat/auth/_clave_movil_page_flow.py:516`
- `src/cadrumo/application/user_profile/_censo_sync.py:233`
- `src/cadrumo/application/user_profile/_censo_sync.py:380`
- `src/cadrumo/application/user_profile/_cotejo_apply.py:246`
- `src/cadrumo/application/live/_filed_data_capture.py:258`
- `src/cadrumo/application/live/_filed_data_capture.py:803`
- `src/cadrumo/application/live/_filed_data_capture.py:871`
- `src/cadrumo/application/live/_filed_data_capture.py:887`
- `src/cadrumo/application/live/_filed_data_capture.py:1806`
- `src/cadrumo/application/live/_filed_data_capture.py:1848`
- `src/cadrumo/application/live/_filed_data_capture.py:1864`
- `src/cadrumo/application/live/_filed_data_capture.py:1909`
- `src/cadrumo/application/live/_filed_data_capture.py:1925`
- `src/cadrumo/application/storage/sync_runs/_records.py:161`
- `src/cadrumo/application/storage/sync_runs/_persist.py:51`
- `src/cadrumo/adapters/inbound/tui/_manager_screen.py:1000`
- `src/cadrumo/entrypoints/cli/_config/_manager_actions.py:49`
- `src/cadrumo/entrypoints/cli/_config/_manager_frontend.py:334`
- `src/cadrumo/entrypoints/cli/_modelo_work_wizard_cli.py:51`
- `src/cadrumo/entrypoints/cli/_modelo_amend_wizard_cli.py:53`
- `src/cadrumo/application/flows/tests/test_frontend_parity.py:36`
- `src/cadrumo/tests/manager_pilot.py:30`
- `pyproject.toml:125`
- `.codex/rules/aeat-architecture-boundaries.md:31`
- `src/cadrumo/entrypoints/cli/_config/tests/test_manager_action_seam.py:166`
- `src/cadrumo/entrypoints/cli/_config/tests/test_manager_action_seam.py:349`
- `src/cadrumo/adapters/inbound/tui/tests/test_manager_screen.py:364`
- `src/cadrumo/application/storage/sync_runs/_records.py:161`
- `src/cadrumo/application/_config_reset_models.py:26`
- `src/cadrumo/application/_config_reset_models.py:193`
- `src/cadrumo/application/user_profile/_bundle_export_operation.py:92`
- `src/cadrumo/application/_journal_repository.py:1`
- `src/cadrumo/entrypoints/mcp/_inprocess.py:1`
- `src/cadrumo/entrypoints/mcp/_call_runtime.py:67`
- `.vault/adr/2026-08-09-cli-action-envelope-hardening-adr.md:27`
- `.vault/adr/2026-06-10-cli-envelope-notice-standardisation-adr.md:19`
- `.vault/adr/2026-06-30-agent-harness-adr.md:18`
- commit `07d63e7ac53fa8a4ea10628f9799ac00cc74fe26`
- https://textual.textualize.io/guide/workers/
