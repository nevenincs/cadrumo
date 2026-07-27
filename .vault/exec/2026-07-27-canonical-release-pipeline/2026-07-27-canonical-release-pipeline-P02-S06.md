---
tags:
  - '#exec'
  - '#canonical-release-pipeline'
date: '2026-07-27'
modified: '2026-07-27'
step_id: 'S06'
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
     The S06 and 2026-07-27-canonical-release-pipeline-plan placeholders are machine-filled by
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
     The Prove every destination step idempotent against its own prior success so a re-dispatch of the same cohort converges, using clobber or skip-existing semantics per destination, gate: uv run --no-sync pytest dev/release/tests dev/packaging/tests -q -k idempot passes over the helper functions, end-to-end re-dispatch convergence needs CI and is flagged non-local and ## Scope

- `.github/workflows/publish-release.yml`
- `dev/packaging/marketplace_publish.py`
- `dev/release/tests/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Prove every destination step idempotent against its own prior success so a re-dispatch of the same cohort converges, using clobber or skip-existing semantics per destination, gate: uv run --no-sync pytest dev/release/tests dev/packaging/tests -q -k idempot passes over the helper functions, end-to-end re-dispatch convergence needs CI and is flagged non-local

## Scope

- `.github/workflows/publish-release.yml`
- `dev/packaging/marketplace_publish.py`
- `dev/release/tests/`

## Description

- Survey each destination write for whether a re-dispatch converges or fails.
- Make release creation recognise and re-upload over this cohort's own release.
- Make the index upload skip files a partial prior upload already landed.
- Exempt this cohort's own release from the identity guard, keyed on the commit.
- Split the exemption rule out of the network shell so it is provable.

## Outcome

Landed under the commit subject `feat(release): make every destination converge
on a re-dispatch`.

The survey found three channel pushes and the payload upload already converged;
two destinations did not. Release creation failed outright when the release
existed, and the index upload failed on the first already-present file.

Release creation now recognises the release this cohort itself made, identified
by the same source commit, and re-uploads its assets. A release on any other
commit remains a hard error.

The index upload skips already-present files. Six distributions go up and that
upload is not atomic, so a fault after the third leaves three published and
three not; without skipping, a re-dispatch dies on the first present file and
the remaining three can never land. It is the one destination where a
half-finished write cannot be undone, so converging is the only remedy
available.

A design tension surfaced and was resolved rather than worked around: the
identity guard would have refused the recovery path itself, since a re-dispatch
finds its own release and the guard reads that as a collision. The guard gained
an own-cohort exemption keyed on the source commit, never on the version, which
is what prevents it laundering a release belonging to anything else.

Gate: the release suite passes at one hundred and eighty-seven tests.

Anti-tautology proof: making the exemption ignore the commit, which is precisely
the laundering defect, reds two tests.

## Notes

A tautological test was written and discarded before commit. The first draft
re-implemented the exemption filter inside the test and asserted against the
copy, proving only that the copy worked; a second asserted against an empty
input and was trivially true. Both were deleted, and the rule was split out of
the network shell as a pure function so the real implementation is exercised
against real rows. The refactor was prompted by the bad test rather than the
other way round, which is the useful part to record.

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
