---
tags:
  - '#audit'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:6fc3466cd5e92ccd4d7fd073d1365768168dcb63563dfb325d104ed069e845e5'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace ci-lane-deconflation with a kebab-case feature tag, e.g. #foo-bar.
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

# `ci-lane-deconflation` audit: `P05 S131 code review`

## Scope

Independent review of P05.S131 `9508a1f8b0db3a04774f17218410cf70a6b7a10e`, its plan/ADRs/execution record, all six committed paths, canonical imports, Renta evidence and retenciÃ³n semantics, size/baseline state, and current `HEAD`.

## Findings

### P05 S131 code review | high | 86-test evidence is paraphrased and does not establish selection completeness

The S131 record names eight executable sequential pytest commands but records only `pass (N passed)` for each. It does not quote any runner summary line, exit result, collection result, or deselection count. The advertised total of 86 can therefore conceal default-marker deselection, directly violating the accepted CI-lane execution-evidence ADR. Rerun each selection with an explicit `addopts` policy where needed, record literal collection and execution summaries with zero deselections (or disclose every excluded test), exit status, and the actual duration.

## Recommendations

- Replace the eight paraphrased pytest claims with exact result summaries and selection evidence, then re-review the record-only repair.

The source extraction is otherwise canonical: `_renta_income_evidence.py` directly owns sales-invoice evidence, refusal and bounded retenciÃ³n inference; the ledger imports it privately and exposes no facade. Declared-first retenciÃ³n, cash-fallback aggregation, M100 jurisdiction/provenance and refusal semantics remain routed through the moved owner. The ledger's recorded 1057-line measure is under the ceiling and no baseline changed.

