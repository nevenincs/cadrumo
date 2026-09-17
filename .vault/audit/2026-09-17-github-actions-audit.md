---
tags:
  - '#audit'
  - '#github-actions'
date: '2026-09-17'
modified: '2026-09-17'
body_schema: 'body-v2'
body_hash: 'sha256:ce77f59434ec7b83ae3b6a3ab3279a76722c352a0a07866488fa47d541b48c7f'
related:
  - "[[2026-09-17-github-actions-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace github-actions with a kebab-case feature tag, e.g. #foo-bar.
     Exactly these two tags are allowed; do not append additional tags.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - Cite code as inline backtick locators: `src/module.py:42`; never as a
       markdown link. -->

# `github-actions` audit: `github-actions phase-close review`

## Scope

Integrated review at the P02 to P04 phase close. It covers:
- `.github/workflows/merge-gate.yml`, `release.yml` and `release-please.yml`;
- `.github/actions/setup/action.yml`;
- the `justfile` recipes those workflows call;
- `dev/ci/change_scope.py`, `dev/release/pypi_publication_state.py` and the `--cohort-dir` path in `dev/packaging/campaign.py`.

## Findings

### fork-self-hosted | critical | Fork pull requests can run code on self-hosted runners

**Problem.** The repository is public, and `pull_request` runs the workflow file from the PR head. A fork can therefore remove the step-level guard at `.github/workflows/merge-gate.yml:28` and `:78`.

**Resolution.** The guard cannot be enforced from inside the workflow. It needs the repository setting that requires approval for runs from outside contributors, now owner Step `P05.S23`.

### too-broad-fallback | critical | A too-broad change scope runs only the fixed contract set

**Problem.** `dev/ci/change_scope.py:312-313` and `justfile:1001-1007` run only the fixed contract set when a change is too broad. A `conftest.py`, `pyproject.toml` or `core` change therefore merges after testing only that set.

**Resolution.** This matches the accepted decision: a visible advisory at merge, with full suites deferred to release. It is kept as an accepted risk.

### scoped-exclusions | high | Scoped test targets are dropped and serial tests never run

**Problem.** `justfile:1008` applies `calculation_exclusions`, which drops registry-selected targets. The `not serial` marker also means serial tests never run in the gate.

**Resolution.** Reopened for a fix.

### prove-commit-binding | high | The proven cohort is not bound to the commit of its prove run

**Problem.** `release.yml:925-926` locates the prove run by `headSha`, while the prove jobs check out `inputs.ref`, which can move. The cohort manifest records only the tag (`dev/packaging/release_cohort.py:442`).

**Resolution.** Reopened for a fix.

### integrity-sigpipe | medium | The integrity check can skip under SIGPIPE

**Problem.** `justfile:289` pipes `git diff` into `grep -q` under `pipefail`. If `grep` exits early, the SIGPIPE status can skip `integrity`.

**Resolution.** Fix in progress.

### docs-after-failure | medium | Docs can publish after a channel publish or acquisition check fails

**Problem.** `release.yml:1362` gates docs publication on the PyPI result only.

**Resolution.** Fix in progress.

### release-please-permissions | medium | The default token in release-please has more permission than it uses

**Problem.** `release-please.yml:16-19` grants write scopes to the default token, which only lists pull requests.

**Resolution.** Fix in progress.

### duplicate-release-gate | low | The merge gate runs twice on the release PR head

**Problem.** The release PR head gets the `pull_request` gate, and the prove run calls the same gate with a full scan (`release.yml:34-39`).

**Resolution.** Accepted as intentional: the prove run adds the full scan.

## Recommendations

- **fork-self-hosted:** the owner enables approval for outside-contributor runs before `P05.S09` makes the gate required.
- **too-broad-fallback:** revisit the decision if post-merge breakage from broad changes shows up before releases.
