---
tags:
  - '#plan'
  - '#docs-delivery-hardening'
date: '2026-09-27'
tier: L1
related:
  - '[[2026-09-27-website-repository-boundary-docs-static-delivery-adr]]'
modified: '2026-09-27'
body_schema: body-v2
body_hash: 'sha256:ce272cdd0aacbac082bb4216a82165344577b441ae9e19154173fd947c3e1d49'
---

# `docs-delivery-hardening` plan

## Description

Approved 2026-09-27

Authorization: the user instructed "Action and fix the findings" after reviewing the Cadrumo audit. Implement the accepted static delivery successor, preserving existing content and both mounts. The governing decision replaces only documentation delivery in the prior Cloudflare decision. Code, tests, live configuration, and recovery evidence belong to this feature; other application work stays untouched.

## Steps

- [x] `S01` - Implement verified static manifests and serialized recoverable publication; `dev/deploy/docs_asset_delivery.py, dev/deploy/docs_asset_manifest.py, dev/deploy/r2_objects.py, dev/deploy/tests/test_docs_asset_delivery.py`.
- [ ] `S02` - Integrate publishing rollback monitoring and CI safeguards; `dev/deploy/docs_static_site.py, dev/deploy/docs_delivery_settings.py, .github/workflows/release.yml, .github/workflows/docs-health.yml, dev/deploy/tests/, docs/development/`.
- [ ] `S03` - Migrate the verified release configure scoped delivery and validate production; `dev/deploy/, var/docs-hardening/, .vault/audit/`.

## Parallelization

Execute sequentially with one writer. No delegated assignments.

## Verification

Focused publisher tests prove manifest integrity, incomplete-release rejection, deployment locking, static path preservation, file limits, and recovery. Lint and type checks cover changed Python. Live staging and public tests cover both mounts, all language roots, search navigation, 404, redirects, validators, ranges, CORS, warm caching, scoped TLS, and unchanged landing content. Inspect deployed metadata to prove no executable module. Confirm no new Worker executions for documentation delivery. Record configuration snapshots and a final integrated audit before completion.
