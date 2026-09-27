---
tags:
  - '#plan'
  - '#docs-delivery-hardening'
date: '2026-09-27'
tier: L1
related:
  - '[[2026-09-27-website-repository-boundary-docs-static-delivery-adr]]'
  - '[[2026-07-21-ci-discipline-adr]]'
modified: '2026-09-27'
body_schema: body-v2
body_hash: 'sha256:c363c39aa1f1c5d06bdd9bb6780bd329fb959ae291c8db3acf8cb29ac7d1a529'
---

# `docs-delivery-hardening` plan

## Description

Approved 2026-09-27

Authorization: the user instructed "Action and fix the findings" after reviewing the Cadrumo audit. Implement the accepted static delivery successor, preserving existing content and both mounts. The governing decision replaces only documentation delivery in the prior Cloudflare decision. Code, tests, live configuration, and recovery evidence belong to this feature; other application work stays untouched.

## Steps

- [x] `S01` - Implement verified static manifests and serialized recoverable publication; `dev/deploy/docs_asset_delivery.py, dev/deploy/docs_asset_manifest.py, dev/deploy/r2_objects.py, dev/deploy/tests/test_docs_asset_delivery.py`.
- [x] `S02` - Integrate publishing rollback monitoring and CI safeguards; `dev/deploy/, dev/quality/metadata/import_load_targets.json, .github/workflows/release.yml, .github/workflows/docs-health.yml, RELEASING.md, justfile, dev/tests/test_lane_reachability.py, worker/`.
- [x] `S03` - Migrate the verified release configure scoped delivery and validate production; `dev/deploy/, dev/docs/tests/test_docs_build.py, docs/_templates/base.html, .github/workflows/docs-health.yml, var/docs-hardening/, .vault/audit/`.

## Parallelization

Execute sequentially with one writer. No delegated assignments.

## Verification

Focused publisher tests prove manifest integrity, incomplete-release rejection, deployment locking, static path preservation, file limits, and recovery. Lint and type checks cover changed Python. Live staging and public tests cover both mounts, all language roots, search navigation, 404, redirects, validators, ranges, CORS, warm caching, scoped TLS, and unchanged landing content. Inspect deployed metadata to prove no executable module. Confirm no new Worker executions for documentation delivery. Record configuration snapshots and a final integrated audit before completion.
