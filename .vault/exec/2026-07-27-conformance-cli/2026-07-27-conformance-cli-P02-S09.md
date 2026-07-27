---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-27'
modified: '2026-07-27'
step_id: 'S09'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# add the classification-coherence checker (calculation_class vs tax_domain vs core modelo constants, plus the declared-but-dead axis census) as an importable typed fact-builder

## Scope

- `src/cadrumo/domain/calculations/registry/_classification_coherence.py`

## Description

- Add `_classification_coherence.py`: a typed fact-builder folding the four
  homes that classify a modelo as filed, informative, or non-filing.
- Model the facts as strict frozen pydantic rows: `ClassificationCoherenceFinding`,
  `DeclaredAxisUsage`, `ModeloClassificationRow`, `RegistryClassificationAudit`,
  with closed `Literal` vocabularies for finding kind, tracked axis, and axis
  status. No untyped mapping crosses the boundary.
- Emit four finding kinds: an informative-axis divergence between
  `calculation_class` and `tax_domain`, a modelo declared non-registry that the
  tree nonetheless compiles, a tree modelo no core identifier names, and a
  dependency classification conditioned on economic activity while the taxpayer
  does not file the source at all.
- Derive whether a divergence is forced by handing a class-swapped copy of the
  modelo to the real `validate_informative_class_invariant` rather than
  mirroring its rule, so the answer cannot drift from what registry build
  enforces.
- Census five declared schema axes against the population of candidate
  declaration sites, so an unused axis is reported against a real denominator.
- Expose `build_classification_coherence_audit` with injected modelos and
  injected core constants, plus a bundled convenience reading the tree through
  the non-validating loader and stamping `registry_validated=False`.
- Export the nine public names through the registry package top-level facade.
- Regenerate the API reference stubs with the apidocs scaffold CLI.

## Outcome

The checker reports and never canonicalizes. It does not raise on a
disagreement, and it rewrites nothing: which axis is right for a given modelo
is a question about Spanish tax law, not a fact derivable from the tree.

The central design finding is that the two informative axes are not redundant
labels. `calculation_class` is an ENFORCEMENT posture: declaring `informative`
binds the modelo to an invariant that refuses formulas, cross-model relations,
and any casilla outside informational or manual. `tax_domain` is a bare
taxonomy label carrying no invariant. A modelo that is informative in the AEAT
sense but computes bound totals therefore CANNOT carry the informative class
without failing registry build. Modelo 349 is the worked case already recorded
in its own registry test. A report that flattened the two axes into one
"disagreement" count would read as a to-do list whose first item breaks the
build, so every divergence finding carries the invariant's own answer to
whether the other value is even available.

Re-derived census against the live tree, 73 modelos and 90 revisions:

- `calculation_class` informative: 11. `tax_domain` informative: 17. Their
  intersection is 2 (modelos 347 and 720), so 24 modelos diverge on the axis
  pair: 9 declare the informative class with a substantive tax domain, 15
  declare the informative domain with a filing class.
- None of the 24 divergences is forced. Every one of them would survive the
  informative-class invariant, so nothing in the tree explains any of them.
  This is a live drift signal and the strongest single finding of the fold.
- All five tracked axes are unused: `calculation_class = "summary"` 0 of 73,
  revision support-removal decisions 0 of 90, extraction confidence
  `review_required` 0 of 43, extraction verification source
  `real_aeat_corpus_pdf` 0 of 43, completeness-manifest `manual_extraction` 0
  of 52.
- Zero contradictions on the remaining kinds: no non-registry modelo is defined
  in the tree, no tree modelo is absent from the core identifier enum, and no
  dependency conditions economic activity while the taxpayer does not file the
  source.

Deltas against the figures the research swept: the informative counts, the
modelo and revision totals, and every dead-axis zero reproduce exactly.
`UNMODELED_OBLIGATIONS` is empty today, so the research phrase naming 80
reasons matches `OUT_OF_SCOPE_OBLIGATIONS`, which does carry 80. The research
counted 16 of 73 modelos carrying a completeness manifest; the per-revision
count is 52, which is the manifest population this fold reports and not a
contradiction of the per-modelo figure.

Two consequences named in the module rather than left implicit: with zero
support-removal declarations anywhere, the support matrix's `is_deprecated` is
always false by construction and no consumer of it is exercised; and
`calculation_class = "summary"` is not merely undeclared but undistinguished,
since the sole branch on the field tests only for inequality against
`informative`, so a modelo declaring it would silently receive filing
treatment.

Verification: `ruff format` and `ruff check` clean, `ty check` reports all
checks passed, `pyright` reports 0 errors 0 warnings, and the core-struct
docstring link gate passes 3 tests.

## Notes

A self-review read after the mutation run found a latent defect in the module
as first committed and it was fixed in a follow-on commit. The informative-class
invariant emits one blocker per offending casilla, and every blocker was joined
into the finding's detail, which the schema bounds at 512 characters. A modelo
carrying about a dozen bound casillas therefore overflowed the bound and raised
a validation error while constructing the finding, aborting the whole
governance read on precisely the divergence the fold exists to report. The live
tree hid it completely: none of the 24 current divergences carries a blocker, so
the path is unreachable today and becomes reachable the moment an author sets
the informative tax domain on a computation-heavy modelo.

The fix is two-layered on purpose. Detail rendering now samples one blocker and
counts the rest, and every detail is clamped to the field bound before the
finding is constructed. The sampling keeps the sentence readable; the clamp is
what guarantees no registry-authored id or label can make a finding refuse to
exist. The complete blocker list stays on the row, where it always was. The
clamp was verified to be the actual raise-guard by neutering the sampler alone
and observing a truncated detail rather than an exception.

Fixture-sidecar provenance (`real_corpus` against `synthetic_generated`) was in
the requested census list but is deliberately excluded and documented as such
in the module. Those sidecars are test fixtures with no registry schema model,
gate-validated rather than compiled into the tree, and shipped registry code
must not reach into test corpora to census them. The remaining five axes are
all genuine registry schema surfaces read from the loaded tree.

The semantic-discovery probe was waived by explicit operator directive for this
campaign: the code index is broken and the service is under a hands-off order.
Grounding used ripgrep sweeps for the concept under several plausible names
(coherence, dead axis, declared-but-dead, classification drift, unused axis),
whole-file reads of the nearest analogue and of the schema epicenters, and a
read of the owning package facade before any symbol was added. No pre-existing
owner of this concept exists.

The fold reads compiled modelo definitions only, never a fragment-directory
listing, per the convergence that exists because subdirectory-blind tooling
twice produced wrong parse-only verdicts here.
