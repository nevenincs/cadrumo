---
tags:
  - '#adr'
  - '#filing-draft-modelo-typing'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:722d453f57db1fae9fb2b9e0faf34d9b0c04ef211a743853bf5bd69b6cb28d95'
related:
  - "[[2026-08-07-canonical-identifiers-adr]]"
  - "[[2026-06-10-modelo-enum-hardening-adr]]"
  - '[[2026-09-02-filing-draft-modelo-typing-reference]]'
---

# `filing-draft-modelo-typing` adr: `Persisted draft modelo identifier is typed ModeloCode` | (**status:** `proposed`)

## Problem Statement

`ModeloDraft.modelo` in `src/cadrumo/domain/filing/schema.py:325` is declared
`str`. The draft is a persisted FINANCIAL secure object, so the declaration is
not only an annotation: it is the read-time acceptance contract applied to every
stored draft on rehydration. The field is the last bare-`str` modelo identifier
on a persisted filing aggregate - the sibling persisted records
`domain/modelos/work_unit.py:160`, `domain/modelos/filing_record.py:184`, and
`domain/modelos/participation_index.py:86` already declare `ModeloCode` through
the same envelope machinery - and consumers compensate for the gap by re-wrapping
at the read boundary (`application/modelo/workspace.py:187,2192,2203`) or by
accepting a `str | ModeloCode` union and coercing
(`application/modelo/filing_actions.py:502-514`). The type-checker burn-down
cannot close those seams while the source of the value is untyped, and the retype
cannot be taken casually because it changes what already-stored data is allowed
to be.

`2026-08-07-canonical-identifiers-adr` governs the identifier-retype class and
places this field outside its own enrollment: modelo codes are not one of the
four AEAT-issued document-identifier namespaces, and that record explicitly
scopes out the remaining unclassified fields of its 589-field census. It leaves
behind the constraint that binds here - a persisted-field retype requires a
strict roundtrip test with every defaultable field populated non-default plus an
anti-tautology proof - and the operator authorisation permitting Cadrumo's own
persisted data to be discarded and re-derived through the sanctioned teardown
authorities. `2026-06-10-modelo-enum-hardening-adr` settled the sibling question
for identifier literals in code and is not re-decided here.

## Considerations

- Three modelo representations coexist and are not interchangeable. `ModeloCode`
  (`domain/modelos/codes.py:16`) validates shape only: exactly three characters,
  all digits, raising `ModeloValidationError`, which subclasses `ValueError` and
  so surfaces through pydantic rather than escaping it. `ModeloId`
  (`domain/calculations/registry/ids.py:21`) is the registry's annotated alias for
  the identical three-digit shape. `Modelo` (`core/modelo.py:46`) is the closed
  roster of every identifier the codebase recognises; every member's value is
  exactly three digits, so the roster is a strict subset of what `ModeloCode`
  accepts.
- **What is on disk is already constrained to what `ModeloCode` accepts, by an
  invariant that predates this question.** `ModeloDraft.snapshot_ref` is a
  required, non-defaulted `RegistrySnapshotRef` whose own `modelo` field is
  `ModeloId`, and `_enforce_draft_invariants` refuses any draft where
  `self.modelo` differs from `self.snapshot_ref.modelo` (`schema.py:381-384`).
  Both run on rehydration. A stored draft whose modelo is padded, empty,
  four-digit, lower-cased, suffixed, or otherwise off-shape therefore fails to
  load today, under the existing type, before this decision changes anything. The
  set of drafts that load and the set that satisfy `ModeloCode` are the same set.
- The sole production writer closes the write side independently: `build_draft`
  (`application/filing/draft_construction.py:147-193`) derives `snapshot_ref` from
  `snapshot.modelo.id`, itself a `ModeloId`, and the cross-field validator rejects
  a caller-supplied modelo that disagrees with it. No production path can write an
  off-shape value.
- Drafts are encrypted secure objects in a per-profile bucket, FINANCIAL
  sensitivity, keyed by their content address under the object-key grammar
  `{draft_id}`. No plaintext draft corpus exists in the repository to inspect, so
  the argument above is the evidence: the acceptance set is established by the
  read path's own invariants, not by sampling stored files.
