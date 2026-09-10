---
tags:
  - '#research'
  - '#registry-edition-authoring'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:918ec3f3c24cd525a0898957cb12432951e6a521b1c08cd9de2342d369d8257e'
related: []
---

# `registry-edition-authoring` research: `edition restatement measurement`

A successor edition of a modelo repeats most of its predecessor's casilla declarations. This
asks how much of a successor edition is actually a copy, and what stops the tree from
recognising one. It matters because 14,171 of the 19,688 declaration files under the registry
data root are casilla files, and 19,563 of their 29,678 rows belong to a successor edition
rather than a first edition.

The conclusion: fewer than one in a hundred successor rows is identical to its predecessor as
authored, but more than four in five are identical once the tokens that merely repeat the row's
own edition are removed. The obstacle is restatement inside the row, not the choice to keep
declarations in files.

## Findings

### Successor rows are copies, and restatement is what hides it

16,758 rows chained between adjacent editions. Chaining used `continuidad_id` where declared and
the bare casilla identifier otherwise, with editions ordered by the `valid_from` field of each
`revision.toml`. 2,805 rows are new in their edition; 2,901 are removed.

| Comparison | Identical | 1 field differs | 2 | 3 or more |
| --- | --- | --- | --- | --- |
| As written | 146 (0.9%) | 10,314 | 5,018 | 1,280 |
| Ignoring `export_refs` and `source_refs` | 12,168 (72.6%) | 3,874 | 447 | 269 |
| All edition restatement removed | 13,855 (82.7%) | 2,469 (14.7%) | 218 | 216 |

The third comparison removes `source_refs`, `export_refs`, nested references, year-bearing
formula and binding identifiers, and orden references — tokens whose only content is the
edition, which the containing directory already states.

Residual real differences corpus-wide, after restatement is removed: `section` 366,
`semantic_role` 233, `input_kind` 109, `number` 105, `formula` 85, `binding` 80, `data_type` 75.

### The work diverges sharply by modelo

| Modelo | Identical | Note |
| --- | --- | --- |
| 490 | 100% | plus 357 genuinely new rows |
| 200 | 99.6% | plus 276 new |
| 714 | 98.9% | all 436 differences were one orden reference reissued |
| 322 | 98.7% | carries both authoring lanes across editions |
| 303 | 97.5% | plus 24 new |
| 390 | 93.1% | stub first edition |
| 100 | 71.7% | genuine legal change, not drift |
| 309 | 53.8% | renumbers boxes while keeping identifiers stable |

Modelo 309 is a real structural difference rather than restatement, and is the known hard case
for any lineage-keyed model.

### Modelo 100's divergence is honest legal change

Across 3,065 pairs whose `legal_refs` differ, the classification is 64.5% genuine temporal
grounding, 26.7% the same legal content re-cited under an annually reissued identifier, and 7.5%
authoring drift. For modelo 100 specifically it is 76.0% temporal and 14.8% restatement, so its
lower similarity reflects the law changing, not declarations decaying. Modelo 714's 436
differences are 100% restatement.

The classification is derived by comparing each cited reference's own
`effective_from` / `effective_to` / `governs_periods_from` / `governs_periods_to` against the
editing edition's window.

### Legal reference order is incidental

Only 3 of 16,758 pairs are pure reorderings with no content change, and no consumer treats array
position as meaningful. The lists compare correctly as sets. Set relationships corpus-wide:
superset 64.9%, subset 2.8%, disjoint 17.7%, partial overlap 14.5%.

### Temporal grounding already lives on the reference, not the casilla

`LegalReference` carries a required `effective_from` plus `effective_to` and retroactive period
bounds, and the catalogue already stores multiple dated rows per article — `ley-35-2006:art-52`
exists as four rows, one per legal window. `SourceReference` likewise carries `applies_from` and
`applies_to` with an optional period selector.

A casilla-side temporal lineage field was considered and rejected on this evidence: it would
duplicate the catalogue's dated rows and create two temporal truths that can disagree. The
actionable slice is the 7.5% authoring drift — concentrated in modelo 200 (13 of 13 differing
pairs), modelo 303 (9 of 9), and one anachronistic citation in modelo 100's casilla `c0066` —
which a period-correctness validator addresses using the mechanism that already exists.

### Fragmentation is per-modelo habit, undeclared

Modelo 100 uses one row per file and accounts for 11,357 of the 14,171 casilla files. Modelo 200
averages 3.4 rows per file, modelo 390 sixteen, modelo 303 forty-two. Nothing declares the
convention.

### What a delta would and would not save

Successor rows requiring authorship fall from 19,563 to 5,708, a 70.8% reduction. The corpus
falls from 29,678 rows to 15,823. This is a reduction in what a person authors; the materialised
edition still contains every row and every validator continues to see a complete edition.

It does not improve coverage. Modelo 200 sits at 1.7% completeness-manifest coverage of its
declared casillas before and after.

### Not investigated

Lineage sufficiency was not established: `continuidad_id` is declared on 20.5% of rows and
absent from 25 of 33 multi-edition modelos, so 71% of the chaining above fell back to the bare
identifier. Only casilla declarations were measured; other sections were not. Whether lineage
can be seeded mechanically for the 25 modelos lacking it was not tested.

## Sources

- `src/cadrumo/_data/registry/aeat/modelos/` — the measured corpus, 19,688 files
- `src/cadrumo/domain/calculations/registry/schema_references.py` — `LegalReference` and
  `SourceReference` temporal fields
- `src/cadrumo/_data/registry/aeat/legal/` — the dated legal catalogue rows
- Measured against the working tree of branch `fix/registry-gen` on 2026-09-09. Casilla
  declarations were verified unchanged throughout the measurement window: no commit and no
  uncommitted change touched any `casillas/` path. Concurrent work in the same worktree was
  confined to `export/` trees for modelos 390, 322, 151, 210 and 200.
