---
tags:
  - '#adr'
  - '#mcp-identity-linked-operation'
date: '2026-07-08'
modified: '2026-07-17'
body_hash: 'sha256:f6ac8dc5733330c02880941dd5c8e3e797a417f18f686edfd097e8164add1fd6'
related:
  - "[[2026-07-08-mcp-identity-linked-operation-research]]"
  - "[[2026-07-08-mcp-console-review-audit]]"
  - "[[2026-07-08-mcp-protocol-hardening-adr]]"
  - "[[2026-07-08-mcp-progressive-discovery-adr]]"
---

# `mcp-identity-linked-operation` adr: `bind every MCP operation to the confirmed active taxpayer identity` | (**status:** `accepted`)

## Problem Statement

The `aeat` CLI operates on a per-taxpayer profile — an active identity plus its
encrypted bucket. A tax filing MUST be tied to the correct identity: Erika would
not file a return while Erik is the active profile. The 2026-07-08 MCP console
review (audit `2026-07-08-mcp-console-review-audit`) found the console does not
enforce this. The core surface has no identity-ASSERTION tool: `overview status`
is core and carries the active-profile label, but its job is work-state, and the
command the docs and the golden-eval treat as the canonical identity check
(`config profile status`) is not in the core surface, so an agent must search for
it — it must already suspect it needs an identity check to discover the tool that
performs one. The live human-in-the-loop gate keys purely on mutability with zero
identity dimension. And the one identity signal a mutating result already carries
(the echoed `bucket_id`) is defeated by redaction, which collapses every profile's
UUID to the constant literal `<bucket-id>`, so a wrong-profile mutation is
indistinguishable in the response from a right-profile one. Identity confirmation
is scored only offline by a golden eval; nothing enforces it live.

This ADR decides how the console binds an operation to a confirmed identity. It is
the one genuinely new decision from the review — it adds a core tool, a new gate
dimension, and a core-envelope change — and so is a new ADR rather than
conformance debt against the two accepted MCP ADRs (which the companion
`mcp-hardening-conformance` plan closes without a new decision).

## Considerations

- **The identity state already exists; only its surfacing is missing.** The
  active-profile health assessment (`assess_active_profile_health`) already
  carries the active-profile label, status, missing-required facts, and a
  next-action; `config switch` already self-echoes the profile it switched to.
  The console can reuse these — no new CLI coupling, no new identity source.
- **The label, not the UUID, is the identity carrier.** Raw profile/bucket UUIDs
  are redacted to a constant placeholder by design (paste-safety for human CLI
  users); the human-chosen profile label is already clear-text on profile status.
  The identity an agent and a human reconcile is the label, so the label is what
  the console must surface — un-redacting the UUID is neither necessary nor
  desirable.
- **The gate must be an ordering discipline, not a data check.** The console
  cannot verify the agent CHOSE the right taxpayer — only the human can. What it
  can enforce is that an identity read HAPPENED before an identity-sensitive
  action, and that the active label is placed where a human tier sees it. This is
  the same fail-closed posture the project takes on under-declaration.
- **Gate invariance carries over.** Both prior MCP ADRs require that the direct
  call path and the `execute` meta-tool path run byte-identical gates; the
  identity gate must too.
- **The mutating-set definition depends on the risk table.** "Which calls are
  mutating" is exactly the declared per-command risk data the companion
  conformance plan lands (its risk table), so that table ships first and this
  gate consumes it rather than re-deriving mutability.

## Considered options

### I1 — Identity assertion surface

- *Rely on `overview status` (already core):* rejected as sufficient — it carries
  the label but is not marketed or shaped as an identity check, and it is not the
  command the golden-eval anchors on, so an agent does not reliably reach for it
  to confirm identity.
- **Chosen — a `whoami` always-on core read-only tool.** A console-native tool
  wrapping `assess_active_profile_health` returns the active-profile label,
  whether a tax id is present, readiness, and the next action; its description
  states its safety job ("call before any mutating command to confirm which
  taxpayer is active; call again after a profile switch"). The same identity
  block is added to the `harness.load` floor response, since session orientation
  is that tool's job. `whoami` joins the hand-built orientation core (14 → 15
  tools); it is a console tool like `search`/`execute`, not a manifest slice
  member. Identity is NOT stamped into every `search` result (noise); per-result
  identity is I3.

### I2 — Live identity gate

- *Advise only (echo the label, no block):* rejected — an advisory the agent may
  ignore does not prevent the wrong-profile filing the review found; the stakes
  are a cross-taxpayer data-integrity failure the project rules fail-closed.
- *Block every mutating call until re-confirmed each time:* rejected — needless
  friction; one identity read covers a session until the identity changes.
- **Chosen — block the first mutating call of a session, re-armed on any
  profile-changing verb, until an identity read has occurred.** The server
  refuses the first mutating call (mutating defined off the risk table) unless an
  identity read (`whoami` / `config profile status` / `overview status`) happened
  since session start or since the last profile-changing verb (`config switch`,
  the `config profile` mutations); the refusal is deterministic, instructive, and
  localized, so an agent recovers in exactly one read-only round-trip. It runs in
  the pre-tool-use layer identically on the direct and `execute` paths. The gate
  proves the identity read HAPPENED, not that the agent reconciled it — the
  residual is covered by the I4 echo and scored by the golden eval.
