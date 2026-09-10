---
tags:
  - '#plan'
  - '#corpus-evidence-integrity'
date: '2026-09-10'
tier: L2
related:
  - '[[2026-09-10-corpus-evidence-integrity-corpus-text-provenance-adr]]'
  - '[[2026-09-10-corpus-evidence-integrity-hand-shaped-corpus-text-research]]'
  - '[[2026-08-28-corpus-evidence-integrity-corpus-editorial-gloss-hazard-audit]]'
  - '[[2026-09-10-registry-temporal-coverage-corpus-tier-enforcement-adr]]'
modified: '2026-09-10'
body_schema: body-v2
body_hash: 'sha256:96db31d0fa77f3328d7915a80ff248e9c19717b595f6c99c6a00fa48bd9c8e90'
---

# `corpus-evidence-integrity` plan

Make corpus text attestation a derived, unbypassable property, and clear the population it
refuses before arming it.

## Description

This plan executes `2026-09-10-corpus-evidence-integrity-corpus-text-provenance-adr`. The
registry checks that a citation corresponds to its corpus file and that the file states an
operative provision, but nothing checks that the text came from BOE rather than an author.
`2026-09-10-corpus-evidence-integrity-hand-shaped-corpus-text-research` measures the
population: five files, six citations, five of them claiming `legal_authority`.

`P01` is a precondition, not cleanup. Every one of those citations is re-grounded against
real BOE text before the refusal is armed in `P03`, so the gate does not land red. `P01.S04`
and `P01.S05` also close the editorial-gloss case that
`2026-08-28-corpus-evidence-integrity-corpus-editorial-gloss-hazard-audit` recorded, using
the remediation shape that audit judged the more faithful: law text in the corpus file,
commentary in the entry notes.

`P02` builds the classifier as its own canonical public module. It is named for
**attestation** rather than provenance deliberately: `test_corpus_provenance_coverage.py`
already owns "provenance" for a different question - whether a payload's origin is recorded
at all - and `aeat-naming` forbids two senses of one stem. `P03` arms the refusal at both
citation boundaries and adds the exception surface.

`2026-09-10-registry-temporal-coverage-corpus-tier-enforcement-adr` is listed as a governing
document for sequencing only; this plan does not execute it. That record's bounded migration
must classify the same files `P01` replaces, and doing so before `P01` lands would assign a
tier to a paraphrase. No Step here mutates that feature's surface.

## Steps

### Phase `P01` - Re-ground the authored citations

Clear the population the gate will refuse, so the refusal is not born red. The six citations resting on hand-shaped corpus text are re-grounded against real BOE text, and the editorial gloss is separated from law text.

- [x] `P01.S01` - Replace the two hand-shaped Orden HAC/1526/2024 excerpts with the real BOE consolidated text for article 1 and the disposicion final unica, verified against the live BOE record; `src/cadrumo/_data/corpus/normatives/html/orden-hac-1526-2024-art-1.html`.
- [x] `P01.S15` - Re-verify every required_text phrase on the two Orden HAC/1526/2024 entries against the replaced BOE text, replacing the unaccented phrasings that only matched the paraphrase; `src/cadrumo/_data/registry/aeat/legal/censo.toml`.
- [x] `P01.S02` - Replace the hand-shaped Orden EHA/3290/2008 excerpt with the real BOE consolidated text for articles 1 and 4, preserving both existing anchors; `src/cadrumo/_data/corpus/normatives/html/orden-eha-3290-2008.html`.
- [x] `P01.S16` - Re-verify every required_text phrase on the two Orden EHA/3290/2008 entries against the replaced BOE text and correct the reviewed_by claim of a verbatim BOE fetch that the bundled file contradicts; `src/cadrumo/_data/registry/aeat/legal/irnr.toml`.
- [x] `P01.S03` - Replace the hand-shaped Ley 12/2002 article 29 excerpt with the real BOE consolidated text of the Concierto Economico provision; `src/cadrumo/_data/corpus/normatives/html/ley-12-2002.html`.
- [x] `P01.S17` - Re-verify every required_text phrase on the Ley 12/2002 article 29 entry against the replaced BOE text; `src/cadrumo/_data/registry/aeat/legal/iva.toml`.
- [x] `P01.S04` - Replace the hand-shaped Ley 35/2006 article 48 law text with the real BOE consolidated text and drop the appended editorial section from the corpus file; `src/cadrumo/_data/corpus/normatives/html/ley-35-2006-art-48.html`.
- [x] `P01.S05` - Move the casilla commentary displaced from the article 48 excerpt into the legal entry notes and re-verify every required_text phrase against the replaced corpus text; `src/cadrumo/_data/registry/aeat/legal/irpf.toml`.

