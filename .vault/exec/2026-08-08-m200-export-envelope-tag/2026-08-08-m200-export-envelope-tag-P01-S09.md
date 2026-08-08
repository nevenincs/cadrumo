---
tags:
  - '#exec'
  - '#m200-export-envelope-tag'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:51445f000e26f2fe55ec5a57a63373f65333d1562d6a2e907cb2dbccb275de63'
step_id: 'S09'
related:
  - "[[2026-08-08-m200-export-envelope-tag-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace m200-export-envelope-tag with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S09 and 2026-08-08-m200-export-envelope-tag-plan placeholders are machine-filled by
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
     The add a closed-set guard test asserting no accounts-regime concept (aseguradora, entidad de credito, inversion colectiva, garantia reciproca, estado de cuentas) exists anywhere in the registry or domain model outside an explicit allowlist, so a future addition fails the gate until both hardcoded discriminante literal '0' sites are revisited together and ## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_export.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# add a closed-set guard test asserting no accounts-regime concept (aseguradora, entidad de credito, inversion colectiva, garantia reciproca, estado de cuentas) exists anywhere in the registry or domain model outside an explicit allowlist, so a future addition fails the gate until both hardcoded discriminante literal '0' sites are revisited together

## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_export.py`

## Description

- Add a guard asserting the Modelo 200 page-000 discriminante field is still a
  literal `0`, located by its AEAT-fixed byte position (offset 6, length 1) rather
  than by id or kind, since id and kind are exactly what the guard watches.
- Add a scan asserting no closed typed declaration channel -- the export
  `draft_attribute` token set and the binding source-kind set -- names the
  estado-de-cuentas axis or any of the four non-Normal regimes.
- Add a cross-site agreement assertion at the export surface: both envelope tags'
  discriminante bytes are read out of the rendered payload and compared against
  each other, not against a third restatement of the expected value.
- Factor both detectors into named predicates and give each an anti-vacuity
  control, so a matcher that never fires cannot read as a clean tree.

## Outcome

The discriminante's two independent authorities -- a registry literal for the
opening tag, a hardcoded character inside the closing tag's computed template --
are now tied together three ways: the literal cannot change or be re-kinded
silently, a typed channel that could feed it cannot appear silently, and the two
rendered bytes must agree. Each failure message names both sites, because fixing
one alone ships a fichero whose tags disagree about the filer's accounts regime,
and no completeness or parity gate reads that divergence: both tags stay
structurally well-formed.

The Step asked for a substring scan of the registry and domain model behind an
explicit allowlist. That shape was measured before being adopted and rejected: the
regime vocabulary matches 61 files under the source tree once the corpus and locale
catalogues are excluded -- casilla labels quoting AEAT's own wording, and unrelated
bindings whose ids contain "creditos" for dotaciones por deterioro de créditos. An
allowlist of that size is the honor-system list the quality rules forbid, and it
would detect nothing through the noise.

So the scan was narrowed to closed typed sets small enough to enumerate, which
carry none of the vocabulary today and therefore need no allowlist at all. The
substituted shape is not weaker for the Step's stated purpose -- it fires when a
regime concept becomes *declarable*, which is strictly earlier than when one
becomes *mentioned* -- but it is narrower than the literal wording, and a regime
concept introduced only as registry prose, with no typed channel and no change to
the discriminante field, would not trip it. That residue is stated rather than
papered over.

## Verification

<!-- Where the evidence is that something RAN, quote the instrument rather than
     summarising it: the invocation, then the runner's verbatim summary line.

         uv run --no-sync pytest <paths> -m integration -n 0
         15 passed in 10.35s

     The invocation shows the selection (marker expression and path scope); the
     summary line shows what that selection produced. A run that selected nothing
     exits zero and reads as green, so a paraphrase such as "the tests pass"
     discards exactly the part a reader needs. Quote, do not summarise. -->

Both guards, both anti-vacuity controls, and the cross-site agreement assertion,
alongside every other test in the two modules they landed in:

    uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_export.py src/cadrumo/application/filing/tests/test_export.py -n0 -q
    80 passed in 19.22s

The controls are what make the guards load bearing: each detector is exercised on
input that must trip it and on input that must not.

## Notes

The narrowing described above is a deliberate substitution of gate shape, not a
reduction of scope, and it is the one judgement in this Step a reviewer should
check rather than accept.
