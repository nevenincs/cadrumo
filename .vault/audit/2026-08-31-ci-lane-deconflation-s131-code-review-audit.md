---
tags:
  - '#audit'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:0cdefea41f82166097525f58e5db82ec263c2851fc04a559ed854dbd5a3e5150'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# `ci-lane-deconflation` audit: `P05 S131 code review`

## Scope

Independent review of P05.S131 `9508a1f8b0db3a04774f17218410cf70a6b7a10e`, its plan/ADRs/execution record, all six committed paths, canonical imports, Renta evidence and retenciÃƒÂ³n semantics, size/baseline state, and current `HEAD`.

## Findings

### P05 S131 code review | high | 86-test evidence is paraphrased and does not establish selection completeness

The S131 record names eight executable sequential pytest commands but records only `pass (N passed)` for each. It does not quote any runner summary line, exit result, collection result, or deselection count. The advertised total of 86 can therefore conceal default-marker deselection, directly violating the accepted CI-lane execution-evidence ADR. Rerun each selection with an explicit `addopts` policy where needed, record literal collection and execution summaries with zero deselections (or disclose every excluded test), exit status, and the actual duration.

### P05 S131 code review | low | final recovery restores source and resolves selection evidence

Recovery `1a0618d39abeee2238e3a50996d8922d15205987` restores the canonical evidence sibling and ledger private import after accidental peer source loss `4112a6cb24`; direct ownership and the P05.S131 plan/exec records are present at current HEAD. Evidence repair `2eb69e1866` records marker-free `addopts=` commands, literal pass/exit values, raw collections, explicit complementary M131/M100 node groups and zero deselections, accounting exactly for all 86 tests. No baseline or S132 change appears. The prior high finding is resolved.

## Recommendations

- Replace the eight paraphrased pytest claims with exact result summaries and selection evidence, then re-review the record-only repair.

No additional P05.S131 corrective work is required.

The source extraction is otherwise canonical: `_renta_income_evidence.py` directly owns sales-invoice evidence, refusal and bounded retenciÃƒÂ³n inference; the ledger imports it privately and exposes no facade. Declared-first retenciÃƒÂ³n, cash-fallback aggregation, M100 jurisdiction/provenance and refusal semantics remain routed through the moved owner. The ledger's recorded 1057-line measure is under the ceiling and no baseline changed.

