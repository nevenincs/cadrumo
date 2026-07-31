---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-17'
body_hash: 'sha256:b6833773b9e675963aa343372430f204273d4f47d2ca158e6d1016fc5432d756'
step_id: 'S09'
related:
  - "[[2026-06-16-aeat-user-docs-hardening-plan]]"
---

# Harden file-at-aeat.md

## Scope

- `docs/how-to/file-at-aeat.md`

## Description

- Verify-close: read `file-at-aeat.md` in full against the hardening standard and confirm its audit findings are resolved at HEAD.
- Confirm the audit's own positive confirmation for this page: the never-submit safety boundary is stated correctly, and every cited in-tool command (`work revision`, `modelo export`, `work file --notes/--by`, `reconcile file`, `reconcile pull`) exists, takes the documented flags, and refuses cleanly for unverified drafts or missing markers.
- Confirm the ordered upload checklist correctly places the manual AEAT-portal step outside the tool and records the local `work file` marker only after portal submission.

## Outcome

- Page verified compliant at HEAD; the audit records `file-at-aeat` SAFETY as solid with all cited commands valid. Delta: none required.
- Imperative ordered checklist, prominent never-submit boundary, checksum-record guidance, cross-links resolve.

## Notes

- Residual m16 (invalid-PDF parser-internals leak on `reconcile`/`file-at-aeat`) is an APP-side typed-refusal finding, out of documentation-hardening scope. CLI conformance gate green.
