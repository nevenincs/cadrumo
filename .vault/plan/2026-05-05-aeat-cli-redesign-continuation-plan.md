---
tags:
  - '#plan'
  - '#aeat-cli-redesign'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-02-aeat-cli-redesign-research]]'
  - '[[2026-05-02-aeat-cli-redesign-adr]]'
  - '[[2026-05-03-aeat-cli-redesign-audit]]'
---



# `aeat-cli-redesign` `continuation` plan

Continue the AEAT CLI redesign from the current in-progress ADR and backend
audit. This plan is an operational continuation record, not architectural
approval. The ADR remains in progress until a later review explicitly accepts
the command contract.

## Proposed Changes

Keep the user-facing command boundary strict: root exposes `setup` and `app`;
`app` exposes only `overview`, `ledger`, `invoice`, and `declaration`. Developer
and registry tooling must stay outside the user tree.

Preserve the declaration safety contract. Export writes local artifacts only.
Verify inspects local export artifacts only. No command may submit or mutate live
AEAT state.

Keep the CLI as a transport layer over application/domain APIs. Command handlers
may parse argv, call typed backend functions, and render results; they must not
own tax decisions, schema decisions, registry decisions, persistence rules, or
calculation logic.

Use the tape-derived messy tax workflows as regression drivers. The tapes should
continue to cover invalid imports, incomplete periods, duplicate statements,
wrong-account files, manual source-file checking, skip and unskip decisions,
mixed-use shares, invoice enrichment, late records, stale calculations, local
export refusal, local export verification, and recalculation after new evidence.

## Tasks

- Restore the user CLI boundary.
  1. Remove any reintroduced developer command group from `aeat app`.
  1. Add or keep tests that assert the visible root and app command sets.
  1. Scan active source and tests for transient implementation metadata.
- Stabilize declaration export and verify.
  1. Keep export and verify model-scoped so unrelated model registry work does
     not slow a single declaration command.
  1. Keep export local-only and verify file-based.
  1. Profile the export test path before broadening the CLI test matrix.
- Reconcile the ADR, audit, and implementation state.
  1. Do not mark the ADR approved.
  1. Record any implemented command surface as current delivery state against
     the in-progress ADR.
  1. Keep unresolved backend gaps visible instead of hiding them behind CLI
     wording.
- Replay tape-guided CLI workflows.
  1. Run help-surface checks for root, setup, app, and each app domain.
  1. Exercise ledger import, review, edit, skip, unskip, split, and invalid-file
     paths.
  1. Exercise invoice review, edit, match, document-link, retention, and payment
     paths.
  1. Exercise declaration calculate, review, approve, stale-calculation,
     validation, preview, export, verify, and recalculation paths.
- Close backend gaps only when they are directly required by the user CLI.
  1. Move any remaining schema or validation decisions out of the CLI layer.
  1. Keep profile, auth, ledger, invoice, declaration, and overview behavior in
     application/domain modules.
  1. Add real-behavior tests for the backend API before depending on it from the
     CLI.

## Parallelization

Run the work locally in small reviewable changes. Do not create scheduled jobs
or background continuation hooks. Separate unrelated registry or calculation
truth work from CLI commits so the user-facing interface can be reviewed and
reverted independently if needed.

## Verification

Success means the visible CLI reads as a tax-preparation product, not as a
developer toolset. Root help shows only `setup` and `app`. App help shows only
`overview`, `ledger`, `invoice`, and `declaration`. Command help uses consistent
user nouns and verbs. Declaration export and verification remain local-only.

Run the CLI surface tests, declaration export tests, formatting/lint checks for
touched files, and a source/test scan for transient run-state wording. Profile
the export test suite before expanding test coverage so slow paths are visible
instead of normalized.
