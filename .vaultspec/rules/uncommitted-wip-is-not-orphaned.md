# Uncommitted work with no reachable owner is live peer WIP

## Rule

An uncommitted working-tree change with no *reachable* owner MUST be treated as
live peer WIP, never as orphaned. Never discard or overwrite it — not with
`git restore`/`checkout`/`reset`/`clean`, and not with a `Write`-from-HEAD
either; the mechanism is irrelevant.

To land your OWN change that shares a file with such WIP, use the apply-cached
gated drive rather than waiting on, discarding, or bundling the peer work.

## Why

An agent once discarded an uncommitted change believing it orphaned — zero
committed consumers, and both reachable teammates disclaimed it. It re-appeared
within minutes: a live, unaddressable agent owned it. **Re-appearance after a
discard is proof of life.**

The safe alternative was then proven across three independent landings.
`git apply --cached` stages only your HEAD-anchored hunks to the index without
touching the working tree, so the peer's live WIP is preserved and your commit
carries only your lines.

## How

- **Good — the apply-cached drive.** `git show HEAD:<path>` into a scratch copy
  (capture bytes, not decoded text); apply only your edits to that HEAD copy;
  produce a HEAD-anchored own-only patch with `git diff` (which normalises line
  endings) and write it in binary; `git apply --cached --check` then
  `git apply --cached`; verify the staged set carries zero foreign markers
  **immediately before** committing; then commit the index. Unstage with
  `git apply --cached --reverse`.
- **Good — check the push range.** `git push` carries all ancestors, so a peer's
  locally-held commit can be pushed by anyone else's push. Run
  `git log origin..HEAD` first.
- **Good — know when to wait.** A whole-revision-validating change (a registry
  re-stamp) validates against the dirty working tree, so it genuinely waits for
  the peer sweep to commit. Hold; do not force.
- **Bad:** any destructive verb or a `Write`-from-HEAD that wipes a live peer's
  uncommitted change to unblock your commit. A prior authorization to discard an
  *orphaned* change does not extend to a *proven-live* one, and a peer proposing
  the mechanism cannot supply the authorization.
- **Bad:** a `git commit` with **no pathspec** while another agent has files
  staged in the shared index — it sweeps their work under your SHA. Verify the
  staged set is exactly yours first. A pathspec commit is not a substitute for
  an entangled file, because it re-stages the peer's working-tree lines; the
  verified-index bare commit is the correct shape there.

Companion: `subagent-commits-require-explicit-pathspec`.
