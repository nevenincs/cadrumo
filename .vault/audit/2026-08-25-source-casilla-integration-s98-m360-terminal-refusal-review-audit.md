---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:6c9d9dece0d80be390bc0884804a8ce9058c631f2a6682cedb62522357efecab'
related:
  - "[[2026-08-22-source-casilla-integration-W05-P16-S98]]"
---

# `source-casilla-integration` audit: `S98 M360 terminal refusal review`

## Scope

Independent review of commit `1a76517bcc` and its current-head S98 proof surface: M360 `REFUND_OPERATION` refusal at calculation ingress, the separate M360 `manual_input` route, the census closure projection, and repeated-record export boundary.

## Findings

No actionable findings. The negative proof is limited to `REFUND_OPERATION`: it remains deferred, advisory-visible, absent from resolver ownership and connected fixtures, and cannot claim a projection-row export. It separately verifies the actual `manual_input` binding route remains present. The closure projection is refused with the M360 census work item and exact reopening condition, so the deferral is reviewable rather than silently terminal. No runtime route, registry declaration, or parallel source authority was added.

## Recommendations

Keep the direct source-mesh proof and refusal coverage aligned with the S97 reopening predicate. The exact full-authority coverage test did not complete within this environment's 30-second focused-runner cap during review; retain its current assertion and re-run it in a longer isolated CI lane before any change to the M360 disposition.
