---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-17'
body_hash: 'sha256:20364c4e4b3e39cbe506062b4b4e52d23c58618654fc1d9f03f9c5a6d290d6c5'
step_id: 'S79'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-07-10-cross-domain-continuity-audit]]"
---

# re-run Marc autonomo IT and fresh persona reaching work verify confirm verificado_completo refused on empty drafts

## Scope

- `.vault/audit/`

## Description

- Re-ran the Marc autónomo and fresh S.A. personas through the shipped CLI in separate encrypted stores.
- Probed empty work verification before each calculation, then supplied declarative profile facts and populated calculation inputs through CLI flags.
- Exercised the ledger period grammar, empty-ledger commands, Modelo work-list localisation, and Modelo 349 applicability surface for Marc.
- Captured every refusal, granted verification, and unhandled workflow boundary outcome in the target audit.

## Outcome

Marc's empty Modelo 130 work unit refused verification because it had no selectable calculation revision. A populated draft then persisted with revision `d82fe1d6e3631c6f30f5ad15cc41d61c334d6096a9b7d0f851d9f00e325ba022`. After the operator declared an activity-start date of 2026-01-01, verification completed with `granted_verificado_completo=true`; the only remaining result was a pre-activity advisory.

The canonical ledger period grammar is healthy: `2026T1` is refused with Catalan guidance to use `1T` plus `--year`, and the `1T` dry run succeeds. Empty-ledger classify and view are structured refusals and list returns an explicit empty collection. Marc's normal work-list rendering uses the Catalan `Esborrany` state. Modelo 349 remains informationally incomplete because the profile does not declare intracommunity operations.

The fresh S.A. also refused empty work verification and saved populated Modelo 200 revision `f19c84f4273f6f6ed5c6fbcd5de0ffb4770b16dbc27340dc2fca2ea69157301d` from a 100,000 base plus the required legal-entity facts. It could not be granted verified-complete because relation evidence for the preceding Modelo 200 and 202 filings is absent. After changing the profile start date, verification leaked a full internal traceback before returning `REFUSED_MODELO_WORKFLOW_GATE` with `UNHANDLED_EXCEPTION` for the unsupplied Modelo 202 relation. This is retained as a blocker rather than treating the final refusal as a successful verification result.

## Notes

- No source, registry, test, or plan-row changes were made.
- The historical bare `00562` instruction is no longer safe as written: the current CLI catalog exposes both a manual `DP200010:00562` and a computed `DP200014:00562`. The latter is the cuota íntegra, so this run supplied the unambiguous `00501` base and did not inject the unrelated manual field.
- The S.A. blocker is a real profile-drift journey: changing a legitimate declaration fact after the calculation must fail through the normal CLI boundary without emitting an internal traceback.
