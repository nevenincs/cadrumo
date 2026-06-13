---
tags:
  - '#adr'
  - '#domain-profile-rename'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - "[[2026-06-01-domain-boundary-audit-adr]]"
  - "[[2026-06-01-domain-boundary-audit-plan]]"
  - "[[2026-06-01-domain-boundary-audit-audit]]"
  - '[[2026-06-04-domain-profile-rename-research]]'
---

# `domain-profile-rename` adr: `Rename domain/profile to domain/contribuyente (S63 target name, ADR D7)` | (**status:** `accepted`)

## Problem Statement

ADR D7 of the domain-boundary audit mandates renaming the `domain/profile` package to
its "true subject" but deliberately left the target name open (the plan step `W06.P17.S63`
wrote "e.g. `domain/renta_profile`"). The package is not a bare tax-residence profile: it
holds the contribuyente's tax-residence/CCAA data, renta and Modelo-100 family facts, the
profile-key registry, and the asset/inventory ledger record models. With the ledger errors
already relocated (S61/S62) and the DB-17 inverted edge removed (S64), only the rename
itself remains — and it cannot proceed without a pinned name, because it is an 89-file
sweep that is costly to redo.

## Considerations

- The `aeat-spanish-stem-naming` rule requires AEAT domain concepts to carry their Spanish
  stem (`iva`, `renta`, `modelo`, `casilla`, `censo`, …). The owning concept here is the
  *contribuyente* (taxpayer) and their tax profile.
- `renta_profile` (D7's "e.g.") under-describes the package: tax-residence and
  asset/inventory content is not renta-specific.
- `taxpayer_profile` is accurate but English, departing from the Spanish-stem convention.
- The choice was confirmed with the operator (2026-06-03): **`domain/contribuyente`**.

## Constraints

- 89 files reference `domain.profile` (every submodule + importers + the entire
  `docs/api/aeat.domain.profile.*` stub tree). The rename is one atomic move and needs the
  tree quiesced (all 89 targets simultaneously non-peer-WIP through script→verify→commit)
  — hence D7/plan sequence S63 last, once the campaign's other drifts are closed (now the
  case: S63 is the sole remaining item).
- No frontier/immature dependency; the mechanism (scripted token replacement + the codified
  6-point module-rename checklist) is proven across S54/S65/S66.

## Implementation

Rename the `domain/profile` package directory to `domain/contribuyente` and repoint every
reference using the proven scripted pattern, covering all six rename surfaces codified in
the audit ledger: (a) import statements (`aeat.domain.profile` / `domain.profile import` /
relative `from ..profile`), (b) core error-registry path strings, (c) `:mod:` docstring
cross-references, (d) any hardcoded module-path strings in marker tests, (e) `.importlinter`
ignore entries naming `domain.profile.*`, and (f) the apidocs stub tree (regenerate). The
subpackages (`assets`, `inventory`, `_keys`, `_errors`, `_ccaa`, `_normalise`, family
records) move with the package. Verification: `pytest --collect-only` clean, the
domain/profile + importer test suites green, `ty`, `lint-imports` contracts unchanged, and
`apidocs scaffold --check` conformant — all in one atomic commit tagged
`relocation:domain.profile`.

## Rationale

`contribuyente` is the Spanish stem for the owning concept and is broad enough to cover the
package's three-concern content without claiming a narrower identity it does not hold, satisfying
both ADR D7's "true subject" intent and the `aeat-spanish-stem-naming` rule. It was operator-
confirmed over the `renta_profile` and `taxpayer_profile` alternatives.

## Consequences

- **Gains.** The package name finally matches its content; D7 is fully discharged; the
  misleading "profile" identity is gone.
- **Difficulties.** An 89-file atomic sweep is the campaign's highest-blast-radius change
  and demands a quiescent window on the shared worktree; a mid-sweep peer collision forces
  an abort-and-retry (the diff is fully scripted, so retry is cheap). The `docs/api` tree
  rename is large but mechanical via `apidocs scaffold`.
- **Pathways.** Completes ADR D7 and the domain-boundary campaign's structural rename work.

## Codification candidates

- **Rule slug:** `module-rename-six-surface-checklist`.
  **Rule:** Renaming a Python module or package MUST update all six reference surfaces in
  one atomic commit — imports, core error-registry path strings, `:mod:` docstring
  cross-references, hardcoded module-path strings in marker/inventory tests,
  `.importlinter` ignore entries (including those naming renamed *test* files), and the
  generated apidocs stub tree — because an import-only sweep silently leaves the last four
  stale (registry-enforcement, docs-build, and import-linter breakages surface later).
