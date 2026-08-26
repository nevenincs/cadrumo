---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:93f4d84b75dafa0943b2d3f3e48fb0694193d6abcd74e7e4747d855cc3848af3'
step_id: 'S67'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Complete the close honesty review by verifying D1 through D7 against the live tree

## Scope

- `.vault/audit/`

## Changes

- `M` `.vault/plan/2026-08-26-cli-root-verb-homes-plan.md`
- `verify:` `each decision checked against COMMAND_GRAPH, the shipped gates and the synced rule` -> `D5 was contradicted and is amended (S66); D1-D4, D6, D7 hold`

## Notes

The close review asks one question of each decision: is this true of the tree,
not of the plan. Seven decisions, checked individually.

**D1 holds.** The placement gate refuses per subject from declared policy and is
silent on the subjects carrying no signal, exactly as D1 says it must be. The
residue that silence leaves was separately judged in S60.

**D2 holds.** Transport verbs are keyed on the counterparty; no leaf declaring a
transport locus wears a retired token; `get` was the last one and went in S45.

**D3 holds.** Option spelling is refused on the DECLARED locus rather than a
name list or a `Path` guess, which was the point of the precondition.

**D4 holds.** `file` names exactly one leaf, `app modelo work file`, and the gate
asserts that rather than trusting it.

**D5 did NOT hold and is amended** — recorded in full at S66. The record forbade
the verb the tree ships.

**D6 holds, including the part easiest to skip.** It promises two gates and both
ship. Its exemption discipline is real: the spelling gate's exemptions carry a
stated reason, are keyed to a live parameter, and
`test_every_exemption_still_names_a_live_parameter` fails a stale one instead of
letting it linger and silently excuse a future parameter.

**D7 holds, all four corrections verified in the synced rule**: the `config` root
help no longer claims diagnostics it does not own; the opening paragraph is
widened from AEAT to the remote counterparty; the dual-transport sentence reads
"subgroup of `pull` and `import --file`"; the `censo import --file` example is
there and the dead `_data/agent` path is gone, replaced by `src/cadrumo-harness`.

**One inaccuracy of this campaign's own making, corrected here.** The S39 row and
the close audit's addendum both described the verb-grammar gate as "the gate D6
promised". D6 promises the placement gate and the spelling gate; it does not
promise a verb-grammar gate. That gate enforces D2 and is additional to what the
record committed to — good work, wrongly attributed. The row now says so.

What this review does not establish: that the criterion in S60 is enforced. It is
judgement recorded in prose, and a future subject could be mounted against it
with nothing going red.
