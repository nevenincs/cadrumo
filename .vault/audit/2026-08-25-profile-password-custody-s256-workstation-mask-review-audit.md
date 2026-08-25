---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:b7524b7387d4b4b9e82e8bbdbc385628a22bd2dc9161642aa66be5aaa4989bea'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# `profile-password-custody` audit: `S256 workstation mask review`

## Scope

Reviewed `W06.P12.S256` at current HEAD with provenance through commit
`6c43ddb406` and the refreshed `install-confirm` workstation golden. The review
covered central coordinate ownership, JSON and text normalization, two real
fresh-sandbox executions, volatile free-capacity tolerance, deterministic
total-memory and registry-health tamper visibility, and golden/page coherence.
The focused mask-policy module was also executed directly. Production code and
goldens were not modified by the review.

## Findings

No findings. The mask is a closed set of exact `(row id, fact name)` coordinates
for hardware free RAM, hardware free VRAM, and contention binding-free capacity.
It does not use the retired `_bytes` suffix rule, so total RAM, total VRAM,
thresholds, shortfalls, and byte facts on unrelated rows remain exact. JSON
normalization preserves fact keys while masking only their values. Text
normalization requires the exact row/fact prefix followed by a tab, preventing
prefix or sibling-field overmatching.

The real workstation sequence is discovered by its owner id and executed twice
in fresh sandboxes through the production runner. Comparison succeeds across
ordinary free-capacity drift. Mutating only `free_memory_bytes` remains ignored,
while mutating `total_memory_bytes` or flipping the real
`registry:referential-integrity` health row produces a comparison failure. This
is a substantive anti-tautology pair: the mask demonstrably tolerates its exact
subject while deterministic host and registry evidence still bites. The
refreshed golden carries the owner CLI page's current dependency and preflight
shape, with normalized text showing only the three intended masked coordinates.

The focused coordinate-policy module passed all 7 tests.

## Recommendations

No remediation is required for S256. Keep future volatile measurements behind
explicit reviewed row/fact coordinates and pair every addition with a real-run
tolerance direction plus deterministic sibling and registry-health tamper
directions. No CRITICAL, HIGH, MEDIUM, or LOW finding is open.
