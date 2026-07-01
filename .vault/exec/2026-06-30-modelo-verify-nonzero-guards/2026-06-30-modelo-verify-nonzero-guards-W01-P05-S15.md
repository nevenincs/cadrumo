---
tags:
  - '#exec'
  - '#modelo-verify-nonzero-guards'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S15'
related:
  - "[[2026-06-30-modelo-verify-nonzero-guards-plan]]"
---

# Append the modelo-210-2025-rendimientos-integros-implica-base-imponible ADVISORY predicate implies_nonzero(["rendimientos_integros", "base_imponible"]) with legal_refs trlirnr-rdleg-5-2004:art-24 to the existing 2025 verification_predicates.toml, leaving the representante-fiscal predicate untouched

## Scope

- `src/aeat/_data/registry/aeat/modelos/210/revisions/2025/verification_expectations/0001-verification_predicates.toml`

## Description

- Confirmed no peer WIP in the M210 registry path via `git status --short` and `git diff` before editing.
- Confirmed `rendimientos_integros` (manual, required, money) and `base_imponible` (computed via `m210_resolve_base_imponible`) casillas exist in `casillas/0001-casillas.toml`, and that `trlirnr-rdleg-5-2004:art-24` already resolves in `irnr.toml` with a reviewed BOE corpus citation.
- Appended a second `[[revisions."2025".verification_predicates]]` array entry to `0001-verification_predicates.toml`: `predicate_id = "modelo-210-2025-rendimientos-integros-implica-base-imponible"`, `expression = 'implies_nonzero(["rendimientos_integros", "base_imponible"])'`, `finding_kind = "ADVISORY"`, `legal_refs = ["trlirnr-rdleg-5-2004:art-24"]`.
- Left the pre-existing `m210-representante-fiscal-required` BLOCKING_RULE predicate (lines 12-16) byte-identical; only appended below it in the same file, per the registry-revision-content-inline-or-fragmented convention this file already follows (inline declaration).
- Added an explanatory comment block grounding the ADVISORY severity choice (formula-defended consequent, but a legitimately zero base on the general/UE-EEE branch via a full art 24.6 expense offset is not ruled out) and explicitly scoping out the inmobiliaria branch (deferred to Wave W02 Phase P07, no DSL support for categorical-equality predicates yet).
- Added the locale leaf `application.modelo.findings.modelo_210_2025_rendimientos_integros_implica_base_imponible` to all four locales (en, es, ca, hu) via `python -m aeat.locales set`, matching the M131/M200 advisory-message convention; confirmed via `python -m aeat.locales audit` that the new key carries no missing/extra drift in any locale.

## Outcome

The 2025 revision's `verification_predicates` array now carries two predicates: the untouched representante-fiscal BLOCKING_RULE gate and the new base-imponible ADVISORY guard. The registry loads and validates cleanly (confirmed by the S16/S17 test runs). Locale parity holds for the new finding key across all four shipped locales.

## Notes

The locale-audit run surfaced one pre-existing, unrelated drift item (`cli.app.modelo.work.revision_verbose_help` missing in all four locales) that predates this change and is out of this Step's scope.

Two shared-worktree races were observed and handled per the worktree-safety discipline, neither requiring any destructive git operation: (1) a concurrent `python -m aeat.locales set` (or `scaffold`) invocation by another agent overwrote the freshly-set locale leaf in all four files via a lost-update race before it was staged; detected via a follow-up `grep`, re-applied the same four `set` calls, and re-verified presence immediately. (2) After staging this Step's authored files, a peer agent's `git commit` (custody-resolver-imports fix) ran without a pathspec while this Step's files sat staged in the shared index, sweeping them into that peer's commit `bdc8d0a64`. Per `uncommitted-wip-is-not-orphaned`, this is a documented shared-index hazard, not data loss; verified via `git show bdc8d0a64 --stat` and per-file content diff that every one of this Step's five files (the TOML predicate, both new/extended test files, and the three exec records) landed byte-identical to the staged content, with zero foreign-content interleaving. No destructive git command was run to investigate or remediate either incident.