### Phase `P02` - Canonical text-attestation classifier

Add the derived three-valued classification as its own public defining module, with the enum and classifier colocated, exercised on an isolated fixture tree before any consumer depends on it.

- [ ] `P02.S06` - Define the CorpusAttestation enum and the derived classifier that reads a normative corpus file and returns boe_attested, boe_presumptive, or authored, named to avoid colliding with the existing file-origin provenance gate; `src/cadrumo/domain/calculations/registry/corpus_text_attestation.py`.
- [ ] `P02.S07` - Prove the classifier's teeth on an isolated fixture tree covering each band, a BOE-markup file without an identifier, and a representative authored defect, without mutating the bundled corpus; `src/cadrumo/domain/calculations/registry/tests/test_corpus_text_attestation.py`.

### Phase `P03` - Bind attestation to evidence tier

Arm the refusal at both citation boundaries and add the narrowly-keyed exception surface, keeping the classification visible through the resolved result rather than flattening it.

- [ ] `P03.S08` - Refuse a legal_authority LegalReference whose corpus text does not classify as boe_attested, and delegate to the shared classifier rather than a second reader; `src/cadrumo/domain/calculations/registry/legal.py`.
- [ ] `P03.S09` - Apply the same refusal at the SourceReference boundary for targets resolving under the normatives tree, reusing the shared classifier; `src/cadrumo/domain/calculations/registry/corpus_catalogue.py`.
- [ ] `P03.S10` - Add the per-file exception surface admitting boe_presumptive text for legal_authority with a required reason, keyed to one corpus file and rejecting prefix or count-based entries; `src/cadrumo/domain/calculations/registry/corpus_text_attestation.py`.
- [ ] `P03.S11` - Carry the attestation band into the resolved citation and its explanation so an authored or presumptive classification stays visible to the filing handoff rather than collapsing to a boolean; `src/cadrumo/domain/calculations/registry/schema_references.py`.
- [ ] `P03.S12` - Cover positive resolution, refusal at both boundaries, valid and invalid exception entries, and parity between the legal and source paths against the real compiled registry; `src/cadrumo/domain/calculations/registry/tests/test_corpus_attestation_binding.py`.

### Phase `P04` - Closeout

Correct the stale coverage docstring, run the owning gates, and confirm no regression against the full registry authority.

- [ ] `P04.S13` - Correct the corpus-tier validator docstring that states no committed entry declares corpus_tier, which nineteen entries now contradict; `src/cadrumo/domain/calculations/registry/legal.py`.
- [ ] `P04.S14` - Run the registry lane and confirm the full authority still compiles and publishes a validated snapshot with the refusal armed; `justfile`.

## Parallelization

`P01.S01` through `P01.S04` touch four independent corpus files and may run in parallel.
`P01.S05` depends on `P01.S04`, since the notes it writes are the text that step removes and
its `required_text` re-verification reads the replaced file.

`P02` is independent of `P01` and may run alongside it: the classifier and its fixture tests
touch no bundled corpus file. `P02.S07` depends on `P02.S06`.

`P03` carries hard ordering behind both. `P03.S08` and `P03.S09` arm refusals that `P01`
must have cleared, and all of `P03` depends on the classifier from `P02.S06`. Within `P03`,
`S08` and `S09` are parallel; `S10` and `S11` follow `S06`; `S12` runs last.

`P04.S13` is an isolated docstring correction with no dependency and may run at any point.
`P04.S14` runs last by definition.

One writer per file: `P02.S06` and `P03.S10` both target the attestation module, and
`P03.S08` and `P04.S13` both target `legal.py`. Those pairs must not run concurrently.

## Verification

- The classifier assigns each of the three bands correctly on an isolated fixture tree, and
  a representative authored defect is detected rather than passed (`P02.S07`).
- A `legal_authority` citation resolving to authored text is refused at the `LegalReference`
  boundary, and the equivalent `SourceReference` case is refused identically (`P03.S12`).
- An exception entry admits exactly one named file with a stated reason; a prefix, pattern,
  or count-based entry is rejected (`P03.S12`).
- The attestation band survives into the resolved citation and its explanation, verified as a
  distinct value rather than a boolean (`P03.S12`).
- No file under the normative corpus classifies as `authored` while any citation of it
  declares `legal_authority`, measured against the real compiled registry.
- `ValidatedRegistryAuthority` compiles and publishes a validated snapshot with the refusal
  armed, and the registry lane passes with its exit status recorded (`P04.S14`).
- Every `required_text` phrase on the five re-grounded entries still resolves against the
  replaced BOE text; an `ABSENT` result proves a defect in the replacement, not the registry.
