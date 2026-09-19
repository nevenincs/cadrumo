---
tags:
  - '#audit'
  - '#issue-630-immutable-dispatch'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:9886185ed4beb5dd5f946ca8c7afc946e6ac3ea7d1654c2ccb08287078177e90'
related: []
---

# `issue-630-immutable-dispatch` audit: `Immutable release dispatch implementation review`

## Scope

Fresh-context review of implementation commit
`36a2b0e567c49f048393e20255e81cadbace0eec` against its parent and current
branch HEAD. The audit covered immutable revision validation, `gh workflow run` argv,
dispatch-to-resolution identity, removal of the mutable `--ref` CLI option, the
branch-advance regression, and every repository caller of `dispatch_workflow`,
`dispatch_and_resolve`, and the `dev.release.run_resolution` CLI. No workflow was
dispatched and production code was not modified.

## Findings

### pre-dispatch-sha-validation | high | Invalid revisions are dispatched before they are refused

`dispatch_and_resolve` captures the clock and calls `dispatch_workflow` with `head_sha`
before any immutable-SHA validation runs. The only validation remains inside
`resolve_dispatched_run`, reached after `gh workflow run` has already performed the
external mutation. Thus a malformed CLI value such as `main`, a short SHA, or non-hex
text is sent as `--ref`; only after GitHub accepts or refuses that dispatch does local
resolution report that the value is not a full commit SHA. The composite function's
contract says it dispatches an exact immutable revision, so validation must precede its
first external action. Existing coverage tests malformed input only at the pure resolver
and never proves that the mutating composite refuses before invoking `gh`.

### sha-case-identity | medium | Accepted uppercase SHA input cannot match GitHub's canonical lowercase run identity

The SHA validator explicitly accepts uppercase hexadecimal, but candidate matching compares
`record["head_sha"] == head_sha` case-sensitively. Git object ids are hexadecimal identities,
and GitHub run payloads return the canonical lowercase spelling. An uppercase full SHA
therefore passes validation and can dispatch the intended commit, then polls until budget
exhaustion because the same identity in lowercase is rejected. A direct resolver probe with
an uppercase 40-character SHA and its lowercase run record reproduced
`RunNotYetVisibleError`. Either normalize once to lowercase before both dispatch and
resolution, or reject non-canonical spelling before dispatch.

No critical findings were identified. For the repository's current workflow callers,
`BUMPED_COMMIT`, resumed-run `head_sha`, and acquisition `HEAD_SHA` all flow through the
single `--head-sha` argument; the removed `--ref` option is absent from the CLI and both
orchestrator call sites. The generated dispatch argv places that same SHA after `--ref`,
and the branch-advance regression correctly ignores the newer-main run and resolves the
chosen revision. Those facts do not close the invalid-input mutation ordering or accepted
case mismatch above.

## Recommendations

- For `pre-dispatch-sha-validation`, centralize full-SHA validation and invoke it at the
  beginning of `dispatch_and_resolve`, before reading the dispatch timestamp or resolving
  and invoking `gh`. Add a subprocess-boundary regression whose probe executable records
  invocation and prove malformed input leaves it untouched.
- For `sha-case-identity`, canonicalize the validated SHA once and use that exact value for
  both dispatch argv and run matching, with coverage for uppercase input and a lowercase
  GitHub run record; alternatively refuse uppercase as non-canonical before dispatch.
- Do not integrate the commit or close issue 630 until both findings are resolved and the
  focused workflow/resolver gates remain green.

## Resolution verification

Corrective commit `79e4db0c7963c8b455c11565d5c3cf4db4f75878` resolves both
settled findings. A single `_canonical_commit_sha` boundary validates a full hexadecimal
object id and returns GitHub's lowercase spelling. `dispatch_and_resolve` invokes it before
reading the clock, resolving `gh`, or dispatching; `dispatch_workflow` independently invokes
the same boundary before resolving or calling its subprocess; and
`resolve_dispatched_run` canonicalizes before any live run-list request. Mutable branch
names, short ids, and non-hex 40-character tokens therefore refuse before every external
side effect on each exposed path.

The canonical lowercase SHA is now passed to `gh workflow run --ref`, forwarded into
polling, compared with GitHub's run record, and returned in `DispatchedRun`. The new
uppercase regression confirms one lowercase identity crosses both dispatch and matching.
The no-side-effect regressions use an argv-capturing subprocess and prove invalid refs
create no capture; the composite regression additionally proves its clock is not read.

All repository callers remain coherent: the release orchestrator's campaign and derived
acquisition-lane calls still expose only `--head-sha`, the removed CLI `--ref` option has
not returned, and unrelated direct-dispatch workflows remain outside this resolver's
identity contract.

Verification at current HEAD:

- Run-resolution, release-orchestrator workflow, and adjacent change-tier tests: 72
  passed.
- Ruff, CLI-help surface inspection, caller sweep, and corrective-diff whitespace check:
  clean.
- No new severity-ranked findings were identified.

The implementation is now safe to integrate, and issue 630 is safe to close.
