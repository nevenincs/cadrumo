---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:e1305b060db912e9b4f1c2a4a66201ee200a1617f1af11fb3b8503eda0c44bfc'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace profile-password-custody with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

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
