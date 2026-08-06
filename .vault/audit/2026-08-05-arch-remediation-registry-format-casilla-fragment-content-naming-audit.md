---
tags:
  - '#audit'
  - '#arch-remediation-registry-format'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:c5dd95937aaa31f705a291342bd9766608a4a8310a7acb987dd7bd8264e75cc4'
related:
  - "[[2026-07-02-arch-remediation-registry-format-adr]]"
  - "[[2026-07-02-arch-remediation-registry-format-plan]]"
  - "[[2026-07-03-arch-remediation-registry-format-audit]]"
---

# `arch-remediation-registry-format` audit: `casilla fragment content-derived naming: is compiled order load-bearing?`

## Scope

The loader compiles a revision's casillas in `sorted(rglob("*.toml"))` order over
the fragment directory, so a fragment's filename is its merge position. The corpus
used `<ordinal>-c<span>.toml`, which is truthful but makes a casilla's stem drift
whenever an earlier casilla is added: 2,113 Modelo 100 stems drifted this way. The
proposed fix is a purely content-derived stem, `c<span>.toml`. That permutes
compiled order in 24 directories across 10,041 positions, essentially all of
Modelo 100, and nobody had established whether that order mattered.

This audit answers that question, records the evidence, and covers the rename that
followed. Measurements were taken against throwaway copies of the registry tree and
against in-memory permutations built with `model_copy`; the bundled corpus was never
written to during measurement.

## Findings

### order-consumer-inventory | low | Exactly one consumer reads the casilla sequence, and only for presentation

Every site iterating a revision's casillas was enumerated and classified. The sole
consumer that genuinely consumes the sequence is the workbook layout planner
`plan_layout`, which assigns Entradas and Cálculos rows by iteration order, plus the
helpers deriving referenced bindings, relations and parameters through insertion
order. Everything deciding what the taxpayer declares is keyed by casilla id and is
order-free: `build_draft` sorts its values and provenance by id, the filing schema
collection sorts by canonical id, the record metadata is consumed as a dict, the
fichero-BOE record sequence is keyed on an explicit `order` field on the export
layout rather than on casillas, the docs casilla projection sorts, and the locale
scanner builds a set. The workbook parity and cross-transport consistency gates are
themselves entirely set-based, so neither asserts order. No explicit order or
position field exists on the casilla definition.

### section-order-not-held | medium | The corpus never held the section grouping the rename was suspected of destroying

The export rule requires exports to mirror the official structure including section
order, so the concern was that a content-derived permutation would scramble
declaration-ordered sections. Measurement showed the property was already absent:
Modelo 303 declared 19 contiguous runs across 10 distinct sections and Modelo 200
declared 1,010 runs across 638 sections, both before any rename. Under the real
permutation the figures moved to 20 and 1,003 respectively, and adjacent-descent
counts against the official record-design key went from 18 to 18 and from 43 to 38.
The rename is therefore near-neutral on both axes, and there was no official-order
property available for it to destroy.

### stale-workbook-guard | low | A pre-rename workbook is refused rather than misread, by a guard that already existed

The Sheets pull resolves each casilla by the A1 address the live layout plans, so a
reorder could in principle make a previously exported workbook read a neighbouring
casilla's value. That hazard is already closed, but by snapshot binding rather than
by order stability: `registry_sha` hashes the ordered snapshot JSON, so any reorder
changes it and the pull refuses the stale sheet. This was confirmed with a
discriminating control: the digest changed for the two permuted modelos and stayed
identical for an untouched third, so the guard tracks the corpus rather than firing
indiscriminately.

### rename-semantically-inert | low | 12,663 fragments renamed with the compiled corpus byte-identical

An id-keyed content digest covering every compiled casilla was captured before and
after the rename. Across 90 revisions and 15,774 casillas, zero revisions changed
digest. Git recorded every staged move as a pure rename with no content change. The
gate replay confirmed the export-parity and workbook-versus-fichero-BOE consistency
assertions pass identically on the permuted and baseline trees, and the draft-facing
projections are identical. Modelo 100 was measured separately because it is excluded
from the workbook lane by its untranslatable formula operations: all four revisions
are order-invariant on every projection that applies to them.

### uniqueness-was-implicit | medium | The ordinal guaranteed stem uniqueness for free, and the replacement had to make that explicit

A merge ordinal is unique by construction, so the previous naming convention could
not produce two fragments with the same stem. A content-derived stem carries no such
guarantee: two fragments declaring the same span would collide and become
unaddressable. The rename plan reported zero collisions across the corpus, and a
direct scan confirmed zero directories with duplicate stems, but the property was
holding by luck rather than by enforcement. The naming gate now checks it directly,
with its own positive control, because a violation class that has never fired cannot
be trusted.

### migration-runner-swallowed-git-failures | high | A rename runner reported success while applying 103 of 12,663 moves

