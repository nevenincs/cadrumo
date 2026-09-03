---
tags:
  - '#audit'
  - '#code-duplication'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:cc300b46e7395e300bf9608ba402d5963469afaa075b6d2a4ecb6c69f05d5ed3'
related: []
---
# `code-duplication` audit: `ledger invoice lifecycle command specification consolidation`

## Scope

Reviewed committed change `699d3df4d7`, which replaces repeated frozen `ArgumentSpec` and `OptionSpec` construction within the ledger invoice lifecycle command declarations with shared records and adds an exact lifecycle contract test. The audit compared every shared field and insertion offset against the parent commit; checked frozen-record and tuple immutability; compared the resulting declarations with the ledger invoice intake surface; and ran the focused test, Ruff, `ty`, and the repository-owned duplication audit.

Successor re-review covered `8e996268ca` and `b4c913ff31`: the new public common-parameter module, the live intake/lifecycle object identities, retained command-specific facts, the expanded exact contract test, type and lint gates, and the whole-tree duplication scan.

## Findings

### cross-file-invoice-parameter-authority | high | The consolidation leaves the canonical cross-file family duplicated

The seven lifecycle metadata options (`operation_type`, `operation_date`, `retention_rate`, `retention_amount`, `invoice_class`, `series`, and `rectifies_invoice_number`) are field-for-field equal and identically ordered in `invoice add` and `invoice update`, yet are distinct objects. The optional `iva_category` option is likewise equal but distinct. The whole-tree duplication audit reports 84 clones (0.41%) and identifies the same lifecycle/intake family as 123-, 81-, and 21-line cross-file clones. The new lifecycle-local constants make the first local reuse canonical but do not give the intake command the same authority, contrary to the single-canonical-definition boundary; future metadata changes can now drift across `add`, `update`, and `wizard`.

### lifecycle-contract | low | The committed lifecycle behavior is exactly preserved

The focused contract test projects every parameter field reaching the command runtime: kind, name, deferred annotation and hooks, choices, default kind and literal, help key, metavar, visibility, complete constraint tuple, transport, option declarations, flag behavior, cardinality, prompts, environment, eager state, and secret channels. It asserts the four affected command tuples in order. It also proves the shared records have exact identity, while `update` and `wizard` `notes` retain their distinct defaults (`None` versus empty string). The frozen `ArgumentSpec`, `OptionSpec`, nested contract records, and tuples make sharing immutable. The test oracle would reject field, declaration, default, help-key, ordering, or shared-identity mutations on the lifecycle surface, but it contains no intake-to-lifecycle identity assertion and thus cannot detect the remaining cross-file duplicate.

### successor-common-owner | medium | The original eight-record authority gap is resolved

The successors move `iva_category` and the seven metadata options into the public semantically named `app_ledger_invoice_common_command_parameters` module. `add`, `update`, and `wizard` all use the exact exported frozen objects at their original offsets. The expanded contract test covers `add` alongside every lifecycle command and asserts those cross-module identities, while retaining the distinct `counterparty_nif` requiredness and the `update` versus creation `notes` defaults.

### residual-add-wizard-parameter-authority | high | Ten field-identical create parameters still have separate definitions

The successor does not resolve the full intake/lifecycle clone family. After excluding the deliberately different `counterparty_nif`, `invoice add` and `invoice wizard` have 18 parameters with the same names and complete equality. Eight are now shared, but ten remain separate equal objects: `kind`, `counterparty_name`, `invoice_number`, `invoice_date`, `taxable_base`, `country_code`, `iva_rate`, `currency`, `recargo`, and `notes`. The fresh repository-owned scan reports 79 clones (0.38%) but still names target intake/lifecycle clones of 21, 123, and 37 lines. These are not command-specific facts: all ten declarations, defaults, help metadata, and positions relative to their nonshared `counterparty_nif` are independently equal. The test asserts their values but not their intended canonical identity, so a future edit can drift the two creation doors.

## Recommendations

Do not approve the consolidation yet. Retain the public owner introduced by the successors, but extend it to own the ten remaining fully substitutable create-parameter records and consume them at the existing offsets in both `add` and `wizard`. Preserve the separate optional-versus-required `counterparty_nif` records and their current positions. Extend the identity assertion across every newly shared record, keep the complete literal contract projection, and rerun the focused suite, Ruff, `ty`, and the whole-tree duplication audit. The audit can be approved when the invoice intake/lifecycle clone family no longer appears in that scan or is backed by a documented, non-substitutable contract difference.
