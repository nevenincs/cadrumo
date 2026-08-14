---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:643658545dd0d52f1133d1ae5cec855853c273de00b0c168d5f364e203eaf89e'
step_id: 'S92'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---

# Audit every fixture disposition against current consumers and lifecycle

## Scope

- `.vault/audit`

## Description

- Re-derive the redundancy measure from the census rather than trusting the execution records.
- Check each landed disposition against its current consumers and its autouse reach.
- Confirm no shared definition widened a lifecycle by moving into a package configuration file.
- Record where the measure behind the campaign's own remediation was wrong.

## Outcome

Every landed disposition preserves lifecycle. Reach and consumer counts were measured before and after each move and are unchanged; the encrypted-storage cluster has one definition reached through two package-configuration boundaries, which is pytest's requirement for exposing one fixture to two subtrees rather than duplication.

Of the four dispositions landed during the close phase, none is a flat merge. Each cluster's bodies were byte-identical while closing over a module-level constant whose value differed per file, so a flat merge would have pointed several modules' own later assertions at another module's record with every test still passing. Two now take the value through a dependency the consuming module overrides with a raising default, one takes it as a required positional with no default anywhere, and one moved its rendezvous object together with the fixture that closes over it. A further candidate was excluded on genuine body divergence.

No shared definition went into a package configuration file, which was the live trap: an autouse fixture defined in a module is autouse for that module alone, and the same fixture in a conftest reaches every test beside it.

## Notes

The audit's most consequential finding is against the campaign's own measurement. Grouping on whole-name identity understated the population; regrouping per cluster raised it to roughly fifty redundant definitions; including the owner globals the census already models, the count of genuinely substitutable clusters is zero. Most of the remediation this phase set out to perform therefore should not be performed, and the remaining large same-name groups were never dispatched.

Both corrections came from running the instrument rather than reading its output, and the decisive one came from an implementer who read the constants instead of the bodies. That is the durable lesson here: a body digest answers whether two fixtures execute the same statements, not whether they mean the same thing.
