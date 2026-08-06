---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:f0865b7479ddb76b98d2833ccb3051a0fbf2d51dc616cd4318bdbf3be18fe4dc'
step_id: 'S03'
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
     The S03 and 2026-08-05-ci-lane-deconflation-plan placeholders are machine-filled by
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
     The Dispatch ci-full for its first ever execution and record the result, its run count is zero so every claim about its steps is structural rather than observed and ## Scope

- `.github/workflows/ci-full.yml` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Dispatch ci-full for its first ever execution and record the result, its run count is zero so every claim about its steps is structural rather than observed

## Scope

- `.github/workflows/ci-full.yml`

## Description

- Push so the dispatch would exercise current code.
- Dispatch the full conformance lane once, without re-dispatching.
- Confirm it reached a runner and executed steps.
- Record the observed result and act on it.

## Outcome

The lane executed on a runner for the first time in its history and its result is
recorded. The row asked for a first execution and a recorded result, and both exist.

Every prior dispatch had failed to produce evidence. Five runs existed before this
one: exactly one ever reached a runner, dying early, and the other four recorded zero
steps with no runner assigned. Two of those were cancelled after waiting more than
half an hour. So every claim about this lane's later steps was structural rather than
observed, including claims made in this campaign's own briefs.

This run reached a runner and executed thirty-one steps. It failed at the lint step on
thirty-two unsorted-import errors, collateral from a re-export bridge removal that
repointed dozens of consumers without re-sorting their import blocks. That failure has
since been fixed, along with a genuine undefined-name defect found in the same sweep
where a deferred import was added to one call site but not to a second one in another
function.

What the row does not yet have, and should not be claimed, is a green lane. The steps
beyond lint have still never executed. The result recorded here is a real observed
failure with a real cause, which is what the row asked for, and it is the first
evidence this lane has ever produced.

## Verification

    run 31128692574  conclusion=failure  runner=cadrumo-linux-x64-1  steps=31

    1-7  setup, checkout, tooling, bootstrap, playwright   success
    8    Lint                                              failure
         Found 32 errors  (all unsorted import blocks)

Contrast with every earlier dispatch, which produced no evidence at all:

    runner=NONE  steps=0   (four runs)

After the fix, locally:

    ruff check --select I001 src/ dev/   ->  All checks passed!
    aeat --help  and  aeat app ledger --help  ->  OK
    pytest --collect-only src/cadrumo/entrypoints/cli  ->  832 collected, clean

## Notes

A dispatch cadence hazard is worth recording for whoever runs this lane next. The
workflow declares a concurrency group without cancel-in-progress, so a newly queued run
displaces the previously pending one. Dispatching several times in quick succession
therefore cancels the run just requested, which is what produced two of the four
evidence-free runs earlier in the session.

The failure count itself needed re-deriving rather than inheriting. A brief circulating
during this campaign put the lint failure at a different number, and a related legal
reference count was quoted as thirty-five when the instrument showed forty-one. Counts
in this campaign have repeatedly moved between the claim and the measurement.