- The migration mechanism is `adapters/persistence/storage/schema_lineage.py`: a
  per-namespace, per-version registry of one-hop plaintext-bytes upgraders, an
  outer ceiling gate on the SQL row version, and an inner strict-equality gate on
  the envelope version. The filing-drafts namespace sits at secure-object schema
  version 2. **No production upgrader is registered for any namespace** - the only
  registrations in the tree are scratch-namespace test fixtures - which is that
  module's documented pre-release posture: durability floors chase their own
  current version and older shapes are deleted rather than migrated, until the
  checkpoint flip freezes the floors.
- `draft_id` is a SHA-256 content address over a payload that includes the modelo
  as a JSON string (`schema.py:486-496`). `ModeloCode` is a `str` subclass and
  serialises to the same JSON scalar, so no stored `draft_id` changes and no
  object key is orphaned. The repository re-derives and enforces that address on
  every write (`adapters/persistence/profile/filing_drafts.py:132-149`), so drift
  here would be loud rather than silent.
- `no-legacy-compatibility` requires a persisted migration to be forward,
  deterministic, idempotent, and tested from every supported stored version, and
  forbids silent coercion from an unknown shape. `no-silent-under-declaration`
  requires an unreadable draft to stay distinguishable from an absent one. Both
  bear on the refusal path, not on the acceptance path.

## Considered options

- **Leave the field `str`.** Zero risk to stored data; the declared contract stays
  weaker than the invariant already enforced beside it, consumers keep re-wrapping
  `ModeloCode(...)` at read boundaries, and the burn-down stays blocked. Rejected:
  it preserves a gap that costs work at every consumer and protects nothing.
- **Type the stored field `ModeloCode`.** Narrows the declared type to the shape
  the aggregate already proves, moves the refusal onto the field itself, and lets
  the consumer wraps be deleted. Chosen.
- **Type the stored field `Modelo`, the closed enum.** Strictly stronger, and wrong
  at a persisted boundary: it makes the readability of stored data depend on a
  code-level roster, so retiring or renaming a member would strand drafts that were
  valid when written, and a modelo fileable before the enum is updated could not be
  drafted at all. Rejected as a durability hazard.
- **Type `ModeloId`, the registry annotated alias.** Identical shape, but it is the
  registry schema's identifier vocabulary; using it on a filing aggregate crosses a
  package boundary for no gain and splits the modelo vocabulary a third way.
  Rejected under the one-canonical-stem rule in `aeat-naming`.
- **Leave the stored field `str` and project to `ModeloCode` on read.** Keeps the
  stored declaration maximally permissive and types the consumer surface. Rejected:
  it is what the codebase already does by hand, it puts one contract at many
  boundaries instead of one, and it leaves the persisted contract silent about a
  shape the aggregate already depends on.
- **Retype behind a `BeforeValidator` coercion hop**, mirroring the registry's
  `coerce_enum_member` pattern. No `ModeloCodeField` equivalent exists for this
  type, and building one here would license exactly the silent normalisation -
  stripping, padding, case-folding - that `no-legacy-compatibility` forbids.
  Rejected.

## Constraints

- The retype must not change the stored wire shape. `ModeloCode` serialises as a
  bare JSON string, so `draft_id`, the object-key grammar, and the envelope payload
  are unchanged; any step that would alter them is outside this decision.
- No secure-object schema-version bump and no upgrader hop may be introduced by
  this change. Registering a hop for a transformation nothing needs would fabricate
  a stored shape nothing ever wrote, which the pre-release posture in
  `schema_lineage.py` forbids.
- The claim that no stored value can fail `ModeloCode` rests on `snapshot_ref`
  being required and on the cross-field equality check. If a later change gives
  `snapshot_ref` a default, relaxes that equality, or loosens `ModeloId`, this
  decision's premise lapses and must be re-established before the retype is relied
  on.
- Refusal must stay per-object and loud. A draft that fails the field surfaces as
  an identified unreadable object; it is never skipped by enumeration, coerced, or
  counted as absent.
- This record is a decision only. It authorises no schema edit and no migration
  code. Its code grounding is `2026-09-02-filing-draft-modelo-typing-reference`;
  the locators repeated here are the few the decision turns on.

## Implementation

`ModeloDraft.modelo` is declared `ModeloCode`, imported directly from its defining
module, in one atomic change together with the consumer sites that currently
re-wrap it or accept a `str | ModeloCode` union. The hash and marker helpers
`registry_schema_version` and `compute_modelo_draft_id` keep `str` parameters:
they legitimately accept a modelo-shaped value from either vocabulary, and
narrowing them is a separate question.

