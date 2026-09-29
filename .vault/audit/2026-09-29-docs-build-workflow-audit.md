---
tags:
  - '#audit'
  - '#docs-build-workflow'
date: '2026-09-29'
modified: '2026-09-29'
body_schema: 'body-v2'
body_hash: 'sha256:5f698d52e047f4c55ddcf77fa6c735a297ca41f460289714f89dfff422d1d72b'
related: []
---

# `docs-build-workflow` audit: `Docs build and preview workflow review`

## Scope

A design review, on 2026-09-29, of who builds and runs which documentation surface and when, and of which generated artifacts are committed. It was read-only, and an independent reviewer verified it against the files. The review covered the docs build (`dev/docs/build.py`, `docs/conf.py`, `dev/docs/serve.py`), the `cli-sequence` gate (`dev/docs/sequence_build_gate.py`, `dev/docs/sequences/`), the API stub generator (`dev/docs/apidocs/manager.py`) and the merge-gate change scope (`dev/ci/change_scope.py`).

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

## Recommendations

- Decide how the pull-request gate runs the full sequence check, keyed by input content rather than a git diff.
- Make refresh and check refuse to run on a stale local authority, naming the republish command.
- Define preview tiers: a page and a section rendered from committed goldens with a persistent doctree cache, and the full build as the gate. Fix the serve classification.
- Decide whether the API stubs move to build time, and what guard replaces the committed tree.
