---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
step_id: 'S139'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh re-found the four modules whose subject IS the creation surface rather than converting them

## Scope

- `src/cadrumo/entrypoints/cli/_config/tests/`

## Description

- Establish per module whether the subject survives, rather than assuming the
  four share one answer.
- Check existing coverage before relocating anything.
- Retire only with the superseding test named.

## Outcome

The four split four ways, and the largest module went from nineteen tests to
seven at a net deletion of well over three hundred lines. Verified
independently: four passed, three failed, with each failure name mapping to a
rowed defect.

**The governing fact corrected the campaign's framing.** Creation is not gone;
NON-INTERACTIVE creation is, by design. The verb still exists and is still the
advertised entry point, diverting on a capable terminal to the profile manager
and registering through the credential-first door; on a console-less host — every
test process — it refuses. The retirement is coherent with password custody
rather than incidental to it, because a passphrase cannot be safely supplied on
a command line. That withdrew most of a standing escalation.

**The four remaining passes are real coverage**: two edit refusals whose fixtures
now register through the credential door, and two foral refusals that fire
before the retirement check.

**The three remaining failures are held deliberately, and each is the only
in-tree evidence of a defect that would otherwise exist solely in a vault row** —
the lost next-action guidance, the unenforced legal-form requirement, and the
crash on an event type absent from its own enum. A passing test would erase each
of them, so none was rewritten to assert the broken state.

Thirteen retirements are each named in the module docstring with what answers
them: three have no successor because the capability is gone by design, six are
answered by the application completeness suites at the layer that decides them,
two by the wizard catalogue that owns flag-to-fact mapping, one loses only its
create half, and one has no home at all because its subject is the CONTENT of an
operator message and the application layer does not render operator text.

## Notes

**What the row bought is not visible in its count.** Nineteen tests were
anticipated for relocation; four were touched. The value was that making a dead
path reachable exposed three defects nobody was looking for: a live operator
guidance obligation lost when creation moved surfaces, a requirement the retired
path enforced that no surviving surface enforces and the schema does not back —
with a corporate-tax-rate consequence — and a surviving verb that crashes on an
invalid event type.

**Two techniques did most of the work and both generalise.**

Classifying by the FAILING LINE rather than by the failure message: when one
guard preempts a module, every test fails identically and the message says
nothing about which subjects survived. Setup-line failures mean the test's own
assertion was never reached. The qualifier that keeps it honest is that "failed
in setup" is not "subject untouched" — where the setup call IS the subject, the
subject is genuinely retired.

And checking existing coverage before relocating: nine of ten candidate
relocations turned out redundant against a suite that already proved the same
property at the layer that decides it. Relocating them would have authored a
second proof of one fact.

The retirements rest on scripted creation being retired, which holds regardless
of how the legal-form question is ruled; the record keeps the two dispositions
separate so a later reader cannot read one as contingent on the other.
