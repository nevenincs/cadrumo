---
tags:
  - '#exec'
  - '#censal-profile-autofill'
date: '2026-07-26'
modified: '2026-07-26'
step_id: 'S34'
related:
  - "[[2026-07-25-censal-profile-autofill-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace censal-profile-autofill with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S34 and 2026-07-25-censal-profile-autofill-plan placeholders are machine-filled by
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
     The Refuse a live session when an active profile carries no fiscal identity, closing the certificate path where a cleared field disarmed both the credential guard and the deferred session comparison, gated by a sweep over the whole provider enum and ## Scope

- `src/cadrumo/application/auth/_sessions.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Refuse a live session when an active profile carries no fiscal identity, closing the certificate path where a cleared field disarmed both the credential guard and the deferred session comparison, gated by a sweep over the whole provider enum

## Scope

- `src/cadrumo/application/auth/_sessions.py`

## Description

- Establish by execution that a profile's fiscal identity can be cleared after
  creation, that the profile remains promoted afterwards, and that the
  certificate provider then reaches a live bind with neither guard refusing.
- Establish, also by execution, that a profile still in setup can be minted
  carrying no facts at all, which decides the refusal's shape.
- Carry the profile's lifecycle status onto the auth facts projection, since
  distinguishing an identity never recorded from one recorded and later removed
  needs the record and not just its values.
- Refuse at the point where the deferred comparison's expectation is chosen,
  inside the branch only a provider without an operator-configured credential
  reaches, leaving the existing credential-side refusal untouched.
- Exempt a profile still in setup, and leave the no-profile case to the
  refusals that already own it rather than answering it with a message about
  restoring a field.
- Add the operator-facing refusal in all four locales through the locale CLI.
- Gate the property across every provider rather than the one that was missed.

## Outcome

The path is closed at the auth layer for a promoted profile. The refusal is one
branch; the gate is a sweep over the provider enum, asserting that no provider
binds a session against a blank profile identity, so a provider added later
that reaches a different line is covered by a test that already exists.

Verification: the auth application suite passes at 221, and the credential
surfaces at the CLI boundary pass in both the unit and integration lanes, run
without workers so no serial test was held out. Lint, format and type check
clean.

The anti-tautology check behaved informatively rather than merely passing.
Neutering the refusal reddens the certificate arm of the sweep and leaves the
two Cl@ve arms green, because those are defended by the older credential-side
refusal. That is the correct reading: the sweep asserts a property that
several guards jointly uphold, and it names which provider depends on which.

## Notes

This closes one of two doors. The refusal covers a promoted profile whose
identity was removed, which is the state proven reachable. A profile still in
setup is deliberately allowed to authenticate, so the equivalent protection
for that case has to come from the guard on the read it performs, which is
owned elsewhere. Until that lands the window is narrower - it needs a profile
mid-setup rather than any profile - but it is not closed, and this record
should not be read as closing it.

The end-to-end path from a bound foreign session through to an adopted read is
strongly indicated and was not executed here. What is proven is that both
guards decline to refuse. The remaining link is being confirmed against an
existing reproduction harness rather than a second one built here.

One fact about this module rather than a general claim: the profile
registration command's documentation states that a profile minted at the start
of setup has its fiscal id reserved, and nothing enforces that - the early-mint
arm validates shape only and accepts zero facts. This is the third place in
this subsystem where documentation asserts a guarantee the code does not make,
after the credential guard's fail-closed description and the deferred check's
description of where the certificate is compared. All three were load-bearing
for a security property, and all three were believed before being tested.
