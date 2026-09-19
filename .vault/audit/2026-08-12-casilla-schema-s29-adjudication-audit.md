---
tags:
  - '#audit'
  - '#casilla-schema'
date: '2026-08-12'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:80910ef0041ad5b9e673cb3035c41b4fee26a761761af815f524d8691a1283f0'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
  - "[[2026-08-10-casilla-schema-dead-surface-adr]]"
---
# `casilla-schema` audit: `S29 verify_declaracion adjudication review`

## Scope

Formally reviewed `W04.P09.S29` against the accepted dead-surface decision, the full `src/cadrumo/application/verification/` package and tests, the live declaration reconciliation implementation in `_reconcile.py` and `_reconcile_casilla.py`, and the pulled-filing and M303/M349 companion reconcilers. The review independently repeated semantic discovery over code and ADR corpora, checked exact production reachability, mapped every branch and output of `verify_declaracion` to the 17-row disposition table, and verified the live claims against code and real-behavior tests.

The accepted dead-surface decision directly and later adjudicates the older `_verify.py` "do not delete" docstring. The docstring is therefore displaced architecture prose, not an authority that can veto the accepted deletion. Zero production Python importers of `application.verification` or `verify_declaracion` were found outside the package. Exact-name references are documentation citations, not call sites.

## Findings

### [x] capability-scope-wording | low | One row overstated what the dead verifier actually reconciled

The original row headed "Reconcile all computed casillas and reconcile situational casillas only when both sides carry them" was not an exact description of `verify_declaracion`. The verifier loops over `sorted(extracted.items())`; it value-reconciles extracted casillas in the union of the two policy sets, but it does not emit a discrepancy for an omitted computed casilla. Omission affects the separate `coverage` calculation and can drive `NEEDS_REVIEW` through `min_coverage`. By contrast, the living declaration reconcile does iterate the computed policy scope and emits `MISSING_IN_FILED`, subject to its documented printed-record export exemptions. The row's disposition and the overall deletion conclusion remained sound. Resolution: the S29 exec now says the dead verifier value-compares extracted reconciled casillas and separately coverage-gates omitted computed casillas, while identifying the living path's stronger explicit `MISSING_IN_FILED` behavior. The LOW finding is closed.

No missing capability, unsupported covered claim, architecture-inconsistent dropped reason, or semantic absorption requirement was found. The remaining 16 rows accurately cover period/snapshot selection, stamped-reference validation, policy folding, fresh calculation and binding readiness, numeric extraction, tolerance, discrepancy payload and classification, coverage/status/narrative, snapshot and expectation metadata, external-grounding metadata, strict verdict transport, timestamping, and verification-specific error translation.

## Recommendations

- Correct the S29 scope row before lifecycle closure to say that the dead verifier value-compares extracted reconciled casillas and separately coverage-gates omitted computed casillas. No code absorption follows from the correction.
- Proceed to S30 without adding behavior to the living reconcile path. Its persisted-revision lifecycle, typed missing/extra/value divergences, policy tolerance, grounded diffs, strict record/report carriers, atomic persistence, and explicit advisories cover the post-filing question; copying the dead fresh-calculation, duplicate status/error vocabulary, or confidence ratio would create a second authority or misstate the external-evidence comparison.
- During S30's deletion sweep, use the broader static-reference census as well as the import census: the current tree has 83 registry TOML files declaring `cadrumo.application.verification`, plus eight non-test production Python string/doc references across five files, including the error-registry entry. These are deletion hygiene, not missing S29 semantics.

Final verdict: PASS. The wording correction is present, S29 is warning-clean, and S30 is not blocked on semantic absorption.

Verification: the exact S29 command passed with 78 tests. The production AST import census found zero importers. The declared table contains exactly 17 capability rows. A supplementary reconciliation-record and declaration-render run produced 77 passes and one existing Modelo 390 reproduced-render exact-set failure; the absent target is neither a computed nor a reconcile-when-present casilla, so that red gate does not contradict the S29 coverage or deletion conclusion and is not attributed to this Step.
