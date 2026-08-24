---
tags:
  - '#audit'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:28e9a14da64e318bd8e1f9e0679c6356251ff87d786f9540b0d83e4f95ae31a5'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---

# `registry-completeness-closure` audit: `s09 post review`

## Scope

Independent post-implementation review of commits `6a6b72a01c` and
`aa943b2463`. The review covered the filing-grade admission boundary, exact
layout capability, official-source byte identity, generated-fragment
provenance, emitted-byte proof, refusal semantics, facade exposure, focused
tests, and execution-record truthfulness.

## Findings

### export-proof-closure | high | A verified source file is treated as proof that the product can emit a filing

`compose_filing_export_coverage` marks a filing-grade revision satisfied after
snapshot admission and rehashing the layout-authority files cited by the loaded
layout. It does not require or verify the generator provenance manifest, its
exact semantic-map digest, reviewed render-profile digest, generated-fragment
digest set, or a successful production emitted-byte proof. This is weaker than
the accepted closure predicate and admits a layout-shaped declaration even when
the product cannot render it. The bundled Modelo 111 revision
`2019-y-siguientes` demonstrates the defect: the composer reports `satisfied`
for its fixed-width layout, while it carries no `_generation.provenance.json`
and the live production export is known to refuse every operator because the
required `colegio_concertado` value has no production source. Across the bundled
tree, 67 of 102 filing limbs report satisfied while 41 filing-grade revision
directories carry no generator provenance manifest. The three focused tests all
pass because none removes generation or emission proof, and the execution record
therefore overstates that S09 proves emitted filing capability.

### embedded-source-identity | high | Embedded envelope source digests are ignored

The live rehash walks `layout.source_refs`, verifies the catalogue entries, and
records those catalogue digests. It never compares a generated layout's
`filing_envelope` or `auxiliary_envelope_header` `source_ref` and
`source_sha256` identity with the cited catalogue source. Registry-build export
validation likewise checks inclusion of the embedded source reference but does
not compare the embedded digest. A direct mutation of Modelo 303 revision 2025
changed the filing-envelope digest from its real value to sixty-four zeroes;
the composer still returned `satisfied` with no refusal. Thus the report can
rehash the correct official binary while silently accepting generated envelope
provenance bound to different bytes.

## Recommendations

- For `export-proof-closure`, require the canonical generator provenance and
  exact semantic-map/render-profile/generated-fragment identities, plus the
  campaign's successful production emitted-byte evidence, before a filing limb
  can satisfy. Add a Modelo 111 regression proving a structurally present but
  non-emittable layout remains refused.
- For `embedded-source-identity`, validate and live-recheck both envelope forms'
  embedded source reference and digest against the catalogue, with missing,
  mismatched, and stale-digest mutation tests.
