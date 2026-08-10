---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:0df5615beebb23ae0f905c95cd9a547a4a7506d5a104884443c42718db8f1dd3'
step_id: 'S31'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# Define and validate the exhaustive per-modelo, per-design, source-SHA-pinned render-profile authority with exact-anchor coverage, explicit unsigned Num versus signed N handling, individually grounded rules for all 126 smaller fields, and no legacy-tree oracle or implicit defaults

## Scope

- `dev/registry/`

## Description

- Define a strict frozen render-profile schema bound to exact modelo, design epoch, source reference, source SHA-256, and parser-owned anchors.
- Resolve official-source evidence from exact cells in the hash-verified workbook while keeping reviewed policy decisions explicitly distinct from official text.
- Enumerate every eligible width-17 `Num` and signed `N` anchor and every smaller numeric anchor in deterministic reviewable fragments.
- Encode the reviewed checkbox and two-digit-year policies only at their exact authorized anchors.
- Validate exact eligibility equality, source applicability, evidence agreement, representation consistency, duplicate and overlap refusal, and variable-envelope exclusion.
- Prove the real profile and causal mutation refusals without mocks, fakes, patches, skips, or legacy layout authorities.

## Outcome

The Modelo 200 design-epoch 2025 profile is pinned to source reference `aeat-dr-200-2025` and SHA-256 `a4506d24b7973a745d1225d59147078e03f14a30791a229d852b37f757442505`. Its 128 deterministic fragments enumerate 3,323 unsigned `Num` width-17 anchors, 2,227 signed `N` width-17 anchors, and 126 exact singleton anchors. The singleton authority consists of 38 binary-resolved official-source conclusions, 86 reviewed checkbox decisions that encode selected as `1` and absent or unselected as `0`, and two reviewed `DP200DID` decisions that encode the final two digits of a four-digit year.

The production validator derives the eligible set from fixed parser IR, requires exact governed-set equality, and excludes the typed `DP200000` variable envelope. Official evidence is read from exact workbook cells only after binary SHA verification; reviewed policy carries its exact governed anchor and never masquerades as official source text. No renderer or provenance behavior from `S32` is integrated.

Focused verification passed with 24 tests. The broader record-design, semantic-map, join, and profile authority slice passed with 63 tests. Scoped Ruff and strict BasedPyright passed with zero diagnostics. All 128 fragments remain below the 500-line review cap, with a maximum of 373 lines. The feature-scoped vault check passed all checks; the plan check retained only the intentional non-monotonic inserted-step `PLAN022` warning.

Independent formal review passed with no critical, high, medium, or low findings. The durable `s31-render-profile` audit records the review scope, exact census, mutation proof, and gate results.

## Notes

The first fail-closed schema implementation landed in shared-branch commit `d434265d54`, followed by reviewed hardening in `de9ae7da0d`. S31 remained open until the missing 86 checkbox and two short-year exact-anchor policies were explicitly authorized. This completion preserves those decisions as reviewed policy rather than relabeling them as official AEAT evidence.

The shared worktree contained unrelated peer modifications throughout execution. Only the S31 schema, tests, profile fragments, formal-review audit, execution record, and CLI-managed plan row are part of this step. A feature-index/body-sections warning can temporarily appear for newly untracked concurrent vault records until the shared generated index is refreshed by its owner; markdown, frontmatter, placeholder, and feature-scoped vault checks for the authored records are otherwise clean.
