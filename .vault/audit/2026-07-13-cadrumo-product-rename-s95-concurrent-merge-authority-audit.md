---
tags:
  - '#audit'
  - '#cadrumo-product-rename-s95-concurrent-merge-authority'
date: '2026-07-13'
modified: '2026-07-13'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# `cadrumo-product-rename-s95-concurrent-merge-authority` audit: `S95 concurrent merge authority review`

## Scope

- Independently review the logical S95 transaction across concurrent merge `f70329749d` and closeout `3db2049e848e0ab1cf921f98054078f86b2762e6`, including both merge parents and the exact final blobs.
- Verify reciprocal ADR supersession, the binding identity matrix, runtime identity constants and tests, plan checkbox honesty, the S95 execution record, foreign-work exclusion, and whether absorbed `a254972aee` content reintroduced any other false authority.
- Run read-only identity, live CLI, rule-sync, ADR, plan, vault, and diff gates. Make no implementation or authority fix and commit only this audit while preserving the staged marketplace README and dirty S58 record.

## Findings

Verdict: **FAIL**. One HIGH authority defect blocks downstream casing closure. No critical, medium, or low findings were found.

### s95-concurrent-merge-authority | high | accepted 2026-07-13 ADR conflicts with the binding identity authority

Commit `a254972aee` introduced `.vault/adr/2026-07-13-product-rename-adr.md`; merge `f70329749d` absorbed that exact blob, and it remains unchanged at the reviewed closeout. The ADR is still accepted and declares the public product name as title-case `Cadrumo`. Its body also preserves stale Stage-B console-renaming and `aeat` import-package statements. A trailing correction says the ADR remains accepted and delegates the corrections to the binding CLI ADR's "status note", but `3db2049e84` correctly deletes that false status note. The binding CLI ADR supersedes only the 2026-07-12 product-rename ADR, so this second accepted ADR has no reciprocal supersession edge and points to text that no longer exists. The final authority graph therefore still permits a conflicting title-case product identity despite the six S95-owned surfaces being correct.

The intended S95-owned state otherwise reconciles. The final 2026-07-12 parent ADR is stamped `2026-07-13`, marked superseded, and reciprocally names the binding CLI ADR. The final CLI ADR is byte-identical to the clean S90 authority blob: product display `CADRUMO`; distribution, repository, package, plugin, and MCP identity `cadrumo`; human executable `aeat`; MCP executable `cadrumo-mcp`; environment prefix `CADRUMO_`; companion distributions and `cadrumo_data`; remote authority `AEAT`. It contains neither the absorbed title-case status note nor a third-reconfirmation claim; its only title-case occurrence is a quoted historical commit title.

Runtime identity and its direct tests use `CADRUMO`. The focused suite reports 5 passed, Ruff check and format gates pass, `aeat --version` reports `CADRUMO 0.2.0`, and live help contains exact-case `CADRUMO`, `AEAT`, and `aeat` with no exact-case `Cadrumo`.

Plan provenance is exact. Relative to the first merge parent, S07, S87, S90, and S93 reopen; S95 is added checked; and no other S94-to-S95 plan row changes. S07, S87, S90, and S93 remain open at the closeout. The S95 record honestly says merge `f70329749d` absorbed the staged baseline while resolving a foreign marketplace conflict, records the four reopenings, and does not claim that the remaining authority conflict was repaired.

The logical merge phase changes six S95 paths and passes `git diff --check`; the closeout changes only the CLI ADR and S95 record and also passes `git diff --check`. The dirty S58 record has the same HEAD and index blob and remains only an unstaged edit. The marketplace README changed as foreign merge-resolution content and remains separately staged after S95; the closeout did not include it.

Plan checking exits successfully with only known `PLAN022`. ADR status checking has only two unrelated pre-existing warnings, and focused frontmatter, Markdown, and placeholder checks are clean. Rule-sync dry-run leaves all four product-authority rule copies unchanged. The repository-wide vault check cannot serve as a green gate in the shared tree: it reports 348 unrelated structural errors and 87 warnings while references, schema, ADR status, rename integrity, and encoding remain clean.

## Recommendations

- Block downstream casing closure until the accepted 2026-07-13 product-rename ADR is explicitly superseded by the binding CLI ADR, with reciprocal metadata updated on both documents and its stale title-case/Stage-B text retained only as historical context under superseded status. Do not restore the deleted false status note as the remedy.
- Independently re-review the authority graph after remediation, including both reciprocal supersession edges and every accepted naming ADR.
- Keep S07, S87, S90, and S93 open. Continue the other currently open casing lanes under their existing ownership, including S05, S25, S37, S43, S45, S48-S54, S57-S58, S62-S67, S76, S78, and S86.
- Preserve the staged marketplace README and dirty S58 work as foreign concurrent changes; do not absorb either into an authority-remediation commit.
