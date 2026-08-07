---
name: subagent-commits-require-explicit-pathspec
trigger: always_on
---

# Commits require an explicit pathspec

## Rule

A dispatched agent or the coordinator committing in this shared worktree MUST
pass an explicit pathspec to `git commit -- <path>...` naming only files it
authored, and MUST verify with `git diff --cached` that the staged set carries
zero foreign markers immediately before committing.

**A bare `git commit` with no pathspec is forbidden** unless the index was
deliberately built by an apply-cached staging and verified own-only: the shared
index routinely holds peer campaigns' staged work, and a no-pathspec commit
sweeps all of it under your SHA and message.

## Why

A subagent tasked with a one-line change verified its own file was clean, ran
`git add -- <its file>`, then ran `git commit` with **no pathspec**. The shared
index already held 35 staged files from an unrelated campaign, and all of them
were bundled into one commit under the subagent's message. This was not benign:
it left a registry regime broken at committed HEAD — a deleted derivation
function still referenced by schema and bindings, a silent-under-declaration
defect — and mis-attributed a peer campaign's work to a foreign SHA.

`git add` being path-scoped is not enough; the commit itself must be
path-scoped, because `git commit` with no pathspec commits the entire index.

## How

- **Good:** `git commit -m "..." -- src/cadrumo/foo.py src/cadrumo/tests/test_foo.py`
  after `git diff --cached -- <those same paths>` confirms only your hunks are
  staged. A pathspec commit ignores every other staged path.
- **Good:** for a file entangled with a peer's uncommitted hunks, use the
  apply-cached gated drive from `uncommitted-wip-is-not-orphaned` — a verified
  own-only index, then a bare commit — rather than a pathspec commit that would
  re-stage the peer's interleaved lines.
- **Good:** verify AFTER with `git show <sha> --numstat`. A pre-commit index
  read is TOCTOU: a peer can stage between your check and your commit.
- **Bad:** `git add -- my_file.py && git commit -m "..."` — no pathspec on the
  commit sweeps every other staged file under your SHA.
- **Bad:** a no-pathspec `git commit` "because I only touched one file". You did
  not stage the index; peers did, and the commit takes the whole index.
- **Bad:** a broad `git add` (a directory, `-A`, or `.`) followed by
  `git reset -- <your files>` to undo it. `git reset` in any form is
  categorically forbidden here. There is no reset escape hatch: never
  over-stage.

Companions: `uncommitted-wip-is-not-orphaned`, `aeat-git-worktree-safety`.
