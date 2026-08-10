---
tags:
  - '#audit'
  - '#profile-active-routing'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:28175f56a239693570d1bdebaea76ea8766ea613048bb4d55f8fe5731259c0bc'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace profile-active-routing with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `profile-active-routing` audit: `Profile active routing code review`

## Scope

Fresh-context review of committed `HEAD` `28585d91a7` against the accepted
`cli-workflow-redesign` profile-routing contract. The review covered the
optional target for `config profile edit`, omitted and explicit targets for
`config profile history`, conditional root gating for `config profile
validate`, explicit-target argument parsing, target-scoped repository and
authentication boundaries, operator-help grammar, storage write-policy
catalogue cleanup, and the focused real-behaviour tests. Production code was
reviewed read-only.

## Findings

### shared-worktree-process | high | Prohibited recovery operations bypassed peer-WIP safeguards

The parent reports restoring the exact governing ADR with Git and manually
deleting a stale `.git/index.lock`. Both operations bypass the preservation
discipline required in this shared worktree: restoring a tracked file can
discard concurrent authored changes, while removing a lock without proving
that no owning Git process remains can permit concurrent index mutation. The
review re-read committed `HEAD` and found the intended ADR and implementation
present, so no resulting product defect was observed, but the process breach
made that outcome contingent rather than safe by construction.

### explicit-target-parser-coverage | low | The option-value scanner lacks direct regression tests

The root correctly distinguishes omitted `show`, `validate`, and `history`
targets from explicit targets and currently skips every value-taking option
used by those leaves. The focused CLI tests cover the principal unnamed and
named forms, but do not directly prove that values supplied to `--format`,
`--language`, `--output-language`, history filters, or global `--profile` are
never mistaken for positional targets. Because the scanner maintains its own
option catalogue, a later option addition could silently turn an active-profile
read into a self-scoped bypass.

Resolved in the same campaign: direct tests now import the production scanner
and cover separated and `=` option values, global `--profile`, every history
filter family, and positional targets following options. The focused test lane
passes all twelve cases.

### interactive-edit-proof | low | Successful cross-profile manager handover is not end-to-end proven

The edit-routing tests use real registered profiles and prove that omitted and
active targets pass, while unknown and non-active targets cannot silently edit
the active taxpayer. They intentionally exercise the non-full-screen refusal
branch. The successful interactive branch—present the canonical login screen,
authenticate the named non-active profile, hand over the pointer, then open
that profile in the manager—is covered by composition of the routing and login
screen tests rather than one terminal-capable end-to-end test. No implementation
error was found in that composition.

No medium, high, or critical product finding remains. History constructs
`BucketEventHistoryRepository` with the requested bucket's secure-object
repository, binds that authenticated target to the invocation, and defaults
omission through the active bucket pointer. Unnamed validation reaches the
canonical active-session gate; named validation bypasses only the unrelated
active-profile gate and reads within the target's own storage session. Operator
help exposes `edit [NAME]` and `history [PROFILE]`. The write-policy catalogue
removes `config reset` and duplicate invoice entries and has a uniqueness
assertion. These boundaries satisfy the accepted ADR without moving business
logic into the CLI.

## Recommendations

- For `shared-worktree-process`, do not use restore-like Git operations on
  shared tracked files. Inspect with `git diff`/`git show`, preserve peer WIP,
  and only remove an index lock after identifying the owning process and
  proving it has exited; coordinate any exceptional recovery explicitly.
- `explicit-target-parser-coverage` is closed by the direct production-parser
  regression matrix added during this review.
- For `interactive-edit-proof`, retain the current fail-closed tests and add a
  real terminal-capable journey when the test harness can host the full-screen
  login flow. This is a validation enhancement, not a release-blocking code
  change.
