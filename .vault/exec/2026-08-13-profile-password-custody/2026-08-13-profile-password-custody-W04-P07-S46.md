---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:34ae57d33604168f3bd3d98988a7ba1e30f1fde05898ab27dee2dd6eb580cad5'
step_id: 'S46'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh retire the dead operator instructions left by the cutover

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/ and src/cadrumo/entrypoints/cli/ and src/cadrumo/application/setup/tests/ and src/cadrumo/application/tests/`

## Description

- Establish by invocation which cited verbs actually resolve, before writing
  any replacement text.
- Rewrite the torn-install refusal, the forgotten-passphrase refusal, both
  already-provisioned refusals, the unsupported-key-schedule refusal and the
  bucket-DEK missing-wrap refusal to state that no in-app repair exists,
  naming no verb, and to point at preserving the secret-store directory rather
  than removing it.
- Drop the three retired verb spellings from the runtime bootstrap-exempt
  allowlist, which the gates do not scan and which fails open when stale.
- Delete the terminal-writing helper that existed only to display a retired
  recovery phrase, together with its reviewed-write allowlist entry.
- Delete the two gates whose subject was retired, repoint the one whose
  property survives at the verb that still holds it, and delete the one that
  had gone vacuous because every argument list exited non-zero for want of the
  command rather than for the reason asserted.
- Absorb all three retired spellings into a single gate refusing a quiet
  re-mount.
- Delete the error registration for a refusal whose behaviour is also gone.
- Repoint the emission declarations at their real sites and the crash-injection
  map at the transaction that actually clears the pointer.
- Replace the hardcoded coupling tally with a staleness assertion, the
  sanctioned pair set beside it already deciding what may exist.

## Outcome

No refusal now names a verb that does not resolve.

The reach was wider than reported. Both instructions in the torn-install
refusal were dead, not one: the recovery verb and the profile-creation verb it
offered as the safe alternative. A third, the passphrase-change verb, was
found dead in two further refusals. The retirement of the recovery family is
documented in the tree, so those citations are stale text over a real
retirement; the profile-creation verb is not, and reads as a regression, so
its citations were deliberately left standing rather than stripped, since
removing them would fight the gate that requires them.

Three of the four emission declarations were wrong rather than two, and one
declared event has no production emitter at all: the operator edit path writes
facts while stamping strings outside the event taxonomy. That was pinned as a
gap that fails when it closes, rather than reclassified as reserved under an
assertion that cannot fail.

Two gates were proven to bite through runtime patches applied from outside the
repository. Restoring the unguarded terminal read reds the secure-input gate
with the echo warning it exists to catch; re-mounting the retired verb group
reds the retirement gate. A first probe attempt did not bite because a second
guard caught it, which is worth as much as a probe that does.

## Notes

The crash-injection repair is correct by construction but unproven end to end.
All eleven parametrised boundaries are red for an unrelated reason, an
authenticated retention assessment now being required before deletion, so the
harness never reaches an injection point. That also corrects the earlier
reading that the mis-pointed boundary was silently passing: it is failing, and
the failure masks the stale map rather than hiding behind a green result.

One escalation was ruled rather than actioned. A boundary ledger is red on a
coupling the cutover introduced, and enrolling it would widen a documented
boundary to bless a dependency the removal step is scheduled to delete, which
would leave an orphan blessing a coupling that no longer exists. It stays red
until that step resolves it.

Several red gates were left deliberately: entries whose coupling is inverted,
pins unresolved by a concurrent relocation, and unenrolled writers. All sit in
files being edited concurrently, and acting on a snapshot of a contended file
is what produced an index collision earlier in this campaign.

The locale leaf for the deleted refusal is removed in the working tree but
uncommitted, riding a concurrent catalogue sweep rather than capturing that
sweep's work.

A follow-up is recorded separately: enrolling the retired spellings in the
scan that already walks source, catalogues, documentation and the sequence
contracts would make a dead operator instruction structurally impossible, but
sixteen surfaces still cite them, including a whole workflow document and the
repair-policy inventory. That is a campaign rather than a step.
