---
tags:
  - '#audit'
  - '#live-iva-compensation-wallet'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-27-live-iva-compensation-wallet-w05-p14-s49-auth-acquisition-outcomes-exec]]'
---

# `live-iva-compensation-wallet` S49 Code Review

S49-001 | HIGH | Required auth/outcome manifest fields would break older acquisition reloads
The S49 implementation correctly added redacted auth outcome and per-surface `outcome_mode` fields, but the first pass made those fields required on the persisted acquisition manifest models. Existing profile-local encrypted manifests from the immediately previous shape could therefore fail model validation during stored remote-state reload. The repair adds explicit legacy defaults for missing auth and surface outcome fields and covers that shape in `test_legacy_acquisition_manifest_without_auth_outcome_still_loads`.

No remaining critical or high issues were found in the local review after the compatibility repair. The changes remain read-only with respect to AEAT: they classify and persist acquisition outcomes only, and do not add any browser action, filing, payment, representation, or form-confirmation submission.