- **Implementation refinement — `harness.load` counts as an identity read.**
  Because "mutating" is defined off the risk table and the manifest carries
  per-family mutability, nearly every non-`overview` verb (including genuine
  reads such as `ledger view` / `config profile show`) classifies non-read-only,
  so a literal three-read set fires the gate on almost any first call. The
  identity-read set is therefore widened to include the `harness.load` floor
  tool, which — per I1 — now carries the active-profile identity block in its
  response: an agent that loaded the harness has demonstrably seen who is active,
  exactly the guarantee the gate exists to enforce. This sharply reduces friction
  on the near-universal first call while preserving safety, because a
  profile-changing verb still re-arms the gate (a post-switch mutation must
  re-confirm identity). The read set is thus `whoami` / `config profile status` /
  `overview status` / `harness.load`, keyed off tool identity, not a leaf-name
  heuristic.

### I3 — Per-operation identity carrier

- *Add `active_profile_label` to each mutating result model:* rejected — a
  per-command blast radius across many result models, and it re-fragments the
  surface `cli-notices-are-the-only-diagnostic-channel` unified onto one spine.
- **Chosen — one optional `active_profile` field on the shared envelope spine.**
  The human-label active profile (null before a profile exists) is added to the
  `SchemaEnvelope` spine and its stderr `ErrorEnvelope` sibling, populated at emit
  for profile-bound commands. One model, one conformance-test extension, zero
  per-command blast radius, and it is the shared-spine shape the notice-channel
  rule already mandates. UUID redaction is left untouched.

### I4 — Human-tier identity echo

- **Chosen — CONFIRM elicitations name the active profile label.** The
  confirmation prompt for a destructive or handoff verb names the active-profile
  label ("export the Modelo 130 draft for Erika"), so the human approving the
  action sees whose data it touches and can catch an Erik/Erika mismatch at the
  gate.

### I5 — UUID redaction posture (explicit non-choice)

- **Chosen — bucket and profile UUIDs stay redacted; the human label is the
  identity carrier.** Recorded as a deliberate non-change so a future reader does
  not "fix" the constant-placeholder echo by un-redacting the UUID — the label,
  already clear-text and human-meaningful, is the correct identity signal, and the
  redaction preserves paste-safety for human CLI users.

## Constraints

- **Depends on the risk table (companion conformance plan).** I2's "mutating
  call" definition consumes the declared per-command risk table that the
  `mcp-hardening-conformance` plan lands; that table ships first. Until it lands,
  this gate would fall back to the leaf-name classification it is meant to
  supersede, so the sequencing is a hard dependency, not a preference.
- **Safety rails carry over unchanged.** Never-live-submit, evidence-bytes-never-
  off-host, and secure-storage bind this ADR; the identity gate strengthens, never
  weakens, them. Secrets are never elicited (the identity read returns a label,
  not a credential).
- **Gate invariance is non-negotiable.** The identity gate must produce
  byte-identical refusals on the direct and `execute` paths, extending the
  existing conformance tests rather than weakening them.
- **The label is a non-secret.** The active-profile label on the envelope spine is
  the human-chosen profile name already shown clear-text by profile status; it is
  not sensitive financial data and carries no legal_refs concern.

## Implementation

High-level layering; the paired plan owns steps and sequencing.

- **Envelope spine (I3), first.** Add the optional `active_profile` label field to
  the shared `SchemaEnvelope` spine and the stderr `ErrorEnvelope`; populate it at
  emit for profile-bound commands; extend the shared-spine conformance test.
- **`whoami` tool (I1).** A console-native read-only core tool over the existing
  profile-health assessment, added to the hand-built orientation core and to the
  `harness.load` identity block.
- **Identity gate (I2) + echo (I4).** Per-session identity-read state in the
  pre-tool-use layer, re-armed on any profile-changing verb; an instructive
  localized refusal on the first un-confirmed mutating call, byte-identical on
  both call paths; CONFIRM elicitations name the active label.
- **Measurement.** The Erik/Erika profile-switch scenario becomes a scored
  live-harness scenario, run before and after as the acceptance gate.

## Rationale

Every ruling follows the review and reuses an existing surface rather than
inventing one. I1 gives the agent the identity-assertion tool the core surface
lacked, reusing the profile-health assessment so there is no new identity source.
I2 turns the offline-only identity check into a real pre-tool-use gate at the one
moment it matters — the first state change — with a fail-closed posture matched to
the cross-taxpayer stakes and a one-round-trip recovery that keeps the friction
proportionate. I3 places the identity carrier on the shared envelope spine, the
shape the notice-channel rule already mandates, avoiding a per-command blast
radius. I4 puts the label where the human tier catches a mismatch. I5 records the
redaction non-change so the label — not an un-redacted UUID — remains the identity
signal. The dependency on the conformance plan's risk table is honest: "which call
mutates" must be declared data, not the leaf-name heuristic this whole review is
retiring.

## Consequences

**Gains.** An agent can always answer "whose data am I about to touch" from an
always-on tool; a wrong-profile mutation is blocked at the first state change
until identity is confirmed; every envelope and every destructive-verb
confirmation names the active taxpayer, so an Erik/Erika mismatch is catchable by
the agent, by the human tier, and by the eval. The identity binding is uniform
across the direct and meta call paths.

**Honest difficulties.** The gate proves an identity read happened, not that the
agent reconciled it correctly — a determined mis-operation that reads identity and
then ignores it is still possible; the I4 echoes and the golden eval are the
compensating controls, not a proof. The gate adds one mandatory read-only
round-trip at session start and after each switch — proportionate, but real
latency. The envelope-spine field touches the one shared contract every command
emits, so its conformance test and the redaction boundary must both stay green.
The block depends on the risk table landing first; shipping this gate against the
leaf-name classification would inherit exactly the auto-approve hole the review
found, so the sequencing must hold.

**Pathways opened.** The per-session identity state generalises to other
session-scoped safety gates (e.g. a period-scoped or filing-year-scoped
confirmation); the envelope-spine active-profile field gives downstream tooling a
uniform identity anchor for audit and trajectory analysis.
