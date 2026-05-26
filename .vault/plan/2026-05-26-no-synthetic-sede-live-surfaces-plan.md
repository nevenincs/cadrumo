---
tags:
  - '#plan'
  - '#no-synthetic-sede-live-surfaces'
date: '2026-05-26'
tier: L2
related:
  - '[[2026-05-26-no-synthetic-sede-live-surfaces-research]]'
  - '[[2026-05-26-no-synthetic-sede-live-surfaces-adr]]'
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

# `no-synthetic-sede-live-surfaces` implementation plan

### Phase `P01` - policy invariant

Define the registry and guard invariant that AEAT-hosted live surfaces must not allow synthetic input.

- [x] `P01.S01` - Add schema validation rejecting AEAT-hosted live cross-references that allow synthetic data; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `P01.S02` - Add remote-state guard validation rejecting AEAT-hosted policies that allow synthetic data; `src/aeat/domain/calculations/registry/_remote_state_guard.py`.
- [x] `P01.S03` - Update registry policy tests for the no-synthetic AEAT-host invariant; `src/aeat/domain/calculations/registry/test_remote_state_guard.py`.

### Phase `P02` - surface rewrites

Rewrite the committed Modelo 100 and Modelo 349 live-surface declarations and tests to conform to the no-synthetic-Sede rule.

- [x] `P02.S04` - Rewrite Modelo 100 Renta WEB Open registry and tests to disallow synthetic live input (7dfcaac94) - flipped `synthetic_data_allowed` to `false` with provenance comment citing the ADR; surface remains `open_simulator`; `src/aeat/_data/registry/aeat/modelos/100/`.
- [x] `P02.S05` - Rewrite Modelo 349 GROI and IXVI registry and tests to disallow synthetic live input (7dfcaac94) - flipped both `modelo-349-groi-spanish-counterparty-check` and `modelo-349-ixvi-foreign-counterparty-check` to `synthetic_data_allowed = false`; both retain `authenticated_simulator` classification; `src/aeat/_data/registry/aeat/modelos/349/`.
- [ ] `P02.S06` - Rewrite outbound Sede live-surface tests and drivers to avoid live synthetic input; `src/aeat/adapters/outbound/aeat/sede/`.

### Phase `P03` - validation and handoff

Run the focused validation gates, record execution evidence, and close the declaration-extraction S124 handoff only after implementation is verified.

- [ ] `P03.S07` - Run focused registry and Sede test gates for the no-synthetic policy; `src/aeat/domain/calculations/registry/`.
- [ ] `P03.S08` - Record execution evidence and close the declaration-extraction S124 handoff; `.vault/exec/`.
