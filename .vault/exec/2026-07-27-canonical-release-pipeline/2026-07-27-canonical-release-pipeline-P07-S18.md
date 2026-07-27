---
tags:
  - '#exec'
  - '#canonical-release-pipeline'
date: '2026-07-27'
modified: '2026-07-27'
step_id: 'S18'
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
     The S18 and 2026-07-27-canonical-release-pipeline-plan placeholders are machine-filled by
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
     The Add the lane-reachability gate asserting every test_*.py under the repository is selected by at least one declared pytest lane, computing reachability from pyproject testpaths, justfile recipes, and every workflow pytest invocation with both the path scope AND the marker expression modeled, since this incident's tests were excluded twice over, gate: uv run --no-sync pytest dev/ci/tests -q -k reachability passes and its injectable-root self-test plants an orphaned test file and asserts the gate reds and ## Scope

- `dev/ci/tests/test_lane_reachability.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add the lane-reachability gate asserting every test_*.py under the repository is selected by at least one declared pytest lane, computing reachability from pyproject testpaths, justfile recipes, and every workflow pytest invocation with both the path scope AND the marker expression modeled, since this incident's tests were excluded twice over, gate: uv run --no-sync pytest dev/ci/tests -q -k reachability passes and its injectable-root self-test plants an orphaned test file and asserts the gate reds

## Scope

- `dev/ci/tests/test_lane_reachability.py`

## Description

- Add the reachability model computing lanes from configuration, recipes, and workflows.
- Model path scope and marker expression together, since either alone is insufficient.
- Add the hard gate with no baseline and no allowlist.
- Give every orphan the gate found a real lane rather than an exemption.
- Prove both halves of the model by planted violations against an injectable root.

## Outcome

Landed under the commit subject `ci(lanes): make an unreachable test file a
failure, and reach the fourteen that were`.

Reachability is a two-part question and both parts are modelled. The channel
generator tests were excluded twice over: lanes reaching their directory
rejected their marker, and lanes accepting their marker did not reach their
directory. A path-only model calls them reachable, so marker expressions are
evaluated structurally rather than by string containment. The repository's
standard expression contains the word for the serial marker while rejecting
serial-marked files, so a containment check inverts the answer on the exact case
the gate exists to catch.

Two precisions the naive version gets wrong. Only genuine test-runner
invocations carry marker expressions, because the same flag is the version
control system's message flag and this repository uses it that way in the same
files. And a file's markers come from per-test decorators as well as the
module-level declaration, or a decorator-only file reads as unmarked and matches
narrow expressions it cannot satisfy.

On its first real run the gate found fifteen orphans nobody knew about. Twelve
documentation tests sat inside a lane whose marker expression their markers did
not satisfy, which was confirmed empirically rather than inferred: that lane
collects zero tests from those files while their own marker collects three. Two
bundle tests were reached by no lane at all. All fifteen were given real lanes
rather than an allowlist, and the tree now stands at zero unreachable across two
thousand two hundred and one test files.

Gate: the reachability suite passes at fourteen tests, and the full lane suite at
sixty-nine.

Anti-tautology proof: two planted violations against an injectable root, one for
each half of the model. A file outside every lane's paths is reported, and so is
a file inside a lane's paths carrying a marker that lane rejects. The second is
the half a path-only model would miss.

## Notes

The gate caught a defect in itself during authoring: a helper named with the
test prefix was collected as a test and errored on a missing fixture. Renamed.

One pre-existing failure was absorbed rather than deferred. A perf-policy gate
asserted an exact marker string that an unrelated change had since extended with
a further exclusion, so it failed against a lane that over-satisfied its own
policy. It now asserts the policy by intent, with the reason recorded, so the
next added exclusion does not break it again.

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
