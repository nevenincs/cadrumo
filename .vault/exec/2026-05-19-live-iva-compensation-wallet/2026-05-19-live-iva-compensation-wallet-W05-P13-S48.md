---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-07-05'
modified: '2026-07-05'
step_id: 'S48'
related:
  - "[[2026-05-19-live-iva-compensation-wallet-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace live-iva-compensation-wallet with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S48 and 2026-05-19-live-iva-compensation-wallet-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Add real-behavior diagnostic tests that use production auth diagnostics and redaction logic without private taxpayer fixtures, fakes, stubs, or monkeypatched browser behavior. Partial 2026-05-26: `src/aeat/application/auth/test_diagnostics.py` now drives the real secure-object diagnostic read model with sanitized payloads and centralized AEAT route constants and ## Scope

- `live-driver regression coverage remains open. Completed 2026-05-27: the real `ClaveMovilAuthProvider` attempt-context path is exercised against active profile secure storage and sanitized Cl@ve settings`
- `proving route/mode/profile/support diagnostics are present while raw DNI/NIE and support values are absent. Review follow-up 2026-05-27: active profile identifiers and labels are now emitted only as redacted references/presence booleans in Cl@ve diagnostics`
- `and an accidental secure-storage plan/audit inclusion was removed by a dedicated repair commit`
- `src/aeat/application/auth src/aeat/adapters/outbound/aeat/auth` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add real-behavior diagnostic tests that use production auth diagnostics and redaction logic without private taxpayer fixtures, fakes, stubs, or monkeypatched browser behavior. Partial 2026-05-26: `src/aeat/application/auth/test_diagnostics.py` now drives the real secure-object diagnostic read model with sanitized payloads and centralized AEAT route constants

## Scope

- `live-driver regression coverage remains open. Completed 2026-05-27: the real `ClaveMovilAuthProvider` attempt-context path is exercised against active profile secure storage and sanitized Cl@ve settings`
- `proving route/mode/profile/support diagnostics are present while raw DNI/NIE and support values are absent. Review follow-up 2026-05-27: active profile identifiers and labels are now emitted only as redacted references/presence booleans in Cl@ve diagnostics`
- `and an accidental secure-storage plan/audit inclusion was removed by a dedicated repair commit`
- `src/aeat/application/auth src/aeat/adapters/outbound/aeat/auth`

## Description

- Reconciled this historical checked plan row to a canonical per-step exec record.
- Verified the row remains checked in `2026-05-19-live-iva-compensation-wallet-plan` at HEAD.
- Preserved the plan row, source tree, and prior exec/audit artifacts unchanged.

## Outcome

`vaultspec-core vault add exec` created this record with a `step_id` matching the checked row. The implementation evidence is the current checked plan row plus the feature source, tests, and audits already referenced by that row and its scope; this pass repairs traceability for `plan-closure-requires-exec-records` only.

## Notes

No new code, live AEAT access, plan checkbox change, source kind, resolver convention, or validator convention was introduced. The standing open live verification row `W06.P15.S56` remains separate and is not closed by this reconciliation.