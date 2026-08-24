---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:d50937760efde9f4353ba66783547e73fb4a22bb2de1c5ce1670526371ca0aee'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
  - "[[2026-08-13-profile-password-custody-rollup-adr]]"
  - "[[2026-08-18-profile-password-custody-campaign-close-audit]]"
  - "[[2026-08-13-profile-password-custody-W03-P05-S206]]"
  - "[[2026-08-13-profile-password-custody-W03-P06-S195]]"
  - "[[2026-08-13-profile-password-custody-W03-P06-S209]]"
---

# `profile-password-custody` audit: `fresh-context campaign close`

## Scope

Fresh-context honesty review of the completed 209-row campaign at current
`HEAD` after `b1a81de241`, `2dea32b0bb`, and `4cb16d0ca0`. The review compared
the plan, governing accepted decisions, phase summary, the earlier campaign-close
audit, all Step-record filenames, the S195, S206, and S209 execution and review
records, and the current recovery and supervised-KDF implementation and tests.
It also searched current source, operator documentation, and lifecycle records
for pending or narrowed claims. Unrelated dirty peer work was excluded.

The mechanical closure ledger is complete: the plan contains 209 checked,
unique Step identifiers and every identifier has one matching execution-record
filename. S195 now carries the previously deferred green anti-tautology witness;
S206 carries recovery-parity implementation and resolved review evidence; S209
carries the full WSL descriptor-attestation matrix and independent review. No
checked row is missing its Step record.

## Findings

### empty-execution-evidence | high | A checked Step has a scaffold but no execution evidence

The filename bijection is complete, but it is not an evidence bijection.
`W04.P07.S148` is checked while its execution record has empty Description,
Outcome, and Notes sections; it records only the planned scope. Nothing in that
record says what changed, what passed, whether the row was deferred, or where
equivalent evidence lives. Twenty-one further checked Step records fail the
attested body schema through empty required sections, including S172 with no
Outcome heading; most of those retain substantial evidence elsewhere in their
record, but S148 is a pure scaffold. A placeholder file cannot satisfy the
campaign-close requirement that a checked row have matching execution or
formal deferral evidence.

Concrete action: reopen S148 until its implementation and verification are
re-derived at current HEAD and persisted through the execution-record verb, or
formally defer it with a linked carry-forward in the close audit. Reconcile the
remaining 21 body-schema warnings, starting with S172's missing Outcome, and
rerun the feature-scoped body-sections and exec-mapping checks before closure.

### recovery-decision-drift | high | Mandatory creation-time recovery contradicts the accepted custody decision

S206 and current operator documentation correctly remove the irreversible
password-only creation outcome from every supported CLI and TUI creation lane,
but the governing accepted roll-up still declares recovery optional, says
enrollment occurs after activation, and concludes that recovery becomes
optional. The plan row goes further and says the accepted decision places
enrollment at creation, which is false of the cited ADR. The current application
primitive also still accepts no recovery handoff and documents that omission as
a permanent no-recovery outcome. Thus the safer shipped product behavior is not
an implementation of the accepted architecture; it is an unrecorded reversal
of it. Under the campaign-close rule, an ADR ruling on code is not
self-executing, and code cannot silently amend an ADR either. Closure is not
honest while the architecture authority and implementation disagree.

Concrete action: amend or supersede the custody roll-up through the ADR verb to
decide mandatory verified recovery at creation, explicitly rule whether the
application registration primitive may remain optional for non-operator callers,
and open implementing Steps in the same action for every residual code or prose
change. Re-run the S206 matrix and this honesty review before closure.

### machine-secret-governance-link | medium | The plan omits a decision that governs its final descriptor work

The roll-up delegates headless scalar-secret transport to
`2026-08-23-cli-machine-secret-channel-unification-adr`, and S209's execution
and review records rely on that decision for exact descriptor and platform
semantics. The plan's `related` list does not include it, despite the vault rule
that a roll-up plan list every governing ADR. This breaks the plan-to-decision
trace precisely at the security boundary S209 closes.

Concrete action: add the machine-secret-channel ADR to the plan through the
owning plan edit verb, regenerate the feature index, and verify the plan and
feature with Vaultspec checks.

### historical-close-prose | low | The earlier close audit still reads as the current terminal closure

The 2026-08-18 close audit says the campaign closes at 206 of 208 and records
S195 and S206 as deferred. Those statements were accurate history, and the new
execution records resolve both carry-forwards, but there is no supersession note
inside that audit and its title remains indistinguishable from a terminal close.
A reader landing on it without chronology can still conclude that S206 remains
unbuilt.

Concrete action: preserve the historical evidence but use the vault audit edit
verb to add a concise supersession pointer to this fresh-context audit after the
HIGH and MEDIUM actions close; do not rewrite the historical measurements.

## Recommendations

Do not approve campaign closure yet. Reconcile the mandatory recovery decision
first, enroll the machine-secret ADR in the plan's governing set, and mark the
older close audit as historical. Then repeat the exact 209-row/record bijection,
targeted stale-prose search, S206 recovery matrix, S209 platform gate, and
feature-scoped Vaultspec validation. S195, S206, and S209 need no new
implementation finding beyond the decision reconciliation above.
