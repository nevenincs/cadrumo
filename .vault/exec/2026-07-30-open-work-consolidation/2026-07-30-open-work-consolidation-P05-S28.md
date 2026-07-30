---
tags:
  - '#exec'
  - '#open-work-consolidation'
date: '2026-07-30'
modified: '2026-07-30'
body_schema: 'body-v1'
step_id: 'S28'
related:
  - "[[2026-07-30-open-work-consolidation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace open-work-consolidation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S28 and 2026-07-30-open-work-consolidation-plan placeholders are machine-filled by
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
     The Assess whether the same post-auth failure spends a Clave Permanente credential, a question recorded only inline in one step record and tracked nowhere, escalating to a coding campaign with a discovery gate if it proves a defect and ## Scope

- `src/cadrumo/adapters/outbound/aeat/auth/_clave_permanente_support.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Assess whether the same post-auth failure spends a Clave Permanente credential, a question recorded only inline in one step record and tracked nowhere, escalating to a coding campaign with a discovery gate if it proves a defect

## Scope

- `src/cadrumo/adapters/outbound/aeat/auth/_clave_permanente_support.py`

## Description

- Read the Cl@ve Permanente provider, its support and metadata modules, and the shared session store, probe, and browser-lifecycle helpers.
- Compare its fresh-login capture path against the Cl@ve Movil path that commits `37e6e931ba` and `d0e2ca4bea` repaired.
- Establish whether an accepted-credential-but-failed-navigation window exists for Permanente.
- Establish what credential a discarded Permanente session actually costs, which decides the severity.
- Confirm the finding at HEAD independently rather than accepting the investigating agent report.

## Outcome

Permanente IS exposed to the same structural defect, and the severity is materially lower than Movil.

The structural parity is real and confirmed at HEAD. In `_clave_permanente.py`, `_capture_fresh_login_state` reads `storage_state()` only on the success path, and its `except` branch closes the context, closes the browser session, and re-raises without ever reading the state first. A `POST_AUTH_LANDING_TIMEOUT` raised while waiting for the SSO redirect therefore propagates through that unsalvaging branch, tearing down a context whose credentials the identity provider has already accepted. This is the same shape as the pre-fix Movil code. A tree-wide search confirms the string `salvage` appears only in the Movil module and its test, so nothing analogous exists for Permanente, and `_is_authenticated_aeat_landing` already exists on the Permanente provider, so the landing-filter half of the Movil remedy has a ready counterpart.

The severity diverges sharply on credential cost, which is the crux and the reason this is not simply a second instance of the same bug. Movil spends a single-use, device-bound approval that the operator must physically grant inside a non-extendable window, so discarding an accepted session imposes a real human cost. Permanente authenticates with a reusable identifier and password read from settings, so re-authenticating after a discarded context is a headless resubmission with no operator interaction and no device. SMS-OTP elevation never enters this path: the provider detects the elevation marker and refuses immediately rather than driving an OTP step, so no second factor is consumed or wasted.

The remedy is a small, well-scoped port of the existing pattern rather than a design problem, and it is genuinely a port rather than an inheritance fix, because the two providers do not share the flow-driving code. Movil drives its flow through a page-flow mixin while Permanente implements its own capture, form-driving, and landing-wait directly, which is why the Movil commits did not carry over.

## Notes

The assessment closes; the remediation does not, and deliberately does not enter this plan. The governing decision rules that a row found to need code leaves this non-coding plan for a coding campaign with a semantic-discovery gate in front of it. The gate was unavailable for the whole of this session, so no code was written and none should be until it is healthy.

Two things stayed unverified and both bear on priority rather than on the finding. Whether repeated successful-but-late logins can trigger a Cl@ve lockout or anti-automation challenge is unestablished, and if it can, the salvage becomes a mitigation for that risk rather than a convenience, which would raise its priority. Whether `POST_AUTH_LANDING_TIMEOUT` has ever actually fired outside a test is also unestablished, and live-log evidence either way would settle how often the window is really hit.

The honest framing for a later reader: this row asked a question that had been sitting unexamined inside another step record with nothing tracking it, and the answer is that the gap is real, cheap to close, and low-cost to leave open for now. It should not be quietly dropped on the grounds of low severity, because low severity plus a cheap fix plus an existing proven pattern is the combination most likely to be forgotten rather than decided.
