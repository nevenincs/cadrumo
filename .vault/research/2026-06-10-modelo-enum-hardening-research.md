---
tags:
  - '#research'
  - '#modelo-enum-hardening'
date: '2026-06-10'
related: []
---



# `modelo-enum-hardening` research: `Modelo-enum sweep: residual inconsistencies and latent problems`

During the in-session Modelo-enum and regulatory-value centralisation campaign,
an honest discovery pass quantified the residuals the sweep left and the latent
problems it touched, so the follow-on plan is grounded in evidence rather than
assumption. All counts are over production code with test files excluded.

## Findings

### F1 - Member-versus-value inconsistency (quality)

A raw count found 81 `Modelo.M###.value` string uses against 67 bare-member
`Modelo.M###` uses, with most converted files mixing both. The agents that drove
much of the sweep defaulted to `.value` even where strict-pydantic and StrEnum
comparison accept the member directly. Decision: prefer the member in
comparison, membership, dict-key, and str-field positions; reserve `.value` for
a genuine plain-str contract.

### F2 - Literal-annotation defaults (5 sites)

Five fields use `field: Literal["<code>"] = "<code>"` (in `borrador/_schema.py`,
`sede/_schema.py`, `registry/_ledger_bindings.py` twice, and
`renta/_ledger_expenses.py`). The CI gate excludes these as already
type-constrained, but they can be tightened to `Literal[Modelo.M<code>]` so the
enum is the single source.

### F3 - `modelo: str` fields with `max_length=8` (risk)

Fifteen-plus pydantic and dataclass fields declare `modelo: str` with
`max_length=8`. The `8` (against a three-digit code) signals these may carry
composite or loosely-validated forms, so retyping to `Modelo` needs per-field
investigation rather than a blind change; some may legitimately stay `str`.

**Verdict (P01.S02):** every such field uses `Field(min_length=1, max_length=8)`,
a deliberately loose bound that is neither the 3-digit `ModeloCode` shape
validator nor the closed `Modelo` set. Retyping to `Modelo` would over-constrain
the field to the 31 enum codes and risk rejecting a valid persistence or wire
input (a future or non-standard code the loose bound was chosen to admit), so
these fields are left as `str`. Tightening to `ModeloCode` (3-digit shape) is
plausible but unverified per producer and out of proportion to the cosmetic
gain. P05 is therefore closed as "investigated; no retype warranted", satisfying
the plan's field-disposition criterion by documented decision rather than inline
comments.

### F4 - Registry-resolver gap for two rates

`AMORTIZACION_INMUEBLE_RATE` (3 percent, RD 439/2007 art. 14.2) and
`REBECA_MARITIME_EXEMPTION_FRACTION` (50 percent, Ley 19/1994) are leaf
constants, unlike the rental reduction rates in `_tier_resolver.py` which
already read from the registry with a constant fallback. Routing these two
through the same pattern closes the gap.

### F5 - Gate false positives (2)

The AST gate's allowlist carries two non-modelo strings that read as codes: a
quarter-digit membership test `work_unit.period[0] in "123"` and a RIRPF article
number `"100"` in a citation blocklist. The first can be refactored so it no
longer pattern-matches a modelo; the second is inherent and stays allowlisted
with a reason.

### F6 - Retired-code modelling (resolved in-session)

`M037` (censo simplificada, suppressed by Orden HAC/1526/2024) is a real modelo
with code support but no registry definition. It was initially excluded because
the enum was generated from `registry_modelo_codes()`. Resolved by adding `M037`
plus a `NON_REGISTRY_MODELOS` carve-out and adjusting the parity gate and the
authorization fleet; recorded here as the precedent for any future
retired-but-supported code.
