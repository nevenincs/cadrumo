---
tags:
  - '#adr'
  - '#git-free-tooling'
date: '2026-10-07'
modified: '2026-10-09'
body_schema: 'body-v2'
body_hash: 'sha256:c8ac8d27b48f16273e01fc4a95bfb99e5e6d0f08c59421a97f9d5afe949b4fff'
related:
  - "[[2026-09-17-github-actions-adr]]"
  - "[[2026-10-04-application-distribution-adr]]"
  - '[[2026-10-07-git-free-tooling-audit]]'
---
# `git-free-tooling` adr: repository-owned code never invokes Git | (**status:** `accepted`)

## Problem Statement

Tests and build tools invoke Git to inspect the working checkout, derive build numbers and prepare packaging fixtures. CI shells also use Git to publish generated files. These paths make verification depend on repository history and a version-control executable.

## Considerations

Current callers include `dev/env/clean.py`, `dev/env/_dotenv.py`, `dev/ci/change_scope.py`, `dev/registry/edition_round_trip.py`, `dev/deploy/docs_delivery_policy.py`, packaging smoke scripts, `native/cmake/BuildNumber.cmake` and release workflow shells. The former optional-lock test permits these dependencies.

Grounding: `2026-10-07-git-free-tooling-audit` records the former history-dependent tooling and Git-backed fixtures, the explicit-input and forge-API replacements, and the executable-call enforcement evidence. It is a retrospective implementation audit, not the authorization for this decision; its verification results and remaining installation/publication limits are preserved there.

## Considered options

- Keep Git with lock-free options: rejected by the operator's absolute prohibition.
- Remove Git invocations and use current filesystem content, explicit build inputs and forge APIs: selected.

## Constraints

Authorization is the user's 2026-10-07 instruction: no Git CLI calls anywhere in the codebase; delete tests that call Git. This covers product, development tools, tests, native build definitions and repository-owned workflow shells. Git commands used by a developer to manage this repository are outside executable project code. External checkout/package-manager implementations and forge REST endpoints are not repository-owned Git CLI invocations.

Preserve assertions, cleanup protections, release identity and publication guards. Do not replace missing evidence with fabricated counts or identity. Reference comparisons use explicit supplied trees. Build numbering has an explicit positive integer input, with a development default. Missing CI change metadata selects the complete gate rather than an empty change set. Pytest uses plain assertions and does not synthesize comparison diffs.

## Implementation

Remove direct Git callers and Git-specific tests. Use the owning filesystem inventory and ignore policy for cleanup. Remove automatic worktree-secret discovery. Use content hashes for local delivery labels. Pass changed paths as a file, with full-tree selection when absent. Publish generated release files through authenticated forge APIs. Packaging tests install staged local formula/manifests without constructing repositories. Enforce the prohibition with a codebase-wide executable-call gate.

## Rationale

The filesystem and explicit inputs describe the actual subject under test, including source snapshots and uncommitted changes. Repository history and a Git process are unnecessary dependencies for those subjects.

## Consequences

The Git-based mechanisms named in earlier CI and packaging records are retired under this instruction. The 2026-09-17 CI decision keeps its lane and correctness obligations; change selection no longer runs a local Git diff. Native identities keep their existing owner. This changes implementation inputs, not release publication authority. Actual implementation and verification are recorded separately.
