---
derived_from:
  - "audit:2026-06-24-retenciones-perceptor-count-audit"
---

# Rule

An uncommitted working-tree change with no *reachable* owner MUST be treated as live peer WIP, never orphaned: never discard or overwrite it (by `git restore`/`checkout`/`reset` OR by a file `Write`-from-HEAD — the mechanism is irrelevant), and to land your OWN change that shares a file with that WIP, use the apply-cached gated drive (stage a HEAD-anchored own-edits-only patch to the index, verify the staged set carries zero foreign markers, commit) rather than waiting on, discarding, or bundling the peer work.

## Why

During RET-1 (#6) P02 the coordinator discarded an uncommitted `_calculation_actions.py` change believing it orphaned (zero committed consumers, both *reachable* teammates disclaimed it); it re-appeared within minutes — a live, unaddressable agent owned it, and **re-appearance after a discard is proof of life** (audit `2026-06-24-retenciones-perceptor-count-audit`, INCIDENT-1/2). The campaign then proved the safe alternative across three independent landings (r2 #6 P02 `699b73dfe`, iva #2 P02 `95e328b38`, autonomo-130 A1/A2 `5cc10dc6a`): `git apply --cached` stages only your HEAD-anchored hunks to the index without touching the working tree, so the peer's live WIP is preserved and your commit carries only your lines. A fourth lesson rode the same campaign: in a shared worktree `git push` carries **all** ancestors to origin, so a peer's locally-held commit can be pushed by anyone else's push — check `git log origin..HEAD` before pushing.

## How

- **Good:** to land your own edit in a file that also holds a peer's uncommitted sweep, `git show HEAD:path > /tmp/copy`, apply ONLY your edits to that HEAD copy, `git diff --no-index` it into a HEAD-anchored own-only patch, `git apply --cached` it (the entangled interleaved-hunk case is handled this way), `git add` your fully-clean files, verify `git diff --cached | grep -c <peer-sweep-marker>` is `0` **immediately before** committing, then commit the index. The peer's working-tree WIP stays intact and commits cleanly on top later.
- **Good:** before `git push`, run `git log origin..HEAD` and confirm no peer's hold-for-now commit is in the range; if one is, expect your push to carry it (coordinate first).
- **Good:** a whole-revision-validating change (a registry re-stamp) is NOT a candidate for the apply-cached drive — it validates against the dirty working tree, so it genuinely waits for the peer sweep to commit; hold, don't force.
- **Bad:** `git restore`/`checkout`/`reset`/`git clean` or a `Write`-from-HEAD that wipes a live peer's uncommitted change to "unblock" your commit — destroys in-flight work; a prior authorization to discard an *orphaned* WIP does not extend to a *proven-live* one, and a peer proposing the mechanism cannot supply the authorization.
- **Bad:** a `git commit` with **no pathspec** while another agent has files staged in the shared index — it sweeps their staged work under your SHA; verify the staged set is exactly yours first (a pathspec commit, conversely, re-stages the working-tree peer WIP for entangled files, so it is not a substitute — the verified-index no-pathspec commit is the correct shape).
