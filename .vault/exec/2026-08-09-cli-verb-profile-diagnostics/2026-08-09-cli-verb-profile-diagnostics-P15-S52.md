---
tags:
  - '#exec'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:ac2852afc9f33b2c1614e3107987a43ad1657b497e438016fa383a17fe5fefd3'
step_id: 'S52'
related:
  - "[[2026-08-09-cli-verb-profile-diagnostics-plan]]"
---
# Record the registered profile-preflight-missing error that carries an unactionable message and has no raise site anywhere in production

## Scope

- `src/cadrumo/core/errors/registry/_domain_part3.py`

## Description

- Traced the unactionable refusal the behaviour census surfaced: "Modelo preflight could not find a required profile selector. Complete the profile before continuing."
- Searched the whole source tree for anything that raises the error class bound to it.

## Outcome

**Recorded, not actioned.** The error class is declared, exported from its package facade, and bound to a registered error code with that message - and **nothing in the tree raises it**. Zero raise sites.

The message would be a clear defect if it could reach an operator: it reports that a required profile selector is missing while naming neither the selector nor the field, and it uses internal vocabulary an operator has no way to act on. But no code path can emit it, so it reaches nobody.

Two reasons this is recorded rather than fixed. Grounding a message that cannot fire would be work with no observable effect, and would leave the dormant class looking live. Deleting the class instead reaches into the error registry, whose parity gates and code table are a different surface from operator-facing refusal text, and dormant-capacity cleanup is a different concern from this campaign's.

What matters for whoever picks it up: if this error is ever wired to a real path, its message must carry the missing requirement rather than assert one exists. Every comparable refusal in this campaign now does.

## Verification

    rg -n 'ProfilePreflightMissingError' src/cadrumo --type py

Four references: the class definition, two facade export lines, and the error-registry binding. A targeted search for raise sites returns zero.

## Notes

Found by the behaviour-scoped census rather than by the dotted-token censuses, because the defect here is not a raw identifier but the ABSENCE of any identifier where the message asserts one is missing. That is the same class as the bare-count diagnostics summary corrected earlier, surviving in a message nothing emits.
