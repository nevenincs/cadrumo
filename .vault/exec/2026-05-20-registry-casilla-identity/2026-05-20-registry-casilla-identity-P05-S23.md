---
tags:
  - '#exec'
  - '#registry-casilla-identity'
date: '2026-05-20'
modified: '2026-05-20'
step_id: 'S23'
related:
  - '[[2026-05-20-registry-casilla-identity-plan]]'
  - '[[2026-05-20-registry-casilla-identity-adr]]'
  - '[[2026-05-20-registry-casilla-identity-research]]'
---

# `registry-casilla-identity` `P05.S23`

Attempted to author calculation-completeness manifests for every
calculation-bearing modelo. Outcome: a structural finding — the
manifest-derivation tooling can produce a manifest only for Modelo 200.
No manifests were authored beyond M200, the gate was not weakened, and
the modelos that cannot be manifested are inventoried below for
follow-up.

- No files created or modified. This Step is a reported finding per the
  plan's explicit instruction: "if a modelo's calculation closure has a
  genuinely missing or ungrounded casilla, do NOT author a manifest that
  hides it and do NOT weaken the gate — record that modelo + the gap as
  a reported finding for follow-up, and skip its manifest."

## Description

The off-load-path `derive_calculation_completeness_casillas` tool derives
a modelo's calculation closure and intersects it with the official AEAT
Diseño de Registros. The intersection is keyed on the five-digit casilla
tag AEAT embeds in Diseño field text as `[NNNNN]` (regex `_CASILLA_TAG_RE`
in `_record_design.py`).

Running the derivation across all 26 modelos shows the tool yields a
non-empty manifest for exactly one modelo — Modelo 200 — and an empty
intersection for every other calculation-bearing modelo.

### Finding 1 — the manifest-derivation tooling is M200-only

The calculation-completeness manifest is derived as
`calculation closure ∩ Diseño five-digit [NNNNN] tags`. Modelo 200 is
the only modelo whose registry casilla `number`s are genuine five-digit
AEAT Diseño tags (`00592`, `00599`). Every other modelo identifies
casillas with a different vocabulary:

- semantic slugs (`iva.repercutido.general`, `decl.retenciones-total`,
  `compensacion-generada-periodo`, `tipo-declaracion`, `ejercicio`);
- short ordinal numbers (`01`, `02`, `03`);
- position-range numbers (`136-144`, `145-160`).

Those Diseños carry **zero** `[NNNNN]` five-digit tags, so the
derivation finds an empty intersection. A `CalculationCompletenessManifest`
must enumerate at least one casilla (schema validator), and the
off-load-path drift re-verification test asserts the checked-in manifest
equals the freshly re-derived set. Hand-authoring a manifest for one of
these modelos would therefore either fail the non-empty validator or, if
populated with the closure casillas, fail the drift test because
re-derivation yields an empty set. Authoring such a manifest is not
possible without either weakening the gate or breaking the drift test —
both forbidden.

This is a **tooling gap, not a registry defect**: the closure casillas
of these modelos are all declared in the registry and all carry their
`legal_refs` / `source_refs` grounding (verified — no closure casilla
across any modelo is ungrounded). The gate has nothing to red for them;
the derivation simply cannot express their manifest. Generalising
`derive_calculation_completeness_casillas` to the non-five-digit
casilla-number vocabularies is the follow-up task.

### Finding 2 — the closure walker keeps id/number token-form mismatches

`calculation_closure_numbers` reduces reference tokens to bare `number`s
via an `id → number` map and keeps an unmapped token verbatim (so the
M200 missing-casilla defect class still surfaces). For modelos whose
formulas reference casillas by `id` rather than `number` — Modelo 180
targets `decl.total-perceptores` (an `id`), Modelo 100 mixes `id`-form
and `number`-form references — the verbatim-kept token is an `id`, not a
missing casilla. The closure for M100, M130, M180, M190, M193, M390
consequently lists tokens that look "undeclared" but are `id`-form
references to casillas that *are* declared. This is a minor imprecision
in the closure helper, not a registry gap; it is recorded so a future
manifest-derivation generalisation resolves both `id` and `number`
reference forms before intersecting with the Diseño.

### Per-modelo inventory

Calculation-bearing modelos for which a manifest could NOT be authored
(closure size shown; all closure casillas declared and grounded; Diseño
carries no five-digit tags so derivation yields zero):

- M036 (closure 2), M111 (12), M115 (4), M123 (5 / 13 across two
  revisions), M130 (24), M131 (15, four revisions), M180 (6, two
  revisions), M184 (6), M190 (22), M193 (6), M202 (42 / 42 / 49 across
  three revisions), M232 (3, two revisions), M303 (17), M309 (3),
  M322 (8), M347 (2), M349 (4), M353 (8), M369 (2 / 2 / 4 across three
  schemas), M390 (18), M720 (2), M840 (2).
- M100 (closure 444–616 across six revisions) additionally has no
  `record_design`-kind source in its `source_refs`, so the derivation
  cannot even locate a Diseño corpus; it is the largest calculation
  surface and the most affected by Finding 1.

Modelo for which a manifest WAS authored and the gate is live (in
`P05.S22`):

- M200 2024-y-siguientes — closure `{(DP200014B, 00592),
  (DP200014B, 00599)}`, clears the gate.

## Tests

No code or data changed, so no new gate run is required for this Step.
The state confirmed by `P05.S22` and re-confirmed by `P05.S25` holds:
all 26 modelos load valid, the calculation-completeness gate is live for
M200 and rollout-staged dormant for every other modelo (each carries no
`completeness_manifest`, which the gate treats as a non-failure pending
manifest authoring). The finding above is the inventory the plan's S23
asks for: the gate is live for the one modelo that cleanly clears, and
every modelo that cannot yet be manifested is recorded with its cause.
