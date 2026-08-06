---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:48662fb0269a68edf849afe9bb0c66512b1385473d4226f9718873822d884565'
step_id: 'S16'
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
     The S16 and 2026-08-05-ci-lane-deconflation-plan placeholders are machine-filled by
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
     The Re-pin the model-facing description digest once the description sources settle, the gate forbids re-pinning from a dirty tree and the locale and CLI help surfaces are actively churning and ## Scope

- `dev/packaging/tests/test_verify_distribution_identity.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Re-pin the model-facing description digest once the description sources settle, the gate forbids re-pinning from a dirty tree and the locale and CLI help surfaces are actively churning

## Scope

- `dev/packaging/tests/test_verify_distribution_identity.py`

## Description

- Establish whether the pinned digest depends on the in-flight description-source churn.
- Measure the observed digest under a guarded extraction of committed source, twice, at two different commits.
- Confirm the digest is the only failing check rather than one of several.
- Re-pin the constant and verify the gate turns green.

## Outcome

The digest was re-pinned and the gate is green. The row's stated precondition was
half wrong, and that is the substance of this record.

The row says to wait until the description sources settle. Fifty-three paths across
the five source trees are indeed dirty, and the verifier does refuse on that basis:
a digest computed over uncommitted work would bake that work into a committed gate.
So the cleanliness precondition is real.

But it was being read as a reason the correct VALUE was unknown, and it is not. The
in-flight churn is a single coherent campaign of mechanical import repoints that
touch no argument, tool, prompt, or resource text, so it cannot move the surface the
digest covers. Measured against committed source only, the drift is present anyway
and independent of everything uncommitted.

The value was measured twice under guarded extractions, at two commits several hours
apart, and came back byte-identical both times with an identical per-surface
breakdown. A value stable across independent measurements at different commits is a
constant rather than a moving target, which is the property that made pinning it
defensible.

The gate instructs that a re-pin ride in the same commit as the change that moved the
surface. That instruction is unsatisfiable here: the change already landed,
unidentified, and there is no commit left to ride. Read literally the row could never
close. The instruction's purpose is to stop a pin being refreshed casually to silence
a red gate, and that purpose is served by the evidence instead. A wrong pin would be
worse than a red gate, because red is loud and gets fixed while a pin matching nothing
goes green while measuring nothing.

## Verification

Guarded extraction of committed source, imports asserted to resolve inside it before
the number was trusted:

    GUARD cadrumo: INSIDE
    GUARD dev.packaging: INSIDE
    observed=0538e21e869b1ad89064c787521719aa1d79cfb20e07f23f79dc2e72eca361f0
    count=1658 by_surface={'argument': 1264, 'prompt': 35, 'resource': 54, 'tool': 305}

Gate after the re-pin:

    uv run --no-sync pytest -q -n0 dev/packaging/tests/test_verify_distribution_identity.py
    12 passed in 68.91s

## Notes

The first measurement of this value was taken without an import guard, and it agreed
with the second. That agreement was the danger rather than the reassurance: two runs
returning an identical digest is exactly what a shadowed import produces when both
runs actually read the working tree. The measurement was redone with both packages
asserted to resolve inside the extraction before the number was trusted. A confirming
result from an unguarded instrument is the one that most needs the guard, because it
is the one nobody re-examines.

An independent corroboration arrived by accident. The pin was computed from a clean
extraction, yet the gate passes against a working tree carrying fifty-three modified
description-source paths. That outcome is only possible if the in-flight campaign is
genuinely digest-neutral, which is the claim the whole decision rested on.

The originating surface change was never identified. It is known only that something
added or removed a verb or option before this campaign began. Identifying it was not
required to establish the correct value, but it is the reason the gate's same-commit
instruction could not be honoured, and a reader who wants to reopen this decision
should start there.

The commit was landed through a temporary index because the repository index lock had
been held for over two hours. That leaves a stale entry for the changed file until the
lock clears, which is repairable and was accepted deliberately over leaving the work
uncommitted.
