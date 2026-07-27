---
tags:
  - '#exec'
  - '#canonical-release-pipeline'
date: '2026-07-27'
modified: '2026-07-27'
step_id: 'S05'
related:
  - "[[2026-07-27-canonical-release-pipeline-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace canonical-release-pipeline with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S05 and 2026-07-27-canonical-release-pipeline-plan placeholders are machine-filled by
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
     The Invert the promote job's destination order to release creation with assets and docs payload, then Scoop, Homebrew, and marketplace pushes, then the PyPI upload last, gate: uv run --no-sync pytest dev/release/tests -q -k publish_release passes with the conformance test pinning PyPI as the final destination write and ## Scope

- `.github/workflows/publish-release.yml`
- `dev/release/tests/test_publish_release_workflow.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Invert the promote job's destination order to release creation with assets and docs payload, then Scoop, Homebrew, and marketplace pushes, then the PyPI upload last, gate: uv run --no-sync pytest dev/release/tests -q -k publish_release passes with the conformance test pinning PyPI as the final destination write

## Scope

- `.github/workflows/publish-release.yml`
- `dev/release/tests/test_publish_release_workflow.py`

## Description

- Confirm no later destination consumes the package index before moving it.
- Move the irreversible index upload from first to last among the destination writes.
- Record the ordering rationale beside the step it governs.
- Add the conformance test pinning every reversible write ahead of it.
- Prove the ordering by restoring the previous arrangement.

## Outcome

Landed under the commit subject `feat(release): run the irreversible upload
last, after every reversible write`.

Every destination above the index upload can be undone: a release and its assets
deleted, a tag removed, and the channel pushes reverted as ordinary commits. An
index upload is permanent and burns the version the moment it lands.

Running it first meant a failure in any later step stranded the index holding
bytes that matched no release, with no way back. That is not hypothetical. It is
what a version collision would have produced, because the release-creation step
immediately following would have failed on a tag that already existed.

Ordered last, a failure before it unwinds completely, and a failure at it leaves
every channel serving release assets, none of which depend on the index.

The dependency direction was checked before the move rather than assumed. Nothing
between the old and new positions consumes the index: the formula's declared
resources are locked third-party distributions, while the product itself is
fetched from the release.

Gate: the publication conformance suite passes at ninety-four tests, asserting
each reversible destination by name ahead of the upload and the upload as the
final step with nothing after it to fail.

Anti-tautology proof: restoring the previous ordering reds the conformance test,
naming the first reversible write it finds out of place.

## Notes

The ordering alone is not sufficient for recovery, only necessary. A re-dispatch
must also converge rather than refuse its own prior attempt, which is the
following Step; until that landed, this Step made failure survivable in
principle but not yet in practice.

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
