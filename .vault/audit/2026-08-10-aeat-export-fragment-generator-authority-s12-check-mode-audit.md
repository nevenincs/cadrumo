---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:5f6afb3122f02b182de93638464be471b3b21af243c9b035c085aa5ec8c18bcf'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---

# `aeat-export-fragment-generator-authority` audit: `S12 read-only generated export check`

## Scope

Audit the S12 read-only export-fragment regeneration check. The review boundary covers fresh isolated rendering, S10 validation, canonical provenance and current-authority verification, normalized loader semantics, exact regular-member bytes, target immutability, and refusal of obsolete direct or sibling surfaces.

## Findings

### candidate-ancestor-links | high | resolved before final review

The first independent review found that a linked candidate ancestor could redirect rendering before S10 validation. The checker now requires every existing component from the explicit candidate registry root through its revision root to be non-linked before rendering, and applies the equivalent pre-read guard to the published path. A real symlink proof confirms no redirected export is created and the published target hashes remain unchanged.

### s12-re-review | low | no remaining critical high or medium findings

The independent re-review passed the component-wise guard and its real symlink proof. The focused S12 suite passed 14 tests and the complete `dev/registry/tests` suite passed 105 tests after the correction.

## Recommendations

Retain the component-wise link gate whenever future CLI wiring invokes this read-only checker.
