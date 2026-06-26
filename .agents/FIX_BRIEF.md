# Fix-agent brief — land one confirmed fix safely in a shared worktree

You are a senior engineer fixing ONE confirmed issue from the documentation/functionality
hardening audit (`.vault/audit/2026-06-18-aeat-user-docs-hardening-audit.md`). The root
cause is already diagnosed in your task; verify it, then land a real fix + test.

Repo: `Y:\code\aeat-worktrees\chore-476-restructure-execution`. CLI: `uv run --no-sync aeat …`.

## Hard safety rules (this tree runs many concurrent agents)
- NEVER run a destructive git command: no `stash`, `reset`, `checkout`/`restore <path>`,
  `clean`, `rebase`, `revert`, `branch -D`, `worktree remove`, force-push, or `rm -rf` of
  tracked paths. Read-only git (`status`, `diff`, `log`, `show`) only, plus
  `git add -- <your explicit files>` is allowed but **do NOT commit** unless told to.
- Before your first edit to any file: run `git diff -- <file>` and `git log -1 -- <file>`.
  If the file has uncommitted peer WIP you did not author, STOP and report it — do not edit.
- Stay strictly within your assigned file scope. Do not touch files another agent owns.

## How to work
1. Reproduce the issue first (run the documented command in an isolated runtime:
   `cd <repo> && source .agents/persona_env.sh /tmp/fix-<your-slug> && uv run --no-sync aeat …`).
   The harness sets `AEAT_SECRET_PASSPHRASE` and isolates all `var/*` state per agent.
2. Read the relevant code, confirm the root cause, implement the minimal correct fix.
   Follow project rules: typed pydantic boundaries, closed-set enums in `core`, no shims,
   no legacy branches, CLI errors must be typed refusals (never raw tracebacks), regulated
   values must stay grounded in the registry/legal corpus (do not invent tax behaviour).
3. Add a REAL regression test under the nearest `tests/` folder (never beside the module).
   No mocks/fakes/stubs/monkeypatch/xfail/skip. No tautological assertions. The test MUST
   fail on the old behaviour and pass on your fix. For calc values, do not hand-compute the
   registry formula — assert structure/provenance/real-world identity instead.
4. Verify: run `uv run --no-sync ruff check <your files>` (clean) and your scoped tests
   (`uv run --no-sync pytest <your test path> -q -p no:cacheprovider`, add `-m integration`
   if the file is marked integration). Re-run the reproduction to confirm the CLI now behaves.
5. Do NOT commit. Leave changes in the working tree.

## Report back (compact, ≤15 lines)
- The fix: file(s) + one-line description of the change.
- The test: path + what it asserts + that it's green.
- Repro before/after (the actual CLI output difference).
- Any peer-WIP abort, or any part you could not complete and why.
- Whether lint + scoped tests are green.
