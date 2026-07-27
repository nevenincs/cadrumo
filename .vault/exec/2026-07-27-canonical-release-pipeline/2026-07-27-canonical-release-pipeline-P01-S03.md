---
tags:
  - '#exec'
  - '#canonical-release-pipeline'
date: '2026-07-27'
modified: '2026-07-27'
step_id: 'S03'
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
     The S03 and 2026-07-27-canonical-release-pipeline-plan placeholders are machine-filled by
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
     The Invoke the identity authority at cohort seal time in the packaging workflow so sealing a version that is owned, burned, or not above the manifest floor refuses before any artifact uploads, gate: uv run --no-sync pytest dev/packaging/tests -q -k workflow passes with a conformance test pinning the seal job's guard invocation, full seal-refusal execution needs a CI dispatch and is flagged non-local and ## Scope

- `.github/workflows/packaging-smoke.yml`
- `dev/packaging/tests/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Invoke the identity authority at cohort seal time in the packaging workflow so sealing a version that is owned, burned, or not above the manifest floor refuses before any artifact uploads, gate: uv run --no-sync pytest dev/packaging/tests -q -k workflow passes with a conformance test pinning the seal job's guard invocation, full seal-refusal execution needs a CI dispatch and is flagged non-local

## Scope

- `.github/workflows/packaging-smoke.yml`
- `dev/packaging/tests/`

## Description

- Add the identity-authority invocation ahead of the cohort build in the packaging workflow.
- Read the candidate version from the declaration the build is about to stamp.
- Add the conformance test pinning the guard position relative to the build.
- Prove the ordering assertion by mutation.

## Outcome

Landed under the commit subject `feat(packaging): refuse a doomed version at
seal time, not only at publication`.

The same authority now answers at two points. Refusing at seal time costs one
re-run. Refusing at publication is the last check before an irreversible index
upload. Refusing nowhere is how a version a destination already owned reached
that upload. Because both call sites invoke one module, the two answers cannot
disagree.

Ordering is the load-bearing property, so that is what the conformance test
pins: a guard placed after the build would let a doomed cohort be sealed and
published from, which is a strictly worse failure than not guarding at all,
because the artifact then exists and looks legitimate.

Gate: the packaging workflow conformance suite passes at forty-five tests.

Anti-tautology proof: moving the guard below the cohort build reds the test with
the message naming the ordering requirement; restoring returns green.

## Notes

Non-local by design, and flagged as such in the plan: full seal-refusal
execution needs a continuous-integration dispatch, because the network probes
reach the package index and the forge. The conformance test is the local half
and pins the invocation and its position; the refusal behaviour itself is proven
by the identity module's own tests.

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
