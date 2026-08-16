---
generated: true
tags:
  - '#index'
  - '#arch-remediation-lazy-import-policy'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:b2d686882d911368f212a2bacf9c43f76fd9c74eb89bf5b681ee112c9004bac3'
related:
  - '[[2026-07-02-arch-remediation-lazy-import-policy-P01-S01]]'
  - '[[2026-07-02-arch-remediation-lazy-import-policy-P01-S02]]'
  - '[[2026-07-02-arch-remediation-lazy-import-policy-P01-S03]]'
  - '[[2026-07-02-arch-remediation-lazy-import-policy-P02-S04]]'
  - '[[2026-07-02-arch-remediation-lazy-import-policy-P02-S05]]'
  - '[[2026-07-02-arch-remediation-lazy-import-policy-P03-S06]]'
  - '[[2026-07-02-arch-remediation-lazy-import-policy-adr]]'
  - '[[2026-07-02-arch-remediation-lazy-import-policy-plan]]'
  - '[[2026-07-06-arch-remediation-lazy-import-policy-research]]'
---

# `arch-remediation-lazy-import-policy` feature index

Auto-generated index of all documents tagged with `#arch-remediation-lazy-import-policy`.

## Documents

### adr

- `2026-07-02-arch-remediation-lazy-import-policy-adr` - `arch-remediation-lazy-import-policy` adr: `function-local import policy: sanctioned classes, allowlist, ratchet` | (**status:** `accepted`)

### exec

- `2026-07-02-arch-remediation-lazy-import-policy-P01-S01` - Declare the typed lazy-import allowlist entry model carrying site, sanctioned class, reason, and restructuring disposition co-located with the gate
- `2026-07-02-arch-remediation-lazy-import-policy-P01-S02` - Implement the classifier gate that walks production modules, collects function-local first-party imports, and structurally recognises the five sanctioned classes: core resource-repository loaders, PEP 562 CLI cold-start deferrals, TYPE_CHECKING blocks, optional third-party dependency guards, and adapter heavy-import deferrals
- `2026-07-02-arch-remediation-lazy-import-policy-P01-S03` - Make an unclassified site outside the allowlist fail the gate with the site path and the five sanctioned classes named in the message
- `2026-07-02-arch-remediation-lazy-import-policy-P02-S04` - Sweep every current unsanctioned function-local import site and record each in the allowlist with its class, reason, and restructuring disposition, entering the error-registry deferred-bind queue and named cycle-breakers with their existing ADR citations
- `2026-07-02-arch-remediation-lazy-import-policy-P02-S05` - Add the allowlist-length and per-class count ratchet so an increase requires editing the declaration in the same commit while a decrease is free
- `2026-07-02-arch-remediation-lazy-import-policy-P03-S06` - Add the grimp runtime-graph pass as a documented axis in the swarm-audit cadence rule at its vaultspec source and run vaultspec-core sync, so the executed import graph is re-measured on the standing structural-audit rhythm

### plan

- `2026-07-02-arch-remediation-lazy-import-policy-plan` - `arch-remediation-lazy-import-policy` plan

### research

- `2026-07-06-arch-remediation-lazy-import-policy-research` - `arch-remediation-lazy-import-policy` research: `program-track decision research bridge`
