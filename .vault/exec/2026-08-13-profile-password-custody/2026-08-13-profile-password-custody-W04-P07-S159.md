---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:8490913ccef2d0b7c93f709b614d1e3953b443036810091300c8d7024729a915'
step_id: 'S159'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium resolve which side owns the schema version for the five fincas concepts that each declare it twice, once on the domain model and once on the ORM row as two independent literals nothing compares, deciding ownership from where the format is enrolled rather than sweeping both into one name, since two declarations of one record's current version is drift with no detector and this carries taxpayer data

## Scope

- `src/cadrumo/domain/fincas/ and src/cadrumo/adapters/persistence/`

## Description

- Read the mapper before ruling, since it decides which declaration is live.
- Name one constant per shape in the layer that declares it.
- Strike the persistence-row default and stop the docstrings restating it.

## Outcome

**The ownership question answered itself once the mapper was read: the row's
declaration was never live.** The repository copies `schema_version` in BOTH
directions at all five pairs — the record's value on write, the row's value on
read — so the column's own default was **never once exercised**. It was not a
competing declaration. It was a dead one standing ready to disagree, which makes
the risk latent rather than active and settles ownership on evidence rather than
on the layering principle. Both happened to point the same way; only one of them
was measured.

Five named constants now live in the module that declares the shapes, the five
column defaults are struck, and the docstrings that restated the value stopped
restating it. The number had been written twenty times — ten declarations and
ten docstrings — for five records. It is now written five times, once per shape.

**Five constants rather than one shared value, deliberately.** These are five
record shapes that can version independently, and a single constant would force
them to bump together for no reason the data supports.

**The awaiting-classification count went UP, from fourteen to nineteen, and that
is the result rather than a regression.** Naming a literal is not classifying a
format. These five were invisible to the binding gate precisely because it
discovers formats by constant NAME, so a version written as a bare literal could
not be seen at all. They are now visible and openly unclassified, which is the
only state from which they can be argued. The reason is written into the count
assertion's own docstring, because without it the next reader lowers the number
back and re-hides them.

Verification is the repository roundtrip and its anti-tautology arm rather than a
broad count: removing a NOT NULL column default surfaces as an integrity error on
any insert path the mapper does not cover, and there is no such path — all five
row constructions are in the mapper. Both format gates plus those tests pass at
twenty-four.

## Notes

The wider rental suite shows sixty-one failures under one ambient cause, a
registry validation error from a peer's evidence-tier sweep complaining that
bundled orden files carry no annex. Nothing to do with versions.

**The layering principle was tested against evidence in the sibling bundle step
and lost there**, and the two rulings should be read together. There the current
version stayed in the application layer because it, the durability floor, the
one-hop upgraders and the accepted-version set form one lineage unit that a
version bump must move as a whole; splitting it would have divided one atomic
obligation across layers. Here the evidence pointed at the declaring module
instead. The transferable part is that "which layer owns this" was answered by
reading what the code actually does in both cases, and the answers differed.

**A restatement in prose is the same defect as a second literal in code.** This
row stopped the docstrings restating the version for the same reason the sibling
step removed a docstring line claiming which versions are supported. This
campaign has repeatedly found a restatement being read as current long after it
stopped being true, and prose is where it survives longest because nothing
compiles it.

**No S164 inventory is carried here.** That row was assigned, then amended, then
stood down within the same turn, and no investigation of the two coexisting
custody packages was started — so there are no partial findings to preserve and
nothing was left half-landed. The inventory in the stand-down handover is the
lead's, not this row's.

**A capture hazard worth filing once.** Most of this work reached HEAD inside a
peer's broad registry-sweep commit rather than under its own message; what was
committed directly here is only the residue those captures missed. The
attribution cost is visible, but the sharper hazard is not: **if such a sweep
commit is ever reverted, it takes this work with it, and nothing in that commit's
message would warn whoever reverts it.** Four captures occurred in one day, which
is why the record rather than the git history is the durable attribution channel.
