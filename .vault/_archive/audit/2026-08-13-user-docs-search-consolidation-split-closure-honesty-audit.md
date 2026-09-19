---
tags:
  - '#audit'
  - '#user-docs-search-consolidation'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:64bfb30579c6f793d85db81faf75b2d09fc973fc649ef4ba012809b7aca22525'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

# `user-docs-search-consolidation` audit: `split-closure honesty review`

## Scope

Fresh-context review of the two rows closed on 2026-08-13 by SPLITTING a two-halved row and rowing the excluded half rather than absorbing it: `P03.S08` on its built-site half and `P04.S12` on its code half. Audited against current HEAD: the original row text before the split, both execution records' factual assertions, the new dry-run verb and its gates in `dev/deploy/docs_static_site.py` and `dev/deploy/tests/test_docs_static_site.py`, the per-language build recipes in `justfile`, and their premise in `dev/docs/build.py`. Reviewer was read-only. Every finding below was re-verified by the plan lead against current code before action, per the standing rule that swarm output is inventory rather than gospel.

## Findings

### clause-survival | none | Neither split drops a clause

Every clause of both original rows survives: delivered, or explicitly rowed. `P03.S08`'s deployed-probe clause is carried verbatim in intent by the new `P03.S40`, including its rationale that a green CI pass must never mask a broken live root. `P04.S12`'s live-response clause is carried by `P04.S13`, whose own text already forbids a built-site probe standing in for it. Both rewritten rows carry an explicit exclusion paragraph naming the carrying row. Neither execution record claims anything about a deployed root.

### orphan-sweep-empties-the-language-roots | high | The apex build deleted every page of every localized root

The full-build orphan sweep in `dev/docs/build.py` resolves each built page's docname against a source under `docs/`. A page at `html/es/index.html` therefore resolved to a `docs/es/index.md` that has never existed and was unlinked as an orphan, while the sweep's skip set covered only asset and infrastructure directories. Every localized root nested in the same HTML tree was consequently emptied by the next apex build, leaving exactly the residue this campaign twice mis-diagnosed: a language directory holding subdirectories and not one rendered page.

This materially corrects the closure's own causal account. The per-language recipes really did lack the flag that creates a per-language subdirectory, and that defect is real and fixed. But it is not the whole cause of the observed artefact, and on its own the recipe fix was not durable: it would have populated the language roots for the next apex build to empty again. The deploy path was safe only by ordering accident, since it happens to build the apex before the language roots.

Fixed. The sweep now exempts a nested per-language site root, deriving the language set from the canonical output-language enum rather than a hand-list, and deliberately not from the module that names the deploy root set, because that module imports this one. A regression gate asserts the localized roots survive an apex sweep and pairs that with a genuine orphan in the same tree, so an exemption widened until it swept nothing fails rather than passes vacuously. The exemption was proven load-bearing by clearing it at runtime from outside the repository: with it the localized page survives, without it the page is deleted.

### shared-composition-was-ungated | medium | Nothing failed if the publish and the dry run drifted apart

The dry run is only worth running if its verdict is the publish's verdict. That held by construction once both paths went through one build-and-validate composition, but it was enforced by nothing: re-inlining the validation calls into the publish, which is the exact shape that existed before the extraction, would have reintroduced a dry run that passes where a publish refuses, with a green suite.

Fixed. A gate reads the publish's own call sequence and requires build, then validate, then upload, refuses the re-inlined form by name, and pins the dry run's default build to the shared composition. Proven to bite by re-inlining the validation in a copy of the source outside the repository and confirming the verdict flips to red.

### parity-gate-subject-is-machine-dependent | medium | The green run did not record which corpus it measured

The per-root recall gate prefers a real localized root when one carries at least three built pages and otherwise takes the real English pages with the language attribute retargeted. Which branch runs depends on untracked build output, so the same command can measure a real, a synthetic, or a stale corpus on the same machine. The fallback is by design and the property under test is which index the records land in rather than the prose, so the closure's claim stands. What was missing is that the recorded evidence did not say which branch each root took. The execution record now states it: on the 2026-08-13 run the English root read the real built English pages, and the three localized roots took the retargeted fallback because the language roots held no pages, being the very defect the same session fixed.

### dry-run-verdict-is-not-yet-the-publish-verdict | medium | The apex root's own search bundle is validated only after upload

The shared validation covers the apex entry page and the language roots, but not the apex root's own Pagefind bundle, while the post-publish index verification includes the apex and raises when that built file is absent. That verification runs after the upload and the cache invalidation, so an apex root that would fail the publish's own index check still passes the dry run. A validator that would have covered exactly this sits in the module with no production caller, and there is an unresolved contradiction between the entry validator's docstring, which states the apex no longer owes a Pagefind bundle because it correctly moved into the roots, and the post-publish check, which still demands one. Rowed rather than fixed, because what the apex owes is a decision and not a mechanical gap.

### language-set-is-hand-listed-in-the-recipes | medium | A recipe can silently miss a published root

The per-language recipes hand-list three language codes while the deploy derives its root set from the canonical output-language enum and treats English as a root like any other. A fifth language would leave the recipes silently short, and no gate pins that a per-language recipe carries the flag that creates its own root. The defect class that cost this campaign two mis-diagnosed blockers is therefore ungated. Rowed.

### boundary-integrity | none | No development-record references leaked into delivered surfaces

The new docstrings, recipe comments and gates carry no vault stems, plan or step identifiers, wiki-links, or harness paths.

## Recommendations

The high finding and the ungated composition are fixed and gated in this campaign, each with its bite proven from outside the repository. The three remaining medium findings are rowed as open steps rather than absorbed: reconciling what the apex root owes between the pre-upload validation and the post-publish index verification, including the fate of the uncalled validator, and deriving the per-language recipes from the canonical language set behind a gate that pins the per-root output flag.

Both closures stand. The campaign is not structurally complete: two steps remain open and both are blocked on an operator-authorised deploy, which is outward-facing and outside an agent's authorisation.
