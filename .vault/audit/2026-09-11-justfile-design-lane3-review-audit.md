---
tags:
  - '#audit'
  - '#justfile-design'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:bc2477560874e2a07b80ba86e367f0092c52335ab4c17886b9eaaa2731f8efc4'
related:
  - "[[2026-09-11-justfile-design-adr]]"
  - "[[2026-09-11-justfile-design-plan]]"
  - "[[2026-09-11-justfile-design-research]]"
  - "[[2026-09-11-justfile-design-audit]]"
---

# `justfile-design` audit: `Lane 3 justfile and packaging implementation review`

## Scope

Reviewed the Lane 3 implementation against the approved justfile-design plan,
ADR, research, and audit. The review covered private lane transport in
`dev/test_runs`, the executable canonical-population census in
`dev/tests/test_lane_reachability.py`, the resident-service marker disposition,
the packaging selectors and cohort dependencies in `justfile`, container
capability recipes, and the packaging selector-contract test.

Review status: PASS. No Critical or High findings were identified.

## Findings

### transport-boundary | low | Lane execution transport contains no semantic membership

The lane runner accepts caller-provided recipe names, preserves output in an
isolated run directory, continues independent lanes, reports duration, and
returns the first non-zero status. The added transport test proves arbitrary
caller-owned names and the absence of the retired test-all transport label.

### population-census | low | Canonical ownership is exhaustive and unique

The reachability census evaluates real tracked test nodes against explicit
marker expressions, path scopes, and exclusions. Its verified corpus contains
over 28,000 nodes with no non-resident unowned or multiply-owned node, and no
node uniquely owned by the temporary tooling backstop. Focused selectors and
the coverage measurement profile are excluded from the canonical census.

### capability-disposition | low | Capability and resident-service holds are explicit

Container, Windows, TUI-render, OS-keychain, workbook, and live-read tests have
dedicated capability selectors outside portable aggregates. The resident
service population consists of the two golden-query service functions and the
terminology sweep function; they remain deliberately outside public population
accounting for W05's RAG-surface removal. The pure workbook-classification
function in the golden-query module is reclassified into repository contracts.

### packaging-flow | low | Artifact selectors share one sealed temporary cohort

The installed-oracle and non-performance serial packaging recipes both depend
on the same temporary cohort builder and use disjoint selectors. Preflight,
artifact qualification, campaign profiles, and performance qualification are
separate recipes. Release distributions depend only on the distribution build,
while infrastructure images have their own aggregate.

## Recommendations

W05 should migrate workflow and developer callers to the replacement surfaces,
prove the retired-name absence, remove the temporary backstop and legacy smoke
recipes, and compose the final gates. Those are planned follow-up actions, not
implementation defects in this lane.
