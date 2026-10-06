---
tags:
  - '#audit'
  - '#google-client-provisioning'
date: '2026-10-06'
modified: '2026-10-06'
body_schema: 'body-v2'
body_hash: 'sha256:7ee46e2d651e9e6e5a20a624b1096ba9d6e417c01cece94a47ee2a66a4c9f3bb'
related:
  - "[[2026-10-06-google-client-provisioning-plan]]"
  - "[[2026-10-04-google-app-identity-adr]]"
---

# `google-client-provisioning` audit: Credential provisioning and history removal

## Scope

S01-S03, task-owned changes over the pre-task working-tree snapshots; rewritten Git HEAD bc2dafb1e66aefe7a7471f24b964686c180859a6 plus uncommitted implementation. Reviewed core Settings, OAuth adapter, ignored environment provisioning, Python artifacts, native CMake cache admission, Rust worker environment scrubbing, CI secret mapping and reachable history. Independent reviewer completed integrated review and correction review. Verdict: PASS for this scope; repository-wide checks are not green.

## Findings

### source-workers | medium | Development workers initially lost the client after environment scrubbing

The initial implementation depended on inherited settings in a source checkout, while profile workers deliberately remove that environment variable. Corrected within S02: development environment setup materializes the ignored resource through the same validated build helper. The regression exercises the actual child environment policy and core Settings fallback. Final reviewer confirmed resolution; 21 development-environment and provisioning tests passed.

### artifact-isolation | low | Initial rebuild test needed a clean process

Corrected: the sdist-to-wheel regression now runs under a fresh isolated Python process without credential environment or dotenv and asserts the loaded application/build modules originate from the extracted sdist. No remaining finding.

## Recommendations

No further in-scope correction remains. Preserve the repository secret as the CI build input; do not commit the generated resource or environment files. Distributed Desktop clients remain extractable public-client configuration; this change controls source publication, not binary confidentiality.

Verification: 129 focused OAuth/settings/environment-reference/provisioning tests passed, followed by 21 development-env/provisioning tests for the worker correction. Packaging worker reported 56 applicable packaging/cohort/cache tests passed, excluding two pre-existing authority-currency and interpreter-pin failures. Scoped Ruff, formatting, typing and the corrected dev import-classification contract passed. Workflow checks, Windows CMake configuration with docs enabled, native_contract and rust_application builds passed. Full repository style/format/type/import checks were run and failed on unrelated existing changes; the one task-owned type issue and dev classification issue were corrected and scoped checks passed. No live OAuth or complete installer acceptance was run.

History evidence: var/google-credential-history-scan.json identified one credential-bearing blob among 325010 scanned reachable blobs. The restricted rewrite changed 126 descendant commits, feature/tui, stash and affected detached recovery heads; unrelated commit trees were preserved. Final all-ref/reflog traversal no longer contains the credential blob or path. Remote feature/tui never contained the rejected commit and remains an ancestor. No push performed. This is reachable-history removal, not physical erasure of unreachable local objects.

Local credential values in main/env/.env and tui/env/.env were checked equal and ignored. GitHub accepted CADRUMO_GOOGLE_OAUTH_CLIENT_JSON; only its presence can be read back. No values are recorded here. Test logs are under var/storage/development/.logs/test-runs/2026-10-06; history results are in var/google-history-rewrite/result.json.
