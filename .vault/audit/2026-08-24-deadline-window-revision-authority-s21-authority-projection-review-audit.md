---
tags:
  - '#audit'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:bca169f8c3052b966c3fcd59e5c0af27ca658c055e5b71bbed29b2732ba5bb31'
related: []
---

# `deadline-window-revision-authority` audit: `s21 authority projection review`

## Scope

Independently reviewed `W03.P08.S21` against the accepted deadline-window
revision-authority ADR, its research and reference, and the approved plan. The
review covered `ValidatedRegistryAuthority.deadline_windows`, its use of
`select_revision`, certified warm-load behavior, qualifier-aware ordering,
defensive ownership assertion, preservation of authored multiplicity, and the
absence of a parallel resolver or deduplication path. Semantic discovery through
Vaultspec RAG was followed by exact-symbol confirmation across the registry,
deadline, and application production surfaces.

## Findings

No triaged findings. The projection reuses the existing `select_revision`
authority for each window's canonical `Period` coordinate, retains every row in
the selected revision rather than collapsing multiplicity, and orders qualifier
variants from the existing `ResultDisposition` values and authored official-code
scope. The new sort helper introduces no tax vocabulary or matching semantics.
The identity assertion defensively proves that the returned provenance object is
the object stored under the canonically selected revision id. A
fingerprint-certified authority that skips a newer validator still performs the
canonical selection at projection time, so stale non-owner copies are not
returned.

Ruff passed for `src/cadrumo/domain/calculations/registry/_authority.py`. The
focused ownership suite passed. The existing authority suite reached five setup
errors because the in-progress bundled corpus still contains the known M184,
M303, and M322 violations allocated to corpus-repair steps; those errors occur
during registry validation before the S21 projection test and do not identify an
S21 regression. Fourteen focused tests completed as nine passes and five setup
errors.

## Recommendations

Verdict: approve `W03.P08.S21` with no severity-bearing findings. Continue with
`W03.P08.S22` to add the dedicated fleet projection regressions, and rerun the
bundled authority suite after the planned corpus-repair steps restore a valid
registry tree.
