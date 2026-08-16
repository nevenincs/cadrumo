---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:6a18e6048df7c69a62620399db73a04bccba06741c9574e12055c49ed4adaa17'
step_id: 'S185'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium rewrite the data-protection operator guide against the accepted per-profile recovery decision, since the page was stripped to state that the passphrase is the only key and nothing recovers without it, which was true of the tree at that moment and is no longer the accepted direction, and a guide that understates a recovery route is the mirror of the false assurance it was stripped to remove

## Scope

- `docs/how-to/protect-data-access.md`

## Description

- Correct the two claims the page made that the shipped work falsified.
- Document the recovery phrase: what it is, when it appears, that it appears
  once, and that it cannot be added later.
- Document the passphrase change verb and both of its retention guarantees.
- State plainly what an operator cannot yet do, rather than implying it.

## Outcome

The page asserted, in its own words, that Cadrumo "ships no command to change
it and no command to recover access without it", and that losing the passphrase
leaves a reset as the only way forward. Both were true when written. Neither is
true now: credential rotation ships as a first-class verb, and a profile
created at a terminal is enrolled for recovery at the moment it is created.

The Step frames the danger precisely -- a guide that understates a recovery
route is the mirror of the false assurance it was stripped to remove -- and the
correction has to avoid BOTH errors, which is the whole difficulty. Recovery
enrolment ships; the command that OPENS a profile from a recovery phrase does
not. Telling an operator they can recover today would be the original false
assurance wearing the opposite sign.

So the page now says exactly what is true: the phrase is shown once, on the
terminal only, is never written to a file or an export or a log, and no copy is
kept, so nobody can show it again. It says the phrase exists only for a profile
created at a terminal, because a scripted run has nowhere safe to display it
and therefore mints none. It says enrolment happens only during creation and
cannot be added afterwards. And it says to keep the phrase even though it
cannot yet be used alone, naming that the opening command is not in this
release -- which is what stops an operator discarding the one artifact that
preserves their future ability to recover.

The rotation section states the two facts an operator actually needs after
changing a credential: no record is re-encrypted so everything still opens, and
a recovery phrase written down earlier is still correct. Both are reported by
the command itself, so the page is describing behaviour rather than promising
it. The non-interactive form is documented on the bounded stdin channel, with
the reason a command-line argument is never acceptable.

The verb was also added to the curated operator help surface, which no gate
scans and which the command-line contract rule requires be swept by hand.

## Notes

The nitpicky documentation build cannot be run to completion at present: the
site build invokes a casilla-reference generator that loads the modelo
registry, and the registry refuses tree-wide while a concurrent campaign
authors several modelos. Sixteen of the seventeen documentation checks pass;
the failing one is that whole-site build, and it fails before reaching this
page. Re-run it once the registry loads again.

What this row did NOT do: it documents the recovery phrase as an artifact to
keep, not as a route an operator can walk. The restore and restore-recover
verbs are separate open rows, and the page will need a further pass naming them
once they ship.
