---
name: subagent-commits-require-explicit-pathspec
trigger: always_on
---

# Rule

A dispatched agent (or coordinator) committing in this shared worktree MUST pass
an explicit pathspec to `git commit -- <path>...` naming only files it authored,
and MUST verify (`git diff --cached`) that the staged set carries zero foreign
markers immediately before committing. A bare `git commit` with no pathspec is
forbidden: the shared index routinely holds peer campaigns' staged work, and a
no-pathspec commit sweeps all of it under your SHA and message.

## Why

During the DAE-80 agent-harness rollout a subagent tasked with a one-line change
verified its own file was clean, then ran `git add -- <its file>` followed by a
`git commit` with NO pathspec. The shared index already held 35 staged files from
the unrelated `cross-domain-continuity` campaign, and the no-pathspec commit
bundled all of them into commit `84f84166f` under the subagent's message. This
was not benign: it left the M100 anualidades regime (LIRPF art. 64/75) broken at
committed HEAD — a deleted derivation function still referenced by
`schema.toml`/registry bindings, a silent-under-declaration-class defect — and it
mis-attributed a peer campaign's work to a foreign SHA. `git add` being
path-scoped is not enough; the commit itself must be path-scoped, because
`git commit` with no pathspec commits the entire index. This is the enforcement
teeth behind `uncommitted-wip-is-not-orphaned` (which governs how to LAND your own
change amid live peer WIP) and `aeat-git-worktree-safety` (which forbids the
destructive un-bundling that a swept commit tempts).

## How

- **Good:** `git commit -m "..." -- src/cadrumo/foo.py src/cadrumo/tests/test_foo.py`
  after `git diff --cached -- src/cadrumo/foo.py src/cadrumo/tests/test_foo.py` confirms
  only your hunks are staged; a pathspec commit ignores every other staged path.
- **Good:** for a file entangled with a peer's uncommitted hunks, use the
  apply-cached gated drive from `uncommitted-wip-is-not-orphaned` (stage a
  HEAD-anchored own-edits-only patch, verify zero foreign markers, then a
  verified-index commit) rather than a pathspec commit that would re-stage the
  peer's interleaved lines.
- **Bad:** `git add -- my_file.py && git commit -m "..."` (no pathspec on the
  commit) — sweeps every other file staged in the shared index under your SHA.
  This is the `84f84166f` incident.
- **Bad:** a no-pathspec `git commit` "because I only touched one file" — you did
  not stage the index; peers did, and the commit takes the whole index.
- **Bad:** a broad `git add` (a directory, `-A`, or `.`) that sweeps peer-staged
  files, then a `git reset -- <your files>` to "undo" it. `git reset` in any form
  is categorically forbidden here (`aeat-git-worktree-safety`) — even an
  index-only pathspec reset. The fix is to never over-stage: `git add -- <your
  explicit files only>` then `git commit -- <the same explicit files>`. If you
  ever find you need `git reset` to clean up a bad add, you added too broadly —
  there is no reset escape hatch.
