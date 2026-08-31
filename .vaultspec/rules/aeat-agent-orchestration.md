# AEAT execution ownership

## Invariants

- The person or agent delivering a change owns its evidence: inspect the live tree, verify any delegated finding, and report only the state that still exists at handoff.
- Delegation is optional. Use it only when the operator permits it and the work can be split without losing the context needed for correctness. No task requires a swarm, standing team, role count, vendor, or launcher.
- Give one writer ownership of each shared file or tightly coupled surface. Coordinate overlapping work before editing and preserve unrelated worktree changes.
- A plan, issue, agent transcript, or prior audit is orientation, never proof that code is correct or work is complete. Acceptance comes from the current source, authoritative evidence, and the gates that exercise the changed behavior.
- Make reversible choices from the repository when they stay within the requested scope. Do not use autonomy to broaden authorization, publish externally, write live AEAT systems, or discard another contributor's work.
- Re-read affected files and the current diff before acting on a finding or handing work off; concurrent work can invalidate an earlier inventory.
- Report blockers precisely. Pre-existing failures remain visible, but they do not justify hiding a regression introduced by the current change.

## Handoff

A handoff states the outcome, changed surfaces, validation run with exit status, and any remaining risk. Agent topology, campaign history, and private scratch reasoning are not project facts and do not belong in source code or durable documentation.
