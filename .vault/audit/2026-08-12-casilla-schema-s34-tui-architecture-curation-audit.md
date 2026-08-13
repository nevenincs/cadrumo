---
tags:
  - '#audit'
  - '#casilla-schema'
date: '2026-08-12'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:f041e8a2564677c5a280357d618ee8af0cd8fce7cbd2cd4e148b286a4d3a492c'
related:
  - "[[2026-08-11-tui-interface-adr]]"
  - "[[2026-08-11-tui-architecture-adr]]"
  - "[[2026-08-10-casilla-schema-read-model-adr]]"
  - "[[2026-08-10-casilla-schema-plan]]"
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-11-tui-interface-plan]]"
  - "[[2026-08-12-casilla-schema-s34-tui-review-audit]]"
  - "[[2026-08-10-casilla-schema-W04-P10-S34]]"
---
# `casilla-schema` audit: `S34 TUI architecture lifecycle reconciliation`

## Scope

Focused curation of the apparent conflict among the accepted `2026-08-11-tui-interface-adr`, accepted `2026-08-11-tui-architecture-adr`, accepted `2026-08-10-casilla-schema-read-model-adr`, the casilla-schema S34/S35 plan rows, the blocked TUI architecture and interface plans, commit `0c5fb5253d`, its S34 execution record, and `2026-08-12-casilla-schema-s34-tui-review-audit`. This audit adjudicates authority and lifecycle only. It changes no ADR, plan row, execution record, production code, test, locale, or Git state.

The evidence pass used semantic search over the ADR, plan, audit, research, and code corpora, full reads of the governing records, targeted source and history confirmation, `vaultspec-core status` for all three features, and graph/frontmatter inspection for status and supersession. All three governing ADRs are `accepted`; none carries `supersedes` or `superseded_by` for another record in this cluster.

## Findings

### authority-ordering | resolved | The accepted decisions govern the target while their explicit dependency order governs the transition

The read-model ADR owns `ModeloWorkReview` in `application.modelo` and makes the TUI a read-only consumer. The TUI architecture ADR is topology authority for the final state: `cadrumo.entrypoints.tui` is the exclusive production Textual root, `modelo.view` is the reserved destination, and the legacy inbound package must ultimately be deleted without a compatibility facade. The TUI interface ADR adopts that topology but also supplies the narrower sequencing rule: casilla-schema closes first and records the review screen it produced; only afterward does the blocked TUI architecture campaign absorb that screen into `cadrumo.entrypoints.tui.modelo.view`, close legacy identity, and produce the receipt required by the downstream interface campaign.

Plans implement those accepted decisions; execution records report what happened; audits find and recommend. Therefore an audit cannot override the ADRs' explicit sequence, and a target-state prohibition cannot be read in isolation from the same accepted cluster's ordered migration contract.

### locator-classification | major | S34 and S35 name an intentional transitional source, not a stale canonical locator

The S34 and S35 rows predate the TUI records, but the later accepted interface ADR directly links the casilla plan and expressly requires the casilla campaign to finish before TUI architecture starts. The TUI architecture plan is currently `0/103` and blocked on casilla-schema; the interface plan is `0/33` and blocked on both predecessors. The migration manifest is generated only at TUI architecture S01, after casilla closure, so S34/S35 become input to that initial inventory rather than a new identity added after the manifest freezes.

The legacy path is not the canonical destination. It is nevertheless the only sequencing-compatible delivery location before the architecture campaign opens. Relocating now would start blocked TUI architecture implementation early; deleting now would discard the delivered review behavior and prevent the casilla dependency from closing.

### audit-fork | major | The S34 review audit's placement recommendation conflicts with the accepted transition sequence

The S34 review audit correctly identifies the final root and correctly keeps S34 open for lossy finding rendering, responsive proof, and S35-control regression coverage. Its `legacy-tui-placement` finding becomes incorrect when it concludes that S34 cannot close solely because the screen is temporarily in the legacy package and recommends immediate relocation. That conclusion omits the accepted dependency order and the explicit later absorption requirement.

This is a lifecycle fork in an audit finding, not an ADR contradiction and not authority to change the plan. Preserve the earlier audit as historical review evidence; this curation audit narrows its placement recommendation. The three non-placement findings remain open and unchanged.

### plan-gap | major | The TUI architecture plan lacks the explicit Modelo migration row required for a valid receipt

