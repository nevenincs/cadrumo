---
tags:
  - '#exec'
  - '#canonical-release-pipeline'
date: '2026-07-27'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:3b1e1755dd4efad4f989ba0fdc73a0492a689d12d57615d5390464297634f683'
related:
  - "[[2026-07-27-canonical-release-pipeline-plan]]"
---

# `canonical-release-pipeline` ledger

## Changes

- `S01` `T` `dev/release/burned_versions.toml`
- `S01` `T` `dev/release/version_identity.py`
- `S01` `T` `dev/release/tests/test_burned_versions.py`
- `S02` `T` `dev/release/promote_python_cohort.py`
- `S02` `T` `dev/release/version_identity.py`
- `S02` `T` `dev/release/tests/test_promote_python_cohort.py`
- `S03` `T` `.github/workflows/packaging-smoke.yml`
- `S03` `T` `dev/packaging/tests/`
- `S04` `T` `.github/workflows/publish-release.yml`
- `S04` `T` `dev/release/tests/test_publish_release_workflow.py`
- `S05` `T` `.github/workflows/publish-release.yml`
- `S05` `T` `dev/release/tests/test_publish_release_workflow.py`
- `S06` `T` `.github/workflows/publish-release.yml`
- `S06` `T` `dev/packaging/marketplace_publish.py`
- `S06` `T` `dev/release/tests/`
- `S07` `T` `.github/workflows/pypi-upload.yml`
- `S07` `T` `dev/release/tests/test_pypi_upload_workflow.py`
- `S08` `T` `dev/packaging/release_cohort.py`
- `S08` `T` `dev/packaging/cohort_manifest.py`
- `S08` `T` `dev/packaging/tests/`
- `S09` `T` `dev/packaging/marketplace_publish.py`
- `S09` `T` `dev/packaging/tests/`
- `S10` `T` `dev/packaging/marketplace_publish.py`
- `S10` `T` `.github/workflows/publish-release.yml`
- `S10` `T` `dev/packaging/tests/`
- `S11` `T` `dev/quality/tests/test_doc_privacy.py`
- `S12` `T` `dev/quality/tests/test_doc_privacy.py`
- `S13` `T` `.github/workflows/docs-publish.yml`
- `S13` `T` `dev/deploy/tests/`
- `S14` `T` `dev/deploy/docs_static_site.py`
- `S14` `T` `dev/deploy/frontend_static_site.py`
- `S14` `T` `dev/deploy/tests/`
- `S15` `T` `docs/`
- `S15` `T` `dev/docs/tests/`
- `S16` `T` `.vault/audit/`
- `S17` `T` `.github/workflows/ci-full.yml`
- `S17` `T` `dev/ci/tests/`
- `S18` `T` `dev/ci/tests/test_lane_reachability.py`
