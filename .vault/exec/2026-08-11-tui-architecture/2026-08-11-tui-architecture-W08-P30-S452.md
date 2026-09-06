---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:5601ca662a4ced24d74178eafcdb064d8d566894f05d7c7abb43c4b822564eff'
step_id: 'S452'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Re-apply the reconciliation direction key rename the concurrent writer reverted, and record why nothing caught it. The catalogue kept the corrected shape while the committed source went back to the old keys, so the surface asked for keys the catalogue no longer holds. It rendered anyway: tr() humanises an unknown key into title-cased prose from its last segment, so a missing key reads as a plausible English label in every locale while the authored translation sits unused.

## Scope

- `src/cadrumo/entrypoints/tui/ledger/reconciliation.py`
- `src/cadrumo/entrypoints/tui/ledger/controller.py`

## Changes

The S449 rename was reverted in the committed source for the FOURTH time, and
chasing why nobody noticed found something larger than the revert.

State on arrival: all four catalogues carried the corrected shape --
`direction` a leaf, `direction_state` holding the two values -- while HEAD's
reconciliation.py and controller.py asked for `direction.invoice_only`. The
catalogue half of S449 was committed and survived; the source half was not and
was overwritten. git status showed both files clean, so this arrived in a commit
rather than an edit.

TR() DOES NOT FAIL ON A MISSING KEY. It humanises one. Measured directly:

    tr("tui.ledger.reconciliation.direction.invoice_only") -> "Invoice only"
    tr("a.b.c.not_a_real_key")                             -> "Not a real key"

So the reverted surface rendered "Invoice only" and "Transaction only" in EVERY
locale, including Spanish, while the authored Spanish -- "Solo la factura cita
el apunte" -- sat unused at the new key. No exception, no marker, nothing in a
log. A missing translation is indistinguishable from a real English label, which
is why a revert of exactly this kind can survive review and a test run.

That is the honest reason the parity gate matters at all. It is not tidiness:
for the general key path it is the ONLY thing standing between a mistyped or
stale key and a screen that looks translated and is not. The strictness that
raises MissingTranslationError, which this campaign leaned on throughout,
applies to the modelo schema surface rather than to keys generally.

Re-applied; Spanish now resolves and the shadowing gate passes.

## Notes

THIS NEEDS COMMITTING TO STOP RECURRING. The fix is two lines across two files
and has now been lost four times. Each loss is silent for the reason above. I
have not committed anything this session and will not without being asked, but
the asymmetry is worth stating plainly: the catalogue edits survive because they
were committed by the other writer, and the source edits do not.

The humanising fallback is recorded as a finding, not fixed. Making tr() strict
generally would change behaviour for every unresolved key in the product and is
a decision about failure mode, not a defect to correct quietly in a locale step.
