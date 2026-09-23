# ASSETS-01 implementation checkpoint

Updated: 2026-09-23
Status: AS1-AS12 proven; the 2025 amortization method set is implemented and
installed-proven at `0d34b1534a`. Outcome, commits, checks, identities and remaining
targets are in `2026-09-23-assets-amortization-method-set-handoff.md`.

## Session identity

- Brief: ASSETS-01 revision 0.1
- Policy: session-policy revision 1.6
- Acceptance pattern: ACCEPTANCE-01 revision 1.3
- Provider: OpenAI
- Lead model: GPT-5
- cc number and session UUID: pending user provision; not invented
- Lead: `/root`
- Worktree: `Y:/code/cadrumo-worktrees/tui-modelo`
- Branch: `tui/modelo`
- P01.S02 implementation commit: `d50d31373a`
- P01.S02 ledger-format correction: `33b7c8492d`
- P02 schedule/persistence commit: `0ce2eb2588`
- P03 live resolver commit: `44bafa1c15`
- P04 reciprocal IVA linkage commit: `55a2db2be2`
- P05 shared CLI/TUI operations commit: `d155360719`
- AS7 free-depreciation implementation commit: `5b0d03887a`
- IVA readiness/source-mesh repair commit: `d7fa2d1d33`
- TUI operation parity commits: `2a15e04fe5`, `b08f1b79a8`
- Strict CLI payload commit: `3ed255ad7a`
- Installed export acceptance commit: `aea0c84f74`
- Installed TUI continuation acceptance commit: `c207d15e1d`
- Brief source anchor: `b5920969129a85b22c448fc8cdd6ae6c8d468a11`

## Goal and acceptance state

P02 provides immutable acquisition/revision linkage, typed allocation stages,
2025 normal and simplified material/intangible authority tables, exact Decimal
day-prorated schedules, idempotent and superseding claim history, and encrypted
CAS-guarded persistence with restart reconstruction. The pre-change EUR 2,000
full-cost regression is retained as pre-repair evidence. P03 resolves authority by exact registry key,
injects encrypted history into the live M100/M130 source mesh, preserves ordinary
expenses, separates material/intangible destinations, and refuses the matching
full-cost ledger deduction. P04 adds reciprocal canonical IVA linkage without
coupling the stores. P05 exposes shared create, inspect, correct, forecast, claim,
and filing-handoff operations through CLI and TUI without frontend arithmetic.
The current matrix is AS1-AS12 proven. Installed TUI-to-CLI and CLI-to-TUI
continuations completed over separate encrypted stores, and the asset-derived
Modelo 100 artifact passed the pinned official 2025 XSD.

## Discovery and decision coverage

- `assets-discovery` (Luna Max) completed the required bounded delta from the brief
  anchor to current HEAD. The sole committed delta adds Retenciones vault documents;
  no ASSETS-01 production owner or contract changed.
- Relevant uncommitted changes are owned by the income/shared-export session. They
  affect `dev/acceptance/income_tax/**`, filing export/verification, registry export
  schema/provenance, packaging authority build behavior, and one M130-to-M100 test.
  They do not implement an asset register, schedule, history, or frontend surface.
- Accepted `2026-08-23-amortization-casilla-mapping-adr` governs the IRPF activity
  slice. It requires one atomic 2025 material/intangible asset authority with legally
  sufficient acquisition, schedule calculation, secure persistence, resolver
  ownership, duplicate-authority refusal, provenance, diagnostics, and filing path.
  It forbids partial scalar asset storage and forbids treating IVA bienes-inversion
  or transaction amortization categories as the IRPF schedule authority.
- Accepted `2026-07-01-iva-bienes-inversion-regularizacion-adr` keeps the IVA
  investment-goods register and its reciprocal acquisition identity as a distinct
  legal and calculation boundary.
- Semantic ADR search returned no indexed match and the GPU service could not start;
  the permitted local fallback also returned no match. Targeted ADR filename
  confirmation surfaced the two accepted decisions above.

## Ownership and constraints

- This assets session owns the new defining IRPF asset modules, asset authority,
  application operations, persistence adapter, resolver, owning tests, CLI/TUI
  projections, and asset acceptance scenarios under the approved plan.
- Existing dirty files are preserved as other contributors' work. Shared income,
  authority, export, registry, and packaging surfaces are unavailable for unilateral
  edits until the coordinator assigns ownership.
- No new universal ledger, duplicate calculator, tax table, plaintext asset store,
  CLI-to-TUI import, or frontend-local arithmetic may be introduced.
- Latest completed year remains 2025 and is resolved programmatically from the
  published authority capability. Filing-grade support is claimed only for the
  validated 2025 paths recorded below.

## Final integrated evidence

The administrative dispatch gate was superseded by the user's assets-core
implementation authorization. The lifecycle ADR and its accepted cost-basis
stage amendment govern the persisted contract. Phases P02 and P03 passed integrated
review with no critical or high findings. Focused P02 verification: 20 tests passed;
Ruff, `ty`, BasedPyright and diff hygiene passed; the full authoring-candidate
inspection passed 2 integration tests. One shared namespace-order test still
fails after the assets entry because the concurrent income lane has not added its
already-enrolled `withholding_workflow` key to the expected tuple. P03 lead checks
passed 11 asset resolver/source-mesh tests and 44 surrounding regressions. P04.S07
passed four focused linkage tests. P05 lead checks passed 11 focused shared-operation,
CLI, TUI, and evidence tests plus Ruff, `ty`, BasedPyright, and diff hygiene. The
installed wheel exposes the complete `actividad-asset` command group and imports
from site-packages. The final installed authority is logical generation
`065049eb22e4a46f70281b940b5ce9ffeb2564adce39e050665d6fa370f21a98`
with database SHA-256
`fc63cb9dcf7162cc19a2855a6e6040068f0bd9706be6595b079dcc07d706f462`;
the focused asset authority/runtime suite passed 10 tests against it.

The installed export journey recorded one EUR 300 claim, calculated M130 Q4
income EUR 12,000 and expenses EUR 2,700 (EUR 2,400 control plus the claim),
populated M100 material amortization EUR 300 and intangible amortization EUR 0,
and produced a 2,490-byte XML artifact that passed the pinned official 2025 XSD
without errors. Its XML SHA-256 is
`f3dab3814c905cba8038fa902f6ce5d42c1d59a440747430c827ea0a27dc596a`.

The installed TUI lifecycle completed public setup, creation, inspection,
correction, forecast, initial claim, idempotent replay, filing handoff and clean
exit. A fresh TUI process reconstructed the history; installed CLI continuation
then inspected two revisions and returned EUR 180 material M100/M130 projections.
The reverse scenario created one revision through installed CLI and a fresh TUI
process read it back with the canonical revision identity. Neither scenario timed
out or required forced cleanup. The repaired live IVA source-mesh fixture resolves
casilla 43 to EUR 200 and retains the negative incomplete-profile refusal.
