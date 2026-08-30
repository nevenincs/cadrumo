---
tags:
  - '#audit'
  - '#calculation-correctness-campaign'
date: '2026-08-28'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:d1b3afbcd2a0f7394549b4058172953278b5f943d67f009aefad81a4c9a5d73a'
related: []
---

# `calculation-correctness-campaign` audit: `M210 IRNR: the art 25.1.a EU/EEA reduced rate is unreachable for canones and inmobiliaria`

## Correction

**The over-payment claim this audit originally made is WITHDRAWN.** It was
authored from reading the resolver and the parameter table, without driving the
engine. Driving the engine refutes it. The corrected finding is narrower and is
a naming/modelling defect, not a liability defect. The original text is
superseded in full by what follows; nothing was changed in production code,
registry data or tests at any point.

## What was claimed, and what the engine actually does

The claim was that an EU/EEA-resident filer declaring `canones` or
`inmobiliaria` is silently charged the 24 % general rate where TRLIRNR art.
25.1.a entitles them to 19 %, in the over-payment direction, with nothing
watching.

Driven against the real snapshot (`bundled_authority().snapshot('210',
filing_year=2025, period='0A')`, 10.000 EUR rendimientos, devengo 2025-12-31,
via `calculate_registry_snapshot`):

| `tipo_renta` | country | resolved rate | outcome |
|---|---|---|---|
| `canones` | IE | — | `M210_CONVENIO_RATE_MISSING` |
| `canones` | IT | — | `M210_CONVENIO_RATE_MISSING` |
| `canones` | DE | 0 | treaty exemption applied |
| `general` | IE / IT / DE | — | `M210_CONVENIO_RATE_MISSING` |
| `ue_residente` | IE / IT / DE | — | `M210_CONVENIO_RATE_MISSING` |

No configuration produced a silent 24 % charge on a declared EU/EEA resident.

The reason is in `_formula_runtime_irnr.py:92` `evaluate_irnr_resolve_tipo_gravamen`:
the domestic baseline is returned **only** under `if not country:`. Once a
fiscal-residence country is declared, a missing treaty row raises
`UnresolvedFormulaOutcomeError(M210_CONVENIO_RATE_MISSING)` rather than falling
back to the baseline, and the modelo verification workflow converts that into an
operator-facing finding post-engine. An empty country string never reaches the
branch either — the binding validator rejects it ("enum_binding
'm210-2025-profile-country-of-fiscal-residence' must be a non-empty string").

So the 24 % baseline is reachable only when no fiscal residence is declared at
all — precisely the filer who is not evidenced as an EU/EEA resident, for whom
the art. 25.1.a general rate is the correct charge. This is the
`no-silent-under-declaration` "typed unresolved outcome" design working as
intended, in the direction the original finding claimed was unwatched.

`canones` + DE resolving to 0 is likewise correct: the ES-DE convenio exempts
royalties at source, and the `ceiling` / `flat` override machinery applied it.

## What survives: a misleading model, not a wrong number

Two things in the original reading remain true and are worth recording, neither
of which changes a computed liability:

- The parameter table at
  `src/cadrumo/_data/registry/aeat/modelos/210/revisions/2025/parameters/0001-m210-tipo-gravamen-2025.toml`
  (byte-identical in `2026-y-siguientes/`, correctly so — art. 25 is year-stable)
  carries `ue_residente` as a *value* of an income-type enum, beside `canones`,
  `inmobiliaria` and `general`. Residence and income type are two axes of art.
  25.1.a collapsed into one lookup key.
- That file's own comment for `canones` — "La reduccion al 19% para residentes
  UE/EEE del art 25.1.a se alcanza por el concepto `ue_residente`" — describes a
  path that, as the table above shows, does not actually reach 19 % either: a
  declared country sends every `tipo_renta` through the convenio branch. The
  comment describes an election that the resolver does not honour in the way the
  prose implies.

The practical consequence is confined to filers resident in an EU/EEA state whose
convenio is **not bundled** (only AR, BE, DE, FR, GB, MA, NL, PT, US ship). Those
filers receive a finding rather than a figure. That is the safe direction, and it
is the same gap already recorded for M360 (LIVA art. 119 not catalogued) —
missing bundled treaty and directive text, not a defective calculation.

## Method note

This is the second instance in this campaign of the same error shape: calling a
registry state a defect from a static reading. The first was the M100 2025
relief casillas (reverted in `8258892c64`, audit corrected in `d35d2894ca`). The
standing lesson was "grep the tests for the casilla id before calling a registry
state a defect". It generalises, and the generalisation is the durable one:

**Before asserting a computed-liability defect, DRIVE THE ENGINE and read the
`unresolved_outcomes`.** A resolver that appears to fall back to a restrictive
default may instead raise a typed unresolved outcome one branch further down. A
static reading cannot see which branch is live; three lines of
`calculate_registry_snapshot` can.

The `no-silent-under-declaration` organising question stays sound — the answer
here was simply that something *does* watch that direction.
