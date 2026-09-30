---
tags:
  - '#exec'
  - '#docs-delivery-hardening'
date: '2026-09-27'
modified: '2026-09-29'
body_schema: 'body-v2'
body_hash: 'sha256:07e30c35522bbd074313d956e8ecf2bc5933c906f1125f17cbbfae59fb2904a4'
related:
  - "[[2026-09-27-docs-delivery-hardening-plan]]"
---

# `docs-delivery-hardening` ledger

## Changes

- `S01` `A` `dev/deploy/docs_asset_manifest.py`
- `S01` `A` `dev/deploy/docs_asset_delivery.py`
- `S01` `M` `dev/deploy/r2_objects.py`
- `S01` `A` `dev/deploy/tests/test_docs_asset_delivery.py`
- `S01` `verify:` `Focused publisher tests 7 passed; Ruff and ty` -> `pass`
- `S02` `M` `dev/deploy/docs_static_site.py`
- `S02` `M` `dev/deploy/docs_asset_delivery.py`
- `S02` `M` `dev/deploy/docs_asset_manifest.py`
- `S02` `A` `dev/deploy/docs_delivery_settings.py`
- `S02` `A` `dev/deploy/docs_health.py`
- `S02` `M` `.github/workflows/release.yml`
- `S02` `A` `.github/workflows/docs-health.yml`
- `S02` `M` `RELEASING.md`
- `S02` `M` `dev/deploy/tests/test_docs_asset_delivery.py`
- `S02` `M` `dev/deploy/tests/test_docs_delivery.py`
- `S02` `verify:` `105 unit tests plus 37 integration tests including one registry-race rerun` -> `pass`
- `S02` `verify:` `Ruff, ty, actionlint and zizmor` -> `pass`
- `S02` `M` `dev/deploy/cloudflare_api.py`
- `S02` `D` `dev/deploy/tests/test_docs_worker.py`
- `S02` `D` `worker/docs-site.mjs`
- `S02` `D` `worker/docs-site.test.mjs`
- `S02` `M` `justfile`
- `S02` `M` `dev/tests/test_lane_reachability.py`
- `S02` `A` `.vault/audit/2026-09-27-docs-delivery-hardening-audit.md`
- `S02` `verify:` `Final focused deployment lane 103 tests; Ruff ty actionlint zizmor` -> `pass`
- `S03` `M` `.github/workflows/docs-health.yml`
- `S03` `M` `dev/deploy/docs_delivery_settings.py`
- `S03` `M` `dev/deploy/docs_static_site.py`
- `S03` `M` `dev/deploy/tests/test_docs_delivery.py`
- `S03` `M` `dev/docs/tests/test_docs_build.py`
- `S03` `A` `docs/_templates/base.html`
- `S03` `M` `.vault/audit/2026-09-27-docs-delivery-hardening-audit.md`
- `S03` `verify:` `Sealed inventories; 72 public directory byte comparisons; all language health probes; browser navigation; native delivery metadata; TLS and cache probes` -> `pass`
- `S03` `verify:` `Query-preservation checks, 24 focused publisher tests and real Sphinx identity render` -> `pass`
- `S02` `M` `dev/quality/metadata/import_load_targets.json`
- `S02` `verify:` `uv run --no-sync python -m dev.quality.import_gate` -> `pass`
- `S02` `verify:` `45 CI workflow contract tests` -> `pass`
- `S02` `verify:` `just check-workflows and check-workflow-security` -> `pass`

## Notes

- `S02` Six broader reachability failures enumerate an unrelated nested .claude worktree; retained untouched. Native mixed conditional precedence and per-host handshake minimum remain platform limitations.
