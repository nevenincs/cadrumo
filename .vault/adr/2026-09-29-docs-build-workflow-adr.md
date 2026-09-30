---
tags:
  - '#adr'
  - '#docs-build-workflow'
date: '2026-09-29'
modified: '2026-09-29'
body_schema: 'body-v2'
body_hash: 'sha256:6297ef7106e1940d2e0e4869a203d12c14fbe888b3341c1f0a334575426ce8ac'
related:
  - "[[2026-09-29-docs-build-workflow-audit]]"
  - "[[2026-06-01-docs-cli-buildtime-adr]]"
  - "[[2026-07-13-docs-cli-sequences-adr]]"
---

# `docs-build-workflow` adr: `Docs build and preview workflow` | (**status:** `accepted`)

Operator direction 2026-09-29: act on every documentation build and API recommendation from the design review. The operator authorized all modifications in advance.

## Problem Statement

`2026-09-29-docs-build-workflow-audit` found four faults:
- Golden drift reaches `main` because the pull-request gate never runs the `cli-sequence` check.
- A stale local authority can bake wrong values into goldens.
- Authors have no fast way to preview one page or one section.
- 1,950 generated API stubs are committed with no recorded reason, and they conflict across concurrent branches.

## Considerations

- A committed golden is a test oracle. Regenerating it inside the build would compare output with itself (`2026-07-13-docs-cli-sequences-adr`, D2). The goldens stay committed.
- An API stub is not an oracle. The generator is the truth, and `2026-06-01-docs-cli-buildtime-adr` already moved the CLI reference to build time on that ground.
- The committed stub tree's only real benefit is catching a filter change that silently drops pages (`dev/docs/apidocs/manager.py:19-34`). The replacement must keep that protection without a committed copy.
- A CI step has a 10-minute budget (`2026-07-20-ci-speed-redesign-adr`). A full sequence check took about 8 minutes on 4 workers (`2026-09-24-docs-build-performance-research`).
- The content-keyed verdict cache already exists (`dev/docs/sequences/verdict_cache.py`). It helps only if its root survives checkout.

## Considered options

- Merge gate. The chosen option: run the committed-goldens gate whenever a change can alter documented output, with the verdict cache on a runner-persistent root. Rejected: a nightly run, which still lets drift reach `main`; and selecting sequences by the pages a diff touched, which misses output changes caused by source edits.
- Authority currency. The chosen option: a refusal at the engine entry. Rejected: an automatic republish inside refresh, which mutates shared local state during a docs command and hides the stale condition.
- Preview. The chosen option: tiers that render from committed goldens without executing and reuse a persistent doctree cache. Rejected: a preview that executes sequences, which is slow and duplicates the gate.
- API stubs. The chosen option: generate them at build time in full scope, guarded by an independent derivation of the admitted module set. Rejected: keeping them committed with a `linguist-generated` mark, which hides the diff but keeps the conflicts and the regenerate-and-commit cycle.

## Constraints

- A single-page or section preview does not verify sequences. The gate does, and the preview says so.
- Writes the change scope makes must stay within its existing change-class rules and their tests (`dev/ci/tests/test_change_scope.py`).

## Implementation

- D1, authority currency: before executing anything, the sequence refresh, check and coherence modes confirm that the authority the runner will read is current, using `authority_database_currency`. When it is stale they refuse and name `uv run --no-sync python -m dev.registry.pipeline publish-authority --if-stale`. The result is cached per process.
- D2, merge gate: a change class covering `docs/**`, `dev/docs/**` and `src/cadrumo/**` selects the committed-goldens gate in the merge gate. The gate's job sets the verdict-cache root to a runner-persistent directory, so an unchanged input set skips execution. A cache miss runs the sharded check.
- D3, preview tiers:
  - `just docs-page PATH` accepts a page or a directory of pages, renders from committed goldens without executing sequences, and keeps its doctree cache between runs.
  - `just docs-build` stays the full build and gate.
  - `docs-serve` stops being classified as a partial build, so its generated references regenerate.
- D4, API stubs: a full-scope build generates `docs/api/*.rst` from the module tree at `builder-inited`, into the tree it reads. The stubs are removed from git and ignored; the hand-written `docs/api/index.md` stays. A test derives the admitted module set independently, as a plain walk of `src/cadrumo` minus the declared exclusions, and compares it with the generator's population. That keeps a filter defect visible without a committed copy.

## Rationale

Each decision moves a check to the earliest point that can see the fault:
- D1 turns a false divergence into one named refusal.
- D2 catches drift in the pull request that caused it, not at release.
- D3 gives authors seconds-scale feedback, because the gate already verifies the output.
- D4 removes a regenerate-and-commit cycle and a conflict source while keeping the only protection the committed tree gave.

## Consequences

- Pull requests that touch source or docs pay the sequence gate on a cache miss. Sharding must keep it inside the step budget; if it cannot, the gate needs its own step.
- Reviewers no longer see API stub churn. A dropped module shows up as a failing derivation test instead of a stub deletion.
- A preview can show a page whose goldens are stale. The page's frame-count check and the gate remain the protection.
