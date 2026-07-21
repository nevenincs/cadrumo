---
tags:
  - '#audit'
  - '#docs-static-deployment'
date: '2026-07-11'
modified: '2026-07-11'
related:
  - "[[2026-07-10-docs-static-deployment-plan]]"
---
# `docs-static-deployment` audit: `Pagefind delivery repair`

## Scope

Review Pagefind, docs deployment, and closeout controls.

## Findings

### pagefind-delivery | pass | Find no critical or high issue.

Verify Pagefind writes once, excludes `_modules`, and keeps a Windows copy fallback.

### deploy-safety | pass | Find no critical or high issue.

Require the fixed stack, alias, strict serial build, sitemap, and Pagefind artifacts before upload.

### pagefind-api-exclusion | pass | Find no critical or high issue.

Keep generated `api` and `_modules` files public but outside Pagefind.

### pagefind-pages-mode | pass | Find no critical or high issue.

Keep full record injection by default and validate deploy pages mode.

### deployment-sitemap | pass | Find no critical or high issue.

Write canonical human and CLI URLs while excluding generated API and source pages.

### delivery-verification | high | Deploy does not verify public endpoints.

Require canonical, legacy, missing-page, and private-origin checks after invalidation.

### deployment-atomicity | medium | Direct sync can expose a partial release.

Stage immutable releases before switching the live origin.

### human-gate | medium | Automation can bypass the deploy confirmation.

Refuse deployment when continuous-integration context is detected.

### operator-runbook | low | No-change stack deployments need no rerun.

Accept a successful no-change result.

## Recommendations

Add endpoint verification, immutable release staging, and continuous-integration refusal.
