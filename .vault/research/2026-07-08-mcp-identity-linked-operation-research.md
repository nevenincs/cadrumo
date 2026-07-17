---
tags:
  - '#research'
  - '#mcp-identity-linked-operation'
date: '2026-07-08'
modified: '2026-07-17'
related:
  - '[[2026-07-08-mcp-console-review-audit]]'
  - '[[2026-07-08-mcp-identity-linked-operation-adr]]'
---

# `mcp-identity-linked-operation` research: `Identity-linking safety review of the MCP console`

A no-context reviewer drove the real `aeat-mcp` server to answer: how does an
agent know which taxpayer profile is active before an identity-sensitive call,
and is that safe? This document records the investigation that grounds the
`mcp-identity-linked-operation` ADR. The full finding is also persisted in the
`2026-07-08-mcp-console-review-audit`.

## Findings

### The identity state exists but is not surfaced where an agent needs it

The CLI is per-taxpayer-profile. `config profile status` returns the active
profile's human label in clear text; `overview status` (already in the MCP core
surface) carries `active_profile.label`; `config switch` self-echoes the profile
it switched to. The active-profile health assessment
(`assess_active_profile_health`) already carries the label, status, missing
required facts, and a next action. So the identity data is present — the gap is
that the core surface has no tool whose JOB is identity assertion, and the
canonical identity command (`config profile status`) is not in the core surface,
so an agent must search for it before it can confirm who is active.

### The live gate has no identity dimension

`confirmation_for_tool` (the pre-tool-use gate) keys purely on the command's
mutability classification; it has no notion of identity. Identity confirmation is
scored only offline by a golden-eval scenario, never enforced during a live
session.

### Redaction defeats the one identity echo a mutation already carries

Mutating commands echo a `bucket_id`, but redaction collapses raw profile/bucket
UUIDs to the CONSTANT literal placeholder (not a per-value hash) by default, so
every mutation against every profile echoes identical text. The human-chosen
label — already clear-text on profile status — is the only trustworthy identity
signal, and mutating results do not carry it.

### The Erik/Erika failure mode

A session with Erik active, told "now do Erika's Modelo 130", runs `modelo work
create`/`calculate` against Erik's bucket if the agent forgets `config switch`;
the response echoes the constant `bucket_id` placeholder, so nothing in the result
flags the mismatch, and no live gate pauses to confirm identity.

## Options weighed

- An identity-assertion tool vs relying on `overview status`: the latter carries
  the label but is not shaped or reached-for as an identity check.
- Advise vs block on the first mutation: an advisory the agent can ignore does not
  prevent the wrong-profile filing; the stakes are a cross-taxpayer data-integrity
  failure the project rules fail-closed.
- Per-result-model identity field vs the shared envelope spine: the spine avoids a
  per-command blast radius and matches the unified-diagnostic-channel discipline.
- Un-redacting the UUID vs surfacing the label: the label is the human-meaningful
  identity carrier and keeps paste-safety intact.

These options are resolved in the `mcp-identity-linked-operation` ADR (I1-I5).
