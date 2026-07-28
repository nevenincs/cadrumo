---
tags:
  - '#exec'
  - '#homebrew-arm64-pac-ret'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S05'
related:
  - "[[2026-07-25-homebrew-arm64-pac-ret-plan]]"
---

# Decide and record whether homebrew-linux-arm64 is claimed or dropped from the support matrix if the toolchain fault proves unresolvable, because an unclaimed row must not silently read as an untested claim

## Scope

- `docs/updates.md`
- `.vault/adr/`

## Description

- Establish whether this step's condition -- the toolchain fault proving unresolvable -- actually triggered.
- Read the accepted decision record's ruling on the row's support status.
- Verify the mechanism that stops an unproven row from reading as a tested claim, rather than assuming the documentation is worded safely.

## Outcome

The condition did not trigger. The toolchain fault is resolved and proven on the real reproducer, so the branch this step guarded -- drop the row from the support matrix -- never opened.

The row is CLAIMED, at full scope. That is the accepted decision record's own ruling: the Linux arm64 evidence row stays required and no support-level carve-out is needed, because the mitigation is scoped to the tier that faults and the primary distribution channel already ships without the hardening in question.

The protection against a silent untested claim is structural rather than editorial. A user-facing acquisition instruction is only permitted when a self-consistent evidence record with a passing status exists on disk for every row backing that instruction. The documentation currently issues no positive Homebrew install instruction, so nothing is claimed ahead of its proof, and the gate passes -- 13 passed. Two of the three Homebrew rows hold passing records; the Linux arm64 row does not yet, and minting it is the remaining step.

## Notes

"Claimed" here means retained in the support matrix, not proven. The distinction is the point of this step: the row is committed to, its evidence is still owed, and the gate keeps those two facts from being conflated.

The gate is not green merely by being inert. Its corpus scan finds nothing while every channel is pre-launch, so it carries an explicit positive control pinning each pattern's match and non-match behaviour, including that a negation preceding a command is a disclaimer rather than a claim. A pattern set that stopped discriminating would fail the control even with the corpus silent -- so the passing result reflects a working instrument, not an empty one.
