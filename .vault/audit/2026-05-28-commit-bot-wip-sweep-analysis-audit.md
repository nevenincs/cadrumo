---
name: commit-bot-wip-sweep-analysis
description: Process analysis of commit-bot WIP-sweep race condition in shared parallel worktree
metadata:
  type: audit
  date: 2026-05-28
  modified: '2026-05-28'
  tags:
    - "#audit"
    - "#restructure-execution"
---

# Commit-bot WIP-sweep race condition analysis

## Incident

S400 fresh-agent execution 2026-05-28 observed three intended author-commits swept into peer commit-bot bundles before the author could explicitly stage them:

- Commit c2fb739d1 (peer-authored bundle)
- Commit 699044acf (peer-authored bundle)
- Commit fd506bfdd (peer-authored bundle)

The code survives (all lines reachable, tests pass), but **commit-message authorship breaks**: future `git bisect` / `git blame` operations return the commit-bot instead of the actual author.

## Root Cause

**Commit-bot harvest pattern exploits a window between Edit calls and git add:**

1. Agent A calls `Edit` to modify file X
2. Agent A completes semantically-related edit to file Y
3. Agent A prepares to call `git add -- X Y` with intended commit message
4. **Between step 2 and step 3, peer commit-bot scans working tree**
5. Commit-bot detects un-committed changes in X and Y
6. Commit-bot bundles X+Y into a standalone commit with peer authorship
7. Commit-bot pushes before Agent A can run `git add`

Result: Agent A's intended semantic commit message is lost; the work appears under peer authorship in the log.

## Existing Defense Insufficient

The memory rule `explicit_path_staging_in_parallel_worktree` mandates explicit-path staging (`git commit -- <paths>`), which prevents **index pollution** (other agents' changes mixing into the commit). However, it does **not** prevent the **harvest-window race**: even with explicit paths, if the commit-bot runs between Edit and `git add`, the commit-bot sees untracked changes and harvests them.

## Quasi-Fix: Tighter Edit→Stage→Commit Cycles

**Agents authoring work that requires specific commit-message attribution should run `git add -- <explicit-paths>` + `git commit -- <explicit-paths>` immediately after every semantically-complete edit, rather than batching edits and staging at the end.**

### Change in Discipline

**Before (vulnerable to sweep):**
```
Edit file A (semantic unit 1)
Edit file B (semantic unit 2)
Edit file C (semantic unit 3)
[HARVEST WINDOW HERE]
git add -- A B C
git commit -m "msg"
```

**After (minimizes harvest window):**
```
Edit file A (semantic unit 1)
git add -- A
git commit -- A -m "msg 1"

Edit file B (semantic unit 2)
git add -- B
git commit -- B -m "msg 2"

Edit file C (semantic unit 3)
git add -- C
git commit -- C -m "msg 3"
```

The second pattern reduces the harvest window from "multi-edit phase" to "single Edit duration", making bot interception less likely.

## Questions for Coordinator Review

### Safety Assessment

1. **Is the harvest-pattern conservative?** Does the commit-bot validate that changes are non-conflicting before bundling? Or does it blindly sweep any untracked working-tree changes?
2. **Is the bundling safe?** Do swept commits maintain correctness (no broken tests, no import errors)?
3. **Is the attribution problem severe?** When `git bisect` or `git blame` returns the commit-bot, can operators trace back to the original author through commit message context or other metadata?

### Process Implications

1. **Should this discipline be mandatory for all agents?** Or only for agents writing code/tests that will be bisect-inspected?
2. **Should commit-bot harvest be disabled entirely?** Or only disabled for WIP-phase agents still iterating on semantically-linked edits?
3. **Is there a kernel-level fix?** (e.g., commit-bot respects `.git/index.lock` as a liveness signal that an agent is mid-stage, and defers harvest until lock clears)

## Candidate Lesson #8

If the harvest-pattern is deemed safe enough to keep, this should be banked as **Lesson #8: Edit→commit cycles must be atomic in shared worktrees** — agents planning multiple edits for a single logical commit should anticipate harvest-window interception and compress the window by committing immediately after each Edit in the batch.

## Recommendation

Surface this to the coordinator for a **process-level decision on commit-bot behavior**. The current state is:
- ✅ Content preservation (work survives, no data loss)
- ✅ Test correctness (swept commits don't break tests)
- ❌ Attribution accuracy (future bisect/blame is wrong)

The question is whether ❌ is acceptable in a shared worktree, or whether it warrants disabling the harvest pattern entirely or requiring tighter cycles.
