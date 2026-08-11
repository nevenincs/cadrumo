---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:d8964ebf856eac6d3418dc7bec99d4f88ff682df976af6eda1794ecfac4bee93'
step_id: 'S02'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace casilla-schema with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S02 and 2026-08-10-casilla-schema-plan placeholders are machine-filled by
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
     The confirm the registry restructure (91 to 94 revisions, the M303 split) is committed, pin that commit as the measurement SHA, and re-take the six basis-tracked numbers (registry revisions, relation pairs, relation-declaring revisions, export-exemption casillas, manifest-bearing revisions, manifest-less revisions) with a bundled-authority probe, recording the command and outputs in the exec record and ## Scope

- `src/cadrumo/_data/registry/aeat/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# confirm the registry restructure (91 to 94 revisions, the M303 split) is committed, pin that commit as the measurement SHA, and re-take the six basis-tracked numbers (registry revisions, relation pairs, relation-declaring revisions, export-exemption casillas, manifest-bearing revisions, manifest-less revisions) with a bundled-authority probe, recording the command and outputs in the exec record

## Scope

- `src/cadrumo/_data/registry/aeat/`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

## Outcome

**Measurement SHA: `35f2b7d1611b1dc40ad2e2ca1d6be4b2fcd94330`** (worktree dirty 1716, index carrying 1616 staged files that the probe does not read).

**The restructure is confirmed committed.** 94 `revision.toml` files tracked at that SHA, and the M303 split is present with both `2024-hasta-08-y-2t` and `2024-desde-09-y-3t` tracked (six M303 revisions total). The row's "91 to 94" transition is complete.

### Command

```
uv run --no-sync python <probe>
```

The probe is `s02_basis_probe.py`, kept out of the repository. It calls `bundled_authority()` and reads the COMPILED `ModeloDefinition` objects. The only thing it takes from the filesystem is the list of modelo directory names; every coverage judgement is read off the loaded snapshot, per the registry-authority-flow rule that coverage is assessed from the loaded snapshot and never from a directory listing.

### The six basis-tracked numbers

| # | number | value |
|---|---|---|
| 1 | registry revisions | **94** |
| 2 | relation pairs | **78** |
| 3 | relation-declaring revisions | **22** |
| 4 | export-exemption casillas | **42** |
| 5 | manifest-bearing revisions | **56** |
| 6 | manifest-less revisions | **38** |

Modelos: **73 directories, 73 loaded, 0 refused.**

Export exemptions are carried by 12 revisions: M130/2019-y-siguientes 1, M131 1 each across 2019-2023, 2024, 2025 and 2026, M303 5 on 2009-y-siguientes and 6 on each of its five later revisions, M720/2013-y-siguientes 2.

### Controls, printed by the probe rather than asserted

- `5 + 6 = 94`, equal to the revision count. The manifest buckets are total and disjoint.
- Loaded revisions 94 equals the 94 on disk, so there is no load-refusal gap.
- Shape errors: 0.
- Relation pairs came back **78**, which independently matches the `78/78` figure the canonical-derivations ADR quotes from a different instrument. That is the corroboration that the probe measures the intended thing.

### Two shape faults caught before the run, each of which would have produced a confident all-zero answer

The first draft of this probe would have reported 0 relation pairs, 0 relation-declaring revisions, 0 export exemptions and 94 manifest-less revisions - internally consistent, plausible, and wrong in every cell.

- `ModeloDefinition.revisions` is a `Mapping[RevisionId, ModeloRevision]`, not a sequence. Iterating it yields KEYS, and `getattr(str, "relations", ())` returns `()`. The probe now asserts the mapping shape and asserts each iterated value is not a `str`.
- There is no `export_exemption` attribute. The field is `casilla.export_exemption_reason`, confirmed against `_validate_export_exemption.py:209,226`. A `getattr` against the guessed name returns `None` forever and reports zero exemptions on a corpus carrying 42.

Both were found by checking the schema before trusting a zero, rather than by running and reading the output as a result.

## Notes

### The measurement SHA pins the tracked registry exactly, and carries one stated impurity

The probe reads TOML from the working tree, so "pin that commit as the measurement SHA" needed checking rather than assuming. Measured: **registry files differing worktree-vs-HEAD is 0**, so every tracked registry byte the probe read is identical to HEAD at the measurement SHA. The 1,616-file index is irrelevant here - a probe reads the working tree, never the index.

**The impurity, stated rather than papered: 11 UNTRACKED registry fragments were present and the loader does compile that section.** They are `support_removal_decisions/0001-export-layout-support-removal.toml` under M111, M115, M123 (x2), M130, M200, M202 (x3) and M232 (x2). Each declares `decision = "remove_from_filing_grade"` for an export layout, citing S45's withdrawal of filing-grade layouts whose record design contains producer fields without canonical typed producer authority.

I initially expected the loader to ignore the section and wrote that expectation down before running the check; **the check contradicted it** - ten modules reference `support_removal_decisions`, including `domain/calculations/registry/_constructs.py` and `_classification_coherence.py`. Recording the contradiction rather than the corrected belief, because printing the hypothesis first is the only reason the hit list was read as a refutation instead of as confirmation.

So the six numbers are **HEAD's tracked registry plus 11 untracked S45 withdrawal fragments**. None of the six metrics is defined in terms of layout withdrawal, and number 4 counts a casilla field rather than a layout, so no figure is expected to move if the fragments are removed - but that is reasoning, not measurement, and the next reader should treat the numbers as pinned to that qualified tree rather than to HEAD alone.

### The M303 load refusal is discharged, measured three ways

A standing campaign record held that M303 does not load at all, that 22 of its 36 header tokens were not `ExportHeaderKey` members, and that nine modelos were load-refused. **None of that is true at the measurement SHA.** 73 of 73 modelos load, 0 refused; all 94 revisions compile; M303 loads with all six revisions and carries export exemptions on every one. The mechanism is visible in the facade: `ExportHeaderKey` occurs **0** times in the registry facade at HEAD and `FilingProducerKey` occurs **2**, so the header-key to producer-key rename completed and landed. The refusal was a symptom of a half-landed rename, not a property of the corpus.

### Two figures the rest of the campaign should take from here

**38 manifest-less revisions is the S08 worklist size**, and 56 manifest-bearing is its complement. These are the denominators the owner-ruled progress counts are measured against; a revision among the 38 renders UNDEFINED, never zero.

**M232 `2018-y-siguientes` is among the untracked withdrawal set**, and it is the revision carrying all 50 of the non-BOUND-with-a-binding casillas that forced the canonical-derivations ADR amendment. Its export layout is being withdrawn from filing grade. That does not disturb the amendment's reasoning - M232 carries zero ledger-IVA bindings either way, so the divergent rows stay where `_rate_box_partition` never looks - but it is a live reason the number 50 may not be stable, and therefore a second argument for the intersection gate the amendment adopted over the emptiness gate it replaced: the intersection gate is indifferent to M232 churn, an emptiness gate would move with it.
