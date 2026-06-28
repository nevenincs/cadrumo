---
tags:
  - "#exec"
  - "#aeat-restructure"
date: 2026-05-01
modified: '2026-05-01'
related:
  - "[[2026-04-30-aeat-restructure-adr]]"
  - "[[2026-04-30-aeat-restructure-plan]]"
  - "[[2026-04-30-aeat-restructure-research]]"
---

# 2026-04-30-aeat-restructure step-12 tier-3 vault inline-updates

## status

Tier-3 inline-updates landed via PR #497.

## what

A new driver `scripts/rewrite_vault_paths.py` applies the canonical
`scripts/restructure_rewrite_map.json` longest-match-first to every
`.md` file under `.vault/`. Each document's topic / decision is
preserved — only the path token is rewritten.

## coverage

- 589 vault documents touched
- +5610 / -5610 lines (pure path-token swaps, identical line counts)
- `vaultspec-core vault check all`: same 9 errors / 6 warnings as
  pre-rewrite (no regression introduced)

## per-tier completion

| Tier | Treatment | Status | Step landed |
|------|-----------|--------|-------------|
| T1 | Supersession (Tier-1 documents replaced) | ✓ | Step 7 |
| T2 | Validate + inline-update (HARD GATE) | ✓ | Step 4 + Step 7 |
| T3 | Inline-update | ✓ | this step (PR #497) |
| T4 | Archive untouched | ✓ | (no-op) |

## findings disposition

All 589 rewrites were FIX dispositions. No FILE / STRIKE classifications
required: the rewrite map is exhaustive, the layout-move is canonical,
and the per-document substance is preserved.

## pre-existing drift (out of scope)

`vault check all` flags 9 pre-existing errors + 6 warnings unrelated
to the restructure:

- 1 filename-pattern violation (`2026-04-29-inventory-management-summary.md`)
- 2 dangling wiki-links
- 6 missing feature indices

These predate the restructure and are explicitly out of scope for
Step 12 per the plan's "Tier-3 inline-update" mandate (rewrite stale
references; do not re-design the corpus).
