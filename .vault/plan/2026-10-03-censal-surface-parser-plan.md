---
tags:
  - '#plan'
  - '#censal-surface-parser'
date: '2026-10-03'
tier: L1
related:
  - '[[2026-10-03-censal-surface-parser-adr]]'
modified: '2026-10-03'
body_schema: body-v2
body_hash: 'sha256:1d001519759e5f991c49a7244bff4f3cdeee4766b810e314e47c28d6123b29c0'
---

# `censal-surface-parser` plan

## Description

Approved 2026-10-03. The operator requested live mapping, own-name Cl@ve Movil and robust parsing of all four consultations, reusing the existing TUI/CLI/profile flow. The linked decision governs the additive evidence contract; no second sync or adoption path is permitted.

## Steps

- [ ] `S01` - Implement semantic census consultation parsing and guarded popup acquisition; prove complete live capture and encrypted observation parity; `src/cadrumo/adapters/outbound/aeat/sede, src/cadrumo/application/user_profile/censal_observation.py`.

## Parallelization

Sequential, one browser session. No delegated implementation.

## Verification

Synthetic parser mutation tests cover reordered headers, presentation changes, unknown fields, ambiguous values and auth/maintenance pages. Real browser tests prove consultation-only navigation and popup handling. A live authenticated pull compares all parsed fields with rendered DOM evidence, then verifies the canonical reviewed observation through encrypted custody. Run focused tests, Ruff format/lint, configured type and import checks, then review the integrated change. Do not report capture as adoption of ungrounded regime facts.

