---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-01'
modified: '2026-08-01'
body_schema: 'body-v1'
body_hash: 'sha256:1dd8e7cc4b856bbd82036dd0571269372bb622c243b9c8dd1cf55e6aaf7ddd31'
step_id: 'S19'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

# Make the record-injection language follow the build language with the card summary preferring the root language's description, so every localized root's records land in the index its palette loads, correcting the module's stale per-language docstring in the same change and citing the localized-root artefact measurement in the exec record

## Scope

- `dev/docs/pagefind_inject.py`
- `dev/docs/build.py`
- `dev/docs/tests/test_deployment_search_parity.py`

The Step named only the injector. The other two are the resolution seam that feeds it and the parity gate that pins it; both were required for the Step's own success condition and are recorded here rather than absorbed silently.

## Description

- Confirm the defect against a real built artefact before changing anything, rather than acting on the code reading alone.
- Replace the hardcoded `_PRIMARY_LANGUAGE` pin with a `language` parameter threaded through the injector to the custom-record write.
- Add `docs_build_language`, resolving the build language from the same environment key that sets the page language, and pass it from the injector resolver.
- Prefer the root language's description for the card summary, falling back to English then the always-present Spanish text.
- Correct the module docstring, which described a per-language-section injection that its own implementation comment contradicted.
- Extend the deployment-parity gate with a per-root half asserting against each root's built artefact.
- Replace an assumed page constant in the pre-existing entry-count assertion with a measured indexed-page baseline.
- Prove the gate non-vacuous by restoring the English pin and observing it fail, then restoring the fix.
- Measure a real localized root built by the deployment's own command form, closing the retarget caveat.

## Outcome

The defect was real and reader-visible. Measured before the change, on a real built artefact under the deployment's own environment, the Spanish root wrote an `es` index holding only its rendered pages beside a separate `en` index holding all injected records. A browser on an `es` page fetched `wasm.es.pagefind` alone, never the English split, and the palette's kind filters came back `None`. A Spanish reader could search rendered prose and nothing else.

After the change the same corpus lands in the one index the palette loads. The bounded reproduction produced a single `es` split holding pages plus records, with kind filters `casilla`, `cli` and `concept` all present.

The authoritative evidence is a real localized root, built with the deployment's own command form (strict, user scope, language `es`, into an isolated output directory) and its own environment (canonical language base URL, single worker, full record-injecting contract), with the local storage root isolated to avoid log-rotation collisions between concurrent processes. Build exit was `0`, read from a dedicated exit file rather than inferred. It emitted 160 pages carrying the Sphinx-written `lang="es"` attribute and injected 7,890 records.

That root's shipped index carries exactly one language split, `es`, at 6,781 entries. There is no `en` split at all. Its palette, read through the same search API a reader's palette calls, narrows by `casilla` 6,359, `cli` 287 and `concept` 49. The English root's palette reports the identical three counts, so the record corpus is the same on both roots and each sits in the index that root actually loads. The roots' differing total entry counts are entirely the page difference between a full-scope and a user-scope build, not a record difference.

The gate fails when the fix is removed. With the English pin restored it reported six failures naming each localized root's stranded split and the missing kinds, in the form `the 'es' root built index splits ['en', 'es']; records outside 'es' are stranded in a split this root's palette never loads` and `a reader on the 'es' root cannot narrow by kind(s) ['casilla', 'cli', 'concept']; the palette sees []`. A separate pass proved the cross-lingual recall assertion non-vacuous, reporting that the Spanish root did not recall the probed record by its declared terms. The English root passed under both mutations, which is correct, since the pin is right for English. With the fix restored the module reported 21 passed, and no probe residue remains.

## Notes

The retarget caveat is closed. The gate's localized page corpus prefers a real localized root and otherwise takes real built pages with the language attribute rewritten. Only the fallback path was available while the gate ran, so the equivalence was an argument rather than an observation. The real-root measurement above confirms it: a Sphinx-emitted localized root produces a single split in its own language carrying the full record corpus, exactly as the retarget predicted.

A pre-existing failure was found and repaired rather than left. The entry-count assertion compared the index against a hardcoded page constant, but the indexing tool reports a page for every file it walks and writes an entry only for those with indexable body content. A three-file fixture whose selection had drifted onto two generated casilla pages reported three pages while writing one entry, so the arithmetic was wrong while both the injection and the index were correct. The constant was replaced with a baseline measured from a no-injection pass over the same corpus, which keeps the assertion exact instead of relaxing it. The per-root half uses the same measured baseline.

The first real build attempt failed and the failure was not this Step's. A strict build aborted at exit 2 with six command-sequence divergences from committed goldens, every one caused by an uncommitted working-tree change adding period-code validation for a text casilla input, which now refuses periods the documented sequences pass. Because the publish builds from the working tree rather than from committed state, that failure would block a publish while the change is present. It was reported to the coordinator immediately and left untouched, since the sequence machinery belongs to another campaign. The measurement was completed by setting the module's own documented opt-out for the sequence check, leaving every other build input identical. The evidence therefore stands for the injection language, and deliberately does not stand as proof that the sequence surface is healthy.

A process failure is worth recording. The first build was launched with the exit status echoed after a redirect, so the background task reported exit 0 while the build had actually failed at exit 2. The masking was caught only by reading the log rather than trusting the reported status. Subsequent runs wrote the exit status to its own file.

One follow-up remains, deliberately not chased here. A parallel change adds a canonical set of decided injected record kinds beside the index pass, and repairs the deploy-time preflight that previously accepted any root with non-empty index chunks. Once that lands, the parity gate's local literal set should consume the canonical constant so the two cannot drift.

The gate costs about eight minutes for the module, since the record projections run once per root. The injection is bounded to a few real records per kind for that reason; the projections, the injector, the index write and the artefact read all remain the production ones. The bound is worth revisiting if the cost grows, because a gate slow enough to be deselected is its own false green.
