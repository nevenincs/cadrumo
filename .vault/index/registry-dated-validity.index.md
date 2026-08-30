---
generated: true
tags:
  - '#index'
  - '#registry-dated-validity'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:cf5b7ed25eee66fdb3a73f6941c48a72f984b1946b93b7c383b6bf633ca2a061'
related:
  - '[[2026-08-27-registry-dated-validity-P01-S02]]'
  - '[[2026-08-27-registry-dated-validity-P01-S03]]'
  - '[[2026-08-27-registry-dated-validity-P01-S04]]'
  - '[[2026-08-27-registry-dated-validity-P01-S05]]'
  - '[[2026-08-27-registry-dated-validity-P02-S06]]'
  - '[[2026-08-27-registry-dated-validity-P02-S07]]'
  - '[[2026-08-27-registry-dated-validity-P02-S08]]'
  - '[[2026-08-27-registry-dated-validity-P03-S09]]'
  - '[[2026-08-27-registry-dated-validity-P03-S10]]'
  - '[[2026-08-27-registry-dated-validity-P03-S11]]'
  - '[[2026-08-27-registry-dated-validity-P04-S12]]'
  - '[[2026-08-27-registry-dated-validity-P04-S13]]'
  - '[[2026-08-27-registry-dated-validity-P04-S14]]'
  - '[[2026-08-27-registry-dated-validity-P04-S15]]'
  - '[[2026-08-27-registry-dated-validity-P04-S16]]'
  - '[[2026-08-27-registry-dated-validity-P05-S17]]'
  - '[[2026-08-27-registry-dated-validity-P05-S18]]'
  - '[[2026-08-27-registry-dated-validity-P05-S19]]'
  - '[[2026-08-27-registry-dated-validity-P05-S20]]'
  - '[[2026-08-27-registry-dated-validity-P05-S21]]'
  - '[[2026-08-27-registry-dated-validity-P05-S22]]'
  - '[[2026-08-27-registry-dated-validity-P05-S23]]'
  - '[[2026-08-27-registry-dated-validity-P05-S24]]'
  - '[[2026-08-27-registry-dated-validity-adr]]'
  - '[[2026-08-27-registry-dated-validity-audit]]'
  - '[[2026-08-27-registry-dated-validity-frozen-constant-hunt-audit]]'
  - '[[2026-08-27-registry-dated-validity-plan]]'
  - '[[2026-08-27-registry-dated-validity-research]]'
---

# `registry-dated-validity` feature index

Auto-generated index of all documents tagged with `#registry-dated-validity`.

## Documents

### adr

- `2026-08-27-registry-dated-validity-adr` - `registry-dated-validity` adr: `dated citation windows replace whole-file-per-year copies, and a window is a grounding claim` | (**status:** `accepted`)

### audit

- `2026-08-27-registry-dated-validity-audit` - `registry-dated-validity` audit: `what the collapse deliberately did not fix`
- `2026-08-27-registry-dated-validity-frozen-constant-hunt-audit` - `registry-dated-validity` audit: `regulatory values that do not match the provision that governs them`

### exec