The migration is the **null migration**, and it is null by proof rather than by
assumption. No upgrader is registered, no namespace version moves, no stored bytes
are rewritten. What is delivered in place of transformation code is the evidence
that no transformation is owed: a test that builds the off-shape stored payloads -
empty, whitespace, two-digit, four-digit, over-padded, suffixed, non-ASCII digits -
and shows each is already refused by the current `str`-typed model on the real
rehydration path, and refused by the retyped model as well. The two differ only in
which invariant refuses first and under which error identity.

A stored draft that fails the field refuses loudly at rehydration: the object is
reported by key as unreadable, with the offending value's shape described rather
than its content. It is never coerced, never defaulted, never dropped from
enumeration. Recovery is the operator-authorised route already sanctioned by
`2026-08-07-canonical-identifiers-adr` - teardown and re-derivation through the
config-reset and bucket-maintenance authorities - never a quarantine table, and
never a repair-in-place path that would have to guess the intended modelo.

Tests owed by this decision: a strict roundtrip with every defaultable field
populated non-default, asserting the modelo arrives as a `ModeloCode` instance
rather than an equal string; the anti-tautology proof above, extending
`domain/filing/tests/test_roundtrip_anti_tautology.py`; a proof that the
cross-field modelo / snapshot-ref agreement refusal still bites after the retype,
so the narrower field type does not mask it; and a supported-stored-version test
that loads a committed schema-version-2 draft payload through the real production
read path. Version 2 is the only supported stored version for this namespace, and
the test states that explicitly rather than leaving the enumeration implicit.

## Rationale

The knockout is that this retype does not change the acceptance set of stored data
at all. `snapshot_ref` is required, its modelo is three digits, and the draft
refuses any disagreement between the two, so the `ModeloCode` contract is already
enforced on every load, transitively, by invariants that shipped before this
question was asked. The choice is therefore between declaring a contract that is
already true and continuing not to declare it. Every migration-shaped risk that
would normally gate a persisted retype - an unreadable stored value, a rehashed
content address, an orphaned object key, a gap in the upgrader chain - is absent
here for a reason that can be stated and tested, which is why the null migration is
a finding rather than an omission.

The closed enum loses on durability: it would tie the readability of a stored
financial record to a roster that changes with the codebase, and a stored draft
must not become unreadable because a member was retired. Read-time projection
loses on placement: it is the status quo, and it distributes one contract across
every consumer. `ModeloCode` is the canonical typed modelo representation
`aeat-naming` names, it is what the sibling persisted records already declare, and
it is the only option that costs nothing on disk.

## Consequences

- The declared persisted contract matches the enforced one, and the refusal moves
  onto the field where a reader sees it. The consumer-side `ModeloCode(...)` wraps
  and the `str | ModeloCode` union become redundant and are deleted in the same
  change, which is the burn-down's actual gain.
- Failure identity changes at the margin: an off-shape stored modelo that today
  refuses as a filing validation error from the cross-field comparison will refuse
  as a modelo validation error from the field. A caller matching on the specific
  exception type or message for this case must be updated; both are `ValueError`
  subclasses, so a caller matching the base is unaffected.
- The decision buys no protection against a shape-valid but wrong modelo - a draft
  claiming a code no modelo uses, or claiming 303 for what is a 130. Shape typing
  does not check agreement, exactly as `2026-08-07-canonical-identifiers-adr`
  records for the tax-identity fields on this same model. Nobody may read "the
  modelo is typed" as "the modelo is correct".
- The premise is load-bearing and undocumented in code today. Anyone later
  defaulting `snapshot_ref`, relaxing the agreement check, or loosening `ModeloId`
  silently invalidates the null migration, so the retype carries a note at the
  invariant saying so.
- A stored draft that cannot be read is an operator-visible loss of a filing draft
  with no repair short of re-derivation. That cost is accepted because such a draft
  is already unreadable today: this decision does not create the condition, and
  re-derivation from ledger facts and the registry is the product's existing
  answer.
- Grounding this decision surfaced a docstring in `schema_lineage.py` claiming two
  namespaces register a real one-hop upgrader at the bottom of that file, where the
  file registers none. It is left unresolved here and is worth its own record: it
  would mislead the first author who does owe a real hop.
