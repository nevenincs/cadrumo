---
tags:
  - '#plan'
  - '#registry-temporal-coverage'
date: '2026-09-10'
tier: L3
related:
  - '[[2026-09-10-registry-temporal-coverage-corpus-tier-enforcement-adr]]'
  - '[[2026-09-10-registry-temporal-coverage-corpus-tier-enforcement-research]]'
  - '[[2026-09-10-corpus-evidence-integrity-hand-shaped-corpus-text-research]]'
modified: '2026-09-10'
body_schema: body-v2
body_hash: 'sha256:379efc919299feb686057c405b66edfca66874bc8e3275673f08a08d65de0d12'
---

# `registry-temporal-coverage` plan

Implement the amended corpus-tier enforcement ADR as a provenance gate: derive the origin class from normative-corpus bytes, bind filing-grade legal authority to that class, re-ground the five identified hand-shaped files and six citations, then prove the committed authority fails closed. The plan is grounded in the related ADR and research.

## Description

Wave W01 establishes the canonical classifier and authority boundary. Wave W05 performs the prerequisite official-text remediation in independently reviewable corpus and catalogue edits. Wave W06 verifies both the committed catalogue and isolated defects through production validation. `corpus_tier` remains independently validated; this plan does not add a mandatory tier sweep.

## Engineering Goal

Ship one filing-authority provenance contract for `corpus/normatives/`: every `LegalReference` must derive its evidence class from the bundled bytes; BOE-attested files are accepted, BOE-presumptive files are accepted only through an explicit reviewed per-file record, and authored files are refused before citation clauses can promote them. The contract is complete only when the six formerly authored filing citations use BOE-attested captures with fresh sidecars, `ValidatedRegistryAuthority` exposes the same derived classification, and the committed registry plus corpus-integrity gates prove that no authored filing authority can pass.

## Steps

## Wave `W01` - derive normative corpus provenance

Establish a file-derived provenance classifier and bind filing-grade legal authority to it before any corpus remediation is relied on.

### Phase `W01.P01` - define classifier boundary

Introduce one canonical provenance classifier for normative corpus files and prove each derived state from isolated fixtures.

- [x] `W01.P01.S01` - Define the derived normative-corpus provenance classifier and its file-resolution contract; `src/cadrumo/domain/calculations/registry/corpus_provenance.py`.
- [x] `W01.P01.S02` - Prove attested, presumptive, authored, and out-of-scope provenance classifications with isolated corpus fixtures; `src/cadrumo/domain/calculations/registry/tests/test_corpus_provenance.py`.

### Phase `W01.P02` - enforce legal-authority provenance

Wire provenance into the canonical legal validation path so filing-grade citations fail closed on authored evidence.

- [x] `W01.P02.S03` - Bind derived provenance to legal-reference evidence-tier validation and correct the stale corpus-tier coverage statement; `src/cadrumo/domain/calculations/registry/legal.py`.
- [x] `W01.P02.S04` - Exercise accepted, presumptive-exception, and authored-refusal legal-reference cases through the real validator; `src/cadrumo/domain/calculations/registry/tests/test_registry_legal_grounding.py`.
- [x] `W01.P02.S05` - Expose provenance classification through the validated authority without a second resolver path; `src/cadrumo/domain/calculations/registry/authority.py`.
- [x] `W01.P02.S06` - Verify validated-authority publication preserves the provenance-bound legal authority contract; `src/cadrumo/domain/calculations/registry/tests/test_authority.py`.

## Wave `W05` - reground authored legal evidence

Replace or downgrade every filing-grade citation backed by hand-shaped corpus text before enabling the provenance refusal.

### Phase `W05.P09` - repair censo citations

Re-ground both Orden HAC/1526/2024 citations against official text and retain only verifiable corpus evidence.

- [x] `W05.P09.S24` - Replace the hand-shaped Orden HAC/1526/2024 article corpus capture with official BOE-derived text; `src/cadrumo/_data/corpus/normatives/html/orden-hac-1526-2024-art-1.html`.
- [x] `W05.P09.S25` - Replace the hand-shaped Orden HAC/1526/2024 final-provision corpus capture with official BOE-derived text; `src/cadrumo/_data/corpus/normatives/html/orden-hac-1526-2024-df-unica.html`.
- [x] `W05.P09.S26` - Re-ground the Censo legal catalogue entries to the replaced Orden HAC/1526/2024 corpus evidence; `src/cadrumo/_data/registry/aeat/legal/censo.toml`.

### Phase `W05.P10` - repair IRNR legal evidence

Re-ground the M216 citations that currently resolve through a hand-shaped order capture.

- [x] `W05.P10.S27` - Replace the hand-shaped Orden EHA/3290/2008 corpus capture with official BOE-derived article captures; `src/cadrumo/_data/corpus/normatives/html/`.
- [x] `W05.P10.S28` - Re-ground the IRNR legal catalogue entries to the replaced Orden EHA/3290/2008 corpus evidence; `src/cadrumo/_data/registry/aeat/legal/irnr.toml`.

### Phase `W05.P11` - repair IRPF and IVA legal evidence

Remove the identified editorial or hand-shaped text from filing-grade legal evidence in the remaining catalogues.

- [x] `W05.P11.S29` - Replace the Ley 35/2006 article 48 corpus capture with official text separated from editorial gloss; `src/cadrumo/_data/corpus/normatives/html/ley-35-2006-art-48.html`.
- [x] `W05.P11.S30` - Re-ground the IRPF legal catalogue entry to the repaired Ley 35/2006 article 48 corpus evidence; `src/cadrumo/_data/registry/aeat/legal/irpf.toml`.
- [x] `W05.P11.S31` - Replace the Ley 12/2002 corpus capture with official BOE-derived text; `src/cadrumo/_data/corpus/normatives/html/ley-12-2002.html`.
- [x] `W05.P11.S32` - Re-ground the IVA legal catalogue entry to the replaced Ley 12/2002 corpus evidence; `src/cadrumo/_data/registry/aeat/legal/iva.toml`.

## Wave `W06` - verify provenance closure

Demonstrate that the repaired committed corpus and the real registry authority refuse unattributed filing-grade evidence while preserving valid authority.

### Phase `W06.P12` - prove committed-registry closure

Exercise the production registry and isolated defects through the same validation boundary used for authority publication.

- [ ] `W06.P12.S33` - Assert every committed legal catalogue entry satisfies its provenance-bound filing-authority contract; `src/cadrumo/domain/calculations/registry/tests/test_registry_legal_grounding.py`.
- [ ] `W06.P12.S34` - Verify normative corpus catalogue resolution preserves provenance classification without weakening byte-integrity checks; `src/cadrumo/domain/calculations/registry/tests/test_corpus_catalogue_companion.py`.

## Parallelization

W01 is a hard prerequisite for W05 and W06. Within W01, P01 precedes P02. Within W05, P09, P10, and P11 may proceed in parallel because they own different corpus and catalogue files; each catalogue update follows its paired corpus replacement. W06 begins only after W01 and all W05 phases are complete.

## Verification

The provenance-classifier fixture suite must prove every derived state and the authored filing-grade refusal. The legal grounding and authority suites must load the real committed registry and confirm valid BOE-attested entries remain accepted. The corpus catalogue verification must retain path, digest, and byte-integrity checks. The full relevant registry test suite, plan check, and Vaultspec validation must pass before closeout.
