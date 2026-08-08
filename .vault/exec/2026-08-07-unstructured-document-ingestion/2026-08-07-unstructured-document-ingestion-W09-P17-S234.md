---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:d1f940d348acefa3d4b1297de89f295abeca0fa2770c160bb4107cfa157a28a2'
step_id: 'S234'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace unstructured-document-ingestion with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S234 and 2026-08-07-unstructured-document-ingestion-plan placeholders are machine-filled by
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
     The RULED, and it precedes any widening. Derive the uncatalogued specimen from the VOCABULARY rather than pinning a country, everywhere a behaviour class is gated by one. The property under test is a country we cannot place, and TH is an accident of when the test was written, so the fixture is coupled to a boundary that was always going to move. Landing the argued tier reds 15 tests: six anti-rot anchors firing exactly as authored, and nine across two peer files, one of which is built NARRATIVELY on Thailand's absence with a module docstring opening Thailand is why this is not a curiosity and constants naming it. Repointing constants is two lines and would leave the rationale prose contradicting the data, which is the defect class this campaign has hit six times. So the fix takes the prose as well as the constants: take any assigned code the table lacks, so the test follows the boundary instead of pinning it. Correct regardless of whether the tier is ever admitted, which is why it lands first and separately. Verified alternates should the derivation prove impractical at a site: SA EG NG VA all still resolve uncatalogued and ## Scope

- `src/cadrumo/application/ledger` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# RULED, and it precedes any widening. Derive the uncatalogued specimen from the VOCABULARY rather than pinning a country, everywhere a behaviour class is gated by one. The property under test is a country we cannot place, and TH is an accident of when the test was written, so the fixture is coupled to a boundary that was always going to move. Landing the argued tier reds 15 tests: six anti-rot anchors firing exactly as authored, and nine across two peer files, one of which is built NARRATIVELY on Thailand's absence with a module docstring opening Thailand is why this is not a curiosity and constants naming it. Repointing constants is two lines and would leave the rationale prose contradicting the data, which is the defect class this campaign has hit six times. So the fix takes the prose as well as the constants: take any assigned code the table lacks, so the test follows the boundary instead of pinning it. Correct regardless of whether the tier is ever admitted, which is why it lands first and separately. Verified alternates should the derivation prove impractical at a site: SA EG NG VA all still resolve uncatalogued

## Scope

- `src/cadrumo/application/ledger`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

- Rest the structured-country degradation suite's ARGUMENT on the property
  rather than on a named country, not only its constants.
- Delete the local candidate pool in favour of the shared specimen helper.
- Gate the reserved alpha-3 cell, which the derivation exposed as untested.
- Stop a production docstring naming the country that happens to be outside the
  vocabulary today.

## Outcome

A behaviour class gated by a specific country is coupled to a boundary that was
always going to move, and the coupling is invisible until it moves. It moved
during this row: the vocabulary was observed changing size twice inside one
session while a sibling lane worked on it, and eight cases in the degradation
suite went red for a reason with nothing to do with the behaviour under test.

The row is delivered across two lanes. The shared helper and five mechanical
sites are a sibling lane's; the helper draws its candidates from AEAT's own SII
enumeration and from Facturae's, so a specimen is a code a real submitted
document can actually state rather than a string nobody would print, and it
derives the two spellings independently because a correspondence for a code
outside the vocabulary is precisely what this tree does not have. This record
covers the seventh site, the narrative one, which was left for its author because
converting it is a rewrite of an argument rather than a constant swap.

**The prose was the substantive half, and it had gone false.** The suite's
constants had already been converted to the shared helper; what survived was a
module docstring resting the whole rationale on one country, including the
sentence "Thailand has since been enrolled" -- written while that was momentarily
true mid-session and false at HEAD, where the code reports uncatalogued. A gate
whose prose asserts a vocabulary state is exactly the hostage the derivation
removes, committed in prose instead of in a constant, and it is the harder one to
see because no test fails for it. The argument now rests on the property: a
country the vocabulary cannot place, whichever one that is today.

