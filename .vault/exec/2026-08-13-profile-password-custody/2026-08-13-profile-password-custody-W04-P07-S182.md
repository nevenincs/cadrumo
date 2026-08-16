---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:d9f3637c723f89afdcd3251ac7c6929d36ac82e6a63a8fadbeb03440c0515f84'
step_id: 'S182'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh settle the disposition of the orphaned bucket-identity canonicaliser and fold every private duplicate of it in one change, since the module the authority package was told to fold onto has zero references anywhere and is not exported, so attaching a live consumer to it would bind working code to a module another lane may delete, while four sites across the authority, modelo signing, recipient encryption and usage-ratio packages each carry their own private copy of one identity rule

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/_bucket_identity.py and src/cadrumo/core/identity/ and src/cadrumo/application/auth/_apoderado.py and src/cadrumo/application/modelo/ and src/cadrumo/domain/usage_ratios/`

## Description

- Relocate the orphaned bucket-identity canonicaliser out of the storage
  master-key package into the identity package, beside the alias it enforces.
- Delete the orphan at its old site.
- Fold every private copy of the rule onto the canonical one, judging each on
  whether it restates the rule or only translates its refusal.
- Add an agreement test so the writer's spelling and the reader's recognition
  cannot diverge.

## Outcome

The Step's premise was that four sites each kept a private copy of one identity
rule while the module they were to be folded onto had zero references and was
not exported. Both halves held.

The canonicaliser now lives in the identity package beside the alias it defers
to, and its docstring records why it had no owner before: it was defined in the
storage master-key package with no consumer at all while four call sites each
kept their own copy. A shared rule with four copies and no canonical home is
the shape that lets the copies diverge silently, and two spellings of one
bucket composing different addresses means one taxpayer's data addressed two
ways.

Three of the four sites folded. The fourth did NOT, and deliberately: the
usage-ratio wrapper does not restate the rule, it translates the shared
refusal into that domain's own error class. That is precisely the arrangement
the canonical prescribes — it raises the plain builtin so it does not impose
one surface's error class on every other — so deleting it would have been a
wrong removal dressed as canonicalisation.

The authority-package copy was the genuine remaining duplicate and the worst
shape of the four: it re-derived the rule through its own type adapter while a
local variable shadowed the canonical name, so one file held both an
independent implementation and the canonical import. It now delegates, and the
dead adapter and its import are gone.

One consuming test moved from asserting the pydantic validation class to
asserting the plain builtin. That is not a weakening: the property under test
is the refusal, the exception class was incidental to the old local
implementation, and the pydantic error subclasses the builtin so the assertion
holds whichever the boundary raises.

## Notes

Found by meaning rather than by name. A name-stem sweep could not have found
these: the copies shared no common identifier with the canonical, which is the
same reason they were able to drift apart in the first place.
