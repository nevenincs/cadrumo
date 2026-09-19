---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:89f906e5627e343a81a920654d8f66f81da676265467d0bc5fa8c47ad1a8ada3'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-26-tui-architecture-s170-alias-selection-remediation-audit]]"
---

# `tui-architecture` audit: `S170 semantic selector consolidation`

## Scope

Corrective record for the third independent S170 review. That review found the
detector still depended on literal catalogue names, covered only one selector
family, skipped additional authority in the canonical file, and could confuse
analytics with selection. This remediation models typed provenance and a
WorkUnit decision, consolidates exact and operator selection into the sole
public selector, and makes resident classification consume the same scanner
predicate. It does not change the S170 plan state.

## Findings

### catalogue-provenance | high | Catalogue identity follows types, parameters, and assignments

`SubstitutableWorkSelectorRule` declares catalogue and repository protocol
types rather than a required variable spelling. The scanner follows renamed
typed parameters, local aliases, attribute aliases such as
`holder.units=catalogue`, typed repository loads, `values` and `items`, tuple
targets, and comprehensions. Exact mutants cover each route.

### selector-family-coverage | high | Natural, exact-id, operator-id, and repository first-match selection are detected

Candidate predicates now include natural-coordinate comparisons, exact
`work_unit_id` equality, and prefix or suffix operator matching. A typed
repository load followed by a returned candidate is also selection authority.
Detection requires a returned, resolved, or indexed candidate rather than a
mere scan.

### analytics-separation | high | Projection and counting loops remain negative controls

Coordinate reads without comparisons do not qualify. Aggregate and collection
returns such as `sum`, `len`, `sorted`, or `tuple` are excluded before candidate
name resolution, so comparison-based counts and histories do not become false
owners. Static and resident-classifier mutants prove projection and counting
responses remain non-owners.

### canonical-consolidation | high | Exact and operator catalogue scans now live in the sole public selector

The bodies of `_select_exact_modelo_work_resolution` and
`_select_operator_work_unit_resolution` were inlined into
`select_modelo_work_resolution`, preserving typed contradictions, not-found and
ambiguity refusals, coordinate validation, and resolution construction. Both
private helpers were deleted. A scanner-owned definition census requires one
public selector and proves the fragmented helpers remain absent. The canonical
file is scanned like every other production file; only the exact public
defining function is exempt.

### shared-rag-semantics | high | Every canonical-path hit is inspected with the reusable selector predicate

Resident classification no longer stops after recognizing the canonical path.
It records canonical ownership and still scans each snippet, so a second
selector returned from the same file is a parallel owner. The classifier uses
the scanner-owned semantic predicate and includes exact canonical-path,
renamed, attribute, tuple, projection, and analytics controls.

### focused-evidence | low | Static and resident S170 proofs pass

Ruff passed. Fixed-point, public-cutover, and reusable scanner suites completed
with 50 passing tests in 100.91 seconds. The direct resident S170 proof passed
at port `8766` in 3.56 seconds. The focused production behavior suite was
attempted but shared registry data currently contains an empty Modelo 165
deadline-window fragment directory, causing `RegistryLoadError` before selector
behavior executes; this audit does not call that lane green.

## Recommendations

Keep `W03.P20.S170` unchecked. Commit only the canonical selector,
scanner, declarative fixed-point and resident tests, and this audit. A later
independent review must replay every positive and negative mutant and verify
the inlined behavior once the shared registry fixture is valid. Only that
review may recommend a lifecycle transition.