The accepted interface ADR says the architecture receipt is invalid unless the architecture authority and plan explicitly add and close migration of the casilla review screen to `cadrumo.entrypoints.tui.modelo.view`. The current TUI architecture plan has generic relocation, manifest closure, legacy deletion, and final review rows, but no explicit Modelo screen/filter migration row. The downstream interface plan already assumes a landed canonical Modelo view and only later extends it.

This is the actionable lifecycle gap. It does not justify editing casilla S34/S35 or moving code before the dependency gate opens.

### decision-versus-code | deferred-by-authority | Commit 0c5fb5253d is transitional drift with an accepted removal path

Commit `0c5fb5253d` adds the read-only screen, tests, facade exports, and locales under `cadrumo.adapters.inbound.tui`. That location violates the final topology but is covered by the accepted two-campaign migration sequence. It must not survive TUI architecture closure. Until then, the screen may be repaired and S35 added in the same transitional owner, provided no compatibility facade or second implementation is created.

## Recommendations

1. Keep casilla-schema S34 and S35 in place. Do not remove or retire them: the accepted dependency chain requires casilla-schema to deliver and close before TUI architecture may begin. Do not replace or silently edit their scope locators, because that would erase the transitional history and start blocked architecture work. Do not append duplicate casilla steps for the canonical package.
2. Keep S34 open until the three still-valid review findings are resolved: localized finding text plus `expectation_id`, real rendered-frame/navigation responsive proof, and structural exclusion of premature S35/mutation controls. Then close S34 normally in its transitional scope. Execute and close S35 there before casilla S40, so the complete surface enters the migration census once.
3. With author approval, amend the TUI architecture authority only as needed to make its already-required Modelo absorption explicit, without changing the accepted target or sequence. Through the plan-owning CLI, insert one new TUI architecture step before relocation parity/legacy deletion: move the complete S34/S35 Modelo review surface and its tests to `src/cadrumo/entrypoints/tui/modelo/view`, consume only public `application.modelo.ModeloWorkReview`, preserve behavior and named-outlier evidence, and remove the legacy exports/files in the same consumer-complete change without a shim. The new immutable step id should be whatever the CLI allocates; do not reuse or renumber existing ids.
4. Make the new migration step a prerequisite of migration-manifest closure S88, legacy deletion S89, fixed-point gates S102, and final review S103. S89 remains the package-wide deletion proof; the inserted step is the explicit destination/parity proof required by the interface ADR's receipt.
5. Do not delete or relocate commit `0c5fb5253d` now. Defer physical relocation to the newly explicit TUI architecture step after casilla S40 closes and the architecture dependency gate opens. If the owner rejects transitional delivery, that is a judgment change to the accepted sequencing and requires an ADR amendment before any plan or code action.
6. Treat `legacy-tui-placement` in `2026-08-12-casilla-schema-s34-tui-review-audit` as corrected by this audit. Retain its other findings and its overall FAIL until those functional/proof defects are resolved; placement alone is not a valid blocker under the accepted sequence.

## Retirement note, 2026-08-13

The owner ruled that no TUI campaign will land. Three of the six recommendations above, and one finding, are retired by that ruling; the rest stand.

**Retired: the `plan-gap` finding, and recommendations 3, 4 and 5.** All four are instructions to the `tui-architecture` authority and plan - amend the ADR to make Modelo absorption explicit, insert a migration step before relocation parity and legacy deletion, make it a prerequisite of S88/S89/S102/S103, and defer physical relocation until after casilla S40 opens the dependency gate. None of them has an executing campaign, so they are retired rather than carried as open items that no one owns. Recommendation 3's condition ("with author approval") was never met and is now moot.

**Stood down as satisfied: recommendations 1, 2 and 6.** S34 and S35 stayed in place, were executed and closed in their transitional scope, and the `legacy-tui-placement` finding of `2026-08-12-casilla-schema-s34-tui-review-audit` remains corrected by this audit.

**Superseded in premise, retained as history: `locator-classification` and `decision-versus-code`.** Both classified the legacy path as an *intentional transitional source* pending later absorption. The classification was correct when written and is preserved as the record of why the screen shipped there, but its premise no longer holds: the placement is permanent. That is ruled in the amendment to `2026-08-10-casilla-schema-read-model-adr` dated 2026-08-13, which is the authority for the screen's home. The sentence in `decision-versus-code` that commit `0c5fb5253d` "must not survive TUI architecture closure" is void, not pending.

**`authority-ordering` stands unchanged.** Its reasoning - that an audit cannot override an accepted cluster's explicit dependency order - was never contingent on the order being executed.
