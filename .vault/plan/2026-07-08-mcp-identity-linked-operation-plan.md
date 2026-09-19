---
tags:
  - '#plan'
  - '#mcp-identity-linked-operation'
date: '2026-07-08'
modified: '2026-07-17'
body_hash: 'sha256:0336d6f271cd7c4c998b444be3dca9ed3c5691d207e0375b6797789834fac2e6'
tier: L2
related:
  - '[[2026-07-08-mcp-identity-linked-operation-adr]]'
  - '[[2026-07-08-mcp-console-review-audit]]'
  - '[[2026-07-08-mcp-identity-linked-operation-research]]'
---

# `mcp-identity-linked-operation` plan

### Phase `P01` - Envelope-spine active-profile field

Add the optional active_profile human-label field to the shared SchemaEnvelope spine and its stderr ErrorEnvelope sibling, populated at emit for profile-bound commands, so every response carries the identity anchor without a per-command blast radius (ADR I3).

- [x] `P01.S01` - Add the optional active_profile label field to the shared SchemaEnvelope spine and the stderr ErrorEnvelope sibling, defaulting null before a profile exists; `src/aeat/core/json_contract.py`.
- [x] `P01.S02` - Populate active_profile at emit for profile-bound commands from the active-profile resolution, leaving the redacted bucket/profile UUIDs untouched; `src/aeat/entrypoints/cli/_common.py`.
- [x] `P01.S03` - Extend the shared-spine conformance test so the success and error envelopes both carry active_profile and a profile-bound command populates it; `src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py`.

### Phase `P02` - whoami core tool

Add a whoami always-on core read-only tool over the existing profile-health assessment and put the same identity block in the harness floor, giving an agent an always-present identity-assertion tool (ADR I1).

- [x] `P02.S04` - Add the whoami console tool over assess_active_profile_health returning the active-profile label, tax_id_present, readiness, and next_action, with a description stating its identity-safety job; `src/aeat/entrypoints/mcp/_harness_tools.py`.
- [x] `P02.S05` - Advertise whoami in the hand-built orientation core (15 tools) and add the same identity block to the harness floor payload; `src/aeat/entrypoints/mcp/_server.py`.
- [x] `P02.S06` - Add whoami tests: it is always advertised, returns the active label, and is never persona-scoped away; `src/aeat/entrypoints/mcp/tests/test_harness_delivery.py`.

### Phase `P03` - Live identity gate and elicitation echo

Block the first mutating call of a session, re-armed on any profile-changing verb, until an identity read has occurred, byte-identical on the direct and execute paths, and name the active-profile label in CONFIRM elicitations (ADR I2, I4).

- [x] `P03.S07` - Add per-session identity-read state and the block-first-mutation gate, re-armed on any profile-changing verb, refusing an unconfirmed first mutating call with an instructive localized refusal keyed off the risk table; `src/aeat/entrypoints/mcp/_identity_gate.py`.
- [x] `P03.S08` - Wire the identity gate into the pre-tool-use path byte-identically on the direct and execute paths, and name the active-profile label in the CONFIRM elicitation prompt; `src/aeat/entrypoints/mcp/_server.py`.
- [x] `P03.S09` - Author the identity-refusal and elicitation-echo locale strings through the locales CLI across all four catalogues; `src/aeat/locales`.
- [x] `P03.S10` - Add identity-gate tests: unconfirmed first mutation refuses, a prior identity read clears it, a profile switch re-arms it, and the refusals are byte-identical on both call paths; `src/aeat/entrypoints/mcp/tests/test_identity_gate.py`.

### Phase `P04` - Erik/Erika measurement

Turn the profile-switch wrong-identity scenario into a scored live-harness golden scenario, run before and after as the acceptance gate (ADR Implementation / measurement).

- [x] `P04.S11` - Author the Erik/Erika profile-switch golden scenario where a mutation under the wrong active profile must be blocked until identity is re-confirmed; `src/aeat/agent/eval/scenarios/identidad_perfil.toml`.
- [x] `P04.S12` - Extend the live scoring with an identity-confirmation dimension and run the scenario before and after as the acceptance gate; `src/aeat/agent/eval/_live_scoring.py`.

## Description

Implements the proposed `mcp-identity-linked-operation` ADR (I1-I5): the MCP
console binds every operation to the confirmed active taxpayer identity so a
mutation cannot run under the wrong profile (the Erik/Erika failure the review
found). P01 adds the `active_profile` label to the shared envelope spine so every
response carries the identity anchor. P02 adds the `whoami` core tool over the
existing profile-health assessment. P03 adds the block-first-mutation identity
gate (re-armed on a profile switch) and the elicitation identity echo. P04 turns
the profile-switch wrong-identity case into a scored golden scenario. This plan
DEPENDS on the companion `mcp-hardening-conformance` plan's P01 risk table for its
"which call mutates" definition, so that table lands first.

## Parallelization

Phases are mostly sequential because they build one channel. `P01` (envelope
spine) is independent and can start immediately. `P02` (whoami) is independent of
`P01`. `P03` (the gate) depends on the companion conformance plan's risk table
(the mutating-set definition) AND on `P02` (an identity read via whoami clears the
gate), so it lands after both. `P04` (measurement) is last and gates acceptance.
Cross-plan hard dependency: do not start `P03` until `mcp-hardening-conformance`
P01 has landed; the two plans also share `_server.py`, so serialize edits there.

## Verification

- The success and error envelopes both carry `active_profile`, a profile-bound
  command populates it with the human label, and a no-profile state leaves it
  null; UUID redaction is unchanged (`test_json_schema_conformance.py`).
- `whoami` is always advertised in the core surface (15 tools), is never
  persona-scoped away, and returns the active-profile label + readiness; the
  harness floor carries the same identity block (`test_harness_delivery.py`).
- The first mutating call of a session is refused with an instructive localized
  refusal until an identity read has occurred; a prior `whoami`/`config profile
  status`/`overview status` clears it; a `config switch` re-arms it; the refusals
  are byte-identical on the direct and `execute` paths (`test_identity_gate.py`).
- A CONFIRM elicitation for a destructive/handoff verb names the active-profile
  label; the locale strings exist in all four catalogues
  (`aeat.locales scaffold --check` clean).
- The Erik/Erika golden scenario is scored: a mutation attempted under the wrong
  active profile is blocked until identity is re-confirmed, and the live-harness
  run passes the identity-confirmation dimension before and after.
- Full-tree gates: `uv run --no-sync pytest src/aeat/entrypoints/mcp
  src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py -q` green;
  `uv run --no-sync pytest --collect-only -q` clean.
