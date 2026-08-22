---
tags:
  - '#audit'
  - '#issue-623-python-patch-pin'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:b8840e9bd0e55a1a06278fa032f785b5293ecb775c0ab8c6d34c56f5a89749f7'
related: []
---



# `issue-623-python-patch-pin` audit: `Exact Python patch pin implementation review`

## Scope

Fresh-context review of issue 623 implementation commit
`52a5e893d482970ca2534b0620eaf86bd1b82b6a` against its parent. The review
covered all 16 changed workflows, every current `astral-sh/setup-uv` consumer,
checkout ordering, setup-uv/uv version-selection semantics, the immutable
release-cohort builder, the compatibility-matrix exception, package support
metadata, and the new repository-wide structural gate.

`HEAD` was verified as the requested implementation commit and the worktree was
clean apart from this CLI-scaffolded audit. The sweep found 33 setup-uv steps in
16 workflows, all after checkout, and zero remaining `python-version`
overrides. Current setup-uv documentation confirms that its `python-version`
input sets `UV_PYTHON` and overrides project version files; omitting it leaves
subsequent uv commands to resolve the checked-in exact `.python-version`. The
release-cohort runtime now reads the same file, while `requires-python >=3.13`
remains a separate package-compatibility declaration rather than a CI runtime
selection.

Focused workflow/property and release-cohort checks passed 27 tests; Ruff and
Git whitespace checks passed. Actionlint accepted 15 changed workflows. Its
only diagnostic across the full changed set was the pre-existing custom
`windows-scoop` self-hosted label missing from actionlint configuration in
`packaging-scoop.yml`, unrelated to the removed Python override.

## Findings

### setup-uv-consumer-count | medium | the repository-wide gate passes when it scans no setup-uv consumers

`test_setup_uv_consumers_follow_the_repository_python_pin` accumulates only
violations and asserts that the collection is empty; it never asserts that any
setup-uv step was discovered. Replacing `_workflow_documents` with an empty
result and invoking the test completed successfully (`VACUOUS_PASS_CONFIRMED`).
Consequently, deleting or renaming every setup-uv consumer makes the new gate
green while eliminating the exact toolchain contract it claims to enforce.
The matrix exception has the same anti-tautology weakness: its acceptance path
has no synthetic positive/negative cases and no live compatibility-matrix
consumer, so the current four-line predicate is not independently proven to
accept only the intended exception shape.

## Recommendations

For `setup-uv-consumer-count`, count discovered setup-uv steps and assert a
non-zero expected surface before asserting zero violations. Extract or
parameterise the override classifier and add anti-tautology cases covering an
ordinary omitted override, a valid matrix containing the repository pin plus
an alternative, and invalid matrices that omit the pin or contain no
alternative. Mutation evidence should show that an empty workflow inventory
and each invalid exception redden the gate.

The production change is directionally correct, but issue 623 is not safe to
integrate or close until this medium gate defect is fixed and the focused
workflow/property checks pass again.
