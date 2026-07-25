---
tags:
  - '#exec'
  - '#post-release-distribution'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S32'
related:
  - "[[2026-07-17-post-release-distribution-plan]]"
---

# DONE 7d20b2d984, the three tap-pattern over-broadenings are closed, scanning moved per line so a cross-newline match cannot form and the regression document genuinely reproduces the whole-file match, the pattern re-anchored on the account so a third-party tap is not a claim, and a negation preceding the command marks a disclaimer. GATE, the positive control carries all three strings as must-not-match cases

## Scope

- `dev/docs/tests/test_distribution_claims.py`

## Description

- Move claim scanning from whole-file to per-line.
- Re-anchor the tap pattern on the publishing account rather than an arbitrary owner/name slug.
- Treat a negation preceding the command on a line as a disclaimer rather than a claim.

## Outcome

All three over-broadenings are closed and each has a must-not-match case behind it. Per-line scanning removes the cross-newline match, account anchoring stops an unrelated third-party tap reading as a claim about this product, and the negation guard delivers what the module docstring already promised.

## Notes

The first regression document I wrote for the cross-newline case did not actually reproduce it, so the test would have proven nothing. Direct evaluation caught that, and the document now genuinely matches under whole-file scanning and not per line, with an assertion pinning that it still reproduces. The negation must precede the command rather than appear anywhere on the line: scanning the whole line would let a trailing caveat silence a real claim, and a silenced claim is the failure direction this gate exists to prevent. Semantic search was degraded for the whole of this work: the code index served roughly a fifth of the tree while reporting itself healthy, so a search miss was worthless as evidence. Discovery was done by direct directory listings, file reads, and targeted pattern search instead.
