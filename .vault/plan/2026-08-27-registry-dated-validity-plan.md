---
tags:
  - '#plan'
  - '#registry-dated-validity'
date: '2026-08-27'
tier: L2
related:
  - '[[2026-08-27-registry-dated-validity-adr]]'
  - '[[2026-08-27-registry-dated-validity-research]]'
modified: '2026-08-27'
body_schema: body-v2
body_hash: 'sha256:a47f60fa4d0c3ac07d69efb903f2cf54b825e2a66f09e429be061dac456a47f5'
---

<!-- RETIRED: S01 -->

# `registry-dated-validity` plan

## Description

## Steps

### Phase `P01` - Window primitive and the categories reference implementation

Land the shared closed-window primitive together with its first consumer, collapse the two spending-category profile years onto it, and rewrite the two coverage gates that read year-named filenames. The primitive never ships alone: it lands with the corpus that exercises it.

- [x] `P01.S02` - Add the closed ValidityWindow primitive as a public canonical core module, with both bounds required, no default and no open end, a from-before-to invariant, and year-coverage derivation over a group of windows, plus real-behaviour tests including a refusal proof for an omitted bound; `src/cadrumo/core/validity_window.py and src/cadrumo/core/tests/`.
- [x] `P01.S03` - Collapse the two spending-category profile years into one undated file carrying a required ValidityWindow on every citation, drop the forty-one mirrored 2024 citations rather than re-windowing them, derive covered years from the citation windows, preserve the exact-year refusal unchanged, update every consumer and fixture, and delete the year-named files and their tests outright in the same commit; `src/cadrumo/_data/registry/aeat/categories/ and src/cadrumo/domain/categories/`.
- [x] `P01.S04` - Rewrite the two year-coverage gates off the year-named-filename premise onto derived window coverage, replacing the withhold-a-file bite proof with a narrow-a-window bite proof, keeping both assertions on the property and never on a tally, and keeping the resolver-refuses-a-miss anchor; `src/cadrumo/application/registry/tests/ and src/cadrumo/domain/iva/tests/`.
- [x] `P01.S05` - Add the anti-mirror gate refusing a citation whose reference or url names a filing year while its window reaches outside that year, keyed on the citation's own two fields so no allowlist is possible; `src/cadrumo/domain/categories/tests/`.

### Phase `P02` - The IVA corpora onto the same pattern

Collapse the two year-named IVA corpora, whose content is year-neutral throughout, authoring each window from the cited provision's own effective span in the legal catalogue and checking it there rather than accepting an author's assertion.

- [x] `P02.S06` - Add the provision-window gate refusing any grounded row whose validity window reaches outside the intersection of its cited provisions' own effective spans in the registry legal catalogue, so the permissible span is derived from the catalogue rather than attested by the author, and fails closed on a provision repealed or effective mid-window; `src/cadrumo/domain/iva/tests/`.
- [x] `P02.S07` - Collapse the IVA regulation catalogue into one undated file with a required ValidityWindow on every citation authored from the cited provision's effective span, derive covered years from those windows, preserve the exact-year refusal, and delete the year-named file and its filename-year loader branch outright; `src/cadrumo/_data/registry/aeat/iva/ and src/cadrumo/domain/iva/`.
- [x] `P02.S08` - Collapse the IVA place-of-supply groundings the same way, attaching the window to the rule rather than to a citation because the rule is the grounding-bearing row there, and checking it against the intersection of its legal_references' effective spans; `src/cadrumo/_data/registry/aeat/iva/ and src/cadrumo/domain/iva/`.

### Phase `P03` - Proof and close

Prove every new gate bites by breaking the production data from outside the tracked tree, re-measure the coverage baseline against the recorded pre-change state, and record what the migration deliberately did not fix.

- [x] `P03.S09` - Prove every new gate bites by mutating the production data from outside the tracked tree, confirming each red and restoring, covering the omitted bound, the widened year-named citation and the widened provision window; `src/cadrumo/domain/ and src/cadrumo/core/`.
- [x] `P03.S10` - Re-measure the coverage gates against the recorded pre-change baseline of three failing corpora, confirm the two IVA corpora resolve green on derived provision-checked coverage and that the categories red is a genuine grounding gap rather than a regression, and run the affected suites sequentially; `src/cadrumo/ and dev/`.
- [x] `P03.S11` - Record in the vault what this migration deliberately did not fix, being the exact-year pinning defect reserved to its own brief, the category citation quote fields that carry locale keys absent from all four catalogues, and the three under-cited profiles whose 2024 coverage is withdrawn pending the bundled 2024 manual; `.vault/audit/`.

### Phase `P04` - Ground the spending-category corpus to the supported window

Close the coverage red the format migration correctly surfaced, by grounding what the corpus asserts rather than by widening what it claims. Driven after the format work because the defect it uncovered -- a year-variable statutory cap encoded as a wrong constant -- could only be seen once the mirror was gone.

