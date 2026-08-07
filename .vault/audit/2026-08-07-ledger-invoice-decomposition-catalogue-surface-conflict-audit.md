---
tags:
  - '#audit'
  - '#ledger-invoice-decomposition'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:a00c45796cad369b37c4be78c865699f0516fc7a982c65583fc532a652eec0be'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---
# `ledger-invoice-decomposition` audit: P06.S55 targets a surface another campaign is retiring

## Summary

Step `P06.S55` of the ledger-invoice-decomposition plan directs an agent to wire
the simplificada issuer validator to an operator Notice, and to extend the
catalogue invoice creation entry point so it accepts an invoice class and an
optional tax id. Its premise still holds at HEAD: the validator has no production
caller, and the creation function takes a required counterparty tax id and no
invoice class.

The step is nonetheless not safe to execute, because a second in-flight campaign
is deleting the surface it names. The conflict is invisible from either plan
alone, which is why it is recorded here rather than resolved by editing code.

## The conflict

The invoice-canonical-structure plan carries five open steps whose whole purpose
is to collapse two invoice stores onto one aggregate. Two of them name this exact
surface: one repoints the five bare invoice verbs at the canonical aggregate and
retires the catalogue sub-noun outright, and another deletes the slim model, both
services, the repository, the storage namespace and the direction enum in one
atomic commit carrying every consumer.

So `P06.S55` asks for new capability on the catalogue creation path in the same
window that the other campaign retires the catalogue noun and deletes one of the
two stores behind it. Implementing it would add a caller to a function scheduled
for retirement, widen a signature that is about to be replaced, and hand the
deleting campaign an extra consumer to carry through its atomic commit.

The ledger plan contains no mention of the retirement, so an agent picking up
`P06.S55` from that plan alone sees a well-formed step with a verified premise
and no reason to hesitate.

## Why the premise check is not sufficient here

The usual guard against a decayed step is to re-verify its premise at HEAD. That
guard passes here and still gives the wrong answer: the premise describes what is
true now, while the hazard is what another campaign has already decided to make
false. A step can be simultaneously accurate about the present and obsolete.

The discriminator is ownership rather than truth. Before implementing a step that
names a shared surface, the question is not only whether its premise holds, but
whether another open plan claims that surface - and a plan whose steps say
`retire`, `delete`, `collapse` or `repoint` is claiming it.

## Recommendation

Leave `P06.S55` open and blocked rather than executed or silently dropped. Its
underlying intent is sound: a validator that is exported, tested and reachable by
no production path is dormant capacity, and the no-dormant-resolver discipline
says it should either be wired or removed.

Re-scope it once the canonical-structure campaign closes its P03 steps, against
whatever creation entry point survives the collapse. The wiring is then a single
call on one aggregate instead of a widened signature on a doomed one, and the
question of which store the Notice speaks for no longer arises.

No code was changed for this finding.
