---
tags:
  - '#exec'
  - '#canonical-release-pipeline'
date: '2026-07-27'
modified: '2026-07-27'
step_id: 'S10'
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
     The S10 and 2026-07-27-canonical-release-pipeline-plan placeholders are machine-filled by
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
     The Add the fail-closed publish preflight refusing while a retired name or retired-identity account metadata remains live and un-superseded in the marketplace index, with the refusal naming the supersession instruction, gate: uv run --no-sync pytest dev/packaging/tests -q -k preflight passes covering the refusal and the clean-pass cases and ## Scope

- `dev/packaging/marketplace_publish.py`
- `.github/workflows/publish-release.yml`
- `dev/packaging/tests/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add the fail-closed publish preflight refusing while a retired name or retired-identity account metadata remains live and un-superseded in the marketplace index, with the refusal naming the supersession instruction, gate: uv run --no-sync pytest dev/packaging/tests -q -k preflight passes covering the refusal and the clean-pass cases

## Scope

- `dev/packaging/marketplace_publish.py`
- `.github/workflows/publish-release.yml`
- `dev/packaging/tests/`

## Description

- Add a fail-closed verification mode that publishes nothing.
- Refuse a live retired entry, an unreferenced retired tree, and stale metadata.
- Invoke it in the publication path before the merge.
- Prove the orphaned-tree case by mutation.

## Outcome

Landed under the commit subject `feat(packaging): verify the retirement on every
release, not only the one that did it`.

Supersession that is merely performed is a state; supersession that is verified
is an invariant. A performed retirement can be undone by a replay, a stale
manifest, or a stranger claiming the abandoned name, and nothing would notice.
The check therefore re-runs on every release rather than only the one that
retires a name.

Three distinct ways the rename can be half-done are covered. A live retired
entry is the obvious one. A tree with no index entry looks clean in the index and
is still fetchable by direct path, so it continues serving the old identity. And
a marketplace whose plugin list says one name while its description says another
cannot tell a reader which half is authoritative, so metadata retires with the
entries as one event.

Scoped to declared retirements rather than a general scan, so a cohort that
retires nothing is not checked.

Gate: the marketplace and preflight suites pass at fifty-two tests, including the
permit case, since refusals prove nothing without one.

Anti-tautology proof: blinding the check to an orphaned retired tree reds that
case alone, leaving the others green.

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