- [x] `P04.S12` - Obtain the official RETA cuota maxima por contingencias comunes for every supported filing year from AEAT and BOE primary sources, cross-checking each figure against a second official source and verifying that AEAT's own published method reproduces every published year before using it to derive the one year AEAT has not yet published; `external official sources, recorded in the feature audit`.
- [x] `P04.S13` - Extend ProportionalityRule with dated statutory-cap rows so a cap the law re-fixes each ejercicio stops being a constant, make a cap either law-fixed or year-referenced but never both, refuse two amounts for one year, and intersect cap availability into the coverage derivation so the corpus cannot claim a year it can cite but not compute; `src/cadrumo/domain/categories/ and src/cadrumo/domain/categories/tests/`.
- [x] `P04.S14` - Enrol RIRPF art. 9 and art. 22 in the legal catalogue from the already-bundled consolidated RD 439/2007, with required_text phrases read out of that file and verified present before writing, agent_reviewed provenance and an explicit operator-re-stamp note; `src/cadrumo/_data/registry/aeat/legal/irpf.toml`.
- [x] `P04.S15` - Partition the citation sources so every citation is bounded on exactly one axis, require a provision id on statutory citations, derive each statutory window from its provision's effective span intersected with the supported filing window, and give the three statutorily-uncited profiles the article their rule rests on quoted verbatim from the bundled corpus; `src/cadrumo/domain/categories/ and src/cadrumo/_data/registry/aeat/categories/profiles.toml`.
- [x] `P04.S16` - Prove every new gate bites by mutating the shipped corpus from outside the tracked tree, covering a stripped provision id, a window widened past its provision, a cap edited away from the AEAT figure and a cap schedule moved off a year the citations still cover, then re-run both coverage gates; `src/cadrumo/domain/categories/ and src/cadrumo/application/registry/tests/`.

### Phase `P05` - Fix the defects the frozen-constant hunt confirmed

Turn the hunt's findings into product behaviour. Each fix reuses the mechanism this codebase already has for the job rather than adding a second way to say the same thing, and lands with a gate proven to bite from outside the tracked tree.

- [x] `P05.S17` - Measure the Art. 109 seventy per cent over the base the reglamento names: exclude subvenciones corrientes, subvenciones de capital and indemnizaciones for the agrarian apartados, gate the exemption to the activity classes art. 109 grants it to, and fail closed on a row that does not declare its activity class rather than guessing an exemption for it; `src/cadrumo/core/_concepto_ingreso.py, src/cadrumo/domain/transactions/, src/cadrumo/application/modelo/_art109_activity_income.py and src/cadrumo/_data/registry/aeat/legal/irpf-retencion-actividades.toml`.
- [x] `P05.S18` - Carry both limits LIRPF art. 30.2.5.a states for the seguro de enfermedad by widening the statutory-cap variant to an annual per-person amount alongside its daily one, declaring the 500 and 1.500 limbs in the corpus, and summing each limb over its own population, with an uncounted caller falling back to the ordinary limb so widening the rule regresses nobody; `src/cadrumo/domain/categories/ and src/cadrumo/domain/renta/ and src/cadrumo/_data/registry/aeat/categories/profiles.toml`.
- [x] `P05.S19` - Count the tier c) rehabilitation window in calendar years rather than in days, relocating the leap-clamping year shift out of the retention domain into a neutrally named core primitive both consumers read, and retiring the days-declared registry parameter across every revision that carried it so no declaration describes a unit the code no longer uses; `src/cadrumo/core/calendar_shift.py and src/cadrumo/domain/fincas/ and src/cadrumo/domain/retention/ and src/cadrumo/_data/registry/aeat/modelos/100/revisions/`.

## Parallelization

`P01.S02` and `P01.S03` through `P01.S05` are one atomic landing, not four commits: the
primitive would otherwise ship as an unused shell, and the two coverage gates read the
year-named filenames the collapse deletes, so they break the moment the corpus moves.
They are separate rows because they are separately reviewable, and they share one commit.

`P02` depends on `P01` for the primitive and for the rewritten coverage gates. Inside
`P02`, `S06` precedes `S07` and `S08` because the provision-window gate is what makes the
authored windows checkable rather than asserted; `S07` and `S08` touch disjoint corpora
and disjoint models and could be taken in either order.

`P03` is strictly last. `S09` cannot prove a gate bites before the gate has data to bite
on, and `S10`'s comparison is meaningless before both corpora have moved.

## Verification

The recorded pre-change baseline is three failing coverage parameterisations in
`src/cadrumo/application/registry/tests/test_exact_key_corpus_year_coverage.py` (six
passing) and two in
`src/cadrumo/domain/iva/tests/test_year_coverage_matches_supported_filing_years.py`, all
pre-existing at `507a5fb98b`. Any comparison that does not start from those numbers will
misattribute a red.

Every gate added here is proven by breaking the production data and observing the red,
using a runtime mutation from outside the tracked tree so no file under `src` changes and
a crashed run leaves no residue. Three mutations are required: an omitted window bound, a
year-named citation widened past its own year, and a window widened past its cited
provision's effective span.

The migration is correct when the two IVA corpora resolve every supported filing year
from derived provision-checked windows, the categories corpus resolves 2025 and refuses
every other year with its existing refusal type, and no consumer, fixture or locale
scanner reads a year-named filename. The categories red on the coverage gate is expected
and is a genuine grounding gap; closing it means grounding, never mirroring.

Assertions are on the property throughout. No file count, module count or year tally is
encoded as a pass condition.
