---
generated: true
tags:
  - '#index'
  - '#cli-operator-surface'
date: '2026-06-10'
related:
  - '[[2026-06-10-cli-operator-crud-matrix-audit]]'
  - '[[2026-06-10-cli-operator-surface-W01-P01-S01]]'
  - '[[2026-06-10-cli-operator-surface-W01-P01-S02]]'
  - '[[2026-06-10-cli-operator-surface-W01-P01-S03]]'
  - '[[2026-06-10-cli-operator-surface-W01-P01-S04]]'
  - '[[2026-06-10-cli-operator-surface-W01-P01-S05]]'
  - '[[2026-06-10-cli-operator-surface-W01-P01-S06]]'
  - '[[2026-06-10-cli-operator-surface-W01-P03-S11]]'
  - '[[2026-06-10-cli-operator-surface-W01-P03-S12]]'
  - '[[2026-06-10-cli-operator-surface-W01-P03-S13]]'
  - '[[2026-06-10-cli-operator-surface-W01-P03-S14]]'
  - '[[2026-06-10-cli-operator-surface-adr]]'
  - '[[2026-06-10-cli-operator-surface-audit]]'
  - '[[2026-06-10-cli-operator-surface-plan]]'
  - '[[2026-06-10-cli-operator-surface-research]]'
---

# `cli-operator-surface` feature index

Auto-generated index of all documents tagged with `#cli-operator-surface`.

## Documents

### adr

- `2026-06-10-cli-operator-surface-adr` - `cli-operator-surface` adr: `operator surface verb, lifecycle, and honesty decisions` | (**status:** `accepted` -- operator approval with caveats recorded 2026-06-10)

### audit

- `2026-06-10-cli-operator-crud-matrix-audit` - `cli-operator-surface` audit: `CRUD and workflow capability validation of the operator CLI`
- `2026-06-10-cli-operator-surface-audit` - `cli-operator-surface` audit: `operator surface design weaknesses from the userdocs campaign`

### exec

- `2026-06-10-cli-operator-surface-W01-P01-S01` - add a test-time conformance gate that pins next-action and failure-hint strings naming a command path to a live command, mirroring the documented-command gate mechanism
- `2026-06-10-cli-operator-surface-W01-P01-S02` - extend the conformance gate to assert every Typer option typed as an enum has its advertised choice set equal to the set the handler accepts, failing on any advertised member the handler refuses
- `2026-06-10-cli-operator-surface-W01-P01-S03` - narrow the doclink --source enum choice to the three members the handler accepts or widen the handler so the advertised set matches, satisfying the new gate
- `2026-06-10-cli-operator-surface-W01-P01-S04` - narrow the work verify --select choices to the states verify accepts so latest-verified and filed stop being advertised-but-impossible, satisfying the new gate
- `2026-06-10-cli-operator-surface-W01-P01-S05` - correct the evidence-id help string that promises unambiguous prefix to state exact-equality matching, via the aeat.locales CLI
- `2026-06-10-cli-operator-surface-W01-P01-S06` - run the documented-command conformance gate and the new D5 gate to confirm zero drift across hint strings and enum-choice sets
- `2026-06-10-cli-operator-surface-W01-P03-S11` - run a feasibility spike on deferring help-text rendering until after eager-option resolution to determine whether --language can be made to actually localize help text without destabilising the import-time i18n model
- `2026-06-10-cli-operator-surface-W01-P03-S12` - implement the highest feasible D6 outcome in ordering work-then-remove-then-warn: make --language localize help text if the spike succeeds, else remove it from the help surface it cannot affect, else emit a one-line warning naming AEAT_OUTPUT_LANGUAGE
- `2026-06-10-cli-operator-surface-W01-P03-S13` - add real-behavior tests proving --language no longer silently fails for help text, asserting the chosen outcome and leaving the profile-owned precedence and AEAT_OUTPUT_LANGUAGE override unchanged
- `2026-06-10-cli-operator-surface-W01-P03-S14` - update locale strings via the aeat.locales CLI for any new warning text and regenerate the CLI reference if the flag surface changes

### plan

- `2026-06-10-cli-operator-surface-plan` - `cli-operator-surface` `operator surface hardening rollout` plan

### research

- `2026-06-10-cli-operator-surface-research` - `cli-operator-surface` research: `operator surface weaknesses and prior-decision reconciliation`
