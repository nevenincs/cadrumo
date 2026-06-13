---
tags:
  - '#exec'
  - '#registry-casilla-identity'
date: '2026-05-20'
modified: '2026-05-20'
step_id: 'S11'
related:
  - '[[2026-05-20-registry-casilla-identity-plan]]'
  - '[[2026-05-20-registry-casilla-identity-adr]]'
  - '[[2026-05-20-registry-casilla-identity-research]]'
---

# `registry-casilla-identity` `P03.S11`

Added the off-load-path Diseño-completeness manifest drift
re-verification test that re-derives every checked-in manifest from the
corpus Diseño and fails CI on divergence.

- Modified: `src/aeat/domain/calculations/registry/test_record_design.py`

## Description

Two real-behaviour tests were added to the read-only record-design test
module, exercising the live registry tree and corpus — no mocks, stubs,
skips, or xfail markers.

`test_completeness_manifests_match_their_corpus_diseno` discovers every
revision in the registry tree that declares a `completeness_manifest`,
and for each machine-derivable manifest re-runs the off-load-path
`derive_diseno_completeness_casillas` derivation against the official
AEAT Diseño de Registros corpus the manifest names as its `source_ref`.
It asserts the re-derived `(segmento, number)` set still equals the
manifest's enumerated set; a divergence — corpus updated without
regenerating the manifest, or a hand-edited manifest — fails CI with the
manifest-only and corpus-only casilla deltas in the message.
`multi_segment` is inferred from whether any manifest casilla carries a
`segmento`. A manifest flagged `manual_extraction` (a PDF-only Diseño
that resists machine extraction) is exempt from the machine
re-derivation but must carry a recorded `manual_extraction_reason`; the
exemption is explicitly asserted, never a silent skip. A discovery
sanity assertion confirms the machine-checked plus manual-recorded count
equals the discovered manifest count, guarding against the loop silently
skipping every manifest.

`test_completeness_manifest_derivation_machinery_detects_corpus_casillas`
exercises the same derivation directly against the Modelo 200 2024
corpus Diseño, asserting the Liquidación cuota-chain casillas `00552`,
`00558`, `00562` surface under the `DP200014` record segment and that
the segment-qualified pair count exceeds the bare distinct-number count.
This proves the drift re-verification is load-bearing: if the derivation
could not extract casillas, the drift test would pass vacuously on every
manifest.

No manifests are authored yet (P05 authors them), so the drift test
currently iterates an empty manifest set and passes; the derivation
machinery test exercises the corpus directly so the suite has a real
assertion today and fails loudly the moment a manifest drifts.

## Tests

`pytest` on the two new tests passes; the full `test_record_design.py`
module and `test_modelo_parity_coverage.py` pass, confirming all 26
modelos remain valid. `ruff check` on the touched file passes clean.
