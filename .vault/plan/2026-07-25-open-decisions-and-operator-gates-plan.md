---
tags:
  - '#plan'
  - '#open-decisions-and-operator-gates'
date: '2026-07-25'
modified: '2026-07-28'
body_hash: 'sha256:9c834b7231b145ff194f4a63487be38cdc2007a73defaf4bd248faf2d94af730'
tier: L1
related:
  - '[[2026-07-25-test-harness-honesty-plan]]'
  - '[[2026-07-25-account-distribution-standard-plan]]'
  - '[[2026-07-24-profile-login-session-plan]]'
  - '[[2026-07-25-code-dedup-sweep-adr]]'
  - '[[2026-07-25-reconcile-evidence-relocation-adr]]'
  - '[[2026-07-24-evidence-revision-identity-adr]]'
  - '[[2026-07-25-account-distribution-standard-adr]]'
  - '[[2026-07-25-open-decisions-and-operator-gates-three-rulings-audit]]'
---
# `open-decisions-and-operator-gates` plan

- [x] `S01` - DECISION OPEN, rule on the code-dedup-sweep ADR which sits at proposed with no plan and no exec records, since dedup work has already landed against it and an unruled record leaves that work ungoverned; `.vault/adr/2026-07-25-code-dedup-sweep-adr.md`.
- [x] `S02` - DECISION OPEN, rule on the reconcile-evidence-relocation ADR which sits at proposed with no plan, noting its own audit records the payload overflow as a systemic four-instance shape rather than a single defect; `.vault/adr/2026-07-25-reconcile-evidence-relocation-adr.md`.
- [x] `S03` - DECISION OPEN, rule on the evidence-revision-identity ADR which sits at proposed with no plan, and which has a companion operator-walkthrough audit already written against it; `.vault/adr/2026-07-24-evidence-revision-identity-adr.md`.
- [x] `S04` - OPERATOR ONLY, run just test-os-keychain from an interactive desktop session, because six custody-bound cases covering session minting and the idempotence guard and silent resume have never been observed green on any host, an agent SSH network logon cannot supply the credential, and the cases are excluded from every lane including CI so this is a recurring obligation rather than a one-time sign-off, re-opened by any change to login or logout or resume or session-key custody; `operator action, interactive desktop session`.
- [x] `S05` - OPERATOR ONLY, decide whether to publish the local commit backlog to the now-public repository, since every push carries all ancestors and one agent pushing publishes the whole fleet's work, and force-push is categorically forbidden so a superseded record is corrected forward rather than rewritten; `operator action, git push to origin main`.
- [x] `S06` - OPERATOR ONLY, add the renamed distribution secrets because secrets cannot be renamed only re-created, and the old product-prefixed secrets still hold the values while the workflows now read the account-scoped names; `operator action, gh secret set HOMEBREW_TAP_TOKEN and CLAUDE_MARKETPLACE_TOKEN`.
- [x] `S07` - OPERATOR ONLY, delete the stale pre-rename plugin entry from the public marketplace, because the marketplace declares the old product name so the documented install command cannot resolve against it today; `operator action, nevenincs/neve-marketplace plugins and marketplace.json`.
- [x] `S08` - OPERATOR ONLY, arm publication by setting the publish-enabled repository variable, deliberately left unset so Gate 1 refuses, which every downstream acquisition and reacquisition step is blocked behind; `operator action, gh variable set CADRUMO_PUBLISH_ENABLED`.
- [x] `S09` - OPERATOR ONLY, confirm branch protection on the default branch admits the publish workflow if any release-time write to that branch survives the final topology, since that coupling did not exist before the repository went public; `operator action, nevenincs/cadrumo branch protection`.
- [x] `S10` - Review the secret-scanning findings over full history, enabled on this repository at the moment it went public with push protection, since scanning had never run against the private history before publication; `operator action, nevenincs/cadrumo secret scanning alerts`.
## Description

## Steps

## Parallelization

## Verification

## Context

A fresh reader should be able to see, from plan status alone, both what is undecided and what is blocked on a human. This plan carries the decisions sitting at proposed with no ruling, and the actions no agent may take: outward-facing publication, repository lifecycle, host configuration, and any verification requiring an interactive desktop logon. Nothing here is agent-executable; every step names why.
