---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:664cc5ce7b8f3dd699cd84a4886dc5361e64f6ca1ac90ae6483cb6e145adee98'
step_id: 'S66'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Close-review finding: the accepted ADR still forbade in five places the verb the operator ruled and the tree ships, and its Rationale defended the rejected option

## Scope

- `.vault/adr/2026-08-26-cli-root-verb-homes-adr.md`

## Changes

- `M` `.vault/adr/2026-08-26-cli-root-verb-homes-adr.md`
- `verify:` `python -c "...COMMAND_GRAPH archive subject..."` -> `export, import, inspect, push, reconcile`
- `verify:` `vaultspec-core vault check all` -> `no finding naming this feature`

## Notes

Found by opening the close honesty review the orchestration rule requires, and
asking the question a fresh reviewer asks first: does the tree satisfy the
decisions the accepted ADR actually states?

It did not, on D5. The record says in five places that the whole-corpus Drive
mirror lives under a `mirror` subject, and says explicitly that it **does NOT
join** the `archive` subject, giving a reason: "`archive` implies a thing you can
restore, and the mirror cannot be read back — putting it under `archive` would
promise recoverability that does not exist." The tree ships `config profile
archive push`, which is precisely the arrangement that sentence forbids.

The operator ruled that change three days of work ago, rejecting `mirror` as a
subject noun. The close audit recorded the ruling. The ADR was never amended for
it — and this ADR carries two other amendments in exactly the right style, at D2
for the CREATING verb category and at D5 for the registry-integrity
non-retirement, so the omission is not a house-style question. Its Rationale
section was still arguing, at length, FOR the option that lost.

That is the `aeat-agent-orchestration` failure inverted. The rule warns that an
ADR amendment ruling on code is not self-executing; here the CODE moved and the
record did not, so a reader consulting the governing decision would have been
told that what shipped is forbidden, for a stated safety-shaped reason.

The amendment answers the original objection rather than overruling it, because
the objection was sound: the danger was that `archive` promises a round trip.
The answer is that the VERB carries the promise, not the subject. `push` beside a
working `export` / `import` pair makes the absent `pull` loud on every help
listing, where `mirror push` was quiet because the subject told the reader
nothing to expect. The declared gap is unchanged and still owes a follow-on
record.

The superseded text is retained and marked, matching the two existing
amendments, so the reasoning that was displaced stays readable.

The close review is not finished; this is its first finding.