The ISO 3166-1 user-assigned ranges are the deliberate exception and stay pinned,
with the reason stated where they are declared. No enrolment can turn a reserved
code into a country, so a literal there can never go stale -- and that asymmetry
is the distinction the whole file exists to keep: a code naming nothing by
construction, against one our data has simply not reached.

**Converting the argument exposed a hole the constants hid.** Writing out the
spelling-by-kind matrix showed three cases and one empty cell: uncatalogued
alpha-2, uncatalogued alpha-3 and unassigned alpha-2 each had one, and unassigned
alpha-3 had none. That cell carries the worst failure on the relief path, where a
reserved alpha-3 misread as a catalogue gap is FORGIVEN -- honouring a declared
zero-rated export claimed on a code with no referent, from the spelling Facturae
states, which is the format most of this corpus arrives in. Both siblings are now
gated.

One instance outside the row's stated scope was closed rather than reported: a
production docstring in the transactions domain cited a named country as "the
live example" of a jurisdiction the vocabulary omits. True at HEAD and about to
stop being true, since the tier admitting it is withheld pending exactly this
sweep. It is prose-only, carries no behaviour, and leaving a known-about-to-be-
false claim in production while recording this defect class would have been
incoherent.

Modified files:

- `src/cadrumo/application/ledger/tests/test_structured_country_degradation.py`
- `src/cadrumo/domain/transactions/_models.py`

## Verification

    uv run --no-sync pytest src/cadrumo/application/ledger/tests src/cadrumo/domain/iva src/cadrumo/adapters/inbound/einvoice -n0 -q -m unit
    1976 passed, 26 deselected, 16 warnings in 218.43s (0:03:38)

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_structured_country_degradation.py -n0 -q -m unit
    25 passed in 13.33s

    uv run --no-sync pytest src/cadrumo/domain/transactions/tests -n0 -q -m unit
    201 passed in 16.73s

The row's own surface, re-run once every file of it was byte-identical to HEAD:

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_structured_country_degradation.py src/cadrumo/application/ledger/tests/test_country_vocabulary_narrowing.py src/cadrumo/application/ledger/tests/test_ingestion_category_resolution.py src/cadrumo/domain/iva -n0 -q -m unit
    794 passed in 72.24s (0:01:12)

Emptying the reserved alpha-3 range set, loaded from outside the repository as a
pytest plugin so nothing under the source tree changed:

    [MUTATION APPLIED] _USER_ASSIGNED_ALPHA3 emptied (was 1092 codes)
    3 failed, 22 passed in 12.53s

Three reds for three distinct reasons -- the anchor, the advisory kind, the
relief refusal -- where the same probe previously reddened only the anchor. The
mutation now reports the coverage rather than reporting its own probe.

A no-op control, identical imports at session start with no mutation, run twice:

    [NO-OP CONTROL] imported domain.iva; ZZZ classifies unassigned
    25 passed

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

The derivation must carry an ANCHOR, and that is the half most easily dropped. A
derived specimen with no anchor can quietly come to name a country the vocabulary
has since admitted, at which point the cases still pass and test nothing -- the
same silent-change-of-subject the pinned constant caused, arrived at from the
other direction. The anchor class asserts the specimen still carries the property
it was selected for, and its docstring states precisely what that adds: the
status axis asks the same resolver the specimen was selected through, so it is
not an independent second opinion, and what it genuinely discriminates is that
the specimen is outside the reserved ranges and that the alpha-3 branch fires.

The row's stated fallbacks (SA, EG, NG, VA) were not needed; the derivation was
practical at every site.

A review of the sibling suite reported both relief cases failing whenever
anything imports the IVA domain at session start. That was valid against the tree
it was measured on, where those cases asserted the relief STANDS and so needed
the filer's territory to resolve. They were rewritten for an unrelated reason
before the report arrived and now assert the refusal and its narrowed reason,
with the single stands-case supplying the filer's scope explicitly rather than
reading a profile. The no-op control above confirms the sensitivity is
structurally gone rather than accidentally quiet, so no serial marker was added.
