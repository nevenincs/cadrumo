---
tags:
  - '#exec'
  - '#canonical-release-pipeline'
date: '2026-07-27'
modified: '2026-07-27'
step_id: 'S04'
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
     The S04 and 2026-07-27-canonical-release-pipeline-plan placeholders are machine-filled by
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
     The Replace the check-pypi-only destination guard in Gate 2 with the all-destination authority, gate: uv run --no-sync pytest dev/release/tests -q -k publish_release passes with the conformance test asserting no check-pypi-only invocation remains and the Gate 2 step invokes the authority and ## Scope

- `.github/workflows/publish-release.yml`
- `dev/release/tests/test_publish_release_workflow.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Replace the check-pypi-only destination guard in Gate 2 with the all-destination authority, gate: uv run --no-sync pytest dev/release/tests -q -k publish_release passes with the conformance test asserting no check-pypi-only invocation remains and the Gate 2 step invokes the authority

## Scope

- `.github/workflows/publish-release.yml`
- `dev/release/tests/test_publish_release_workflow.py`

## Description

- Retire the partial destination flag from the promotion tool and rename it to what it now does.
- Add the identity-authority step to publication Gate 2, before any destination is written.
- Delegate the surviving index probe to the identity module rather than repeating it.
- Update the conformance test to assert the retired flag is absent, not merely unused.
- Sweep the runbook reference to the retired flag.

## Outcome

Landed under the commit subject `feat(release): replace the partial destination
guard at Gate 2 with the whole question`.

Gate 2 asked only whether a package index owned the version. That check passed
on the day it mattered, precisely because the index was the single destination
that did not own it, so promotion reached the irreversible upload and then
failed creating a release that already existed.

The narrow question is retired rather than bypassed. The flag becomes an
emit-only operation, and the identity authority runs as its own step before any
destination is written. The surviving index-slice helper stays for its remaining
caller but delegates the probe instead of repeating it: two implementations of
one probe is how the narrow question came to be asked in isolation, so there is
exactly one.

The operator surface was corrected in the same change. The command printed a
traceback with its message buried at the bottom; it now prints a refusal naming
every owning destination and exits non-zero, quoting the recorded burn reason so
the operator does not have to look it up.

Gate: the release suite passes at one hundred and eighty-two tests, with the
conformance test asserting the retired flag is gone and that the identity
authority runs after the version is emitted.

Anti-tautology proof: removing the identity invocation from Gate 2 reds the
conformance test; restoring returns ninety-three green.

## Notes

A measurement error was made and corrected during verification. A refusal was
reported as exiting zero; the command had been piped into another, so the shell
status belonged to the pipe rather than the tool. Re-run unpiped, the exit status
was always one. The genuine defect that check surfaced was the traceback, which
was fixed. The lesson is the standing one: never believe an exit status observed
through a pipe.

The runbook was swept in the same change. Operator instructions naming a flag
that no longer exists is the same defect class already corrected once in this
campaign's workflow prose, and leaving it would have reproduced it.

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
