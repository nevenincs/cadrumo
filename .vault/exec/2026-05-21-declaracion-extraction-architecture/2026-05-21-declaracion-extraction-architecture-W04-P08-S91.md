---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-21'
modified: '2026-05-21'
step_id: S91
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-21-declaracion-extraction-architecture-adr]]'
---

# W04.P08.S91 - Record W02 review-fix removal of M347 and M840 dead profiles

## Outcome: Verified current state

Confirmed by inspecting `src/aeat/_data/registry/aeat/modelos/347.toml` and
`src/aeat/_data/registry/aeat/modelos/840.toml`:

- **M347** (`revisions."2008-y-siguientes"`): no `extraction_profiles` stanza
  present. The W02 code-review fix removed the dead `declaracion_pdf` profile
  that targeted `decl.tipo-declaracion` (data_type=text) with
  `match_strategy=numeric_casilla`.

- **M840** (`revisions."2003-y-siguientes"`): no `extraction_profiles` stanza
  present. Same removal.

Both modelos' constructs lack an `extraction_profiles =` field, consistent with
removal.

Consequence: W04.P14.S84 must author a real `named_label` profile for M347;
W04.P09.S26 / W04.P10.S32 must author a real `named_label` profile for M840.

The current committed state loads and validates cleanly (all 26 modelos pass the
snapshot-build gate) because the validator only rejects profiles that have
text-casilla targets with wrong strategy — absent profiles are not an error.

## Action

No code changes. This Step is a state-confirmation record only.
