---
tags:
  - '#audit'
  - '#registry-m123-fragmentation'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - "[[2026-06-02-registry-hardening-next-work-plan]]"
---

# `registry-m123-fragmentation` audit: `M123 directory-mode fragmentation need audit`

## Scope

Audit `src/aeat/_data/registry/aeat/modelos/123` for the P04.S27
directory-mode fragmentation decision. The audit checked current layout, local
diff state, stale single-file siblings, line-count headroom, row-length
headroom, and likely future split boundaries.

## Findings

- **PASS:** M123 already uses directory mode through `manifest.toml` and
  revision directories for `2019-2023` and `2024-y-siguientes`.
- **PASS:** No stale `123.toml` sibling exists, and `git diff -- .../123`
  reported no local registry-data edits before this audit.
- **PASS:** The largest M123 fragment is `2024-y-siguientes/revision.toml` at
  1,218 lines. The next largest is `2019-2023/revision.toml` at 932 lines.
  Both are below the current TOML fragment gate and below the older
  single-file reviewability ceiling.
- **PASS:** Maximum row length is 305 characters in the 2019 revision, 290 in
  the 2024 revision, 207 in `manifest.toml`, and 180 or less in the
  completeness manifests. All are below the row-size gate.
- **WATCH:** Export layout record fields dominate both revision files. If M123
  approaches the reviewability ceiling, export layouts are the first generic
  split boundary to use, before casillas.
- **WATCH:** The 2024 revision also carries deadline windows near the tail.
  Future fragmentation should keep deadline, application-link, live-reference,
  extraction-profile, and export-layout sections separated by generic fragment
  categories rather than introducing M123-specific behavior.

## Recommendations

- Do not split M123 in this step. It is already reviewable directory-mode data
  with meaningful line-count and row-length headroom.
- Continue enforcing corpus-level TOML file-size and row-size gates so M123
  cannot silently regress into a large single-review surface.
- If future growth pushes M123 near the threshold, split section-first:
  `export` fragments, then application/deadline/live-reference/extraction
  fragments, then casilla fragments only if needed.
- Keep the loader and schema path generic. M123 needs no model-specific
  definition or loader branch.
- For any future split, verify the generic directory-mode loader and committed
  registry load with focused registry tests before closing the step.

## Codification candidates

- **Source:** M123 no-split decision.
  **Rule slug:** `fragment-only-when-reviewability-pressure-exists`.
  **Rule:** Do not fragment already reviewable directory-mode modelos solely
  for symmetry; split only when file-size, row-size, or section-density gates
  justify a generic fragment boundary.
