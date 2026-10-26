---
tags:
  - '#plan'
  - '#google-client-provisioning'
date: '2026-10-06'
tier: L1
related:
  - '[[2026-10-04-google-app-identity-adr]]'
  - '[[2026-10-04-canonical-environment-adr]]'
modified: '2026-10-06'
body_schema: body-v2
body_hash: 'sha256:2c844ec66a5e52283e5e4709b84deb67d0adce23b69237b38911dfd02baa0d81'
---

# `google-client-provisioning` plan

## Description

Approved 2026-10-06. The user explicitly requested moving the Google client out of Git and its history into main/env/.env, tui/env/.env and GitHub repository secrets, core Settings ownership, and unchanged local and CI native sign-in. This supersedes only the earlier Google identity ADR commitment to source-control the client. The full installed-client JSON is preserved under CADRUMO_GOOGLE_OAUTH_CLIENT_JSON, a secret-valued core setting. Build artifacts embed that setting's validated configuration; installed processes need no dotenv or inherited credentials. No credentials enter committed examples, generated contracts, logs or command arguments.

## Steps

- [x] `S01` - Move publisher OAuth resolution into core Settings with a packaged fallback; `src/cadrumo/core, src/cadrumo/adapters/outbound/google, env/.env.example, docs/reference/environment-overrides.md`.
- [x] `S02` - Provision validated OAuth metadata into Python and native artifacts and ignored development-worker resources from build environment and local dotenv; `dev/packaging, dev/env, packaging, native, .importlinter`.
- [x] `S03` - Install local and GitHub credentials, wire CI, purge credential history, and verify integrated delivery; `.github/workflows, .gitignore, ignored env/.env files, Git refs, .vault`.

## Parallelization

S01 core/settings and OAuth loader may run concurrently with S02 build provisioning, using the agreed CADRUMO_GOOGLE_OAUTH_CLIENT_JSON field and packaged _data/google/oauth_client.json fallback contract. S01 owns src/cadrumo/core/config_google.py, config.py, OAuth installation_client.py and their tests, env/.env.example and generated env reference. S02 owns packaging build hook, dev/packaging, CMake and native packaging tests. The supervisor owns .github workflows, ignored local environments, GitHub secret writes, Git history, ADR reconciliation, shared checks, all commits and final review. Workers must preserve concurrent edits and must not commit.

## Verification

Verify synthetic settings precedence, missing/malformed refusal and redaction, packaged fallback without environment, OAuth flow compatibility, build input refresh on credential changes, CMake/native artifact inclusion, CI secret mapping, ignored local environments and repository secret names. Run scoped tests and configured lint, formatting, type and import checks. Purge the credential path and exact values from affected reachable Git history while preserving worktrees and verify no reachable match. Keep runtime OAuth calls out of tests.

## Context

The user authorizes local credential provisioning and GitHub repository secret writes. History cleanup must preserve unrelated work and stash contents.
