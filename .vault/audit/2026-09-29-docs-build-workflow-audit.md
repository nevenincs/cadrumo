---
tags:
  - '#audit'
  - '#docs-build-workflow'
date: '2026-09-29'
modified: '2026-09-30'
body_schema: 'body-v2'
body_hash: 'sha256:43f533ea0246ad1813dfa8d44ac29607107832abe225273cf57f3cec9423d8ad'
related:
  - '[[2026-09-29-docs-build-workflow-plan]]'
---

# `docs-build-workflow` audit: `Docs build and preview workflow review`

## Scope

A design review, on 2026-09-29, of who builds and runs which documentation surface and when, and of which generated artifacts are committed. It was read-only, and an independent reviewer verified it against the files. The review covered the docs build (`dev/docs/build.py`, `docs/conf.py`, `dev/docs/serve.py`), the `cli-sequence` gate (`dev/docs/sequence_build_gate.py`, `dev/docs/sequences/`), the API stub generator (`dev/docs/apidocs/manager.py`) and the merge-gate change scope (`dev/ci/change_scope.py`).

Plan-close review, 2026-09-30, of the plan's Steps S01 to S05 as committed on `fix/docs-json`, against decisions D1 to D4. It traced the authority refusal through the engine, the build hook and the page children; the merge-gate selection and verdict key through a real change-scope probe; the preview recipe; and the build-time API stubs with their derivation guard. The later site-chrome, product, documentation and translation commits on the branch sit outside the plan's Steps and are not reviewed here. On the merged tree the local authority is stale only because `uv.lock` changed, which the compiler environment hashes, and the engine refuses as D1 requires. Result: `PASS`, with no critical or high finding.

## Findings

### sequence-drift-found-at-release | high | The pull-request gate never runs the cli-sequence check

The merge gate's change scope selects no `dev/docs` tests for changes to source, the registry or docs (`dev/ci/change_scope.py:88-143`). Golden divergence surfaces only at release prove (`.github/workflows/release.yml:305-312`), so drift accumulates and lands as bulk re-record commits. The change scope itself is derived from `git diff` (`dev/ci/change_scope.py:172-177`).

### stale-authority-bakes-wrong-goldens | high | Refresh and check trust a stale local authority

The sequence runner reads the locally published authority that `dev/_paths.py` selects. On 2026-09-29 a descriptor that predated three pulls produced 27 false golden divergences, and a refresh would have committed them. `authority_database_currency` (`dev/registry/pipeline/authority_publication.py:432-504`) detects this, but `dev/docs/sequences` never calls it.

### single-page-preview-is-cold | medium | Single-page preview executes sequences and re-reads every page

`--single-page` scopes the sequence check to the page, so its sequences execute (`docs/conf.py:1632-1646`, `dev/docs/sequence_build_gate.py:157-191`). It also uses a fresh temporary doctree directory (`dev/docs/build.py:724-729`), so Sphinx re-reads every non-API page on each run.

### no-section-preview | medium | No build scope exists between one page and everything

Only `--scope full|user` exists (`dev/docs/build.py:868-878`). The changed-page mode takes explicit paths, writes to a temporary directory and deletes it, so it is a check, not a preview (`dev/docs/build.py:737-756`).

### serve-misclassifies-its-build | medium | docs-serve looks like a partial build to conf.py

`dev/docs/serve.py` passes the source directory first, so `_specific_build_sources` returns spurious targets (`docs/conf.py:1010-1029`, acknowledged at `dev/docs/serve.py:517-523`). As a result the sequence check runs on no pages, and the glossary, casilla and legal references are not regenerated during serve. This was established by reading the code; it was not executed.

### api-stubs-committed-without-reason | medium | 1,950 generated API stubs are committed with no recorded decision

