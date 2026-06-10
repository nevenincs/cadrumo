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
comparison accept the member directly.

**Refined convention and resolution (P03.S04).** Closer analysis showed the
member-vs-`.value` choice is not "drop all `.value`": for a pydantic field
value, a call argument, a parameter or CLI-option default, or a return that
feeds a `str` contract, `.value` yields a clean plain `str` whose stored/passed
type is stable across a JSON round-trip, so `.value` is the correct form there.
The member is unambiguously better only in comparison, membership, and dict-key
positions, where `Modelo.M303 == x` reads cleaner and is behaviour-identical.
Under this convention most existing `.value` uses are already correct and the
actionable set is small. The clean comparison-position sites were converted
(`_registry_provider`, `_iva_wallet_gate`, `_verification_actions`,
`_filed_observation_persistence`); the remaining comparison-position cases live
in files a peer is converting organically, so they are left to that pass to
avoid concurrent-edit conflicts in the shared worktree. P03 is closed on the
convention plus the clean-site conversion rather than an 80-site churn.

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

**Disposition (P04) - delivered with verified BOE corpus.** The BOE text for
both provisions was fetched from the BOE Datos Abiertos consolidated-legislation
API (per-block endpoints `bloque/a14` and `bloque/a75`). RD 439/2007 art. 14 is
the value-establishing provision for the 3 por ciento amortisation, and Ley
19/1994 art. 75.1 (not art. 73, which is eligibility only) for the 50 por 100
REBECA exemption. Amortisation is fully registry-grounded: a full-text corpus
excerpt, the `rd-439-2007:art-14` catalogue entry, per-ejercicio parameters
2020-2025, and `_resolve_amortizacion_inmueble_rate` reading the registry with
the grounded constant as fallback, plus a grounding test. REBECA is
catalogue-grounded (corpus + `ley-19-1994:art-75` entry); a per-year registry
resolver was consciously NOT added because the maritime calculation has no
filing-year context and the 50 por 100 is a durable statutory fraction (the
leaf `REBECA_MARITIME_EXEMPTION_FRACTION` remains the value, now bound to the
catalogue). A pre-existing grounding bug was fixed in passing: the REBECA refs
cited the non-existent `BOE-A-1994-16100`; corrected to `BOE-A-1994-15794`. See
the verify-pass audit for the full disposition.

**Disposition (P03) - deferred, low value against high churn.** The member
versus `.value` inconsistency is benign because a `StrEnum` member equals,
hashes, and `str()`-formats identically to its value, and serialises the same in
JSON. Standardising removes roughly 80 `.value` suffixes across about 25 files,
several of which peers are concurrently editing in this shared worktree. The
cosmetic gain does not justify the churn and merge-conflict risk now; it is best
done as a single mechanical pass when the surrounding files are quiet.

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
