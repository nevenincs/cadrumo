---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: 2026-05-28
modified: '2026-05-28'
step_id: S387
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-27-m210-irnr-full-engine-adr]]"
---

# `cross-domain-continuity` `W04.P19.S387` (M210 casilla skeleton — initial commit)

First-cut authoring of the Modelo 210 IRNR Phase 1 registry skeleton: manifest, 2025 revision frame, and the six-casilla base / rate / cuota chain for the general (TRLIRNR Art 25.1.a, 24%) and ue_residente (Art 25.1.f, 19%) tipos de renta. Initial commit landed with three latent issues that the companion S387.patch (7a270e4ed) addressed; both commits are documented separately for clarity.

Commit: `602b0cdfb`

- Created: `src/aeat/_data/registry/aeat/modelos/210/manifest.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/210/revisions/2025/revision.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/210/revisions/2025/casillas/0001-casillas.toml`

## Description

Manifest declares the M210 modelo at `tax_domain = "irnr"`, `cadence = "ad_hoc"`, `output_sensitivity = "financial"`, with the five TRLIRNR legal anchors landed by S399 (Arts 2, 10, 24, 25.1.a, 25.1.f) wired through `legal_refs`. `source_refs` points at the `aeat-modelo-210-procedure` source descriptor.

2025 revision declares the period selector as `{ years = [2025], periods = ["evento"] }` (M210 is event-driven, not calendar-cadenced), bound `valid_from = 2025-01-01` / `valid_to = 2025-12-31`, and forwards the four substantive legal anchors (Arts 24, 25.1.a, 25.1.f).

Casillas TOML defines the six-casilla skeleton implementing the base / rate / cuota chain:

- `tipo_renta` (text, semantic_role = irnr_tipo_renta) — operator declares the income type.
- `rendimientos_integros` (money, Art 24 base imponible).
- Three more casillas covering the rate selection, cuota integra, and pagos a cuenta surface in the canonical Phase 1 chain.
- Cuota diferencial as the final settlement casilla.

Header comment on the casillas TOML explicitly records the Phase 1 scope: only the general (Art 25.1.a, 24%) and ue_residente (Art 25.1.f, 19%) variants are covered. The remaining tipos de renta (pension under Art 25.1.b, inmobiliaria under Art 25.2, ganancia patrimonial under Art 25.3, pagos a cuenta under Art 25.5) are Phase 2 scope per the m210-irnr-full-engine ADR §D2.3 and the M210 Phase 2 engine plan W01.

Phase 1 ships every casilla with `input_kind = "manual"` because the formula registry is NOT authored yet. S388 lands the formula TOMLs (base = rendimientos_integros for Art 25.1.a; tipo_gravamen = bracket-table lookup; cuota_integra = base × rate; cuota_diferencial = cuota_integra − pagos a cuenta). Until S388 ships, every casilla currently flagged manual flips back to `input_kind = "computed"` with its formula id wired through. While the manual-input shape stays, the M210 work-create surface keeps the Path-B refusal stub per ADR §D5.

## Three latent issues addressed by S387.patch (7a270e4ed)

The initial commit landed without the workbook_parity_refs and application_links files, and without correctly handling the manual-input fallback at the loader boundary. The companion S387.patch (7a270e4ed) addressed all three; that record carries the patch detail.

## WIP-absorption incident

The S387 initial commit was authored with a `git commit -m "msg"` without an explicit pathspec. The staging index at commit time held this S387 work plus the S385b plan-edit WIP from the cross-domain-continuity #258 deferred-work scoping note, and the commit absorbed both. Net effect was benign (the absorbed S385b plan edit was the most useful in-flight WIP at the moment), but the absorption was unintentional and represents the failure mode documented in memory rule `explicit_path_staging_in_parallel_worktree`. Standing rule reaffirmed: every commit in this shared worktree MUST use `git commit -m "msg" -- <explicit-pathspec>`.

## Gate evidence

- G1 no naked env reads: unchanged.
- G2 typed pydantic at boundary: TOML rows are schema-validated at registry load; the loader is the typed boundary.
- G3 user messages via tr(): N/A; registry authoring.
- G4 no locale yml hand-edits: unchanged.
- G5 no shims: Path-B refusal stub on the work-create surface is intentional defence-in-depth until the formula registry lands at S388.
- G6 no tautological tests: registry-authoring commit; no tests added in this commit (the patch commit added registry-load tests).

## References

- ADR: m210-irnr-full-engine (Phase 1 scope, D2 casilla chain, D5 manual-input + Path-B refusal posture).
- Companion: S387.patch at 7a270e4ed (registry-load fixes, workbook_parity + application_links).
- Sibling: S388 (deferred — formula TOMLs flipping manual → computed).
- Surface: `src/aeat/_data/registry/aeat/modelos/210/`.
