---
tags:
  - '#audit'
  - '#m303-carry-reconciliation'
date: '2026-08-10'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:0270178e4f10336da1d52b95ada4f7684d5afc9eb4b906c1a1a28914f3b2c612'
related:
  - "[[2026-08-07-m303-carry-reconciliation-plan]]"
---

# `m303-carry-reconciliation` audit: `M303 S13 filed-population measurement blocker`

## Scope

Audit whether S13 has a real Modelo 303 population: a persisted filed
declaration with a declaration-PDF artefact but no submitted-file artefact.
The step permits render recovery only after that population is measured; test
fixtures and static branch shapes are insufficient.

## Findings

### encrypted-live-corpus | high | The persisted population cannot be enumerated without an unlocked profile

The production path persists a `FiledDeclaracionObservation` through the
active-profile encrypted store. Its `list_observations()` reader requires the
same active bucket session as real capture. The read-only `aeat config profile
status --json` probe refused with `reason: absent`; no active profile was
unlocked. The storage inventory exposes only category-level state, not
decrypted artefact kinds. Therefore no count, including zero, is established.

### encrypted-live-corpus-resolved | low | The authorized production query found no Modelo 303 observations

After the prior blocked attempt, the selected profile was separately unlocked
and the real encrypted store was enumerated under its active master-key provider.
The aggregate-only query returned `total_m303=0`,
`m303_with_submitted_file=0`, `m303_with_declaration_pdf=0`, and
`m303_declaration_pdf_without_submitted_file=0`. It read only `modelo` and
artefact kinds and emitted no identifiers, artefact content, stored values,
paths, or storage references. This resolves the access finding for the current
active-profile corpus, but it does not turn an empty M303 slice into evidence
that submitted-file coverage is complete in a non-empty corpus.

### conditional-capture-shape | medium | Repository invariants do not prove submitted-file universality

The Sede capture records a submitted-file artefact only when a live declaration
row offers the archive link, and records a declaration-PDF artefact independently
when its copy link is available. The observation model requires one or more
artefacts but does not require a submitted file. This proves the target shape is
representable, not that an M303 record in the operator's live corpus has it.

### fixture-boundary | low | Exporter and bundled render specimens cannot answer the population question

The plan and prior S13/S15 history distinguish registry/exporter structural
evidence from AEAT-served filed evidence. Existing fixtures can validate a
grounded recovery parser if the population is measured, but cannot prove an
operator's persisted filing population is empty or non-empty.

## Recommendations

- The prior leave-open recommendation is superseded by the authorized
  aggregate-only measurement and its independent approval. Close S13 under its
  explicit zero-target criterion without adding a declaracion-render parser.
- Retain the scope boundary: the result concerns the current active-profile
  corpus at measurement time, and provides no submitted-file coverage claim for
  a non-empty M303 corpus.
- If a later measurement finds a non-zero missing-submitted-file plus
  declaration-PDF count, reopen the recovery question and ground it on which
  AEAT render slot carries a value, never on the pre-printed C, I, or D letters.
