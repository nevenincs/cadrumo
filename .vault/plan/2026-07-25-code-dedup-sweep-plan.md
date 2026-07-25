---
tags:
  - '#plan'
  - '#code-dedup-sweep'
date: '2026-07-25'
modified: '2026-07-26'
tier: L1
related:
  - '[[2026-07-25-code-dedup-sweep-adr]]'
  - '[[2026-07-25-code-dedup-sweep-rag-inventory-audit]]'
---


# `code-dedup-sweep` plan

- [x] `S01` - Land the non-raising inner-envelope equality predicate in the storage substrate beside the existing lineage policy, exported through the storage package facade, leaving ensure_schema_version_readable deliberately absent from that facade because it is the layer-one gate; `src/cadrumo/adapters/persistence/storage/`.
- [x] `S02` - Replace the inequality with the predicate at all twenty inner-envelope read paths in one atomic explicit-pathspec commit, each site keeping its exception class and translated message key and per-object context mapping unchanged, and the non-raising contract preserving the usage_ratios except-clause ordering; `10 sites in adapters/persistence/profile/, 4 in adapters/outbound/aeat/sede/_observation_store.py, 2 in application/workflow/_persistence.py, 2 in application/user_profile/_repository.py, application/live/_verify.py, application/live/_snapshot_base.py`.
- [x] `S03` - Add the structural AST gate refusing an inequality comparison of schema_version on a persisted inner-envelope read path, alias-aware rather than name-matching, shipping with a planted-violation anti-tautology proof modelled on commit a5d21ced8a; `src/cadrumo/adapters/persistence/storage/tests/`.
- [x] `S04` - Extend the lineage gate to pin the two facts the vacuity proof rests on, asserting each registered namespace's declared schema_version against the version its readers compare and the Envelope ge=1 floor, expressed as a relation rather than the literal 1 so a legitimate per-namespace bump does not red it; `src/cadrumo/adapters/persistence/storage/tests/test_schema_lineage.py`.
- [x] `S05` - Record the inner-re-stamp obligation on the upgrader registration surface so the first registered hop inherits it explicitly, without fabricating an old-shape fixture that no-legacy-compatibility forbids; `src/cadrumo/adapters/persistence/storage/_schema_lineage.py`.
- [x] `S06` - Rule the bucket-manifest version gap in its own decision record under the durability framing, a fourth persisted format hardcoded at create and passed through on save and read with no version gate of any kind, so a manifest written by a newer application is accepted silently; `storage/bucket/_manifest.py, storage/bucket/_manifest_io.py, application/user_profile/_profile_repository.py, new ADR`.
## Description

Executes the accepted inner-envelope decision. Twenty persisted read paths compare
the inner envelope's schema version with an inequality where the canonical
contract is equality, which is provably a no-op today and becomes the only
read-time detector of a half-written upgrader once the first version bump lands.
The knockout criterion is cost asymmetry across the regime flip, not present-day
risk: the same edit after the flip is a hard refusal newly applied to data a
taxpayer has already filed.

S01 through S05 are the decision. S06 is a distinct decision the ADR surfaced and
deliberately did not fold in — a fourth persisted format read with no version gate
at all, which is a stronger gap than this plan's own subject and needs its own
record rather than an implementer's judgement.

## Steps

S01 lands the predicate. S02 sweeps the twenty sites onto it. S03 and S04 make the
state durable with a structural gate and a lineage-gate addition. S05 records the
upgrader obligation. S06 is a separate ruling, not implementation.

## Parallelization

S01 blocks S02, and S02 must land as one atomic explicit-pathspec commit rather
than a per-site drip. A half-swept tree leaves the substrate straddling two
contracts, which in this shared worktree is worse than either endpoint and
invites a peer to copy whichever shape they happen to read first.

S03 and S04 are independent of each other and both follow S02 — running the
structural gate against a half-swept tree would red it for the right reason at the
wrong time. S05 is independent throughout. S06 shares no files with any other step
and can be taken by a separate owner at any point.

Re-read HEAD before editing any of the twenty sites. Several sit in files under
active peer campaigns, and `git diff` on a target file must be clean of
non-authored work before the first edit.

## Verification

The tightening MUST be behaviour-identical at every current version. Prove it
rather than assert it: the argument depends jointly on every namespace sitting at
its declared version and on the envelope field's floor, and S04 pins both.

Run the persistence roundtrip suites that carry both gate kinds the earlier refuted
consolidation would have broken — the save-load strict-equality roundtrips and the
mutate-the-payload-and-assert-refusal proofs, including the future-inner-stamp and
inner-drift cases that assert exact message keys and context mappings. Those
context assertions are the real gate on S02: they fail if any site's error identity
moved.

Select markers explicitly rather than relying on the repo default, which deselects
integration-marked modules and exits green on nothing. Re-run any serial test the
xdist scheduler held. The S03 gate is not verified by passing — it is verified by
its planted-violation proof failing when the gate is removed.
