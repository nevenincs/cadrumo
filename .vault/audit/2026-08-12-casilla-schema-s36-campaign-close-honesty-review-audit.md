---
tags:
  - '#audit'
  - '#casilla-schema'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:f34b8540df493cadd26af9af1251c20dfce2f668d0a4b521c0d342d1ef729e34'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
  - "[[2026-08-10-casilla-schema-blocker-spine-adr]]"
  - "[[2026-08-10-casilla-schema-canonical-derivations-adr]]"
  - "[[2026-08-10-casilla-schema-dead-surface-adr]]"
  - "[[2026-08-10-casilla-schema-read-model-adr]]"
---

# `casilla-schema` audit: `S36 campaign-close honesty review`

## Scope

Fresh-context campaign-close review begun at HEAD `3ec74d02ae` and rechecked after concurrent unrelated commits at final HEAD `84d84714ad` against all 42 live plan rows, the 39 checked execution records, 38 earlier feature audits, the generated feature index, the four locale catalogues, Git history, and the four accepted decisions: "canonical registry derivations for joins, relation consumption and official boxes", "an operator action spine over the blocker vocabularies", "one modelo work review read-model in application/modelo", and "delete or wire the dead verification surfaces". Discovery began with independent semantic code and vault searches for the complete campaign, its accepted ADR cluster, plan, executions, audits, read model, TUI, deletions, derivations, and blocker spine; exact declarations, consumers, tests, and history were then confirmed with targeted searches and whole-file reads.

Lifecycle accounting is internally coherent but not complete: `vaultspec-core status casilla-schema` reports 39/42, every checked Step has a matching execution record, S36 is next, and S39/S40 remain open. Earlier FAIL audits were followed through their appended resolutions; S24, S30, S34, S35, S38, S41, and S80 all carry final PASS dispositions. The only pre-review dirty path was an unrelated unstructured-document-ingestion ADR and was preserved. This review changed no production, test, locale, plan, generated index, Git index, or commit state.

## Findings

### spanish-casilla-stem | high | The campaign introduced an English alias family for the AEAT casilla concept

`src/cadrumo/core/_official_box_status.py:8` declares `OfficialBoxStatus`; `src/cadrumo/domain/calculations/registry/_export.py:183` declares `classify_official_boxes`; `src/cadrumo/application/modelo/_work_review.py:150` persists `official_box_status`; and the TUI consumes the same English-named field. These are not generic UI boxes: their own definitions classify how a registry casilla is represented by an official AEAT export surface. The always-on naming authority predates the landing and requires the Spanish `casilla` stem for concepts mapping one-to-one to AEAT surfaces, explicitly forbidding English `Box` aliases. The canonical implementation is otherwise singular and facade-correct, so this is a destructive rename and consumer sweep, not a reason to add an alias.

### m303-revision-split-regression | high | The campaign's M303 restructure left its end-to-end calculation chain pinned to a deleted revision

`src/cadrumo/application/modelo/tests/test_e2e_ledger_m303_quarters_to_m390_annual.py:109` fixes `_M303_REVISION` to `2023-y-siguientes`, and line 508 passes it to the real work-unit creation path. The validated M303 authority now declares `2023`, the two split 2024 revisions, `2025`, and `2026-y-siguientes`; the retired id is correctly refused. The exact real persisted-repository module therefore fails all four tests before calculation. This is campaign-owned: S02 made the split the measurement basis, while S10's execution record already disclosed the stale deleted id and left it red. A campaign cannot close with its M303-to-M390 end-to-end chain disabled by its own revision migration.

### retired-verification-locales | high | Dead application-verification locale leaves survived the deletion campaign

The locale authority reports `application.verification.errors.missing_binding_values`, `period_mapping_failed`, `registry_policy_invalid`, `registry_snapshot_invalid`, and `registry_snapshot_ref_mismatch` as extra in all four catalogues. Concrete residues start at `src/cadrumo/locales/en.yml:1308`, `es.yml:1478`, `ca.yml:1429`, and `hu.yml:1353`. S30 correctly deleted the application package, tests, registry consumer rows, and one separately reviewed orphan error leaf, but these five families still name the deleted package and have no live codebase key. Under the accepted dead-surface ADR and no-legacy rule they must be removed through `dev.locales`, not retained as dormant compatibility prose.

### stale-relation-applicability-counts | medium | A known exact-count gate is red and violates the standing quality rule

`src/cadrumo/domain/calculations/registry/tests/test_relation_handoff_inventory.py:108-114` hard-codes the full applicability population and its partitions. The exact owning lane now returns 156 rows instead of 108: 19 tests pass and this one fails. S13's execution record explicitly called it unrelated to S13 behavior and left it red, but it is inside the campaign's relation-handoff owner surface and the standing goal forbids exact counts as pass conditions. Replace the corpus tallies with invariant/property assertions and retain the measured distribution only as execution evidence.

