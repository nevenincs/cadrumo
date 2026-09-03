---
tags:
  - '#audit'
  - '#code-duplication'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:67ac153dfb75ac4e691911c7a9e4977b265f17713103e324dfe730c595101c04'
related: []
---
# `code-duplication` audit: `ledger invoice lifecycle command specification consolidation`

## Scope

Reviewed committed change `699d3df4d7`, which replaces repeated frozen `ArgumentSpec` and `OptionSpec` construction within the ledger invoice lifecycle command declarations with shared records and adds an exact lifecycle contract test. The audit compared every shared field and insertion offset against the parent commit; checked frozen-record and tuple immutability; compared the resulting declarations with the ledger invoice intake surface; and ran the focused test, Ruff, `ty`, and the repository-owned duplication audit.

## Findings

### cross-file-invoice-parameter-authority | high | The consolidation leaves the canonical cross-file family duplicated

The seven lifecycle metadata options (`operation_type`, `operation_date`, `retention_rate`, `retention_amount`, `invoice_class`, `series`, and `rectifies_invoice_number`) are field-for-field equal and identically ordered in `invoice add` and `invoice update`, yet are distinct objects. The optional `iva_category` option is likewise equal but distinct. The whole-tree duplication audit reports 84 clones (0.41%) and identifies the same lifecycle/intake family as 123-, 81-, and 21-line cross-file clones. The new lifecycle-local constants make the first local reuse canonical but do not give the intake command the same authority, contrary to the single-canonical-definition boundary; future metadata changes can now drift across `add`, `update`, and `wizard`.

### lifecycle-contract | low | The committed lifecycle behavior is exactly preserved

The focused contract test projects every parameter field reaching the command runtime: kind, name, deferred annotation and hooks, choices, default kind and literal, help key, metavar, visibility, complete constraint tuple, transport, option declarations, flag behavior, cardinality, prompts, environment, eager state, and secret channels. It asserts the four affected command tuples in order. It also proves the shared records have exact identity, while `update` and `wizard` `notes` retain their distinct defaults (`None` versus empty string). The frozen `ArgumentSpec`, `OptionSpec`, nested contract records, and tuples make sharing immutable. The test oracle would reject field, declaration, default, help-key, ordering, or shared-identity mutations on the lifecycle surface, but it contains no intake-to-lifecycle identity assertion and thus cannot detect the remaining cross-file duplicate.

## Recommendations

Do not approve `699d3df4d7` as duplicate consolidation. Move only the fully substitutable `iva_category` and seven metadata declarations to one semantically named public invoice-command-parameter module and consume those exact records from intake and lifecycle. Extend the contract test to assert field equality, order, and identity across `add`, `update`, and `wizard`; retain command-specific records such as requiredness and placement of `counterparty_nif`, and the distinct `notes` defaults, as local declarations. Re-run the focused suite, Ruff, `ty`, and the whole-tree duplication audit after the canonicalization.
