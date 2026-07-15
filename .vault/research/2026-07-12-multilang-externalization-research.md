---
tags:
  - '#research'
  - '#multilang-externalization'
date: '2026-07-12'
modified: '2026-07-12'
related:
  - "[[2026-05-04-multilang-externalization-phase1-plan]]"
  - '[[2026-07-12-multilang-externalization-adr]]'
---

# `multilang-externalization` research: `current localization architecture reconciliation`

Re-ground the 2026-05-04 externalization plan before any unchecked legacy row
is treated as current work. The review used `vaultspec-rag`, targeted source
searches, and the current localization implementation and conformance tests.

## Findings

### Current implementation

The external-catalogue outcome of the earlier decision is present: the project
declares `python-i18n`, carries the four YAML catalogues under
`src/aeat/locales/`, and lazy-initialises the renderer in
`src/aeat/core/i18n/_render.py`. The supported output-language set is
`es`, `en`, `ca`, and `hu`.

`src/aeat/core/i18n/_translatable.py` defines `Translatable` as a strict
string subtype for abstract translation keys. It is not the old inline
multilingual payload: callers import it as `tr` to make keys identifiable and
the renderer resolves the key from the active catalogue. The current
`test_translatable_contract.py`, locale coverage tests, placeholder-parity
tests, and locale manager are the active guardrails. The later authority
indirections reference classifies `Translatable as tr` as a valid internal
alias, not a compatibility shim.

### Drift in the accepted ADR and plan

The accepted phase-1 ADR and its unstructured 30-row manual-remediation list
require deletion of the whole `core/i18n` module and every `Translatable`
type. Those instructions directly contradict the working architecture above.
They also name superseded file layouts and a CLI-local initializer that no
longer owns rendering. Completing those rows literally would remove the
current typed-key contract and its real-behavior guard suite.

The valid historical intent is narrower: remove inline language-value payloads
and centralize renderable user text in YAML. The plan provides no current
evidence that an inline `tr(t(es=..., en=..., ca=..., hu=...))` form remains,
while it overreaches by classifying the current key marker and supported
language enum as forbidden remnants.

### Recommended disposition

A replacement ADR should supersede the contradictory phase-1 ADR/plan rather
than amend it silently. It should retain the central YAML catalogues,
`python-i18n` rendering, the typed `Translatable` key token, and the four
output languages; declare the forbidden form precisely as inline language
payloads or unscanned user-facing literals; and route documentation
localization as a separately scoped surface. Until that decision is accepted,
the 30 old unchecked entries are retired design instructions, not safe
implementation tasks.

The user reserved ADR authoring to Sol, so this research is evidence only and
does not change ADR status or plan checkboxes.
