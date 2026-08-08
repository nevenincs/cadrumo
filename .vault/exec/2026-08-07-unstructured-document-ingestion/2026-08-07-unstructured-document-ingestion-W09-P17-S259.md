---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:d7cc932705ee8e56fb8087c201a9e2fb55cc4efe1a60d7c9d3a826f5eaed7241'
step_id: 'S259'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# `unstructured-document-ingestion` exec W09.P17.S259

## Scope

- `src/cadrumo/locales`

## Description

- Split the block by shape before authoring, because four of the keys were deficient in one locale only and a Spanish-first pass would have skipped them.
- Check every key for an already-authored sibling revision before writing anything, and measure the answer rather than assume it carries from the previous arm.
- Ground each help string on the casilla's own authored Spanish label, and take the register from the sibling help strings already authored in the same revision.
- Generate all values and review them before any write, rather than writing and reviewing after.
- Apply the block through one manifest instead of one process per leaf.
- Verify every leaf by re-reading it, and again against HEAD rather than the working tree.

## Outcome

**Forty casillas authored in four locales, one hundred and sixty leaves, every one verified by re-read.** The four-catalogue key-echo population is now a single leaf, and that leaf is blocked by a rowed tooling defect rather than by anything unresolved here.

**The block was not uniform, and the plan as first written would have silently skipped part of it.** Four of the forty-four keys echoed in exactly one locale while Spanish was already authored; a Spanish-first pass would have found a real value, done nothing, and closed the row with those four still echoing. They were handled as their own arm and are recorded in this feature's S243 record.

**The grounding is stronger than translation, and it came from measuring rather than assuming.** The previous arm had been able to reuse an authored sibling revision for the same casilla — the identical Spanish appearing in seven revisions for one label and five for another. That shortcut does not carry here: measured across all forty, exactly zero had a reusable authored sibling, because each of these casillas appears once. What every one of them does have is its own authored Spanish `label`, which is Diseño-derived and already reviewed. Each help string is therefore that casilla's own label restated as an instruction, in the register the sibling help strings in the same revision already use, read across all four locales before drafting.

**Nothing reaches past the label.** No statement about the reverse-charge mechanism, no legal citation, no scope the Diseño does not carry. The tier boxes reuse the sibling's own scoping clause for the same tier concept, because that clause is authored evidence about tier boxes in this revision rather than a claim invented here. The instruction to author the narrower true thing where the source would not carry the register's claim is therefore satisfied by construction rather than case by case, and there is nothing to report under it — the question never arose, because the label was never exceeded.

**The dry run caught a defect that would otherwise have shipped forty times.** All one hundred and sixty values were generated and read before a single write. Hungarian was wrong: the compound had been built from the plural stem, `termékekbeszerzések`, where Hungarian takes the singular, `termékbeszerzések`; and an `a(z)` placeholder had been left where the article is known. Both were corrected and re-inspected before the first write. Written first and reviewed after, that error would have entered a filing-grade surface forty times in the locale least likely to get a second reader.

## Verification

    python -m dev.locales set-batch <manifest>
    updated 4 locale catalogues: ca.yml, en.yml, es.yml, hu.yml

    re-read of every leaf in the manifest against the working tree : 160 of 160
    re-read of every leaf in the manifest against HEAD             : 160 of 160

The second reading is the one that counts. A sweeper committed the catalogues mid-close, so the working-tree reading and the committed state were separate questions, and only the HEAD reading answers whether the work shipped.

    pytest src/cadrumo/tests/test_locale_translation_honesty.py -n0 -q
    1 failed, 6 passed in 155.79s

    key-echoes: en 0, es 0, ca 0, hu 1
    identical-source axis: passes entirely

The single remaining failure names one leaf, `modelo.schema.100.revision.2022.casilla.1076.help`. Its Spanish, English and Catalan are all null, so under the documented rule nothing can be derived for Hungarian; the correct state is null, matching its own sibling. The verb that would express that cannot resolve the path, and the defect carries its own row.

**No write was trusted on its exit status.** That is not caution for its own sake: a `set` in the preceding arm returned exit 2 and left the placeholder on disk, and a pass that believed the writer would have reported twenty-four writes while shipping twenty-three.

## Notes

**A tooling miss, recorded against this Step.** The block was first driven as one hundred and sixty separate `set` invocations, each reloading the entire catalogue authority, which is why the pass ran for hours before being switched. `set-batch` takes a manifest mapping locale codes to dotted-key scalar maps and applies the whole block in one process; it was visible in the CLI's help from the first arm and was not used. The remainder was completed through it. The reason for the delay was the transport, never the catalogues' size, and the next lane to touch these files should batch.

Switching method mid-pass raced nothing, because this lane was the only writer. The in-flight pass was stopped first, identified by its own command line and confirmed to carry this session's own scratchpad path, so no peer process was touched.

**A pre-existing divergence found and deliberately not widened into.** The same casilla with byte-identical Spanish carries different Hungarian across revisions 2024 and 2025. The preceding arm aligned a 2022 leaf to the newer rendering and left the older alone: the row was closing echoes, not reconciling a catalogue, and rewriting an authored revision would have been scope nobody asked for. It is a genuine finding and belongs to whoever owns catalogue consistency.

Every value went through `python -m dev.locales`; no `.yml` and no allowlist file was hand-edited.

The catalogues were committed by a sweeper rather than under this Step's own pathspec. The content was verified present at HEAD before this record was written.