- `2026-08-27-registry-dated-validity-P01-S02` - Add the closed ValidityWindow primitive as a public canonical core module, with both bounds required, no default and no open end, a from-before-to invariant, and year-coverage derivation over a group of windows, plus real-behaviour tests including a refusal proof for an omitted bound
- `2026-08-27-registry-dated-validity-P01-S03` - Collapse the two spending-category profile years into one undated file carrying a required ValidityWindow on every citation, drop the forty-one mirrored 2024 citations rather than re-windowing them, derive covered years from the citation windows, preserve the exact-year refusal unchanged, update every consumer and fixture, and delete the year-named files and their tests outright in the same commit
- `2026-08-27-registry-dated-validity-P01-S04` - Rewrite the two year-coverage gates off the year-named-filename premise onto derived window coverage, replacing the withhold-a-file bite proof with a narrow-a-window bite proof, keeping both assertions on the property and never on a tally, and keeping the resolver-refuses-a-miss anchor
- `2026-08-27-registry-dated-validity-P01-S05` - Add the anti-mirror gate refusing a citation whose reference or url names a filing year while its window reaches outside that year, keyed on the citation's own two fields so no allowlist is possible
- `2026-08-27-registry-dated-validity-P02-S06` - Add the provision-window gate refusing any grounded row whose validity window reaches outside the intersection of its cited provisions' own effective spans in the registry legal catalogue, so the permissible span is derived from the catalogue rather than attested by the author, and fails closed on a provision repealed or effective mid-window
- `2026-08-27-registry-dated-validity-P02-S07` - Collapse the IVA regulation catalogue into one undated file with a required ValidityWindow on every citation authored from the cited provision's effective span, derive covered years from those windows, preserve the exact-year refusal, and delete the year-named file and its filename-year loader branch outright
- `2026-08-27-registry-dated-validity-P02-S08` - Collapse the IVA place-of-supply groundings the same way, attaching the window to the rule rather than to a citation because the rule is the grounding-bearing row there, and checking it against the intersection of its legal_references' effective spans
- `2026-08-27-registry-dated-validity-P03-S09` - Prove every new gate bites by mutating the production data from outside the tracked tree, confirming each red and restoring, covering the omitted bound, the widened year-named citation and the widened provision window
- `2026-08-27-registry-dated-validity-P03-S10` - Re-measure the coverage gates against the recorded pre-change baseline of three failing corpora, confirm the two IVA corpora resolve green on derived provision-checked coverage and that the categories red is a genuine grounding gap rather than a regression, and run the affected suites sequentially
- `2026-08-27-registry-dated-validity-P03-S11` - Record in the vault what this migration deliberately did not fix, being the exact-year pinning defect reserved to its own brief, the category citation quote fields that carry locale keys absent from all four catalogues, and the three under-cited profiles whose 2024 coverage is withdrawn pending the bundled 2024 manual
- `2026-08-27-registry-dated-validity-P04-S12` - Obtain the official RETA cuota maxima por contingencias comunes for every supported filing year from AEAT and BOE primary sources, cross-checking each figure against a second official source and verifying that AEAT's own published method reproduces every published year before using it to derive the one year AEAT has not yet published
- `2026-08-27-registry-dated-validity-P04-S13` - Extend ProportionalityRule with dated statutory-cap rows so a cap the law re-fixes each ejercicio stops being a constant, make a cap either law-fixed or year-referenced but never both, refuse two amounts for one year, and intersect cap availability into the coverage derivation so the corpus cannot claim a year it can cite but not compute
- `2026-08-27-registry-dated-validity-P04-S14` - Enrol RIRPF art. 9 and art. 22 in the legal catalogue from the already-bundled consolidated RD 439/2007, with required_text phrases read out of that file and verified present before writing, agent_reviewed provenance and an explicit operator-re-stamp note
- `2026-08-27-registry-dated-validity-P04-S15` - Partition the citation sources so every citation is bounded on exactly one axis, require a provision id on statutory citations, derive each statutory window from its provision's effective span intersected with the supported filing window, and give the three statutorily-uncited profiles the article their rule rests on quoted verbatim from the bundled corpus
- `2026-08-27-registry-dated-validity-P04-S16` - Prove every new gate bites by mutating the shipped corpus from outside the tracked tree, covering a stripped provision id, a window widened past its provision, a cap edited away from the AEAT figure and a cap schedule moved off a year the citations still cover, then re-run both coverage gates
- `2026-08-27-registry-dated-validity-P05-S17` - Measure the Art. 109 seventy per cent over the base the reglamento names: exclude subvenciones corrientes, subvenciones de capital and indemnizaciones for the agrarian apartados, gate the exemption to the activity classes art. 109 grants it to, and fail closed on a row that does not declare its activity class rather than guessing an exemption for it
- `2026-08-27-registry-dated-validity-P05-S18` - Carry both limits LIRPF art. 30.2.5.a states for the seguro de enfermedad by widening the statutory-cap variant to an annual per-person amount alongside its daily one, declaring the 500 and 1.500 limbs in the corpus, and summing each limb over its own population, with an uncounted caller falling back to the ordinary limb so widening the rule regresses nobody
- `2026-08-27-registry-dated-validity-P05-S19` - Count the tier c) rehabilitation window in calendar years rather than in days, relocating the leap-clamping year shift out of the retention domain into a neutrally named core primitive both consumers read, and retiring the days-declared registry parameter across every revision that carried it so no declaration describes a unit the code no longer uses
- `2026-08-27-registry-dated-validity-P05-S20` - Derive the Art. 30.2.5.a insured population and its two limbs from the family profile, keeping membership and limb as separate questions and refusing the wider Art. 58.1 set that would admit a non-cohabiting dependent child and an over-25 child with discapacidad, and expose it beside the one canonical reconstruction of the family record from stored facts
- `2026-08-27-registry-dated-validity-P05-S21` - Wire the LIRPF art. 30.2.5.a insured-person counts into the shipped aggregation so both cap limbs reach production
- `2026-08-27-registry-dated-validity-P05-S22` - Ground every category citation on inline corpus text with a declared verified, refused or not-bundled state
- `2026-08-27-registry-dated-validity-P05-S23` - Retire the fabricated home-office usage-ratio default so a suministro deduction requires the taxpayer's own declared proportion
- `2026-08-27-registry-dated-validity-P05-S24` - Carry the censo-declared dwelling area into the deduction and centralise the home-office grouping

### plan

- `2026-08-27-registry-dated-validity-plan` - `registry-dated-validity` plan

### research

- `2026-08-27-registry-dated-validity-research` - `registry-dated-validity` research: `whole-file-per-year duplication, the four validity spellings, and what the copies actually assert`
