---
tags:
  - "#exec"
  - "#aeat-restructure"
date: 2026-05-01
modified: '2026-05-01'
related:
  - "[[2026-04-30-aeat-restructure-adr]]"
  - "[[2026-04-30-aeat-restructure-plan]]"
  - "[[2026-04-30-aeat-restructure-step-05-shim-verifier-exec]]"
---

# 2026-04-30-aeat-restructure step-05 mechanical rebase script

## status

Step 5 PR 3 of N. Lands the mechanical import-path rebaser per ADR Transition mechanic + Acceptance criteria.

## scope

- `scripts/restructure_rewrite_map.json` — flat OLD→NEW dotted-path dict for every relocating module per the ADR Implementation section. 39 entries covering core/, adapters/inbound/, adapters/outbound/, adapters/persistence/, application/, entrypoints/, and the modelos rename.
- `scripts/rebase_imports.py` — pure-regex rewriter handling the four import shapes ADR Acceptance criteria mandates: absolute, relative (re-anchored against the file's new package location at run time), `TYPE_CHECKING` blocks, star imports, and dynamic `importlib.import_module` quoted-string forms. Longest-prefix-first ordering ensures sub-tree carve-outs (e.g. `aeat.entrypoints.cli.financial`) rewrite before their parent (`aeat.entrypoints.cli`).
- `scripts/test_rebase_imports.py` — 11-case test fixture covering every shape. Includes the round-trip identity test (forward → reverse returns the original input), satisfying the ADR Post-Step-8 rollback paths section's reverse-rewrite-map requirement.

## verification

- `pytest scripts/test_rebase_imports.py` — 11/11 passed.
  - Absolute / top-level / quoted dotted-name rewrites.
  - `TYPE_CHECKING` block rewrites.
  - Star-import rewrites.
  - Longest-prefix-first selection.
  - Unrelated imports preserved.
  - Substring-match defensive (no misfire on `aeat.errors_extra`).
  - Round-trip forward→reverse is identity.
  - Multi-symbol imports preserved.
  - Indented-block imports preserved.

## next step

Step 5 PR 4 — produce → verify → export end-to-end smoke test (CI-gating per ADR Acceptance criterion 13). The smoke test exercises the full Kent pipeline against a synthetic transaction set; structural import-resolution alone is insufficient proof of restructure correctness. Subsequent: PR 5 (mypy/ty config), PR 6 (packaging verification CI job).