The rename tool issued one `git mv` per fragment and exited zero even when those
invocations failed on index-lock contention from concurrent agents. It stopped after
103 of 12,663 moves while reporting success, and the partial state was detectable
only by counting files. The mixed corpus still loaded, which is consistent with the
order finding but also means the failure was silent at every level a caller would
normally check. The remedy used was to perform the moves on the filesystem and stage
once with a pathspec, which removes 12,663 index-lock acquisitions and their
contention window. The tool itself is scratch tooling that is not retained, so the
durable content here is the shape of the trap rather than the specific defect.

### collection-docstring-claimed-declaration-order | low | A public accessor documented an ordering its implementation did not provide

`RegistryCasillaCollection.all` documented itself as returning casilla schemas in
declaration order, while the projection that builds it has always sorted by
canonical casilla id. The docstring was corrected to state the real contract and why
declaration order is deliberately not the one exposed. This surfaced only because
the order question forced a reading of every ordering claim in the path.

### shared-worktree-swept-the-staged-rename | low | A concurrent bare commit absorbed the staged rename under another change

The 12,367 staged renames and the naming-gate rewrite were committed by a
concurrent automated snapshot commit that took the whole index rather than an
explicit pathspec, landing 12,420 files under an unrelated subject. No work was
lost and the tree is correct, but the rename is not attributable to a commit of its
own, which weakens the audit trail for a corpus-wide change. This is the failure
mode the project's explicit-pathspec commit discipline exists to prevent, observed
from the side of the agent whose work was absorbed.

### export-rule-claims-unenforced-section-order | medium | The export rule documents a parity assertion the gate does not make

The rule governing modelo exports states that the registry-grounded parity gate
asserts the casilla set against the completeness manifest, the numbering and
segmento, and registry-declaration section order. The first two are asserted; the
third is not. The workbook parity gate compares number and segmento as sets, checks
a live formula on every renderable computed casilla, and checks a number format per
casilla, but never reads `section` -- the word does not appear in the gate at all,
and no other gate asserts casilla section order or contiguity either. The
fichero-BOE lane does enforce a sequence, but a different one: it asserts that the
emitted record order follows the export layout's declaration, keyed on an explicit
integer `order` on each record, which is export-layout record sequence rather than
casilla section. So the rule advertises a guarantee nothing enforces.

This is distinct from the finding that the corpus does not hold section contiguity.
That one says the property is absent from the data; this one says the property is
claimed as gated in the governing rule. The two compound: a reader consulting the
rule would conclude section order is protected, and would be wrong on both counts.
The gap predates this rename and was surfaced by it rather than caused by it --
declaration order is what the workbook lays out, so establishing whether order was
load-bearing required reading what actually enforces it.

## Recommendations

Keep the order-invariance gate as the standing guarantee behind the naming
convention. It pins both halves of the safety argument: that the id-keyed
projections are invariant under permutation, and that cell addresses and the
snapshot digest do move, so the invariance assertions cannot pass vacuously. The
naming gate's prose points at it deliberately; if that gate is ever relaxed, the
content-derived convention has to be reconsidered with it.

Treat stem uniqueness as a permanent obligation of content-derived naming rather
than a property observed once. It is now enforced per directory by the naming gate,
which is the only reason the previous ordinal's implicit guarantee can be given up
safely.

Do not reintroduce a merge ordinal to recover ordering. The measured position is
that compiled order is presentation-only; a future need for a specific casilla
sequence should be declared as data on the casilla or its export layout, the way the
fichero-BOE record sequence already declares an explicit order field, rather than
smuggled back into filenames where it drifts stems across revisions.

Any future corpus-wide migration runner should verify its own effect rather than
trust an exit code, and should avoid per-file version-control invocations in this
shared worktree, where lock contention from concurrent agents is routine rather than
exceptional. The specific runner behind the high-severity finding above is scratch
tooling that is discarded rather than repaired, so that finding closes by removal of
the tool and not by a fix; the recorded lesson is the remediation.

Resolve the advertised-but-unenforced section order through a decision record. This
is the one item here that cannot be closed by adding an assertion, because the
property is already violated in the data: enforcing contiguity today would red
immediately on Modelo 303 and Modelo 200. A follow-on ADR must choose between three
positions, and the choice is architectural rather than mechanical. Either the
workbook is required to group casillas by section, which means the layout planner
sorts rather than following declaration order and the workbook stops mirroring the
authored sequence; or section grouping is required of the corpus itself, which makes
section contiguity an authoring invariant with a migration behind it; or the export
rule's claim is corrected to state what is genuinely gated, leaving section order an
explicitly ungated presentational concern. The first two change what the operator
sees in an official-structure export, so neither should be adopted by adding a gate
quietly. Until that ADR lands, the rule text overstates the guarantee and should be
read as aspirational on the section-order clause alone.
