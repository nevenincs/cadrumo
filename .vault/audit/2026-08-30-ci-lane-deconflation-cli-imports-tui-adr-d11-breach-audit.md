---
tags:
  - '#audit'
  - '#ci-lane-deconflation'
date: '2026-08-30'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:4ed69ac54b7dcec22b1bcf5a15b8b14239a21242f07ef150d272d4209b7be37f'
related:
  - "[[2026-08-11-tui-architecture-adr]]"
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# `ci-lane-deconflation` audit: `CLI imports TUI in breach of ADR D11`

## Scope

The five `cadrumo.entrypoints.cli -> cadrumo.entrypoints.tui` import edges import-linter reported at HEAD 2026-08-31, once the layering gate was restored by commit `f3e2617c`. Edges read from grimp, the same graph import-linter walks. No code was changed by this audit: the remedy spans the CLI surface and the TUI boundary and is a design decision, not a sweep.

## Findings

### the CLI imports the TUI at five sites, which ADR D11 forbids by name | `src/cadrumo/entrypoints/cli/`

- `_modelo_work_select_cli.py:45` -> `entrypoints.tui.modelo.view.work_select` (`ModeloWorkSelectApp`)
- `_modelo_work_select_cli.py:59` -> `entrypoints.tui.components.host` (`ScreenHostApp`)
- `_modelo_work_select_cli.py:60` -> `entrypoints.tui.modelo.routes` (`WORKSPACE_SELECTION_OUTCOME`, `resolve_destination`)
- `_modelo_work_select_cli.py:61` -> `entrypoints.tui.modelo.view.controller` (`admit_workspace_session`)
- `_modelo_work_review_cli.py:29` -> `entrypoints.tui.modelo.view.work_review` (`ModeloWorkReviewApp`)

`2026-08-11-tui-architecture-adr` D11 states: "`cadrumo.entrypoints.tui` is an outermost entrypoint package. No backend package, CLI or MCP entrypoint, shared test utility, or development tool may import, load, re-export, annotate against, or register from it. Packaging metadata and out-of-process smoke execution are the only external references."

The ruling admits no exception for a deferred import, and all five of these ARE deferred -- function-local, behind the `tui_was_requested` policy check. Deferring an import changes when the edge executes, not whether it exists; D11 forbids importing, not importing eagerly.

### nothing sanctioned these: they are unexempted violations, not carve-outs | `.importlinter`

`.importlinter` carries exemptions for `entrypoints.tui.launcher -> adapters` -- the OUTWARD direction, which D11 permits -- and none for the inward `cli -> tui` direction. So these five were never adjudicated; they were simply never seen.

### they landed while the gate was dark, which is the point | `.importlinter`

The layering gate had been aborting on a stale exemption and evaluating **0 of 10** contracts. A gate that reports zero contracts is indistinguishable at a glance from a gate that reports no violations, and in that window a dependency the architecture explicitly forbids entered the CLI's two most operator-facing modelo verbs. This is the concrete cost of the dead gate, not a hypothetical one.

### the coupling is real, not incidental | `_modelo_work_select_cli.py:38`

`_run_select_destination` calls `ModeloWorkSelectApp(units).run()` and returns the chosen work-unit id; `_run_workspace_destination_for_selected_unit` calls `admit_workspace_session` and returns the workspace's refusal condition. Both consume an in-process RETURN VALUE from the TUI. Any remedy has to replace that value channel, so this is not an import that can simply be deleted.

## Recommendations

1. Treat this as a breach to remove, not a carve-out to grant. D11 is a ruled decision and the operator has confirmed the direction is never acceptable. **Do NOT resolve it by adding a `cli -> tui` exemption to `.importlinter`** -- that would launder the violation through the gate that just caught it, one tick after the gate was restored.

2. Use the remedy D11 already names: **out-of-process execution**. The CLI may spawn the TUI as a separate process; it may not import it. That requires replacing two in-process return values with a process-boundary channel -- the selected work-unit id, and the workspace admission refusal condition -- so the shape is a small typed exit contract, not a redesign.

3. Decide the seam with the TUI lane rather than unilaterally. The CLI side is the caller and the TUI side owns `ScreenHostApp`, `routes` and `view.controller`; the exit contract belongs to whichever side the ADR's authors intended to own the launcher. This audit deliberately does not choose.

4. Add a contract or exemption-free assertion that keeps `cli -> tui` at zero once removed, so the direction cannot re-enter the next time the gate is quiet.

5. Read the other 58 production violations the restored gate reports before treating this one as isolated. It is the clearest breach, not necessarily the only ruled one -- `application.ledger` reaches `adapters.persistence` widely, and `llm` and `application.ledger` import each other in both directions.
