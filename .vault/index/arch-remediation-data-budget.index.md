---
generated: true
tags:
  - '#index'
  - '#arch-remediation-data-budget'
date: '2026-08-16'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:e924d98e45db75ef3cefdb40117ca01313ed2eff8a433ddfee423a6191664a9b'
related:
  - '[[2026-07-02-arch-remediation-data-budget-adr]]'
  - '[[2026-07-02-arch-remediation-data-budget-plan]]'
  - '[[2026-07-06-arch-remediation-data-budget-research]]'
---

# `arch-remediation-data-budget` feature index

Auto-generated index of all documents tagged with `#arch-remediation-data-budget`.

## Documents

### adr

- `2026-07-02-arch-remediation-data-budget-adr` - `arch-remediation-data-budget` adr: `Whole-tree and split-distribution data budgets` | (**status:** `accepted`)

### exec

- `2026-07-02-arch-remediation-data-budget-S01` - Add hatchling wheel excludes for src/aeat/**/tests/** and src/aeat/tests/** so no test module or fixture ships in the installed wheel
- `2026-07-02-arch-remediation-data-budget-S02` - Add a packaging content-boundary gate that builds the wheel and asserts no tests member is present
- `2026-07-02-arch-remediation-data-budget-S03` - Extend the packaging gate to assert the wheel contains the required data roots plus py.typed, the BIP-39 wordlist, and external_constants.toml so the exclude cannot silently strip functional payload
- `2026-07-02-arch-remediation-data-budget-S04` - Add a size-budget gate asserting the _data tree is at or under 550 MB, failing with a message that names the data-budget ADR and the two breach options raise-by-ADR or split
- `2026-07-02-arch-remediation-data-budget-S05` - Declare the corpus-split escape hatch as a named constant beside the budget carrying its target condition so the option is discoverable in code

### plan

- `2026-07-02-arch-remediation-data-budget-plan` - `arch-remediation-data-budget` plan

### research

- `2026-07-06-arch-remediation-data-budget-research` - `arch-remediation-data-budget` research: `program-track decision research bridge`
