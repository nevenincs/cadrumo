---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:e5c85723c74d11f1518a61ee61dbf80af8ec14fd753666f7c317a586b59d7d77'
step_id: 'S09'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace ci-lane-deconflation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S09 and 2026-08-05-ci-lane-deconflation-plan placeholders are machine-filled by
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
     The Flip continue-on-error off the integration parallel step once its backlog closes, the step is deterministic so it can go blocking independently of the serial pass and ## Scope

- `.github/workflows/ci-full.yml` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Flip continue-on-error off the integration parallel step once its backlog closes, the step is deterministic so it can go blocking independently of the serial pass

## Scope

- `.github/workflows/ci-full.yml`

## Description

- Measure the lane's real failure set with a working-tree pass and with a guarded extraction of committed source.
- Separate genuine defects from working-tree artefacts, from failures the instrument cannot measure, and from third-party outages.
- Close the one real defect found.
- Refer the remaining structural blocker to the operator and record the ruling.

## Outcome

The step is closed as a deliberate non-change. The flag stays on, permanently, by
operator ruling. The lane keeps its live rate lookup and therefore keeps its
non-blocking flag.

The row gates the flag on a triaged backlog closing. That backlog did close: the one
genuine defect at committed source was a test asserting that an empty perceptor store
should yield zeroed casillas, when the resolver correctly refuses in order to prevent a
silent zero. It was corrected and the lane's real-defect count reached zero.

Closing it did not make the flag safe to turn off, and that is the finding. The lane
reaches a live European Central Bank endpoint transitively through a multi-currency
fixture, so turning the flag off would make the release verdict depend on a third party
nobody here operates. One pass failed on repeated gateway timeouts; a direct probe
minutes later succeeded three times, and a guarded extraction did not reproduce the
failures at all. A transient outage, not a defect, and precisely the condition that
would redden a blocking lane for reasons no commit caused.

The operator ruled to keep the live lookup and accept the permanent flag rather than
pin rates to a committed fixture. The reasoning is that foreign-exchange rates are
regulated inputs, and a stale committed fixture would ground calculations in wrong
rates silently, which is the failure class this project guards hardest against. A loud
permanent flag is preferable to a quiet wrong number.

A second, independent obstacle remains recorded for anyone who revisits this. Of the
failures at committed source, one was a real defect and twenty-seven were unmeasurable
by an extraction because they need an installed package, an installed service, an
external binary, or a generated documentation tree. Those can only be measured on a
real runner, so even a defect-free lane could not have been certified from local
evidence alone.

## Verification

Working-tree pass, which is blind to masking and therefore not the basis for any
conclusion:

    pytest -q -n 8 -m "integration and not serial and not os_keychain"
    3 failed, 3837 passed, 9 warnings in 734.06s

Guarded extraction of committed source, imports asserted to resolve inside it:

    28 failed, 3812 passed, 9 warnings in 734.75s
    guard: 9 proofs, 9 INSIDE_EXTRACTION, 0 SHADOWED

    real at HEAD              1
    working-tree artefact     0
    instrument-unmeasurable  27
    external dependency       0   (the outage did not reproduce)

The defect fix, verified on both lanes:

    1 passed unit, 4 passed integration

## Notes

The failure count was never the operative question, and reading it as such would have
produced the wrong action twice over. Two of the three working-tree failures were a
gateway timeout rather than a defect, and would have been filed as real work by anyone
reading test names without assertion text. Conversely the count reaching zero would
have licensed turning the flag off onto a lane that still depends on a foreign service.

The two instruments disagreed by design and both were necessary. The working-tree pass
cannot see past a peer's uncommitted fix; the extraction cannot see anything requiring
an installed package. Neither alone supports a verdict, and the divergence between them
was itself informative.

The pre-run estimate of the unmeasurable bucket was close in files and badly wrong in
tests, because three heavily parametrised modules produced twenty-three failures
between them. A count's unit must match the unit of the question it answers.

The operator decision is recorded here rather than in a decision record because it
settles this step only. If the lane is ever required to block, the question reopens and
deserves a proper decision record with research, not a ruling taken in passing.
