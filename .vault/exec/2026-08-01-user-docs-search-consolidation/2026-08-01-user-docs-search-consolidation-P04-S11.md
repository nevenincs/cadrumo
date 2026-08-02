---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-01'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:f44ff9e3a65ec75c1a6385ec8ca0176ed07ea34eb643243b80702f787d2eb5ea'
step_id: 'S11'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

# Add a deployment-parity gate asserting the built site's pagefind entry carries every decided record kind and every language root, so an env value can never silently re-narrow the shipped contract again

## Scope

- `dev/docs/tests/`

## Description

- Extract the mode-to-injector decision out of the build driver into one named resolver, so the gate can observe the real decision instead of re-deriving its mapping.
- Add a bounded-sample seam to the record injector, defaulted off, so a gate can exercise the production injector without paying the full corpus write.
- Extract the publisher's post-publish endpoint checks into a named function, so language-root coverage is assertable without reaching the network.
- Add the deployment-parity gate: it resolves the injector from the real deploy environment, writes a real Pagefind index over real built HTML, and reads the record kinds back out of the written artefact.

## Outcome

The gate observes the shipped artefact, never the build configuration, because the configuration was correct throughout the defect and only the artefact was wrong.

It reads the artefact three independent ways. The record kinds come back through `pagefind.js` in a real browser - the same API the reader's palette calls - as filter counts over the written index. The shipped entry file is checked to carry an indexed count equal to pages plus injected records, which is the one property a live HTTP check can confirm without a browser: a full index always exceeds its page count, and the live site's count equalled its page count exactly. The written fragments are decompressed from disk and required to carry each kind, so no assertion can pass on the injection's own report while the artefact is empty.

Language-root coverage is asserted against the publisher's real check list: every localized root must be required to answer 200 after publish.

Verification, all real counts: the gate module runs 5 tests, passing in 78 seconds - short enough to actually run, which matters because a gate slow enough to be deselected is a false green of its own. The full-corpus alternative was measured at 890 seconds.

Mutation proof: restoring the `pages` deploy value fails 4 of the 5, including the artefact reads (`the deployed index carries no records of kind(s) ['casilla', 'cli', 'concept']` and `kinds [...] are absent from the written fragments`). The fifth, language-root publish coverage, is orthogonal to the index mode and correctly stays green. Restoring the value returns all 5 to green.

On the localized roots, which the plan treats as a separate gap: the publisher already builds each one, validates that it carries an index page and substantive index data, syncs it under the documentation prefix, and requires it to answer 200 after publish. The delivery function rewrites a trailing-slash request to the root's index page and the distribution declares no origin path, so the mapping is intact end to end. A localized user-scope build was run directly against the deploy's own out-dir form and Sphinx reported success, and the repository's existing per-language nitpicky gates passed for Spanish, Catalan, and Hungarian in the same session. What remains unproven is only the localized root's injected-record artefact, because the injection phase outlasted the measurement window; the resolver assertion covers the decision for every language.

## Notes

The gate injects four real records per kind rather than the full 7,890. The projections, the injector object, the Pagefind write, and the artefact read are all production; only the row count is bounded, and the row count is not the property asserted. The full corpus costs about fifteen minutes per run, which would push the gate out of every routine lane.

A missing built-HTML tree fails the gate rather than skipping it, so an absent artefact can never read as a pass.

Observed while running the gate, and pre-existing: every index build writes a stray Pagefind directory at the repository root. The index context manager writes a second time on exit with no output path, so the write lands relative to the working directory. It is gitignored and untracked, so nothing can be committed by accident, but it is unwanted output from every build and no step owns it.

Grounded by semantic search over the codebase, not by searching for the environment variable's name. That distinction mattered here: searching by meaning for where record injection is disabled, and for anything that already asserts what the built index contains, surfaced an existing sweep that walks the injected corpus against a built site and checks every target resolves to a real page and anchor. A search for the variable name would never have reached it, because it names neither the variable nor the mode. That sweep is sound rather than silently passing - it builds its own site, asserts the output exists, and explicitly refuses a run where a whole record kind was skipped - and it checks target resolvability, which is a different axis from the deployment contract this gate covers. So the two are complementary and no pre-existing gate covered the contract. The same search by meaning confirmed injection can be disabled at exactly one production call site, that the deploy build environment is constructed in exactly one place, and that the localized roots have no second build path.
