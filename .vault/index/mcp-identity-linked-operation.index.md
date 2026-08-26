---
generated: true
tags:
  - '#index'
  - '#mcp-identity-linked-operation'
date: '2026-08-16'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:9be3b4655c35eec2fcc96e9416bbcb58bdfd03544c9a0ccbec7401be814c23ec'
related:
  - '[[2026-07-08-mcp-identity-linked-operation-adr]]'
  - '[[2026-07-08-mcp-identity-linked-operation-plan]]'
  - '[[2026-07-08-mcp-identity-linked-operation-research]]'
---

# `mcp-identity-linked-operation` feature index

Auto-generated index of all documents tagged with `#mcp-identity-linked-operation`.

## Documents

### adr

- `2026-07-08-mcp-identity-linked-operation-adr` - `mcp-identity-linked-operation` adr: `bind every MCP operation to the confirmed active taxpayer identity` | (**status:** `accepted`)

### exec

- `2026-07-08-mcp-identity-linked-operation-P01-S01` - Add the optional active_profile label field to the shared SchemaEnvelope spine and the stderr ErrorEnvelope sibling, defaulting null before a profile exists
- `2026-07-08-mcp-identity-linked-operation-P01-S02` - Populate active_profile at emit for profile-bound commands from the active-profile resolution, leaving the redacted bucket/profile UUIDs untouched
- `2026-07-08-mcp-identity-linked-operation-P01-S03` - Extend the shared-spine conformance test so the success and error envelopes both carry active_profile and a profile-bound command populates it
- `2026-07-08-mcp-identity-linked-operation-P02-S04` - Add the whoami console tool over assess_active_profile_health returning the active-profile label, tax_id_present, readiness, and next_action, with a description stating its identity-safety job
- `2026-07-08-mcp-identity-linked-operation-P02-S05` - Advertise whoami in the hand-built orientation core (15 tools) and add the same identity block to the harness floor payload
- `2026-07-08-mcp-identity-linked-operation-P02-S06` - Add whoami tests: it is always advertised, returns the active label, and is never persona-scoped away
- `2026-07-08-mcp-identity-linked-operation-P03-S07` - Add per-session identity-read state and the block-first-mutation gate, re-armed on any profile-changing verb, refusing an unconfirmed first mutating call with an instructive localized refusal keyed off the risk table
- `2026-07-08-mcp-identity-linked-operation-P03-S08` - Wire the identity gate into the pre-tool-use path byte-identically on the direct and execute paths, and name the active-profile label in the CONFIRM elicitation prompt
- `2026-07-08-mcp-identity-linked-operation-P03-S09` - Author the identity-refusal and elicitation-echo locale strings through the locales CLI across all four catalogues
- `2026-07-08-mcp-identity-linked-operation-P03-S10` - Add identity-gate tests: unconfirmed first mutation refuses, a prior identity read clears it, a profile switch re-arms it, and the refusals are byte-identical on both call paths
- `2026-07-08-mcp-identity-linked-operation-P04-S11` - Author the Erik/Erika profile-switch golden scenario where a mutation under the wrong active profile must be blocked until identity is re-confirmed
- `2026-07-08-mcp-identity-linked-operation-P04-S12` - Extend the live scoring with an identity-confirmation dimension and run the scenario before and after as the acceptance gate

### plan

- `2026-07-08-mcp-identity-linked-operation-plan` - `mcp-identity-linked-operation` plan

### research

- `2026-07-08-mcp-identity-linked-operation-research` - `mcp-identity-linked-operation` research: `Identity-linking safety review of the MCP console`
