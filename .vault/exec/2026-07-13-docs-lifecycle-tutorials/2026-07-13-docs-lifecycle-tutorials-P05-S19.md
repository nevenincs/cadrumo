---
tags:
  - '#exec'
  - '#docs-lifecycle-tutorials'
date: '2026-07-15'
modified: '2026-07-15'
body_hash: 'sha256:2ccded1d086ffd4b11dff95d806f632bf75e96f9f7f55717afdcc0be938cb02d'
step_id: 'S19'
related:
  - "[[2026-07-13-docs-lifecycle-tutorials-plan]]"
---

# Replay both lifecycle tutorials end-to-end against a sandbox profile and reconcile the narrated figures with real command output

## Scope

- `docs/tutorials/irpf-lifecycle.md docs/tutorials/iva-lifecycle.md`

## Description

- Locate both lifecycle tutorials at their post-restructure home
  (`docs/how-to/irpf-lifecycle.md`, `docs/how-to/iva-lifecycle.md`; the
  `docs/tutorials/` paths in the Step row predate the Tutorials-quadrant
  retirement).
- Replay both pages through the hermetic sequence engine
  (`python -m dev.docs.sequences check` and `check --coherence`) — four
  runs, each executing every cli-sequence block in fresh sandboxes.
- Hand-replay IRPF Stage 1 and Stage 2 in an isolated storage root to
  reconcile the prose-only narrated figures the automated goldens do not
  assert on.
- Reconcile every narrated figure against real command output.
- Fix the one divergence found and re-run the page gate to green.

## Outcome

- Golden tier and coherence tier both clean for both pages at HEAD.
- Every calculated figure matched: casilla 03 = 500.00, casilla 04 =
  100.00, casilla 13 minoración = 100.00 (narrated prose-only), casilla 19
  resultado = 0.00 (narrated prose-only), `granted_verificado_completo` =
  true, `completeness_status` = complete.
- One real command-syntax divergence found and fixed: the Stage 1
  profile-create display frame omitted the required
  `--entity-type natural_person` flag (a `@static` frame no gate executes;
  run verbatim it refused with `REFUSED_WIZARD_MISSING_FLAG`). Corrected in
  commit `7a0e056788`; page goldens re-verified clean.
- Step closed; the plan's final open step is complete.

## Notes

- A transient registry-load failure on the first coherence runs was peer
  campaign WIP (the Modelo 131 2024 fragments landing ahead of their legal
  catalogue entries); it self-resolved when the peer's atomic commit landed
  and is recorded here for transparency only — not a tutorial defect.
- The live VIES check and the `@static` Q2-Q4 / annual frames are skipped
  by design (they require a taxpayer's own filed history or a future
  presentation window); the coherence harness applies the same skip logic
  the pages document.
