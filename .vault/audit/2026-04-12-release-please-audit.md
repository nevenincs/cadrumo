---
tags:
  - "#audit"
  - "#release-please"
date: 2026-04-12
modified: '2026-04-12'
title: release-please local-only — code review audit
related:
  - "[[2026-04-12-release-please-adr]]"
  - "[[2026-04-12-release-please-plan]]"
  - "[[2026-04-12-release-please-phase5-summary-exec]]"
issue: wgergely/aeat#60
verdict: accept-with-changes
---

# audit: release-please local-only wiring

Reviewer: vaultspec-code-reviewer (agent)
Branch: `chore/60-release-please`
Verdict: **ACCEPT WITH MINOR CHANGES** (all non-blocking)

## rubric

| # | Check                                                    | Result       |
| - | -------------------------------------------------------- | ------------ |
| 1 | LOCAL-only rule (no `release-please.yml`)                | PASS         |
| 2 | Version source-of-truth three-way agreement              | PASS         |
| 3 | Pydantic mandate (v2 + `extra="forbid"`)                 | PASS         |
| 4 | Unit tests cover config + manifest + changelog + version + workflow | PASS |
| 5 | CHANGELOG backfill accuracy vs `git log main`            | PASS (notes) |
| 6 | `just release`/`release-apply` `[unix]`+`[windows]` parity | PASS       |
| 7 | CLAUDE.md conventional-commits mandate                   | PASS         |
| 8 | Local gates green (lint, typecheck, test, hooks)         | PASS         |
| 9 | No out-of-scope creep (`src/aeat/`, `[tool.pytest]`)     | PASS         |

## findings

### blocking

None.

### non-blocking (LOW severity)

1. **`release-apply` is instructional-only, not executable.** The
   recipe prints a 7-step checklist; the operator performs the
   edits by hand. `RELEASING.md` §2 wording ("guides the operator
   through… Updating…, Creating a commit…, Creating a tag…") could
   read as if the recipe does these things. **Action taken**:
   tightened the RELEASING.md wording to make the instructional
   nature explicit. Keeping the recipe manual is defensible for a
   v0.1.0 scaffold.
2. **`npx release-please@16` pins only the major.** A minor/patch
   bump could change `--dry-run --debug` output shape. Acceptable
   for now; revisit if release-please 16.x lands a breaking change.
3. **CHANGELOG `[0.1.0]` editorial annotations** (e.g. the
   "superseded" note on #31, the collapsed status #43 follow-ups)
   are not reproducible by release-please. Acceptable as a one-time
   hand-seeded backfill.
4. **`test_release_please_manifest_is_well_formed`** asserts
   `list(payload.keys()) == ["."]` before the pydantic parse. The
   model already enforces this via `extra="forbid"` + a single
   aliased field. Redundant but harmless.
5. **`.vaultspec/providers.json`** carries a pre-existing local
   modification unrelated to #60. Excluded from the PR commit.

### notes (FYI)

- `ci` and `style` are correctly `hidden: true` in
  `release-please-config.json` so future generated CHANGELOGs stay
  focused on user-visible sections.
- `release` writes only to `var/release/` which is covered by the
  blanket `var/` entry in `.gitignore`.
- Test-file docstring pre-empts the "why not colocated?" question
  with an explicit pointer to the ADR.

## actions taken in response

- Tightened `RELEASING.md` §2 wording to make clear that
  `just release-apply` prints a checklist rather than performing
  the edits. See diff in the PR.
- Confirmed `.vaultspec/providers.json` is excluded from the
  commit.
- No other LOW-severity items were addressed in this PR; they are
  editorial and out of scope for the scaffolding chore.

## conclusion

Accept. The executing team commits the work, opens the PR, and
references this audit alongside the ADR, plan, and phase-5 summary.
