---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-10'
body_hash: 'sha256:2f6783c780f00c3f82e5cdba5fcff5102575ef98b518342b73119919ab4582d0'
step_id: 'S147'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# re-run Catalan-preferring and Hungarian-preferring personas verify no message in wrong language

## Scope

- `.vault/audit/`

## Description

- Recovered the deferred operating brief with `vaultspec-rag`: Hungarian output for the Wave-8 modelo-error keys and the registered `config auth clear`, profile-show, and modelo work command surfaces is the retained S147 target.
- Created independent Catalan and Hungarian personas in fresh `AEAT_LOCAL_STORAGE_ROOT` stores. Each used a natural-person, economic-activity profile and the applicable Modelo 130 2026/1T work route.
- Ran `aeat --language ca` and `aeat --language hu` through profile create, profile status, profile show, modelo work create, calculate, direct revision verify, list, and status; ran ledger list, classify, and invalid-id view; and ran `config auth clear`.
- Retried every parser-boundary probe through the supported root placement. The root option is `--language`; root-level `--output-language` is correctly refused with a pointer to `--language`, so that spelling was not counted as a locale-parity finding.
- Preserved the real calculation revisions and verification reports in their isolated stores only. Did not invoke `work file`, because the verified revision would advance to a filing state and this persona brief has no filing authority.

## Outcome

The required no-wrong-language parity result is not met.

### MAJOR | Parser boundary keeps English wrappers under selected Catalan and Hungarian

With the supported root commands `aeat --language ca ...` and `aeat --language hu ...`, a missing required `--modelo` option renders `Missing option '--modelo'.` in English. `ledger classify` without a transaction id and `ledger view missing-transaction` likewise retain the English `Invalid value:` wrapper before their Catalan or Hungarian inner message. The generated help instruction and error heading localize correctly; the wrapper does not.

### MAJOR | Modelo calculation and verification emit raw English and Spanish into Catalan and Hungarian journeys

Both Modelo 130 calculate runs render formula-detail tokens such as `subtract`, `max`, `percent`, and `if_then_else` in English. The otherwise Catalan and Hungarian saved-draft notice ends with the Spanish state value `borrador`.

Both direct verification runs grant `verificado_completo` and then render the advisory finding and next action entirely in English, including `cross-period dependency scoped out as no-prior-obligation` and `Confirm the recorded activity-start date is correct.` This is an operator-visible successful-workflow result, not an unsupported command spelling.

### PASS | Localized success path and empty ledger list work outside the leaking fields

Catalan and Hungarian profile creation, profile status/show, Modelo 130 work creation, work status, and empty-ledger list all completed through fresh encrypted stores with their human-facing headings and notices in the selected locale. `config auth clear` completed for both personas without human prose leakage.

## Notes

- The text renderer's stable schema labels and identifiers such as `operation`, `work_unit_id`, legal references, and formula identifiers were treated as machine-format contract fields, not translated prose. The English callable names, parser wrappers, verification advisory, action text, and Spanish `borrador` were treated as human-facing leakage.
- The Catalan calculation revision was `cbacd75d09b61e5dd1485d15c591c8d65be24630fe9697e7edce8f3b607ab621`; the Hungarian revision was `8747ec5998a22565d835ab5a3f182e44353b7f12ca05232cc8200e79c58b7e63`. Both completed verification with one English advisory.
- This record deliberately does not close S147. It supplies evidence for the parent audit/consolidation owner; no product code, plan row, or shared rolling audit was changed.
