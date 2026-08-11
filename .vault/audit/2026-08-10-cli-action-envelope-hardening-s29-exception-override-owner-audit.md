---
tags:
  - '#audit'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:22e4f81c917d41a1c741f1534330c7b765db8f36c0f5c32a899dd7a632743b41'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
## Scope

Review the S29 current-tree exception-override owner gate, including exact observation identity, canonical plan ownership, and failure modes that could hide a source site.

## Findings

### s29-exception-override-owner | high | source traversal now fails closed

The initial review found that read, decode, and parse failures could silently reduce the blast radius. The scanner now raises a deterministic DispositionValidationError containing the source path and failure kind. Real temporary filesystem cases prove directory read failure, invalid UTF-8, and syntax failure stop the census.

### s29-exception-override-owner | high | active observations cannot be excluded

The initial review found that a live override could carry an EXCLUDED disposition. The owner gate now admits only producer or transformer dispositions. A real current-source/current-plan regression proves an excluded justificante owner fails.

### s29-exception-override-owner | pass | physical multiplicity is retained

The current extractor reports 46 physical observations and 43 stable CandidateKeys. The censo parser key owns two observations and the modelo profile-create key owns three. Ledger fingerprint multisets must exactly equal the source-derived multiset, so missing, extra, and duplicate entries fail.

### s29-exception-override-owner | pass | ownership uses the canonical open plan projection

All live owners resolve from `vaultspec-core vault plan query --json` to open scoped Steps. Closed S21 and S24 are diagnostic predecessors only. S96 owns modelo selectors and forwarding, S98 registry forwarding, and S99 justificante cooperative MRO forwarding. The former workflow source is historical-only; S97 is not a live ledger owner.

## Recommendations

Close S29 only as the live exception-override linkage gate. Do not claim broad action-ledger closure: the revision-pinned legacy disposition reconciliation remains a separately scoped concern. Continue with S30, which proves registered error recovery against the live command and input surface.

## Validation

- Focused serial suite: 21 passed in 128.64s.
- Direct owner gate: 46 physical observations / 43 stable keys.
- Ruff and format checks passed.
- Targeted basedpyright: 0 errors, 0 warnings.
- Diff whitespace check passed.