The stubs are a pure function of the module tree, written only by `python -m dev.docs.apidocs scaffold` and guarded byte-for-byte (`dev/docs/apidocs/manager.py:172-196`). `2026-06-01-docs-cli-buildtime-adr` moved the CLI reference to build time because committing it forced a regenerate-and-commit cycle, and the same argument applies to the stubs. The committed tree's one real benefit is catching a filter change that silently drops pages (`dev/docs/apidocs/manager.py:19-34`). Package stubs list their children, so sibling additions on concurrent branches conflict (`dev/docs/apidocs/manager.py:327-396`).

### verdict-key-missed-engine-imports | medium | The verdict key omitted dev modules the engine imports

The independent review before the pull request's first CI run found that the key hashed `dev/docs/sequences` and two named modules, while every sequence child runs through `dev/packaging/command_execution.py`. A change there could reuse a clean verdict recorded before it. S05 resolved it: the key and the documented-output change class both derive the engine's static `dev` import closure (`dev/docs/sequences/verdict_cache.py:134-171`, `dev/ci/change_scope.py:169`), and tests prove that a lazily imported helper changes the key while a `TYPE_CHECKING`-only import does not.

### goldens-gate-skips-compiler-changes | medium | Registry compiler changes never select the committed-goldens gate

The documented-output class matches `docs/**`, `dev/docs/**`, `src/cadrumo/**`, `uv.lock` and the engine's import closure (`dev/ci/change_scope.py:167-171`), and that closure excludes registry tooling (`dev/docs/sequences/verdict_cache.py:49`). The exclusion is right for the verdict key, which carries the authority generation, but selection runs before the key is computed. A pull request that changes only the registry compiler changes the compiled generation, and with it the documented output, yet the gate reports "not selected" (`dev/ci/sequence_goldens_gate.py:62-64`). A probe on 2026-09-30 returned false for `dev/registry/__init__.py`, one of 110 `dev/registry` files in the published authority's compiler closure, and for `pyproject.toml`, which the compiler environment also hashes. For that path class, drift still surfaces only at release prove, the fault D2 exists to remove.

### currency-check-repeats-per-page-child | low | Every page child re-runs the authority check its parent already made

`check_sequences_in_subprocess` refuses a stale authority once in the parent (`dev/docs/sequences/checks.py:634`). Each page child then runs `check --page`, whose `check_sequences` checks again (`dev/docs/sequences/checks.py:433-434`). One check re-hashes the registry sources and the compiler closure, which took 3.1 s in a fresh process on 2026-09-30. Across 34 sequence pages that adds about 13 s of wall time at the gate's 8 jobs (`dev/ci/sequence_goldens_gate.py:38`), and about 26 s at 4.

### currency-check-depends-on-import-order | low | The authority check finds no authority unless the path bootstrap was imported first

The checkout's authority root is seeded into the environment only as a side effect of importing `dev/_paths.py` (`dev/_paths.py:41-42`), and `dev/docs/sequences/authority_currency.py` does not import it. A fresh process that imported only that module got "no published registry authority resolves" from `require_current_authority`, although `.authority/authority.current.json` exists. Every current caller first imports `dev/docs/sequences/checks.py`, which imports `dev._paths` (`dev/docs/sequences/checks.py:25`), so no gate is affected today.

## Recommendations

- Decide how the pull-request gate runs the full sequence check, keyed by input content rather than a git diff.
- Make refresh and check refuse to run on a stale local authority, naming the republish command.
- Define preview tiers: a page and a section rendered from committed goldens with a persistent doctree cache, and the full build as the gate. Fix the serve classification.
- Decide whether the API stubs move to build time, and what guard replaces the committed tree.
- goldens-gate-skips-compiler-changes: select the gate for every input of the compiled generation, the registry compiler closure and `pyproject.toml`, not only for the verdict-key inputs. Widening D2's change-class list is a refinement for the docs build workflow ADR to settle, as an amendment or as confirmation that the release gate stays the backstop for compiler-only changes.
- currency-check-repeats-per-page-child: check currency once per gate run, not once per page child.
- currency-check-depends-on-import-order: make the authority check establish the path bootstrap it depends on.
