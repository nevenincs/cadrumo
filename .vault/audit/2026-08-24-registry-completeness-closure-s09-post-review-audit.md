---
tags:
  - '#audit'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:0cbbe4cd3a22d343129055b1e77af10a2d2027d0116854557518414361699d15'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace registry-completeness-closure with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

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