### generated-feature-index | medium | The generated casilla-schema index is radically stale

The feature-scoped VaultSpec check reports that `casilla-schema.index` has six related links while the feature now has 85 documents. The index still links only the original research, plan, and four ADRs, omitting every execution and audit produced by the campaign. This is generated output owned by `vaultspec-core vault feature index`, so it must be regenerated through that verb after the final P11 and S36 artifacts settle; hand editing is forbidden.

### iva-stem-gate-prose | medium | Two S33 audit sentences make the campaign fail the IVA stem gate

`2026-08-12-casilla-schema-s33-readiness-mapping-audit` lines 41 and 63 use the duplicated phrase `IVA/IVA` while describing the absence of such drift. The exact Spanish-stem gate passes four nodes and fails its authored-repository-prose node on only those two campaign-owned lines. Correct the sentences through the VaultSpec CLI so the audit states the same conclusion without reproducing the prohibited token.

### s02-empty-description | low | A checked execution record remains structurally incomplete

The feature-scoped body-section check reports `2026-08-10-casilla-schema-W01-P01-S02` with an empty required `## Description`. Its extensive Outcome and Notes provide the evidence, but the attested body schema requires the section and campaign-close accounting must not carry a checked record that still fails its own structural contract.

## Recommendations

1. Append one P11 Step to rename the complete `OfficialBoxStatus` / `official_box_status` / `classify_official_boxes` family to a Spanish `casilla`-stem authority, sweep every production/test/locale consumer atomically, and prove the English names have zero references. Delete the old names; add no alias or compatibility export.
2. Append one P11 Step to make the real M303 quarterly-to-M390 annual end-to-end suite resolve the law-selected split revision for each filing year/period, then run all four tests green. Do not restore the deleted revision token or add tolerance for it.
3. Append one P11 Step to remove the five retired `application.verification.errors.*` leaves from all four catalogues through `dev.locales`, and require `dev.locales scaffold --check` to show none of those keys as extra. Record remaining unrelated profile and IVA-wallet catalogue debt separately.
4. Append one P11 Step to replace the relation-handoff applicability count assertions with count-free semantic invariants, include a bite proof, and make the complete owning module green.
5. Append one P11 Step to correct the two S33 audit sentences through the VaultSpec CLI, then require the IVA-stem gate to pass.
6. Append one P11 Step to fill S02's Description through the VaultSpec CLI, then require the feature-scoped body-section check to pass.
7. Append one final P11 Step, ordered after all other close findings and before S36 re-review, to regenerate `casilla-schema.index` through `vaultspec-core vault feature index -f casilla-schema` and require the feature check to pass.
8. Re-run S36 only after every appended Step has a checked execution record and a verified resolution. S39 may then retire the campaign rule, and S40 may declare structural completeness only if the exact full tracked-suite collection, focused behavior lanes, locale/stem checks, feature-scoped VaultSpec checks, and accepted-decision reconciliation all pass.

Verdict: **FAIL / CHANGES REQUIRED**. The canonical derivations, action spine, read model, TUI behavior, and destructive dead-code removal are substantially delivered and structurally singular, and the full tracked-suite collection passes. Campaign closure is not honest while seven actionable findings remain. Each finding above requires an appended P11 Step; none is formally deferred by accepted authority.

## Verification

- Full tracked-suite serial collection: `uv run --no-sync pytest src dev packaging --collect-only -q -n 0 --override-ini=addopts=` exited zero in 107.9 seconds.
- Focused derivation/spine lane: 19 passed, 1 failed; the sole failure is the stale relation applicability count (`108` expected, `156` current).
- M303-to-M390 real persistence/export lane: 4 failed, all on refusal of deleted M303 revision `2023-y-siguientes` before calculation.
- Spanish IVA-stem gate: 4 passed, 1 failed on the two S33 audit sentences.
- Locale scaffold check: red on the five retired verification keys in all four catalogues plus unrelated profile, IVA-wallet, dependency-help, and ledger debt. The S34/S35 locale namespaces were previously independently proven complete.
- Import-hygiene scan: zero production cross-package private imports, zero shim modules, zero underscore-named public exports, and zero shipped reaches into `dev`.
- Scoped Ruff and BasedPyright over the canonical official-representation/read-model surfaces: clean, with zero type diagnostics.
- Plan check: structurally valid with only the intentional non-monotonic retired-id warning. Feature exec mapping and modified stamps are clean.
- Feature body sections: only the pre-existing S02 Description plus the newly scaffolded S36 documents before authorship. Feature index check: stale at six links versus 85 documents.
- Repository-wide VaultSpec check exited zero but reported broad unrelated vault debt; the campaign-owned findings are isolated above rather than conflated with that tree-wide backlog.
