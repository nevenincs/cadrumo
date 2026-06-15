---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S08'
related:
  - "[[2026-06-14-storage-backend-security-review-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace storage-backend-security-review with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S08 and 2026-06-14-storage-backend-security-review-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Verify the stored payload hash and recomputed revision id on every secure-object read and fail closed on mismatch and ## Scope

- `src/aeat/adapters/persistence/storage/sql/secure_objects.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Verify the stored payload hash and recomputed revision id on every secure-object read and fail closed on mismatch

## Scope

- `src/aeat/adapters/persistence/storage/sql/secure_objects.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

- Empirically probe the precondition: a fidelity test recomputing `revision_id`
  from round-tripped columns **failed**, proving `written_at` round-trips lossy
  (SQLite drops the `+00:00` tzinfo: `...581079+00:00` writes, `...581079` reads).
- Fix the precondition: canonicalise every instant to naive-UTC isoformat in
  `derive_revision_id` (`_canonical_instant`), so write-time and read-time
  derivations are identical. Probe now passes.
- Add `verify_revision_self_consistency` next to `derive_revision_id`: recompute
  `revision_id` from the stored lineage columns; absent revision metadata is
  consistent, a present-but-divergent id is not.
- Wire the gate into both read paths: `_record_from_row` (load → raises
  `SecureObjectUnreadableError`) and `iter_records_with_failures` (enumeration →
  yields `SecureObjectUnreadable`, fault-isolated; SELECT extended with the
  lineage columns).
- Add the anti-tautology proof: tamper `payload_hash` without restamping
  `revision_id` → both read paths fail closed.

## Outcome

STEP COMPLETE. Read-time revision-lineage self-consistency now fails closed on
every secure-object read.

The gate closes the residual H3 left open: the plaintext lineage/integrity columns
(`revision_id`, `payload_hash`, `ciphertext_hash`, `previous_*`) sit **outside**
the payload AEAD and were trusted unverified. Because `revision_id` is a content
address over the whole lineage tuple, recomputing it from the stored columns and
comparing detects a tamper of **any single column — including `payload_hash`** —
that does not also restamp `revision_id`. So the literal S08 ask ("verify the
stored payload hash and recomputed revision id") is satisfied transitively by the
one revision-id check, without a payload-dependent comparison.

The earlier-rejected hazards were both resolved rather than dodged:

- The **round-trip false-positive** hazard (a lossy `written_at` would fail-close
  valid rows) was *empirically confirmed* by a failing fidelity probe, then *fixed*
  at the root by canonicalising the instant in `derive_revision_id`. The probe is
  retained as a canary so the canonicalisation cannot silently regress. Pre-beta /
  no-legacy makes changing the derivation free.
- The **corruption-suite conflict** is avoided by design: the check is purely
  metadata-internal (it uses the stored `payload_hash`/`ciphertext_hash` columns,
  never recomputes them from the payload/wire), so a corruption probe that
  re-encrypts a mutated payload without restamping metadata leaves the lineage
  self-consistent → the gate stays silent and the domain model_validator fires as
  before. No anti-tautology suite needed reconciling.

Gates: full storage suite green (**848**, +2 new tests); the cross-domain
corruption-suite sweep (14 files) green except two **pre-existing peer failures**
in `test_revision_stamp_roundtrip` — `binding.aggregation.op` AttributeError in the
registry binding-aggregation layer (the active M100-grounding registry campaign's
surface), reproduced identically at HEAD with this change reverted, so not owned
here. The secure-object `revision_id` (storage lineage content-address) is distinct
from the registry `stamped_revision_id`; this change does not touch the latter.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

The "data access is an absolute key" caution that motivated the earlier deferral
was honoured by proving round-trip fidelity *first* (failing probe → root-cause fix
→ passing probe → retained canary) rather than shipping a gate on an unverified
assumption. Pre-existing peer regression in `test_revision_stamp_roundtrip`
(registry binding-aggregation dict-vs-typed) reported to the owning campaign, not
patched here per `full-tree-gate-must-distinguish-owner`.
