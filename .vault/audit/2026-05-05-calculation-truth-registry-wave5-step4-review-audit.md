---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related: []
---

# Modelo 131 Annual Legal Grounding Review

## Review Scope

- `registry/aeat/legal/irpf.toml`
- `registry/aeat/modelos/131.toml`
- `corpus/normatives/html/orden-hfp-1359-2023.html`
- `corpus/normatives/html/orden-hac-1347-2024.html`
- `corpus/normatives/html/orden-hac-1425-2025.html`

## Findings

- No blocking findings after registry verification.
- The annual 2024, 2025, and 2026 BOE module orders are now present in the
  local corpus and catalogued as legal authority for their year-scoped
  objective-estimation module approval.
- The current Modelo 131 revision now cites the 2026 module-order legal
  authority in addition to RD 439/2007 article 110 and Orden EHA/672/2007.
- The registry verifier exposed source-integrity drift in local HTML corpus
  files, and the source catalogue now matches the files actually committed in
  the worktree.
- The plan ledger now separates live discovery from live parser coverage:
  Modelo 131 has a verified zero-row live scan, but no sanitized live fixture.
- The plan ledger now separates flat liquidacion calculations from export
  design work: DPA activity detail, DID direct-debit layout, and the flatter
  2019-2023 record design remain explicit unchecked rows.

## Residual Risk

- The annual module orders do not by themselves complete historical Modelo 131
  revision authoring. The 2019-2023, 2024, and 2025 TOML revisions still need
  explicit registry representation and behaviour tests.
