---
tags:
  - '#audit'
  - '#casilla-schema'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:0821a46e35427404ddd60ca9f8e283b936bd9f84efeb069911e96ffb385b33cd'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
  - "[[2026-08-10-casilla-schema-read-model-adr]]"
  - "[[2026-08-10-casilla-schema-research]]"
---
# `casilla-schema` audit: `S22 calculation binding channel facade`

## Scope

Reviewed W03.P07.S22 against the accepted read-model decision, campaign plan, research, application boundaries, and repository quality constraints. Scope was limited to the `application.modelo` facade and `test_calculation_resolution.py`. The required contract is promotion of the existing private-owner `resolve_calculation_binding_channels` function through the application facade as the exact same object, without a wrapper, alias declaration, compatibility bridge, or second implementation.

## Findings

No actionable S22 findings.

The facade imports `resolve_calculation_binding_channels` directly from `_calculation_resolution` and lists that imported name in `__all__`. It does not define a wrapper, assign a renamed compatibility symbol, or copy any resolution logic. Runtime inspection confirms the facade attribute is the owner function by identity, and the scoped source census finds exactly one function definition in `_calculation_resolution.py`.

This is the correct architectural boundary for S23: the accepted read-model decision requires the review-record producer to consume the existing calculation binding-channel answer through the public `application.modelo` surface before the record is introduced. Ownership remains in `_calculation_resolution`; only discoverability and supported import routing change.

The direct regression imports the public facade and owner module and asserts exact identity. It does not reconstruct the channel resolver, construct a shadow function, or use a fake, stub, mock, patch, monkeypatch, skip, or expected-failure construct. The existing real replay-payload behavior test remains intact and green.

## Verification

- Fresh VaultSpec semantic discovery located the accepted read-model decision, plan prerequisite, and relevant research; the code search service timed out twice under load, after which exact scoped source inspection completed the owner/facade trace.
- Focused owning test module: 2 passed.
- Scoped Ruff: passed.
- Scoped strict BasedPyright: 0 errors, 0 warnings, 0 notes.
- Scoped `git diff --check`: passed.
- Runtime facade identity: passed.
- Sole-definition census: one `def resolve_calculation_binding_channels`, in `_calculation_resolution.py`.
- Scoped diff: one direct facade import, one `__all__` entry, and one identity assertion; no compatibility or duplicate authority.

## Recommendations

No corrective action is required for S22. S23 should import `resolve_calculation_binding_channels` from the `application.modelo` facade rather than reaching back into `_calculation_resolution` or recreating its grouping behavior.

Verdict: **PASS.** W03.P07.S22 promotes the existing canonical binding-channel resolver as one exact public identity and introduces no wrapper, compatibility layer, duplicate implementation, or test shortcut.
