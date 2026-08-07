---
tags:
  - '#plan'
  - '#arch-remediation-registry-format'
date: '2026-08-05'
modified: '2026-08-07'
body_hash: 'sha256:602d13983a26e9c0811fbec59a37228d3f6faa2bb724fef7eef5e58bca20618a'
tier: L1
related:
  - '[[2026-08-05-arch-remediation-registry-format-casilla-section-order-adr]]'
  - '[[2026-08-05-arch-remediation-registry-format-casilla-fragment-content-naming-audit]]'
  - '[[2026-07-06-arch-remediation-registry-format-research]]'
---

# `arch-remediation-registry-format` plan

Correct the export rule's parity-gate claim to the set the gates genuinely enforce,
and record casilla section order as deliberately ungated presentation.

## Description

This plan executes the casilla-section-order ADR in the `related:` frontmatter,
which is backed by the casilla-fragment-content-naming audit alongside it. The
audit measured that the export rule advertises a parity assertion no gate makes,
and that the corpus does not hold section contiguity either. The ADR chose to
correct the claim rather than manufacture the property, on the finding that AEAT's
own record design is number-keyed and interleaves sections, so contiguity and the
official record key are incompatible orderings.

The work is deliberately small and carries no code, gate, or corpus change. One
authoring surface changes, the rule source, and the generated provider copies
follow it through the sync verb. A third Step leaves a note in the workbook parity
gate so a future reader does not restore the claim from the rule's history, which
is the specific way this defect would recur: the claim outlived the narrower
wording it was compressed from.

Scope boundaries worth stating because the ADR is explicit about them. The parity
gate itself is not modified beyond its docstring, the corpus is not reordered, and
no assertion is added. Adding the advertised assertion would red immediately, which
is why this is a documentation correction rather than an enforcement change. The
rule is corrected at its authoring source under the vaultspec tree and never at the
generated copies, which the next sync would silently revert.

## Steps

- [x] `S01` - Correct the parity-gate claim in the rule source so it enumerates only the enforced assertions, and add the paragraph stating casilla section is ungated presentation; `.vaultspec/rules/modelo-export-mirrors-official-structure.md`.
- [x] `S02` - Propagate the corrected rule to the generated provider copies with the sync verb, confirming no generated copy carries a hand-edit; `.claude/rules/modelo-export-mirrors-official-structure.md`.
- [x] `S03` - Record in the workbook parity gate docstring that section order is deliberately unasserted, so a future reader does not re-add the claim from the rule history; `src/cadrumo/application/storage/calc_sheets/tests/test_modelo_export_parity.py`.

## Parallelization

`S01` and `S02` carry hard ordering: the sync verb propagates whatever the rule
source says, so running it before the source is corrected regenerates the stale
text and the Step verifies nothing. They are best executed together by one agent
rather than handed off between them, because the corrected source is uncommitted
between the two and a peer sync landing in the gap would produce a confusing diff.

`S03` is independent of both and touches a different tree, so it may run in
parallel. It must still be a separate commit from the rule change: the rule lives
under the vaultspec authoring tree and the docstring under the test tree, and
splitting them keeps each reviewable on its own.

All three Steps are low complexity and mechanical, so this plan warrants a sonnet
executor throughout. No Step here justifies an opus dispatch, and inflating one to
fit an executor tier would be the wrong reading of the ADR, which explicitly
authorises no structural work.

## Verification

`S01` is verified when a search of the rule source for the parity-gate sentence
returns an enumeration that no longer contains a section-order clause, and the
added paragraph states three things explicitly: that casilla section is a semantic
tag rendered as orientation banners, that contiguity is neither gated nor held by
the corpus, and that a future presentation sequence must land as explicit data
rather than through fragment filenames.

`S02` is verified when the generated provider copy is byte-identical to what the
sync verb produces from the corrected source, confirmed by running sync and
observing the copy change in the same run rather than assuming it. A generated
copy that differs from a fresh sync output means it was hand-edited, which is the
failure this Step exists to exclude.

`S03` is verified when the workbook parity gate still passes and its docstring
states that section order is deliberately unasserted. The Step must not add an
assertion: a run of the gate before and after the docstring edit must show the same
number of assertions exercised, since adding one would red on the corpus the ADR
measured.

The plan is complete when all three Steps are closed and each has an execution
record. One cross-cutting criterion applies to every Step: the audit and the ADR
both claim the enforced set, so whoever closes `S01` must confirm the corrected
enumeration matches what the gates actually assert at HEAD rather than copying the
ADR's summary of them. The ADR's summary was itself written from a measurement, and
a second-hand copy of a measurement is how the original overstatement entered the
rule.
