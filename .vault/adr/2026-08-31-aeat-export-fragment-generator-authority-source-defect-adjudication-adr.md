---
tags:
  - '#adr'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:7d1e94022b1e19880538294353d7b118edbeaf51a77964391502bbc04484df4b'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-adr]]"
  - "[[2026-08-27-registry-temporal-coverage-design-authority-declaration-adr]]"
  - '[[2026-08-31-aeat-export-fragment-generator-authority-m390-2022-page-7-constant-reference]]'
---

# `aeat-export-fragment-generator-authority` adr: `adjudicating a self-contradictory cell in an official AEAT record design` | (**status:** `proposed`)

## Problem Statement

The generator treats an AEAT-published record design as authoritative and compares every literal field against it byte-for-byte. That comparison has now refused a modelo 390 filing-year 2022 fragment, and the refusal is correct: the published workbook contradicts itself, stating both an eleven-character constant and the twelve-byte slot that constant occupies. The measurement, the two independent passes behind it, and the reason only one of the two halves can be honoured are recorded in `2026-08-31-aeat-export-fragment-generator-authority-m390-2022-page-7-constant-reference`.

No accepted record says what the generator should do when the authority is internally inconsistent. Until one does, a real and correctly-detected source defect blocks the modelo 390 2022 semantic map, and through it the export-tree work that the temporal-coverage and completeness-closure campaigns wait on. The decision is needed now because the alternative routes around it all destroy the check that found the defect.

## Considerations

The comparison earned its keep here: it is the only gate that reads the source document rather than the project's transcription of it, and the semantic-map validator passed all 537 entries precisely because the map is self-consistent.

The corpus is byte-exact official evidence. `sensitive-financial-data-secure-storage-only` and the grounding rules treat AEAT's published artefacts as things the application preserves, not things it rewrites.

The adjudicated value is not a free choice. Three independent signals converge on a single reading, and the defective reading is unusable rather than merely disfavoured, per the cited reference.

`2026-08-27-registry-temporal-coverage-design-authority-declaration-adr` settled a structurally identical problem one axis away: two contracts disagreed because the registry could not express a concept, and the fix was to declare the concept as data rather than to exempt cases in test source.

A defect adjudication is a claim about a specific published file, not about a modelo or a filing year. AEAT reissues designs; a correction that outlived its document would silently misread its successor.

## Considered options

**Edit the committed layout to carry the typo.** Rejected: it cannot produce a loadable tree, since the following length guard refuses eleven bytes in a twelve-byte slot, and it would corrupt a reviewed layout to match a defect.

**Relax or remove the byte comparison.** Rejected: it deletes the only check capable of detecting an error in the source, immediately after that check found one.

**Special-case the field inside the literal builder.** Rejected: an in-code exemption is the honor system `aeat-quality-gates` removes, and the design-authority precedent rejected the same shape.

**Correct the bundled workbook.** Rejected: it breaks the sha256 pin and rewrites official evidence the corpus exists to preserve.

**Reuse the semantic map's `anomaly_exceptions`.** Rejected: it belongs to a different validator, is documentary by its own docstring, and waives nothing. It cannot reach this refusal.

**Declare the adjudication as hash-pinned registry data.** Chosen.

## Constraints

The byte comparison stays exact for every field that has no declaration; nothing here may widen into a general tolerance. The corpus stays byte-exact. Nothing here touches `review_status`, which is the operator's signature on a different axis. The declaration must be refusable in its own right, so that a malformed or unevidenced entry fails the build rather than passing silently.

This rests on the source-authority contracts already accepted in `2026-08-10-aeat-export-fragment-generator-authority-adr` and the authority declaration above; both are accepted and in force, so no frontier dependency is introduced.

## Implementation

A source-defect declaration is registry data, keyed by the source ref together with the sha256 of the exact file it describes, and by the sheet and cell coordinate within it. It carries the defective content as published, the adjudicated content, and the evidence establishing the adjudication.

The literal builder consults declarations at the point where it currently raises, and only there. A declaration applies only when the published content matches the recorded defective content exactly; any other content means the file is not the one adjudicated, and the refusal stands.

Two properties make the mechanism self-limiting. Because the key includes the file digest, a reissued design carries a different digest, the declaration ceases to apply, and the gate refuses again until the new file is adjudicated on its own terms -- the failure mode is a stale correction going dormant, never a stale correction being applied. And because an adjudicated literal must still satisfy the slot width the same cell declares, the mechanism cannot express an arbitrary substitution; it can only resolve a contradiction in the direction the document's own surviving half supports.

The declaration set is enumerable, so the estate can state how many corrections it carries and against which files, rather than leaving them scattered across parser branches.

## Rationale

Every rejected option pays for one unblocked fragment with the loss of a gate, a reviewed artefact, or the integrity of the corpus. This option pays with a declaration that is narrower than the thing it unblocks: pinned to one file by digest, one cell by coordinate, and one exact published string.

The knockout is the digest pin. It converts a correction from an assertion about AEAT into an assertion about a particular document that was read and adjudicated, which is the only form of the claim that stays true over time.

It also keeps the detection intact. The gate still refuses everything it refuses today; it simply distinguishes a defect nobody has examined from one that has been examined, recorded, and evidenced.

## Consequences

The modelo 390 2022 map lands, and the export-tree chain behind it moves.

The honest cost is that the project acquires the ability to read an official document differently from how it is written. That is a real power in a filing-grade system, and the mitigations are deliberate rather than incidental: the pin is per-file, the adjudicated value must satisfy the document's own declared geometry, and each entry carries its evidence. The risk it does not remove is judgement -- a future entry could be wrong on the merits while satisfying every structural constraint, and only review catches that.

A second-order gain: the estate gains a place to record that an official source is defective at all. Today that knowledge exists only as a gate failure that someone must re-derive from scratch.

The pathway this opens is the harder question deferred here. This record adjudicates a contradiction the document itself exposes. It does not authorise correcting a source that is internally consistent and merely believed to be wrong, which is a materially larger claim and should have its own decision if it is ever needed.
