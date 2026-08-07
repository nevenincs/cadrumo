---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:022e7f15acbb4d1be0530b05e87ea84b985e9f252c96fbcf563cd07ea8d90ba4'
step_id: 'S20'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec W05.P07.S20

## Outcome

**Settled against a real installed cohort. The defect does not reproduce, and both halves of the Step's requirement hold.**

An earlier pass recorded this as unreproducible-in-tree and left it open, on the ground that the Step names the *installed* console path and no cohort was available. That was the right caution and the wrong conclusion: the cohort is buildable from this repository.

## What was built and installed

The root wheel alone will not install — it pins `cadrumo-data-manuals==0.2.2`, which is what "cohort" means concretely here. Both companions live in-repo, so the full set builds:

    cadrumo-0.2.2-py3-none-any.whl
    cadrumo_data_manuals-0.2.2-py3-none-any.whl
    cadrumo_data_official-0.2.2-py3-none-any.whl

Installed into a clean venv with `--find-links`, producing a real `aeat` console script — not the in-tree module entry the earlier pass exercised.

## Half one: help must never need database access

    $ aeat --help
    exit=0, stdout 2681 chars, stderr EMPTY

No database mention, no `Settings` reference, no traceback anywhere in either stream. The installed help path does not construct settings far enough to reach the former-product database refusal.

## Half two: a refusal must route through the translated boundary

Driving a command that genuinely needs state, from the same installed script:

    $ aeat app ledger list
    exit=2
    Refused. You are not logged in. Run `aeat config login` to unlock your profile.
      -> Run `aeat config login`
      reason: absent

That is the envelope shape the Step asks for — a translated refusal carrying a suggestion and a reason — and `Traceback (most recent call last)` appears zero times in stdout or stderr.

So the refusal does not leak a traceback, which is the mechanism the Step required and the reason it was written.

## Why the earlier caution was still correct

An in-tree green would not have established this. The installed script resolves its own paths and settings root, and the earlier pass could not tell whether the difference mattered. It did not, but that was worth demonstrating rather than assuming — and the demonstration cost one wheel build.

The lesson worth keeping is narrower than "always build the cohort": the blocker was stated as needing an artefact, and the artefact turned out to be three `uv build` invocations away. A blocker naming an artefact is worth re-testing against what the repository can actually produce.

## Note

The build is at `cadrumo-0.2.2`, which is the current in-tree version, so this exercises the code as it stands rather than a published release. A published-cohort re-check belongs with the distribution campaign's own acquisition steps.
